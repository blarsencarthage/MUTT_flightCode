# PXI/Pickering Debugging Session — 2026-07-17

Notes from a debugging session on the "function generators aren't starting" issue,
covering root causes found and fixed, and what's still open. Read this before
re-investigating PXI connection issues — several of these look similar on the
surface but have different root causes.

## Summary for a fresh instance picking this up

**Hardware:** LXI PXI chassis holding two 41-620 function generator cards
(plus a leftover unrelated card, since removed), IP `169.254.112.5`,
controlled by `groundController.py`/`flightController.py` via
`pickeringControls/pickeringInterface.py`'s `initPXIE()`, which wraps the
vendored `pilxi-5.7` package. **Note:** `Pickering Manuals/
Pickering_CabinetManual.pdf` describes the **60-105** LXI/USB 4-Slot Modular
Chassis, but the physical unit in use has **no USB port** — that manual does
not match the actual hardware model. Model is otherwise unconfirmed; check
the chassis label/front LCD if it matters for future debugging.

**Original problem:** function generators weren't starting. This turned out to
be *several* independent bugs (session lifetime, an unguarded driver call, a
broken diagnostic — see numbered sections below), all fixed except the last
one.

**Current unresolved state:** every run connects to the chassis fine, sees the
correct total card count (2), but reports **0 free cards** — the two real
41-620s are permanently claimed by something else, so `OpenCard()` never
reaches them. Confirmed consistently across multiple log captures
(`ground_2026-07-17_12-53-55.log`, `_13-40-41.log`, `_13-56-13.log`), including
after fixing the `GetForeignSessions()` bug (section 5 below) — the driver
reports **no foreign LXI sessions**, yet the cards are still not free.

**USB-override theory: ruled out.** Physically checked — this chassis has no
USB port at all, so the 60-105 manual's "USB always overrides LXI" behavior
(section 6 below) does not apply here; that manual was describing the wrong
model.

**Leading theory now:** with both the orphaned-pilxi-session theory (section 5)
and the USB-override theory (section 6) ruled out, the two 41-620 cards being
claimed-but-not-free with **no visible owner via any client-facing
diagnostic** points to a claim stuck at the chassis/firmware level itself —
not tied to any live client session — likely left over from an earlier
ungraceful disconnect (power loss, crash, force-kill) that the chassis' own
card-ownership bookkeeping didn't clear. This would only be resolved by a
**full chassis power cycle** (rear power switch), not a client-side reset,
since there's no session to release. Not yet tried as of this writing — see
"Next steps" at the end of the file.

## 1. Session lifetime bug (fixed)

**Symptom:** `"Client: Invalid session ID"` on health checks, repeating every
~5s in a reinit loop that never stabilizes.

**Root cause:** `initPXIE()` created a local `pilxi.Pi_Session` object, opened
cards from it, but only ever returned the card list — never the session
itself. Cards only store the raw session *handle value*, not a Python
reference to the `Pi_Session` wrapper. So the moment `initPXIE()` returned,
the `Pi_Session`'s refcount hit zero and CPython garbage-collected it
immediately. `Pi_Session.__del__` calls `Close()` → `PICMLX_Disconnect()`,
which tore down the very session the just-opened cards depended on.

**Fix:**
- `initPXIE()` now returns `(session, waves)` instead of just `waves`.
- `groundController.py` and `flightController.py` (both use the same
  `initPXIE()`) store the session in a new global `pxiSession`, and
  `reinitPXI()` closes the old session before opening a new one.
- Updated `test_pickeringInterface.py` and `GT_PickeringTest.py` for the new
  return signature.
- `pickeringREADME.md` updated — this used to be documented as an open
  unknown ("unknown how this script works with keeping the connection open").

## 2. Live hardware status added to LXI Manager window

Added a **"Generator Status (live hardware read-back)"** table to
`LXIManagerWindow` that reads directly from the card via
`readChannelStatus()` (new function in `pickeringInterface.py`, uses
`PIFGLX_Get*` calls) — frequency, amplitude, waveform, and RUN/IDLE state, per
channel. This is distinct from the main window's per-pair display, which only
*echoes* the last commanded value from the software-side `waveAtributes`
cache and never re-reads the card. Cmd vs Live frequency mismatch is
highlighted red — use this to tell "we told the card to do X" apart from
"the card is actually doing X."

