"""flightLoopV1 — suborbital experiment flight controller (threading framework).

First-pass threading implementation per CLAUDE.md. Each hardware device gets a
dedicated always-on worker thread. Threads talk only through queues. A watchdog
monitors heartbeats / liveness / queue depth and restarts stuck or crashed
workers, dropping to safe mode after too many failed restarts.

The *_ThreadManager functions are the worker bodies — fill in the hardware calls
(marked TODO). The framework around them (heartbeat, watchdog, restart, safe
mode, command routing) is implemented here.

Author: Braedon Larsen
"""

import os
import sys
import threading
import queue
import time
import logging

# This file lives in flightCode/, but the hardware packages (pickeringControls,
# spacecraftSerial) live at the repo root. Put the repo root on sys.path so the
# imports below resolve however the file is launched (direct run, double-click,
# or Windows service), not just via `python -m`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickeringControls.pickeringInterface as PI
import spacecraftSerial.RS422 as craftSerial
import RelayCode as relayControls

# ---------------------------------------------------------------------------
# Tunable constants  (SCREAMING_SNAKE kept — idiomatic for module constants)
# ---------------------------------------------------------------------------
SERIAL_PORT          = "COM3"      # spacecraft RS-422 bus
SERIAL_BAUD          = 9600
RELAY_PORT           = "COM1"      # Numato USB relay board
RELAY_BAUD           = 19200

HEARTBEAT_TIMEOUT    = 5.0         # s before a thread is considered stuck
WATCHDOG_INTERVAL    = 1.0         # s between watchdog passes
QUEUE_DEPTH_WARN     = 10          # qsize -> warning log
QUEUE_DEPTH_ALARM    = 50          # qsize -> critical log
THREAD_RESTART_LIMIT = 3           # restart attempts before safe mode
JOIN_TIMEOUT         = 3.0         # s to wait on a thread during shutdown
WORKER_GET_TIMEOUT   = 0.2         # s — every queue.get uses this, never blocks

PXI_HEALTH_INTERVAL  = 5.0         # s between PXI connection ping checks
PXI_REINIT_LIMIT     = 3           # failed reinit attempts before safe mode


# ---------------------------------------------------------------------------
# Shared state — the ONLY mutable state shared across threads
# ---------------------------------------------------------------------------
stopEvent     = threading.Event()    # set to shut every thread down cleanly
safeModeEvent = threading.Event()    # set once safe mode has been triggered

commandQueue  = queue.Queue()        # serial RX  -> dispatcher
pxiQueue      = queue.Queue()        # dispatcher -> PXI worker
relayQueue    = queue.Queue()        # dispatcher -> relay worker
logQueue      = queue.Queue()        # any thread -> logger (never blocks caller)

heartbeat     = {}                   # dict[threadName, time.monotonic()] 
heartbeatLock = threading.Lock()     # protects heartbeat dict

restartCounts  = {}                   # threadName -> failed-restart count
threads        = {}                   # threadName -> live threading.Thread

pxiLock        = threading.Lock()    # protects pxiWaves during watchdog reinit
pxiReinitCount = 0                   # failed PXI reinit attempts


# ---------------------------------------------------------------------------
# Hardware handles — populated by initHardware(), consumed by the workers
# ---------------------------------------------------------------------------
pxiWaves      = []     # list of waveAtributes (3 per card) returned by initPXIE()
relaySer      = None   # serial.Serial to the Numato board
craftListener = None   # craftSerial.RS422 instance
craftController = None  # relayControls.RelayController instance

# ---------------------------------------------------------------------------
# Experiment state 
# ---------------------------------------------------------------------------
relayStates    = [False, False, False, False]
#If a specifc craft signal has been recived 
signalStates: dict[str, bool] = {"sep": False , "zgStart": False, "zgStop": False}
#The time that the signal was recived
signalTimestamps: dict[str, float] = {"sep": 0.0, "zgStart": 0.0, "zgStop": 0.0}
# waveform state is carried by each waveAtributes object inside pxiWaves


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log = logging.getLogger("flight")


