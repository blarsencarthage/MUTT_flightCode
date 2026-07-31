
# Author: Braedon Larsen
# Created: 2026-06-11
# Updated: 2026-07-29
# Ground controller for 12-element phased array ultrasonic transducer system.
# Architecture matches testHarness: worker threads, queue-based commands,
# event-driven GUI updates via stateBus, and watchdog health monitoring.
# All controls connect to real hardware (PXI, relay board, RS-422 serial).
#
# PXI/function-generator control talks to pi620lx/pilxi directly (no
# pickeringInterfaceV2/pickeringHeader abstraction) — same configure-then-
# outputOn() methodology as pickeringControls/pickeringConnector.py. There is
# no arm/trigger split and no background auto-reconnect thread; a channel's
# Apply configures it and immediately calls outputOn(), after which it either
# free-runs or waits on the external FRONT trigger depending on physical
# wiring. Reconnecting after a dropped session is operator-triggered only
# (LXI Manager's Reinit button).

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
sys.path.insert(0, os.path.join(_HERE, "pickeringControls", "pilxi-5.7"))

import pilxi
import pi620lx
from relayControls.relaySerial import RelayController
import serial

# 41-620 attenuator: 0 dB = full-scale output, per py620 readme's documented
# 0-40 dB attenuation range. Full-scale output is 10 Vpp, open circuit —
# Pickering_FuncGenManual.pdf Section 1's "Waveform Signal" spec (the
# previous 20 Vpp value here was wrong and halved every commanded
# amplitude — see PXI_DEBUG_NOTES.md section 10). card.setAttenuation()
# wants dB — the GUI slider is calibrated in volts, so this converts on the
# way in. pxiChannelState stores amp in volts (as commanded), so no reverse
# conversion is needed on the way out.
_FULL_SCALE_VOLTS   = 10.0
_ATTENUATION_DB_MIN = 0.0
_ATTENUATION_DB_MAX = 40.0


def _dbFromVolts(volts):
    if volts <= 0:
        return _ATTENUATION_DB_MAX
    db = 20.0 * math.log10(_FULL_SCALE_VOLTS / volts)
    return max(_ATTENUATION_DB_MIN, min(_ATTENUATION_DB_MAX, db))

# card.generateSweep() takes an absolute frequencyStepSize_kHz +
# frequencyStepTime_ms pair (per Pickering_FuncGenManual.pdf §4), not a rate —
# SweepModeWindow exposes a single Hz/s "rate" dial instead, and this fixed
# step time is what that rate gets converted against (stepSizeKHz = rate *
# stepTime_s / 1000). 5ms matches pickeringControls/REPL_ConnectionCode.py's
# confirmed-working value on the actual hardware — the driver rejected
# coarser step times (e.g. 1000ms) when that was tried.
_SWEEP_STEP_TIME_MS = 5.0

# ══════════════════════════════════════════════════════════════════════════════
# HARDWARE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

NUM_PAIRS    = 6
NUM_RELAYS   = 4
NUM_CHANNELS = 6   # 2 cards × 3 channels

RELAY_NAMES  = ["Lights", "Cameras", "LXI", "HAVOC"]

# pair_index → (card_list_index, channel_number)
CHANNEL_MAP = {
    0: (0, 1), 1: (0, 2), 2: (0, 3),
    3: (1, 1), 4: (1, 2), 5: (1, 3),
}

# 40-115 relay card (pxiRelayCard) subunit/bit wired to the FG cards' external
# FRONT trigger input. 1-based, matching the old pickeringInterfaceV2.py's
# convention. Firing pulses this closed for _TRIGGER_RELAY_PULSE_S seconds
# then reopens it — entirely separate from applying/stopping channels.
_TRIGGER_RELAY_SUBUNIT = 1
_TRIGGER_RELAY_BIT     = 1
_TRIGGER_RELAY_PULSE_S = 1.0

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
    # "Amp" is entered in volts and converted to dB attenuation via
    # _dbFromVolts() (card.setAttenuation() itself only takes dB) — range is
    # 0-20V, the 41-620's full-scale output.
    ("amp",    "Amp (V)",      0.0,        20.0,     10.0,     0.0,      20.0,  ".3f"),
    ("offset", "Offset (V)",   0.0,         5.0,      0.0,     0.0,       5.0,  ".3f"),
    ("phase",  "Phase (°)",    0.0,       360.0,      0.0,     0.0,     360.0,  ".1f"),
]


# Only SINE/TRIANGLE/SQUARE have a pi620lx.Card.signalShapes equivalent
# (RAMP/DC/PULSE/PWM/ARB are not supported); the GUI has no waveform-shape
# selector, so every channel is hardcoded to SINE.

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
PXI_CONNECT_TIMEOUT_MS = 5000            # ms — Pi_Session TCP connect timeout (chassis can be slow to boot)
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

pxiSession:     pilxi.Pi_Session = None           # None if not connected; recreated on IP change/reinit
pxiCards:       list             = []             # pi620lx.Card, indexed like CHANNEL_MAP's card_list_index
pxiRelayCard                     = None            # 40-115 relay card, if found — discovered but not wired into any workflow
pxiConnected:   bool             = False
pxiChannelState: list            = [None] * NUM_PAIRS   # last-commanded {freq, amp, offset, phase, waveform, status} per pair, or None if never applied
pxiRunState:    str            = "IDLE"           # IDLE (output off) / RUNNING (output on, per pickeringConnector.py's methodology)


def _setRunState(state):
    global pxiRunState
    pxiRunState = state


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
pxiReinitCount: int           = 0    # operator-triggered reinits (IP change / manual reinit); informational only —
                                      # there is no background auto-reconnect, so this is the only way a
                                      # dropped session gets rebuilt
relayController: RelayController = None
lxiErrors:      list          = []   # timestamped error strings (newest last, max 200)
_lxiManagerWindow = None             # singleton Toplevel reference
relayErrors:    list          = []   # timestamped relay error strings (newest last, max 200)
_relayManagerWindow = None           # singleton Toplevel reference
_manualModeWindow = None             # singleton Toplevel reference
_sweepModeWindow = None              # singleton Toplevel reference

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

def _notifyPair(pair_idx, state):
    """Fire a channel_update stateBus event from a pxiChannelState entry —
    pi620lx has no live read-back, so this always reflects the
    last-commanded state."""
    stateBus._notify("channel_update", {
        "pair": pair_idx,
        "freq": state["freq"], "amp": state["amp"],
        "offset": state["offset"], "phase": state["phase"],
        "waveform": state["waveform"], "status": state["status"],
        "generating": state["status"] == "RUNNING",
    })


def _notifyAllPairs(status):
    for p in range(NUM_PAIRS):
        if pxiChannelState[p] is not None:
            pxiChannelState[p]["status"] = status
            _notifyPair(p, pxiChannelState[p])


def _provisionalState(pair_idx, freq=None, amp=None, offset=None, phase=None):
    """Build a display-only state dict for a pair that hasn't been applied
    yet — starts from the last-commanded state (or SINE/all-zero defaults if
    the pair was never applied) and overlays whichever params are changing."""
    base = pxiChannelState[pair_idx]
    state = dict(base) if base is not None else {
        "freq": 0.0, "amp": 0.0, "offset": 0.0, "phase": 0.0,
        "waveform": "SINE", "status": "IDLE",
    }
    if freq is not None:
        state["freq"] = freq
    if amp is not None:
        state["amp"] = amp
    if offset is not None:
        state["offset"] = offset
    if phase is not None:
        state["phase"] = phase
    return state


def queuePxiApply(pair_idx, freq, amp, offset, phase, freerun=False):
    """Enqueue an apply command, immediately notifying the GUI that this pair
    is NOT_UPDATED (commanded but not yet executed by pxi_worker) so the
    table reflects queue backlog instead of silently going stale.

    freerun=True sends "apply_freerun" instead of "apply" — CONT trigger
    mode, ignoring the external FRONT trigger line entirely (see
    pxi_worker's docstring). Only Manual Mode passes this."""
    provisional = _provisionalState(pair_idx, freq, amp, offset, phase)
    provisional["status"] = "NOT_UPDATED"
    _notifyPair(pair_idx, provisional)
    cmd = "apply_freerun" if freerun else "apply"
    pxiQueue.put((cmd, pair_idx, freq, amp, offset, phase))


def queuePxiApplySweep(pair_idx, minFreq, maxFreq, rateHzPerSec, amp, offset):
    """Enqueue an armed frequency-sweep apply — POSEDGE/FRONT trigger mode,
    same as queuePxiApply()'s default (freerun=False): the channel is
    configured and output turned on, but generation doesn't actually start
    sweeping until the shared relay trigger fires. Used exclusively by
    SweepModeWindow."""
    provisional = _provisionalState(pair_idx, minFreq, amp, offset, 0.0)
    provisional["status"] = "NOT_UPDATED"
    _notifyPair(pair_idx, provisional)
    pxiQueue.put(("apply_sweep", pair_idx, minFreq, maxFreq, rateHzPerSec, amp, offset))


def queuePxiStopPair(pair_idx):
    provisional = _provisionalState(pair_idx)
    provisional["status"] = "NOT_UPDATED"
    _notifyPair(pair_idx, provisional)
    pxiQueue.put(("stop_pair", pair_idx))


def queuePxiStopAll():
    for p in range(NUM_PAIRS):
        provisional = _provisionalState(p)
        provisional["status"] = "NOT_UPDATED"
        _notifyPair(p, provisional)
    pxiQueue.put(("stop_all",))