Also fixed the existing Card Status table's "Ch 1/Ch 2/Ch 3" columns, which
were hardcoded literal strings `"1", "2", "3"` — never real data.

## 3. Card-type mismatch (context, not a bug)

Early in the session, the two "free" cards found reported `CardId()` models
`40-414-104` and `40-115-021` — not `41-620` (the function generator family
every comment in this codebase assumes). Every `PIFGLX_*` call against them
failed with a generic `"Unknown error code."`, because they're not function
generator cards at all.

**Turned out to be expected**: those were extra cards physically installed in
ports 1/2, since removed. The real 41-620s are in ports 3/4, confirmed
working via Pickering's own Soft Front Panel.

`initPXIE()` still logs a loud warning (not a skip/filter — deliberately left
as warn-only) whenever an opened card's `CardId()` doesn't contain `"620"`,
via `FG_CARD_ID_HINT`. Useful signal, not necessarily an error, depending on
what's physically plugged in at the time.

## 4. FindFreeCards() crash right after connect (fixed defensively)

**Symptom:** `"Client: Argument is NULL or a value is outside the valid
range."` immediately after a successful `Pi_Session` connect.

**Fix:** `CountFreeCards()` and `FindFreeCards()` are now called separately
(previously `FindFreeCards()` alone, unguarded — the one call in `initPXIE()`
without a `try/except pilxi.Error`). This pins down *which* call is actually
failing, since both funnel driver errors through the same message decoder and
look identical otherwise:
- `CountFreeCards()` itself fails → session unusable, no point retrying →
  logged as `"CountFreeCards() failed: ..."`, hands back to caller's reinit
  backoff.
- `CountFreeCards()` succeeds with 0 → logged as `"Chassis reports 0 free
  cards right now"`, `FindFreeCards()` is skipped entirely (avoids whatever
  it does with a zero-count buffer).
- `CountFreeCards()` reports N>0 but `FindFreeCards()` still fails → retried
  once after 1s, then gives up with `"FindFreeCards() failed again: ..."`.

## 5. Currently open: cards recognized but not free — likely a stuck session

**Current symptom** (most recent log): chassis reports the correct total
card count, but the two real 41-620s are *not* in the free list — only the
leftover `40-115-021` is free. I.e. the chassis sees the function generators,
but something already holds an exclusive claim on them, so `OpenCard()` never
gets to them.

**Ruled out:** Pickering Soft Front Panel — confirmed closed before running
`groundController.py`.

**Leading suspect:** a leftover/orphaned session from a previous run of this
app that didn't exit cleanly (force-killed via Task Manager/IDE stop rather
than the window's close handler) — chassis-side session bookkeeping can
outlive the client TCP connection. Very plausible given how many times this
app has been restarted mid-debugging.

**Diagnostic added:** when cards are found-but-not-free, `initPXIE()` now
also calls `session.GetForeignSessions()` and logs the actual session ID(s)
holding cards elsewhere (pilxi tracks this at the driver level — no need to
guess). `ReleaseForeignSession(id)` exists in `pilxi` to force-release one,
but was deliberately **not** wired up as an automatic action — that's a
"kill someone else's connection" action and should be a deliberate choice,
not automatic.

**Update 2026-07-17 (later same day):** the `GetForeignSessions()` diagnostic itself
was broken. `pilxi-5.7/pilxi/__init__.py`'s wrapper allocates a fixed 100-slot
`ctypes` buffer, and the driver call writes the real count back into
`numSessions`, but the old code returned the raw 100-slot buffer unsliced.
Since ctypes zero-initializes the buffer, this meant `GetForeignSessions()`
returned a 100-element list of `0`s on *every* call, real foreign session or
not — a non-empty Python list, so `if foreign:` was always true. The log line
`"Other live session(s) on this LXI unit: [0, 0, 0, ...]"` was therefore a
false positive baked into the wrapper, not evidence of a foreign session (e.g.
a LabVIEW client holding the cards). It could not confirm or rule out that
theory.

