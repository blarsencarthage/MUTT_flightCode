"""Standalone pi620lx demo that drives the full 12-transducer / 6-pair array.

Built directly on the vendor pi620lx ClientBridge wrapper the same way test01
in this directory does — this does NOT import pickeringInterface.py. It's a
separate, self-contained architecture: its own channel model and its own
connect/apply/close functions, not a trimmed copy of that module.

Array layout (pair count, card/channel map, per-pair default parameters)
mirrors groundController.py so this exercises the same 6 transducer pairs
(12 elements, 2 cards x 3 channels) that groundController commands.
"""
import math
import os
import sys
import time

_pkg_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_pkg_dir, "pilxi-5.7"))
import pilxi
import pi620lx

# ══════════════════════════════════════════════════════════════════════════
# ARRAY LAYOUT  (matches groundController.py's NUM_PAIRS / CHANNEL_MAP)
# ══════════════════════════════════════════════════════════════════════════

PXI_IP = "169.254.112.5"
PXI_CONNECT_TIMEOUT_MS = 5000

NUM_PAIRS       = 6
CHANNELS_PER_CARD = 3   # matches groundController's 2 cards x 3 channels layout

# Per-pair settings — each of the 6 channels gets its own independent
# (frequency Hz, amplitude V, offset V, phase deg, symmetry) tuple instead of
# sharing one global default. Edit these values to tune each transducer pair
# individually. Amplitude is given here as a voltage; buildArray() converts
# it to the dB attenuation card.setAttenuation() expects via
# voltageToDB(V) = log10(V / 20).
CHANNEL_SETTINGS = [
    # freq (Hz), amp (V),  offset (V), phase (deg), symmetry (0-100)
    (10_000.0, 5.0, 0.0,   0.0, 50.0),   # pair 1
    (0_000.0, 5.0, 0.0,  60.0, 50.0),   # pair 2
    (0_000.0, 5.0, 0.0, 120.0, 50.0),   # pair 3
    (0_000.0, 5.0, 0.0, 180.0, 50.0),   # pair 4
    (0_000.0, 5.0, 0.0, 240.0, 50.0),   # pair 5
    (0_000.0, 5.0, 0.0, 300.0, 50.0),   # pair 6
]


def voltageToDB(voltage):
    """Convert a commanded amplitude voltage to the dB attenuation value
    card.setAttenuation() expects, per the conversion log10(voltage / 20)."""
    return math.log10(voltage / 20.0)


class PairChannel:
    """Commanded signal state for one transducer pair plus its hardware handle."""

    def __init__(self, pair_idx, card, channel, frequency, amplitude_voltage, offset, phase, symmetry):
        self.pair_idx          = pair_idx
        self.card              = card
        self.channel           = channel
        self.frequency         = frequency
        self.amplitude_voltage = amplitude_voltage
        self.amplitude         = voltageToDB(amplitude_voltage)   # dB attenuation for setAttenuation()
        self.offset            = offset
        self.phase             = phase
        self.symmetry          = symmetry
        self.shape             = card.signalShapes["SINE"]

    def __repr__(self):
        return (f"PairChannel(pair={self.pair_idx + 1}, bus={self.card._bus}, "
                f"channel={self.channel}, freq={self.frequency}Hz, "
                f"amp={self.amplitude_voltage}V ({self.amplitude:.3f}dB), "
                f"offset={self.offset}V, phase={self.phase}°)")


def connect(ip_address=PXI_IP, timeout=PXI_CONNECT_TIMEOUT_MS):
    """Open an LXI session and automatically open every 41-620 card it finds.

    Returns (session, cards) — no manual bus/device entry required; every
    card reported by findCards() is opened.
    """
    session = pilxi.Pi_Session(ip_address, timeout=timeout)
    sessionID = session.GetSessionID()

    base = pi620lx.Base(sessionID)
    cardLocs = base.findCards()

    cards = []
    for bus, device in cardLocs:
        card = base.openCard(bus, device)
        card._bus = bus
        card._device = device
        cards.append(card)
        print(f"Opened 41-620 card at bus={bus} device={device}")

    return session, cards


def buildArray(cards):
    """Map the 6 transducer pairs onto (card, channel), each with its own settings.

    pair_idx -> card index (pair_idx // CHANNELS_PER_CARD), channel number
    (pair_idx % CHANNELS_PER_CARD + 1) — derived automatically from however
    many cards connect() opened, rather than a fixed table.
    """
    pairs = []
    for pair_idx in range(NUM_PAIRS):
        card_idx = pair_idx // CHANNELS_PER_CARD
        ch_num   = pair_idx % CHANNELS_PER_CARD + 1
        if card_idx >= len(cards):
            raise RuntimeError(
                f"Pair {pair_idx + 1} needs card index {card_idx}, "
                f"but only {len(cards)} card(s) were found")
        freq, amp, offset, phase, symmetry = CHANNEL_SETTINGS[pair_idx]
        pairs.append(PairChannel(pair_idx, cards[card_idx], ch_num,
                                  freq, amp, offset, phase, symmetry))
    return pairs


def applyPair(pair):
    """Push a PairChannel's parameters to hardware and start generation."""
    card = pair.card
    card.setActiveChannel(pair.channel)
    card.outputOff()
    card.setTriggerMode(card.triggerSources["FRONT"], card.triggerModes["CONT"])
    card.setOutputOffsetVoltage(pair.offset, True)
    card.setAttenuation(pair.amplitude)
    card.generateSignal(pair.frequency / 1000.0, pair.shape, pair.symmetry,
                         startPhaseOffset=pair.phase, generate=False)
    card.outputOn()


def stopPair(pair):
    pair.card.setActiveChannel(pair.channel)
    pair.card.outputOff()


def closeCards(cards):
    seen = set()
    for card in cards:
        if id(card) not in seen:
            seen.add(id(card))
            card.close()


if __name__ == "__main__":

    print("pi620lx wrapper version: {}".format(pi620lx.__version__))

    session, cards = connect()
    pairs = buildArray(cards)

    try:
        for pair in pairs:
            print(f"Applying {pair!r}")
            applyPair(pair)
        time.sleep(5)

    except pi620lx.Error as error:
        print("Exception occurred:", error.message)

    finally:
        for pair in pairs:
            stopPair(pair)
        closeCards(cards)
