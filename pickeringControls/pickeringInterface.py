
#Author: Braedon Larsen
#Created: 6.11.26
#Updated 6.23.26
import os
import sys
import csv
_pkg_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_pkg_dir, "pilxi-5.7"))
#TODO: Revise waveAtributes class to include the card address and channel number, bring
#updateWaveform into the class and have it run whenever any of the set functions are run.
import pilxi
import pi620lx
import logging
log = logging.getLogger("mutt.LXI")
_WAVEFORM_TYPE_MAP = {
    "SINE":      pilxi.WaveformTypes.PIFGLX_WAVEFORM_SINE,
    "SQUARE":    pilxi.WaveformTypes.PIFGLX_WAVEFORM_SQUARE,
    "TRIANGLE":  pilxi.WaveformTypes.PIFGLX_WAVEFORM_TRIANGLE,
    "RAMP":      pilxi.WaveformTypes.PIFGLX_WAVEFORM_RAMP_UP,
    "RAMP_UP":   pilxi.WaveformTypes.PIFGLX_WAVEFORM_RAMP_UP,
    "RAMP_DOWN": pilxi.WaveformTypes.PIFGLX_WAVEFORM_RAMP_DOWN,
    "DC":        pilxi.WaveformTypes.PIFGLX_WAVEFORM_DC,
    "PULSE":     pilxi.WaveformTypes.PIFGLX_WAVEFORM_PULSE,
    "PWM":       pilxi.WaveformTypes.PIFGLX_WAVEFORM_PWM,
    "ARB":       pilxi.WaveformTypes.PIFGLX_WAVEFORM_ARB,
}

class waveAtributes:
    """Stores all parameters that describe a single waveform channel output."""

    def __init__(self, channel, frequency, amplitude, offset, card=None, phase=0.0,
                 waveform_type=pilxi.WaveformTypes.PIFGLX_WAVEFORM_SINE,
                 activeTime=0.0, settlingTime=0.0):
        self._channel = channel
        self._card = card
        self._frequency = frequency
        self._amplitude = amplitude
        self._offset = offset
        self._phase = phase % 360.0
        self._waveform_type = waveform_type
        self._activeTime = activeTime    # seconds the waveform is actively driven
        self._settlingTime = settlingTime  # seconds allowed for signal to settle

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

    # --- amplitude ---
    def getAmplitude(self):
        return self._amplitude

    def setAmplitude(self, amplitude):
        self._amplitude = amplitude

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
                f"activeTime={self._activeTime}, settlingTime={self._settlingTime})")


