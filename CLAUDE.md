# MUTT_flightCode

Code for autonomous operation of the MUTT experiment (a phased-array
function-generator payload) on suborbital flights.

## Repo layout

- `flightCode/` — code that runs on the flight-side hardware.
- `groundController.py` — ground-station control/monitoring GUI; talks to
  flight hardware and to the Pickering LXI cabinet directly for bench
  testing.
- `pickeringControls/` — interfacing with the Pickering LXI chassis
  (function generator cards + relay card) that drives the phased array.
  See `pickeringControls/pickeringREADME.md` for the v1→pi620lx migration
  notes and hardware/unit quirks that still apply to `groundController.py`'s
  current direct-`pi620lx` approach (see below).
- `pickeringControls/pilxi-5.7/` — vendor-supplied Python wrappers (pilxi
  for the LXI session, pi620lx — bundled inside it — for the 41-620
  function generator cards). Treat as third-party, don't modify.
- `archive/` — retired files moved out of the working tree (not deleted;
  original paths mirrored under `archive/pickeringControls/`): the orphaned
  v2 `pickeringInterfaceV2.py` + its README, `diag_arm_trigger.py` (drove
  v2), `ObjPickeringInterface.py`, `GT_PickeringTest.py`, `test01.py`,
  `REPL_ConnectionCode.py`, `claudeController.py`, and the old
  `python_pilpxi_v1.7/` vendor package. Nothing live imports from here.
- `relayControls/` — relay card handling separate from the Pickering path.
- `spacecraftSerial/` — serial comms to flight hardware.
- `testHarness/` — threading architecture that `groundController.py` was
  rewritten to match (per-pair array sliders via a `pxiQueue`).
- `waveConfigs/*.csv` — example phased-array waveform configs consumed by
  `phasedArray.readConfig()` / `loadWaveConfig()`.
- `Pickering Manuals/` — vendor docs, incl. the Direct IO driver package
  required on any machine that talks to the LXI cabinet.

## Pickering interface — three generations, two still live

Three implementations of "talk to the 41-620
function-gen cards + 40-115 relay card":

1. **v1 — `pickeringInterface.py`** (free functions: `initPXIE()`,
   `updateWaveform()`, etc). Always uses `CONT` trigger mode, so each
   channel starts generating immediately on Apply — no cross-channel phase
   sync. This is the **only** interface `flightCode/flightController.py`
   imports; flight-side code has not moved off v1.
2. **v2 — `archive/pickeringControls/pickeringInterfaceV2.py`**
   (**archived**; `pickeringHeader` class, a real stage → arm → trigger API:
   `sendConfigToCards()` → `armFuncGens()` → `triggerFuncGens()`).
   `groundController.py` no longer imports it and nothing else does, so it
   was moved out of the working tree. Its README
   (`archive/pickeringControls/pickeringInterfaceV2_README.md`) wrongly
   describes it as wired to `groundController.py` — ignore that.
3. **`pickeringControls/pickeringConnector.py`** — minimal reference script showing the
   pattern `groundController.py`'s `_applyPxiChannel()` actually follows:
   session → `pi620lx.Base` → `findCards()`/`openCard()` → per-channel
   `setActiveChannel → outputOff → setTriggerMode → setOutputOffsetVoltage
   → setAttenuation → generateSignal(generate=False) → outputOn`.

