
#Author: Braedon Larsen
#Created: 6.11.26
#Updated 7.17.26 — switched from pilxi's generic PIFGLX_* card interface to the
#vendor-supplied pi620lx wrapper (see test01 in this directory, provided by
#Pickering support), which is the methodology that actually works with the
#41-620 cards in this chassis. pilxi is still used for the LXI session itself
#(pi620lx.Base needs a session ID from it) but no PIFGLX_* / Pi_Session.OpenCard
#calls are made anymore — see pickeringREADME.md for the full list of behavior
#changes this brought (dropped live read-back, dropped CardId()/CardLoc(),
#amplitude now means dB attenuation, frequency now means kHz, new symmetry
#field).
import os
import sys
import csv
import math
_pkg_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_pkg_dir, "pilxi-5.7"))
#TODO: Revise waveAtributes class to include the card address and channel number, bring
#updateWaveform into the class and have it run whenever any of the set functions are run.
import pilxi
import pi620lx
import logging
log = logging.getLogger("mutt.LXI")

# pi620lx.Base/Card.signalShapes only defines these three — hardcoded here
# (rather than pulled from a Base/Card instance) since the values are fixed
# and this map needs to exist before any card is opened. RAMP/DC/PULSE/PWM/ARB
# (previously supported via pilxi.WaveformTypes) have no pi620lx equivalent
# and are not supported — any of those keys falls back to SINE, same as any
# other unrecognized key.
_WAVEFORM_TYPE_MAP = {
    "SINE":     0,
    "TRIANGLE": 1,
    "SQUARE":   2,
}
_WAVEFORM_TYPE_SINE = _WAVEFORM_TYPE_MAP["SINE"]

# 41-620 attenuator: 0 dB = full-scale output, per py620 readme's documented
# 0-40 dB attenuation range. Full-scale output is 20 Vpp — used to convert a
# target volts amplitude into the dB attenuation card.setAttenuation() wants.
_FULL_SCALE_VOLTS = 20.0
_ATTENUATION_DB_MIN = 0.0
_ATTENUATION_DB_MAX = 40.0



def _cardLabel(card):
    """Best-effort human-readable label for a card, for logging.

    pi620lx.Card has no CardId()/CardLoc() (unlike pilxi's Pi_Card_ByDevice).
    initPXIE() stamps _bus/_device onto every card it opens (see below); this
    just formats them, falling back gracefully if a card wasn't opened that
    way (e.g. a mock in a test).
    """
    bus = getattr(card, "_bus", None)
    device = getattr(card, "_device", None)
    if bus is None or device is None:
        return "<unknown card>"
    return f"PXI{bus}::{device}"


