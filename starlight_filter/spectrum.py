"""Pure math and preset data — no I/O, no Windows calls. Runs on any OS."""

from __future__ import annotations

import math
from dataclasses import dataclass


REFERENCE_KELVIN = 6500.0
MIN_KELVIN = 1000.0
MAX_KELVIN = 40000.0


@dataclass(frozen=True)
class Preset:
    class_letter: str        # "O".."M"
    luminosity: str          # "V" (dwarf) or "III" (giant)
    name: str                # display name
    short_label: str         # <=4 chars for the button face
    teff_k: int              # effective temperature in kelvin
    notes: str = ""


PRESETS: list[Preset] = [
    # Dwarfs (luminosity class V)
    Preset("O", "V", "10 Lacertae",       "10L",  36000, "Canonical O9 V spectral standard."),
    Preset("B", "V", "Achernar",          "Ach",  15000, "B6 Vpe rapid rotator; photospheric Teff."),
    Preset("A", "V", "Vega",              "Veg",   9600, "A0 V spectral standard."),
    Preset("F", "V", "Procyon",           "Pro",   6530, "F5 IV-V."),
    Preset("G", "V", "Sun",               "Sun",   5778, "G2 V — default at launch."),
    Preset("K", "V", "Epsilon Eridani",   "εEri",  5080, "K2 V."),
    Preset("M", "V", "Proxima Centauri",  "Prox",  3040, "M5.5 Ve — nearest star."),
    # Giants (luminosity class III)
    Preset("O", "III", "Meissa",          "Mei",  35000, "λ Orionis A, O8 III."),
    Preset("B", "III", "Bellatrix",       "Bel",  22000, "γ Orionis, B2 III."),
    Preset("A", "III", "Thuban",          "Thu",   9750, "α Draconis, A0 III."),
    Preset("F", "III", "Caph",            "Cph",   7080, "β Cassiopeiae, F2 III-IV."),
    Preset("G", "III", "Capella Aa",      "Cap",   4970, "α Aurigae Aa, G8 III."),
    Preset("K", "III", "Arcturus",        "Arc",   4290, "α Boötis, K1.5 III."),
    Preset("M", "III", "Gacrux",          "Gac",   3690, "γ Crucis, M3.5 III."),
]


# Extra famous stars for the "More named stars" dropdown. Kept separate from
# PRESETS so the 2x7 button grid stays a clean spectral-class matrix. Sorted
# hot -> cool so the dropdown mirrors the temperature slider.
NAMED_STARS: list[Preset] = [
    Preset("B", "III", "Spica",             "", 25300, "α Virginis Aa, B1 III-IV."),
    Preset("B", "V",   "Regulus",           "", 12460, "α Leonis A, B8 IVn."),
    Preset("B", "I",   "Rigel",             "", 12100, "β Orionis Aa, B8 Ia supergiant."),
    Preset("A", "V",   "Sirius A",          "",  9940, "α Canis Majoris A, A1 V — brightest night-sky star."),
    Preset("A", "V",   "Fomalhaut",         "",  8590, "α Piscis Austrini A, A3 V."),
    Preset("A", "I",   "Deneb",             "",  8525, "α Cygni, A2 Ia supergiant."),
    Preset("A", "V",   "Altair",            "",  7550, "α Aquilae, A7 V."),
    Preset("A", "II",  "Canopus",           "",  7350, "α Carinae, A9 II bright giant."),
    Preset("F", "I",   "Polaris",           "",  6015, "α Ursae Minoris Aa, F7 Ib supergiant — the North Star."),
    Preset("G", "V",   "Alpha Centauri A",  "",  5790, "α Centauri A, G2 V — Sun's near-twin."),
    Preset("K", "III", "Pollux",            "",  4666, "β Geminorum, K0 III."),
    Preset("K", "III", "Aldebaran",         "",  3910, "α Tauri, K5 III."),
    Preset("M", "I",   "Antares",           "",  3660, "α Scorpii A, M1.5 Iab supergiant."),
    Preset("M", "I",   "Betelgeuse",        "",  3600, "α Orionis, M1-2 Ia-Iab supergiant."),
    Preset("M", "V",   "Barnard's Star",    "",  3134, "M4 V — highest known proper motion."),
    Preset("M", "V",   "Trappist-1",        "",  2566, "M8 V ultracool dwarf; hosts 7 known planets."),
]


def _kelvin_to_rgb_255(kelvin: float) -> tuple[float, float, float]:
    """Tanner Helland's blackbody approximation. Returns each channel in [0, 255]."""
    kelvin = max(MIN_KELVIN, min(MAX_KELVIN, kelvin))
    temp = kelvin / 100.0

    if temp <= 66.0:
        r = 255.0
    else:
        r = 329.698727446 * ((temp - 60.0) ** -0.1332047592)

    if temp <= 66.0:
        g = 99.4708025861 * math.log(temp) - 161.1195681661
    else:
        g = 288.1221695283 * ((temp - 60.0) ** -0.0755148492)

    if temp >= 66.0:
        b = 255.0
    elif temp <= 19.0:
        b = 0.0
    else:
        b = 138.5177312231 * math.log(temp - 10.0) - 305.0447927307

    return (
        max(0.0, min(255.0, r)),
        max(0.0, min(255.0, g)),
        max(0.0, min(255.0, b)),
    )


def rgb_scale_for_temperature(kelvin: float) -> tuple[float, float, float]:
    """Convert a target color temperature to (r, g, b) gamma-ramp scale factors.

    Normalized so the largest channel is 1.0 — we never boost, only attenuate.
    At the reference 6500 K this returns approximately (1.0, 1.0, 1.0).
    """
    r, g, b = _kelvin_to_rgb_255(kelvin)
    m = max(r, g, b)
    if m <= 0.0:
        return (0.0, 0.0, 0.0)
    return (r / m, g / m, b / m)


def apply_blue_reduction(
    rgb: tuple[float, float, float], amount: float
) -> tuple[float, float, float]:
    """Attenuate the blue channel by `amount` in [0.0, 1.0]."""
    amount = max(0.0, min(1.0, amount))
    r, g, b = rgb
    return (r, g, b * (1.0 - amount))
