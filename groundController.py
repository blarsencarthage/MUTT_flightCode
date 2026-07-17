
# Author: Braedon Larsen
# Created: 2026-06-11
# Updated: 2026-07-06
# Ground controller for 12-element phased array ultrasonic transducer system.
# Architecture matches testHarness: worker threads, queue-based commands,
# event-driven GUI updates via stateBus, and watchdog health monitoring.
# All controls connect to real hardware (PXI, relay board, RS-422 serial).

import csv
import logging
import math
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, ttk

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "spacecraftSerial"))

from pickeringControls.pickeringInterface import initPXIE, updateWaveform, waveAtributes
from relayControls.relaySerial import RelayController
import serial

# ══════════════════════════════════════════════════════════════════════════════
# HARDWARE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

NUM_PAIRS    = 6
NUM_RELAYS   = 4
NUM_CHANNELS = 6   # 2 cards × 3 channels

# pair_index → (card_list_index, channel_number)
CHANNEL_MAP = {
    0: (0, 1), 1: (0, 2), 2: (0, 3),
    3: (1, 1), 4: (1, 2), 5: (1, 3),
}

PAIR_COLORS = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948"]

# Normalized (x, y) in [0,1]² for each of the 12 transducers.
TRANSDUCER_XY = [
    # Row 0 — 2 elements
    (0.38, 0.10), (0.62, 0.10),
    # Row 1 — 4 elements
    (0.14, 0.35), (0.38, 0.35), (0.62, 0.35), (0.86, 0.35),
    # Row 2 — 4 elements
    (0.14, 0.60), (0.38, 0.60), (0.62, 0.60), (0.86, 0.60),
    # Row 3 — 2 elements
    (0.38, 0.85), (0.62, 0.85),
]

# transducer_index → pair_index
TRANSDUCER_PAIR = [2, 3, 4, 0, 1, 5, 5, 1, 0, 4, 3, 2]

# (key, label, hard_min, hard_max, default, slider_min, slider_max, fmt_spec)
PARAMS = [
    ("freq",   "Freq (Hz)",  100.0, 1_000_000.0, 40_000.0, 1_000.0, 200_000.0, ".0f"),
    ("amp",    "Amp (V)",      0.0,         5.0,      1.0,     0.0,       5.0,  ".3f"),
    ("offset", "Offset (V)",   0.0,         5.0,      0.0,     0.0,       5.0,  ".3f"),
    ("phase",  "Phase (°)",    0.0,       360.0,      0.0,     0.0,     360.0,  ".1f"),
]

WAVEFORM_NAMES = {
    0: "SINE", 1: "SQUARE", 2: "TRIANGLE",
    3: "RAMP_UP", 4: "RAMP_DOWN", 5: "DC",
    6: "PULSE", 7: "PWM", 8: "ARB",
}

# ══════════════════════════════════════════════════════════════════════════════
# PORT / TIMING CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

GROUND_CONFIGS_DIR = os.path.join(_HERE, "groundConfigs")

PXI_IP             = "169.254.112.5"
RELAY_PORT         = "COM5"
SERIAL_PORT        = "COM3"
SERIAL_BAUD        = 9600

WORKER_TIMEOUT     = 0.2    # s — queue.get() timeout
WATCHDOG_INTERVAL  = 1.0    # s — watchdog poll rate
HEARTBEAT_TIMEOUT  = 5.0    # s — staleness threshold
PXI_HEALTH_INTERVAL = 5.0   # s — PXI ping cadence
MAX_RESTARTS       = 3      # max auto-restarts before safe mode
QUEUE_DEPTH_WARN   = 10
QUEUE_DEPTH_ALARM  = 50

# 84-byte spacecraft frame format (matches spacecraftSerial/craftSerial.py)
CRAFT_SYNC       = bytes([0xAA, 0x55])
CRAFT_FRAME_LEN  = 84
SIGNAL_START     = 80   # absolute offset of first signal byte within packet
SIGNAL_BIT_START = 3    # first used bit in SIGNAL_START byte (MSB-first, bit 0 = MSB)

SIGNAL_NAMES: tuple[str, ...] = (
    # byte 80, bits 3-7
    "discrete03", "discrete02", "discrete01", "rcsRollLeft", "rcsRollRight",
    # byte 81, bits 0-7
    "rcsYawLeft", "rcsYawRight", "rcsPitchDown", "rcsPitchUp",
    "stoppedOnRunway", "approach", "reentryStart", "microgravityEnd",
    # byte 82, bits 0-7
    "apogee", "microgravityStart", "engineCutoff", "rocketFiring",
    "release", "minusTen", "takeOff", "extra",
)

# ══════════════════════════════════════════════════════════════════════════════
# THEME
# ══════════════════════════════════════════════════════════════════════════════

BG     = "#1e1e2e"
BG_ALT = "#252538"
BG_HL  = "#313150"
FG     = "#cdd6f4"
FG_DIM = "#8888aa"
GREEN  = "#a6e3a1"
RED    = "#f38ba8"
YELLOW = "#f9e2af"
BLUE   = "#89b4fa"

# ══════════════════════════════════════════════════════════════════════════════
# OBSERVABLE STATE BUS  (ported from testHarness/virtualHardware.py)
# ══════════════════════════════════════════════════════════════════════════════

class _Observable:
    def __init__(self):
        self._listeners = []
        self._lock = threading.Lock()

    def subscribe(self, fn):
        with self._lock:
            self._listeners.append(fn)

    def _notify(self, event, data):
        with self._lock:
            listeners = list(self._listeners)
        for fn in listeners:
            try:
                fn(event, data)
            except Exception:
                pass


stateBus = _Observable()

# ══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════════════

log = logging.getLogger("mutt")


def configureLogging():
    import datetime
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    fmt = logging.Formatter(
        "%(asctime)s [%(threadName)s] %(levelname)s: %(message)s")
    fh = logging.FileHandler(f"groundLog\ground_{ts}.log")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(fh)
    root.addHandler(sh)


def logMsg(level, message):
    """Enqueue a log message for the telemetry thread — never blocks the caller."""
    logQueue.put((level, message))


def _emitLog(level, message):
    """Write one log record — only called from the telemetry thread."""
    log.log(getattr(logging, str(level).upper(), logging.INFO), message)


# ══════════════════════════════════════════════════════════════════════════════
# SHARED STATE
# ══════════════════════════════════════════════════════════════════════════════

pxiWaves:       list          = []               # waveAtributes × 6 (3 per card)
relayStates:    list          = [False] * NUM_RELAYS
signalStates:   dict          = {name: False for name in SIGNAL_NAMES}
threads:        dict          = {}               # name → Thread
heartbeat:      dict          = {}               # name → monotonic timestamp
stopEvent:      threading.Event = threading.Event()
pxiLock:        threading.Lock  = threading.Lock()
heartbeatLock:  threading.Lock  = threading.Lock()
safeModeEvent:  threading.Event = threading.Event()
pxiQueue:       queue.Queue   = queue.Queue()
relayQueue:     queue.Queue   = queue.Queue()
logQueue:       queue.Queue   = queue.Queue()
restartCounts:  dict          = {}
pxiReinitCount: int           = 0
relayController: RelayController = None
lxiErrors:      list          = []   # timestamped error strings (newest last, max 200)
_lxiManagerWindow = None             # singleton Toplevel reference
relayErrors:    list          = []   # timestamped relay error strings (newest last, max 200)
_relayManagerWindow = None           # singleton Toplevel reference

# ══════════════════════════════════════════════════════════════════════════════
# ERROR LOG HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _lxi_append_error(msg: str) -> None:
    """Append a timestamped entry to lxiErrors (capped at 200 entries)."""
    lxiErrors.append(f"{time.strftime('%H:%M:%S')}  {msg}")
    if len(lxiErrors) > 200:
        lxiErrors.pop(0)


def _relay_append_error(msg: str) -> None:
    """Append a timestamped entry to relayErrors (capped at 200 entries)."""
    relayErrors.append(f"{time.strftime('%H:%M:%S')}  {msg}")
    if len(relayErrors) > 200:
        relayErrors.pop(0)


# ══════════════════════════════════════════════════════════════════════════════
# HEARTBEAT
# ══════════════════════════════════════════════════════════════════════════════

def updateHeartbeat(name):
    """Stamp this thread as alive. Called once per worker-loop iteration."""
    with heartbeatLock:
        heartbeat[name] = time.monotonic()


# ══════════════════════════════════════════════════════════════════════════════
# WORKER THREADS
# ══════════════════════════════════════════════════════════════════════════════

