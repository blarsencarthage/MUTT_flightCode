# MUTT_flightCode — Agent Context Doc

Status snapshot as of **2026-08-04** (HEAD `4f2dae9`, plus uncommitted
working-tree changes on top — see "Uncommitted changes" below). Written for
other AI agents picking up work in this repo — summarizes what exists,
what's functional, what's stale documentation, and what's still stubbed.
See `CLAUDE.md` for the maintained repo-layout/instructions file; this doc
is a deeper, point-in-time status report and should be re-verified
(grep/git log) before trusting specifics, since the code here has moved
fast and left several READMEs behind.

**⚠ Known doc drift as of this writing:** `pickeringControls/
pickeringInterfaceV2_README.md` still describes `groundController.py` as
wired to `pickeringInterfaceV2.pickeringHeader` (the "v2" stage→arm→trigger
design). As of commit `4f2dae9` (2026-07-31) that's no longer true — see
"Pickering interface generations" below. `CLAUDE.md` has been corrected to
match current wiring (2026-08-04); trust it over
`pickeringInterfaceV2_README.md`.

**Archive update (2026-10-11):** the orphaned/duplicate Pickering files were
moved (via `git mv`, not deleted) to `archive/pickeringControls/`, original
filenames kept: `pickeringInterfaceV2.py`, `pickeringInterfaceV2_README.md`,
`diag_arm_trigger.py`, `ObjPickeringInterface.py`, `GT_PickeringTest.py`,
`test01.py`, `REPL_ConnectionCode.py`, `claudeController.py`, and the
`python_pilpxi_v1.7/` vendor package. Where this doc below says one of these
lives in `pickeringControls/`, read that as `archive/pickeringControls/`.
Still live in `pickeringControls/`: `pickeringInterface.py` (v1, used by
flight), `pickeringConnector.py`, `diag_offset_amplitude.py`,
`test_pickeringInterface.py`, `pilxi-5.7/`, and the docs.

## Uncommitted changes (working tree, not yet in a commit)

On top of `4f2dae9`, the working tree currently also has:

- **`DemoModeWindow`** (new class in `groundController.py`, opened via a
  "Demo Mode…" button next to "Sweep Mode…") — a presentation-shortcut
  window: 6 buttons that freerun-engage a single pair at a fixed
  10kHz/5.5V/3V-offset preset (`DEMO_SINGLE_CHANNEL_PRESET`), an "Arm All
  Channels" button for a canned 8-12kHz/5.5V/3V-offset/2000Hz·s⁻¹ audible
  sweep (`DEMO_AUDIBLE_SWEEP_PRESET`), and a smaller configurable sweep
  panel (`DEMO_CUSTOM_SWEEP_PARAMS`) — all three sections share one Fire
  Trigger button. Follows the same lock-on-open/restore-on-close pattern as
  `ManualModeWindow`/`SweepModeWindow`.
- **A real bug fix in `PairControls`** (`_apply()` / `_set_value()`):
  `_apply()` used to also gate on `self._locked`, which silently no-opped
  every call Manual/Demo Mode made through `ctrl.apply()` while they'd just
  locked that same `PairControls` — i.e. Manual Mode's ENGAGE/dial commits
  were dead on arrival, and so were Demo Mode's single-channel buttons.
  `_set_value()` also had a latent `TclError` writing into a Tk-disabled
  `Entry` (same locked-controls scenario), hit via `apply_param()`. Both
  fixed — see `CLAUDE.md`'s "locking gotcha" section for the reasoning.
  Confirmed by code trace to now correctly reach `pxiQueue`; **not yet
  confirmed against real hardware** — worth a live smoke test.