class waveAtributes:
    """Stores all parameters that describe a single waveform channel output.

    NOTE on units (pi620lx methodology, see test01 in this directory):
      - frequency is stored in Hz (same as before) but is converted to kHz
        by updateWaveform() before being passed to card.generateSignal(),
        which expects kHz.
      - amplitude is stored as dB of attenuation (card.setAttenuation()),
        NOT a target voltage — pi620lx's simple/recommended workflow has no
        direct "set amplitude in volts" call. Existing CSV configs written
        for the old volts-based amplitude field will need their values
        reinterpreted as dB.
      - getAmplitudeVolts()/setAmplitudeVolts() convert to/from a target
        output voltage, relative to the 41-620's documented full-scale
        (_FULL_SCALE_VOLTS at 0 dB) and 0-40 dB attenuation range — use
        these when a caller wants to think in volts instead of dB.
      - offset is a voltage in the range -5 to 5V (card.setOutputOffsetVoltage()).
      - symmetry (0-100) is new — pi620lx.Card.generateSignal() requires it
        and the old pilxi PIFGLX_* calls had no equivalent. Defaults to 50.
    """

    def __init__(self, channel, frequency, amplitude, offset, card=None, phase=0.0,
                 waveform_type=_WAVEFORM_TYPE_SINE,
                 activeTime=0.0, settlingTime=0.0, symmetry=50.0):
        self._channel = channel
        self._card = card
        self._frequency = frequency
        self._amplitude = amplitude
        self._offset = offset
        self._phase = phase % 360.0
        self._waveform_type = waveform_type
        self._activeTime = activeTime    # seconds the waveform is actively driven
        self._settlingTime = settlingTime  # seconds allowed for signal to settle
        self._symmetry = symmetry

    # --- channel ---
    def getChannel(self):
        return self._channel

    def setChannel(self, channel):
        self._channel = channel

    # --- frequency ---
    def getFrequency(self):
        return self._frequency

    def setFrequency(self, frequency):
        self._frequency = frequency

    # --- amplitude (dB attenuation — see class docstring) ---
    def getAmplitude(self):
        return self._amplitude

    def setAmplitude(self, amplitude):
        self._amplitude = amplitude

    # --- amplitude in volts (converted to/from dB attenuation) ---
    def getAmplitudeVolts(self):
        """Amplitude in volts, derived from the stored dB attenuation
        relative to _FULL_SCALE_VOLTS (0 dB)."""
        return _FULL_SCALE_VOLTS * (10 ** (-self._amplitude / 20.0))

    def setAmplitudeVolts(self, volts):
        """Set amplitude by target output volts.

        Converted to dB attenuation relative to _FULL_SCALE_VOLTS and
        clamped to the card's documented 0-40 dB attenuation range (0 dB =
        full scale, 40 dB = max attenuation, i.e. quietest).
        """
        if volts <= 0:
            db = _ATTENUATION_DB_MAX
        else:
            db = 20.0 * math.log10(_FULL_SCALE_VOLTS / volts)
            db = max(_ATTENUATION_DB_MIN, min(_ATTENUATION_DB_MAX, db))
        self._amplitude = db

    # --- offset ---
    def getOffset(self):
        return self._offset

    def setOffset(self, offset):
        self._offset = offset

    # --- phase ---
    def getPhase(self):
        return self._phase

    def setPhase(self, phase):
        self._phase = phase % 360.0

    # --- waveform type ---
    def getWaveformType(self):
        return self._waveform_type

    def setWaveformType(self, waveform_type):
        self._waveform_type = waveform_type

    # --- symmetry ---
    def getSymmetry(self):
        return self._symmetry

    def setSymmetry(self, symmetry):
        self._symmetry = symmetry

    # --- activeTime ---
    def getActiveTime(self):
        return self._activeTime

    def setActiveTime(self, activeTime):
        self._activeTime = activeTime

    # --- settlingTime ---
    def getSettlingTime(self):
        return self._settlingTime

    def setSettlingTime(self, settlingTime):
        self._settlingTime = settlingTime

    def __repr__(self):
        return (f"waveAtributes(channel={self._channel}, frequency={self._frequency}, "
                f"amplitude={self._amplitude}, offset={self._offset}, "
                f"phase={self._phase}, waveform_type={self._waveform_type}, "
                f"symmetry={self._symmetry}, activeTime={self._activeTime}, "
                f"settlingTime={self._settlingTime})")


