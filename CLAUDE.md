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
  See `pickeringControls/pickeringInterfaceV2_README.md` for how the
  current (v2) implementation is structured, and
  `pickeringControls/pickeringREADME.md` for the v1→pi620lx migration
  notes and hardware/unit quirks that still apply to v2.
- `pickeringControls/pilxi-5.7/`, `py620_v0.1/`, `python_pilpxi_v1.7/` —
  vendor-supplied Python wrappers (pilxi for the LXI session, pi620lx for
  the 41-620 function generator cards). Treat as third-party, don't modify.
- `relayControls/` — relay card handling separate from the Pickering path.
- `spacecraftSerial/` — serial comms to flight hardware.
- `testHarness/` — threading architecture that `groundController.py` was
  rewritten to match (per-pair array sliders via a `pxiQueue`).
- `waveConfigs/*.csv` — example phased-array waveform configs consumed by
  `phasedArray.readConfig()` / `loadWaveConfig()`.
- `Pickering Manuals/` — vendor docs, incl. the Direct IO driver package
  required on any machine that talks to the LXI cabinet.

## Pickering interface — v1 vs v2

`pickeringInterface.py` (v1, free functions) and `pickeringInterfaceV2.py`
(v2, `pickeringHeader` class) both still exist in `pickeringControls/`, but
as of 7.27.26 `groundController.py` is wired to **v2** (`pxiHeader` global,
built from `pickeringHeader`). v1 is no longer imported anywhere
(`git grep -l pickeringHeader` / `pickeringInterfaceV2` to confirm current
wiring — don't assume this file is stale).

v2 changed the GUI's apply model from v1's "each pair's Apply immediately
starts that channel generating" to **stage → arm → trigger**: per-pair
Apply only stages config (`sendConfigToCards()`, which also de-energizes
output as a side effect); separate Arm/Trigger buttons
(`armFuncGens()`/`triggerFuncGens()`) start all 6 channels simultaneously
off the shared relay so their phases stay synchronized — v1 never actually
synchronized cross-channel phase, since each channel's `CONT` trigger mode
made it start running independently the moment Apply was clicked. See
`pickeringControls/pickeringInterfaceV2_README.md` for the full call
sequence.

Both wrap `pi620lx` (not raw `pilxi.PIFGLX_*`) for the 41-620 function
generator cards — Pickering support confirmed this is the correct approach
for this chassis. Key hardware quirks that apply to both versions (details
in `pickeringControls/pickeringREADME.md`):
- No live read-back from the FG cards — pi620lx has no `PIFGLX_Get*`
  equivalent; all status is last-commanded/software-cached only.
- `amplitude` is dB of attenuation (`setAttenuation()`), not volts.
- Only SINE/TRIANGLE/SQUARE waveforms are supported.
- `offset` range is -5 to 5V.

## Working with the LXI hardware

- Requires the Pickering Direct IO drivers installed locally (under
  `Pickering Manuals/`) — these do the C-wrapper-to-IO conversion the
  Python packages depend on.
- If cards are found by `FindFreeCards()`/`findCards()` but every open
  attempt fails ("found but not free"), a full chassis power cycle has
  been the working fix in past debug sessions — see git history around
  7.17.26 for the investigation (orphaned pilxi session and USB-related
  theories were ruled out first).
