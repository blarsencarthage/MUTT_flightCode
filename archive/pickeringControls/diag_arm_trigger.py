"""Standalone, manually-stepped diagnostic for the arm/trigger free-run + wrong-frequency bug.

Drives pickeringInterfaceV2.pickeringHeader directly (the same class/call
path groundController.py uses) but one step at a time, with input() pauses,
so a scope can be checked at each stage in isolation from groundController's
threads/queue/heartbeat/GUI. Only exercises channel 1 of the first card to
keep the scope trace simple — this is not meant to drive the full array.

Usage: run interactively (`python diag_arm_trigger.py`), press Enter at each
pause, and record on the scope: frequency + whether the channel is running
yet, at each of the 4 checkpoints below.
"""
import math
import os
import sys

_pkg_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _pkg_dir)
from pickeringInterfaceV2 import pickeringHeader

PXI_IP = "169.254.112.5"
TEST_FREQUENCY_HZ = 20000.0   # distinct, easy to recognize on a scope
TEST_AMPLITUDE_V = 10.0
TEST_OFFSET_V = 1.0
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


if __name__ == "__main__":
    print(f"Connecting to LXI at {PXI_IP} ...")
    header = pickeringHeader(PXI_IP, timeout_ms=5000)

    pause("Waiting for background connect. Check console for "
          "'PXI interface initialized successfully' before continuing.")

    if not header.connectionStatus:
        print("Not connected yet — wait longer, or check LXI_IP/cabling.")
        sys.exit(1)

    print(f"Found {len(header.cards)} card(s), relay card "
          f"{'found' if header.relayCard is not None else 'NOT FOUND'}.")
    for i, c in enumerate(header.cards):
        print(f"  header.cards[{i}] -> bus={c._bus}, device={c._device}")

    card = header.cards[0]

    # ---- Step 0: channel-index sweep ----
    # Tests whether setActiveChannel()'s argument is 1-based (matching the
    # vendor example's channel=1 for "first channel") or actually 0-based at
    # the DLL level, which would mean channel=1 silently configures the
    # SECOND physical channel while CH1 (probed) sits untouched — a single
    # off-by-one bug that would explain the frequency/amplitude/generate-flag
    # symptoms all at once, without needing three separate driver bugs.
    print("\n--- STEP 0: channel-index sweep — watch CH1 on the scope only ---")
    for candidate in (0, 1, 2):
        card.setActiveChannel(candidate)
        card.outputOff()
        card.setOutputOffsetVoltage(TEST_OFFSET_V, True)
        card.setAttenuation(_dbFromVolts(TEST_AMPLITUDE_V))
        card.generateSignal(
            TEST_FREQUENCY_HZ / 1000.0,
            card.signalShapes["SINE"],
            50.0,
            startPhaseOffset=TEST_PHASE_DEG,
            generate=False,
        )
        card.outputOn()
        pause(f"setActiveChannel({candidate}) -> outputOn(). Check CH1 on the "
              f"scope NOW: is anything running? Record candidate={candidate} "
              f"and what you see (nothing / {TEST_FREQUENCY_HZ}Hz / ~2.5kHz / other), "
              f"then continue — this candidate's output will be turned back off "
              f"before testing the next one.")
        card.outputOff()

    channel = 1
    print(f"\nMain diagnostic below uses channel={channel} — if step 0 showed "
          f"CH1 actually responds to a different candidate index, edit `channel` "
          f"above before trusting steps 1-4.")

    # ---- Step 1: configure only, output should be OFF ----
    card.setActiveChannel(channel)
    card.outputOff()
    card.setOutputOffsetVoltage(TEST_OFFSET_V, True)
    card.setAttenuation(_dbFromVolts(TEST_AMPLITUDE_V))
    card.generateSignal(
        TEST_FREQUENCY_HZ / 1000.0,
        card.signalShapes["SINE"],
        
        50.0,
        startPhaseOffset=TEST_PHASE_DEG,
        generate=False,
    )
    pause(f"STEP 1 done: card0/ch{channel} configured for "
          f"{TEST_FREQUENCY_HZ}Hz, output should be OFF (no signal on scope). "
          f"Check scope now — confirm nothing is running.")

    # ---- Step 2: set trigger mode, still before outputOn() ----
    card.setTriggerMode(card.triggerSources["FRONT"], card.triggerModes["POSEDGE"])
    pause("STEP 2 done: trigger mode set to FRONT/POSEDGE. Output still OFF — "
          "check scope again, confirm still nothing running.")

    # ---- Step 3: outputOn() — this is the step under test ----
    card.outputOn()
    pause(f"STEP 3 done: outputOn() called. DO NOT pulse the trigger relay yet.\n"
          f"    Check scope RIGHT NOW:\n"
          f"      - Is the channel running already (before any trigger pulse)?\n"
          f"      - If running, what frequency does it show — "
          f"{TEST_FREQUENCY_HZ}Hz, or something else (e.g. ~2.5kHz)?\n"
          f"    Record the answer, then continue to pulse the trigger.")

    # ---- Step 4: pulse the trigger relay ----
    if header.relayCard is not None:
        from pickeringInterfaceV2 import _RELAY_SUBUNIT, _RELAY_BIT, _RELAY_PULSE_WIDTH_S
        import time
        header.relayCard.OpBit(_RELAY_SUBUNIT, _RELAY_BIT, True)
        print("Relay CLOSED (trigger pulse asserted)")
        time.sleep(_RELAY_PULSE_WIDTH_S)
        header.relayCard.OpBit(_RELAY_SUBUNIT, _RELAY_BIT, False)
        print("Relay OPEN (trigger pulse released)")
    else:
        print("No relay card found — cannot pulse trigger. Skipping step 4.")

    pause(f"STEP 4 done: trigger relay pulsed. Check scope now:\n"
          f"      - Running now? What frequency — {TEST_FREQUENCY_HZ}Hz or ~2.5kHz?")

    print("\nDiagnostic complete. Disarming/cleaning up.")
    card.outputOff()
    header.closeLXI()
