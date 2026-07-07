"""testHarness.py — MUTT Virtual Test Harness (tkinter GUI).

Patches pilxi, pi620lx, and serial into sys.modules BEFORE importing any
flight code, then runs flightController.main() in a background daemon thread.

The GUI lets the operator:
  - Inject 85-byte craft signal frames (manual or auto at a set interval)
  - Observe relay state changes as the flight code drives the Numato board
  - Monitor LXI function-generator channel state in real time
  - Track thread health, flight phase signals, and safe-mode status
  - Read flight-code log output in a scrolled text pane

Run from the repo root:
    python -m testHarness.testHarness
    python testHarness/testHarness.py
"""

import logging
import os
import queue
import sys
import threading
import time
import types
import tkinter as tk
from tkinter import scrolledtext

# ── repo root on sys.path ────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _REPO)

# ── inject virtual hardware into sys.modules BEFORE any flight-code import ───
from testHarness.virtualHardware import (
    VIRTUAL_PILXI,
    VIRTUAL_PI620LX,
    VIRTUAL_SERIAL,
    WAVEFORM_NAMES,
    CRAFT_SYNC,
    CRAFT_FRAME_LEN,
    CRAFT_EVENT_BYTE,
    BIT_SEP,
    BIT_ZG_START,
    BIT_ZG_STOP,
    build_craft_frame,
    get_virtual_port,
    stateBus,
)

sys.modules["pilxi"]            = VIRTUAL_PILXI
sys.modules["pi620lx"]         = VIRTUAL_PI620LX
sys.modules["serial"]          = VIRTUAL_SERIAL
sys.modules["serial.serialutil"] = types.ModuleType("serial.serialutil")

# ── now safe to import flight code ───────────────────────────────────────────
import flightCode.flightController as flightLoop  # noqa: E402

# ── post-import fixups ───────────────────────────────────────────────────────

# Relay port: auto-echo so RelayController.read(25) returns immediately
get_virtual_port(flightLoop.RELAY_PORT).auto_echo = True

# waveConfigs safety: if CSV loading failed, set empty list so the PXI thread
# doesn't crash when it tries to iterate None after zgStart arrives
if flightLoop.waveConfigs is None:
    flightLoop.waveConfigs = []

# ── theme ────────────────────────────────────────────────────────────────────
BG     = "#1e1e2e"
BG_ALT = "#252538"
BG_HL  = "#313150"
FG     = "#cdd6f4"
FG_DIM = "#8888aa"
GREEN  = "#a6e3a1"
RED    = "#f38ba8"
YELLOW = "#f9e2af"
BLUE   = "#89b4fa"

NUM_RELAYS   = 4
NUM_CHANNELS = 6   # 2 cards × 3 channels


# ---------------------------------------------------------------------------
# Logging handler — taps the flight logger so its messages appear in the GUI
# ---------------------------------------------------------------------------