def _applyPxiChannel(pair_idx, freq, amp, offset, phase, trig_mode_name):
    """Configure one pair's channel and call outputOn(), shared by both
    trigger-gated ("apply") and free-running ("apply_freerun") commands —
    see pxi_worker's docstring for when each is used."""
    global pxiRunState
    card_idx, ch_num = CHANNEL_MAP[pair_idx]
    with pxiLock:
        if card_idx < len(pxiCards):
            card = pxiCards[card_idx]
            try:
                trigSource = card.triggerSources["FRONT"]
                trigMode = card.triggerModes[trig_mode_name]
                shape = card.signalShapes["SINE"]
                card.setActiveChannel(ch_num)
                card.outputOff()
                card.setTriggerMode(trigSource, trigMode)
                card.setOutputOffsetVoltage(offset, True)
                card.setAttenuation(_dbFromVolts(amp))
                card.generateSignal(
                    frequency=freq / 1000.0, signalType=shape,
                    startPhaseOffset=phase, symmetry=50, generate=False)
                card.outputOn()
                pxiChannelState[pair_idx] = {
                    "freq": freq, "amp": amp, "offset": offset,
                    "phase": phase, "waveform": "SINE", "status": "RUNNING",
                }
                pxiRunState = "RUNNING"
                _notifyPair(pair_idx, pxiChannelState[pair_idx])
                logMsg("INFO",
                    f"PXI pair {pair_idx+1}: freq={freq:.0f}Hz "
                    f"amp={amp:.3f}V offset={offset:.3f}V phase={phase:.1f}° "
                    f"— output on ({trig_mode_name})")
            except Exception as e:
                logMsg("ERROR", f"PXI apply pair {pair_idx+1}: {e}")
                _lxi_append_error(f"apply pair {pair_idx+1}: {e}")
        else:
            logMsg("WARNING",
                f"PXI pair {pair_idx+1}: card {card_idx} not available "
                f"(PXI not connected, or fewer than {card_idx+1} card(s) found)")


def _applyPxiSweepChannel(pair_idx, minFreq, maxFreq, rateHzPerSec, amp, offset):
    """Configure one pair's channel for a continuously-repeating frequency
    sweep via card.generateSweep() and arm it on the external FRONT trigger
    — otherwise identical to _applyPxiChannel()'s POSEDGE path, so
    SweepModeWindow's Fire Trigger button (same "fire_relay" command as the
    main window's) starts every armed channel's sweep in sync off the
    shared relay.

    generateSweep()'s own frequency args are absolute kHz + a step-size/
    step-time pair (see _SWEEP_STEP_TIME_MS); minFreq/maxFreq/rateHzPerSec
    here are in Hz / Hz-per-second to match this GUI's other frequency
    controls, converted right before the call.

    Trigger source/mode is FRONT + POSEDGE (front-panel input, rising edge)
    — same as _applyPxiChannel()'s "apply" path — so the channel arms and
    waits for the shared relay's edge exactly like a normal Apply; only
    generateSweep() vs generateSignal() differs.
    """
    global pxiRunState
    card_idx, ch_num = CHANNEL_MAP[pair_idx]
    stepSizeKHz = rateHzPerSec * (_SWEEP_STEP_TIME_MS / 1000.0) / 1000.0
    with pxiLock:
        if card_idx < len(pxiCards):
            card = pxiCards[card_idx]
            try:
                trigSource = card.triggerSources["FRONT"]
                trigMode = card.triggerModes["POSEDGE"]
                shape = card.signalShapes["SINE"]
                card.setActiveChannel(ch_num)
                card.outputOff()
                card.setTriggerMode(trigSource, trigMode)
                card.setOutputOffsetVoltage(offset, True)
                card.setAttenuation(_dbFromVolts(amp))
                card.generateSweep(shape, 50, 0,
                                    minFreq / 1000.0, maxFreq / 1000.0,
                                    stepSizeKHz, _SWEEP_STEP_TIME_MS)
                card.outputOn()
                pxiChannelState[pair_idx] = {
                    "freq": minFreq, "amp": amp, "offset": offset,
                    "phase": 0.0, "waveform": "SWEEP", "status": "RUNNING",
                }
                pxiRunState = "RUNNING"
                _notifyPair(pair_idx, pxiChannelState[pair_idx])
                logMsg("INFO",
                    f"PXI pair {pair_idx+1}: sweep {minFreq:.0f}-{maxFreq:.0f}Hz "
                    f"rate={rateHzPerSec:.0f}Hz/s amp={amp:.3f}V offset={offset:.3f}V "
                    f"— armed, waiting on trigger")
            except Exception as e:
                logMsg("ERROR", f"PXI sweep apply pair {pair_idx+1}: {e}")
                _lxi_append_error(f"sweep apply pair {pair_idx+1}: {e}")
        else:
            logMsg("WARNING",
                f"PXI pair {pair_idx+1}: card {card_idx} not available "
                f"(PXI not connected, or fewer than {card_idx+1} card(s) found)")


def pxi_worker():
    """Dequeue apply/apply_freerun/stop_pair/stop_all/reinit commands and
    drive the 41-620 cards directly via pi620lx, following
    pickeringControls/pickeringConnector.py's methodology: applying
    configures a pair's channel AND immediately calls outputOn() in the same
    step — there is no separate arm/trigger phase.

    "apply" sets POSEDGE/FRONT trigger mode, matching pickeringConnector.py
    exactly — after outputOn(), the channel either free-runs or waits on the
    external FRONT trigger depending on physical wiring.

    "apply_freerun" sets CONT trigger mode instead (pi620lx's "continuous"
    mode, 0x6 — the same mode pickeringInterfaceV2 v1 used, which is why v1
    channels always started running immediately on Apply with no cross-
    channel phase sync). CONT ignores the trigger line entirely, so
    outputOn() always starts the channel generating right away. Used
    exclusively by Manual Mode (ManualModeWindow) — bubble-nucleation tuning
    only cares that the transducers are on with the right freq/amp/offset,
    not about staying phase-synchronized across channels, so there's no
    reason to make the operator wait on (or fire) the external trigger while
    dialing values in.

    "apply_sweep" is like "apply" (POSEDGE/FRONT trigger, armed but not yet
    generating) except it calls card.generateSweep() instead of
    generateSignal() — a continuously-repeating frequency sweep instead of a
    fixed tone. Used exclusively by SweepModeWindow.

    "stop_pair" turns off just one channel — used by PairControls' Disable
    checkbox for an immediate live effect without waiting for Apply.
    """
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
            _applyPxiChannel(pair_idx, freq, amp, offset, phase, "POSEDGE")

        elif cmd == "apply_freerun" and len(item) == 6:
            _, pair_idx, freq, amp, offset, phase = item
            _applyPxiChannel(pair_idx, freq, amp, offset, phase, "CONT")

        elif cmd == "apply_sweep" and len(item) == 7:
            _, pair_idx, minFreq, maxFreq, rateHzPerSec, amp, offset = item
            _applyPxiSweepChannel(pair_idx, minFreq, maxFreq, rateHzPerSec, amp, offset)

        elif cmd == "reinit":
            reinitPXI(force=True)

        elif cmd == "stop_pair" and len(item) == 2:
            _, pair_idx = item
            card_idx, ch_num = CHANNEL_MAP[pair_idx]
            with pxiLock:
                if card_idx < len(pxiCards):
                    try:
                        card = pxiCards[card_idx]
                        card.setActiveChannel(ch_num)
                        card.outputOff()
                    except Exception as e:
                        logMsg("ERROR", f"PXI stop pair {pair_idx+1}: {e}")
                        _lxi_append_error(f"stop pair {pair_idx+1}: {e}")
                if pxiChannelState[pair_idx] is not None:
                    pxiChannelState[pair_idx]["status"] = "IDLE"
                    _notifyPair(pair_idx, pxiChannelState[pair_idx])
            logMsg("INFO", f"PXI pair {pair_idx+1}: disabled (output off)")

        elif cmd == "stop_all":
            with pxiLock:
                for pair_idx in range(NUM_PAIRS):
                    card_idx, ch_num = CHANNEL_MAP[pair_idx]
                    if card_idx < len(pxiCards):
                        try:
                            card = pxiCards[card_idx]
                            card.setActiveChannel(ch_num)
                            card.outputOff()
                        except Exception as e:
                            logMsg("ERROR", f"PXI stop pair {pair_idx+1}: {e}")
                            _lxi_append_error(f"stop pair {pair_idx+1}: {e}")
                pxiRunState = "IDLE"
                _notifyAllPairs("IDLE")
            logMsg("INFO", "PXI: all channels stopped")

        elif cmd == "fire_relay":
            # Fires the external trigger line by closing the 40-115 relay for
            # _TRIGGER_RELAY_PULSE_S seconds, then reopening it. Does not
            # touch any function generator channel/output — channels must
            # already be armed (outputOn() called via "apply") and waiting on
            # this trigger for anything to actually start generating.
            with pxiLock:
                if pxiRelayCard is not None:
                    try:
                        pxiRelayCard.OpBit(_TRIGGER_RELAY_SUBUNIT, _TRIGGER_RELAY_BIT, True)
                        logMsg("INFO", "PXI relay: closed — firing trigger")
                        stopEvent.wait(_TRIGGER_RELAY_PULSE_S)
                        pxiRelayCard.OpBit(_TRIGGER_RELAY_SUBUNIT, _TRIGGER_RELAY_BIT, False)
                        logMsg("INFO", "PXI relay: reopened")
                    except Exception as e:
                        logMsg("ERROR", f"PXI relay fire failed: {e}")
                        _lxi_append_error(f"relay fire failed: {e}")
                else:
                    logMsg("WARNING", "PXI relay fire ignored: no relay card found")

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