def configureLogging():
    """Root logging config — file + stream, threadName in every record."""
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    fmt = logging.Formatter(
        "%(asctime)s [%(threadName)s] %(levelname)s: %(message)s"
    )
    fileHandler = logging.FileHandler(f"flight_{timestamp}.log")
    fileHandler.setFormatter(fmt)
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(fileHandler)
    root.addHandler(streamHandler)


def logMsg(level, message):
    """Enqueue a (level, message) tuple for the telemetry/logger thread.

    Never blocks the calling worker. Workers should use this rather than
    touching the logging module directly so all I/O happens on one thread.
    """
    logQueue.put((level, message))


def _emitLog(level, message):
    """Actually write a log record — called only from the logger thread."""
    log.log(getattr(logging, str(level).upper(), logging.INFO), message)


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------
def updateHeartbeat(threadName):
    """Stamp this thread as alive. Call once per worker-loop iteration."""
    with heartbeatLock:
        heartbeat[threadName] = time.monotonic()


# ---------------------------------------------------------------------------
# Command routing
# ---------------------------------------------------------------------------
def routeCommand(cmd):
    """Route one parsed spacecraft command to the right hardware queue.

    Commands are strings prefixed by destination. Everything is logged.
    Extend the prefix table as the command protocol is defined.
    """
    logMsg("INFO", f"Command received: {cmd!r}")
    text = cmd.strip() if isinstance(cmd, str) else cmd

    if isinstance(text, str) and text.startswith("PXI:"):
        pxiQueue.put(text)
    elif isinstance(text, str) and text.startswith("RELAY:"):
        relayQueue.put(text)
    else:
        # TODO: define remaining command prefixes / payload format
        logMsg("WARNING", f"Unrouted command: {cmd!r}")


# ===========================================================================
# Worker threads  (the *_ThreadManager bodies — fill in the hardware calls)
# ===========================================================================
#
# Every worker obeys the same contract:
#   * loop while not stopEvent.is_set()
#   * queue.get(timeout=WORKER_GET_TIMEOUT) — never a blocking get
#   * catch queue.Empty and just loop (lets stopEvent be re-checked)
#   * catch Exception, log it, keep going (no silent failures, no crash-out)
#   * call updateHeartbeat(<name>) every iteration
# ---------------------------------------------------------------------------

def craftSerial_ThreadManager():
    """SerialRX + dispatch: read the spacecraft bus and route commands.

    The RS422 listener owns its own reader/processor threads, so here we poll
    its registered signals and forward anything detected into routeCommand().
    """
    name = "SERIAL"
    
    while not stopEvent.is_set():
        try:

            # TODO: replace with the real signal set / read API once defined.
            #   e.g. for sig in ("launch", "abort"):
            #            value = craftListener.detected(sig)
            #            if value:
            #                routeCommand(value)
            pass
        except Exception as e:
            logMsg("ERROR", f"{name} worker error: {e}")
            time.sleep(0.5)   # back-off so a dead port can't spin the CPU
        updateHeartbeat(name)
        time.sleep(WORKER_GET_TIMEOUT)


def pxi_ThreadManager():
    """LXIWorker: drive the Pickering 60-105 / 41-620 function generators."""
    name = "PXI"
    while not stopEvent.is_set():
        try:
            cmd = pxiQueue.get(timeout=WORKER_GET_TIMEOUT)
            # TODO: parse cmd -> wave index + new parameters, then:
            #   with pxiLock:
            #       wave = pxiWaves[idx]
            #       wave.setFrequency(...); wave.setAmplitude(...); etc.
            #       PI.updateWaveform(wave._card, wave)
            # Acquire pxiLock around any pxiWaves access — the watchdog may
            # replace the list during a reinit.
            logMsg("INFO", f"{name} handling: {cmd!r}")
        except queue.Empty:
            pass
        except Exception as e:
            logMsg("ERROR", f"{name} worker error: {e}")
        updateHeartbeat(name)


