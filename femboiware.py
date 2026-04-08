#!/usr/bin/env python3
"""
FemboiWare — desktop toy: borderless image windows that bounce around the screen.
A new window spawns when one hits a screen edge (up to MAX_WINDOWS).
Escape quits (global listener via pynput). Ctrl+C in the terminal also quits.
"""

from __future__ import annotations

import math
import random
import signal
import sys
import tkinter as tk
from pathlib import Path

try:
    from PIL import Image, ImageTk
except ImportError:
    print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

try:
    from pynput import keyboard as pynkeyboard
except ImportError:
    pynkeyboard = None

SCRIPT_DIR = Path(__file__).resolve().parent
IMAGE_PATH = SCRIPT_DIR / "assets" / "image.png"

# Tunables
MAX_WINDOWS = 64
INITIAL_WINDOWS = 8
MOVE_INTERVAL_MS = 50
SPEED_PX = 10
MAX_DISPLAY_SIDE = 420


class FemboiWare:
    def __init__(self) -> None:
        self.running = True
        self.windows: list[tk.Toplevel] = []
        self._kb_listener = None  # pynput.keyboard.Listener when started

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("FemboiWare")
        for seq in ("<Escape>", "<KeyPress-Escape>"):
            self.root.bind_all(seq, self.shutdown)
        self.root.bind_all("<KeyPress>", self._global_keypress)
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        pil = Image.open(IMAGE_PATH).convert("RGBA")
        w, h = pil.size
        if max(w, h) > MAX_DISPLAY_SIDE:
            scale = MAX_DISPLAY_SIDE / max(w, h)
            pil = pil.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(pil)
        self.img_w, self.img_h = pil.size

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        for _ in range(INITIAL_WINDOWS):
            self._spawn(sw, sh)

        self._start_global_escape_listener()

    def _start_global_escape_listener(self) -> None:
        if pynkeyboard is None:
            print(
                "Warning: pynput not installed; Escape may not work on borderless windows. "
                "pip install pynput  (or use Ctrl+C in this terminal)",
                file=sys.stderr,
            )
            return

        def on_press(key: object) -> None:
            if key == pynkeyboard.Key.esc and self.running:
                try:
                    self.root.after(0, self.shutdown)
                except tk.TclError:
                    pass

        self._kb_listener = pynkeyboard.Listener(on_press=on_press)
        self._kb_listener.start()

    def _global_keypress(self, event: tk.Event) -> None:
        if getattr(event, "keysym", None) == "Escape":
            self.shutdown(event)

    def _bind_escape(self, widget: tk.Misc) -> None:
        for seq in ("<Escape>", "<KeyPress-Escape>"):
            widget.bind(seq, self.shutdown)

    def _random_velocity(self) -> tuple[int, int]:
        angle = random.uniform(0.0, 2.0 * math.pi)
        vx = int(round(SPEED_PX * math.cos(angle)))
        vy = int(round(SPEED_PX * math.sin(angle)))
        if vx == 0:
            vx = random.choice((-SPEED_PX, SPEED_PX))
        if vy == 0:
            vy = random.choice((-SPEED_PX, SPEED_PX))
        return vx, vy

    def _spawn(self, sw: int, sh: int) -> None:
        if len(self.windows) >= MAX_WINDOWS:
            return

        tw = tk.Toplevel(self.root)
        tw.overrideredirect(True)
        tw.attributes("-topmost", True)

        x = random.randint(0, max(0, sw - self.img_w))
        y = random.randint(0, max(0, sh - self.img_h))
        tw.geometry(f"{self.img_w}x{self.img_h}+{x}+{y}")

        lbl = tk.Label(tw, image=self.photo, bd=0, highlightthickness=0, takefocus=True)
        lbl.pack()

        vx, vy = self._random_velocity()
        tw._vx, tw._vy = vx, vy  # type: ignore[attr-defined]

        self._bind_escape(tw)
        self._bind_escape(lbl)

        lbl.bind("<Button-1>", lambda e, t=tw, l=lbl: self._on_press(t, l, e))
        lbl.bind("<B1-Motion>", lambda e, t=tw: self._drag_motion(t, e))

        tw.protocol("WM_DELETE_WINDOW", lambda t=tw: self._on_try_close(t))
        self.windows.append(tw)
        self._move_loop(tw)

    @staticmethod
    def _on_press(w: tk.Toplevel, lbl: tk.Label, e: tk.Event) -> None:
        lbl.focus_set()
        w._drag_x = e.x  # type: ignore[attr-defined]
        w._drag_y = e.y  # type: ignore[attr-defined]

    @staticmethod
    def _drag_motion(w: tk.Toplevel, e: tk.Event) -> None:
        try:
            nx = w.winfo_x() + e.x - w._drag_x  # type: ignore[attr-defined]
            ny = w.winfo_y() + e.y - w._drag_y  # type: ignore[attr-defined]
            w.geometry(f"+{nx}+{ny}")
        except tk.TclError:
            pass

    def _move_loop(self, w: tk.Toplevel) -> None:
        if not self.running or w not in self.windows:
            return
        try:
            if not w.winfo_exists():
                return
            vx = int(w._vx)  # type: ignore[attr-defined]
            vy = int(w._vy)  # type: ignore[attr-defined]
            sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
            # Use image size, not winfo_width/height — Toplevel often reports 1×1 until mapped,
            # so right/bottom edge checks miss and new windows rarely spawn.
            ww, wh = self.img_w, self.img_h
            nx = w.winfo_x() + vx
            ny = w.winfo_y() + vy
            bounced_x = False
            bounced_y = False
            if nx <= 0:
                nx = 0
                bounced_x = True
                w._vx = abs(vx)  # type: ignore[attr-defined]
            elif nx + ww >= sw:
                nx = max(0, sw - ww)
                bounced_x = True
                w._vx = -abs(vx)  # type: ignore[attr-defined]
            if ny <= 0:
                ny = 0
                bounced_y = True
                w._vy = abs(vy)  # type: ignore[attr-defined]
            elif ny + wh >= sh:
                ny = max(0, sh - wh)
                bounced_y = True
                w._vy = -abs(vy)  # type: ignore[attr-defined]
            w.geometry(f"+{nx}+{ny}")
            if bounced_x or bounced_y:
                self._spawn(sw, sh)
        except tk.TclError:
            return
        w.after(MOVE_INTERVAL_MS, lambda: self._move_loop(w))

    def _on_try_close(self, w: tk.Toplevel) -> None:
        if not self.running:
            return
        if w in self.windows:
            self.windows.remove(w)
        try:
            w.destroy()
        except tk.TclError:
            pass

    def shutdown(self, _event: tk.Event | None = None) -> None:
        if not self.running:
            return
        self.running = False
        if self._kb_listener is not None:
            try:
                self._kb_listener.stop()
            except Exception:
                pass
            self._kb_listener = None
        for w in list(self.windows):
            try:
                w.destroy()
            except tk.TclError:
                pass
        self.windows.clear()
        self.root.quit()
        self.root.destroy()

    def run(self) -> None:
        def _sigint(_signum: int, _frame: object) -> None:
            try:
                self.root.after(0, self.shutdown)
            except tk.TclError:
                pass

        signal.signal(signal.SIGINT, _sigint)
        self.root.mainloop()


def main() -> None:
    if not IMAGE_PATH.is_file():
        print(f"Missing image at {IMAGE_PATH}", file=sys.stderr)
        sys.exit(1)
    FemboiWare().run()


if __name__ == "__main__":
    main()
