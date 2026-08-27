"""Tkinter UI for Starlight Filter.

Wires sliders and buttons to spectrum.py and gamma.py. No math, no Windows calls.
"""

from __future__ import annotations

import atexit
import signal
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from starlight_filter import gamma, spectrum

APP_ID = "eagnespuerto.StarlightFilter"


def _icon_path() -> Path | None:
    """Locate icon.ico both in dev and inside a PyInstaller bundle."""
    if hasattr(sys, "_MEIPASS"):
        candidate = Path(sys._MEIPASS) / "assets" / "icon.ico"
    else:
        candidate = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
    return candidate if candidate.exists() else None
from starlight_filter.spectrum import (
    MAX_KELVIN,
    MIN_KELVIN,
    NAMED_STARS,
    PRESETS,
    Preset,
)

SUN_TEFF = 5778
APPLY_INTERVAL_MS = 33  # ~30 Hz cap for live drags


class StarlightFilterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Starlight Filter")
        self.root.resizable(False, False)

        icon = _icon_path()
        if icon is not None:
            try:
                self.root.iconbitmap(default=str(icon))
            except tk.TclError:
                pass

        self._pending_apply: str | None = None
        self._selected_preset: Preset | None = None

        self._build_ui()
        self._wire_shutdown()

        if not gamma.is_supported():
            self._enter_degraded_mode()
            return

        self._select_preset(self._find_preset("G", "V"))

    # --- UI construction --------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}
        outer = ttk.Frame(self.root, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")

        # Preset grid: 2 rows (V, III) x 7 columns (O..M).
        preset_frame = ttk.LabelFrame(outer, text="Star presets")
        preset_frame.grid(row=0, column=0, sticky="ew", **pad)

        classes = ["O", "B", "A", "F", "G", "K", "M"]
        ttk.Label(preset_frame, text="").grid(row=0, column=0)
        for col, letter in enumerate(classes, start=1):
            ttk.Label(preset_frame, text=letter, anchor="center").grid(
                row=0, column=col, padx=2, pady=(4, 2)
            )

        self._preset_buttons: dict[tuple[str, str], ttk.Button] = {}
        for row, (lum, label) in enumerate(
            [("V", "Dwarf (V)"), ("III", "Giant (III)")], start=1
        ):
            ttk.Label(preset_frame, text=label).grid(
                row=row, column=0, padx=(6, 8), pady=2, sticky="w"
            )
            for col, letter in enumerate(classes, start=1):
                preset = self._find_preset(letter, lum)
                btn = ttk.Button(
                    preset_frame,
                    text=preset.short_label,
                    width=6,
                    command=lambda p=preset: self._select_preset(p),
                )
                btn.grid(row=row, column=col, padx=2, pady=2)
                self._add_tooltip(btn, f"{preset.name}\n{preset.class_letter}{preset.luminosity} · {preset.teff_k} K")
                self._preset_buttons[(letter, lum)] = btn

        # Named-star dropdown (16 famous stars beyond the class-matrix grid).
        named_frame = ttk.LabelFrame(outer, text="More named stars")
        named_frame.grid(row=1, column=0, sticky="ew", **pad)
        named_frame.columnconfigure(0, weight=1)

        self._named_options = [
            f"{s.name} — {s.class_letter}{s.luminosity} · {s.teff_k} K"
            for s in NAMED_STARS
        ]
        self._named_var = tk.StringVar(value="")
        self._named_combo = ttk.Combobox(
            named_frame,
            textvariable=self._named_var,
            values=self._named_options,
            state="readonly",
            width=44,
        )
        self._named_combo.grid(row=0, column=0, padx=8, pady=6, sticky="ew")
        self._named_combo.bind("<<ComboboxSelected>>", self._on_named_selected)

        # Temperature slider.
        temp_frame = ttk.Frame(outer)
        temp_frame.grid(row=2, column=0, sticky="ew", **pad)
        temp_frame.columnconfigure(0, weight=1)

        header = ttk.Frame(temp_frame)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Color temperature").grid(row=0, column=0, sticky="w")
        self._temp_value_label = ttk.Label(header, text=f"{SUN_TEFF} K")
        self._temp_value_label.grid(row=0, column=1, sticky="e")

        self._temp_var = tk.DoubleVar(value=SUN_TEFF)
        self._temp_scale = ttk.Scale(
            temp_frame,
            from_=MIN_KELVIN,
            to=MAX_KELVIN,
            variable=self._temp_var,
            command=self._on_temp_change,
        )
        self._temp_scale.grid(row=1, column=0, sticky="ew", pady=(2, 0))

        legend = ttk.Frame(temp_frame)
        legend.grid(row=2, column=0, sticky="ew")
        legend.columnconfigure(0, weight=1)
        ttk.Label(legend, text=f"{int(MIN_KELVIN)} K").grid(row=0, column=0, sticky="w")
        ttk.Label(legend, text=f"{int(MAX_KELVIN)} K").grid(row=0, column=1, sticky="e")

        # Blue-light slider.
        blue_frame = ttk.Frame(outer)
        blue_frame.grid(row=3, column=0, sticky="ew", **pad)
        blue_frame.columnconfigure(0, weight=1)

        b_header = ttk.Frame(blue_frame)
        b_header.grid(row=0, column=0, sticky="ew")
        b_header.columnconfigure(0, weight=1)
        ttk.Label(b_header, text="Blue-light reduction").grid(row=0, column=0, sticky="w")
        self._blue_value_label = ttk.Label(b_header, text="0 %")
        self._blue_value_label.grid(row=0, column=1, sticky="e")

        self._blue_var = tk.DoubleVar(value=0.0)
        self._blue_scale = ttk.Scale(
            blue_frame,
            from_=0.0,
            to=100.0,
            variable=self._blue_var,
            command=self._on_blue_change,
        )
        self._blue_scale.grid(row=1, column=0, sticky="ew", pady=(2, 0))

        b_legend = ttk.Frame(blue_frame)
        b_legend.grid(row=2, column=0, sticky="ew")
        b_legend.columnconfigure(0, weight=1)
        ttk.Label(b_legend, text="0 %").grid(row=0, column=0, sticky="w")
        ttk.Label(b_legend, text="100 %").grid(row=0, column=1, sticky="e")

        # Action buttons.
        actions = ttk.Frame(outer)
        actions.grid(row=4, column=0, sticky="e", **pad)
        self._reset_btn = ttk.Button(actions, text="Reset", command=self._on_reset)
        self._reset_btn.grid(row=0, column=0, padx=(0, 6))
        self._apply_btn = ttk.Button(actions, text="Apply", command=self._apply_now)
        self._apply_btn.grid(row=0, column=1)

        self._all_controls = (
            list(self._preset_buttons.values())
            + [
                self._named_combo,
                self._temp_scale,
                self._blue_scale,
                self._reset_btn,
                self._apply_btn,
            ]
        )

    # --- Events -----------------------------------------------------------

    def _on_temp_change(self, _value: str) -> None:
        self._temp_value_label.config(text=f"{int(self._temp_var.get())} K")
        self._selected_preset = None
        self._named_var.set("")
        self._schedule_apply()

    def _on_named_selected(self, _event=None) -> None:
        idx = self._named_combo.current()
        if idx < 0:
            return
        star = NAMED_STARS[idx]
        self._select_preset(star)

    def _on_blue_change(self, _value: str) -> None:
        self._blue_value_label.config(text=f"{int(self._blue_var.get())} %")
        self._schedule_apply()

    def _on_reset(self) -> None:
        gamma.restore()
        self._temp_var.set(SUN_TEFF)
        self._temp_value_label.config(text=f"{SUN_TEFF} K")
        self._blue_var.set(0.0)
        self._blue_value_label.config(text="0 %")
        self._select_preset(self._find_preset("G", "V"))

    def _select_preset(self, preset: Preset) -> None:
        self._selected_preset = preset
        self._temp_var.set(preset.teff_k)
        self._temp_value_label.config(text=f"{preset.teff_k} K")
        # Keep the dropdown in sync: show the star's label if it's a named
        # star, clear it if the click came from the class-matrix grid.
        try:
            idx = NAMED_STARS.index(preset)
            self._named_var.set(self._named_options[idx])
        except ValueError:
            self._named_var.set("")
        self._apply_now()

    def _schedule_apply(self) -> None:
        if self._pending_apply is not None:
            return
        self._pending_apply = self.root.after(APPLY_INTERVAL_MS, self._apply_now)

    def _apply_now(self) -> None:
        if self._pending_apply is not None:
            self.root.after_cancel(self._pending_apply)
            self._pending_apply = None
        kelvin = self._temp_var.get()
        blue_amount = self._blue_var.get() / 100.0
        rgb = spectrum.rgb_scale_for_temperature(kelvin)
        rgb = spectrum.apply_blue_reduction(rgb, blue_amount)
        gamma.apply(rgb)

    # --- Shutdown & degraded mode ----------------------------------------

    def _wire_shutdown(self) -> None:
        atexit.register(gamma.restore)
        self.root.protocol("WM_DELETE_WINDOW", self._shutdown)
        try:
            signal.signal(signal.SIGINT, lambda *_: self._shutdown())
        except (ValueError, OSError):
            # SIGINT can't always be set from a non-main thread; harmless.
            pass

    def _shutdown(self) -> None:
        try:
            gamma.restore()
        finally:
            self.root.destroy()

    def _enter_degraded_mode(self) -> None:
        for control in self._all_controls:
            control.state(["disabled"])
        messagebox.showwarning(
            "Starlight Filter",
            "This display does not support gamma-ramp control.\n\n"
            "Common causes: HDR mode, a color-managed pro display, or a driver "
            "that blocks SetDeviceGammaRamp. The app cannot change the white "
            "point on this monitor.",
        )

    # --- Helpers ----------------------------------------------------------

    def _find_preset(self, class_letter: str, luminosity: str) -> Preset:
        for p in PRESETS:
            if p.class_letter == class_letter and p.luminosity == luminosity:
                return p
        raise KeyError(f"No preset for {class_letter}{luminosity}")

    def _add_tooltip(self, widget: tk.Widget, text: str) -> None:
        tip: dict[str, tk.Toplevel | None] = {"win": None}

        def show(_event=None):
            if tip["win"] is not None:
                return
            x = widget.winfo_rootx() + 10
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            win = tk.Toplevel(widget)
            win.wm_overrideredirect(True)
            win.wm_geometry(f"+{x}+{y}")
            ttk.Label(
                win,
                text=text,
                background="#111",
                foreground="#eee",
                padding=(6, 3),
                justify="left",
            ).pack()
            tip["win"] = win

        def hide(_event=None):
            win = tip["win"]
            if win is not None:
                win.destroy()
                tip["win"] = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)
        widget.bind("<ButtonPress>", hide)


def main() -> None:
    gamma.set_app_user_model_id(APP_ID)
    gamma.capture_original()
    root = tk.Tk()
    try:
        app = StarlightFilterApp(root)
        root.mainloop()
    except Exception:
        gamma.restore()
        raise
    finally:
        gamma.restore()


if __name__ == "__main__":
    main()