**Fix applied:** `GetForeignSessions()` now returns
`sessions[:numSessions.value]` — truncated to the driver-reported count.

**Result after fix:** re-ran multiple times (`ground_2026-07-17_13-40-41.log`,
`_13-56-13.log`) — log now consistently shows `"No other foreign sessions
reported by the driver, yet cards are still not free"`. This *rules out* a
leftover/orphaned pilxi-LXI session (e.g. a previous force-killed run of this
same app, or another LXI client) as the cause, since that diagnostic is now
trustworthy and comes back empty every time.

## 6. USB-override theory — investigated and ruled out

`Pickering_CabinetManual.pdf` §4.1 ("Default Configuration") describes a
Pickering **60-105** chassis where a connected USB cable always takes
priority over Ethernet and disables LXI mode entirely — which would have
explained the found-but-not-free cards (a USB-connected client would be
invisible to `GetForeignSessions()`, an LXI-only mechanism).

**Ruled out:** physically checked the chassis — it has **no USB port**, so
this manual describes a different chassis model than the one actually in
use. The theory doesn't apply here. (Worth confirming the actual model off
the chassis label/front LCD if it becomes relevant again — the manual on
file in this repo does not match the physical hardware.)

## 7. Update 2026-07-17 (evening): pi620lx migration + escalation to session-level refusal

`pickeringInterface.py` was rewritten this same day to use `pi620lx` instead
of pilxi's `PIFGLX_*` calls, per a sample script (`pickeringControls/test01`)
Pickering support sent after confirming `PIFGLX_*` doesn't work with these
41-620 cards. See `pickeringREADME.md` for the full contract change. This
rewrite did **not** touch the LXI session-open call — `initPXIE()` still
opens the session via `pilxi.Pi_Session(ip_address, timeout=timeout)` exactly
as before, and pi620lx is only reached after that call succeeds.

**New symptom, same evening:** `groundController.py` failed to connect from
its very first attempt (`PXI init failed: Client: Connect failed.`) and then
failed on every reinit retry for 5+ minutes straight, including after the
operator manually changed the IP (to the same value) via LXI Manager. Ran
`test01.py` standalone in a separate terminal (without closing
`groundController.py` first) to check whether the chassis was refusing
`groundController.py` specifically — **`test01.py` also failed with the same
`pilxi.Error: Client: Connect failed.`**, despite it having connected
successfully earlier in the day.

**This rules out a code-level cause** (in either the old or new
`pickeringInterface.py` — the session-open call is unchanged) **and confirms
the chassis is refusing connections from every client**, not just this app.
This is a worse version of the section 5 symptom (there, the session opened
fine but cards were claimed; here, no session opens at all) and fits the same
leading theory: a claim/lock stuck at the chassis/firmware level, invisible
to and unclearable by any client-side session logic. Plausibly made worse by
`groundController.py`'s reinit loop retrying the connect every 5-60s for
several minutes straight against an already-wedged chassis.

**Next action: full chassis power cycle** (rear power switch, full off/on —
not just restarting the Python process/app), same as the unactioned
recommendation from section 5/6 below. Re-test with `test01.py` first (lower
blast radius, no reinit loop) before restarting `groundController.py`.

### Next steps (unresolved as of this writing)

Both the orphaned-session theory (section 5) and the USB-override theory
(section 6) are ruled out. Remaining plan, in order:

1. **Power cycle the chassis itself** (rear power switch, full off/on — not
   just restarting the Python app). This is the top-priority next action: a
   card-ownership claim stuck at the chassis/firmware level, not tied to any
   live session, would only clear this way.