def relay_ThreadManager():
    """RelayWorker: drive the Numato USB relay board (ASCII serial protocol)."""
    name = "RELAY"
    while not stopEvent.is_set():
        try:
            cmd = relayQueue.get(timeout=WORKER_GET_TIMEOUT)
            for i, relay in enumerate(relayStates):
                if relay: 
                    craftController.turnOnRelay(i)
                    logMsg("INFO", f"Relay {i} turned ON")
                else: 
                    craftController.turnOffRelay(i)
                    logMsg("INFO", f"Relay {i} turned OFF")
            logMsg("INFO", f"{name} handling: {cmd!r}")
        except queue.Empty:
            pass
        except Exception as e:
            logMsg("ERROR", f"{name} worker error: {e}")
        updateHeartbeat(name)


def telemetry_ThreadManager():
    """Logger: drain logQueue to disk/stream. Keeps draining after stopEvent."""
    name = "TELEM"
    while not stopEvent.is_set():
        try:
            level, message = logQueue.get(timeout=WORKER_GET_TIMEOUT)
            _emitLog(level, message)
        except queue.Empty:
            pass
        except Exception as e:
            # Use logging directly here — never re-enqueue from the logger.
            log.error("TELEM worker error: %s", e)
        updateHeartbeat(name)

    # Flush anything still queued so final flight events are not lost.
    while True:
        try:
            level, message = logQueue.get_nowait()
            _emitLog(level, message)
        except queue.Empty:
            break


# ===========================================================================
# Thread factories + restart  (factory lambdas let us rebuild a Thread object)
# ===========================================================================
THREAD_FACTORIES = {
    "SERIAL": lambda: threading.Thread(
        target=craftSerial_ThreadManager, name="SERIAL", daemon=True),
    "PXI":    lambda: threading.Thread(
        target=pxi_ThreadManager,         name="PXI",    daemon=True),
    "RELAY":  lambda: threading.Thread(
        target=relay_ThreadManager,       name="RELAY",  daemon=True),
    "TELEM":  lambda: threading.Thread(
        target=telemetry_ThreadManager,   name="TELEM",  daemon=True),
}


def startThread(name):
    """Build a fresh Thread from its factory, register it, stamp it, start it."""
    t = THREAD_FACTORIES[name]()
    threads[name] = t
    updateHeartbeat(name)            # pre-stamp so it isn't instantly "stale"
    t.start()
    return t


def restartThread(name):
    """Restart a dead/stuck worker. Trip safe mode once the limit is hit."""
    restartCounts[name] = restartCounts.get(name, 0) + 1
    count = restartCounts[name]

    if count > THREAD_RESTART_LIMIT:
        logMsg("CRITICAL",
               f"{name} exceeded {THREAD_RESTART_LIMIT} restarts — safe mode")
        triggerSafeMode()
        return

    logMsg("WARNING", f"Restarting {name} (attempt {count})")
    try:
        startThread(name)
    except Exception as e:
        logMsg("CRITICAL", f"Failed to restart {name}: {e}")
        triggerSafeMode()


# ===========================================================================
# PXI hardware health
# ===========================================================================
def checkPXIHealth():
    """Ping every open card by reading its CardId. Returns True if all respond.

    CardId() is a lightweight read over the PXI bus. A pilpxi.Error or any
    other exception means that card (or the whole cabinet) is not responding.
    Called from the watchdog — always holds pxiLock before entering.
    """
    if not pxiWaves:
        logMsg("WARNING", "PXI health check: no waves registered")
        return False
    seen = set()
    for i, wave in enumerate(pxiWaves):
        card = wave._card
        if id(card) in seen:
            continue
        seen.add(id(card))
        try:
            card.CardId()
        except Exception as e:
            logMsg("ERROR", f"PXI health check: card {i // 3} not responding ({e})")
            return False
    return True