- **GUI-freeze fix in `LXIManagerWindow._refresh()`**: this window's
  2-second self-`after()` poll used to take `pxiLock` directly on the Tk
  main thread. Since no pilxi/pi620lx driver call has a timeout (see known
  issues below), a hung call in `pxi_worker` — reproduced 2026-08-04 by
  arming `DemoModeWindow`'s audible sweep across both cards, which hung on
  the first channel of the second card — held that lock indefinitely, and
  the main-thread poll blocking on it froze the *entire* GUI (every window),
  which read as a full app crash. Fixed by moving the lock acquisition into
  a background thread (`_fetch_status()`), matching the pattern
  `_fetch_card_info()` already used. This does **not** fix the underlying
  driver hang — only stops it from taking the whole GUI down with it. Any
  other code that takes `pxiLock` from a `self.after()`/main-thread callback
  has the same latent risk; grep `pxiLock` before adding more.
- Exception logging across `pxi_worker`/`_openPXI`/`reinitPXI` changed from
  `f"...: {e}"` to `f"...: {e!r}"` — a real instance of `str(e)` being empty
  for a caught exception was observed in `groundLog/
  ground_2026-08-04_10-31-24.log` (`"PXI sweep apply pair 1: "` with nothing
  after the colon), which made the actual failure undiagnosable from the
  log alone.
- `py620_v0.1/` vendored package deletion (cleanup, still uncommitted).

None of this is reflected in the last commit message. If you're relying on
`git log`/`git show` to understand current behavior, check `git status`/
`git diff` first — the working tree is ahead of HEAD here.

## Repo layout (what's where)

- `groundController.py` (root, ~3100 lines) — ground-station Tk GUI, the
  most actively developed file in the repo. Talks directly to the Pickering
  LXI chassis via `pilxi`/`pi620lx` for bench testing.
- `flightCode/flightController.py` (~670 lines) — flight-side autonomous
  controller framework. Threading architecture is solid; several hardware
  call sites are still stubbed (see below). Still imports **v1**
  `pickeringInterface.py`, not the newer approach `groundController.py`
  now uses — flight and ground code are currently on different Pickering
  interfaces.
