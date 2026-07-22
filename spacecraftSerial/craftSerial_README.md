# serialCraftInterface — RS422Listener_V2.py

## Overview

Reads a serial RS-422 stream from the spacecraft, parses incoming packets, and returns the signal bits as a named dictionary of booleans. All threading and parsing happen under the hood; the caller only interacts with a single public method.

## Data Flow

```
Serial port  →  _reader  →  _segments queue  →  _processor  →  _scan  →  _results queue  →  getSignalBits()
```

## Usage

```python
craft = serialCraftInterface()
signals = craft.getSignalBits()   # blocks until a packet is parsed
print(signals["apogee"])          # True or False
```

Creating the object automatically starts both worker threads. No separate start or listen call is needed.

## Function Reference

### `__init__`
Sets up two internal queues (`_segments` and `_results`) and starts both worker threads as daemons. Daemon threads die automatically when the main program exits.

### `_reader` (background thread)
Continuously opens the serial port and reads up to 1024 raw bytes at a time. Every time bytes arrive it drops them onto `_segments` and immediately goes back to reading. It knows nothing about packet structure — its only job is getting bytes off the wire as fast as possible.

If the port disconnects or throws a `SerialException`, it closes cleanly and waits `RECONNECT_DELAY` seconds before trying to reopen, making the listener resilient to temporary cable disconnects.

### `_processor` (background thread)
Pulls raw byte chunks off `_segments` with a 0.1 second timeout (so it can exit cleanly on stop). Accumulates all incoming chunks into a single growing `bytearray` called `buffer`.

This accumulation step is necessary because reads from `_reader` have no relationship to packet boundaries — a packet might be split across two reads, or one read might contain parts of multiple packets. The `MAX_BUFFER` cap trims the oldest bytes if the buffer grows too large.

### `_scan`
Packet parsing. Operates on the shared buffer in place:

1. Searches for sync bytes `\xAA\x55` — the start-of-packet marker. Returns if not found.
2. Checks that a full 84-byte packet is present in the buffer. Returns if not.
3. Extracts signal bits from the correct offsets:
   - Offset 80 (byte 78 post-sync): bits 3–7 → 5 signals
   - Offsets 81–83 (bytes 79–81 post-sync): all 8 bits each → 24 signals
   - Bit extraction is MSB-first (bit 0 = most significant bit).
4. Zips the 29 boolean values with `SIGNAL_NAMES` to build a `dict[str, bool]`.
5. Pushes the dict onto `_results` and deletes the consumed packet from the front of the buffer.

### `getSignalBits(timeout=5.0) -> dict[str, bool]`
The only public method. Blocks the calling thread until `_scan` has placed a completed packet dict on `_results`, then returns it. Raises `queue.Empty` if no packet arrives within the timeout.

## Packet Layout

| Offset (bytes) | Content |
|---|---|
| 0–1 | Sync bytes `0xAA 0x55` |
| 2–79 | 78 bytes of telemetry (ignored) |
| 80 | Byte 78 post-sync: bits 3–7 are signals |
| 81–83 | Bytes 79–81 post-sync: all 8 bits are signals |

**Total packet length: 84 bytes — 29 signal bits.**

## Signal Reference

Signals are returned in the dict in this order. Bit numbering is MSB-first (bit 0 = most significant bit of the byte).

| # | Key | Packet Offset | Bit |
|---|---|---|---|
| 0 | `discrete03` | 80 | 3 |
| 1 | `discrete02` | 80 | 4 |
| 2 | `discrete01` | 80 | 5 |
| 3 | `rcsRollLeft` | 80 | 6 |
| 4 | `rcsRollRight` | 80 | 7 |
| 5 | `rcsYawLeft` | 81 | 0 |
| 6 | `rcsYawRight` | 81 | 1 |
| 7 | `rcsPitchDown` | 81 | 2 |
| 8 | `rcsPitchUp` | 81 | 3 |
| 9 | `stoppedOnRunway` | 81 | 4 |
| 10 | `approach` | 81 | 5 |
| 11 | `reentryStart` | 81 | 6 |
| 12 | `microgravityEnd` | 81 | 7 |
| 13 | `apogee` | 82 | 0 |
| 14 | `microgravityStart` | 82 | 1 |
| 15 | `engineCutoff` | 82 | 2 |
| 16 | `rocketFiring` | 82 | 3 |
| 17 | `release` | 82 | 4 |
| 18 | `minusTen` | 82 | 5 |
| 19 | `takeOff` | 82 | 6 |
| 20 | `extra` | 82 | 7 |
| 21–28 | `b81_bit0` … `b81_bit7` *(TODO)* | 83 | 0–7 |

> **TODO:** Replace `b81_bit0` through `b81_bit7` in `SIGNAL_NAMES` with the actual signal names for packet offset 83 (byte 81 post-sync) once the ICD is confirmed.

## Configuration

All port and timing constants are defined at the top of `RS422Listener_V2.py`:

| Constant | Value | Description |
|---|---|---|
| `PORT` | `COM3` | Advantech serial port |
| `BAUD` | `6800` | Baud rate (bit/sec) |
| `RECONNECT_DELAY` | `2.0 s` | Wait time before reconnect attempt |
| `MAX_BUFFER` | `4096 bytes` | Hard cap on internal buffer size |
| `PACKET_LENGTH` | `84 bytes` | Total expected packet size |
| `SIGNAL_START` | `80` | Packet offset of first signal byte |
| `SIGNAL_BIT_START` | `3` | First signal bit in the first signal byte |

## Why Two Queues?

`_segments` decouples reading speed from parsing speed — `_reader` can keep pulling bytes off the serial port without waiting for `_scan` to finish. `_results` decouples parsing speed from the caller — `_scan` can process packets ahead of when `getSignalBits()` is called. Each queue is a thread-safe handoff point between the three stages.
