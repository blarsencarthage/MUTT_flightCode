# pi620lx / pilxi Quick Reference — bypassing pickeringHeader

Raw vendor-package calls needed to connect to the LXI cabinet and drive a
41-620 function generator card directly, without going through
`pickeringInterfaceV2.pickeringHeader`. For ad-hoc bench testing/debugging
only — `groundController.py` still uses `pickeringHeader` for normal
operation.

Both packages live under `pickeringControls/pilxi-5.7/` — `pilxi` (LXI
session, relay card) and `pi620lx` (41-620 function generator cards). Treat
both as third-party/vendor code — don't modify them; work around bugs at the
call site instead (see `PXI_DEBUG_NOTES.md`).

## Setup

```python
import os, sys
_pkg_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_pkg_dir, "pilxi-5.7"))
import pilxi
import pi620lx
```

## Connecting

```python
PXI_IP = "169.254.112.5"

# 1. Open the LXI session
session = pilxi.Pi_Session(PXI_IP, timeout=5000)   # ms
sessionID = session.GetSessionID()

# 2. Open pi620lx against that session, find/open the 41-620 card(s)
base = pi620lx.Base(sessionID)
cardLocs = base.findCards()          # -> [(bus, device), ...], 41-620s only
card = base.openCard(bus, device)    # or base.openCard() for the first one found
card._bus, card._device = bus, device   # optional, for your own logging — pi620lx.Card has no CardId()/CardLoc()
```

`findCards()` enumeration order is **not** guaranteed to match the chassis'
physical port labeling — if there's more than one card, print `bus`/`device`
and confirm against the physical slot before trusting which one you're
scoping.

## Finding the relay card (40-115-021, for trigger control)

The relay card is not a 41-620, so it's found through `pilxi` directly, not
`pi620lx`:

```python
relayCard = None
for bus, device in session.FindFreeCards():
    candidate = session.OpenCard(bus, device)
    if "40-115" in candidate.CardId():
        relayCard = candidate
        break
```

## Per-channel function generator control (`pi620lx.Card`)

All calls below operate on whatever channel `setActiveChannel()` last
selected on that `card` object — reselect before every subsequent call if
you're switching channels.

```python
card.setActiveChannel(channel)     # channel: 1-3 per vendor examples — verify
                                    # this is really 1-based on your hardware
                                    # before trusting it; suspected off-by-one
                                    # bug under investigation, see PXI_DEBUG_NOTES.md §9

card.outputOff()                   # de-energizes this channel's output
card.outputOn()                    # enables this channel's output — starts
                                    # generating per the channel's last
                                    # generateSignal()/trigger-mode config

card.setOutputOffsetVoltage(volts, connect)
    # volts: -5.0 to +5.0 (hardware range)
    # connect: bool, enable/disable the DC offset

card.setAttenuation(db)
    # db: 0-40, ATTENUATION not amplitude — see dB<->V conversion below

card.setTriggerMode(source, mode)
    # source: card.triggerSources[...]  (see enum below)
    # mode:   card.triggerModes[...]

card.generateSignal(frequency_kHz, signalType, symmetry,
                     startPhaseOffset=0.0, generate=True)
    # frequency_kHz: NOTE units are kHz, not Hz — divide your Hz value by 1000
    # signalType:    card.signalShapes[...]
    # symmetry:      0-100
    # startPhaseOffset: degrees
    # generate:      True = start generating immediately;
    #                False = configure only, defer start to outputOn()
    #                (this flag is currently suspected NOT to reliably gate
    #                output on this hardware — see PXI_DEBUG_NOTES.md §9;
    #                verify behavior explicitly before relying on it)
```

### Enums (identical values in both `pi620lx.Base` and `pi620lx.Card`)