- `pickeringControls/` — Pickering LXI chassis interfacing. Contains three
  generations of the same idea (see below) plus vendor driver packages
  (`pilxi-5.7/` — third-party, don't modify; `python_pilpxi_v1.7/` is archived) and
  debug docs.
- `relayControls/relaySerial.py` — Numato USB relay board driver
  (`RelayController` class). This is a *different* relay from the
  Pickering 40-115 relay card inside the LXI chassis; functional, no known
  issues.
- `spacecraftSerial/craftSerial.py` — RS-422 listener parsing an 84-byte
  telemetry frame from the launch vehicle into named signal bits
  (`serialCraftInterface.getSignalBits()`). Functional. `RS422.py`/
  `RS422_V1.py` in the same dir look like earlier alternates — confirm via
  grep before assuming either is live; `craftSerial.py` is what
  `flightController.py` actually imports.
- `testHarness/` — fully virtual (no real hardware) tkinter rig that
  patches `pilxi`/`pi620lx`/`serial` with in-memory shims and runs
  `flightCode.flightController.main()` in a background thread. This is the
  thread/queue/`stateBus`/watchdog *pattern* that `groundController.py`
  was rewritten to match — not a literal UI clone (it has a channel table,
  not the per-pair sliders `groundController.py` has).
- `waveConfigs/*.csv` — six per-day flight playlists (`7.1`...`7.6`), each
  a sequence of 6-channel phased-array stage configs consumed by
  `flightController.pxi_ThreadManager()`.
- `groundConfigs/*.csv` — a **separate** CSV format (no
  `activeTime`/`settlingTime`, has `ring`/`disabled`) used only by
  `groundController.py`'s own bench-testing save/load. Don't conflate with
  `waveConfigs/`.
- `PhasedArray/arrayConfigs.csv` — currently empty, not read by any current
  code path. Unused placeholder.
- `Pickering Manuals/` — vendor PDFs + the Direct IO driver installer
  required locally to talk to the LXI chassis at all. Note:
  `Pickering_CabinetManual.pdf` documents the wrong chassis model (60-105,
  has USB) vs. the physical unit in use (no USB port) — treat that one
  PDF's claims with suspicion.
- `Outlines/` — early design-doc markdown, predates most of the current
  implementation; historical only.
- `groundLog/`, `flight*.log` — bench-session runtime logs (one is 23MB);
  referenced heavily in `pickeringControls/PXI_DEBUG_NOTES.md`'s debug
  history.

## Pickering interface generations — which one is actually live

Three implementations of "talk to the 41-620 function-gen cards + 40-115
relay card" now coexist in `pickeringControls/`:

1. **v1 — `pickeringInterface.py`** (free functions: `initPXIE()`,
   `updateWaveform()`, `abortGeneration()`, `readConfigs()`/
   `readAllConfigs()`, `waveAtributes` class). Always uses `CONT` trigger
   mode, so channels start generating immediately on Apply — no
   cross-channel phase sync. **Still the only interface `flightController.py`
   imports.**
2. **v2 — `archive/pickeringControls/pickeringInterfaceV2.py`** (archived; `pickeringHeader` class with a
   background auto-reconnect thread and a real stage→arm→trigger API:
   `loadWaveConfig()` → `sendConfigToCards()` → `armFuncGens()` →
   `triggerFuncGens()` → `disarmFuncGens()`). Per `PXI_DEBUG_NOTES.md`,
   this file has only ever been touched by **one commit** (`59c1f1b`,
   2026-07-27) and was abandoned after an unresolved "channels free-run
   regardless of trigger" bug. **As of HEAD, `groundController.py` no
   longer imports this file at all** — `pickeringHeader`/
   `pickeringInterfaceV2` appear in `groundController.py` only inside
   comments. Effectively orphaned, despite `pickeringInterfaceV2_README.md`
   still describing it as current (`CLAUDE.md` was corrected 2026-08-04).
3. **`pickeringConnector.py`** (new in `4f2dae9`, ~46 lines, no class) —
   minimal reference script: session → `pi620lx.Base` → `findCards()`/
   `openCard()` → per-channel `setActiveChannel → outputOff →
   setTriggerMode(FRONT, POSEDGE) → setOutputOffsetVoltage →
   setAttenuation → generateSignal(generate=False) → outputOn`. **This is
   the pattern `groundController.py`'s current `_openPXI()`/
   `_applyPxiChannel()` actually follow.**

There was also a standalone `claudeController.py` (166 lines, added
`59c1f1b`); confirmed unused and now archived.

**Working-tree note:** an older vendored package,
`pickeringControls/py620_v0.1/`, is deleted in the uncommitted working
tree (cleanup in progress, not yet committed).

## groundController.py — current architecture (post `4f2dae9`)

- Raw `tkinter`/`ttk`, dark Catppuccin-style theme, matching
  `testHarness/testHarness.py`'s palette.
- Threading: `pxiQueue`, `relayQueue`, `logQueue` (`queue.Queue`) +
  worker threads (`pxi_worker`, `relay_worker`, `serial_worker`,
  `telemetry_worker`, `watchdog_worker`) + `THREAD_FACTORIES`/
  `startThread()`/`restartThread()` + heartbeat/watchdog restart pattern —
  all directly mirroring `flightController.py`'s design (per the file's
  own header comment).
- `_Observable` `stateBus` pub/sub: worker threads publish hardware
  events, GUI classes subscribe and marshal updates onto the Tk main
  thread via `self.after(0, ...)`.