class _TkLogHandler(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self._cb = callback
        fmt = logging.Formatter("%(asctime)s [%(threadName)s] %(levelname)s: %(message)s",
                                datefmt="%H:%M:%S")
        self.setFormatter(fmt)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._cb(msg)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class HarnessApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("MUTT Virtual Test Harness")
        self.configure(bg=BG)
        self.minsize(1120, 720)

        # ── GUI state variables ───────────────────────────────────────────────
        self._relay_states = [False] * NUM_RELAYS
        self._auto_send    = tk.BooleanVar(value=False)
        self._auto_interval = tk.DoubleVar(value=1.0)
        self._last_auto_send = 0.0

        self._event_bits: dict[str, tk.BooleanVar] = {
            "SEP":     tk.BooleanVar(value=False),
            "zgStart": tk.BooleanVar(value=False),
            "zgStop":  tk.BooleanVar(value=False),
            **{f"bit{i}": tk.BooleanVar(value=False) for i in range(3, 8)},
        }

        # ── subscribe to hardware state bus ───────────────────────────────────
        stateBus.subscribe(self._on_hw_event)

        # ── build UI ─────────────────────────────────────────────────────────
        self._build_ui()

        # ── attach log handler to flight logger ───────────────────────────────
        logging.getLogger("flight").addHandler(
            _TkLogHandler(lambda msg: self.after(0, self._log, msg))
        )

        # ── start flight code in daemon thread ────────────────────────────────
        threading.Thread(
            target=self._run_flight_code,
            name="FlightMain",
            daemon=True,
        ).start()

        # ── start craft-frame processor thread ───────────────────────────────
        threading.Thread(
            target=self._craft_processor,
            name="CraftProcessor",
            daemon=True,
        ).start()

        # ── periodic GUI refresh ──────────────────────────────────────────────
        self.after(500, self._poll)

    # ── flight code runner ────────────────────────────────────────────────────

    def _run_flight_code(self) -> None:
        try:
            flightLoop.main()
        except Exception as e:
            self.after(0, self._log, f"[FlightMain] CRASHED: {e}")

    # ── craft-frame processor ─────────────────────────────────────────────────

    def _craft_processor(self) -> None:
        """Read injected bytes from the craft virtual port, parse 85-byte frames,
        and update the flight code's signal/phase state directly."""
        port = get_virtual_port(flightLoop.SERIAL_PORT)
        buf  = bytearray()

        while True:
            try:
                chunk = port._rx_queue.get(timeout=0.2)
                buf.extend(chunk)
            except queue.Empty:
                continue

            while len(buf) >= CRAFT_FRAME_LEN:
                idx = buf.find(CRAFT_SYNC)
                if idx == -1:
                    buf.clear()
                    break
                if idx + CRAFT_FRAME_LEN > len(buf):
                    # Sync found but full frame not yet in buffer
                    if idx:
                        del buf[:idx]
                    break
                frame = bytes(buf[idx: idx + CRAFT_FRAME_LEN])
                del buf[:idx + CRAFT_FRAME_LEN]
                self._apply_craft_frame(frame)

    def _apply_craft_frame(self, frame: bytes) -> None:
        ev  = frame[CRAFT_EVENT_BYTE]
        now = time.time()
        changed = False

        if ev & (1 << BIT_SEP) and not flightLoop.signalStates["sep"]:
            flightLoop.signalStates["sep"]        = True
            flightLoop.signalTimestamps["sep"]     = now
            flightLoop.flightPhase["preLaunch"]   = False
            flightLoop.flightPhase["SEP"]          = True
            changed = True
            self.after(0, self._log, "[CraftProcessor] SEP signal detected")

        if ev & (1 << BIT_ZG_START) and not flightLoop.signalStates["zgStart"]:
            flightLoop.signalStates["zgStart"]     = True
            flightLoop.signalTimestamps["zgStart"] = now
            flightLoop.flightPhase["zgStart"]      = True
            changed = True
            self.after(0, self._log, "[CraftProcessor] zgStart signal detected")

        if ev & (1 << BIT_ZG_STOP) and not flightLoop.signalStates["zgStop"]:
            flightLoop.signalStates["zgStop"]      = True
            flightLoop.signalTimestamps["zgStop"]  = now
            flightLoop.flightPhase["zgStop"]       = True
            changed = True
            self.after(0, self._log, "[CraftProcessor] zgStop signal detected")

        if changed:
            self.after(0, self._refresh_state_panel)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Top bar
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(top, text="MUTT Virtual Test Harness",
                 bg=BG, fg=FG, font=("Helvetica", 14, "bold")).pack(side="left")
        self._status_lbl = tk.Label(top, text="Starting flight code…",
                                    bg=BG, fg=YELLOW, font=("Helvetica", 9))
        self._status_lbl.pack(side="right")

        # Three-column body (craft | relay | state)
        body = tk.Frame(self, bg=BG)
        body.pack(fill="x", padx=10, pady=4)
        self._build_craft_panel(body)
        self._build_relay_panel(body)
        self._build_state_panel(body)

        # LXI channel table
        lxi_frame = tk.LabelFrame(self, text="LXI Function Generators",
                                  bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                                  padx=6, pady=4)
        lxi_frame.pack(fill="x", padx=10, pady=4)
        self._build_lxi_panel(lxi_frame)

        # Log
        log_frame = tk.LabelFrame(self, text="Log",
                                  bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                                  padx=4, pady=4)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self._log_box = scrolledtext.ScrolledText(
            log_frame, bg=BG_ALT, fg=FG, font=("Courier", 8),
            height=9, state="disabled", relief="flat",
        )
        self._log_box.pack(fill="both", expand=True)

    def _build_craft_panel(self, parent) -> None:
        f = tk.LabelFrame(parent, text="Craft Signal (85-byte frame)",
                          bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                          padx=8, pady=4)
        f.pack(side="left", fill="y", padx=(0, 6))

        sync_hex = " ".join(f"{b:02X}" for b in CRAFT_SYNC)
        tk.Label(f, text=f"Sync: {sync_hex}   Event byte index: {CRAFT_EVENT_BYTE}",
                 bg=BG, fg=FG_DIM, font=("Courier", 8)).pack(anchor="w", pady=(0, 4))

        bit_defs = [
            ("SEP",     "bit 0 — SEP"),
            ("zgStart", "bit 1 — zgStart"),
            ("zgStop",  "bit 2 — zgStop"),
            ("bit3",    "bit 3 — spare"),
            ("bit4",    "bit 4 — spare"),
            ("bit5",    "bit 5 — spare"),
            ("bit6",    "bit 6 — spare"),
            ("bit7",    "bit 7 — spare"),
        ]
        for key, label in bit_defs:
            var = self._event_bits.get(key)
            if var is None:
                continue
            tk.Checkbutton(f, text=label, variable=var,
                           bg=BG, fg=FG, selectcolor=BG_HL,
                           activebackground=BG, activeforeground=FG,
                           font=("Courier", 8)).pack(anchor="w")

        btn_row = tk.Frame(f, bg=BG)
        btn_row.pack(fill="x", pady=(6, 0))
        tk.Button(btn_row, text="Send Frame", bg=BG_HL, fg=FG, relief="flat",
                  padx=8, activebackground=BLUE, activeforeground=BG,
                  command=self._send_craft_frame).pack(side="left", padx=(0, 6))
        tk.Checkbutton(btn_row, text="Auto", variable=self._auto_send,
                       bg=BG, fg=FG, selectcolor=BG_HL,
                       activebackground=BG, activeforeground=FG,
                       font=("Helvetica", 8)).pack(side="left")

        interval_row = tk.Frame(f, bg=BG)
        interval_row.pack(fill="x", pady=(2, 0))
        tk.Label(interval_row, text="Interval (s):", bg=BG, fg=FG_DIM,
                 font=("Helvetica", 8)).pack(side="left")
        tk.Spinbox(interval_row, from_=0.1, to=60.0, increment=0.1,
                   textvariable=self._auto_interval, width=5,
                   bg=BG_HL, fg=FG, buttonbackground=BG_HL,
                   relief="flat", font=("Helvetica", 8)).pack(side="left", padx=4)

        tk.Label(f, text="Last frame (hex):", bg=BG, fg=FG_DIM,
                 font=("Helvetica", 8)).pack(anchor="w", pady=(6, 0))
        self._frame_preview = tk.Text(f, bg=BG_ALT, fg=FG_DIM,
                                      font=("Courier", 7), height=3, width=38,
                                      relief="flat", state="disabled",
                                      wrap="word")
        self._frame_preview.pack(fill="x")

    def _build_relay_panel(self, parent) -> None:
        f = tk.LabelFrame(parent, text="Relay States",
                          bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                          padx=8, pady=4)
        f.pack(side="left", fill="y", padx=(0, 6))

        self._relay_indicators: list[tk.Label] = []
        self._relay_labels:     list[tk.Label] = []

        for i in range(NUM_RELAYS):
            row = tk.Frame(f, bg=BG)
            row.pack(fill="x", pady=3)
            ind = tk.Label(row, text="●", fg=RED, bg=BG, font=("Helvetica", 18))
            ind.pack(side="left")
            lbl = tk.Label(row, text=f"Relay {i}:  OFF",
                           bg=BG, fg=FG, font=("Courier", 9), width=14, anchor="w")
            lbl.pack(side="left")
            self._relay_indicators.append(ind)
            self._relay_labels.append(lbl)

        tk.Label(f, text="Last command:", bg=BG, fg=FG_DIM,
                 font=("Helvetica", 8)).pack(anchor="w", pady=(10, 0))
        self._relay_cmd_lbl = tk.Label(f, text="—",
                                       bg=BG_ALT, fg=FG, font=("Courier", 8),
                                       anchor="w", padx=4, relief="flat")
        self._relay_cmd_lbl.pack(fill="x")

    def _build_state_panel(self, parent) -> None:
        f = tk.LabelFrame(parent, text="Flight State & Threads",
                          bg=BG, fg=FG, font=("Helvetica", 9, "bold"),
                          padx=8, pady=4)
        f.pack(side="left", fill="y")

        tk.Label(f, text="Signals:", bg=BG, fg=FG_DIM,
                 font=("Helvetica", 8, "bold")).pack(anchor="w")

        self._sig_indicators: dict[str, tk.Label] = {}
        for sig in ("sep", "zgStart", "zgStop"):
            row = tk.Frame(f, bg=BG)
            row.pack(fill="x", pady=2)
            ind = tk.Label(row, text="●", fg=RED, bg=BG, font=("Helvetica", 14))
            ind.pack(side="left")
            tk.Label(row, text=sig, bg=BG, fg=FG,
                     font=("Courier", 8), width=9, anchor="w").pack(side="left")
            self._sig_indicators[sig] = ind

        tk.Label(f, text="Threads:", bg=BG, fg=FG_DIM,
                 font=("Helvetica", 8, "bold")).pack(anchor="w", pady=(10, 0))

        self._thread_indicators: dict[str, tk.Label] = {}
        for name in ("SERIAL", "PXI", "RELAY", "TELEM", "WATCHDOG"):
            row = tk.Frame(f, bg=BG)
            row.pack(fill="x", pady=2)
            ind = tk.Label(row, text="●", fg=YELLOW, bg=BG, font=("Helvetica", 14))
            ind.pack(side="left")
            tk.Label(row, text=name, bg=BG, fg=FG,
                     font=("Courier", 8), width=10, anchor="w").pack(side="left")
            self._thread_indicators[name] = ind

        self._safe_mode_lbl = tk.Label(f, text="SAFE MODE:  NO",
                                       bg=BG, fg=GREEN, font=("Helvetica", 9, "bold"))
        self._safe_mode_lbl.pack(anchor="w", pady=(10, 0))

    def _build_lxi_panel(self, parent) -> None:
        headers = ["Card", "Ch", "Type",     "Frequency",   "Amplitude", "Offset",  "Phase",  "Status"]
        widths  = [5,      4,    9,           14,            11,          9,         8,        12]

        for col, (h, w) in enumerate(zip(headers, widths)):
            tk.Label(parent, text=h, bg=BG, fg=FG_DIM,
                     font=("Helvetica", 8, "bold"), width=w,
                     anchor="w").grid(row=0, column=col, padx=2, pady=(0, 2))

        self._lxi_labels: dict[tuple, dict] = {}
        row_num = 1
        for card_idx in range(2):
            for ch in range(1, 4):
                key  = (card_idx, ch)
                cols: dict[str, tk.Label] = {}
                vals = [str(card_idx), str(ch), "—", "—", "—", "—", "—", "IDLE"]
                fnames = ["card", "ch", "wf", "freq", "amp", "offset", "phase", "status"]
                for col, (fname, val, w) in enumerate(zip(fnames, vals, widths)):
                    lbl = tk.Label(parent, text=val, bg=BG, fg=FG_DIM if fname in ("card","ch") else FG,
                                   font=("Courier", 8), width=w, anchor="w")
                    lbl.grid(row=row_num, column=col, padx=2, pady=1)
                    cols[fname] = lbl
                self._lxi_labels[key] = cols
                row_num += 1

    # ── hardware event handler ────────────────────────────────────────────────

    def _on_hw_event(self, event: str, data: dict) -> None:
        """Called from any thread — dispatch to main thread for GUI safety."""
        self.after(0, lambda e=event, d=dict(data): self._apply_hw_event(e, d))

    def _apply_hw_event(self, event: str, data: dict) -> None:
        if event == "channel_update":
            self._update_lxi_row(data["card"], data["channel"], data)

        elif event == "card_cleared":
            card = data["card"]
            for ch in range(1, 4):
                cols = self._lxi_labels.get((card, ch))
                if cols:
                    cols["status"].config(text="CLEARED", fg=YELLOW)
                    for k in ("wf", "freq", "amp", "offset", "phase"):
                        cols[k].config(text="—", fg=FG)

        elif event == "serial_write":
            if data.get("port") == flightLoop.RELAY_PORT:
                self._handle_relay_write(data.get("data", b""))

    def _update_lxi_row(self, card: int, ch: int, state: dict) -> None:
        cols = self._lxi_labels.get((card, ch))
        if not cols:
            return
        wf_name    = WAVEFORM_NAMES.get(state.get("waveform", 0), "?")
        generating = state.get("generating", False)
        cols["wf"].config(text=wf_name, fg=FG)
        cols["freq"].config(text=f"{state.get('frequency', 0):.1f} Hz", fg=FG)
        cols["amp"].config(text=f"{state.get('amplitude', 0):.3f} V",   fg=FG)
        cols["offset"].config(text=f"{state.get('offset', 0):.3f} V",   fg=FG)
        cols["phase"].config(text=f"{state.get('phase', 0):.1f}°",      fg=FG)
        cols["status"].config(
            text="GENERATING" if generating else "IDLE",
            fg=GREEN if generating else FG_DIM,
        )

    def _handle_relay_write(self, raw: bytes) -> None:
        text = raw.decode(errors="replace").strip()
        self._relay_cmd_lbl.config(text=text or "—")
        # Parse "relay on N" / "relay off N"
        parts = text.lower().split()
        if len(parts) == 3 and parts[0] == "relay" and parts[2].isdigit():
            idx = int(parts[2])
            on  = (parts[1] == "on")
            if 0 <= idx < NUM_RELAYS:
                self._relay_states[idx] = on
                self._relay_indicators[idx].config(fg=GREEN if on else RED)
                self._relay_labels[idx].config(
                    text=f"Relay {idx}:  {'ON ' if on else 'OFF'}")
                self._log(f"[RELAY] relay {parts[1]} {idx}")

    # ── craft signal sender ───────────────────────────────────────────────────

    def _send_craft_frame(self) -> None:
        sep      = self._event_bits["SEP"].get()
        zg_start = self._event_bits["zgStart"].get()
        zg_stop  = self._event_bits["zgStop"].get()
        extra = sum(
            (1 << i) for i in range(3, 8)
            if self._event_bits.get(f"bit{i}", tk.BooleanVar()).get()
        )
        frame = build_craft_frame(sep=sep, zg_start=zg_start,
                                  zg_stop=zg_stop, extra_bits=extra)
        get_virtual_port(flightLoop.SERIAL_PORT).inject(frame)
        self._update_frame_preview(frame)

    def _update_frame_preview(self, frame: bytes) -> None:
        hex_str = " ".join(f"{b:02X}" for b in frame)
        self._frame_preview.config(state="normal")
        self._frame_preview.delete("1.0", "end")
        self._frame_preview.insert("end", hex_str)
        self._frame_preview.config(state="disabled")

    # ── state panel refresh ───────────────────────────────────────────────────

    def _refresh_state_panel(self) -> None:
        for sig, ind in self._sig_indicators.items():
            detected = flightLoop.signalStates.get(sig, False)
            ind.config(fg=GREEN if detected else RED)

    # ── periodic poll ─────────────────────────────────────────────────────────

    def _poll(self) -> None:
        # Thread health
        alive_count = 0
        for name, ind in self._thread_indicators.items():
            t = flightLoop.threads.get(name)
            if t is None:
                ind.config(fg=YELLOW)
            elif t.is_alive():
                ind.config(fg=GREEN)
                alive_count += 1
            else:
                ind.config(fg=RED)

        # Status bar
        if alive_count == len(self._thread_indicators):
            self._status_lbl.config(text="All threads running", fg=GREEN)
        elif alive_count > 0:
            self._status_lbl.config(text=f"{alive_count}/5 threads running", fg=YELLOW)

        # Safe mode
        if flightLoop.safeModeEvent.is_set():
            self._safe_mode_lbl.config(text="SAFE MODE:  YES", fg=RED)

        # Signal indicators
        self._refresh_state_panel()

        # Auto-send
        if self._auto_send.get():
            now = time.monotonic()
            interval = max(0.1, self._auto_interval.get())
            if now - self._last_auto_send >= interval:
                self._last_auto_send = now
                self._send_craft_frame()

        self.after(500, self._poll)

    # ── log ───────────────────────────────────────────────────────────────────

    def _log(self, message: str) -> None:
        self._log_box.config(state="normal")
        self._log_box.insert("end", message + "\n")
        self._log_box.see("end")
        self._log_box.config(state="disabled")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = HarnessApp()
    app.mainloop()


if __name__ == "__main__":
    main()
