"""Standalone, manually-stepped diagnostic for the missing-DC-offset /
wrong-amplitude bug (reported 2026-07-30: 5V amplitude + 4.5V offset at
10kHz measured as ~2.8V amplitude with no DC offset on the scope).

Drives pilxi/pi620lx directly — no pickeringHeader — one step at a time,
with input() pauses, so a scope can be checked at each stage. Only exercises
channel 1 of the first card, free-running (CONT trigger) so no relay pulse
is needed to see output — this isolates amplitude/offset from the separate
arm/trigger bug already tracked in PXI_DEBUG_NOTES.md section 9.

Steps test one hypothesis: that the driver/firmware uses the *commanded*
offset to clamp amplitude headroom (amplitude/2 + |offset| <= full scale)
without ever actually connecting the offset DAC to the output — which would
explain reduced amplitude with zero DC shift.

Usage: run interactively (`python diag_offset_amplitude.py`), press Enter at
each pause, and record on the scope: amplitude (Vpp or Vpk — pick one and
stay consistent) and DC offset (mean level) at each checkpoint.
"""
import math
import os
import sys

_pkg_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_pkg_dir, "pilxi-5.7"))
import pilxi
import pi620lx

PXI_IP = "169.254.112.5"
TEST_FREQUENCY_HZ = 10_000.0   # matches the reported failing case
TEST_AMPLITUDE_V = 5.0
TEST_OFFSET_V = 4.5
TEST_PHASE_DEG = 0.0

# Matches groundController.py's _dbFromVolts() — card.setAttenuation()
# itself only takes dB, so amplitude is entered here in volts and converted.
# Full scale is 10Vpp open circuit per Pickering_FuncGenManual.pdf Section 1
# (see PXI_DEBUG_NOTES.md section 10 — the previous 20.0 here was wrong).
_FULL_SCALE_VOLTS   = 10.0
_ATTENUATION_DB_MIN = 0.0
_ATTENUATION_DB_MAX = 40.0


def _dbFromVolts(volts):
    if volts <= 0:
        return _ATTENUATION_DB_MAX
    db = 20.0 * math.log10(_FULL_SCALE_VOLTS / volts)
    return max(_ATTENUATION_DB_MIN, min(_ATTENUATION_DB_MAX, db))


def pause(msg):
    input(f"\n>>> {msg}\n    Press Enter to continue...")


def _configure(card, channel, amplitude_v, offset_v, connect_offset):
    """Configure+free-run one channel, CONT trigger so output starts
    immediately on outputOn() — no relay pulse needed for this diagnostic."""
    card.setActiveChannel(channel)
    card.outputOff()
    card.setTriggerMode(card.triggerSources["FRONT"], card.triggerModes["CONT"])
    card.setOutputOffsetVoltage(offset_v, connect_offset)
    card.setAttenuation(_dbFromVolts(amplitude_v))
    card.generateSignal(
        TEST_FREQUENCY_HZ / 1000.0,
        card.signalShapes["SINE"],
        50.0,
        startPhaseOffset=TEST_PHASE_DEG,
        generate=False,
    )
    card.outputOn()


if __name__ == "__main__":
    print(f"Connecting to LXI at {PXI_IP} ...")
    session = pilxi.Pi_Session(PXI_IP, timeout=5000)
    base = pi620lx.Base(session.GetSessionID())
    cardLocs = base.findCards()

    if not cardLocs:
        print("No 41-620 cards found — check LXI_IP/cabling.")
        session.Close()
        sys.exit(1)

    bus, device = cardLocs[0]
    card = base.openCard(bus, device)
    print(f"Opened 41-620 card at bus={bus} device={device}.")
    channel = 1

    # ---- Step 1: baseline — requested amplitude, no offset ----
    _configure(card, channel, TEST_AMPLITUDE_V, 0.0, True)
    pause(f"STEP 1: amp={TEST_AMPLITUDE_V}V, offset=0V, connect=True, "
          f"{TEST_FREQUENCY_HZ}Hz. Record amplitude and DC level on the "
          f"scope now (this is the no-offset baseline).")
    card.outputOff()

    # ---- Step 2: reported failing case — amplitude + offset together ----
    _configure(card, channel, TEST_AMPLITUDE_V, TEST_OFFSET_V, True)
    pause(f"STEP 2: amp={TEST_AMPLITUDE_V}V, offset={TEST_OFFSET_V}V, "
          f"connect=True, {TEST_FREQUENCY_HZ}Hz — this should reproduce the "
          f"reported bug (~2.8V amplitude, no DC shift). Record amplitude "
          f"and DC level now.")
    card.outputOff()

    # ---- Step 3: offset commanded but NOT connected ----
    _configure(card, channel, TEST_AMPLITUDE_V, TEST_OFFSET_V, False)
    pause(f"STEP 3: amp={TEST_AMPLITUDE_V}V, offset={TEST_OFFSET_V}V, "
          f"connect=False, {TEST_FREQUENCY_HZ}Hz. If amplitude is STILL "
          f"reduced (~2.8V) with connect=False, that confirms the commanded "
          f"offset value is clamping amplitude headroom independent of "
          f"whether the offset DAC is actually connected to the output. "
          f"If amplitude comes back to ~{TEST_AMPLITUDE_V}V here, the "
          f"headroom-clamp theory is ruled out. Record amplitude and DC "
          f"level now.")
    card.outputOff()

    # ---- Step 4: raw offset DAC code sweep, bypassing setOutputOffsetVoltage()'s
    # volts->code conversion entirely, to check whether the offset DAC moves
    # the trace at all on this hardware/driver.
    print("\n--- STEP 4: raw setOutputOffsetDacCode() sweep — bypasses the "
          "volts conversion in setOutputOffsetVoltage(). Code is a raw "
          "uint32 DAC value (assumed 16-bit: 0-65535); meaning of a given "
          "code is uncalibrated here, this only checks whether ANY code "
          "moves the DC level. ---")
    card.setActiveChannel(channel)
    card.outputOff()
    card.setTriggerMode(card.triggerSources["FRONT"], card.triggerModes["CONT"])
    card.setAttenuation(_dbFromVolts(TEST_AMPLITUDE_V))
    card.generateSignal(
        TEST_FREQUENCY_HZ / 1000.0,
        card.signalShapes["SINE"],
        50.0,
        startPhaseOffset=TEST_PHASE_DEG,
        generate=False,
    )
    for code in (0, 16384, 32768, 49152, 65535):
        try:
            card.setOutputOffsetDacCode(code, True)
        except pi620lx.Error as ex:
            print(f"setOutputOffsetDacCode({code}, True) rejected by driver: "
                  f"{ex.message} — skipping this code.")
            continue
        card.outputOn()
        pause(f"setOutputOffsetDacCode({code}, True). Record DC level on "
              f"the scope now (watch for ANY movement across the sweep, "
              f"even if the absolute voltage doesn't map to what you'd "
              f"expect).")
        card.outputOff()

    print("\nDiagnostic complete. Cleaning up.")
    card.outputOff()
    card.close()
    session.Close()
