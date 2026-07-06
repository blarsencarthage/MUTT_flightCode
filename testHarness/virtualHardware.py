"""virtualHardware.py — in-memory shims for MUTT flight code testing.

Provides drop-in replacements for:
  pilxi / pi620lx  — Pickering LXI function generators
  serial           — pyserial (craft RS-422 bus + Numato relay board)

Patch these into sys.modules BEFORE importing any flight code:
    sys.modules["pilxi"]   = VIRTUAL_PILXI
    sys.modules["pi620lx"] = VIRTUAL_PI620LX
    sys.modules["serial"]  = VIRTUAL_SERIAL
"""

import queue
import threading
import time
import types
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Observable state bus — hardware shims notify the GUI here
# ---------------------------------------------------------------------------

class _Observable:
    def __init__(self):
        self._listeners: list[Callable] = []
        self._lock = threading.Lock()

    def subscribe(self, fn: Callable) -> None:
        with self._lock:
            self._listeners.append(fn)

    def _notify(self, event: str, data: dict) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for fn in listeners:
            try:
                fn(event, data)
            except Exception:
                pass


stateBus = _Observable()

# ---------------------------------------------------------------------------
# Waveform name map (int enum value -> display string)
# ---------------------------------------------------------------------------

WAVEFORM_NAMES = {
    0: "SINE",
    1: "SQUARE",
    2: "TRIANGLE",
    3: "RAMP",
    4: "PULSE",
}

# ---------------------------------------------------------------------------
# Virtual Pickering LXI card
# ---------------------------------------------------------------------------

class VirtualCard:
    """Mimics a pilxi Pi_Card_ByDevice (41-620 function generator)."""

    def __init__(self, card_index: int):
        self._index = card_index
        self._channels: dict[int, dict] = {}

    def _ch(self, ch: int) -> dict:
        if ch not in self._channels:
            self._channels[ch] = {
                "waveform":  0,
                "frequency": 0.0,
                "amplitude": 0.0,
                "offset":    0.0,
                "phase":     0.0,
                "generating": False,
            }
        return self._channels[ch]

    def _fire(self, ch: int) -> None:
        stateBus._notify("channel_update", {
            "card":    self._index,
            "channel": ch,
            **self._ch(ch),
        })

    # ── pilxi card interface ──────────────────────────────────────────────────

    def CardId(self) -> str:
        return f"VirtualCard-{self._index}"

    def ClearCard(self) -> None:
        self._channels.clear()
        stateBus._notify("card_cleared", {"card": self._index})

    def Close(self) -> None:
        stateBus._notify("card_closed", {"card": self._index})

    def PIFGLX_SetWaveform(self, ch: int, wf_type) -> None:
        self._ch(ch)["waveform"] = int(wf_type)
        self._fire(ch)

    def PIFGLX_SetFrequency(self, ch: int, freq: float) -> None:
        self._ch(ch)["frequency"] = float(freq)
        self._fire(ch)

    def PIFGLX_SetAmplitude(self, ch: int, amp: float) -> None:
        self._ch(ch)["amplitude"] = float(amp)
        self._fire(ch)

    def PIFGLX_SetDcOffset(self, ch: int, offset: float) -> None:
        self._ch(ch)["offset"] = float(offset)
        self._fire(ch)

    def PIFGLX_SetStartPhase(self, ch: int, phase: float) -> None:
        self._ch(ch)["phase"] = float(phase)
        self._fire(ch)

    def PIFGLX_InitiateGeneration(self, ch: int) -> None:
        self._ch(ch)["generating"] = True
        self._fire(ch)

    def PIFGLX_AbortGeneration(self, ch: int) -> None:
        self._ch(ch)["generating"] = False
        self._fire(ch)

    def PIFGLX_GetFrequency(self, ch: int) -> float:
        return self._ch(ch)["frequency"]

    def PIFGLX_GetAmplitude(self, ch: int) -> float:
        return self._ch(ch)["amplitude"]

    def PIFGLX_GetDcOffset(self, ch: int) -> float:
        return self._ch(ch)["offset"]

    def PIFGLX_GetStartPhase(self, ch: int) -> float:
        return self._ch(ch)["phase"]

    def get_channel_state(self, ch: int) -> dict:
        return dict(self._ch(ch))


class VirtualSession:
    """Mimics pilxi.Pi_Session."""

    NUM_CARDS = 2

    def __init__(self, ip_address: str = "pxi"):
        self._opened: list[VirtualCard] = []

    def FindFreeCards(self):
        return [(0, i) for i in range(self.NUM_CARDS)]

    def OpenCard(self, bus: int, device: int) -> VirtualCard:
        card = VirtualCard(card_index=device)
        self._opened.append(card)
        return card


# ---------------------------------------------------------------------------
# Mock pilxi module
# ---------------------------------------------------------------------------

def _make_pilxi_module() -> types.ModuleType:
    mod = types.ModuleType("pilxi")

    class WaveformTypes:
        PIFGLX_WAVEFORM_SINE     = 0
        PIFGLX_WAVEFORM_SQUARE   = 1
        PIFGLX_WAVEFORM_TRIANGLE = 2
        PIFGLX_WAVEFORM_RAMP     = 3
        PIFGLX_WAVEFORM_PULSE    = 4

    class Error(Exception):
        def __init__(self, message: str = "pilxi error"):
            super().__init__(message)
            self.message = message

    mod.WaveformTypes = WaveformTypes
    mod.Error         = Error
    mod.Pi_Session    = VirtualSession
    return mod


