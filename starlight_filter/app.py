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

from starlight_filter import autostart, gamma, settings, single_instance, spectrum

APP_ID = "eagnespuerto.StarlightFilter"


def _icon_path() -> Path | None:
    """Locate icon.ico both in dev and inside a PyInstaller bundle."""
    if hasattr(sys, "_MEIPASS"):
        candidate = Path(sys._MEIPASS) / "assets" / "icon.ico"
    else:
        candidate = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
    return candidate if candidate.exists() else None
from starlight_filter.spectrum import (
    ATMOSPHERES,
    DEFAULT_ATMOSPHERE,
    MAX_KELVIN,
    MIN_KELVIN,
    NAMED_STARS,
    PRESETS,
    Preset,
)

SUN_TEFF = 5778
APPLY_INTERVAL_MS = 33  # ~30 Hz cap for live drags
KEEP_ALIVE_MS = 2000    # re-apply ramp so wake/lock resets don't strand us
SAVE_DEBOUNCE_MS = 500  # coalesce bursts of slider drags into one write


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
        self._pending_save: str | None = None
        self._keep_alive_task: str | None = None
        self._selected_preset: Preset | None = None
        self._atmosphere_key: str = DEFAULT_ATMOSPHERE
        self._tray_icon = None  # populated by start_tray() if available

        self._build_ui()
        self._wire_shutdown()
        self._start_tray()

        if not gamma.is_supported():
            self._enter_degraded_mode()
            return

        self._restore_state_or_default_to_sun()
        self._schedule_keep_alive()

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

        # Dynamic warning line for extreme temperatures. Empty in the safe
        # middle band; fills with a short heads-up at either end.
        self._temp_warning_var = tk.StringVar(value="")
        self._temp_warning_label = ttk.Label(
            temp_frame,
            textvariable=self._temp_warning_var,
            foreground="#a15c00",
            wraplength=360,
            justify="left",
        )
        self._temp_warning_label.grid(row=3, column=0, sticky="ew", pady=(2, 0))

        # Atmospheric scattering dropdown — modulates the photospheric color
        # by a per-wavelength transmission spectrum before the CIE integral,
        # so cool/absorbing atmospheres tint the display accordingly.
        atmo_frame = ttk.LabelFrame(outer, text="Atmospheric scattering")
        atmo_frame.grid(row=3, column=0, sticky="ew", **pad)
        atmo_frame.columnconfigure(0, weight=1)

        self._atmosphere_options = [a.name for a in ATMOSPHERES]
        self._atmosphere_var = tk.StringVar(
            value=self._atmosphere_name_for_key(self._atmosphere_key)
        )
        self._atmosphere_combo = ttk.Combobox(
            atmo_frame,
            textvariable=self._atmosphere_var,
            values=self._atmosphere_options,
            state="readonly",
            width=44,
        )
        self._atmosphere_combo.grid(row=0, column=0, padx=8, pady=(6, 2), sticky="ew")
        self._atmosphere_combo.bind(
            "<<ComboboxSelected>>", self._on_atmosphere_selected
        )

        self._atmosphere_desc_var = tk.StringVar(value="")
        ttk.Label(
            atmo_frame,
            textvariable=self._atmosphere_desc_var,
            foreground="#555",
            wraplength=360,
            justify="left",
        ).grid(row=1, column=0, padx=8, pady=(0, 6), sticky="ew")
        self._update_atmosphere_description()

        # Bottom row: autostart checkbox on the left, actions on the right.
        bottom = ttk.Frame(outer)
        bottom.grid(row=4, column=0, sticky="ew", **pad)
        bottom.columnconfigure(0, weight=1)

        self._autostart_var = tk.BooleanVar(value=autostart.is_enabled())
        self._autostart_check = ttk.Checkbutton(
            bottom,
            text="Start with Windows",
            variable=self._autostart_var,
            command=self._on_autostart_toggle,
        )
        self._autostart_check.grid(row=0, column=0, sticky="w")

        actions = ttk.Frame(bottom)
        actions.grid(row=0, column=1, sticky="e")
        self._reset_btn = ttk.Button(actions, text="Reset", command=self._on_reset)
        self._reset_btn.grid(row=0, column=0, padx=(0, 6))
        self._apply_btn = ttk.Button(actions, text="Apply", command=self._apply_now)
        self._apply_btn.grid(row=0, column=1)

        self._all_controls = (
            list(self._preset_buttons.values())
            + [
                self._named_combo,
                self._temp_scale,
                self._atmosphere_combo,
                self._reset_btn,
                self._apply_btn,
                self._autostart_check,
            ]
        )

    # --- Events -----------------------------------------------------------

    def _on_temp_change(self, _value: str) -> None:
        self._temp_value_label.config(text=f"{int(self._temp_var.get())} K")
        self._update_temp_warning()
        self._selected_preset = None
        self._named_var.set("")
        self._schedule_apply()

    def _update_temp_warning(self) -> None:
        # Advisory only — the gamma stack always runs; this just tells the
        # user why their screen might look flat or unreadable at the extremes.
        kelvin = self._temp_var.get()
        if kelvin <= 2000:
            text = (
                "Very low: near-infrared. Screen may look near-black; "
                "Windows will clamp this ramp unless the full-range unlock "
                "is applied (see README)."
            )
        elif kelvin < 3700:
            text = (
                "Low: below ~3700 K Windows silently clamps the ramp. "
                "The tint won't deepen further until the registry unlock "
                "is applied (see README)."
            )
        elif kelvin >= 30000:
            text = (
                "Very high: intense blue tint. Whites, warm colors, and "
                "reds may become hard to read."
            )
        elif kelvin >= 20000:
            text = "High: strong blue tint. Warm colors will look washed out."
        else:
            text = ""
        self._temp_warning_var.set(text)

    def _on_named_selected(self, _event=None) -> None:
        idx = self._named_combo.current()
        if idx < 0:
            return
        star = NAMED_STARS[idx]
        self._select_preset(star)

    def _on_atmosphere_selected(self, _event=None) -> None:
        idx = self._atmosphere_combo.current()
        if idx < 0:
            return
        self._atmosphere_key = ATMOSPHERES[idx].key
        self._update_atmosphere_description()
        self._apply_now()

    def _update_atmosphere_description(self) -> None:
        atmo = next(
            (a for a in ATMOSPHERES if a.key == self._atmosphere_key), ATMOSPHERES[0]
        )
        self._atmosphere_desc_var.set(atmo.description)

    def _atmosphere_name_for_key(self, key: str) -> str:
        for a in ATMOSPHERES:
            if a.key == key:
                return a.name
        return ATMOSPHERES[0].name

    def _on_reset(self) -> None:
        gamma.restore()
        self._temp_var.set(SUN_TEFF)
        self._temp_value_label.config(text=f"{SUN_TEFF} K")
        self._atmosphere_key = DEFAULT_ATMOSPHERE
        self._atmosphere_var.set(self._atmosphere_name_for_key(self._atmosphere_key))
        self._update_atmosphere_description()
        self._select_preset(self._find_preset("G", "V"))

    def _select_preset(self, preset: Preset) -> None:
        self._selected_preset = preset
        self._temp_var.set(preset.teff_k)
        self._temp_value_label.config(text=f"{preset.teff_k} K")
        self._update_temp_warning()
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
        rgb = spectrum.rgb_scale_for_temperature(kelvin, self._atmosphere_key)
        gamma.apply(rgb)
        self._schedule_save(kelvin)

    def _schedule_save(self, kelvin: float) -> None:
        if self._pending_save is not None:
            self.root.after_cancel(self._pending_save)
        atmosphere_key = self._atmosphere_key
        self._pending_save = self.root.after(
            SAVE_DEBOUNCE_MS,
            lambda: settings.save(kelvin, atmosphere_key),
        )

    def _restore_state_or_default_to_sun(self) -> None:
        loaded = settings.load()
        if loaded is None:
            self._select_preset(self._find_preset("G", "V"))
            return
        # Guard against a hand-edited or stale state file.
        temp_k = max(MIN_KELVIN, min(MAX_KELVIN, loaded.temperature_k))
        atmo = spectrum.get_atmosphere(loaded.atmosphere_key)
        self._atmosphere_key = atmo.key
        self._atmosphere_var.set(self._atmosphere_name_for_key(self._atmosphere_key))
        self._update_atmosphere_description()
        self._temp_var.set(temp_k)
        self._temp_value_label.config(text=f"{int(temp_k)} K")
        self._update_temp_warning()
        # Match a named-star / preset if the temperature lines up exactly.
        matched = next(
            (p for p in (*PRESETS, *NAMED_STARS) if p.teff_k == int(temp_k)),
            None,
        )
        if matched is not None:
            self._select_preset(matched)
        else:
            self._named_var.set("")
            self._apply_now()

    def _schedule_keep_alive(self) -> None:
        # Windows resets the gamma ramp across sleep/wake and lock/unlock.
        # A cheap idempotent re-apply every few seconds keeps our tint stuck.
        self._keep_alive_task = self.root.after(
            KEEP_ALIVE_MS, self._tick_keep_alive
        )

    def _tick_keep_alive(self) -> None:
        if gamma.is_supported():
            kelvin = self._temp_var.get()
            rgb = spectrum.rgb_scale_for_temperature(kelvin, self._atmosphere_key)
            gamma.apply(rgb)
        self._schedule_keep_alive()

    def _on_autostart_toggle(self) -> None:
        wanted = bool(self._autostart_var.get())
        ok = autostart.enable() if wanted else autostart.disable()
        # If the registry write failed, revert the checkbox to what it truly is.
        actual = autostart.is_enabled()
        if not ok or actual != wanted:
            self._autostart_var.set(actual)
        # Push the checkmark change into the tray menu immediately.
        if self._tray_icon is not None:
            try:
                self._tray_icon.update_menu()
            except Exception:
                pass

    # --- Tray, shutdown, degraded mode -----------------------------------

    def _start_tray(self) -> None:
        icon = _icon_path()
        if icon is None:
            return
        try:
            from starlight_filter import tray
        except ImportError:
            return  # pystray/Pillow not installed — degrade to old close-quits.
        self._tray_icon = tray.start_tray(
            icon_path=icon,
            schedule=lambda cb: self.root.after(0, cb),
            on_show=self.show_window,
            on_reset=self._on_reset,
            on_toggle_autostart=self._tray_toggle_autostart,
            autostart_is_enabled=autostart.is_enabled,
            on_quit=self._quit_app,
        )

    def _tray_toggle_autostart(self) -> None:
        # Flip the checkbox variable, then re-use the same handler so the UI
        # and registry stay in sync.
        self._autostart_var.set(not autostart.is_enabled())
        self._on_autostart_toggle()

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _wire_shutdown(self) -> None:
        atexit.register(gamma.restore)
        # Closing the window hides to tray instead of quitting.
        self.root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
        try:
            signal.signal(signal.SIGINT, lambda *_: self._quit_app())
        except (ValueError, OSError):
            # SIGINT can't always be set from a non-main thread; harmless.
            pass

    def _hide_to_tray(self) -> None:
        # If pystray never came up, closing the window has to actually quit
        # or the process becomes an invisible zombie.
        if self._tray_icon is None:
            self._quit_app()
            return
        self.root.withdraw()

    def _quit_app(self) -> None:
        try:
            gamma.restore()
        finally:
            if self._tray_icon is not None:
                try:
                    self._tray_icon.stop()
                except Exception:
                    pass
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
    if not single_instance.acquire():
        # Another copy is already running — leave it alone.
        return

    start_minimized = "--minimized" in sys.argv[1:]

    gamma.set_app_user_model_id(APP_ID)
    gamma.capture_original()
    root = tk.Tk()
    try:
        app = StarlightFilterApp(root)
        if start_minimized:
            root.withdraw()
        root.mainloop()
    except Exception:
        gamma.restore()
        raise
    finally:
        gamma.restore()


if __name__ == "__main__":
    main()
