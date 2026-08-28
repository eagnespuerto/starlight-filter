"""Pure math and preset data — no I/O, no Windows calls. Runs on any OS.

Color model: Planck's Law is integrated against the CIE 1931 2° standard
observer to get the true CIE XYZ tristimulus for each blackbody temperature,
then transformed to sRGB via the standard D65 primaries matrix and encoded
with the sRGB transfer function. This replaces the piecewise Tanner Helland
approximation used in v0.2.x with a physics-first path that puts every star
on the Planckian locus.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


REFERENCE_KELVIN = 6500.0
MIN_KELVIN = 1000.0
MAX_KELVIN = 50000.0


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
# hot -> cool so the dropdown mirrors the temperature slider. Includes exotic
# spectral classes (WR, D, L, T) that fall outside the O–M main-sequence grid.
NAMED_STARS: list[Preset] = [
    Preset("WR", "",   "WR 22",                       "", 44700, "WN7h Wolf-Rayet star in Carina; hydrogen-rich."),
    Preset("B",  "III","Spica",                       "", 25300, "α Virginis Aa, B1 III-IV."),
    Preset("D",  "A",  "Sirius B",                    "", 25200, "α Canis Majoris B, DA2 white dwarf."),
    Preset("B",  "V",  "Regulus",                     "", 12460, "α Leonis A, B8 IVn."),
    Preset("B",  "I",  "Rigel",                       "", 12100, "β Orionis Aa, B8 Ia supergiant."),
    Preset("A",  "V",  "Sirius A",                    "",  9940, "α Canis Majoris A, A1 V — brightest night-sky star."),
    Preset("A",  "V",  "Fomalhaut",                   "",  8590, "α Piscis Austrini A, A3 V."),
    Preset("A",  "I",  "Deneb",                       "",  8525, "α Cygni, A2 Ia supergiant."),
    Preset("A",  "V",  "Altair",                      "",  7550, "α Aquilae, A7 V."),
    Preset("A",  "II", "Canopus",                     "",  7350, "α Carinae, A9 II bright giant."),
    Preset("F",  "I",  "Polaris",                     "",  6015, "α Ursae Minoris Aa, F7 Ib supergiant — the North Star."),
    Preset("G",  "V",  "Alpha Centauri A",            "",  5790, "α Centauri A, G2 V — Sun's near-twin."),
    Preset("G",  "V",  "Tau Ceti",                    "",  5344, "τ Ceti, G8 V — nearby sun-like star."),
    Preset("K",  "V",  "40 Eridani A",                "",  5300, "40 Eri A, K0.5 V — triple system 16 ly away."),
    Preset("K",  "V",  "Toliman (Alpha Centauri B)",  "",  5260, "α Centauri B, K1 V — Sun's nearest K dwarf."),
    Preset("K",  "III","Pollux",                      "",  4666, "β Geminorum, K0 III."),
    Preset("K",  "III","Aldebaran",                   "",  3910, "α Tauri, K5 III."),
    Preset("M",  "I",  "Antares",                     "",  3660, "α Scorpii A, M1.5 Iab supergiant."),
    Preset("M",  "I",  "Betelgeuse",                  "",  3600, "α Orionis, M1-2 Ia-Iab supergiant."),
    Preset("M",  "V",  "TOI 700",                     "",  3480, "M2 V — hosts multiple habitable-zone planets."),
    Preset("M",  "V",  "GJ 251",                      "",  3448, "M3 V — hosts a super-Earth candidate."),
    Preset("M",  "V",  "Barnard's Star",              "",  3134, "M4 V — highest known proper motion."),
    Preset("M",  "V",  "GJ 725 B",                    "",  3104, "M3.5 V — companion in the 61 Cyg-like pair 12 ly away."),
    Preset("M",  "V",  "LHS 1140",                    "",  3096, "M4.5 V — hosts a rocky habitable-zone planet."),
    Preset("M",  "V",  "Teegarden's Star",            "",  2904, "M7.0 V — ultracool dwarf 12.5 ly away."),
    Preset("M",  "V",  "Trappist-1",                  "",  2566, "M8 V ultracool dwarf; hosts 7 known planets."),
    Preset("L",  "V",  "Luhman 16 A",                 "",  1310, "L7.5 brown dwarf, closer half of the third-closest system."),
    Preset("T",  "V",  "Luhman 16 B",                 "",  1210, "T0.5 brown dwarf; L/T transition companion of Luhman 16 A."),
]


# CIE 1931 2° standard observer color matching functions, 10 nm sampling from
# 380 to 780 nm (Wyszecki & Stiles, tabulated values). Each row is
# (wavelength_nm, x_bar, y_bar, z_bar).
_CIE_1931_2DEG_CMF: tuple[tuple[float, float, float, float], ...] = (
    (380, 0.001368, 0.000039, 0.006450),
    (390, 0.004243, 0.000120, 0.020050),
    (400, 0.014310, 0.000396, 0.067850),
    (410, 0.043510, 0.001210, 0.207400),
    (420, 0.134380, 0.004000, 0.645600),
    (430, 0.283900, 0.011600, 1.385600),
    (440, 0.348280, 0.023000, 1.747060),
    (450, 0.336200, 0.038000, 1.772110),
    (460, 0.290800, 0.060000, 1.669200),
    (470, 0.195360, 0.090980, 1.287640),
    (480, 0.095640, 0.139020, 0.812950),
    (490, 0.032010, 0.208020, 0.465180),
    (500, 0.004900, 0.323000, 0.272000),
    (510, 0.009300, 0.503000, 0.158200),
    (520, 0.063270, 0.710000, 0.078250),
    (530, 0.165500, 0.862000, 0.042160),
    (540, 0.290400, 0.954000, 0.020300),
    (550, 0.433450, 0.994950, 0.008750),
    (560, 0.594500, 0.995000, 0.003900),
    (570, 0.762100, 0.952000, 0.002100),
    (580, 0.916300, 0.870000, 0.001650),
    (590, 1.026300, 0.757000, 0.001100),
    (600, 1.062200, 0.631000, 0.000800),
    (610, 1.002600, 0.503000, 0.000340),
    (620, 0.854450, 0.381000, 0.000190),
    (630, 0.642400, 0.265000, 0.000050),
    (640, 0.447900, 0.175000, 0.000020),
    (650, 0.283500, 0.107000, 0.000000),
    (660, 0.164900, 0.061000, 0.000000),
    (670, 0.087400, 0.032000, 0.000000),
    (680, 0.046770, 0.017000, 0.000000),
    (690, 0.022700, 0.008210, 0.000000),
    (700, 0.011359, 0.004102, 0.000000),
    (710, 0.005790, 0.002091, 0.000000),
    (720, 0.002899, 0.001047, 0.000000),
    (730, 0.001440, 0.000520, 0.000000),
    (740, 0.000690, 0.000249, 0.000000),
    (750, 0.000332, 0.000120, 0.000000),
    (760, 0.000166, 0.000060, 0.000000),
    (770, 0.000083, 0.000030, 0.000000),
    (780, 0.000042, 0.000015, 0.000000),
)


# Planck's second radiation constant hc/k, expressed in nm·K so we can feed
# wavelengths in nanometers directly.
_C2_NM_K = 1.43877735e7


def _planck_relative_radiance(lam_nm: float, kelvin: float) -> float:
    """Blackbody spectral radiance shape at wavelength lam_nm and temperature K.

    Absolute scale is dropped — only the spectral shape matters, since XYZ is
    normalized to chromaticity downstream.
    """
    exponent = _C2_NM_K / (lam_nm * kelvin)
    # exp overflow guard: at low T the tail below ~380 nm blows up. cap it.
    if exponent > 700.0:
        return 0.0
    return 1.0 / ((lam_nm ** 5) * (math.exp(exponent) - 1.0))


def temperature_to_xyz(kelvin: float) -> tuple[float, float, float]:
    """Integrate Planck × CIE 1931 CMF to get CIE XYZ tristimulus values."""
    kelvin = max(MIN_KELVIN, min(MAX_KELVIN, kelvin))
    x_sum = 0.0
    y_sum = 0.0
    z_sum = 0.0
    for lam, xb, yb, zb in _CIE_1931_2DEG_CMF:
        b = _planck_relative_radiance(lam, kelvin)
        x_sum += b * xb
        y_sum += b * yb
        z_sum += b * zb
    return x_sum, y_sum, z_sum


def chromaticity_xy(kelvin: float) -> tuple[float, float]:
    """CIE 1931 (x, y) chromaticity coordinates on the Planckian locus."""
    x, y, z = temperature_to_xyz(kelvin)
    s = x + y + z
    if s <= 0.0:
        return 0.0, 0.0
    return x / s, y / s


def _xyz_to_linear_srgb(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Standard sRGB (D65) transformation matrix, IEC 61966-2-1."""
    r =  3.2406 * x - 1.5372 * y - 0.4986 * z
    g = -0.9689 * x + 1.8758 * y + 0.0415 * z
    b =  0.0557 * x - 0.2040 * y + 1.0570 * z
    return r, g, b