def _openPXI():
    """One-shot connect + card discovery, mirroring pickeringConnector.py's
    session/base/findCards/openCard sequence exactly. The 40-115 relay card
    (if present) is found the same way pickeringInterfaceV2 used to (scan
    session.FindFreeCards(), match CardId()) but is only stored — nothing
    currently wires it into arm/trigger, since pickeringConnector.py's
    methodology doesn't use it. Raises on failure; caller decides how to log
    it. No background reconnect thread — call reinitPXI() (operator-
    triggered, e.g. LXI Manager's Reinit button) to rebuild a dropped
    connection.
    """
    global pxiSession, pxiCards, pxiRelayCard, pxiConnected
    pxiSession = pilxi.Pi_Session(PXI_IP, timeout=PXI_CONNECT_TIMEOUT_MS)
    sessionID = pxiSession.GetSessionID()
    base = pi620lx.Base(sessionID)

    cards = []
    for bus, device in base.findCards():
        card = base.openCard(bus, device)
        card._bus = bus
        card._device = device
        cards.append(card)
    pxiCards = cards

    pxiRelayCard = None
    for bus, device in pxiSession.FindFreeCards():
        candidate = pxiSession.OpenCard(bus, device)
        if "40-115" in candidate.CardId():
            pxiRelayCard = candidate
            break

    pxiConnected = True


def checkPXIHealth():
    """Returns True if the last _openPXI()/reinitPXI() call succeeded and
    found at least one function generator card.

    NOTE: this is NOT a live round-trip ping. pi620lx.Card.revisionQuery()
    would be the natural candidate for one, but the vendor's pilxi-5.7/
    pi620lx/__init__.py has a bug (returns the raw ctypes buffer instead of
    .value, so _pythonString()'s .decode() always throws) that makes it
    always report failure regardless of actual card state — see the
    revisionQuery() docstring/TODO in that file before ever calling it here
    again. So this only reflects pxiConnected (set once at connect time —
    there is no background reconnect logic to clear it) — a hung/
    unresponsive chassis that never raises won't be caught by this check.
    Real hardware errors will still surface individually through
    pxi_worker's apply/stop_all handlers.
    """
    return pxiConnected and bool(pxiCards)

def reinitPXI(force=False):
    """Tear down the current session and reconnect under pxiLock.

    Operator-triggered only (IP change / manual reinit button) — there is no
    background auto-reconnect thread; the watchdog never calls this
    automatically on a failed health check.
    """
    global pxiSession, pxiCards, pxiRelayCard, pxiConnected, pxiRunState, pxiReinitCount
    pxiReinitCount += 1
    logMsg("WARNING", f"PXI reinit #{pxiReinitCount}: recreating connection to {PXI_IP}")
    with pxiLock:
        if pxiSession is not None:
            try:
                pxiSession.Close()
            except Exception as e:
                logMsg("ERROR", f"PXI reinit: error closing previous session: {e}")
        pxiSession = None
        pxiCards = []
        pxiRelayCard = None
        pxiConnected = False
        try:
            _openPXI()
            pxiRunState = "IDLE"
            logMsg("INFO", f"PXI reinit: connected to {PXI_IP}, "
                            f"{len(pxiCards)} card(s) found")
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

GROUND_CONFIG_FIELDS = ["channel", "frequency", "amplitude", "offset", "phase",
                        "waveform_type", "ring", "disabled"]


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


def saveGroundConfig(name, gui_values=None):
    """Write the currently-commanded hardware state (pxiChannelState) to
    groundConfigs/<name>.csv.

    gui_values, if given, is a list of (freq, amp, offset, phase, ring,
    disabled) indexed by pair_idx. freq/amp/offset/phase fall back to
    gui_values for any pair whose hardware state isn't available (e.g. PXI
    not connected, or never applied), so saving still captures what the
    operator has set on the sliders instead of silently dropping the pair.
    ring/disabled are pure GUI/software concepts pi620lx knows nothing about,
    so they always come from gui_values (defaulting to Outer/enabled if
    gui_values wasn't supplied at all).
    """
    _ensureGroundConfigsDir()
    path = os.path.join(GROUND_CONFIGS_DIR, f"{name}.csv")
    rows = []
    with pxiLock:
        for pair_idx in range(NUM_PAIRS):
            card_idx, ch_num = CHANNEL_MAP[pair_idx]
            state = pxiChannelState[pair_idx]
            if gui_values is not None and pair_idx < len(gui_values):
                ring, disabled = gui_values[pair_idx][4], gui_values[pair_idx][5]
            else:
                ring, disabled = "Outer", False
            if state is not None:
                rows.append([
                    ch_num, state["freq"], state["amp"],
                    state["offset"], state["phase"], state["waveform"],
                    ring, disabled,
                ])
            elif gui_values is not None and pair_idx < len(gui_values):
                freq, amp, offset, phase = gui_values[pair_idx][:4]
                rows.append([ch_num, freq, amp, offset, phase, "SINE", ring, disabled])
    if not rows:
        logMsg("WARNING", f"Ground config '{name}' saved with no pairs "
                           f"(no hardware and no GUI values available)")
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(GROUND_CONFIG_FIELDS)
        writer.writerows(rows)
    return path


