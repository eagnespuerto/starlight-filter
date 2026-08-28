# Starlight Filter — Design Spec

**Date:** 2026-08-27
**Status:** Approved for implementation

## Summary

A single-window Windows applet that shifts the display's white point to match a chosen star, using the Windows gamma-ramp API. The user picks a spectral class (with dwarf/giant subtype) or a preset star; the monitor emits light "as if" from that star's photosphere. A separate slider adds optional blue-light reduction on top. A Reset button restores the gamma ramp that was in effect when the app opened.

Ships as both a runnable Python package and a standalone Windows `.exe` built with PyInstaller.

## Goals

- Make the display's white point a fun, physically-motivated stellar choice.
- Never leave the user with a broken gamma ramp — restoration on every exit path.
- Zero runtime dependencies beyond the Python standard library.
- Ship a double-clickable `.exe` so non-Python users can run it.

## Non-goals

- HDR-aware color management. If the display's driver refuses `SetDeviceGammaRamp`, we surface the failure and disable controls; we do not fall back to an overlay.
- Multi-monitor per-display control. Version 1 applies to the primary display device context; extending later is straightforward but out of scope.
- Persisting user settings across launches. Every launch starts at the Sun preset.

## Architecture

Three small modules, each with one job:

### `starlight_filter/gamma.py`
Thin `ctypes` wrapper over the Win32 gamma API. Owns the original ramp captured at startup.

Public surface:
- `capture_original() -> None` — reads and stores the current gamma ramp via `GetDeviceGammaRamp` on the primary display DC.
- `apply(rgb_scale: tuple[float, float, float]) -> None` — multiplies the captured original ramp by the given (r, g, b) scale factors (each in [0, 1]) and pushes via `SetDeviceGammaRamp`. Clamps to `[0, 65535]` per WORD entry.
- `restore() -> None` — pushes the captured original ramp back unchanged.
- `is_supported() -> bool` — returns whether the initial capture succeeded.

The module hides all `ctypes`, `windll`, and HDC handling. Nothing else in the codebase imports `ctypes`.

### `starlight_filter/spectrum.py`
Pure math and preset data. No I/O, no Windows calls — runs on any OS.

Public surface:
- `rgb_scale_for_temperature(kelvin: float) -> tuple[float, float, float]` — converts a target color temperature (1000–40000 K) into (r, g, b) scale factors relative to a 6500 K reference white. Integrates Planck's Law against the CIE 1931 2° standard-observer color matching functions to get CIE XYZ, then transforms to sRGB via the standard D65 matrix and encodes with the sRGB transfer function. Returns each channel in [0, 1].
- `apply_blue_reduction(rgb: tuple, amount: float) -> tuple` — attenuates the blue channel by `amount` (0.0–1.0) after the temperature transform.
- `PRESETS: list[Preset]` — the 14-entry star table (see below).

`Preset` is a small dataclass: `class_letter`, `luminosity` (`"V"` or `"III"`), `name`, `short_label`, `teff_k`, `notes`.

### `starlight_filter/app.py`
Tkinter UI. Wires sliders/buttons to the two modules. Contains no math and no Windows calls.

Responsibilities:
- Build the window, preset grid, sliders, Reset/Apply buttons.
- Debounce slider drags (~30 Hz cap) before calling `gamma.apply`.
- Register `atexit.register(gamma.restore)` and bind `WM_DELETE_WINDOW` to a clean shutdown that also calls `gamma.restore`.
- Handle `SIGINT` (Ctrl-C in a console launch) with the same shutdown path.
- If `gamma.is_supported()` is false, show a modal explaining the display doesn't support gamma-ramp control and disable the sliders/presets (Reset stays disabled too — nothing to restore).

### Entry points
- `python -m starlight_filter` (via `__main__.py` calling `app.main()`).
- `run.py` shim at repo root for direct `python run.py`.
- Built `.exe` (see Packaging).

## Star preset table

| Class | Dwarf (V)         | Teff (K) | Giant (III)              | Teff (K) |
|-------|-------------------|----------|--------------------------|----------|
| O     | 10 Lacertae       | 36,000   | Meissa (λ Ori)           | 35,000   |
| B     | Achernar          | 15,000   | Bellatrix                | 22,000   |
| A     | Vega              | 9,600    | Thuban                   | 9,750    |
| F     | Procyon           | 6,530    | Caph                     | 7,080    |
| G     | Sun               | 5,778    | Capella Aa               | 4,970    |
| K     | Epsilon Eridani   | 5,080    | Arcturus                 | 4,290    |
| M     | Proxima Centauri  | 3,040    | Gacrux                   | 3,690    |