```python
card.triggerModes = {
    "HIGH": 0x0, "LOW": 0x1, "POSEDGE": 0x2, "NEGEDGE": 0x3,
    "POSEDGESINGLE": 0x4, "NEGEDGESINGLE": 0x5, "CONT": 0x6,
}
card.triggerSources = {
    "FRONT": 0, "PXI0": 1, "PXI1": 2, "PXI2": 3, "PXI3": 4,
    "PXI4": 5, "PXI5": 6, "PXI6": 7, "PXI7": 8, "PXI_STAR": 9,
}
card.signalShapes = {"SINE": 0, "TRIANGLE": 1, "SQUARE": 2}
    # RAMP/DC/PULSE/PWM/ARB have no pi620lx equivalent — not supported
card.instrumentModes = {"CONFIGURE": 0, "GENERATE": 1}
```

## Relay control (trigger pulse, on the relay card, not the FG card)

```python
_RELAY_SUBUNIT = 1   # 1-based subunit on the 40-115-021
_RELAY_BIT = 1        # the one relay wired to the FG trigger lines

relayCard.OpBit(_RELAY_SUBUNIT, _RELAY_BIT, True)    # closed/energized (asserts 5V)
relayCard.OpBit(_RELAY_SUBUNIT, _RELAY_BIT, False)   # open/de-energized

relayCard.ReadBit(_RELAY_SUBUNIT, _RELAY_BIT)        # -> bool, current state
```

A trigger pulse is: close, hold ~50ms, open again.

## dB <-> Volts conversion

`card.setAttenuation()` only takes dB — there is no volts-native call. This
is the exact formula `groundController.py` uses (`_dbFromVolts()`), so
results stay consistent with the GUI:

```python
FULL_SCALE_VOLTS   = 10.0   # hardware full-scale, per Pickering_FuncGenManual.pdf
                             # Section 1's "Waveform Signal: 10V pk to pk, open
                             # circuit load" spec — see PXI_DEBUG_NOTES.md section 10
ATTENUATION_DB_MIN = 0.0
ATTENUATION_DB_MAX = 40.0

def dbFromVolts(volts):
    if volts <= 0:
        return ATTENUATION_DB_MAX
    db = 20.0 * math.log10(FULL_SCALE_VOLTS / volts)
    return max(ATTENUATION_DB_MIN, min(ATTENUATION_DB_MAX, db))

def voltsFromDb(db):
    return FULL_SCALE_VOLTS * (10 ** (-db / 20.0))
```

Usage: `card.setAttenuation(dbFromVolts(desired_volts))`.

## Cleanup

```python
card.close()
session.Close()
```

## Minimal end-to-end example (single channel, CONT/free-run — no trigger wait)

```python
import math, os, sys, time
_pkg_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_pkg_dir, "pilxi-5.7"))
import pilxi, pi620lx

FULL_SCALE_VOLTS = 20.0

def dbFromVolts(volts):
    if volts <= 0:
        return 40.0
    return max(0.0, min(40.0, 20.0 * math.log10(FULL_SCALE_VOLTS / volts)))

session = pilxi.Pi_Session("169.254.112.5", timeout=5000)
base = pi620lx.Base(session.GetSessionID())
bus, device = base.findCards()[0]
card = base.openCard(bus, device)

channel = 1
freq_hz, amp_v, offset_v, phase_deg = 20_000.0, 5.0, 0.0, 0.0

card.setActiveChannel(channel)
card.outputOff()
card.setTriggerMode(card.triggerSources["FRONT"], card.triggerModes["CONT"])
card.setOutputOffsetVoltage(offset_v, True)
card.setAttenuation(dbFromVolts(amp_v))
card.generateSignal(freq_hz / 1000.0, card.signalShapes["SINE"], 50.0,
                     startPhaseOffset=phase_deg, generate=False)
card.outputOn()

time.sleep(5)

card.outputOff()
card.close()
session.Close()
```

## Known open issues (see `PXI_DEBUG_NOTES.md` §9 for full investigation)

As of 2026-07-27, on this hardware: `generateSignal()`'s `generate=False`
flag does not appear to prevent output from starting; the programmed
frequency has been observed stuck at ~2.5kHz regardless of the requested
value; and amplitude has been observed capped near ~22mV regardless of the
requested dB/volts. Root cause unconfirmed — under active investigation with
raw pi620lx calls (bypassing `pickeringHeader`) to isolate whether this is a
wrapper bug, a channel-indexing mismatch, or a genuine hardware/firmware
limit.
