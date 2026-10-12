Author(s): Braedon Larsen
Created: 7.27.26

# pickeringInterfaceV2.py

`pickeringInterfaceV2.py` is a rewrite of `pickeringInterface.py` as a single
stateful class, `pickeringHeader`, instead of a set of free functions. The
goal is that a caller (e.g. `groundController.py`) creates one
`pickeringHeader` per LXI cabinet and only ever calls its public methods —
all pilxi/pi620lx objects, card discovery, and reconnect logic stay inside
the class.

## Object lifecycle

```python
header = pickeringHeader(ipAddress="192.168.0.5", timeout_ms=5000)
```

Creating a `pickeringHeader` immediately starts one background daemon
thread (`_lxiThread` → `_monitorLXI`). That thread, and *only* that thread,
owns the connection lifecycle:

- Every `healthInterval` seconds (default 5s), if not currently connected,
  it calls `_openLXI()`.
- `_openLXI()` opens a `pilxi.Pi_Session` to the cabinet, then:
  - finds the 41-620 function generator cards via `pi620lx.Base.findCards()`
    and opens each one with `pi620Base.openCard(bus, device)`, storing the
    resulting card objects in `self.cards` (a list — however many are
    found, though the rest of the class assumes 2 cards × 3 channels = 6
    total channels, see `phasedArray.NUM_CHANNELS`);
  - separately scans `session.FindFreeCards()`, opens each candidate, and
    checks `CardId()` for the substring `"40-115"` to identify the single
    relay card, stored as `self.relayCard`.
  - Each FG card object gets `_bus`/`_device` attributes stamped onto it
    (pi620lx.Card has no `CardId()`/`CardLoc()`), used only by `_cardLabel()`
    for logging — nothing downstream re-locates cards by bus/device, they
    always operate on the stored card objects.
- If the connection drops later (`connectionStatus` goes false), the same
  loop transparently reconnects and re-discovers cards on the next tick.

There is exactly **one** background thread total — not one per card. All
card/relay operations triggered by the public methods below run
synchronously on the caller's thread, not on `_lxiThread`.

Call `header.closeLXI()` to stop the monitor thread and close the session
when done.

## Configuration model — `phasedArray`

`pickeringHeader.phasedArray` is a nested class, one instance of which
(`self.phasedArray`) is created per `pickeringHeader` and holds the entire
6-channel configuration in `self.channels` (a list of `phasedArray.channel`
objects — one per CSV row / physical channel).

`phasedArray.readConfig(csvPath)` reads a `waveConfigs.csv`-style file
(see `waveConfigs/*.csv` in the repo root) with columns `channel, frequency,
amplitude, offset, phase, waveform_type, activeTime, settlingTime` (plus
optional `symmetry`, default 50). Rows are assigned to `self.channels` by
**file order**, not by the CSV's own `channel` column (which repeats 1-3 per
card and doesn't uniquely identify one of the 6 stored channels).

External code never touches `header.phasedArray` directly — it goes through
`header.loadWaveConfig(csvPath)`, which forwards to `readConfig()`.

## Public method call sequence

The intended workflow, in order:

1. **`header.loadWaveConfig(csvPath)`** — parse a CSV into
   `header.phasedArray`.
2. **`header.sendConfigToCards()`** — for each `(card, cardChannel, config)`
   triple (see `_cardChannelConfigs()` below), select the channel and push
   waveform parameters (offset, attenuation/amplitude, frequency, waveform
   shape, phase) via `card.generateSignal(..., generate=False)`. This
   **only stages the config** — it does not arm the trigger or start
   generation.
3. **`header.armFuncGens()`** — opens (de-energizes) the trigger relay first
   as a safety reset, then for each channel sets the trigger mode to
   `FRONT`/`POSEDGE` and calls `card.outputOn()`. After this call the cards
   are waiting for an external trigger pulse.
4. **`header.triggerFuncGens()`** — closes the relay (energizes) for
   `_RELAY_PULSE_WIDTH_S` (50ms) then reopens it, delivering one trigger
   pulse to all armed channels simultaneously so they start generating in
   phase.
