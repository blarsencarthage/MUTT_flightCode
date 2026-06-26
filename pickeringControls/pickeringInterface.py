
#Author: Braedon Larsen
#Created: 6.11.26
#Updated 6.23.26
import os
import sys
_pkg_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_pkg_dir, "pilxi-5.7"))
#TODO: Revise waveAtributes class to include the card address and channel number, bring 
#updateWaveform into the class and have it run whenever any of the set functions are run.
import pilxi
import pi620lx

class waveAtributes:
    """Stores all parameters that describe a single waveform channel output."""

    def __init__(self, channel, frequency, amplitude, offset, phase=0.0,
                 waveform_type=None):
        self._channel = channel
        self._frequency = frequency
        self._amplitude = amplitude
        self._offset = offset
        self._phase = phase % 360.0
        self._waveform_type = waveform_type  # expects a pilxi.WaveformTypes value

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

    def __repr__(self):
        return (f"waveAtributes(channel={self._channel}, frequency={self._frequency}, "
                f"amplitude={self._amplitude}, offset={self._offset}, "
                f"phase={self._phase}, waveform_type={self._waveform_type})")



def initPXIE(ip_address="pxi"):
    #Initalizes PXI interface and returns a list of open card objects.

    session = pilxi.Pi_Session(ip_address)

    if session is None:
        print("Failed to initialize PXI interface.")
        return None
    else:
        print("PXI interface initialized successfully.")

    freeCards = session.FindFreeCards()

    cards = []
    for bus, device in freeCards:
        try:
            card = session.OpenCard(bus, device)
            card.ClearCard()
            cards.append(card)
        except pilxi.Error as ex:
            print("Exception occurred:", ex.message)

    print(f"Found {len(cards)} valid 41-620 compliant cards.")
    return cards


def updateWaveform(card, wave: waveAtributes):
    if card is None:
        print("No card available.")
        return
    channel   = wave.getChannel()
    frequency = wave.getFrequency()
    amplitude = wave.getAmplitude()
    offset    = wave.getOffset()
    phase     = wave.getPhase()
    wf_type   = wave.getWaveformType() or pilxi.WaveformTypes.PIFGLX_WAVEFORM_SINE
    try:
        print(f"Updating waveform on card {card.CardId()}, channel {channel}: "
              f"frequency={frequency}, amplitude={amplitude}, offset={offset}, phase={phase}")
        card.PIFGLX_AbortGeneration(channel)
        card.PIFGLX_SetWaveform(channel, wf_type)
        card.PIFGLX_SetAmplitude(channel, amplitude)
        card.PIFGLX_SetFrequency(channel, frequency)
        if offset < 0 or offset > 5:
            print("Offset voltage must be between 0 and 5 volts.")
            card.PIFGLX_SetDcOffset(channel, 0)
        else:
            card.PIFGLX_SetDcOffset(channel, offset)
        card.PIFGLX_SetStartPhase(channel, phase)
        card.PIFGLX_InitiateGeneration(channel)
    except pilxi.Error as error:
        print("Exception occurred:", error.message)

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

    print("=== Waveform Generator Self-Check ===")

    if not cards:
        print("No cards provided — nothing to check.")
        return {"passed": [], "failed": []}

    print(f"Cards received: {len(cards)}")

    passed = []
    failed = []

    for i, card in enumerate(cards):
        card_label = f"Card {i + 1}"

        # Identify the card
        try:
            card_id = card.CardId()
        except pilxi.Error as ex:
            print(f"\n  {card_label}: FAILED — could not read CardId ({ex.message})")
            failed.append((i + 1, "Unknown", f"CardId read failed: {ex.message}"))
            continue

        print(f"\n  {card_label} [{card_id}]")

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
            print(f"    FAILED — could not write test values ({ex.message})")
            failed.append((i + 1, card_id, f"Write failed: {ex.message}"))
            continue

        # --- Read values back ---
        try:
            read_freq   = card.PIFGLX_GetFrequency(TEST_CHANNEL)
            read_amp    = card.PIFGLX_GetAmplitude(TEST_CHANNEL)
            read_offset = card.PIFGLX_GetDcOffset(TEST_CHANNEL)
            read_phase  = card.PIFGLX_GetStartPhase(TEST_CHANNEL)
        except pilxi.Error as ex:
            print(f"    FAILED — could not read back values ({ex.message})")
            failed.append((i + 1, card_id, f"Read failed: {ex.message}"))
            continue

        print(f"    {'Attribute':<12} {'Set':>10}  {'Read':>10}  {'Match':>6}")
        print(f"    {'-'*44}")

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
            print(f"    {name:<12} {expected:>9.3f}  {actual:>9.3f}  {status:>6}  {unit}")
            if not ok:
                mismatches.append(f"{name}: expected {expected} {unit}, got {actual} {unit}")

        if mismatches:
            reason = "; ".join(mismatches)
            print(f"    Result: FAILED ({len(mismatches)} mismatch(es))")
            failed.append((i + 1, card_id, reason))
        else:
            print(f"    Result: PASSED")
            passed.append((i + 1, card_id))

    # --- Summary ---
    print(f"\n=== Summary ===")
    print(f"  Total checked : {len(cards)}")
    print(f"  Passed        : {len(passed)}")
    print(f"  Failed        : {len(failed)}")

    if passed:
        print("\nPassed:")
        for idx, cid in passed:
            print(f"  Card {idx}: {cid}")

    if failed:
        print("\nFailed:")
        for entry in failed:
            idx, cid = entry[0], entry[1]
            reason = entry[2] if len(entry) > 2 else "unknown"
            print(f"  Card {idx}: {cid} — {reason}")

    return {"passed": passed, "failed": failed}