2. If the chassis has a factory-reset-style button (confirm this against the
   actual chassis model's manual, not the 60-105 one on file — see section 6),
   try that as an alternative to a full power cycle.
3. Rerun `groundController.py` after the power cycle and confirm cards become
   free (`Chassis reports 2 total card(s)` and `2` free, not `0`).
4. If cards are still unavailable after a full power cycle, this points past
   a simple stuck-claim theory — escalate to checking for another physical
   controller/PC wired to this same chassis on a separate control path, or
   contact Pickering support with the exact chassis model/serial.
5. Secondary/cheap check: Task Manager for more than one
   `python.exe`/`pythonw.exe` — unlikely to be the cause given
   `GetForeignSessions()` now reports empty, but costs nothing to rule out.

## 8. Update 2026-07-27: recurrence after the v2/pickeringHeader rewrite, + a real revisionQuery() vendor bug

`groundController.py` was rewritten this week to use `pickeringInterfaceV2.py`'s
`pickeringHeader` class instead of `pickeringInterface.py`'s free functions
(see `pickeringControls/pickeringInterfaceV2_README.md`). Two issues showed
up in the first real session against hardware, logged in
`groundLog/ground_2026-07-27_11-10-58.log`:

**8a. `checkPXIHealth()` always reported "not responding" — false positive, not hardware.**
`Card.revisionQuery()` in `pilxi-5.7/pi620lx/__init__.py` (~line 316) returns
`self._pythonString(driverRev)` / `self._pythonString(instrumentRev)` —
missing `.value` on the `ctypes.create_string_buffer` objects, unlike every
other method in that file (compare `errorMessage()` immediately above it,
which correctly does `.value` first). `_pythonString()` calls `.decode()` on
whatever it's handed; a raw `ctypes.Array` has no `.decode()`, so this always
raises `'c_char_Array_100' object has no attribute 'decode'` — even when the
card responded correctly. `checkPXIHealth()` had been wired to call
`revisionQuery()` as a live ping, so it showed the health check failing
continuously regardless of actual card state, while the LXI Manager's
`connectionStatus`-based "CONNECTED" indicator stayed green — an apparent
contradiction that was really just "one status is fake."

**Decision:** left the vendor file (`pilxi-5.7/`) unpatched, per standing
policy of treating vendor-supplied wrappers as third-party/hands-off (see
root `CLAUDE.md`). Instead, `checkPXIHealth()` in `groundController.py` was
changed to stop calling `revisionQuery()` entirely — it now only reports
`pxiHeader.connectionStatus` + cards-found, i.e. no live round-trip ping at
all. This means a chassis that goes unresponsive without `pxiHeader`
noticing (see 8b) won't be caught by the periodic health check anymore
either — a real gap, not just a cosmetic one. If a live ping is wanted
later, `revisionQuery()` needs the vendor `.value` fix first, or a different
pi620lx call needs to be found/verified not to share the same bug.

**8b. Real send/arm failures after a ~22-minute `pxi_worker` thread hang — same "cards found but commands fail" pattern as sections 5-7.**
Timeline from the log:
```
11:12:11  last normal activity (health checks/apply working)
11:34:47  PXI heartbeat stale (1353.2s) — watchdog restarts the PXI thread
11:34:53  PXI health: card 0 not responding ()      <- empty message, a real driver error code this time
11:36:22  Failed to send config to card PXI4::15 channel 1: (empty message)
11:36:40  Failed to arm card PXI4::15 channel 1: (empty message)
```
`pxi_worker()` calls `updateHeartbeat()` every `WORKER_TIMEOUT` (0.2s) on
every loop iteration, so a 1353s stale heartbeat means something inside a
`pxiHeader` call (`sendConfigToCards()`/`armFuncGens()`/etc., down inside the
pilxi/pi620lx C driver) genuinely blocked for ~22 minutes — there is no
per-call timeout on individual card commands, only on the initial
`Pi_Session` connect. After it finally returned/gave up, subsequent card
writes started failing outright with real (but textless — the driver has no
description string for whatever code this is) error codes.

A fresh, completely independent diagnostic script run minutes later
(separate process, new `pilxi.Pi_Session` + `pi620lx.Base`, same IP)
connected and successfully called `setActiveChannel()` on both cards
immediately — so the chassis was not dead, and the two real 41-620s were not
permanently wedged this time (unlike sections 5-7's fully-stuck state). But
something about the *existing* long-lived session inside `groundController.py`
went bad mid-run and didn't recover on its own.

**This is the same "found/connected but writes fail" symptom family as
sections 5-7**, just triggered differently (a mid-session hang+failure rather
than never-free-at-connect-time). The section 5-7 leading theory (a stuck
claim/state at the chassis/firmware level that only clears on a full power
cycle) is the working assumption here too, though not confirmed this time —
the app was closed (not power-cycled) before the next successful connection
attempt (my standalone diagnostic script), so it's not proven that a power
cycle specifically was required to unstick it this time, only that closing
and reopening the *session* was sufficient. Worth testing next time: try
"Apply & Reinit" from the LXI Manager (new session, no power cycle) before
escalating to a physical power cycle, to narrow down which level (session vs
chassis firmware) actually needs the reset.

**Not fixed/still open:**
- No root cause for *why* a `pxiHeader` call hangs ~22 minutes then starts
  failing — only a recurrence pattern, matching sections 5-7.
- No per-call timeout exists on pilxi/pi620lx card commands, so a chassis
  going bad mid-session will hang the `PXI` worker thread (and block
  anything else waiting on `pxiLock`) for however long the driver takes to
  give up, with no way to abort it from Python short of killing the thread's
  process. `groundController.py`'s watchdog only detects this after the
  fact (heartbeat staleness) and restarts the worker thread, which does not
  reopen `pxiHeader`'s connection — reopening still requires the operator to
  hit "Apply & Reinit" manually.
- `revisionQuery()`'s missing `.value` bug is unfixed in `pilxi-5.7/`
  (deliberately, see decision above) — don't reintroduce a live health-check
  ping through it without fixing that first.

## Files touched this session

- `pickeringControls/pickeringInterface.py` — session lifetime fix,
  `readChannelStatus()`, `FG_CARD_ID_HINT` warning, `CountFreeCards`/
  `FindFreeCards` split + retry, `GetForeignSessions()` diagnostic.
- `pickeringControls/test_pickeringInterface.py` — updated for new
  `initPXIE()` return signature.
- `pickeringControls/GT_PickeringTest.py` — updated for new return signature.
- `pickeringControls/pickeringREADME.md` — documented session-lifetime
  contract.
- `groundController.py` — `pxiSession` global, `reinitPXI()` closes old
  session, split `CardId()`/`CardLoc()` error handling (previously a
  `CardLoc()` failure could clobber an already-successful `CardId()` read),
  live Generator Status table in `LXIManagerWindow`.
- `flightCode/flightController.py` — same session-lifetime fix as
  `groundController.py` (shared `initPXIE()`).

### Files touched 2026-07-27 (section 8)

- `groundController.py` — `checkPXIHealth()` no longer calls
  `card.revisionQuery()`; now reports `pxiHeader.connectionStatus`/cards-found
  only, no live ping.
- `pickeringControls/pilxi-5.7/pi620lx/__init__.py` — **not** touched;
  `revisionQuery()`'s missing-`.value` bug (section 8a) was deliberately left
  in place per vendor-code-hands-off policy.

## 9. Update 2026-07-27 (later same day): arm/trigger free-run regression + new frequency regression, wiring ruled out, no recoverable earlier-version history

**Reported symptom (start of session):** the stage → arm → trigger workflow
(`sendConfigToCards()` → `armFuncGens()` → `triggerFuncGens()`, see
`pickeringInterfaceV2_README.md`) used to work as intended — channels stayed
silent until the external 5V trigger arrived. At some point during ongoing
modifications this regressed: channels now start generating the instant
config is loaded, armed, or triggered, regardless of whether the external 5V
signal is actually present.

**Investigation, in order:**

1. **Compared call order against the vendor's own reference example**
   (`pickeringControls/py620_v0.1/Examples/Example_SimpleGenerate.py`), which
   calls `card.setTriggerMode(...)` *before* `card.generateSignal(...,
   generate=False)`. The current code (`sendConfigToCards()` /
   `armFuncGens()`) sets trigger mode *after* `generateSignal()`, in a
   separate, later method call. Hypothesized `PI620LX_GenerateSignalEx`
   latches trigger behavior at call time, so the late `setTriggerMode()` call
   would have no effect.
2. **Tried the reorder** — moved `setTriggerMode(FRONT, POSEDGE)` into
   `sendConfigToCards()`, before `generateSignal()`. **Result: made things
   worse.** Free-run behavior was **unchanged** (still starts regardless of
   trigger), and a **new regression appeared**: all channels' output
   frequency locked to ~2.5kHz on the scope regardless of the configured
   value (tried 10kHz, 25kHz, 40kHz, 100kHz — all read ~2.5kHz). **Reverted**
   back to the original order (trigger mode set in `armFuncGens()`, after
   `generateSignal()`) — this is the state the file is in now, matching what
   was committed in `59c1f1b` (the only commit that has ever touched
   `pickeringInterfaceV2.py`, checked across all branches/reflog/stash — see
   below).
3. **Checked ground logs** (`ground_2026-07-27_14-56-14.log` through
   `_15-19-37.log`) — the *software* staged→armed→triggered sequence logs
   exactly as expected every time; no evidence of a duplicate/spurious
   `armFuncGens()`/`outputOn()` call from the log alone. Also noted (not
   directly relevant to this bug, logged for completeness): `COM3`
   (`SERIAL_PORT`, spacecraft serial) and `COM5` (`RELAY_PORT`, separate
   relay controller — not the Pickering 40-115 relay card) never connected in
   any of these sessions, consistent with a PXI-only bench session with that
   hardware unplugged; and the LXI cabinet took ~2m18s to accept a connection
   in one session, consistent with the existing boot-time TODO at the top of
   `pickeringInterfaceV2.py`.
4. **Proposed a wiring-mixup hypothesis** (TRIGGER vs CLOCK SMB swapped on
   the 41-620 front panel — see `Pickering_FuncGenManual.pdf` §1/§2, though
   note that PDF is for the 41-620A, not necessarily the exact card model in
   this chassis) as a single explanation for both symptoms together (floating
   trigger input reading as a spurious edge; wrong/absent reference clock
   explaining a fixed low output frequency). **User confirmed on physical
   inspection: trigger lines and channel lines are wired correctly.** This
   theory is ruled out.
5. **Searched for the "earlier version that worked"** the user described —
   checked `git log --all -- pickeringControls/pickeringInterfaceV2.py`
   (single commit `59c1f1b`, everywhere), reflog, stash, and the other two
   branches (`advTechVersion`, `owenExp` — neither has a `pickeringInterfaceV2.py`
   at all, only the old `pickeringInterface.py` v1). **Conclusion: no
   recoverable earlier version of this file exists anywhere in this repo's
   history.** Whatever the working version looked like was never committed.
   The user believes it was a previous commit but wasn't sure which — worth
   revisiting if a specific commit/backup surfaces later, but nothing further
   to search for in this repo as of this writing.

**Current state:** `pickeringInterfaceV2.py` is back to its original
(`59c1f1b`) call order — known to at least produce correct frequency when
manually verified in isolation (matches the vendor example / v1 /
`claudeController.py`, all of which use this same
configure→triggerMode→generateSignal→outputOn shape, differing only in using
`CONT` instead of `POSEDGE`). The free-run-regardless-of-trigger bug is
**still unresolved** and, with wiring ruled out and no code diff available,
its root cause is unconfirmed — could be a genuine pi620lx/firmware quirk
around `POSEDGE` trigger mode on this card, or something specific to how
`groundController.py`'s threaded `pxi_worker`/queue drives the class
differently than a direct call (untested).

**Diagnostic added, not yet run:** `pickeringControls/diag_arm_trigger.py` —
standalone script that drives `pickeringHeader` directly (bypasses
groundController's threads/queue/heartbeat entirely) on a single channel,
with manual `input()` pauses at 4 checkpoints (configured/output-off →
trigger-mode-set/still-off → `outputOn()`-called/before-any-trigger-pulse →
after-trigger-pulse), so a scope can confirm at each step whether the
channel is running and at what frequency. Designed to separate two
possibilities: (a) `POSEDGE` genuinely doesn't gate `outputOn()` on this
hardware/driver (free-runs the moment `outputOn()` is called, step 3), vs.
(b) something specific to the full `groundController.py` app path causes an
extra/early trigger. **Next step: user will run this tomorrow** (2026-07-28)
and report the 4 checkpoint observations (running yes/no + frequency at
each).

### Files touched 2026-07-27 (section 9)

- `pickeringControls/pickeringInterfaceV2.py` — trigger-mode-ordering change
  tried and reverted; net no change from `59c1f1b`.
- `pickeringControls/pickeringInterfaceV2_README.md` — same, tried and
  reverted.

## 10. Update 2026-07-30: "missing DC offset" was a scope setting, not a bug; amplitude gap traced to a wrong full-scale constant

**Reported symptom:** running via the GUI/bench scripts with 5V amplitude +
4.5V offset at 10kHz, the scope showed a ~2.8V amplitude sine wave with no
DC offset at all.

**Offset — false alarm, resolved.** Wrote `pickeringControls/diag_offset_amplitude.py`
(raw `pilxi`/`pi620lx` calls, no `pickeringHeader`, same call order as
`pickeringConnector.py`: `setActiveChannel` → `outputOff` → `setTriggerMode`
→ `setOutputOffsetVoltage` → `setAttenuation` → `generateSignal(generate=False)`
→ `outputOn`, CONT trigger so no relay pulse needed) to isolate amplitude/
offset from the arm/trigger bug in section 9. Steps 1-3 (offset=0V; offset=
4.5V/connect=True; offset=4.5V/connect=False) all produced the *identical*
2.64Vpp/10kHz signal with no DC shift in any case — ruling out an
amplitude-headroom-clamp theory, since connect=False should have differed
from connect=True if the commanded offset value alone affected the output.
Root cause: **the oscilloscope channel was set to AC coupling**, which
blocks DC entirely regardless of what the function generator outputs.
Switching the channel to DC coupling fixed it immediately — the offset was
present on the signal the whole time. No code or driver bug here. (Step 4's
raw `setOutputOffsetDacCode()` sweep also showed the driver rejecting any
code above 0 — `16384`/`32768`/`49152`/`65535` all raised "Invalid value
passed to parameter 3" — so the valid raw-code range is much narrower than
the assumed 16-bit 0-65535; not investigated further since the volts-based
call is what's actually used in the app and coupling explained the symptom.)

**Amplitude gap — root cause found: wrong full-scale constant, not a
hardware fault.** `groundController.py:46` defines
`_FULL_SCALE_VOLTS = 20.0` with a comment claiming "Full-scale output is
20 Vpp." `Pickering_FuncGenManual.pdf` Section 1's spec table says
otherwise: `Waveform Signal: 10V pk to pk, open circuit load` — the card's
actual full-scale is **10Vpp**, not 20Vpp. `_dbFromVolts()` computes
attenuation as `20*log10(_FULL_SCALE_VOLTS / volts)`; using 20V instead of
the correct 10V computes double the attenuation dB needed for any target
voltage, so every commanded amplitude comes out near **half** of what was
requested. Checking the reported numbers: requesting 5V against the wrong
20V reference computes 12.04dB attenuation; applying that same dB against
the manual's correct 10V full scale gives 10 × 10^(-12.04/20) ≈ 2.5Vpp —
closely matching the measured 2.64Vpp (small residual gap plausibly
probe/loading related, worth re-checking once the constant is fixed). This
constant (and its "20Vpp" comment) is duplicated across
`groundController.py`, `pickeringControls/PI620LX_QUICK_REFERENCE.md`, and
`pickeringControls/diag_offset_amplitude.py` — all copied from the same
wrong assumption. **Not yet fixed in code** — flagged here pending a
decision on whether to correct `_FULL_SCALE_VOLTS` to 10.0 everywhere.

### Files touched 2026-07-30 (section 10)

- `pickeringControls/diag_offset_amplitude.py` — new standalone diagnostic
  script (raw pilxi/pi620lx, no pickeringHeader), used to isolate and rule
  out the offset/amplitude symptom from the trigger bug.
- `pickeringControls/diag_arm_trigger.py` — new standalone diagnostic script,
  not yet run against hardware.