`groundController.py` talks to `pilxi`/`pi620lx` **directly** — no
`pickeringHeader` abstraction, no background auto-reconnect thread. Its
apply model has stage→arm collapsed into one step: `PairControls` Apply (or
the single-channel buttons in `ManualModeWindow`/`DemoModeWindow`) both
configure the channel *and* call `outputOn()` immediately, differing only
in trigger mode — `POSEDGE`/`FRONT` (armed, waits on the real external
trigger) for a normal Apply, vs. `CONT` (free-run, ignores the trigger
entirely — same behavior v1 always had) for the `freerun=True` path used by
Manual/Demo Mode's engage buttons. The 40-115 relay is fired independently
via a `fire_relay` queue command (`GroundControllerApp`'s own "Fire
Trigger" button, and the equivalent in `SweepModeWindow`/`DemoModeWindow`)
— that's the actual synchronized "trigger" step across already-armed
channels. `SweepModeWindow` and `DemoModeWindow`'s sweep panels use a
parallel path (`queuePxiApplySweep()`/`card.generateSweep()`) instead of
`generateSignal()` for a continuously-repeating frequency sweep, armed the
same `POSEDGE`/`FRONT` way.

Both v1 and the current direct approach wrap `pi620lx` (not raw
`pilxi.PIFGLX_*`) for the 41-620 function generator cards — Pickering
support confirmed this is the correct approach for this chassis. Key
hardware quirks (details in `pickeringControls/pickeringREADME.md`):
- No live read-back from the FG cards — pi620lx has no `PIFGLX_Get*`
  equivalent; all status is last-commanded/software-cached only.
- `amplitude` is dB of attenuation (`setAttenuation()`), not volts.
- Only SINE/TRIANGLE/SQUARE waveforms are supported.
- `offset` range is -5 to 5V at the driver level, but `groundController.py`'s
  own `PARAMS`/`DialControl` bounds currently clamp the GUI to 0-5V —
  hardware-capable range and what the sliders let you enter are not the
  same; check `PARAMS` in `groundController.py` before assuming either.
- `amp`/amplitude-in-volts is converted to attenuation dB via
  `_dbFromVolts()` against `_FULL_SCALE_VOLTS = 10.0` (the 41-620's actual
  10Vpp full scale, confirmed against the vendor manual — an earlier `20.0`
  constant silently halved every commanded amplitude; fixed in
  `groundController.py`, but check `pickeringControls/
  PI620LX_QUICK_REFERENCE.md`/`diag_offset_amplitude.py` before trusting
  their copies of this constant).

## groundController.py — demo/manual/sweep windows and the locking gotcha

`GroundControllerApp` opens three modal-ish `Toplevel` windows that
temporarily "own" the array — `ManualModeWindow`, `SweepModeWindow`,
`DemoModeWindow` (presentation shortcuts: 6 fixed-preset single-channel
buttons, a canned 8-12kHz audible sweep, and a smaller configurable sweep
panel). All three call `app._set_array_controls_locked(True)` on open to
grey out the main window's per-pair `PairControls` and restore them on
close.

**`PairControls._apply()` must never gate on `self._locked`.** Manual/Demo
Mode drive their own array access *through* the same locked `PairControls`
(`ctrl.apply_param()` + `ctrl.apply()`), so a lock check inside `_apply()`
would silently block the very windows that locking exists to hand control
to — the operator-facing block is already enforced by disabling the Apply
button/sliders/entries at the Tk level in `_refresh_lock_state()`, which is
sufficient on its own. Similarly, `_set_value()` has to temporarily flip a
locked (`state="disabled"`) `Entry` back to `"normal"` around programmatic
writes, since Tk raises `TclError` on `.insert()`/`.delete()` against a
disabled `Entry` otherwise. `SweepModeWindow` sidesteps both issues by
bypassing `PairControls` entirely (`queuePxiApplySweep()`/
`queuePxiStopPair()` directly) — that's the safer pattern for any new
window that needs to drive channels while the array is locked.

## Working with the LXI hardware

- Requires the Pickering Direct IO drivers installed locally (under
  `Pickering Manuals/`) — these do the C-wrapper-to-IO conversion the
  Python packages depend on.
- If cards are found by `FindFreeCards()`/`findCards()` but every open
  attempt fails ("found but not free"), a full chassis power cycle has
  been the working fix in past debug sessions — see git history around
  7.17.26 for the investigation (orphaned pilxi session and USB-related
  theories were ruled out first).