def readConfigs(configFilePath):
    """Read waveform configurations from a CSV file.

    Expected CSV columns (header row required):
        channel, frequency, amplitude, offset, phase, waveform_type, activeTime, settlingTime
    Optional column:
        symmetry (0-100) — defaults to 50 if the column is absent or blank.

    Returns a list of waveAtributes objects with card=None.
    Assign card handles after hardware is initialized.
    """
    waveforms = []
    with open(configFilePath, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            wf_key = row["waveform_type"].strip().upper()
            wf_type = _WAVEFORM_TYPE_MAP.get(wf_key, _WAVEFORM_TYPE_SINE)
            symmetry_raw = row.get("symmetry", "") if hasattr(row, "get") else ""
            symmetry = float(symmetry_raw) if symmetry_raw not in (None, "") else 50.0
            wave = waveAtributes(
                channel=int(row["channel"]),
                frequency=float(row["frequency"]),
                amplitude=float(row["amplitude"]),
                offset=float(row["offset"]),
                phase=float(row["phase"]),
                waveform_type=wf_type,
                activeTime=float(row["activeTime"]),
                settlingTime=float(row["settlingTime"]),
                symmetry=symmetry,
            )
            waveforms.append(wave)
            log.info(f"Read waveform config: {wave}")
    return waveforms


def readAllConfigs(configFilePaths):
    """Read multiple waveform configuration CSV files.

    Args:
        configFilePaths: ordered list of CSV file paths, one per configuration.

    Returns:
        list[list[waveAtributes]] — one inner list of 6 waveAtributes per config,
        in the same order as configFilePaths. card=None on every entry; assign
        card handles after initPXIE() returns.
    """
    return [readConfigs(path) for path in configFilePaths]


def initPXIE(ip_address="pxi", timeout=5000):
    """Initializes the PXI/LXI interface and returns (session, list of waveAtributes).

    timeout (ms) is the TCP connect timeout — the default pilxi value (1000ms)
    is too short for a chassis that is still booting.

    Card discovery and control go through pi620lx (see test01 in this
    directory), which is 41-620-specific: pi620lx.Base.findCards() only ever
    returns 41-620 function generator cards, so — unlike the old
    pilxi.Pi_Session.FindFreeCards() approach — there is no need to guess
    whether a found card is actually a function generator, and no separate
    "free vs claimed" concept exposed by this API to check.

    NOTE: the returned session object MUST be kept alive by the caller for as
    long as the cards/waveforms are in use. Pi_Session.__del__ disconnects the
    LXI session, which invalidates every card opened from it — if the caller
    lets `session` go out of scope, Python garbage-collects it almost
    immediately (nothing else holds a Python reference to it; pi620lx cards
    only keep the raw session ID, not the Pi_Session wrapper) and every card
    goes invalid a moment later.
    """
    session = pilxi.Pi_Session(ip_address, timeout=timeout)

    if session is None:
        log.error("Failed to initialize PXI interface.")
        return None, []
    else:
        log.info("PXI interface initialized successfully.")

    try:
        sessionID = session.GetSessionID()
    except pilxi.Error as ex:
        log.error(f"GetSessionID() failed: {ex.message} — session is not usable right now.")
        return session, []

    pi620Base = pi620lx.Base(sessionID)

    try:
        cardLocs = pi620Base.findCards()  # [(bus, device), ...] — 41-620 cards only
    except pi620lx.Error as ex:
        log.error(f"findCards() failed: {ex.message}")
        return session, []

    if not cardLocs:
        log.warning("No 41-620 function generator cards found on this LXI unit "
                    "(cards may be claimed by another session/process, or the "
                    "chassis is still enumerating after connect).")

    cards = []
    for bus, device in cardLocs:
        try:
            card = pi620Base.openCard(bus, device)
            card._bus = bus
            card._device = device
            cards.append(card)
            log.info(f"Opened 41-620 card at bus={bus} device={device}")
        except pi620lx.Error as ex:
            log.error(f"Failed to open card at bus={bus} device={device}: {ex.message}")

    log.info(f"Found {len(cards)} valid cards.")
    cardWaves = buildWaveforms(cards)
    return session, cardWaves


def updateWaveform(card, wave: waveAtributes):
    if card is None:
        log.error("No card available.")
        return
    channel       = wave.getChannel()
    frequency_kHz = wave.getFrequency() / 1000.0
    attenuation   = wave.getAmplitude()   # dB — see waveAtributes docstring
    offset        = wave.getOffset()
    phase         = wave.getPhase()
    wf_type       = wave.getWaveformType()
    symmetry      = wave.getSymmetry()
    try:
        log.info(f"Updating waveform on card {_cardLabel(card)}, channel {channel}: "
                 f"frequency={frequency_kHz}kHz, attenuation={attenuation}dB, "
                 f"offset={offset}, phase={phase}, symmetry={symmetry}")
        card.setActiveChannel(channel)
        card.outputOff()
        card.setTriggerMode(card.triggerSources["FRONT"], card.triggerModes["CONT"])
        if offset < -5 or offset > 5:
            log.warning("Offset voltage must be between -5 and 5 volts.")
            card.setOutputOffsetVoltage(0.0, True)
        else:
            card.setOutputOffsetVoltage(offset, True)
        card.setAttenuation(attenuation)
        card.generateSignal(frequency_kHz, wf_type, symmetry,
                             startPhaseOffset=phase, generate=False)
        card.outputOn()
    except pi620lx.Error as error:
        log.error("Exception occurred: %s", error.message)


def abortGeneration(card, channel):
    """Stop signal generation on one channel of a card.

    pi620lx has no PIFGLX_AbortGeneration() equivalent — the closest is
    selecting the channel and switching its output off.
    """
    if card is None:
        return
    try:
        card.setActiveChannel(channel)
        card.outputOff()
    except pi620lx.Error as error:
        log.error("Exception occurred: %s", error.message)


def waveformSelfCheck(cards):
    """
    Self-check routine for an array of 41-620 waveform generator card objects.

    pi620lx has no PIFGLX_Get* read-back calls (unlike pilxi), so this can
    only verify that the write path itself doesn't raise — it can no longer
    read values back from hardware and compare, the way the old pilxi-based
    version did. A card that silently ignores a bad write will still show
    PASSED here.

    For each card: writes known values to channel 1, and reports whether the
    write raised an error.

    Prints a per-card result and a final summary.
    Returns a dict with keys "passed" and "failed", each a list of
    (card_index, card_label) or (card_index, card_label, reason) tuples.
    """
    TEST_CHANNEL     = 1
    TEST_FREQUENCY   = 1000.0   # Hz (converted to kHz before being sent)
    TEST_ATTENUATION = 3.0      # dB
    TEST_OFFSET      = 1.0      # Volts DC offset
    TEST_PHASE       = 45.0     # Degrees
    TEST_SYMMETRY    = 50.0

    log.info("=== Waveform Generator Self-Check (write-only — pi620lx has no read-back) ===")

    if not cards:
        log.info("No cards provided — nothing to check.")
        return {"passed": [], "failed": []}

    log.info(f"Cards received: {len(cards)}")

    passed = []
    failed = []

    for i, card in enumerate(cards):
        card_label = _cardLabel(card)
        log.info(f"\n  Card {i + 1} [{card_label}]")

        try:
            card.setActiveChannel(TEST_CHANNEL)
            card.outputOff()
            card.setTriggerMode(card.triggerSources["FRONT"], card.triggerModes["CONT"])
            card.setOutputOffsetVoltage(TEST_OFFSET, True)
            card.setAttenuation(TEST_ATTENUATION)
            card.generateSignal(TEST_FREQUENCY / 1000.0, _WAVEFORM_TYPE_SINE, TEST_SYMMETRY,
                                 startPhaseOffset=TEST_PHASE, generate=False)
            card.outputOn()
        except pi620lx.Error as ex:
            log.error(f"    FAILED — write raised an error ({ex.message})")
            failed.append((i + 1, card_label, f"Write failed: {ex.message}"))
            continue

        log.info(f"    Result: PASSED (write completed without error)")
        passed.append((i + 1, card_label))

    # --- Summary ---
    log.info(f"\n=== Summary ===")
    log.info(f"  Total checked : {len(cards)}")
    log.info(f"  Passed        : {len(passed)}")
    log.info(f"  Failed        : {len(failed)}")

    if passed:
        log.info(f"\nPassed:")
        for idx, cid in passed:
            log.info(f"  Card {idx}: {cid}")

    if failed:
        log.info(f"\nFailed:")
        for entry in failed:
            idx, cid = entry[0], entry[1]
            reason = entry[2] if len(entry) > 2 else "unknown"
            log.error(f"  Card {idx}: {cid} — {reason}")

    return {"passed": passed, "failed": failed}

def buildWaveforms(cardArray):
    """"
    Builds a list of 6 waveAtributes objects, 3 per card.

    """

    log.info(f"Building waveforms for {len(cardArray)} cards.")
    waveforms = []
    for card in cardArray:
        for channel in range(1, 4): #Using 3 channels per card
            wave = waveAtributes(channel=channel, card=card, frequency=0, amplitude=0, offset=0)
            waveforms.append(wave)
    return waveforms