def readConfigs(configFilePath):
    """Read waveform configurations from a CSV file.

    Expected CSV columns (header row required):
        channel, frequency, amplitude, offset, phase, waveform_type, activeTime, settlingTime

    Returns a list of waveAtributes objects with card=None.
    Assign card handles after hardware is initialized.
    """
    waveforms = []
    with open(configFilePath, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            wf_key = row["waveform_type"].strip().upper()
            wf_type = _WAVEFORM_TYPE_MAP.get(wf_key, pilxi.WaveformTypes.PIFGLX_WAVEFORM_SINE)
            wave = waveAtributes(
                channel=int(row["channel"]),
                frequency=float(row["frequency"]),
                amplitude=float(row["amplitude"]),
                offset=float(row["offset"]),
                phase=float(row["phase"]),
                waveform_type=wf_type,
                activeTime=float(row["activeTime"]),
                settlingTime=float(row["settlingTime"]),
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


def initPXIE(ip_address="pxi"):
    #Initalizes PXI interface and returns a list of open card objects.

    session = pilxi.Pi_Session(ip_address)

    if session is None:
        log.error("Failed to initialize PXI interface.")
        return None
    else:
        log.info("PXI interface initialized successfully.")

    freeCards = session.FindFreeCards() #Returns a list of tuples (bus, device) for each free card found.

    cards = []
    for bus, device in freeCards: #Opens sessions with each free card and appends them to the cards list.
        try: # NOTE: As long as the session with the LXI is open, the card will remain open.
            card = session.OpenCard(bus, device) #Returns a Pi_Card_ByDevice object
            card.ClearCard()
            cards.append(card)
        except pilxi.Error as ex:
            log.error("Exception occurred: %s", ex.message)
    log.info(f"Found {len(cards)} valid cards.")
    cardWaves = buildWaveforms(cards)
    return cardWaves


def updateWaveform(card, wave: waveAtributes):
    if card is None:
        log.error("No card available.")
        return
    channel   = wave.getChannel()
    frequency = wave.getFrequency()
    amplitude = wave.getAmplitude()
    offset    = wave.getOffset()
    phase     = wave.getPhase()
    wf_type   = wave.getWaveformType()
    try:
        log.info(f"Updating waveform on card {card.CardId()}, channel {channel}: "
                 f"frequency={frequency}, amplitude={amplitude}, offset={offset}, phase={phase}")
        card.PIFGLX_AbortGeneration(channel)
        card.PIFGLX_SetWaveform(channel, wf_type)
        card.PIFGLX_SetAmplitude(channel, amplitude)
        card.PIFGLX_SetFrequency(channel, frequency)
        if offset < 0 or offset > 5:
            log.warning("Offset voltage must be between 0 and 5 volts.")
            card.PIFGLX_SetDcOffset(channel, 0)
        else:
            card.PIFGLX_SetDcOffset(channel, offset)
        card.PIFGLX_SetStartPhase(channel, phase)
        card.PIFGLX_InitiateGeneration(channel)
    except pilxi.Error as error:
        log.error("Exception occurred: %s", error.message)

def waveformSelfCheck(cards):
    """
    Self-check routine for an array of 41-620 waveform generator card objects.

    For each card:
      1. Writes known arbitrary values to channel 1 via the PXI connection.
      2. Reads those values back from the card.
      3. Compares set vs. read with a small tolerance.

    Prints a per-card result and a final summary.
    Returns a dict with keys "passed" and "failed", each a list of
    (card_index, card_id) or (card_index, card_id, reason) tuples.
    """
    TEST_CHANNEL   = 1
    TEST_FREQUENCY = 1000.0   # Hz
    TEST_AMPLITUDE = 2.5      # Volts peak-to-peak
    TEST_OFFSET    = 1.0      # Volts DC offset
    TEST_PHASE     = 45.0     # Degrees
    TOLERANCE      = 0.01     # Acceptable difference for float comparisons

    log.info("=== Waveform Generator Self-Check ===")

    if not cards:
        log.info("No cards provided — nothing to check.")
        return {"passed": [], "failed": []}

    log.info(f"Cards received: {len(cards)}")
    log.info(f"Waveform self-check started for {len(cards)} cards.")

    passed = []
    failed = []

    for i, card in enumerate(cards):
        card_label = f"Card {i + 1}"

        # Identify the card
        try:
            card_id = card.CardId()
        except pilxi.Error as ex:
            log.error(f"\n  {card_label}: FAILED — could not read CardId ({ex.message})")
            failed.append((i + 1, "Unknown", f"CardId read failed: {ex.message}"))
            continue

        log.info(f"\n  {card_label} [{card_id}]")

        # --- Write test values ---
        try:
            card.PIFGLX_AbortGeneration(TEST_CHANNEL)
            card.PIFGLX_SetWaveform(TEST_CHANNEL, pilxi.WaveformTypes.PIFGLX_WAVEFORM_SINE)
            card.PIFGLX_SetFrequency(TEST_CHANNEL, TEST_FREQUENCY)
            card.PIFGLX_SetAmplitude(TEST_CHANNEL, TEST_AMPLITUDE)
            card.PIFGLX_SetDcOffset(TEST_CHANNEL, TEST_OFFSET)
            card.PIFGLX_SetStartPhase(TEST_CHANNEL, TEST_PHASE)
            card.PIFGLX_InitiateGeneration(TEST_CHANNEL)
        except pilxi.Error as ex:
            log.error(f"    FAILED — could not write test values ({ex.message})")
            failed.append((i + 1, card_id, f"Write failed: {ex.message}"))
            continue

        # --- Read values back ---
        try:
            read_freq   = card.PIFGLX_GetFrequency(TEST_CHANNEL)
            read_amp    = card.PIFGLX_GetAmplitude(TEST_CHANNEL)
            read_offset = card.PIFGLX_GetDcOffset(TEST_CHANNEL)
            read_phase  = card.PIFGLX_GetStartPhase(TEST_CHANNEL)
        except pilxi.Error as ex:
            log.error(f"    FAILED — could not read back values ({ex.message})")
            failed.append((i + 1, card_id, f"Read failed: {ex.message}"))
            continue

        log.info(f"    {'Attribute':<12} {'Set':>10}  {'Read':>10}  {'Match':>6}")
        log.info(f"    {'-'*44}")

        mismatches = []
        checks = [
            ("Frequency",  TEST_FREQUENCY, read_freq,   "Hz"),
            ("Amplitude",  TEST_AMPLITUDE, read_amp,    "V"),
            ("DC Offset",  TEST_OFFSET,    read_offset, "V"),
            ("Phase",      TEST_PHASE,     read_phase,  "deg"),
        ]
        for name, expected, actual, unit in checks:
            ok = abs(actual - expected) <= TOLERANCE
            status = "OK" if ok else "FAIL"
            log.info(f"    {name:<12} {expected:>9.3f}  {actual:>9.3f}  {status:>6}  {unit}")
            if not ok:
                mismatches.append(f"{name}: expected {expected} {unit}, got {actual} {unit}")

        if mismatches:
            reason = "; ".join(mismatches)
            log.error(f"    Result: FAILED ({len(mismatches)} mismatch(es))")
            failed.append((i + 1, card_id, reason))
        else:
            log.info(f"    Result: PASSED")
            passed.append((i + 1, card_id))

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

