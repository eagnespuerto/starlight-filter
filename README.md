# Starlight Filter

A tiny Windows applet that shifts your monitor's white point to match a chosen star. Pick a spectral class (with dwarf/giant subtype) or a named preset star; the display emits light "as if" from that star's photosphere. Layer on optional blue-light reduction. Hit **Reset** to restore whatever gamma ramp Windows had when the app opened.

## Presets

Fourteen stars, one dwarf (V) and one giant (III) per spectral class O · B · A · F · G · K · M.

| Class | Dwarf (V)         | Teff (K) | Giant (III)              | Teff (K) |
|-------|-------------------|----------|--------------------------|----------|
| O     | 10 Lacertae       | 36,000   | Meissa (λ Ori)           | 35,000   |
| B     | Achernar          | 15,000   | Bellatrix                | 22,000   |
| A     | Vega              | 9,600    | Thuban                   | 9,750    |
| F     | Procyon           | 6,530    | Caph                     | 7,080    |
| G     | **Sun** (default) | 5,778    | Capella Aa               | 4,970    |
| K     | Epsilon Eridani   | 5,080    | Arcturus                 | 4,290    |
| M     | Proxima Centauri  | 3,040    | Gacrux                   | 3,690    |

A separate **More named stars** dropdown holds 28 additional stars sorted hot-to-cool, including four exotic spectral classes that fall outside the O–M main-sequence grid:

- **Wolf-Rayet (WR):** WR 22
- **B–A supergiants and giants:** Spica, Rigel, Deneb, Canopus
- **White dwarf (D):** Sirius B
- **Bright main-sequence:** Regulus, Sirius A, Fomalhaut, Altair, Polaris
- **Sun-like G/K dwarfs:** Alpha Centauri A, Tau Ceti, 40 Eridani A, Toliman (Alpha Centauri B)
- **K/M giants and supergiants:** Pollux, Aldebaran, Antares, Betelgeuse
- **Nearby / notable M dwarfs:** TOI 700, GJ 251, Barnard's Star, GJ 725 B, LHS 1140, Teegarden's Star, Trappist-1
- **L-type brown dwarf:** Luhman 16 A
- **T-type brown dwarf:** Luhman 16 B

The temperature slider spans 1,000 K – 50,000 K to cover the full range from the coolest brown dwarfs to Wolf-Rayet stars. A short warning line appears under the slider at either extreme — flagging cool values Windows will clamp without the registry unlock, and hot values that produce a hard-to-read blue tint.

## Run from source

```bash
pip install -r requirements.txt   # or: pip install pystray Pillow
python run.py
```

Requires Python 3.10+ and two runtime deps: `pystray` and `Pillow` (used for the system-tray icon).

Pass `--minimized` to start hidden in the tray:

```bash
python run.py --minimized
```

## Living in the tray

Closing the main window hides the app to the Windows system tray; the gamma ramp you picked stays applied. Right-click the tray icon for:

- **Show** — bring the main window back
- **Reset gamma** — restore your original ramp without quitting
- **Start with Windows** — writes `HKCU\...\Run\StarlightFilter`, launches the app hidden at sign-in
- **Quit** — restore the original ramp and exit

Only Quit actually stops the process; the original gamma ramp is also restored on any unexpected exit (Ctrl-C, crash, sign-out).

A single-instance guard means launching a second copy silently exits — click the tray icon of the running one instead.

## Build a .exe

```bash
python build.py
```

Installs PyInstaller into the current environment if it isn't already there, then writes `dist/StarlightFilter.exe` — a single-file windowed executable you can double-click.

The `.exe` is unsigned, so Windows SmartScreen will show "Windows protected your PC" the first time you run it. Click **More info → Run anyway**.

## Tests

```bash
python -m pytest tests/
```

Tests cover the pure-math module (`spectrum.py`) and run on any OS. The Win32 gamma wrapper and Tk UI are thin adapters and are tested manually on Windows.

## How it works

- On launch, the app captures the current Windows gamma ramp via `GetDeviceGammaRamp`.
- Choosing a star or moving a slider computes RGB scale factors from the target color temperature (Tanner Helland's blackbody approximation), normalizes them so the largest channel stays at 1.0 (we never boost, only attenuate), applies optional blue-light reduction, and pushes a new ramp via `SetDeviceGammaRamp`.
- On any exit path — closing the window, Ctrl-C, an unhandled exception, or process shutdown — the original ramp is restored.

## Won't work on

- HDR displays while in HDR mode.
- Some color-managed pro displays with drivers that refuse `SetDeviceGammaRamp`.

When gamma-ramp control isn't available, the app shows a dialog and disables the controls rather than pretending to work.

## The Windows blue-channel clamp

Since Windows 7, `SetDeviceGammaRamp` silently discards any ramp that deviates more than about half-scale from linear. In practice this means anything cooler than roughly **3700 K** (about the temperature of Gacrux) has no effect: Proxima Centauri, Betelgeuse-style reds, and the low end of the temperature slider will look the same as Gacrux until the clamp is removed.

f.lux, Redshift, and Iris all hit the same wall. The documented unlock is a registry value: `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ICM\GdiIcmGammaRange = 256` (DWORD). This repo ships that as a ready-to-apply file:

```
assets/enable-full-gamma-range.reg
```

Double-click it, approve the UAC prompt, then **sign out and back in** (or reboot). After that, the full 1000 K – 50000 K slider range works.

To revert, double-click the companion file:

```
assets/restore-default-gamma-range.reg
```

Same UAC prompt, same sign-out / sign-in. It just deletes the `GdiIcmGammaRange` value and leaves the ICM key intact.

## License

MIT — see [LICENSE](LICENSE).
