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