Notes:
- O V uses 10 Lacertae because it is the canonical O9 V spectral standard; no O-class dwarf is a naked-eye star.
- The "giant" row uses luminosity class III (proper giants) throughout, not supergiants, for internal consistency. This means the visually iconic red supergiant Betelgeuse and blue supergiant Rigel are intentionally *not* included; Gacrux and Bellatrix are their class-III analogues.
- Achernar is technically B6 Vpe (rapid rotator, emission); listed at its representative photospheric Teff.
- Sun stays as the default selection at launch.

## UI

Single non-resizable window, ~460 × 360 px.

```
┌─ Starlight Filter ────────────────────────────────────┐
│                                                        │
│                O    B    A    F    G    K    M         │
│  Dwarf  (V)  [10L][Ach][Veg][Pro][●Sun][εEri][Prox]    │
│  Giant (III) [Mei][Bel][Thu][Cph][Cap][Arc][Gac]       │
│                                                        │
│  Color temperature                       5778 K        │
│  ├──────────────●────────────────────────────┤         │
│  1000 K                                40000 K         │
│                                                        │
│  Blue-light reduction                       0 %        │
│  ├●───────────────────────────────────────────┤        │
│  0 %                                      100 %        │
│                                                        │
│                                [ Reset ]  [ Apply ]    │
└────────────────────────────────────────────────────────┘
```

- Preset buttons: 3-letter labels; hover tooltip shows full name, luminosity class, and Teff.
- Temperature slider: 1000–40000 K, live-updates during drag (throttled).
- Blue-light slider: 0–100%, applied after the temperature transform.
- Reset: reapplies the captured original ramp. Does not close the app. Also resets both sliders to Sun defaults and re-highlights the Sun preset.
- Apply: exists for keyboard/accessibility parity; drag already applies live.

## Reset & safety invariants

- On startup: `gamma.capture_original()` runs before any UI is shown. If it fails, the app enters degraded mode with a modal explanation.
- On every exit path — `WM_DELETE_WINDOW`, `SIGINT`, `atexit`, unhandled exception in the Tk mainloop — the original ramp is restored. This is the one non-negotiable invariant.
- If `SetDeviceGammaRamp` returns false during a live update, the app logs it and keeps the last-known-good ramp; it does not attempt to apply again until the user moves a control.

## Testing

- `tests/test_spectrum.py` — pure-math tests, run on any OS in CI:
  - 6500 K → (1.0, 1.0, 1.0) within tolerance.
  - Monotonicity: hotter → higher blue/red ratio; cooler → lower.
  - Every entry in `PRESETS` maps to RGB in [0, 1] and produces the expected qualitative shift (M-class warmer than Sun, O-class cooler).
  - Blue-reduction: `apply_blue_reduction(x, 0)` is identity; `apply_blue_reduction(x, 1)` zeroes blue.
- No unit tests for `gamma.py` or `app.py` — they are thin adapters over Win32 and Tk. Risk is concentrated in `spectrum.py`.
- Manual smoke test on Windows, documented in the README: launch → cycle presets → confirm visible shift → hit Reset → close window → confirm original ramp restored (visually, and via a fresh launch showing the ramp is untouched).

## Packaging (.exe)

Build with **PyInstaller**, single-file mode, windowed (no console).

- `build.py` at repo root drives the build:
  - Verifies PyInstaller is installed (install into a local venv on demand; do not touch system Python).
  - Runs `pyinstaller --onefile --windowed --name StarlightFilter --icon assets/icon.ico run.py`.
  - Copies the resulting `dist/StarlightFilter.exe` to `dist/` at repo root.
- Icon: a small SVG-derived `.ico` at `assets/icon.ico`. A minimal placeholder ships in v1; nicer art can land later.
- No code signing in v1. Users will see the SmartScreen "unrecognized app" prompt; the README documents "More info → Run anyway".
- `dist/`, `build/`, and `*.spec` are `.gitignore`d; the built `.exe` is not committed. GitHub Releases is the distribution channel later; v1 just documents the build command.

## Repo layout

```
starlight-filter/
  README.md
  LICENSE                              (MIT)
  pyproject.toml                       (name, version, entry point; no runtime deps)
  .gitignore                           (dist/, build/, *.spec, __pycache__/, .venv/)
  run.py                               (module shim: from starlight_filter.app import main; main())
  build.py                             (PyInstaller driver)
  assets/
    icon.ico                           (placeholder)
  starlight_filter/
    __init__.py
    __main__.py
    app.py
    gamma.py
    spectrum.py
  tests/
    test_spectrum.py
  docs/superpowers/specs/
    2026-08-27-starlight-filter-design.md
```

## Out of scope for v1

- Persisting settings across launches.
- Multi-monitor per-display control.
- HDR / DisplayCAL / ICC profile awareness.
- Scheduled sunset-to-sunrise automation (f.lux-style).
- Code signing the `.exe`.
- Custom user-defined presets.