def pxi_worker():
    """Dequeue waveform commands and apply them to the real PXI hardware."""
    name = "PXI"
    while not stopEvent.is_set():
        try:
            item = pxiQueue.get(timeout=WORKER_TIMEOUT)
        except queue.Empty:
            updateHeartbeat(name)
            continue

        cmd = item[0]

        if cmd == "apply" and len(item) == 6:
            _, pair_idx, freq, amp, offset, phase = item
            card_idx, ch_num = CHANNEL_MAP[pair_idx]
            wave_idx = card_idx * 3 + (ch_num - 1)
            with pxiLock:
                if wave_idx < len(pxiWaves):
                    wave = pxiWaves[wave_idx]
                    wave.setFrequency(freq)
                    wave.setAmplitude(amp)
                    wave.setOffset(offset)
                    wave.setPhase(phase)
                    try:
                        updateWaveform(wave._card, wave)
                        try:
                            wf_name = WAVEFORM_NAMES.get(int(wave.getWaveformType()), "SINE")
                        except Exception:
                            wf_name = "SINE"
                        stateBus._notify("channel_update", {
                            "pair": pair_idx,
                            "freq": freq, "amp": amp,
                            "offset": offset, "phase": phase,
                            "waveform": wf_name, "generating": True,
                        })
                        logMsg("INFO",
                            f"PXI pair {pair_idx+1}: freq={freq:.0f}Hz "
                            f"amp={amp:.3f}V offset={offset:.3f}V phase={phase:.1f}°")
                    except Exception as e:
                        logMsg("ERROR", f"PXI apply pair {pair_idx+1}: {e}")
                        _lxi_append_error(f"apply pair {pair_idx+1}: {e}")
                else:
                    logMsg("WARNING",
                        f"PXI pair {pair_idx+1}: wave index {wave_idx} "
                        f"not available ({len(pxiWaves)} waveform(s) initialized)")

        elif cmd == "reinit":
            reinitPXI()

        elif cmd == "stop_all":
            with pxiLock:
                for wave in pxiWaves:
                    try:
                        wave._card.PIFGLX_AbortGeneration(wave.getChannel())
                    except Exception:
                        pass
            for p in range(NUM_PAIRS):
                c_idx, ch = CHANNEL_MAP[p]
                w_idx = c_idx * 3 + (ch - 1)
                if w_idx < len(pxiWaves):
                    w = pxiWaves[w_idx]
                    try:
                        wf_name = WAVEFORM_NAMES.get(int(w.getWaveformType()), "SINE")
                    except Exception:
                        wf_name = "SINE"
                    stateBus._notify("channel_update", {
                        "pair": p,
                        "freq": w.getFrequency(), "amp": w.getAmplitude(),
                        "offset": w.getOffset(), "phase": w.getPhase(),
                        "waveform": wf_name, "generating": False,
                    })
            logMsg("INFO", "PXI: all channels stopped")

        updateHeartbeat(name)


def relay_worker():
    """Dequeue relay commands and forward them to the RelayController."""
    name = "RELAY"
    while not stopEvent.is_set():
        try:
            item = relayQueue.get(timeout=WORKER_TIMEOUT)
        except queue.Empty:
            updateHeartbeat(name)
            continue

        if item[0] == "set" and len(item) == 3:
            _, relay_idx, state = item
            if relayController is not None:
                try:
                    if state:
                        relayController.signalRelayOn(relay_idx)
                    else:
                        relayController.signalRelayOff(relay_idx)
                    relayStates[relay_idx] = state
                    stateBus._notify("relay_update",
                                     {"relay": relay_idx, "state": state})
                    logMsg("INFO",
                           f"Relay {relay_idx} -> {'ON' if state else 'OFF'}")
                except Exception as e:
                    logMsg("ERROR", f"Relay {relay_idx} command failed: {e}")
                    _relay_append_error(f"relay {relay_idx} command failed: {e}")
            else:
                logMsg("WARNING", "Relay command ignored: controller not initialized")

        elif item[0] == "reconnect":
            new_port = item[1] if len(item) > 1 else RELAY_PORT
            _reconnect_relay(new_port)

        updateHeartbeat(name)


def serial_worker():
    """Read 84-byte craft frames from the spacecraft RS-422 port and update signalStates."""
    name = "SERIAL"
    while not stopEvent.is_set():
        ser = None
        try:
            ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=0.5)
            ser.reset_input_buffer()
            logMsg("INFO", f"SERIAL: connected to {SERIAL_PORT} @ {SERIAL_BAUD} baud")
            buf = bytearray()

            while not stopEvent.is_set():
                chunk = ser.read(256)
                if chunk:
                    buf.extend(chunk)

                while len(buf) >= CRAFT_FRAME_LEN:
                    idx = buf.find(CRAFT_SYNC)
                    if idx == -1:
                        buf.clear()
                        break
                    if idx + CRAFT_FRAME_LEN > len(buf):
                        if idx:
                            del buf[:idx]
                        break
                    frame = bytes(buf[idx: idx + CRAFT_FRAME_LEN])
                    del buf[:idx + CRAFT_FRAME_LEN]
                    _parse_craft_frame(frame)

                updateHeartbeat(name)

        except serial.SerialException as e:
            logMsg("WARNING", f"SERIAL: port error ({e}) — reconnecting in 2s")
        except Exception as e:
            logMsg("ERROR", f"SERIAL worker error: {e}")
        finally:
            if ser is not None and ser.is_open:
                ser.close()

        if not stopEvent.is_set():
            stopEvent.wait(2.0)
            updateHeartbeat(name)


def _parse_craft_frame(frame):
    raw_bits: list[bool] = []
    b = frame[SIGNAL_START]
    for bit in range(SIGNAL_BIT_START, 8):
        raw_bits.append(bool((b >> (7 - bit)) & 1))
    for offset in range(SIGNAL_START + 1, SIGNAL_START + 4):
        b = frame[offset]
        for bit in range(8):
            raw_bits.append(bool((b >> (7 - bit)) & 1))
    for key, state in zip(SIGNAL_NAMES, raw_bits):
        if state != signalStates.get(key, False):
            signalStates[key] = state
            stateBus._notify("signal_update", {"name": key, "state": state})
            if state:
                logMsg("INFO", f"SERIAL: {key} asserted")


def telemetry_worker():
    """Drain logQueue to the logging framework. Flushes remaining items on shutdown."""
    name = "TELEM"
    while not stopEvent.is_set():
        try:
            level, message = logQueue.get(timeout=WORKER_TIMEOUT)
            _emitLog(level, message)
        except queue.Empty:
            pass
        except Exception as e:
            log.error("TELEM error: %s", e)
        updateHeartbeat(name)

    while True:
        try:
            level, message = logQueue.get_nowait()
            _emitLog(level, message)
        except queue.Empty:
            break


# ══════════════════════════════════════════════════════════════════════════════
# THREAD FACTORIES  (mirrors flightController pattern)
# ══════════════════════════════════════════════════════════════════════════════

THREAD_FACTORIES = {
    "PXI":    lambda: threading.Thread(target=pxi_worker,       name="PXI",    daemon=True),
    "RELAY":  lambda: threading.Thread(target=relay_worker,     name="RELAY",  daemon=True),
    "SERIAL": lambda: threading.Thread(target=serial_worker,    name="SERIAL", daemon=True),
    "TELEM":  lambda: threading.Thread(target=telemetry_worker, name="TELEM",  daemon=True),
}


def startThread(name):
    t = THREAD_FACTORIES[name]()
    threads[name] = t
    updateHeartbeat(name)
    t.start()
    return t


def restartThread(name):
    restartCounts[name] = restartCounts.get(name, 0) + 1
    count = restartCounts[name]
    if count > MAX_RESTARTS:
        logMsg("CRITICAL", f"{name} exceeded {MAX_RESTARTS} restarts — entering safe mode")
        triggerSafeMode()
        return
    logMsg("WARNING", f"Restarting {name} (attempt {count}/{MAX_RESTARTS})")
    try:
        startThread(name)
    except Exception as e:
        logMsg("CRITICAL", f"Failed to restart {name}: {e}")
        triggerSafeMode()


# ══════════════════════════════════════════════════════════════════════════════
# PXI HARDWARE HEALTH  (mirrors flightController pattern)
# ══════════════════════════════════════════════════════════════════════════════

def checkPXIHealth():
    """Ping every open card. Returns True if all respond."""
    if not pxiWaves:
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
            logMsg("ERROR", f"PXI health: card {i // 3} not responding ({e})")
            _lxi_append_error(f"health check card {i // 3}: {e}")
            return False
    return True


