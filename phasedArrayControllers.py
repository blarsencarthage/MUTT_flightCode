
# Author: Braedon Larsen
# Created: 2026-06-11
# GUI controller for 12-element phased array ultrasonic transducer system.

import os
import sys
import math
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pickeringControls.pickeringInterface import initPXIE, updateWaveform

# ══════════════════════════════════════════════════════════════════════════════
# HARDWARE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

NUM_PAIRS = 6

# pair_index → (card_list_index, channel_number)
# card_list_index is the position in the list returned by initPXIE()
CHANNEL_MAP = {
    0: (0, 1), 1: (0, 2), 2: (0, 3),
    3: (1, 1), 4: (1, 2), 5: (1, 3),
}

# ══════════════════════════════════════════════════════════════════════════════
# ARRAY DIAGRAM GEOMETRY
# Edit TRANSDUCER_XY and TRANSDUCER_PAIR to reconfigure the physical layout.
# ══════════════════════════════════════════════════════════════════════════════

PAIR_COLORS = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948"]

# Normalized (x, y) in [0,1]² for each of the 12 transducers.
# Arranged in a 2-3-4-3 diamond hex pattern (rows top → bottom).
TRANSDUCER_XY = [
    # Row 0 — 2 elements
    (0.38, 0.10), (0.62, 0.10),
    # Row 1 — 3 elements
    (0.24, 0.35), (0.50, 0.35), (0.76, 0.35),
    # Row 2 — 4 elements
    (0.11, 0.60), (0.37, 0.60), (0.63, 0.60), (0.89, 0.60),
    # Row 3 — 3 elements
    (0.24, 0.85), (0.50, 0.85), (0.76, 0.85),
]

# Which pair each transducer belongs to (transducer_index → pair_index).
# Consecutive pairs of transducers share a channel: 0,1→pair0; 2,3→pair1 …
TRANSDUCER_PAIR = [i // 2 for i in range(12)]

# ══════════════════════════════════════════════════════════════════════════════
# PARAMETER DEFINITIONS
# (key, label, hard_min, hard_max, default, slider_min, slider_max, fmt_spec)
# ══════════════════════════════════════════════════════════════════════════════

PARAMS = [
    ("freq",   "Freq (Hz)",  100.0, 1_000_000.0, 40_000.0, 1_000.0, 200_000.0, ".0f"),
    ("amp",    "Amp (V)",      0.0,         5.0,      1.0,     0.0,       5.0,  ".3f"),
    ("offset", "Offset (V)",   0.0,         5.0,      0.0,     0.0,       5.0,  ".3f"),
    ("phase",  "Phase (°)",    0.0,       360.0,      0.0,     0.0,     360.0,  ".1f"),
]

# ── Theme ────────────────────────────────────────────────────────────────────
BG      = "#1e1e2e"
BG_ALT  = "#252538"
BG_HL   = "#313150"
FG      = "#cdd6f4"
FG_DIM  = "#8888aa"


# ══════════════════════════════════════════════════════════════════════════════
# ARRAY DIAGRAM CANVAS
# ══════════════════════════════════════════════════════════════════════════════

class ArrayDiagram(tk.Canvas):
    """Canvas widget that renders the phased array transducer layout."""

    RADIUS = 20

    def __init__(self, parent, on_select=None, **kw):
        kw.setdefault("bg", BG)
        kw.setdefault("highlightthickness", 0)
        super().__init__(parent, **kw)
        self._on_select = on_select
        self._selected: int | None = None
        self.bind("<Configure>", lambda e: self._draw(e.width, e.height))
        self.bind("<Button-1>",  self._on_click)

    def _draw(self, w: int, h: int) -> None:
        self.delete("all")
        r = self.RADIUS

        # dashed lines connecting paired transducers
        pair_coords: dict[int, list[tuple[float, float]]] = {}
        for i, (nx, ny) in enumerate(TRANSDUCER_XY):
            p = TRANSDUCER_PAIR[i]
            pair_coords.setdefault(p, []).append((nx * w, ny * h))

        for p, pts in pair_coords.items():
            if len(pts) == 2:
                self.create_line(*pts[0], *pts[1],
                                 fill=PAIR_COLORS[p], width=2, dash=(5, 4))

        # transducer circles
        for i, (nx, ny) in enumerate(TRANSDUCER_XY):
            p = TRANSDUCER_PAIR[i]
            cx, cy = nx * w, ny * h
            selected = (p == self._selected)
            self.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill=PAIR_COLORS[p],
                outline="white" if selected else "#44446a",
                width=3 if selected else 1,
            )
            self.create_text(cx, cy, text=str(p + 1),
                             fill="white", font=("Helvetica", 9, "bold"))

        # legend
        legend_y_start = h - NUM_PAIRS * 18 - 6
        for p in range(NUM_PAIRS):
            lx = 8
            ly = legend_y_start + p * 18
            self.create_oval(lx, ly, lx + 12, ly + 12,
                             fill=PAIR_COLORS[p], outline="")
            self.create_text(lx + 18, ly + 6, anchor="w",
                             text=f"Pair {p + 1}",
                             fill=FG_DIM, font=("Helvetica", 8))

    def _on_click(self, event: tk.Event) -> None:
        w, h = self.winfo_width(), self.winfo_height()
        for i, (nx, ny) in enumerate(TRANSDUCER_XY):
            cx, cy = nx * w, ny * h
            if math.hypot(event.x - cx, event.y - cy) <= self.RADIUS:
                p = TRANSDUCER_PAIR[i]
                self._selected = p
                self._draw(w, h)
                if self._on_select:
                    self._on_select(p)
                return

    def select_pair(self, pair_idx: int) -> None:
        """Highlight the given pair and redraw."""
        self._selected = pair_idx
        self._draw(self.winfo_width(), self.winfo_height())