def _srgb_encode(v: float) -> float:
    """sRGB opto-electronic transfer function (linear light → display code)."""
    if v <= 0.0:
        return 0.0
    if v <= 0.0031308:
        return 12.92 * v
    return 1.055 * (v ** (1.0 / 2.4)) - 0.055


def rgb_scale_for_temperature(kelvin: float) -> tuple[float, float, float]:
    """Convert a target color temperature to (r, g, b) gamma-ramp scale factors.

    Path: Planck's Law → CIE 1931 XYZ → sRGB (D65) matrix → sRGB gamma.
    Normalized so the largest channel is 1.0 — we never boost, only attenuate.
    At the reference 6500 K this returns approximately (1.0, 1.0, 1.0).
    """
    x, y, z = temperature_to_xyz(kelvin)
    s = x + y + z
    if s <= 0.0:
        return 0.0, 0.0, 0.0
    # Normalize to Y=1 so the matrix operates on a unit-brightness stimulus,
    # keeping the pre-gamma linear values in a sensible numeric range.
    x /= y
    z /= y
    y_norm = 1.0

    r_lin, g_lin, b_lin = _xyz_to_linear_srgb(x, y_norm, z)

    # Out-of-gamut components (deep red or deep blue blackbodies) come back
    # negative from the matrix. Clip before the transfer function.
    r_lin = max(0.0, r_lin)
    g_lin = max(0.0, g_lin)
    b_lin = max(0.0, b_lin)

    r = _srgb_encode(r_lin)
    g = _srgb_encode(g_lin)
    b = _srgb_encode(b_lin)

    m = max(r, g, b)
    if m <= 0.0:
        return 0.0, 0.0, 0.0
    return r / m, g / m, b / m