def reinitPXI():
    """Close all card handles and re-run initPXIE() under pxiLock."""
    global pxiWaves, pxiReinitCount
    pxiReinitCount += 1
    if pxiReinitCount > MAX_RESTARTS:
        logMsg("CRITICAL",
               f"PXI reinit exceeded {MAX_RESTARTS} attempts — entering safe mode")
        triggerSafeMode()
        return
    logMsg("WARNING", f"PXI reinit attempt {pxiReinitCount}/{MAX_RESTARTS}")
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
            new_waves = initPXIE(PXI_IP)
            if new_waves:
                pxiWaves.extend(new_waves)
                logMsg("INFO",
                    f"PXI reinit OK: {len(new_waves) // 3} card(s) restored")
                pxiReinitCount = 0
            else:
                logMsg("ERROR", "PXI reinit returned no waves")
                _lxi_append_error("reinit returned no waves")
        except Exception as e:
            logMsg("ERROR", f"PXI reinit failed: {e}")
            _lxi_append_error(f"reinit failed: {e}")


def _reconnect_relay(new_port: str) -> None:
    """Stop the current RelayController and start a fresh one on new_port."""
    global relayController, RELAY_PORT
    RELAY_PORT = new_port
    try:
        if relayController is not None:
            relayController.stop()
    except Exception as e:
        _relay_append_error(f"stop on reconnect: {e}")
    try:
        relayController = RelayController(port=RELAY_PORT)
        relayController.start()
        logMsg("INFO", f"Relay reconnected on {RELAY_PORT}")
    except Exception as e:
        logMsg("ERROR", f"Relay reconnect failed: {e}")
        _relay_append_error(f"reconnect failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# GROUND CONFIGS  (save/load current card state as CSV, same shape as flight
# waveConfigs but without activeTime/settlingTime)
# ══════════════════════════════════════════════════════════════════════════════

GROUND_CONFIG_FIELDS = ["channel", "frequency", "amplitude", "offset", "phase", "waveform_type"]


def _ensureGroundConfigsDir():
    os.makedirs(GROUND_CONFIGS_DIR, exist_ok=True)


def listGroundConfigs():
    """Return sorted config names (without .csv) found in groundConfigs/."""
    _ensureGroundConfigsDir()
    return sorted(
        os.path.splitext(f)[0]
        for f in os.listdir(GROUND_CONFIGS_DIR)
        if f.lower().endswith(".csv")
    )


def saveGroundConfig(name):
    """Write the currently-applied hardware state (pxiWaves) to groundConfigs/<name>.csv."""
    _ensureGroundConfigsDir()
    path = os.path.join(GROUND_CONFIGS_DIR, f"{name}.csv")
    rows = []
    with pxiLock:
        for pair_idx in range(NUM_PAIRS):
            card_idx, ch_num = CHANNEL_MAP[pair_idx]
            wave_idx = card_idx * 3 + (ch_num - 1)
            if wave_idx >= len(pxiWaves):
                continue
            wave = pxiWaves[wave_idx]
            try:
                wf_name = WAVEFORM_NAMES.get(int(wave.getWaveformType()), "SINE")
            except Exception:
                wf_name = "SINE"
            rows.append([
                ch_num, wave.getFrequency(), wave.getAmplitude(),
                wave.getOffset(), wave.getPhase(), wf_name,
            ])
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(GROUND_CONFIG_FIELDS)
        writer.writerows(rows)
    return path


def loadGroundConfig(name):
    """Read groundConfigs/<name>.csv, one row per pair in CHANNEL_MAP order."""
    path = os.path.join(GROUND_CONFIGS_DIR, f"{name}.csv")
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "frequency": float(row["frequency"]),
                "amplitude": float(row["amplitude"]),
                "offset":    float(row["offset"]),
                "phase":     float(row["phase"]),
            })
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# WATCHDOG
# ══════════════════════════════════════════════════════════════════════════════

def watchdog_worker():
    """Monitor thread liveness, heartbeat staleness, queue depth, and PXI health."""
    name = "WATCHDOG"
    monitored_queues = {"pxi": pxiQueue, "relay": relayQueue, "log": logQueue}
    last_pxi_check = 0.0

    while not stopEvent.is_set():
        now = time.monotonic()

        for tName in list(THREAD_FACTORIES.keys()):
            t = threads.get(tName)
            if t is None or not t.is_alive():
                logMsg("ERROR", f"{tName} thread not alive — restarting")
                restartThread(tName)
                continue
            with heartbeatLock:
                last = heartbeat.get(tName, 0.0)
            if now - last > HEARTBEAT_TIMEOUT:
                logMsg("ERROR",
                    f"{tName} heartbeat stale ({now - last:.1f}s) — restarting")
                restartThread(tName)

        for qName, q in monitored_queues.items():
            depth = q.qsize()
            if depth >= QUEUE_DEPTH_ALARM:
                logMsg("CRITICAL", f"{qName} queue depth {depth} (alarm threshold)")
            elif depth >= QUEUE_DEPTH_WARN:
                logMsg("WARNING", f"{qName} queue depth {depth} (warn threshold)")

        if now - last_pxi_check >= PXI_HEALTH_INTERVAL:
            last_pxi_check = now
            with pxiLock:
                healthy = checkPXIHealth()
            if not healthy:
                logMsg("ERROR", "PXI health check failed — reinitialising connection")
                reinitPXI()

        updateHeartbeat(name)
        time.sleep(WATCHDOG_INTERVAL)


# ══════════════════════════════════════════════════════════════════════════════
# SAFE MODE
# ══════════════════════════════════════════════════════════════════════════════