def reinitPXI():
    """Close all existing card handles and re-run initPXIE().

    Replaces pxiCards in-place under pxiLock so the PXI worker always sees a
    consistent list. Increments pxiReinitCount; triggers safe mode when the
    limit is exceeded.
    """
    global pxiWaves, pxiReinitCount
    pxiReinitCount += 1

    if pxiReinitCount > PXI_REINIT_LIMIT:
        logMsg("CRITICAL",
               f"PXI reinit exceeded {PXI_REINIT_LIMIT} attempts — safe mode")
        triggerSafeMode()
        return

    logMsg("WARNING", f"PXI reinit attempt {pxiReinitCount}")

    # Close unique card handles before rebuilding — ignore errors on close.
    with pxiLock:
        seen = set()
        for wave in pxiWaves:
            card = wave._card
            if id(card) not in seen:
                seen.add(id(card))
                try:
                    card.Close()
                except Exception:
                    pass
        pxiWaves.clear()

        try:
            newWaves = PI.initPXIE()
            if newWaves:
                pxiWaves.extend(newWaves)
                n_cards = len(pxiWaves) // 3
                logMsg("INFO", f"PXI reinit succeeded: {n_cards} card(s) restored")
                pxiReinitCount = 0   # reset count on a clean recovery
            else:
                logMsg("ERROR", "PXI reinit returned no waves")
        except Exception as e:
            logMsg("ERROR", f"PXI reinit failed: {e}")


# ===========================================================================
# Watchdog
# ===========================================================================
def watchdog_ThreadManager():
    """Health monitor: liveness, heartbeat staleness, queue depth, PXI hardware.

    Runs every WATCHDOG_INTERVAL. Not auto-restartable from within itself —
    the main loop is the backstop if the watchdog ever dies.
    """
    name = "WATCHDOG"
    monitoredQueues = {
        "command": commandQueue,
        "pxi":     pxiQueue,
        "relay":   relayQueue,
        "log":     logQueue,
    }
    lastPXICheck = 0.0   # monotonic timestamp of the last PXI ping

    while not stopEvent.is_set():
        now = time.monotonic()

        # --- per-thread health ---
        for tName in list(THREAD_FACTORIES.keys()):
            t = threads.get(tName)

            # 1. Hard failure — the thread object died.
            if t is None or not t.is_alive():
                logMsg("ERROR", f"{tName} not alive — restarting")
                restartThread(tName)
                continue

            # 2. Soft failure — heartbeat too old (deadlock / stuck I/O).
            with heartbeatLock:
                last = heartbeat.get(tName, 0.0)
            if now - last > HEARTBEAT_TIMEOUT:
                logMsg("ERROR",
                       f"{tName} heartbeat stale ({now - last:.1f}s) — restarting")
                restartThread(tName)

        # 3. Queue depth — a worker falling behind.
        for qName, q in monitoredQueues.items():
            depth = q.qsize()
            if depth >= QUEUE_DEPTH_ALARM:
                logMsg("CRITICAL", f"{qName} queue depth {depth} (alarm)")
            elif depth >= QUEUE_DEPTH_WARN:
                logMsg("WARNING", f"{qName} queue depth {depth} (warn)")

        # 4. PXI hardware health — ping cards on their own slower interval.
        if now - lastPXICheck >= PXI_HEALTH_INTERVAL:
            lastPXICheck = now
            with pxiLock:
                healthy = checkPXIHealth()
            if not healthy:
                logMsg("ERROR", "PXI health check failed — reinitialising connection")
                reinitPXI()

        updateHeartbeat(name)
        time.sleep(WATCHDOG_INTERVAL)