def _make_pi620lx_module() -> types.ModuleType:
    return types.ModuleType("pi620lx")


VIRTUAL_PILXI   = _make_pilxi_module()
VIRTUAL_PI620LX = _make_pi620lx_module()


# ---------------------------------------------------------------------------
# Virtual serial port
# ---------------------------------------------------------------------------

class VirtualSerialPort:
    """In-memory bidirectional serial port.

    rx_queue — bytes the harness injects for the flight code to read
    tx_queue — bytes the flight code writes (relay commands, etc.)

    Set auto_echo=True on the relay port so the RelayController's
    read(25) call returns immediately with the echoed command, preventing
    a 1-second timeout per relay command.
    """

    def __init__(self, port: str):
        self.port      = port
        self.is_open   = True
        self.auto_echo = False
        self._timeout  = 0.5
        self._rx_queue: queue.Queue = queue.Queue()
        self._tx_queue: queue.Queue = queue.Queue()

    # ── harness interface ─────────────────────────────────────────────────────

    def inject(self, data: bytes) -> None:
        """Push bytes for the flight code's read() to receive."""
        if data:
            self._rx_queue.put(data)

    def drain_tx(self) -> bytes:
        """Collect all bytes the flight code has written since the last drain."""
        out = bytearray()
        while True:
            try:
                out.extend(self._tx_queue.get_nowait())
            except queue.Empty:
                break
        return bytes(out)

    # ── serial.Serial interface ───────────────────────────────────────────────

    def read(self, size: int = 1) -> bytes:
        result   = bytearray()
        deadline = time.monotonic() + self._timeout
        while len(result) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                chunk = self._rx_queue.get(timeout=min(0.05, remaining))
                result.extend(chunk)
            except queue.Empty:
                break
        return bytes(result[:size])

    def write(self, data: bytes) -> int:
        self._tx_queue.put(data)
        stateBus._notify("serial_write", {"port": self.port, "data": data})
        if self.auto_echo:
            self._rx_queue.put(data)
        return len(data)

    def reset_input_buffer(self) -> None:
        while not self._rx_queue.empty():
            try:
                self._rx_queue.get_nowait()
            except queue.Empty:
                break

    def reset_output_buffer(self) -> None:
        while not self._tx_queue.empty():
            try:
                self._tx_queue.get_nowait()
            except queue.Empty:
                break

    def close(self) -> None:
        self.is_open = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ---------------------------------------------------------------------------
# Port registry — one VirtualSerialPort per COM name
# ---------------------------------------------------------------------------

_port_registry: dict[str, VirtualSerialPort] = {}
_registry_lock = threading.Lock()


def get_virtual_port(port_name: str) -> VirtualSerialPort:
    """Return the singleton VirtualSerialPort for the given port name."""
    with _registry_lock:
        if port_name not in _port_registry:
            _port_registry[port_name] = VirtualSerialPort(port_name)
        return _port_registry[port_name]


# ---------------------------------------------------------------------------
# Mock serial module
# ---------------------------------------------------------------------------

def _make_serial_module() -> types.ModuleType:
    mod = types.ModuleType("serial")

    class SerialException(OSError):
        pass

    class Serial:
        """Intercepted serial.Serial — returns the matching VirtualSerialPort."""

        def __new__(cls, port=None, baudrate=9600, bytesize=8,
                    parity="N", stopbits=1, timeout=0.5, **kw):
            vp = get_virtual_port(port or "UNKNOWN")
            vp._timeout = timeout if timeout is not None else 0.5
            vp.is_open  = True
            return vp

    mod.Serial          = Serial
    mod.SerialException = SerialException
    mod.PARITY_NONE     = "N"
    mod.PARITY_EVEN     = "E"
    mod.PARITY_ODD      = "O"
    return mod


VIRTUAL_SERIAL = _make_serial_module()


# ---------------------------------------------------------------------------
# 85-byte craft signal frame
# ---------------------------------------------------------------------------

# Placeholder constants — update when the real sync word and bit mapping are confirmed.
CRAFT_SYNC       = bytes([0xEB, 0x90])
CRAFT_FRAME_LEN  = 85
CRAFT_EVENT_BYTE = 80   # 0-based index of the flight-event byte within the frame

BIT_SEP      = 0
BIT_ZG_START = 1
BIT_ZG_STOP  = 2
# bits 3-7 are spare


def build_craft_frame(
    sep: bool = False,
    zg_start: bool = False,
    zg_stop:  bool = False,
    extra_bits: int = 0,
) -> bytes:
    """Assemble an 85-byte craft signal frame.

    Sync bytes are placed at indices 0-1.  The event byte at CRAFT_EVENT_BYTE
    carries the flight-event bits.  All other bytes are zero-filled.
    extra_bits is OR-ed into bits 3-7 of the event byte (bits 0-2 ignored).
    """
    frame = bytearray(CRAFT_FRAME_LEN)
    frame[0] = CRAFT_SYNC[0]
    frame[1] = CRAFT_SYNC[1]

    ev = 0
    if sep:      ev |= (1 << BIT_SEP)
    if zg_start: ev |= (1 << BIT_ZG_START)
    if zg_stop:  ev |= (1 << BIT_ZG_STOP)
    ev |= (extra_bits & 0b11111000)

    frame[CRAFT_EVENT_BYTE] = ev
    return bytes(frame)