# ══════════════════════════════════════════════════════════════════════════════
# SCROLLABLE FRAME
# ══════════════════════════════════════════════════════════════════════════════

class ScrollFrame(tk.Frame):
    """A vertically scrollable container; add child widgets to .inner."""

    def __init__(self, parent, **kw):
        kw.setdefault("bg", BG)
        super().__init__(parent, **kw)
        self._canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self._sb = tk.Scrollbar(self, orient="vertical",
                                command=self._canvas.yview)
        self.inner = tk.Frame(self._canvas, bg=BG)
        self._win_id = self._canvas.create_window(
            (0, 0), window=self.inner, anchor="nw")

        self._canvas.configure(yscrollcommand=self._sb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._sb.pack(side="right", fill="y")

        self.inner.bind("<Configure>", self._on_inner_resize)
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_inner_resize(self, _) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event) -> None:
        self._canvas.itemconfig(self._win_id, width=event.width)

    def _on_mousewheel(self, event) -> None:
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# ══════════════════════════════════════════════════════════════════════════════
# PAIR CONTROL ROW
# ══════════════════════════════════════════════════════════════════════════════

class PairControls(tk.Frame):
    """Slider + entry controls for one transducer pair."""

    def __init__(self, parent, pair_idx: int, cards: list,
                 on_focus=None, **kw):
        bg = BG if pair_idx % 2 == 0 else BG_ALT
        super().__init__(parent, bg=bg, padx=4, pady=4, **kw)
        self._idx = pair_idx
        self._cards = cards        # shared list; mutated by main app on init
        self._on_focus = on_focus
        self._bg = bg
        self._vars: dict[str, tk.DoubleVar] = {}
        self._entries: dict[str, tuple] = {}
        self._build()

    def _build(self) -> None:
        bg = self._bg
        color = PAIR_COLORS[self._idx]

        # colored dot + label
        tk.Label(self, text="●", fg=color, bg=bg,
                 font=("Helvetica", 16)).grid(row=0, column=0,
                                              rowspan=2, padx=(2, 4))
        tk.Label(self, text=f"Pair {self._idx + 1}", fg=FG, bg=bg,
                 font=("Helvetica", 9, "bold"),
                 width=6, anchor="w").grid(row=0, column=1, rowspan=2,
                                           padx=(0, 10))

        for col_i, (key, label, hard_min, hard_max,
                    default, sl_min, sl_max, fmt) in enumerate(PARAMS):
            c = col_i * 3 + 2

            tk.Label(self, text=label, fg=FG_DIM, bg=bg,
                     font=("Helvetica", 8),
                     anchor="center").grid(row=0, column=c,
                                           columnspan=2, sticky="ew", padx=2)

            var = tk.DoubleVar(value=default)
            self._vars[key] = var

            scale = tk.Scale(
                self, from_=sl_min, to=sl_max, variable=var,
                orient="horizontal", length=120, showvalue=False,
                bg=bg, fg=FG, troughcolor=BG_HL,
                activebackground=color, highlightthickness=0, bd=0,
                command=lambda v, k=key, f=fmt: self._push_to_entry(k, float(v), f),
            )
            scale.grid(row=1, column=c, padx=(2, 0), sticky="ew")

            entry = tk.Entry(self, width=10, justify="center",
                             bg=BG_HL, fg=FG, insertbackground=FG,
                             relief="flat", bd=2)
            entry.insert(0, format(default, fmt))
            entry.grid(row=1, column=c + 1, padx=(2, 8))
            entry.bind("<Return>",   lambda _, k=key: self._pull_from_entry(k))
            entry.bind("<FocusOut>", lambda _, k=key: self._pull_from_entry(k))
            entry.bind("<FocusIn>",  lambda _: self._on_focus and
                                               self._on_focus(self._idx))
            self._entries[key] = (entry, fmt, hard_min, hard_max)

        # Apply button
        tk.Button(self, text="Apply", bg=BG_HL, fg=FG, relief="flat",
                  padx=8, activebackground=color, activeforeground="white",
                  command=self._apply).grid(
            row=0, column=len(PARAMS) * 3 + 2, rowspan=2, padx=(4, 2))

    # ── slider → entry sync ──────────────────────────────────────────────────

    def _push_to_entry(self, key: str, val: float, fmt: str) -> None:
        entry, _, _, _ = self._entries[key]
        entry.delete(0, "end")
        entry.insert(0, format(val, fmt))

    # ── entry → slider sync ──────────────────────────────────────────────────

    def _pull_from_entry(self, key: str) -> None:
        entry, fmt, lo, hi = self._entries[key]
        try:
            val = float(entry.get())
            val = max(lo, min(hi, val))
            self._vars[key].set(val)
            entry.delete(0, "end")
            entry.insert(0, format(val, fmt))
        except ValueError:
            pass

    # ── hardware call ────────────────────────────────────────────────────────

    def _apply(self) -> None:
        if self._on_focus:
            self._on_focus(self._idx)
        card_idx, channel = CHANNEL_MAP[self._idx]
        if card_idx < len(self._cards):
            updateWaveform(
                self._cards[card_idx],
                channel,
                frequency=self._vars["freq"].get(),
                amplitude=self._vars["amp"].get(),
                offset=self._vars["offset"].get(),
                phase=self._vars["phase"].get(),
            )
        else:
            print(f"Pair {self._idx + 1}: card index {card_idx} not available "
                  f"({len(self._cards)} card(s) found).")

    def apply(self) -> None:
        """Public entry point for 'Apply All'."""
        self._apply()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════════

class PhasedArrayGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Phased Array Transducer Control")
        self.configure(bg=BG)
        self.minsize(960, 520)

        # Shared list — PairControls holds a reference to this same object.
        # Populated after hardware init so all controls see the real cards.
        self._cards: list = []
        self._pair_controls: list[PairControls] = []

        self._build_ui()
        self.after(150, self._init_hardware)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # title bar
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(top, text="Phased Array Transducer Control",
                 bg=BG, fg=FG, font=("Helvetica", 14, "bold")).pack(side="left")
        self._status_var = tk.StringVar(value="Initializing hardware…")
        tk.Label(top, textvariable=self._status_var,
                 bg=BG, fg=FG_DIM, font=("Helvetica", 9)).pack(side="right")

        # horizontal split: diagram | controls
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=4)

        # ── left: array diagram ───────────────────────────────────────────────
        left = tk.Frame(body, bg=BG, width=300)
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)

        tk.Label(left, text="Array Diagram", bg=BG, fg=FG,
                 font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(0, 4))

        self._diagram = ArrayDiagram(left, on_select=self._on_pair_select)
        self._diagram.pack(fill="both", expand=True)

        # ── right: scrollable pair controls ──────────────────────────────────
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        tk.Label(right, text="Pair Controls", bg=BG, fg=FG,
                 font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(0, 4))

        scroll = ScrollFrame(right)
        scroll.pack(fill="both", expand=True)

        for i in range(NUM_PAIRS):
            ctrl = PairControls(scroll.inner, pair_idx=i,
                                cards=self._cards,
                                on_focus=self._on_pair_select)
            ctrl.pack(fill="x", pady=1)
            # thin separator
            tk.Frame(scroll.inner, bg=BG_HL, height=1).pack(fill="x")
            self._pair_controls.append(ctrl)

        # ── bottom action bar ─────────────────────────────────────────────────
        bot = tk.Frame(self, bg=BG)
        bot.pack(fill="x", padx=12, pady=(4, 10))

        for label, cmd in [("Apply All Pairs", self._apply_all),
                            ("Stop All",        self._stop_all)]:
            tk.Button(bot, text=label, bg=BG_HL, fg=FG, relief="flat",
                      padx=12, pady=5,
                      activebackground="#4e4e70", activeforeground=FG,
                      command=cmd).pack(side="left", padx=(0, 10))

    # ── hardware ──────────────────────────────────────────────────────────────

    def _init_hardware(self) -> None:
        try:
            cards = initPXIE()
            self._cards.extend(cards)
            n = len(cards)
            self._status_var.set(
                f"Connected — {n} card{'s' if n != 1 else ''} found")
        except Exception as ex:
            self._status_var.set(f"Hardware error: {ex}")
            print("Hardware init error:", ex)

    # ── callbacks ─────────────────────────────────────────────────────────────

    def _on_pair_select(self, pair_idx: int) -> None:
        self._diagram.select_pair(pair_idx)

    def _apply_all(self) -> None:
        for ctrl in self._pair_controls:
            ctrl.apply()

    def _stop_all(self) -> None:
        for card in self._cards:
            for ch in range(1, 7):
                try:
                    card.PILFG_AbortGeneration(ch)
                except Exception:
                    pass
        self._status_var.set("All channels stopped")


# ══════════════════════════════════════════════════════════════════════════════

def main():
    app = PhasedArrayGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