# ===========================================================================
# Safe mode
# ===========================================================================
def triggerSafeMode():
    """Drive all hardware to a known-inert state. Each action is isolated so
    one hardware failure cannot prevent the others from running.
    """
    if safeModeEvent.is_set():
        return                       # already safed — don't re-run
    safeModeEvent.set()
    logMsg("CRITICAL", "ENTERING SAFE MODE")

    # All Numato relay channels open.
    try:
        # TODO: for n in range(4): relaySer.write(f"relay off {n}\r".encode())
        logMsg("INFO", "Safe mode: relays opened")
    except Exception as e:
        logMsg("ERROR", f"Safe mode relay shutdown failed: {e}")

    # All PXI / function generator outputs zeroed.
    try:
        # TODO: for wave in pxiWaves: wave._card.PIFGLX_AbortGeneration(wave.getChannel())
        logMsg("INFO", "Safe mode: PXI outputs zeroed")
    except Exception as e:
        logMsg("ERROR", f"Safe mode PXI shutdown failed: {e}")

    # Fault signal to the spacecraft bus.
    try:
        # TODO: notify spacecraft of fault over craftListener / serial
        logMsg("INFO", "Safe mode: fault signalled to spacecraft")
    except Exception as e:
        logMsg("ERROR", f"Safe mode fault signal failed: {e}")


# ===========================================================================
# Hardware init + lifecycle
# ===========================================================================
def initHardware():
    """Bring up hardware before the worker threads start (see MainLoopOutline).

    Returns True on success. Failures are logged; decide per-device whether a
    failure is fatal as the self-checks are fleshed out.
    """
    global pxiWaves, relaySer, craftListener, relayController
    ok = True

    # --- Pickering PXI cabinet + function-generator self-check ---
    try:
        pxiWaves = PI.initPXIE()
        # TODO: PI.waveformSelfCheck([w._card for w in pxiWaves]) and act on the result
    except Exception as e:
        logMsg("ERROR", f"PXI init failed: {e}")
        ok = False


    # --- Spacecraft RS-422 listener ---
    try:
        craftListener = craftSerial.RS422(port=SERIAL_PORT, baud=SERIAL_BAUD)
        # TODO: craftListener.addSignal(...) for each flight command
        craftListener.start()
    except Exception as e:
        logMsg("ERROR", f"Craft serial init failed: {e}")
        ok = False
    # --- Relay controller Opening ---
    try:
        relayController = relayControls.RelayController(port = RELAY_PORT, baud = RELAY_BAUD)
    except Exception as e:
        logMsg("ERROR", f"Relay controller init failed: {e}")
        ok = False

    return ok


def shutdown():
    """Clean shutdown: stop everything, join with a bounded wait."""
    logMsg("INFO", "Shutdown requested")
    stopEvent.set()

    if craftListener is not None:
        try:
            craftListener.stop()
        except Exception as e:
            log.error("craftListener stop failed: %s", e)

    for name, t in threads.items():
        if name == "TELEM":
            continue                 # join the logger last so it can drain
        t.join(timeout=JOIN_TIMEOUT)

    telem = threads.get("TELEM")
    if telem is not None:
        telem.join(timeout=JOIN_TIMEOUT)


# ===========================================================================
# Main
# ===========================================================================
def main():
    configureLogging()
    log.info("Flight controller starting")

    # Logger first so init/hardware messages are captured.
    startThread("TELEM")

    if not initHardware():
        logMsg("WARNING", "Hardware init reported a failure — continuing")

    # Start the remaining workers (TELEM already running).
    for name in THREAD_FACTORIES:
        if name != "TELEM":
            startThread(name)

    # Start the watchdog.
    threads["WATCHDOG"] = threading.Thread(
        target=watchdog_ThreadManager, name="WATCHDOG", daemon=True)
    updateHeartbeat("WATCHDOG")
    threads["WATCHDOG"].start()

    # Main loop — supervise the watchdog and idle until shutdown.
    try:
        while not stopEvent.is_set():
            wd = threads.get("WATCHDOG")
            if wd is None or not wd.is_alive():
                logMsg("ERROR", "Watchdog died — restarting")
                threads["WATCHDOG"] = threading.Thread(
                    target=watchdog_ThreadManager, name="WATCHDOG", daemon=True)
                updateHeartbeat("WATCHDOG")
                threads["WATCHDOG"].start()
            time.sleep(1.0)
    except KeyboardInterrupt:
        logMsg("INFO", "KeyboardInterrupt — shutting down")
    finally:
        shutdown()


if __name__ == "__main__":
    main()