def loadGroundConfig(name):
    """Read groundConfigs/<name>.csv, one row per pair in CHANNEL_MAP order.

    ring/disabled default to Outer/False for configs saved before those
    columns existed.
    """
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
                "ring":      row.get("ring") or "Outer",
                "disabled":  str(row.get("disabled", "False")).strip().lower() == "true",
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
                logMsg("ERROR",
                    "PXI health check failed — reinit is operator-triggered only "
                    "(use LXI Manager's Reinit button)")

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
            for pair_idx in range(NUM_PAIRS):
                card_idx, ch_num = CHANNEL_MAP[pair_idx]
                if card_idx < len(pxiCards):
                    card = pxiCards[card_idx]
                    card.setActiveChannel(ch_num)
                    card.outputOff()
            if pxiRelayCard is not None:
                pxiRelayCard.OpBit(_TRIGGER_RELAY_SUBUNIT, _TRIGGER_RELAY_BIT, False)
            _setRunState("IDLE")
        logMsg("INFO", "Safe mode: PXI outputs disarmed")
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
        _openPXI()   # synchronous, one-shot — see _openPXI()'s docstring
        if pxiCards:
            logMsg("INFO", f"PXI: {len(pxiCards)} card(s) initialized")
        else:
            logMsg("ERROR", f"PXI: connected to {PXI_IP} but found 0 function "
                             f"generator cards (already claimed by another session?)")
            _lxi_append_error(f"connected to {PXI_IP} but found 0 cards "
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
    n = len(pxiCards)
    return f"Ready — {n} PXI card{'s' if n != 1 else ''}"


# ══════════════════════════════════════════════════════════════════════════════
# TK LOG HANDLER  (ported from testHarness/testHarness.py)
# ══════════════════════════════════════════════════════════════════════════════

class _TkLogHandler(logging.Handler):
    """Logging handler safe to attach to the root logger and receive records
    from any thread.

    emit() must NEVER touch a Tk widget/call .after() directly: RelayController
    (relaySerial.py) logs straight to the root logger from its own background
    thread — not through this app's logQueue/TELEM-thread — so emit() can run
    concurrently with the main thread's own logging calls. Handler.handle()
    holds self.lock (a per-handler RLock) across the emit() call; if emit()
    called self.after(...) here (as an earlier version did), a background
    thread could be blocked inside that after() call — waiting on the main
    thread's Tk event loop — while holding self.lock, and if the main thread
    is itself blocked in Handler.handle() waiting for the same lock (e.g.
    logging its own message at the same moment) instead of running the event
    loop, the two deadlock and the GUI never opens. queue.Queue.put_nowait()
    doesn't touch Tk and can't deadlock this way; MainWindow drains it on its
    own periodic self.after() poll instead.
    """
    def __init__(self):
        super().__init__()
        self.queue: queue.Queue = queue.Queue()
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(threadName)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S"))

    def emit(self, record):
        try:
            self.queue.put_nowait(self.format(record))
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
            card_idx, ch_num = CHANNEL_MAP[p]
            self.create_oval(lx, ly, lx + 12, ly + 12,
                fill=PAIR_COLORS[p], outline="")
            self.create_text(lx + 18, ly + 6, anchor="w",
                text=f"Card {card_idx + 1} Ch {ch_num}",
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

RING_OPTIONS = ["Inner", "Outer"]


class PairControls(tk.Frame):
    """Slider + entry controls for one transducer pair.

    Clicking Apply puts an ("apply", pair_idx, freq, amp, offset, phase) tuple
    on pxiQueue. pxi_worker picks it up, configures that pair's channel
    directly on the 41-620 card, and immediately calls outputOn() — there is
    no separate arm/trigger step (see pxi_worker's docstring). A stateBus
    "channel_update" event fires afterward so the LXI table refreshes.

    Each pair also has a Ring dropdown (Inner/Outer — a pure GUI/software
    grouping consumed by GroundControllerApp's ring panel, not sent to
    hardware on its own) and a Disable checkbox: checking it immediately
    sends a ("stop_pair", pair_idx) command (outputOff on that channel right
    away) and greys out the sliders/entries/Apply button so they can't be
    used while disabled; unchecking re-enables them but does not resume
    output on its own — Apply must be clicked again.
    """

    def __init__(self, parent, pair_idx, on_focus=None, **kw):
        bg = BG if pair_idx % 2 == 0 else BG_ALT
        super().__init__(parent, bg=bg, padx=4, pady=4, **kw)
        self._idx     = pair_idx
        self._on_focus = on_focus
        self._bg      = bg
        self._vars    = {}
        self._entries = {}
        self._scales  = {}
        self._sl_bounds = {}
        self._locked  = False   # True while Manual Mode owns the array — see set_locked()
        card_idx, ch_num = CHANNEL_MAP[pair_idx]
        self._label_text = f"Card {card_idx + 1} Ch {ch_num}"
        self._build()

    def _build(self):
        bg    = self._bg
        color = PAIR_COLORS[self._idx]

        tk.Label(self, text="●", fg=color, bg=bg,
                 font=("Helvetica", 16)).grid(row=0, column=0, rowspan=2, padx=(2, 4))
        tk.Label(self, text=self._label_text, fg=FG, bg=bg,
                 font=("Helvetica", 9, "bold"), width=12, anchor="w").grid(
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
            self._scales[key] = scale
            self._sl_bounds[key] = (sl_min, sl_max)

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

        ring_col = len(PARAMS) * 3 + 2
        tk.Label(self, text="Ring", fg=FG_DIM, bg=bg,
                 font=("Helvetica", 8), anchor="center").grid(
            row=0, column=ring_col, sticky="ew", padx=2)
        # Default: first 2 pairs Inner, remaining 4 Outer — a starting point
        # only; freely reassignable per-pair, not enforced (see AskUserQuestion
        # decision: "freely assignable, no enforcement").
        self._ring_var = tk.StringVar(value="Inner" if self._idx < 2 else "Outer")
        self._ring_box = ttk.Combobox(self, textvariable=self._ring_var, values=RING_OPTIONS,
                                 state="readonly", width=6)
        self._ring_box.grid(row=1, column=ring_col, padx=(2, 8))

        disable_col = ring_col + 1
        tk.Label(self, text="Disable", fg=FG_DIM, bg=bg,
                 font=("Helvetica", 8), anchor="center").grid(
            row=0, column=disable_col, sticky="ew", padx=2)
        self._disabled_var = tk.BooleanVar(value=False)
        self._disable_chk = tk.Checkbutton(self, variable=self._disabled_var, bg=bg,
                        activebackground=bg, highlightthickness=0,
                        command=self._on_disable_toggle)
        self._disable_chk.grid(row=1, column=disable_col, padx=(2, 8))

        self._apply_btn = tk.Button(self, text="Apply", bg=BG_HL, fg=FG, relief="flat",
                  padx=8, activebackground=color, activeforeground="white",
                  command=self._apply)
        self._apply_btn.grid(row=0, column=disable_col + 1, rowspan=2, padx=(4, 2))

    def _push_to_entry(self, key, val, fmt):
        entry, _, _, _ = self._entries[key]
        entry.delete(0, "end")
        entry.insert(0, format(val, fmt))

    def _pull_from_entry(self, key):
        entry, fmt, lo, hi = self._entries[key]
        try:
            val = max(lo, min(hi, float(entry.get())))
            self._set_value(key, val, fmt)
        except ValueError:
            pass

    def _set_value(self, key, val, fmt):
        """Set var + slider + entry together, widening the slider's range if
        the value falls outside its normal display bounds. Without this, a
        tk.Scale silently clamps its linked variable back within from_/to,
        which would corrupt the value actually sent to hardware."""
        scale = self._scales[key]
        sl_min, sl_max = self._sl_bounds[key]
        if val < sl_min or val > sl_max:
            scale.configure(from_=min(sl_min, val), to=max(sl_max, val))
        else:
            scale.configure(from_=sl_min, to=sl_max)
        self._vars[key].set(val)
        entry, _, _, _ = self._entries[key]
        entry.delete(0, "end")
        entry.insert(0, format(val, fmt))

    def _on_disable_toggle(self):
        disabled = self._disabled_var.get()
        self._refresh_lock_state()
        if disabled:
            queuePxiStopPair(self._idx)

    def _apply(self, freerun=False):
        if self._disabled_var.get() or self._locked:
            return
        if self._on_focus:
            self._on_focus(self._idx)
        queuePxiApply(
            self._idx,
            self._vars["freq"].get(),
            self._vars["amp"].get(),
            self._vars["offset"].get(),
            self._vars["phase"].get(),
            freerun=freerun,
        )

    def set_locked(self, locked):
        """Grey out this pair's controls without touching hardware — used
        while Manual Mode owns the array. Distinct from the Disable
        checkbox (which also stops output); on unlock, state reverts to
        whatever the Disable checkbox says it should be."""
        self._locked = locked
        self._refresh_lock_state()

    def _refresh_lock_state(self):
        state = "disabled" if (self._locked or self._disabled_var.get()) else "normal"
        for scale in self._scales.values():
            scale.configure(state=state)
        for entry, _, _, _ in self._entries.values():
            entry.configure(state=state)
        self._apply_btn.configure(state=state)
        self._ring_box.configure(state=("disabled" if self._locked else "readonly"))
        self._disable_chk.configure(state=("disabled" if self._locked else "normal"))

    def apply(self, freerun=False):
        """Public entry point used by 'Apply All Pairs' and Manual Mode
        (freerun=True — see queuePxiApply's docstring)."""
        self._apply(freerun=freerun)

    def apply_param(self, key, val):
        """Set one param (clamped to its hard bounds) without applying —
        used by the ring/global-frequency panel to stage values onto
        multiple pairs before applying them together."""
        _, fmt, lo, hi = self._entries[key]
        clamped = max(lo, min(hi, val))
        self._set_value(key, clamped, fmt)

    def get_ring(self):
        return self._ring_var.get()

    def set_ring(self, ring):
        if ring in RING_OPTIONS:
            self._ring_var.set(ring)

    def is_disabled(self):
        return self._disabled_var.get()

    def set_disabled(self, disabled):
        if disabled != self._disabled_var.get():
            self._disabled_var.set(disabled)
            self._on_disable_toggle()

    def get_values(self):
        """Current freq/amp/offset/phase/ring/disabled as shown in the GUI."""
        return (self._vars["freq"].get(), self._vars["amp"].get(),
                self._vars["offset"].get(), self._vars["phase"].get(),
                self._ring_var.get(), self._disabled_var.get())

    def load_values(self, freq, amp, offset, phase, ring="Outer", disabled=False):
        """Populate sliders/entries/ring/disable from a saved config and
        immediately apply (unless disabled)."""
        self.set_disabled(disabled)
        self.set_ring(ring)
        for key, val in (("freq", freq), ("amp", amp), ("offset", offset), ("phase", phase)):
            _, fmt, lo, hi = self._entries[key]
            clamped = max(lo, min(hi, val))
            self._set_value(key, clamped, fmt)
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

        headers = ["#", "Model", "Bus", "Slot", "Last Check"]
        widths  = [3,   10,      5,     5,      12]
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
        tk.Label(card_frame,
                 text="Live per-channel read-back is not available with the pi620lx "
                      "interface (no PIFGLX_Get*-equivalent calls) — this table shows "
                      "card identity only, not live signal state.",
                 bg=BG, fg=FG_DIM, font=("Helvetica", 7, "italic"),
                 wraplength=520, justify="left").grid(
            row=2, column=0, columnspan=len(headers), sticky="w", padx=4, pady=(4, 0))

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

        # Connection status derived from the raw pxiSession/pxiCards globals directly
        with pxiLock:
            connected = pxiConnected
            n_cards = len(pxiCards)
            has_relay = pxiRelayCard is not None
        if connected:
            self._status_dot.config(fg=GREEN)
            self._status_lbl.config(text="CONNECTED", fg=GREEN)
        else:
            self._status_dot.config(fg=RED)
            self._status_lbl.config(text="OFFLINE", fg=RED)
        self._info_lbl.config(
            text=f"Cards: {n_cards}  |  Relay: {'found' if has_relay else 'missing'}  |  "
                 f"Reinit count: {pxiReinitCount}  |  IP: {PXI_IP}")
        if self.focus_get() is not self._ip_entry:
            self._ip_var.set(PXI_IP)

        # Card table — rebuild in background to avoid blocking on the PXI bus
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
        """Gather card bus/device identity (runs in background thread).

        pi620lx.Card has no CardId()/CardLoc() (unlike pilxi's
        Pi_Card_ByDevice) and no PIFGLX_Get* read-back, so this can no longer
        show a live per-channel generator status table — only the bus/device
        location _openPXI() stamped onto each card (card._bus/_device) plus a
        static model label, since pi620lx.Base.findCards() only ever returns
        41-620 cards by construction. The main window's per-pair display
        still echoes the last commanded value only. The relay card (40-115)
        is shown as its own row since it's identified separately from the FG
        cards — though nothing currently drives it (discovered but unused).
        """
        rows = []
        with pxiLock:
            for idx, card in enumerate(pxiCards):
                bus = getattr(card, "_bus", "?")
                device = getattr(card, "_device", "?")
                rows.append({
                    "idx":    idx,
                    "model":  "41-620 FG",
                    "bus":    str(bus),
                    "slot":   str(device),
                    "ts":     time.strftime("%H:%M:%S"),
                })
            if pxiRelayCard is not None:
                bus = getattr(pxiRelayCard, "_bus", "?")
                device = getattr(pxiRelayCard, "_device", "?")
                rows.append({
                    "idx":    len(pxiCards),
                    "model":  "40-115 Relay",
                    "bus":    str(bus),
                    "slot":   str(device),
                    "ts":     time.strftime("%H:%M:%S"),
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
                info["ts"],
            ]
            col_colors = [FG, FG, FG, FG, FG]
            row_labels = []
            for c, (val, w, fg) in enumerate(zip(cols_data, widths, col_colors)):
                lbl = tk.Label(self._card_grid_frame, text=val,
                               bg=BG, fg=fg, font=("Courier", 8),
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
            tk.Label(relay_frame, text=RELAY_NAMES[i], bg=BG, fg=FG,
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
# MANUAL MODE  (bubble-nucleation frequency/amplitude sweep — phase not a
# concern here, only freq/amp; see AskUserQuestion decisions: coarse/fine
# slider pairs, debounced real-time apply, NOT_UPDATED via the queue helpers
# above, lock only per-pair/ring controls)
# ══════════════════════════════════════════════════════════════════════════════

_MANUAL_DEBOUNCE_MS = 100   # ms of slider/entry inactivity before an apply is sent

# (key, label, hard_min, hard_max, default, fmt, fine_span) — fine_span is the
# +/- window the fine slider covers around the current value.
MANUAL_PARAMS = [
    ("freq",   "Frequency (Hz)", 100.0, 1_000_000.0, 40_000.0, ".0f", 2_000.0),
    ("amp",    "Amplitude (V)",    0.0,        20.0,     10.0,  ".3f",     1.0),
    ("offset", "Offset (V)",       0.0,         5.0,      0.0,  ".3f",     0.5),
]

# (key, label, hard_min, hard_max, default, fmt, fine_span) — same shape as
# MANUAL_PARAMS, consumed by SweepModeWindow's DialControls. "rate" is Hz/s,
# not a raw card parameter — see _SWEEP_STEP_TIME_MS/_applyPxiSweepChannel
# for the conversion into generateSweep()'s stepSize/stepTime.
SWEEP_PARAMS = [
    ("minFreq", "Min Frequency (Hz)", 100.0, 1_000_000.0, 20_000.0, ".0f", 2_000.0),
    ("maxFreq", "Max Frequency (Hz)", 100.0, 1_000_000.0, 60_000.0, ".0f", 2_000.0),
    ("rate",    "Sweep Rate (Hz/s)",    0.0,   500_000.0, 10_000.0, ".0f", 5_000.0),
    ("amp",     "Amplitude (V)",        0.0,        20.0,     10.0, ".3f",     1.0),
    ("offset",  "Offset (V)",           0.0,         5.0,      0.0, ".3f",     0.5),
]


class DialControl(tk.Frame):
    """One power-supply-style control: a coarse slider spanning the full
    range, a fine slider spanning a small window around the current value,
    and a numeric entry — all three always agree on the same value. Moving
    any of them schedules on_commit(value) after _MANUAL_DEBOUNCE_MS of
    inactivity (coalesces bursts of slider motion into one hardware command
    instead of flooding pxiQueue — see AskUserQuestion's 'debounced' choice).
    """

    def __init__(self, parent, label, lo, hi, default, fmt, fine_span, on_commit, **kw):
        kw.setdefault("bg", BG)
        super().__init__(parent, **kw)
        self._lo, self._hi = lo, hi
        self._fmt = fmt
        self._fine_span = fine_span
        self._on_commit = on_commit
        self._base = default     # value the fine slider's zero point sits at
        self._value = default    # last-known absolute value
        self._debounce_id = None
        self._suspend = False    # True while programmatically syncing widgets

        tk.Label(self, text=label, fg=FG, bg=self["bg"],
                 font=("Helvetica", 9, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))

        tk.Label(self, text="Coarse", fg=FG_DIM, bg=self["bg"],
                 font=("Helvetica", 8)).grid(row=1, column=0, sticky="w")
        self._coarse_var = tk.DoubleVar(value=default)
        self._coarse = tk.Scale(
            self, from_=lo, to=hi, variable=self._coarse_var,
            orient="horizontal", length=220, showvalue=False,
            bg=self["bg"], fg=FG, troughcolor=BG_HL,
            activebackground=BLUE, highlightthickness=0, bd=0,
            command=self._on_coarse_move)
        self._coarse.grid(row=1, column=1, sticky="ew", padx=(6, 0))

        tk.Label(self, text="Fine", fg=FG_DIM, bg=self["bg"],
                 font=("Helvetica", 8)).grid(row=2, column=0, sticky="w")
        self._fine_var = tk.DoubleVar(value=0.0)
        self._fine = tk.Scale(
            self, from_=-fine_span, to=fine_span, variable=self._fine_var,
            orient="horizontal", length=220, showvalue=False,
            bg=self["bg"], fg=FG, troughcolor=BG_HL,
            activebackground=GREEN, highlightthickness=0, bd=0,
            command=self._on_fine_move)
        self._fine.grid(row=2, column=1, sticky="ew", padx=(6, 0))

        entry_row = tk.Frame(self, bg=self["bg"])
        entry_row.grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 0))
        tk.Label(entry_row, text="Value:", fg=FG_DIM, bg=self["bg"],
                 font=("Helvetica", 8)).pack(side="left")
        self._entry = tk.Entry(entry_row, width=12, justify="center",
                               bg=BG_HL, fg=FG, insertbackground=FG,
                               relief="flat", bd=2)
        self._entry.insert(0, format(default, fmt))
        self._entry.pack(side="left", padx=(6, 0))
        self._entry.bind("<Return>", self._on_entry_commit)
        self._entry.bind("<FocusOut>", self._on_entry_commit)

        self.columnconfigure(1, weight=1)

    # ── widget callbacks ──────────────────────────────────────────────────

    def _on_coarse_move(self, v):
        if self._suspend:
            return
        self._base = float(v)
        self._suspend = True
        self._fine_var.set(0.0)
        self._suspend = False
        self._set_value(self._base)

    def _on_fine_move(self, v):
        if self._suspend:
            return
        val = max(self._lo, min(self._hi, self._base + float(v)))
        self._set_value(val)

    def _on_entry_commit(self, _event):
        try:
            val = max(self._lo, min(self._hi, float(self._entry.get())))
        except ValueError:
            return
        self.set_absolute(val, notify=True)

    def _set_value(self, val):
        self._value = val
        self._entry.delete(0, "end")
        self._entry.insert(0, format(val, self._fmt))
        self._schedule_commit()

    def _schedule_commit(self):
        if self._debounce_id is not None:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(_MANUAL_DEBOUNCE_MS, self._fire_commit)

    def _fire_commit(self):
        self._debounce_id = None
        if self._on_commit:
            self._on_commit(self._value)

    # ── public API ────────────────────────────────────────────────────────

    def set_absolute(self, val, notify):
        """Programmatically set the control to val, re-centering both
        sliders on it. If notify is False (e.g. loading a newly-selected
        channel's current value), on_commit is NOT fired — this just
        reflects existing state rather than commanding a change."""
        val = max(self._lo, min(self._hi, val))
        self._base = val
        self._value = val
        self._suspend = True
        self._coarse_var.set(val)
        self._fine_var.set(0.0)
        self._suspend = False
        self._entry.delete(0, "end")
        self._entry.insert(0, format(val, self._fmt))
        if notify:
            self._schedule_commit()
        elif self._debounce_id is not None:
            self.after_cancel(self._debounce_id)
            self._debounce_id = None

    def get(self):
        return self._value


class ManualModeWindow(tk.Toplevel):
    """Standalone window for manually dialing in frequency/amplitude/offset —
    phase isn't a concern here (bubble nucleation tuning only cares about
    freq/amp/offset), so PairControls' phase value is simply carried through
    untouched. Reuses PairControls.apply_param()+apply() (the same path the
    main window's Ring/Global-Frequency panel already uses) rather than
    talking to pxiQueue directly, so NOT_UPDATED/RUNNING tracking and the
    main LXI table stay in sync for free.

    Opening this window locks the main window's per-pair and ring/global
    controls (via app._set_array_controls_locked) so the two can't fight
    over the same channels; closing it unlocks them again.

    A STOP/ENGAGE interlock gates all of this: the window opens STOPPED —
    dial movement is freely staged (the numbers update, the entry/table
    reflect it) but nothing is sent to hardware — until the operator
    explicitly presses ENGAGE. While engaged, dial commits apply live;
    pressing STOP immediately kills output on every pair this window has
    touched and disengages again, requiring another explicit ENGAGE push
    before anything can move the array again.
    """

    def __init__(self, app):
        super().__init__(app)
        self._app = app
        self.title("Manual Mode — Frequency / Amplitude Tuning")
        self.configure(bg=BG)
        self.minsize(620, 620)
        self.resizable(True, True)

        self._dials = {}       # key -> DialControl
        self._row_labels = []  # per-pair [freq_lbl, amp_lbl, status_lbl]
        self._touched_pairs = set()   # pair indices freerun-applied here — see _on_close()
        self._engaged = False  # interlock state — see class docstring

        app._set_array_controls_locked(True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        stateBus.subscribe(self._on_hw_event)
        self._load_selection()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self):
        warn = tk.Label(self, bg=BG, fg=YELLOW, font=("Helvetica", 8, "italic"),
                 text="Manual Mode owns the array — per-pair and ring/global "
                      "controls on the main window are locked while this is open.",
                 wraplength=580, justify="left")
        warn.pack(fill="x", padx=10, pady=(8, 4))

        interlock_frame = tk.LabelFrame(self, text="Output Interlock", bg=BG, fg=FG,
                                        font=("Helvetica", 9, "bold"), padx=8, pady=6)
        interlock_frame.pack(fill="x", padx=10, pady=4)
        self._interlock_lbl = tk.Label(interlock_frame, text="● STOPPED", bg=BG, fg=RED,
                                       font=("Helvetica", 11, "bold"))
        self._interlock_lbl.pack(side="left")
        self._stop_btn = tk.Button(
            interlock_frame, text="STOP", bg=BG_HL, fg=RED, relief="flat",
            padx=16, pady=4, font=("Helvetica", 9, "bold"),
            activebackground=RED, activeforeground=BG,
            command=self._stop)
        self._stop_btn.pack(side="right", padx=(6, 0))
        self._engage_btn = tk.Button(
            interlock_frame, text="ENGAGE", bg=BG_HL, fg=GREEN, relief="flat",
            padx=16, pady=4, font=("Helvetica", 9, "bold"),
            activebackground=GREEN, activeforeground=BG,
            command=self._engage)
        self._engage_btn.pack(side="right")

        sel_frame = tk.LabelFrame(self, text="Target", bg=BG, fg=FG,
                                  font=("Helvetica", 9, "bold"), padx=8, pady=6)
        sel_frame.pack(fill="x", padx=10, pady=4)
        tk.Label(sel_frame, text="Apply to:", bg=BG, fg=FG,
                 font=("Helvetica", 9)).pack(side="left")
        self._targets = ["Global (All Channels)"] + [
            f"Pair {p + 1} (Card {CHANNEL_MAP[p][0] + 1} Ch {CHANNEL_MAP[p][1]})"
            for p in range(NUM_PAIRS)
        ]
        self._target_var = tk.StringVar(value=self._targets[0])
        target_box = ttk.Combobox(sel_frame, textvariable=self._target_var,
                                  values=self._targets, state="readonly", width=32)
        target_box.pack(side="left", padx=(6, 0))
        target_box.bind("<<ComboboxSelected>>", lambda _e: self._load_selection())

        dial_frame = tk.LabelFrame(self, text="Controls", bg=BG, fg=FG,
                                   font=("Helvetica", 9, "bold"), padx=10, pady=8)
        dial_frame.pack(fill="x", padx=10, pady=4)
        for key, label, lo, hi, default, fmt, fine_span in MANUAL_PARAMS:
            dial = DialControl(dial_frame, label, lo, hi, default, fmt, fine_span,
                               on_commit=lambda val, k=key: self._commit(k, val))
            dial.pack(fill="x", pady=(0, 10))
            self._dials[key] = dial

        table_frame = tk.LabelFrame(self, text="Array Configuration", bg=BG, fg=FG,
                                    font=("Helvetica", 9, "bold"), padx=6, pady=4)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        headers = ["Pair", "Card/Ch", "Freq (Hz)", "Amp (V)", "Offset (V)", "Status"]
        for col, h in enumerate(headers):
            tk.Label(table_frame, text=h, bg=BG_HL, fg=FG_DIM,
                     font=("Helvetica", 8, "bold"), padx=6, pady=2,
                     relief="flat").grid(row=0, column=col, sticky="ew", padx=1, pady=1)

        for p in range(NUM_PAIRS):
            card_idx, ch_num = CHANNEL_MAP[p]
            bg = BG_ALT if p % 2 else BG
            vals = [str(p + 1), f"Card {card_idx + 1} Ch {ch_num}", "—", "—", "—", "IDLE"]
            row = []
            for col, val in enumerate(vals):
                fg = PAIR_COLORS[p] if col == 0 else FG
                lbl = tk.Label(table_frame, text=val, bg=bg, fg=fg,
                               font=("Courier", 8), padx=6, pady=2, relief="flat")
                lbl.grid(row=p + 1, column=col, sticky="ew", padx=1, pady=1)
                row.append(lbl)
            self._row_labels.append(row)

        # Seed the table from whatever's already commanded.
        for p in range(NUM_PAIRS):
            state = pxiChannelState[p]
            if state is not None:
                self._update_row(p, state["freq"], state["amp"],
                                 state["offset"], state["status"])

        tk.Button(self, text="Close", bg=BG_HL, fg=FG, relief="flat",
                  padx=12, pady=4, activebackground="#4e4e70", activeforeground=FG,
                  command=self._on_close).pack(pady=(0, 8))

        self._update_interlock_ui()

    # ── interlock ─────────────────────────────────────────────────────────

    def _engage(self):
        """Push the interlock to ENGAGED and immediately apply whatever the
        dials are currently showing to the current target(s) — so pressing
        ENGAGE always starts output matching what's on screen, not
        whatever was last live before STOP was pressed."""
        if self._engaged:
            return
        self._engaged = True
        self._update_interlock_ui()
        self._push_current_dials_to_targets()
        logMsg("INFO", "Manual Mode: ENGAGED — outputs live")

    def _stop(self):
        """Push the interlock to STOPPED and immediately kill output on
        every pair this window has touched. Dial movement keeps working
        afterward (staging only) until ENGAGE is pressed again."""
        if not self._engaged:
            return
        self._engaged = False
        self._update_interlock_ui()
        for idx in sorted(self._touched_pairs):
            ctrl = self._app._pair_controls[idx]
            if not ctrl.is_disabled():
                queuePxiStopPair(idx)
        logMsg("INFO", "Manual Mode: STOPPED — outputs disengaged")

    def _update_interlock_ui(self):
        if self._engaged:
            self._interlock_lbl.config(text="● ENGAGED", fg=GREEN)
            self._engage_btn.configure(state="disabled")
            self._stop_btn.configure(state="normal")
        else:
            self._interlock_lbl.config(text="● STOPPED", fg=RED)
            self._engage_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")

    # ── target selection ──────────────────────────────────────────────────

    def _selected_pair(self):
        """Returns a pair_idx, or None if 'Global' is selected."""
        idx = self._targets.index(self._target_var.get())
        return None if idx == 0 else idx - 1

    def _current_targets(self):
        pair_idx = self._selected_pair()
        return list(range(NUM_PAIRS)) if pair_idx is None else [pair_idx]

    def _load_selection(self):
        """Reflect the selected target's current freq/amp onto the dials
        without firing a commit — this is just loading state, not a change.
        If the interlock is already ENGAGED, also re-affirm the new target
        live at those values (so switching targets while engaged doesn't
        silently leave the newly-selected pair un-driven)."""
        pair_idx = self._selected_pair()
        if pair_idx is None:
            # Global: show the first enabled pair's values as a representative
            # starting point (there is no single "the" value across an array
            # that may be individually configured).
            source = next((c for c in self._app._pair_controls if not c.is_disabled()),
                          self._app._pair_controls[0] if self._app._pair_controls else None)
        else:
            source = self._app._pair_controls[pair_idx]
        if source is None:
            return
        freq, amp, offset, _phase, _ring, _disabled = source.get_values()
        self._dials["freq"].set_absolute(freq, notify=False)
        self._dials["amp"].set_absolute(amp, notify=False)
        self._dials["offset"].set_absolute(offset, notify=False)
        if self._engaged:
            self._push_current_dials_to_targets()

    # ── committing changes ────────────────────────────────────────────────

    def _push_current_dials_to_targets(self):
        """Apply whatever the freq/amp/offset dials currently show to every
        pair in the current target set, with freerun=True (CONT trigger
        mode — see pxi_worker's docstring). Used by ENGAGE and by target
        switches that happen while already engaged."""
        freq = self._dials["freq"].get()
        amp = self._dials["amp"].get()
        offset = self._dials["offset"].get()
        for idx in self._current_targets():
            ctrl = self._app._pair_controls[idx]
            if ctrl.is_disabled():
                continue
            ctrl.apply_param("freq", freq)
            ctrl.apply_param("amp", amp)
            ctrl.apply_param("offset", offset)
            ctrl.apply(freerun=True)
            self._touched_pairs.add(idx)

    def _commit(self, key, val):
        """Fired (debounced) from a DialControl — always stages the new
        value onto the target PairControls(es); only actually pushed to
        hardware (freerun=True, CONT trigger mode — see pxi_worker's
        docstring) while the interlock is ENGAGED. While STOPPED, this just
        updates the dial/entry display so the operator can dial in values
        before committing to output. Every pair touched while engaged is
        remembered in self._touched_pairs so _on_close()/STOP can restore/
        kill it correctly."""
        for idx in self._current_targets():
            ctrl = self._app._pair_controls[idx]
            if ctrl.is_disabled():
                continue
            ctrl.apply_param(key, val)
            if self._engaged:
                ctrl.apply(freerun=True)
                self._touched_pairs.add(idx)

    # ── live table updates ────────────────────────────────────────────────

    def _on_hw_event(self, event, data):
        if event != "channel_update":
            return
        self.after(0, self._apply_hw_event, data)

    def _apply_hw_event(self, data):
        if not self.winfo_exists():
            return
        p = data.get("pair", 0)
        self._update_row(p, data.get("freq", 0.0), data.get("amp", 0.0),
                         data.get("offset", 0.0), data.get("status", "IDLE"))

    def _update_row(self, pair_idx, freq, amp, offset, status):
        if not (0 <= pair_idx < len(self._row_labels)):
            return
        row = self._row_labels[pair_idx]
        row[2].config(text=f"{freq:.0f}")
        row[3].config(text=f"{amp:.3f}")
        row[4].config(text=f"{offset:.3f}")
        status_fg = {"RUNNING": GREEN, "NOT_UPDATED": YELLOW}.get(status, FG_DIM)
        row[5].config(text=status, fg=status_fg)

    # ── shutdown ──────────────────────────────────────────────────────────

    def _on_close(self):
        """If still ENGAGED, restore normal (POSEDGE, trigger-gated)
        operation on every pair Manual Mode put into CONT/free-run mode —
        re-applies each one through the ordinary path (freerun=False) using
        whatever values are currently staged on its PairControls, so the
        array comes back out of Manual Mode exactly as it would from a
        normal Apply. If STOPPED, those pairs are already off — closing
        the window shouldn't resurrect output the operator just killed, so
        nothing further is sent."""
        if self._engaged:
            for idx in sorted(self._touched_pairs):
                ctrl = self._app._pair_controls[idx]
                if not ctrl.is_disabled():
                    ctrl.apply(freerun=False)
        self._app._set_array_controls_locked(False)
        self.destroy()


class SweepModeWindow(tk.Toplevel):
    """Standalone window for driving one or all pairs through a
    trigger-gated frequency sweep (card.generateSweep() instead of
    generateSignal()) — for exciting a resonance/dispersion scan across a
    frequency band rather than dialing in one fixed tone.

    Unlike ManualModeWindow, every armed channel here is POSEDGE/FRONT-
    trigger-gated exactly like a normal main-window Apply: Arm configures
    and calls outputOn() but nothing actually starts sweeping until the
    relay trigger fires, so all armed channels start their sweep in lockstep
    off the shared trigger line. This window therefore also owns a copy of
    the main window's Fire Trigger control (same "fire_relay" queue command)
    rather than needing its own free-run interlock.

    Opening this window locks the main window's per-pair and ring/global
    controls (via app._set_array_controls_locked), same as Manual Mode —
    the two can't be allowed to fight over the same channels.
    """

    def __init__(self, app):
        super().__init__(app)
        self._app = app
        self.title("Sweep Mode — Frequency Sweep Tuning")
        self.configure(bg=BG)
        self.minsize(640, 640)
        self.resizable(True, True)

        self._dials = {}       # key -> DialControl
        self._row_labels = []  # per-pair [freq_lbl, amp_lbl, offset_lbl, status_lbl]
        self._touched_pairs = set()   # pair indices armed here — see _on_close()

        app._set_array_controls_locked(True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        stateBus.subscribe(self._on_hw_event)

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self):
        warn = tk.Label(self, bg=BG, fg=YELLOW, font=("Helvetica", 8, "italic"),
                 text="Sweep Mode owns the array — per-pair and ring/global "
                      "controls on the main window are locked while this is open. "
                      "Arm stages the sweep and waits on the trigger; Fire Trigger "
                      "starts every armed channel sweeping in sync.",
                 wraplength=600, justify="left")
        warn.pack(fill="x", padx=10, pady=(8, 4))

        sel_frame = tk.LabelFrame(self, text="Target", bg=BG, fg=FG,
                                  font=("Helvetica", 9, "bold"), padx=8, pady=6)
        sel_frame.pack(fill="x", padx=10, pady=4)
        tk.Label(sel_frame, text="Apply to:", bg=BG, fg=FG,
                 font=("Helvetica", 9)).pack(side="left")
        self._targets = ["Global (All Channels)"] + [
            f"Pair {p + 1} (Card {CHANNEL_MAP[p][0] + 1} Ch {CHANNEL_MAP[p][1]})"
            for p in range(NUM_PAIRS)
        ]
        self._target_var = tk.StringVar(value=self._targets[0])
        target_box = ttk.Combobox(sel_frame, textvariable=self._target_var,
                                  values=self._targets, state="readonly", width=32)
        target_box.pack(side="left", padx=(6, 0))

        dial_frame = tk.LabelFrame(self, text="Sweep Controls", bg=BG, fg=FG,
                                   font=("Helvetica", 9, "bold"), padx=10, pady=8)
        dial_frame.pack(fill="x", padx=10, pady=4)
        for key, label, lo, hi, default, fmt, fine_span in SWEEP_PARAMS:
            dial = DialControl(dial_frame, label, lo, hi, default, fmt, fine_span,
                               on_commit=None)
            dial.pack(fill="x", pady=(0, 10))
            self._dials[key] = dial

        action = tk.Frame(self, bg=BG)
        action.pack(fill="x", padx=10, pady=(0, 4))
        tk.Button(action, text="Arm", bg=BG_HL, fg=GREEN, relief="flat",
                  padx=12, pady=5, font=("Helvetica", 9, "bold"),
                  activebackground=GREEN, activeforeground=BG,
                  command=self._arm).pack(side="left", padx=(0, 10))
        tk.Button(action, text="Fire Trigger", bg=BG_HL, fg=YELLOW, relief="flat",
                  padx=12, pady=5, font=("Helvetica", 9, "bold"),
                  activebackground=YELLOW, activeforeground=BG,
                  command=self._fire_relay).pack(side="left", padx=(0, 10))
        tk.Button(action, text="Stop", bg=BG_HL, fg=RED, relief="flat",
                  padx=12, pady=5, font=("Helvetica", 9, "bold"),
                  activebackground=RED, activeforeground=BG,
                  command=self._stop).pack(side="left", padx=(0, 10))

        table_frame = tk.LabelFrame(self, text="Array Configuration", bg=BG, fg=FG,
                                    font=("Helvetica", 9, "bold"), padx=6, pady=4)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        headers = ["Pair", "Card/Ch", "Start Freq (Hz)", "Amp (V)", "Offset (V)", "Status"]
        for col, h in enumerate(headers):
            tk.Label(table_frame, text=h, bg=BG_HL, fg=FG_DIM,
                     font=("Helvetica", 8, "bold"), padx=6, pady=2,
                     relief="flat").grid(row=0, column=col, sticky="ew", padx=1, pady=1)

        for p in range(NUM_PAIRS):
            card_idx, ch_num = CHANNEL_MAP[p]
            bg = BG_ALT if p % 2 else BG
            vals = [str(p + 1), f"Card {card_idx + 1} Ch {ch_num}", "—", "—", "—", "IDLE"]
            row = []
            for col, val in enumerate(vals):
                fg = PAIR_COLORS[p] if col == 0 else FG
                lbl = tk.Label(table_frame, text=val, bg=bg, fg=fg,
                               font=("Courier", 8), padx=6, pady=2, relief="flat")
                lbl.grid(row=p + 1, column=col, sticky="ew", padx=1, pady=1)
                row.append(lbl)
            self._row_labels.append(row)

        # Seed the table from whatever's already commanded.
        for p in range(NUM_PAIRS):
            state = pxiChannelState[p]
            if state is not None:
                self._update_row(p, state["freq"], state["amp"],
                                 state["offset"], state["status"])

        tk.Button(self, text="Close", bg=BG_HL, fg=FG, relief="flat",
                  padx=12, pady=4, activebackground="#4e4e70", activeforeground=FG,
                  command=self._on_close).pack(pady=(0, 8))

    # ── target selection ──────────────────────────────────────────────────

    def _selected_pair(self):
        """Returns a pair_idx, or None if 'Global' is selected."""
        idx = self._targets.index(self._target_var.get())
        return None if idx == 0 else idx - 1

    def _current_targets(self):
        pair_idx = self._selected_pair()
        return list(range(NUM_PAIRS)) if pair_idx is None else [pair_idx]

    # ── arm / trigger / stop ──────────────────────────────────────────────

    def _arm(self):
        """Stage the current dial values onto every pair in the current
        target set and arm it (POSEDGE/FRONT trigger, outputOn()) — nothing
        actually starts sweeping until Fire Trigger closes the relay."""
        minFreq = self._dials["minFreq"].get()
        maxFreq = self._dials["maxFreq"].get()
        rate = self._dials["rate"].get()
        amp = self._dials["amp"].get()
        offset = self._dials["offset"].get()
        if maxFreq < minFreq:
            logMsg("WARNING", "Sweep Mode: max frequency is below min frequency — swap them")
            return
        for idx in self._current_targets():
            ctrl = self._app._pair_controls[idx]
            if ctrl.is_disabled():
                continue
            queuePxiApplySweep(idx, minFreq, maxFreq, rate, amp, offset)
            self._touched_pairs.add(idx)
        logMsg("INFO",
            f"Sweep Mode: armed {minFreq:.0f}-{maxFreq:.0f}Hz @ {rate:.0f}Hz/s "
            f"on {'all channels' if self._selected_pair() is None else f'pair {self._selected_pair()+1}'}")

    def _fire_relay(self):
        pxiQueue.put(("fire_relay",))

    def _stop(self):
        """Immediately kill output on every pair this window has armed."""
        for idx in sorted(self._touched_pairs):
            ctrl = self._app._pair_controls[idx]
            if not ctrl.is_disabled():
                queuePxiStopPair(idx)
        logMsg("INFO", "Sweep Mode: stopped")

    # ── live table updates ────────────────────────────────────────────────

    def _on_hw_event(self, event, data):
        if event != "channel_update":
            return
        self.after(0, self._apply_hw_event, data)

    def _apply_hw_event(self, data):
        if not self.winfo_exists():
            return
        p = data.get("pair", 0)
        self._update_row(p, data.get("freq", 0.0), data.get("amp", 0.0),
                         data.get("offset", 0.0), data.get("status", "IDLE"))

    def _update_row(self, pair_idx, freq, amp, offset, status):
        if not (0 <= pair_idx < len(self._row_labels)):
            return
        row = self._row_labels[pair_idx]
        row[2].config(text=f"{freq:.0f}")
        row[3].config(text=f"{amp:.3f}")
        row[4].config(text=f"{offset:.3f}")
        status_fg = {"RUNNING": GREEN, "NOT_UPDATED": YELLOW}.get(status, FG_DIM)
        row[5].config(text=status, fg=status_fg)

    # ── shutdown ──────────────────────────────────────────────────────────

    def _on_close(self):
        """Turns off every pair this window armed, then restores each back
        to whatever its PairControls currently show (ordinary fixed-tone
        Apply, freerun=False) — mirrors ManualModeWindow's restore-on-close
        behavior so Sweep Mode never leaves a channel sweeping or silently
        stuck armed after the window closes."""
        for idx in sorted(self._touched_pairs):
            ctrl = self._app._pair_controls[idx]
            if not ctrl.is_disabled():
                queuePxiStopPair(idx)
                ctrl.apply(freerun=False)
        self._app._set_array_controls_locked(False)
        self.destroy()


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

        self._tkLogHandler = _TkLogHandler()
        logging.getLogger().addHandler(self._tkLogHandler)
        self.after(100, self._drain_log_handler)

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

        # Ring / global controls
        ring_frame = tk.LabelFrame(content, text="Ring / Global Controls",
                                   bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                                   padx=8, pady=4)
        ring_frame.pack(fill="x", padx=10, pady=4)
        self._build_ring_panel(ring_frame)

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
        self._apply_all_btn = tk.Button(
            action, text="Apply All Pairs", bg=BG_HL, fg=FG, relief="flat",
            padx=12, pady=5,
            activebackground="#4e4e70", activeforeground=FG,
            command=self._apply_all)
        self._apply_all_btn.pack(side="left", padx=(0, 10))
        # "Apply All Pairs" configures every pair's channel and calls
        # outputOn() immediately (see pxi_worker's docstring) — there is no
        # separate arm/trigger step. "Stop All" is the one global kill switch.
        tk.Button(action, text="Stop All", bg=BG_HL, fg=RED, relief="flat",
                  padx=12, pady=5,
                  activebackground=RED, activeforeground=BG,
                  command=self._stop_all).pack(side="left", padx=(0, 10))
        # Fires the 40-115 relay's trigger pulse only — does not touch any
        # channel's config/output. Channels must already be armed (Apply
        # calls outputOn()) and waiting on the external FRONT trigger for
        # this to actually start them generating.
        tk.Button(action, text="Fire Trigger", bg=BG_HL, fg=YELLOW, relief="flat",
                  padx=12, pady=5,
                  activebackground=YELLOW, activeforeground=BG,
                  command=self._fire_relay).pack(side="left", padx=(0, 10))
        tk.Button(action, text="LXI Manager…", bg=BG_HL, fg=BLUE, relief="flat",
                  padx=12, pady=5,
                  activebackground=BLUE, activeforeground=BG,
                  command=self._open_lxi_manager).pack(side="left", padx=(0, 10))
        tk.Button(action, text="Relay Manager…", bg=BG_HL, fg=YELLOW, relief="flat",
                  padx=12, pady=5,
                  activebackground=YELLOW, activeforeground=BG,
                  command=self._open_relay_manager).pack(side="left", padx=(0, 10))
        tk.Button(action, text="Manual Mode…", bg=BG_HL, fg=GREEN, relief="flat",
                  padx=12, pady=5,
                  activebackground=GREEN, activeforeground=BG,
                  command=self._open_manual_mode).pack(side="left", padx=(0, 10))
        tk.Button(action, text="Sweep Mode…", bg=BG_HL, fg=BLUE, relief="flat",
                  padx=12, pady=5,
                  activebackground=BLUE, activeforeground=BG,
                  command=self._open_sweep_mode).pack(side="left", padx=(0, 10))

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

            tk.Label(col, text=RELAY_NAMES[i], fg=FG_DIM, bg=BG,
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
        headers = ["Pair", "Card/Ch", "Type",
                   "Freq (Hz)", "Amp (V)", "Offset (V)", "Phase (°)", "Status"]
        for col, h in enumerate(headers):
            tk.Label(parent, text=h, bg=BG_HL, fg=FG_DIM,
                     font=("Helvetica", 8, "bold"),
                     padx=6, pady=2, relief="flat").grid(
                row=0, column=col, sticky="ew", padx=1, pady=1)

        for p in range(NUM_PAIRS):
            card_idx, ch_num = CHANNEL_MAP[p]
            row_defaults = [str(p + 1), f"Card {card_idx + 1} Ch {ch_num}", "SINE",
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

    def _build_ring_panel(self, parent):
        """Two convenience actions layered on top of the per-pair sliders —
        neither is hardware-aware on its own; both just stage values onto
        each PairControls (via apply_param()) and then call apply(), so the
        result is identical to the operator setting those sliders by hand
        and clicking Apply. Disabled pairs are skipped entirely (their
        sliders are left untouched and no apply is sent)."""
        freq_row = tk.Frame(parent, bg=BG)
        freq_row.pack(fill="x", pady=(0, 6))
        tk.Label(freq_row, text="Frequency (Hz) — all channels:", bg=BG, fg=FG,
                 font=("Helvetica", 9)).pack(side="left")
        self._global_freq_var = tk.StringVar(value="40000")
        self._global_freq_entry = tk.Entry(freq_row, textvariable=self._global_freq_var, width=10,
                 bg=BG_HL, fg=FG, insertbackground=FG,
                 relief="flat", bd=2)
        self._global_freq_entry.pack(side="left", padx=(6, 8))
        self._global_freq_btn = tk.Button(freq_row, text="Apply to All", bg=BG_HL, fg=BLUE, relief="flat",
                  padx=10, activebackground=BLUE, activeforeground=BG,
                  command=self._apply_global_frequency)
        self._global_freq_btn.pack(side="left")

        ring_row = tk.Frame(parent, bg=BG)
        ring_row.pack(fill="x")
        tk.Label(ring_row, text="Inner Amp (V):", bg=BG, fg=FG,
                 font=("Helvetica", 9)).pack(side="left")
        self._inner_amp_var = tk.StringVar(value="10.0")
        self._inner_amp_entry = tk.Entry(ring_row, textvariable=self._inner_amp_var, width=8,
                 bg=BG_HL, fg=FG, insertbackground=FG,
                 relief="flat", bd=2)
        self._inner_amp_entry.pack(side="left", padx=(6, 14))
        tk.Label(ring_row, text="Ratio (Outer/Inner):", bg=BG, fg=FG,
                 font=("Helvetica", 9)).pack(side="left")
        self._ratio_var = tk.StringVar(value="1.0")
        self._ratio_entry = tk.Entry(ring_row, textvariable=self._ratio_var, width=8,
                 bg=BG_HL, fg=FG, insertbackground=FG,
                 relief="flat", bd=2)
        self._ratio_entry.pack(side="left", padx=(6, 14))
        tk.Label(ring_row, text="Phase Δ (Outer − Inner, °):", bg=BG, fg=FG,
                 font=("Helvetica", 9)).pack(side="left")
        self._phase_delta_var = tk.StringVar(value="0.0")
        self._phase_delta_entry = tk.Entry(ring_row, textvariable=self._phase_delta_var, width=8,
                 bg=BG_HL, fg=FG, insertbackground=FG,
                 relief="flat", bd=2)
        self._phase_delta_entry.pack(side="left", padx=(6, 14))
        self._ring_settings_btn = tk.Button(ring_row, text="Apply Ring Settings", bg=BG_HL, fg=GREEN, relief="flat",
                  padx=10, activebackground=GREEN, activeforeground=BG,
                  command=self._apply_ring_settings)
        self._ring_settings_btn.pack(side="left")

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
                row[2].config(text=data.get("waveform", "SINE"))
                row[3].config(text=f"{data['freq']:.0f}")
                row[4].config(text=f"{data['amp']:.3f}")
                row[5].config(text=f"{data['offset']:.3f}")
                row[6].config(text=f"{data['phase']:.1f}")
                status = data.get("status", "IDLE")
                status_fg = {"RUNNING": GREEN, "NOT_UPDATED": YELLOW}.get(status, FG_DIM)
                row[7].config(text=status, fg=status_fg)

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
        queuePxiStopAll()

    def _fire_relay(self):
        pxiQueue.put(("fire_relay",))

    def _apply_global_frequency(self):
        try:
            freq = float(self._global_freq_var.get())
        except ValueError:
            logMsg("WARNING", "Global frequency: invalid number")
            return
        for ctrl in self._pair_controls:
            if ctrl.is_disabled():
                continue
            ctrl.apply_param("freq", freq)
            ctrl.apply()
        logMsg("INFO", f"Global frequency: {freq:.0f} Hz applied to all enabled channels")

    def _apply_ring_settings(self):
        try:
            inner_amp = float(self._inner_amp_var.get())
            ratio = float(self._ratio_var.get())
            phase_delta = float(self._phase_delta_var.get())
        except ValueError:
            logMsg("WARNING", "Ring settings: invalid number(s)")
            return
        outer_amp = inner_amp * ratio
        inner_phase = 0.0
        outer_phase = phase_delta % 360.0
        for ctrl in self._pair_controls:
            if ctrl.is_disabled():
                continue
            if ctrl.get_ring() == "Inner":
                amp, phase = inner_amp, inner_phase
            else:
                amp, phase = outer_amp, outer_phase
            ctrl.apply_param("amp", amp)
            ctrl.apply_param("phase", phase)
            ctrl.apply()
        logMsg("INFO",
            f"Ring settings applied: inner={inner_amp:.3f}V @ 0.0°, "
            f"outer={outer_amp:.3f}V @ {outer_phase:.1f}°")

    def _refresh_config_dropdown(self):
        self._config_dropdown["values"] = listGroundConfigs()

    def _save_config(self):
        name = self._save_name_var.get().strip()
        if not name:
            logMsg("WARNING", "Save config: no name entered")
            return
        safe_name = re.sub(r"[^A-Za-z0-9_\- ]", "_", name)
        gui_values = [ctrl.get_values() for ctrl in self._pair_controls]
        try:
            path = saveGroundConfig(safe_name, gui_values=gui_values)
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
        if not rows:
            logMsg("WARNING", f"Ground config '{name}' has no saved pairs — nothing to load")
            return
        for pair_idx, row in enumerate(rows):
            if pair_idx >= len(self._pair_controls):
                break
            self._pair_controls[pair_idx].load_values(
                row["frequency"], row["amplitude"], row["offset"], row["phase"],
                row["ring"], row["disabled"])
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

    def _open_manual_mode(self):
        global _manualModeWindow
        if _manualModeWindow is not None and _manualModeWindow.winfo_exists():
            _manualModeWindow.lift()
            _manualModeWindow.focus_force()
        else:
            _manualModeWindow = ManualModeWindow(self)

    def _open_sweep_mode(self):
        global _sweepModeWindow
        if _sweepModeWindow is not None and _sweepModeWindow.winfo_exists():
            _sweepModeWindow.lift()
            _sweepModeWindow.focus_force()
        else:
            _sweepModeWindow = SweepModeWindow(self)

    def _set_array_controls_locked(self, locked):
        """Grey out (without stopping) every per-pair and ring/global control
        while Manual Mode owns the array — Stop All / Fire Trigger / LXI &
        Relay Manager stay usable as safety/diagnostic escape hatches (see
        AskUserQuestion decision: 'lock only per-pair controls')."""
        for ctrl in self._pair_controls:
            ctrl.set_locked(locked)
        state = "disabled" if locked else "normal"
        self._apply_all_btn.configure(state=state)
        self._global_freq_entry.configure(state=state)
        self._global_freq_btn.configure(state=state)
        self._inner_amp_entry.configure(state=state)
        self._ratio_entry.configure(state=state)
        self._phase_delta_entry.configure(state=state)
        self._ring_settings_btn.configure(state=state)

    def _toggle_relay(self, relay_idx, state):
        relayQueue.put(("set", relay_idx, state))

    def _log(self, msg):
        self._log_box.config(state="normal")
        self._log_box.insert("end", msg + "\n")
        self._log_box.see("end")
        self._log_box.config(state="disabled")

    def _drain_log_handler(self):
        """Pull queued log records (from _TkLogHandler, any thread) onto the
        log box — runs on the main thread only, see _TkLogHandler docstring
        for why emit() can't touch Tk directly."""
        while True:
            try:
                msg = self._tkLogHandler.queue.get_nowait()
            except queue.Empty:
                break
            self._log(msg)
        self.after(100, self._drain_log_handler)

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