5. **`header.disarmFuncGens()`** — turns each channel's output off and
   de-energizes the relay; use to stop/reset between runs.

`sendConfigToCards()` / `armFuncGens()` / `disarmFuncGens()` are three
distinct steps by design (see docstrings) — don't assume calling one
implies the others.

### `_cardChannelConfigs()` — the card/channel/config pairing

Internal helper that zips `self.cards` (in discovery order) against
`self.phasedArray.channels` (in CSV row order), producing tuples of
`(card, cardChannel 1-3, config)` in the fixed order card0-ch1..3,
card1-ch1..3. `sendConfigToCards`, `armFuncGens`, and `disarmFuncGens` all
iterate this same pairing, so the CSV row order is what determines which
physical channel each row drives.

## Relay card — trigger vs. manual/diagnostic control

The relay card (40-115-021) has two separate call surfaces:

- **Normal FG workflow**: `armFuncGens()` / `triggerFuncGens()` /
  `disarmFuncGens()` — these are the only calls that should be used during
  normal operation.
- **Manual/REPL diagnostics**: `setRelay()`, `pulseRelay()`, `readRelay()`
  — direct single-bit relay control/readback for bench-testing the relay
  card and trigger wiring in isolation from the FG cards. Not part of the
  normal trigger flow; useful when debugging hardware wiring issues.

All relay calls use `_RELAY_SUBUNIT = 1`, `_RELAY_BIT = 1` as defaults —
the one relay wired to the FG trigger lines on this cabinet.

## Key differences from `pickeringInterface.py` (v1)

See `pickeringREADME.md` for the full v1 pilxi→pi620lx migration notes
(units, waveform type support, etc. — all still apply since v2 wraps the
same pi620lx calls). The v1→v2 change is purely structural:

| | v1 (`pickeringInterface.py`) | v2 (`pickeringInterfaceV2.py`) |
|---|---|---|
| Shape | free functions (`initPXIE()`, `updateWaveform()`, ...) | one class, `pickeringHeader` |
| Connection | caller calls `initPXIE()` once, must hold the returned `session` alive | class owns the session; background thread opens/monitors/reconnects automatically |
| Card storage | returned tuple of `(session, waveforms)` | `self.cards`, `self.relayCard`, `self.phasedArray` held internally |
| Config load | CSV parsing left to caller / `readConfigs()` | `header.loadWaveConfig(csvPath)` |
| Trigger | not present in v1 | `armFuncGens()` / `triggerFuncGens()` / `disarmFuncGens()`, driven by the identified 40-115 relay card |

## Usage in `groundController.py`

As of 7.27.26, `groundController.py` is wired to `pickeringHeader` (it was
previously on v1's `pickeringInterface`). It creates one `pxiHeader`
global, keeps the GUI's per-pair sliders/entries in volts and converts
to/from the dB `phasedArray.channel.amplitude` field itself
(`_dbFromVolts()`/`_voltsFromDb()` in `groundController.py` — this
conversion is a GUI concern and intentionally isn't part of this module).

It follows the **stage-then-arm-then-trigger** model directly: each pair's
"Apply" button only writes into `pxiHeader.phasedArray.channels[i]` and
calls `sendConfigToCards()` (no output change — this also means every
Apply de-energizes any currently-running output, since
`sendConfigToCards()` calls `outputOff()` per channel). Separate "Arm" and
"Trigger" buttons call `armFuncGens()`/`triggerFuncGens()` for all 6
channels at once so they start in phase; "Stop All" calls
`disarmFuncGens()`. See `pxi_worker()` in `groundController.py` for the
exact command handling.

## Known gaps / TODO

- No automated tests yet (compare to `test_pickeringInterface.py` for v1).
- No live read-back from hardware (inherited pi620lx limitation, see
  `pickeringREADME.md`).
- `self.cards` isn't hard-capped at 2 — if a chassis ever has more/fewer
  41-620s than `phasedArray.NUM_CHANNELS` (6) accounts for,
  `_cardChannelConfigs()` silently truncates extra cards/channels rather
  than erroring.
- `#TODO` at the top of the file: debounce reconnect attempts against
  estimated LXI boot time after a power cycle.