def triggerSafeMode():
    """Drive all hardware to a known-inert state. Each action is isolated."""
    if safeModeEvent.is_set():
        return
    safeModeEvent.set()
    logMsg("CRITICAL", "ENTERING SAFE MODE")

    try:
        if relayController is not None:
            for i in range(NUM_RELAYS):
                relayController.signalRelayOff(i)
        logMsg("INFO", "Safe mode: all relays opened")
    except Exception as e:
        logMsg("ERROR", f"Safe mode relay shutdown failed: {e}")

    try:
        with pxiLock:
            for wave in pxiWaves:
                try:
                    wave._card.PIFGLX_AbortGeneration(wave.getChannel())
                except Exception:
                    pass
        logMsg("INFO", "Safe mode: PXI outputs zeroed")
    except Exception as e:
        logMsg("ERROR", f"Safe mode PXI shutdown failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# HARDWARE INIT
# ══════════════════════════════════════════════════════════════════════════════

def initHardware():
    """Initialize all hardware and start all worker threads. Returns a status string."""
    global relayController
    errors = []

    startThread("TELEM")   # start logger first so all subsequent logMsg calls work

    try:
        waves = initPXIE(PXI_IP)
        pxiWaves.extend(waves)
        if waves:
            logMsg("INFO",
                f"PXI: {len(waves) // 3} card(s) initialized, {len(waves)} channels ready")
        else:
            logMsg("ERROR", f"PXI: connected to {PXI_IP} but found 0 free cards "
                             f"(already claimed by another session?)")
            _lxi_append_error(f"connected to {PXI_IP} but found 0 free cards "
                               f"(already claimed by another session?)")
            errors.append("PXI: 0 cards found")
    except Exception as e:
        logMsg("ERROR", f"PXI init failed: {e}")
        _lxi_append_error(f"startup init failed (IP {PXI_IP}): {e}")
        errors.append(f"PXI: {e}")

    try:
        relayController = RelayController(port=RELAY_PORT)
        relayController.start()
        logMsg("INFO", f"Relay controller started on {RELAY_PORT}")
    except Exception as e:
        logMsg("ERROR", f"Relay init failed: {e}")
        errors.append(f"Relay: {e}")

    startThread("PXI")
    startThread("RELAY")
    startThread("SERIAL")

    watchdog_t = threading.Thread(target=watchdog_worker, name="WATCHDOG", daemon=True)
    threads["WATCHDOG"] = watchdog_t
    updateHeartbeat("WATCHDOG")
    watchdog_t.start()

    if errors:
        return "Partial init — " + "; ".join(errors)
    n = len(pxiWaves) // 3
    return f"Ready — {n} PXI card{'s' if n != 1 else ''}"


# ══════════════════════════════════════════════════════════════════════════════
# TK LOG HANDLER  (ported from testHarness/testHarness.py)
# ══════════════════════════════════════════════════════════════════════════════

class _TkLogHandler(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self._cb = callback
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(threadName)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S"))

    def emit(self, record):
        try:
            self._cb(self.format(record))
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# ARRAY DIAGRAM  (kept from existing groundController.py)
# ══════════════════════════════════════════════════════════════════════════════

class ArrayDiagram(tk.Canvas):
    """Canvas widget that renders the phased array transducer layout."""

    RADIUS = 20

    def __init__(self, parent, on_select=None, **kw):
        kw.setdefault("bg", BG)
        kw.setdefault("highlightthickness", 0)
        super().__init__(parent, **kw)
        self._on_select = on_select
        self._selected = None
        self.bind("<Configure>", lambda e: self._draw(e.width, e.height))
        self.bind("<Button-1>",  self._on_click)

    def _draw(self, w, h):
        self.delete("all")
        r = self.RADIUS
        pair_coords = {}
        for i, (nx, ny) in enumerate(TRANSDUCER_XY):
            p = TRANSDUCER_PAIR[i]
            pair_coords.setdefault(p, []).append((nx * w, ny * h))
        for p, pts in pair_coords.items():
            if len(pts) == 2:
                self.create_line(*pts[0], *pts[1],
                                 fill=PAIR_COLORS[p], width=2, dash=(5, 4))
        for i, (nx, ny) in enumerate(TRANSDUCER_XY):
            p = TRANSDUCER_PAIR[i]
            cx, cy = nx * w, ny * h
            selected = (p == self._selected)
            self.create_oval(cx - r, cy - r, cx + r, cy + r,
                fill=PAIR_COLORS[p],
                outline="white" if selected else "#44446a",
                width=3 if selected else 1)
            self.create_text(cx, cy, text=str(p + 1),
                fill="white", font=("Helvetica", 9, "bold"))
        legend_y = h - NUM_PAIRS * 18 - 6
        for p in range(NUM_PAIRS):
            lx, ly = 8, legend_y + p * 18
            self.create_oval(lx, ly, lx + 12, ly + 12,
                fill=PAIR_COLORS[p], outline="")
            self.create_text(lx + 18, ly + 6, anchor="w", text=f"Pair {p + 1}",
                fill=FG_DIM, font=("Helvetica", 8))

    def _on_click(self, event):
        w, h = self.winfo_width(), self.winfo_height()
        for i, (nx, ny) in enumerate(TRANSDUCER_XY):
            cx, cy = nx * w, ny * h
            if math.hypot(event.x - cx, event.y - cy) <= self.RADIUS:
                p = TRANSDUCER_PAIR[i]
                self._selected = p
                self._draw(w, h)
                if self._on_select:
                    self._on_select(p)
                return

    def select_pair(self, pair_idx):
        self._selected = pair_idx
        self._draw(self.winfo_width(), self.winfo_height())


# ══════════════════════════════════════════════════════════════════════════════
# SCROLLABLE FRAME  (kept from existing groundController.py)
# ══════════════════════════════════════════════════════════════════════════════

class ScrollFrame(tk.Frame):
    """Vertically scrollable container — add child widgets to .inner."""

    def __init__(self, parent, **kw):
        kw.setdefault("bg", BG)
        super().__init__(parent, **kw)
        self._canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self._sb = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self.inner = tk.Frame(self._canvas, bg=BG)
        self._win_id = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self._canvas.configure(yscrollcommand=self._sb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._sb.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._on_inner_resize)
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_inner_resize(self, _):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._win_id, width=event.width)

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# ══════════════════════════════════════════════════════════════════════════════
# PAIR CONTROLS  (modified: _apply() queues a command instead of calling hardware)
# ══════════════════════════════════════════════════════════════════════════════

class PairControls(tk.Frame):
    """Slider + entry controls for one transducer pair.

    Clicking Apply puts an ("apply", pair_idx, freq, amp, offset, phase) tuple
    on pxiQueue. The pxi_worker picks it up, calls updateWaveform() on the real
    hardware, and fires a stateBus "channel_update" event so the LXI table refreshes.
    """

    def __init__(self, parent, pair_idx, on_focus=None, **kw):
        bg = BG if pair_idx % 2 == 0 else BG_ALT
        super().__init__(parent, bg=bg, padx=4, pady=4, **kw)
        self._idx     = pair_idx
        self._on_focus = on_focus
        self._bg      = bg
        self._vars    = {}
        self._entries = {}
        self._build()

    def _build(self):
        bg    = self._bg
        color = PAIR_COLORS[self._idx]

        tk.Label(self, text="●", fg=color, bg=bg,
                 font=("Helvetica", 16)).grid(row=0, column=0, rowspan=2, padx=(2, 4))
        tk.Label(self, text=f"Pair {self._idx + 1}", fg=FG, bg=bg,
                 font=("Helvetica", 9, "bold"), width=6, anchor="w").grid(
            row=0, column=1, rowspan=2, padx=(0, 10))

        for col_i, (key, label, hard_min, hard_max,
                    default, sl_min, sl_max, fmt) in enumerate(PARAMS):
            c = col_i * 3 + 2
            tk.Label(self, text=label, fg=FG_DIM, bg=bg,
                     font=("Helvetica", 8), anchor="center").grid(
                row=0, column=c, columnspan=2, sticky="ew", padx=2)

            var = tk.DoubleVar(value=default)
            self._vars[key] = var

            scale = tk.Scale(
                self, from_=sl_min, to=sl_max, variable=var,
                orient="horizontal", length=120, showvalue=False,
                bg=bg, fg=FG, troughcolor=BG_HL,
                activebackground=color, highlightthickness=0, bd=0,
                command=lambda v, k=key, f=fmt: self._push_to_entry(k, float(v), f),
            )
            scale.grid(row=1, column=c, padx=(2, 0), sticky="ew")

            entry = tk.Entry(self, width=10, justify="center",
                             bg=BG_HL, fg=FG, insertbackground=FG,
                             relief="flat", bd=2)
            entry.insert(0, format(default, fmt))
            entry.grid(row=1, column=c + 1, padx=(2, 8))
            entry.bind("<Return>",   lambda _, k=key: self._pull_from_entry(k))
            entry.bind("<FocusOut>", lambda _, k=key: self._pull_from_entry(k))
            entry.bind("<FocusIn>",
                       lambda _: self._on_focus and self._on_focus(self._idx))
            self._entries[key] = (entry, fmt, hard_min, hard_max)

        tk.Button(self, text="Apply", bg=BG_HL, fg=FG, relief="flat",
                  padx=8, activebackground=color, activeforeground="white",
                  command=self._apply).grid(
            row=0, column=len(PARAMS) * 3 + 2, rowspan=2, padx=(4, 2))

    def _push_to_entry(self, key, val, fmt):
        entry, _, _, _ = self._entries[key]
        entry.delete(0, "end")
        entry.insert(0, format(val, fmt))

    def _pull_from_entry(self, key):
        entry, fmt, lo, hi = self._entries[key]
        try:
            val = max(lo, min(hi, float(entry.get())))
            self._vars[key].set(val)
            entry.delete(0, "end")
            entry.insert(0, format(val, fmt))
        except ValueError:
            pass

    def _apply(self):
        if self._on_focus:
            self._on_focus(self._idx)
        pxiQueue.put((
            "apply", self._idx,
            self._vars["freq"].get(),
            self._vars["amp"].get(),
            self._vars["offset"].get(),
            self._vars["phase"].get(),
        ))

    def apply(self):
        """Public entry point used by 'Apply All Pairs'."""
        self._apply()

    def load_values(self, freq, amp, offset, phase):
        """Populate sliders/entries from a saved config and immediately apply."""
        for key, val in (("freq", freq), ("amp", amp), ("offset", offset), ("phase", phase)):
            entry, fmt, lo, hi = self._entries[key]
            clamped = max(lo, min(hi, val))
            self._vars[key].set(clamped)
            entry.delete(0, "end")
            entry.insert(0, format(clamped, fmt))
        self._apply()


# ══════════════════════════════════════════════════════════════════════════════
# LXI CABINET MANAGER WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class LXIManagerWindow(tk.Toplevel):
    """Standalone Toplevel for inspecting and managing the LXI cabinet connection."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("LXI Cabinet Manager")
        self.configure(bg=BG)
        self.minsize(560, 480)
        self.resizable(True, True)

        self._error_shown_count = 0   # how many lxiErrors entries are in the log box
        self._card_rows: list[list[tk.Label]] = []

        self._build_ui()
        self._refresh()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Section A: Connection ─────────────────────────────────────────────
        conn_frame = tk.LabelFrame(self, text="Connection",
                                   bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                                   padx=8, pady=6)
        conn_frame.pack(fill="x", padx=10, pady=(8, 4))

        # IP row
        ip_row = tk.Frame(conn_frame, bg=BG)
        ip_row.pack(fill="x", pady=(0, 4))
        tk.Label(ip_row, text="IP / Hostname:", bg=BG, fg=FG,
                 font=("Helvetica", 9)).pack(side="left")
        self._ip_var = tk.StringVar(value=PXI_IP)
        self._ip_entry = tk.Entry(ip_row, textvariable=self._ip_var, width=22,
                                  bg=BG_HL, fg=FG, insertbackground=FG,
                                  relief="flat", bd=2, font=("Courier", 9))
        self._ip_entry.pack(side="left", padx=(6, 8))
        tk.Button(ip_row, text="Apply & Reinit", bg=BG_HL, fg=FG, relief="flat",
                  padx=8, activebackground=BLUE, activeforeground=BG,
                  command=self._apply_ip).pack(side="left", padx=(0, 6))
        tk.Button(ip_row, text="Test Connection", bg=BG_HL, fg=FG, relief="flat",
                  padx=8, activebackground=GREEN, activeforeground=BG,
                  command=self._test_connection).pack(side="left")

        # Status row
        status_row = tk.Frame(conn_frame, bg=BG)
        status_row.pack(fill="x")
        self._status_dot = tk.Label(status_row, text="●", bg=BG,
                                    font=("Helvetica", 14))
        self._status_dot.pack(side="left")
        self._status_lbl = tk.Label(status_row, text="UNKNOWN",
                                    bg=BG, fg=FG, font=("Helvetica", 9, "bold"))
        self._status_lbl.pack(side="left", padx=(4, 20))
        self._info_lbl = tk.Label(status_row, text="",
                                  bg=BG, fg=FG_DIM, font=("Helvetica", 8))
        self._info_lbl.pack(side="left")

        # ── Section B: Card Status ────────────────────────────────────────────
        card_frame = tk.LabelFrame(self, text="Card Status",
                                   bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                                   padx=8, pady=6)
        card_frame.pack(fill="x", padx=10, pady=4)

        headers = ["#", "Model", "Bus", "Slot", "Ch 1", "Ch 2", "Ch 3", "Last Check"]
        widths  = [3,   10,      5,     5,      6,      6,      6,      12]
        for col, (h, w) in enumerate(zip(headers, widths)):
            tk.Label(card_frame, text=h, bg=BG, fg=FG_DIM,
                     font=("Helvetica", 8, "bold"), width=w,
                     anchor="w").grid(row=0, column=col, padx=3, pady=(0, 2))

        self._card_grid_frame = card_frame
        self._card_grid_widths = widths
        self._no_cards_lbl = tk.Label(card_frame, text="No cards detected.",
                                      bg=BG, fg=FG_DIM, font=("Italic", 8))
        self._no_cards_lbl.grid(row=1, column=0, columnspan=len(headers),
                                 sticky="w", padx=4, pady=2)

        # ── Section C: Error Log ──────────────────────────────────────────────
        err_frame = tk.LabelFrame(self, text="Error Log",
                                  bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                                  padx=6, pady=4)
        err_frame.pack(fill="both", expand=True, padx=10, pady=4)

        self._err_box = scrolledtext.ScrolledText(
            err_frame, bg=BG_ALT, fg=RED, font=("Courier", 8),
            height=8, state="disabled", relief="flat")
        self._err_box.pack(fill="both", expand=True)

        btn_row = tk.Frame(err_frame, bg=BG)
        btn_row.pack(fill="x", pady=(4, 0))
        tk.Button(btn_row, text="Clear", bg=BG_HL, fg=FG, relief="flat",
                  padx=8, activebackground=RED, activeforeground=BG,
                  command=self._clear_errors).pack(side="right")

        # ── Close button ──────────────────────────────────────────────────────
        tk.Button(self, text="Close", bg=BG_HL, fg=FG, relief="flat",
                  padx=12, pady=4, activebackground="#4e4e70", activeforeground=FG,
                  command=self.destroy).pack(pady=(0, 8))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _apply_ip(self):
        global PXI_IP
        new_ip = self._ip_var.get().strip()
        if not new_ip:
            return
        PXI_IP = new_ip
        pxiQueue.put(("reinit",))
        _lxi_append_error(f"operator changed IP to '{new_ip}', reinit queued")
        logMsg("INFO", f"LXI Manager: IP changed to '{new_ip}', reinit queued")

    def _test_connection(self):
        self._status_dot.config(fg=YELLOW)
        self._status_lbl.config(text="TESTING…", fg=YELLOW)
        threading.Thread(target=self._run_health_check, daemon=True).start()

    def _run_health_check(self):
        with pxiLock:
            ok = checkPXIHealth()
        self.after(0, self._apply_health_result, ok)

    def _apply_health_result(self, ok: bool):
        if not self.winfo_exists():
            return
        if ok:
            self._status_dot.config(fg=GREEN)
            self._status_lbl.config(text="CONNECTED", fg=GREEN)
        else:
            self._status_dot.config(fg=RED)
            self._status_lbl.config(text="DEGRADED / OFFLINE", fg=RED)

    def _clear_errors(self):
        lxiErrors.clear()
        self._error_shown_count = 0
        self._err_box.config(state="normal")
        self._err_box.delete("1.0", "end")
        self._err_box.config(state="disabled")

    # ── Refresh loop ──────────────────────────────────────────────────────────

    def _refresh(self):
        if not self.winfo_exists():
            return

        # Connection status derived from pxiWaves length
        with pxiLock:
            n_waves = len(pxiWaves)
        n_cards = n_waves // 3
        if n_waves > 0:
            self._status_dot.config(fg=GREEN)
            self._status_lbl.config(text="CONNECTED", fg=GREEN)
        else:
            self._status_dot.config(fg=RED)
            self._status_lbl.config(text="OFFLINE", fg=RED)
        self._info_lbl.config(
            text=f"Cards: {n_cards}  |  Reinit count: {pxiReinitCount}  |  IP: {PXI_IP}")
        if self.focus_get() is not self._ip_entry:
            self._ip_var.set(PXI_IP)

        # Card table — rebuild in background to avoid blocking on CardId()
        threading.Thread(target=self._fetch_card_info, daemon=True).start()

        # Error log — append only new entries
        new_entries = lxiErrors[self._error_shown_count:]
        if new_entries:
            self._err_box.config(state="normal")
            for entry in new_entries:
                self._err_box.insert("end", entry + "\n")
            self._err_box.see("end")
            self._err_box.config(state="disabled")
            self._error_shown_count = len(lxiErrors)

        self.after(2000, self._refresh)

    def _fetch_card_info(self):
        """Gather CardId / CardLoc from hardware (runs in background thread)."""
        rows = []
        with pxiLock:
            seen_ids = {}
            for wave in pxiWaves:
                card = wave._card
                cid = id(card)
                if cid not in seen_ids:
                    seen_ids[cid] = len(seen_ids)
                    try:
                        model = card.CardId()
                        bus, slot = card.CardLoc()
                    except Exception as e:
                        model = f"Error: {e}"
                        bus, slot = "?", "?"
                    rows.append({
                        "idx":   seen_ids[cid],
                        "model": model,
                        "bus":   str(bus),
                        "slot":  str(slot),
                        "ts":    time.strftime("%H:%M:%S"),
                    })
        self.after(0, self._update_card_table, rows)

    def _update_card_table(self, rows: list):
        if not self.winfo_exists():
            return

        # Destroy old data rows
        for row_labels in self._card_rows:
            for lbl in row_labels:
                lbl.destroy()
        self._card_rows.clear()

        if not rows:
            self._no_cards_lbl.grid()
            return

        self._no_cards_lbl.grid_remove()
        widths = self._card_grid_widths
        for r, info in enumerate(rows):
            cols_data = [
                str(info["idx"]),
                info["model"],
                info["bus"],
                info["slot"],
                "1", "2", "3",
                info["ts"],
            ]
            row_labels = []
            for c, (val, w) in enumerate(zip(cols_data, widths)):
                lbl = tk.Label(self._card_grid_frame, text=val,
                               bg=BG, fg=FG, font=("Courier", 8),
                               width=w, anchor="w")
                lbl.grid(row=r + 1, column=c, padx=3, pady=1)
                row_labels.append(lbl)
            self._card_rows.append(row_labels)


# ══════════════════════════════════════════════════════════════════════════════
# RELAY BOARD MANAGER WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class RelayManagerWindow(tk.Toplevel):
    """Standalone Toplevel for inspecting and managing the relay board connection."""

    _COL_HEADERS = ["Relay", "Commanded", "Applied", "Discrepancy", "Manual"]
    _COL_WIDTHS  = [7,       11,          11,        13,             1]

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Relay Board Manager")
        self.configure(bg=BG)
        self.minsize(520, 440)
        self.resizable(True, True)

        self._error_shown_count = 0
        self._table_rows: list[list] = []   # list of (label_widgets..., btn_frame)

        self._build_ui()
        self._refresh()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Section A: Connection ─────────────────────────────────────────────
        conn_frame = tk.LabelFrame(self, text="Connection",
                                   bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                                   padx=8, pady=6)
        conn_frame.pack(fill="x", padx=10, pady=(8, 4))

        port_row = tk.Frame(conn_frame, bg=BG)
        port_row.pack(fill="x", pady=(0, 4))
        tk.Label(port_row, text="Serial Port:", bg=BG, fg=FG,
                 font=("Helvetica", 9)).pack(side="left")
        self._port_var = tk.StringVar(value=RELAY_PORT)
        self._port_entry = tk.Entry(port_row, textvariable=self._port_var, width=12,
                                    bg=BG_HL, fg=FG, insertbackground=FG,
                                    relief="flat", bd=2, font=("Courier", 9))
        self._port_entry.pack(side="left", padx=(6, 8))
        tk.Button(port_row, text="Apply & Reconnect", bg=BG_HL, fg=FG, relief="flat",
                  padx=8, activebackground=YELLOW, activeforeground=BG,
                  command=self._apply_port).pack(side="left", padx=(0, 6))
        tk.Button(port_row, text="Test Connection", bg=BG_HL, fg=FG, relief="flat",
                  padx=8, activebackground=GREEN, activeforeground=BG,
                  command=self._test_connection).pack(side="left")

        status_row = tk.Frame(conn_frame, bg=BG)
        status_row.pack(fill="x")
        self._status_dot = tk.Label(status_row, text="●", bg=BG,
                                    font=("Helvetica", 14))
        self._status_dot.pack(side="left")
        self._status_lbl = tk.Label(status_row, text="UNKNOWN",
                                    bg=BG, fg=FG, font=("Helvetica", 9, "bold"))
        self._status_lbl.pack(side="left", padx=(4, 20))
        self._info_lbl = tk.Label(status_row, text="",
                                  bg=BG, fg=FG_DIM, font=("Helvetica", 8))
        self._info_lbl.pack(side="left")

        # ── Section B: Relay Detail Table ─────────────────────────────────────
        relay_frame = tk.LabelFrame(self, text="Relay States",
                                    bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                                    padx=8, pady=6)
        relay_frame.pack(fill="x", padx=10, pady=4)

        for col, (h, w) in enumerate(zip(self._COL_HEADERS, self._COL_WIDTHS)):
            tk.Label(relay_frame, text=h, bg=BG, fg=FG_DIM,
                     font=("Helvetica", 8, "bold"), width=w,
                     anchor="w").grid(row=0, column=col, padx=4, pady=(0, 2))

        self._relay_frame = relay_frame
        self._cmd_lbls:   list[tk.Label] = []
        self._app_lbls:   list[tk.Label] = []
        self._disc_lbls:  list[tk.Label] = []

        for i in range(NUM_RELAYS):
            tk.Label(relay_frame, text=f"Relay {i}", bg=BG, fg=FG,
                     font=("Courier", 8), width=7, anchor="w").grid(
                row=i + 1, column=0, padx=4, pady=2)

            cmd_lbl = tk.Label(relay_frame, text="—", bg=BG, fg=FG_DIM,
                               font=("Courier", 8), width=11, anchor="w")
            cmd_lbl.grid(row=i + 1, column=1, padx=4, pady=2)
            self._cmd_lbls.append(cmd_lbl)

            app_lbl = tk.Label(relay_frame, text="—", bg=BG, fg=FG_DIM,
                               font=("Courier", 8), width=11, anchor="w")
            app_lbl.grid(row=i + 1, column=2, padx=4, pady=2)
            self._app_lbls.append(app_lbl)

            disc_lbl = tk.Label(relay_frame, text="—", bg=BG, fg=FG_DIM,
                                font=("Courier", 8), width=13, anchor="w")
            disc_lbl.grid(row=i + 1, column=3, padx=4, pady=2)
            self._disc_lbls.append(disc_lbl)

            btn_f = tk.Frame(relay_frame, bg=BG)
            btn_f.grid(row=i + 1, column=4, padx=4, pady=2)
            tk.Button(btn_f, text="ON", bg=BG_HL, fg=GREEN, relief="flat",
                      padx=5, font=("Helvetica", 8),
                      activebackground=GREEN, activeforeground=BG,
                      command=lambda idx=i: relayQueue.put(("set", idx, True))
                      ).pack(side="left", padx=1)
            tk.Button(btn_f, text="OFF", bg=BG_HL, fg=RED, relief="flat",
                      padx=5, font=("Helvetica", 8),
                      activebackground=RED, activeforeground=BG,
                      command=lambda idx=i: relayQueue.put(("set", idx, False))
                      ).pack(side="left", padx=1)

        all_off_row = tk.Frame(relay_frame, bg=BG)
        all_off_row.grid(row=NUM_RELAYS + 1, column=0, columnspan=5,
                         sticky="w", pady=(6, 0))
        tk.Button(all_off_row, text="All Off", bg=BG_HL, fg=RED, relief="flat",
                  padx=10, pady=3, font=("Helvetica", 8),
                  activebackground=RED, activeforeground=BG,
                  command=self._all_off).pack(side="left")

        # ── Section C: Error Log ──────────────────────────────────────────────
        err_frame = tk.LabelFrame(self, text="Error Log",
                                  bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                                  padx=6, pady=4)
        err_frame.pack(fill="both", expand=True, padx=10, pady=4)

        self._err_box = scrolledtext.ScrolledText(
            err_frame, bg=BG_ALT, fg=RED, font=("Courier", 8),
            height=6, state="disabled", relief="flat")
        self._err_box.pack(fill="both", expand=True)

        btn_row = tk.Frame(err_frame, bg=BG)
        btn_row.pack(fill="x", pady=(4, 0))
        tk.Button(btn_row, text="Clear", bg=BG_HL, fg=FG, relief="flat",
                  padx=8, activebackground=RED, activeforeground=BG,
                  command=self._clear_errors).pack(side="right")

        tk.Button(self, text="Close", bg=BG_HL, fg=FG, relief="flat",
                  padx=12, pady=4, activebackground="#4e4e70", activeforeground=FG,
                  command=self.destroy).pack(pady=(0, 8))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _apply_port(self):
        new_port = self._port_var.get().strip()
        if not new_port:
            return
        relayQueue.put(("reconnect", new_port))
        _relay_append_error(f"operator changed port to '{new_port}', reconnect queued")
        logMsg("INFO", f"Relay Manager: port changed to '{new_port}', reconnect queued")

    def _test_connection(self):
        self._status_dot.config(fg=YELLOW)
        self._status_lbl.config(text="TESTING…", fg=YELLOW)
        threading.Thread(target=self._run_connection_test, daemon=True).start()

    def _run_connection_test(self):
        rc = relayController
        connected = rc is not None and rc.isConnected()
        self.after(0, self._apply_connection_result, connected)

    def _apply_connection_result(self, connected: bool):
        if not self.winfo_exists():
            return
        if connected:
            self._status_dot.config(fg=GREEN)
            self._status_lbl.config(text="CONNECTED", fg=GREEN)
        else:
            self._status_dot.config(fg=RED)
            self._status_lbl.config(text="DISCONNECTED", fg=RED)

    def _all_off(self):
        for i in range(NUM_RELAYS):
            relayQueue.put(("set", i, False))

    def _clear_errors(self):
        relayErrors.clear()
        self._error_shown_count = 0
        self._err_box.config(state="normal")
        self._err_box.delete("1.0", "end")
        self._err_box.config(state="disabled")

    # ── Refresh loop ──────────────────────────────────────────────────────────

    def _refresh(self):
        if not self.winfo_exists():
            return

        rc = relayController
        if rc is None:
            self._status_dot.config(fg=FG_DIM)
            self._status_lbl.config(text="NO CONTROLLER", fg=FG_DIM)
            self._info_lbl.config(text="")
        elif rc.isConnected():
            self._status_dot.config(fg=GREEN)
            self._status_lbl.config(text="CONNECTED", fg=GREEN)
            self._info_lbl.config(
                text=f"Port: {rc.port}  |  Baud: {rc.baud}")
        else:
            self._status_dot.config(fg=RED)
            self._status_lbl.config(text="DISCONNECTED", fg=RED)
            self._info_lbl.config(
                text=f"Port: {rc.port}  |  Baud: {rc.baud}")
        if self.focus_get() is not self._port_entry:
            self._port_var.set(RELAY_PORT)

        # Relay state table
        for i in range(NUM_RELAYS):
            if rc is not None:
                commanded = rc.relayEvents[i].is_set()
                applied_raw = rc._appliedStates[i]
            else:
                commanded = relayStates[i]
                applied_raw = None

            cmd_str = "ON " if commanded else "OFF"
            self._cmd_lbls[i].config(
                text=cmd_str, fg=GREEN if commanded else RED)

            if applied_raw is None:
                self._app_lbls[i].config(text="unknown", fg=FG_DIM)
                self._disc_lbls[i].config(text="—", fg=FG_DIM)
            else:
                app_str = "ON " if applied_raw else "OFF"
                self._app_lbls[i].config(
                    text=app_str, fg=GREEN if applied_raw else RED)
                if commanded != applied_raw:
                    self._disc_lbls[i].config(text="MISMATCH", fg=RED)
                else:
                    self._disc_lbls[i].config(text="OK", fg=GREEN)

        # Error log — append only new entries
        new_entries = relayErrors[self._error_shown_count:]
        if new_entries:
            self._err_box.config(state="normal")
            for entry in new_entries:
                self._err_box.insert("end", entry + "\n")
            self._err_box.see("end")
            self._err_box.config(state="disabled")
            self._error_shown_count = len(relayErrors)

        self.after(1000, self._refresh)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════════

class GroundControllerApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("MUTT Ground Controller")
        self.configure(bg=BG)
        self.minsize(1100, 720)

        self._pair_controls:     list = []
        self._relay_indicators:  list = []
        self._signal_indicators: dict = {}
        self._thread_indicators: dict = {}
        self._lxi_labels:        list = []   # _lxi_labels[pair_idx][col] = Label

        stateBus.subscribe(self._on_hw_event)

        logging.getLogger("ground").addHandler(
            _TkLogHandler(lambda msg: self.after(0, self._log, msg)))

        self._build_ui()
        self.after(150, self._init_hardware)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI CONSTRUCTION ──────────────────────────────────────────────────────

    def _build_ui(self):
        # Title bar
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(top, text="MUTT Ground Controller",
                 bg=BG, fg=FG, font=("Helvetica", 14, "bold")).pack(side="left")
        self._status_var = tk.StringVar(value="Initializing hardware…")
        self._status_lbl = tk.Label(top, textvariable=self._status_var,
                                    bg=BG, fg=YELLOW, font=("Helvetica", 9))
        self._status_lbl.pack(side="right")

        # Everything below the title bar lives in a scrollable region so that
        # nothing (e.g. the LXI/Relay Manager buttons) gets clipped off the
        # bottom of the screen if the content is taller than the display.
        main_scroll = ScrollFrame(self)
        main_scroll.pack(fill="both", expand=True)
        content = main_scroll.inner

        # Body: array diagram (left) | status panels (right)
        body = tk.Frame(content, bg=BG)
        body.pack(fill="x", padx=10, pady=4)

        left = tk.Frame(body, bg=BG, width=300)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)
        tk.Label(left, text="Array Diagram", bg=BG, fg=FG,
                 font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(0, 4))
        self._diagram = ArrayDiagram(left, on_select=self._on_pair_select)
        self._diagram.pack(fill="both", expand=True)

        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self._build_relay_panel(right)
        self._build_signal_panel(right)
        self._build_thread_panel(right)

        # Pair controls
        ctrl_frame = tk.LabelFrame(content, text="Pair Controls",
                                   bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                                   padx=4, pady=4)
        ctrl_frame.pack(fill="x", padx=10, pady=4)

        scroll = ScrollFrame(ctrl_frame)
        scroll.pack(fill="both", expand=True)

        for i in range(NUM_PAIRS):
            ctrl = PairControls(scroll.inner, pair_idx=i,
                                on_focus=self._on_pair_select)
            ctrl.pack(fill="x", pady=1)
            tk.Frame(scroll.inner, bg=BG_HL, height=1).pack(fill="x")
            self._pair_controls.append(ctrl)

        # Ground config save/load bar
        cfg_frame = tk.LabelFrame(content, text="Ground Configs",
                                  bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                                  padx=8, pady=4)
        cfg_frame.pack(fill="x", padx=10, pady=4)

        tk.Label(cfg_frame, text="Load:", bg=BG, fg=FG_DIM,
                 font=("Helvetica", 9)).pack(side="left")
        self._config_var = tk.StringVar()
        self._config_dropdown = ttk.Combobox(
            cfg_frame, textvariable=self._config_var, state="readonly", width=24)
        self._config_dropdown.pack(side="left", padx=(4, 8))
        tk.Button(cfg_frame, text="Load", bg=BG_HL, fg=BLUE, relief="flat",
                  padx=10, activebackground=BLUE, activeforeground=BG,
                  command=self._load_config).pack(side="left", padx=(0, 16))

        tk.Label(cfg_frame, text="Save as:", bg=BG, fg=FG_DIM,
                 font=("Helvetica", 9)).pack(side="left")
        self._save_name_var = tk.StringVar()
        tk.Entry(cfg_frame, textvariable=self._save_name_var, width=20,
                 bg=BG_HL, fg=FG, insertbackground=FG,
                 relief="flat", bd=2).pack(side="left", padx=(4, 8))
        tk.Button(cfg_frame, text="Save", bg=BG_HL, fg=GREEN, relief="flat",
                  padx=10, activebackground=GREEN, activeforeground=BG,
                  command=self._save_config).pack(side="left")

        self._refresh_config_dropdown()

        # Action bar
        action = tk.Frame(content, bg=BG)
        action.pack(fill="x", padx=10, pady=(0, 4))
        for label, cmd in [("Apply All Pairs", self._apply_all),
                            ("Stop All",        self._stop_all)]:
            tk.Button(action, text=label, bg=BG_HL, fg=FG, relief="flat",
                      padx=12, pady=5,
                      activebackground="#4e4e70", activeforeground=FG,
                      command=cmd).pack(side="left", padx=(0, 10))
        tk.Button(action, text="LXI Manager…", bg=BG_HL, fg=BLUE, relief="flat",
                  padx=12, pady=5,
                  activebackground=BLUE, activeforeground=BG,
                  command=self._open_lxi_manager).pack(side="left", padx=(0, 10))
        tk.Button(action, text="Relay Manager…", bg=BG_HL, fg=YELLOW, relief="flat",
                  padx=12, pady=5,
                  activebackground=YELLOW, activeforeground=BG,
                  command=self._open_relay_manager).pack(side="left", padx=(0, 10))

        # LXI channel table
        lxi_frame = tk.LabelFrame(content, text="LXI Function Generators",
                                  bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                                  padx=6, pady=4)
        lxi_frame.pack(fill="x", padx=10, pady=4)
        self._build_lxi_panel(lxi_frame)

        # Log pane
        log_frame = tk.LabelFrame(content, text="Log",
                                  bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                                  padx=4, pady=4)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self._log_box = scrolledtext.ScrolledText(
            log_frame, bg=BG_ALT, fg=FG, font=("Courier", 8),
            height=8, state="disabled", relief="flat")
        self._log_box.pack(fill="both", expand=True)

    def _build_relay_panel(self, parent):
        f = tk.LabelFrame(parent, text="Relay Control",
                          bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                          padx=8, pady=4)
        f.pack(fill="x", pady=(0, 4))

        for i in range(NUM_RELAYS):
            col = tk.Frame(f, bg=BG)
            col.pack(side="left", padx=14)

            tk.Label(col, text=f"Relay {i}", fg=FG_DIM, bg=BG,
                     font=("Helvetica", 8)).pack()

            ind = tk.Label(col, text="●", fg=RED, bg=BG, font=("Helvetica", 14))
            ind.pack()
            self._relay_indicators.append(ind)

            btn_row = tk.Frame(col, bg=BG)
            btn_row.pack()
            tk.Button(btn_row, text="ON", bg=BG_HL, fg=GREEN, relief="flat",
                      padx=6, font=("Helvetica", 8),
                      command=lambda idx=i: self._toggle_relay(idx, True)
                      ).pack(side="left", padx=1)
            tk.Button(btn_row, text="OFF", bg=BG_HL, fg=RED, relief="flat",
                      padx=6, font=("Helvetica", 8),
                      command=lambda idx=i: self._toggle_relay(idx, False)
                      ).pack(side="left", padx=1)

    def _build_signal_panel(self, parent):
        f = tk.LabelFrame(parent, text="Signal States",
                          bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                          padx=8, pady=4)
        f.pack(fill="x", pady=(0, 4))

        num_cols = 3
        per_col  = (len(SIGNAL_NAMES) + num_cols - 1) // num_cols  # ceil → 7

        for i, name in enumerate(SIGNAL_NAMES):
            grp = i // per_col
            row = i % per_col
            left_pad = 12 if grp > 0 else 0
            ind = tk.Label(f, text="●", fg=RED, bg=BG, font=("Helvetica", 11))
            ind.grid(row=row, column=grp * 2,     padx=(left_pad, 1), pady=1, sticky="e")
            tk.Label(f, text=name, fg=FG_DIM, bg=BG,
                     font=("Courier", 8), anchor="w").grid(
                row=row, column=grp * 2 + 1, padx=(0, 6), pady=1, sticky="w")
            self._signal_indicators[name] = ind

    def _build_thread_panel(self, parent):
        f = tk.LabelFrame(parent, text="Thread Status",
                          bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                          padx=8, pady=4)
        f.pack(fill="x", pady=(0, 4))

        for name in ("PXI", "RELAY", "SERIAL", "TELEM", "WATCHDOG"):
            col = tk.Frame(f, bg=BG)
            col.pack(side="left", padx=10)
            tk.Label(col, text=name, fg=FG_DIM, bg=BG,
                     font=("Helvetica", 8)).pack()
            ind = tk.Label(col, text="●", fg=YELLOW, bg=BG, font=("Helvetica", 14))
            ind.pack()
            self._thread_indicators[name] = ind

        self._safe_mode_lbl = tk.Label(
            f, text="SAFE MODE: NO", bg=BG, fg=GREEN,
            font=("Helvetica", 8, "bold"))
        self._safe_mode_lbl.pack(side="right", padx=8)

    def _build_lxi_panel(self, parent):
        headers = ["Pair", "Card", "Ch", "Type",
                   "Freq (Hz)", "Amp (V)", "Offset (V)", "Phase (°)", "Status"]
        for col, h in enumerate(headers):
            tk.Label(parent, text=h, bg=BG_HL, fg=FG_DIM,
                     font=("Helvetica", 8, "bold"),
                     padx=6, pady=2, relief="flat").grid(
                row=0, column=col, sticky="ew", padx=1, pady=1)

        for p in range(NUM_PAIRS):
            card_idx, ch_num = CHANNEL_MAP[p]
            row_defaults = [str(p + 1), str(card_idx), str(ch_num), "SINE",
                            "—", "—", "—", "—", "IDLE"]
            row_labels = []
            for col, val in enumerate(row_defaults):
                fg = PAIR_COLORS[p] if col == 0 else FG
                bg = BG_ALT if p % 2 else BG
                lbl = tk.Label(parent, text=val, bg=bg, fg=fg,
                               font=("Courier", 8), padx=6, pady=2, relief="flat")
                lbl.grid(row=p + 1, column=col, sticky="ew", padx=1, pady=1)
                row_labels.append(lbl)
            self._lxi_labels.append(row_labels)

    # ── HARDWARE INIT ────────────────────────────────────────────────────────

    def _init_hardware(self):
        status = initHardware()
        self._status_var.set(status)
        if "error" in status.lower() or "partial" in status.lower():
            self._status_lbl.config(fg=RED)
        else:
            self._status_lbl.config(fg=GREEN)
        self.after(500, self._poll)

    # ── PERIODIC POLL (500 ms) ───────────────────────────────────────────────

    def _poll(self):
        for name, ind in self._thread_indicators.items():
            t = threads.get(name)
            if t is None:
                ind.config(fg=YELLOW)
            elif t.is_alive():
                ind.config(fg=GREEN)
            else:
                ind.config(fg=RED)

        for name, ind in self._signal_indicators.items():
            ind.config(fg=GREEN if signalStates[name] else RED)

        if safeModeEvent.is_set():
            self._safe_mode_lbl.config(text="SAFE MODE: YES", fg=RED)

        self.after(500, self._poll)

    # ── EVENT BUS ────────────────────────────────────────────────────────────

    def _on_hw_event(self, event, data):
        """Called from any thread — dispatch to main thread for GUI updates."""
        self.after(0, self._apply_hw_event, event, data)

    def _apply_hw_event(self, event, data):
        """Apply a hardware state change to the GUI (main thread only)."""
        if event == "channel_update":
            p = data.get("pair", 0)
            if 0 <= p < len(self._lxi_labels):
                row = self._lxi_labels[p]
                row[3].config(text=data.get("waveform", "SINE"))
                row[4].config(text=f"{data['freq']:.0f}")
                row[5].config(text=f"{data['amp']:.3f}")
                row[6].config(text=f"{data['offset']:.3f}")
                row[7].config(text=f"{data['phase']:.1f}")
                generating = data.get("generating", False)
                row[8].config(
                    text="RUNNING" if generating else "IDLE",
                    fg=GREEN if generating else FG_DIM)

        elif event == "relay_update":
            i = data.get("relay", 0)
            if 0 <= i < len(self._relay_indicators):
                self._relay_indicators[i].config(
                    fg=GREEN if data.get("state") else RED)

        elif event == "signal_update":
            name = data.get("name")
            if name in self._signal_indicators:
                self._signal_indicators[name].config(fg=GREEN)

    # ── CALLBACKS ────────────────────────────────────────────────────────────

    def _on_pair_select(self, pair_idx):
        self._diagram.select_pair(pair_idx)

    def _apply_all(self):
        for ctrl in self._pair_controls:
            ctrl.apply()

    def _stop_all(self):
        pxiQueue.put(("stop_all",))

    def _refresh_config_dropdown(self):
        self._config_dropdown["values"] = listGroundConfigs()

    def _save_config(self):
        name = self._save_name_var.get().strip()
        if not name:
            logMsg("WARNING", "Save config: no name entered")
            return
        safe_name = re.sub(r"[^A-Za-z0-9_\- ]", "_", name)
        try:
            path = saveGroundConfig(safe_name)
            logMsg("INFO", f"Ground config saved: {path}")
            self._refresh_config_dropdown()
            self._config_var.set(safe_name)
        except Exception as e:
            logMsg("ERROR", f"Failed to save ground config '{safe_name}': {e}")

    def _load_config(self):
        name = self._config_var.get().strip()
        if not name:
            logMsg("WARNING", "Load config: no config selected")
            return
        try:
            rows = loadGroundConfig(name)
        except Exception as e:
            logMsg("ERROR", f"Failed to load ground config '{name}': {e}")
            return
        for pair_idx, row in enumerate(rows):
            if pair_idx >= len(self._pair_controls):
                break
            self._pair_controls[pair_idx].load_values(
                row["frequency"], row["amplitude"], row["offset"], row["phase"])
        logMsg("INFO", f"Ground config '{name}' loaded and applied ({len(rows)} pair(s))")

    def _open_lxi_manager(self):
        global _lxiManagerWindow
        if _lxiManagerWindow is not None and _lxiManagerWindow.winfo_exists():
            _lxiManagerWindow.lift()
            _lxiManagerWindow.focus_force()
        else:
            _lxiManagerWindow = LXIManagerWindow(self)

    def _open_relay_manager(self):
        global _relayManagerWindow
        if _relayManagerWindow is not None and _relayManagerWindow.winfo_exists():
            _relayManagerWindow.lift()
            _relayManagerWindow.focus_force()
        else:
            _relayManagerWindow = RelayManagerWindow(self)

    def _toggle_relay(self, relay_idx, state):
        relayQueue.put(("set", relay_idx, state))

    def _log(self, msg):
        self._log_box.config(state="normal")
        self._log_box.insert("end", msg + "\n")
        self._log_box.see("end")
        self._log_box.config(state="disabled")

    # ── SHUTDOWN ─────────────────────────────────────────────────────────────

    def _on_close(self):
        stopEvent.set()
        if relayController is not None:
            try:
                relayController.stop()
            except Exception:
                pass
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════

def main():
    configureLogging()
    app = GroundControllerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