- **No `pickeringInterfaceV2` abstraction.** Owns PXI globals directly
  (`pxiSession`, `pxiCards`, `pxiRelayCard`, `pxiConnected`,
  `pxiChannelState`, `pxiLock`). `_openPXI()` is a one-shot,
  operator-triggered connect (via the LXI Manager's Reinit button) — no
  background auto-reconnect thread like v2 had.
- `checkPXIHealth()` is **not** a live hardware ping — `pi620lx.Card.
  revisionQuery()` was found buggy in the vendor driver (ctypes buffer
  missing `.value`) and removed from the health check; health now only
  reflects state from the last successful connect.
- **Stage→arm→trigger is effectively collapsed to stage→trigger.** There
  is no separate `armFuncGens()` call in the live code path.
  `_applyPxiChannel()` configures a channel **and calls `outputOn()`
  immediately** — Apply sets `POSEDGE`/`FRONT` trigger mode by default, so
  after Apply the channel is armed and waits on the real external trigger
  (or free-runs, depending on wiring). A separate `apply_freerun` command
  path (used by `ManualModeWindow`) sets `CONT` trigger mode instead, so
  `outputOn()` starts generation immediately — same behavior v1 always
  had. The shared 40-115 relay is fired independently via a `fire_relay`
  command that pulses `OpBit()` for 1.0s — this is the actual synchronized
  "trigger" step across already-armed channels.
- `SweepModeWindow` (new in `4f2dae9`) uses a parallel apply path
  (`queuePxiApplySweep()`/`_applyPxiSweepChannel()`) calling
  `card.generateSweep()` instead of `generateSignal()`. `DemoModeWindow`
  (uncommitted, see above) reuses this same sweep path for its two sweep
  sections, plus `PairControls.apply()`/`apply_param()` for its
  single-channel preset buttons.
- Key GUI classes: `ArrayDiagram`, `ScrollFrame`, `PairControls`,
  `LXIManagerWindow`, `RelayManagerWindow`, `DialControl`,
  `ManualModeWindow`, `SweepModeWindow`, `DemoModeWindow` (uncommitted),
  `GroundControllerApp`.
- **Locking gotcha:** `ManualModeWindow`/`SweepModeWindow`/`DemoModeWindow`
  all lock the main window's `PairControls` on open
  (`app._set_array_controls_locked(True)`) and drive the array while
  locked. `PairControls._apply()` does **not** check `self._locked` (fixed
  2026-08-04 — it used to, which broke Manual/Demo Mode's engage paths; see
  "Uncommitted changes" above) — only the Tk-level widget-disable in
  `_refresh_lock_state()` blocks the operator. Any new window following
  this pattern should either go through `ctrl.apply()`/`apply_param()`
  (now safe) or bypass `PairControls` entirely like `SweepModeWindow` does.

## flightCode/flightController.py — state of the flight-side framework

Functional threading/watchdog/logging scaffold, but **not flight-ready**:

- `pxi_ThreadManager()` — real implementation: steps sequentially through
  the 6 `waveConfigs/*.csv` playlists, applying all 6 channels per stage
  for `activeTime` seconds, aborting, waiting `settlingTime`, advancing.
- `craftSerial_ThreadManager()` — real implementation, reads
  `craftListener.getSignalBits()` into `signalStates`/`flightPhase`.
- `relay_ThreadManager()` — **partial stub**: applies `relayStates`
  unconditionally on any queue item; no phase-driven staged power-on/off
  logic yet (`#TODO`).
- `triggerSafeMode()` — **mostly stubbed**: all three safety actions
  (relay-off-all, PXI-zero-all, spacecraft fault signal) are commented-out
  `#TODO` lines; only a log message actually executes. This is a real
  safety gap, not just a doc gap, if this code is meant to fly.
- `initHardware()` — functional wiring of `PI.initPXIE()`,
  `serialCraftInterface()`, `RelayController()`; the post-init
  `PI.waveformSelfCheck()` call is not wired up.
- Uses v1 `pickeringInterface.py`, diverged from `groundController.py`'s
  current direct-pi620lx approach — worth reconciling before flight code
  and ground code need to share behavior.

## Known open issues / things to double check before relying on them

- **Unresolved as of last note:** channels free-running regardless of
  external trigger — root cause unconfirmed in `PXI_DEBUG_NOTES.md`; a
  diagnostic script (`archive/pickeringControls/diag_arm_trigger.py`) was written
  but no follow-up result is recorded. Check current state before
  assuming this is fixed.
- `_FULL_SCALE_VOLTS` was a wrong `20.0` (should be `10.0`, since the
  cards are 10Vpp full scale) — `groundController.py` has the corrected
  `10.0` per current source, but `pickeringControls/PI620LX_QUICK_REFERENCE.md`
  and `pickeringControls/diag_offset_amplitude.py` may still have the
  stale `20.0` — verify before trusting either doc/script.
- `pilxi-5.7/pi620lx/__init__.py`'s `revisionQuery()` has a confirmed
  vendor bug (missing `.value` on a ctypes buffer). Left unpatched
  per repo policy (vendor code is hands-off); blocks re-adding a live PXI
  health-check ping until fixed or worked around.
- No per-call timeout exists on any pilxi/pi620lx driver call — a hung
  chassis can block a worker thread indefinitely (a ~22-minute hang is
  documented in `PXI_DEBUG_NOTES.md`); heartbeat-staleness-triggered
  thread *restart* is the only backstop, and it doesn't reopen the
  underlying PXI connection. **Reproduced again 2026-08-04**: arming
  `DemoModeWindow`'s audible sweep across all 6 channels hung on `pair_idx
  3` (the first channel of the *second* physical card, `CHANNEL_MAP`'s
  `card_idx=1`) with no exception ever raised — pairs on card 0 always
  succeeded first. Whether this is specific to card 1, to sweep mode, to
  arming 2 cards back-to-back, or just bad luck is unconfirmed; worth
  targeted testing (e.g. arm only card-1 pairs via `SweepModeWindow` in
  isolation) next hardware session. The GUI-wide freeze this caused has
  been mitigated (see "Uncommitted changes") but the underlying hang has
  not.
- If cards are found by `FindFreeCards()`/`findCards()` but every open
  attempt fails ("found but not free"), a full chassis power cycle has
  been the working fix in past debug sessions (orphaned pilxi session and
  USB-related theories were ruled out first — see git history/
  `PXI_DEBUG_NOTES.md` around 2026-07-17).
- `groundController.py`'s `PARAMS`/`MANUAL_PARAMS`/`SWEEP_PARAMS`/
  `DEMO_CUSTOM_SWEEP_PARAMS` all hard-clamp the offset control to 0-5V, even
  though the driver (`card.setOutputOffsetVoltage()`) and
  `pickeringREADME.md` both document -5 to 5V as hardware-valid. Unclear if
  this is intentional (e.g. avoiding negative offset for some array-geometry
  reason) or just nobody's widened the slider bounds yet — check with the
  user before assuming either.
- `spacecraftSerial/craftSerial_README.md`'s packet-layout table describes
  several bits as placeholder-named pending ICD confirmation, but the
  actual `SIGNAL_NAMES` tuple in code already has real names filled in —
  the README is stale there.

## Docs that are stale and should be read skeptically

- `archive/pickeringControls/pickeringInterfaceV2_README.md` (archived) — describes
  `groundController.py` as wired to v2 `pickeringHeader`; no longer true as
  of `4f2dae9`. (`CLAUDE.md` was corrected 2026-08-04 and is now accurate
  on this point — no longer stale.)
- `flightCode/FlightCodeV1_README.md` — describes `checkPXIHealth()` as
  pinging via `CardId()`; actual code uses `revisionQuery()`.
- `placeholder_FlightcodeSession.md` (root) — session notes from
  2026-06-23/24, predates most of the current architecture; historical
  only.

## Suggested first steps for an agent picking up work here

1. Before trusting any statement above about "current" wiring, grep for
   the relevant import/symbol — this repo has moved fast (see git log:
   3 significant architecture shifts in the Pickering layer within the
   last week) and doc drift is the norm, not the exception.
2. If touching `flightController.py`'s Pickering calls, decide whether to
   reconcile it with `groundController.py`'s current direct-pi620lx
   approach or `pickeringConnector.py`'s pattern, since v1 and the
   ground-side code have diverged.
3. `triggerSafeMode()` in `flightController.py` is the highest-priority
   gap if this code needs to be flight-safe — it currently does nothing
   but log.
