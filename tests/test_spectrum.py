"""Pure-math tests for spectrum.py. Runs on any OS."""

from __future__ import annotations

import math

import pytest

from starlight_filter.spectrum import (
    ATMOSPHERES,
    DEFAULT_ATMOSPHERE,
    MAX_KELVIN,
    MIN_KELVIN,
    NAMED_STARS,
    PRESETS,
    REFERENCE_KELVIN,
    atmosphere_transmission,
    get_atmosphere,
    rgb_scale_for_temperature,
)


def _in_unit(x: float) -> bool:
    return 0.0 <= x <= 1.0 + 1e-9


def test_reference_temperature_is_near_identity():
    r, g, b = rgb_scale_for_temperature(REFERENCE_KELVIN)
    assert math.isclose(max(r, g, b), 1.0, rel_tol=1e-6)
    # 6500 K should be visually close to neutral: no channel deeply attenuated.
    assert min(r, g, b) > 0.85


def test_channels_stay_in_unit_range_across_full_slider():
    for k in range(int(MIN_KELVIN), int(MAX_KELVIN) + 1, 500):
        r, g, b = rgb_scale_for_temperature(k)
        assert _in_unit(r), f"r out of range at {k}: {r}"
        assert _in_unit(g), f"g out of range at {k}: {g}"
        assert _in_unit(b), f"b out of range at {k}: {b}"


def test_cooler_star_has_less_blue_than_reference():
    _, _, b_cool = rgb_scale_for_temperature(3000)
    _, _, b_ref = rgb_scale_for_temperature(REFERENCE_KELVIN)
    assert b_cool < b_ref


def test_hotter_star_has_less_red_than_reference():
    r_hot, _, _ = rgb_scale_for_temperature(20000)
    r_ref, _, _ = rgb_scale_for_temperature(REFERENCE_KELVIN)
    assert r_hot < r_ref


def test_out_of_range_kelvin_is_clamped_not_crashing():
    # Values below MIN_KELVIN and above MAX_KELVIN should not raise.
    rgb_low = rgb_scale_for_temperature(0)
    rgb_high = rgb_scale_for_temperature(100000)
    for x in (*rgb_low, *rgb_high):
        assert _in_unit(x)


def test_all_14_presets_present_and_covered():
    assert len(PRESETS) == 14
    classes = {"O", "B", "A", "F", "G", "K", "M"}
    for lum in ("V", "III"):
        present = {p.class_letter for p in PRESETS if p.luminosity == lum}
        assert present == classes, f"missing classes for luminosity {lum}: {classes - present}"


def test_sun_is_default_g_dwarf():
    sun = next(p for p in PRESETS if p.class_letter == "G" and p.luminosity == "V")
    assert sun.name == "Sun"
    assert sun.teff_k == 5778


def test_every_preset_produces_valid_rgb():
    for p in PRESETS:
        r, g, b = rgb_scale_for_temperature(p.teff_k)
        assert _in_unit(r) and _in_unit(g) and _in_unit(b)
        assert max(r, g, b) > 0.99  # normalization: at least one channel at max


@pytest.mark.parametrize("class_letter", ["O", "B", "A"])
def test_hot_class_dwarfs_reduce_red(class_letter):
    dwarf = next(
        p for p in PRESETS if p.class_letter == class_letter and p.luminosity == "V"
    )
    r, _, _ = rgb_scale_for_temperature(dwarf.teff_k)
    r_ref, _, _ = rgb_scale_for_temperature(REFERENCE_KELVIN)
    assert r < r_ref


def test_named_stars_are_well_formed_and_sorted_hot_to_cool():
    assert len(NAMED_STARS) >= 10
    seen_names: set[str] = set()
    prev_teff = None
    for star in NAMED_STARS:
        assert star.name and star.name not in seen_names, f"duplicate: {star.name}"
        seen_names.add(star.name)
        assert MIN_KELVIN <= star.teff_k <= MAX_KELVIN
        # Main-sequence O–M plus exotic classes: WR (Wolf-Rayet), D (white
        # dwarf), L and T (ultracool / brown dwarfs).
        assert star.class_letter in {
            "O", "B", "A", "F", "G", "K", "M", "WR", "D", "L", "T",
        }
        if prev_teff is not None:
            assert star.teff_k <= prev_teff, f"{star.name} out of hot->cool order"
        prev_teff = star.teff_k


def test_named_stars_do_not_shadow_class_matrix_entries():
    matrix_names = {p.name for p in PRESETS}
    for star in NAMED_STARS:
        assert star.name not in matrix_names, (
            f"{star.name} already in the class-matrix PRESETS"
        )


def test_every_named_star_produces_valid_rgb():
    for star in NAMED_STARS:
        r, g, b = rgb_scale_for_temperature(star.teff_k)
        assert 0.0 <= r <= 1.0 and 0.0 <= g <= 1.0 and 0.0 <= b <= 1.0
        assert max(r, g, b) > 0.99


@pytest.mark.parametrize("class_letter", ["K", "M"])
def test_cool_class_dwarfs_reduce_blue(class_letter):
    dwarf = next(
        p for p in PRESETS if p.class_letter == class_letter and p.luminosity == "V"
    )
    _, _, b = rgb_scale_for_temperature(dwarf.teff_k)
    _, _, b_ref = rgb_scale_for_temperature(REFERENCE_KELVIN)
    assert b < b_ref


def test_atmosphere_off_is_identity():
    # "off" must be a strict identity so bare-photosphere output is unaffected.
    for lam in (380, 500, 700, 780):
        assert atmosphere_transmission("off", lam) == 1.0
    off = rgb_scale_for_temperature(REFERENCE_KELVIN, "off")
    default = rgb_scale_for_temperature(REFERENCE_KELVIN)
    assert off == default


def test_atmospheres_have_default_and_unique_keys():
    keys = [a.key for a in ATMOSPHERES]
    assert len(keys) == len(set(keys)), "duplicate atmosphere key"
    assert DEFAULT_ATMOSPHERE in keys


def test_get_atmosphere_falls_back_for_unknown():
    fallback = get_atmosphere("does-not-exist")
    assert fallback.key == DEFAULT_ATMOSPHERE
    # None also lands on the default rather than crashing.
    assert get_atmosphere(None).key == DEFAULT_ATMOSPHERE


def test_transmission_stays_in_unit_interval_everywhere():
    for atmo in ATMOSPHERES:
        for lam in range(380, 781, 10):
            t = atmosphere_transmission(atmo.key, lam)
            assert 0.0 <= t <= 1.0, f"{atmo.key} at {lam} nm: {t}"


def test_earth_sunset_reddens_the_sun():
    # A sunset atmosphere must strip blue more aggressively than clear sky.
    r_clear, g_clear, b_clear = rgb_scale_for_temperature(5778, "earth")
    r_set, g_set, b_set = rgb_scale_for_temperature(5778, "earth_sunset")
    assert b_set < b_clear
    # Red should end up dominant (normalization pushes it to 1.0).
    assert r_set >= g_set >= b_set


def test_neptune_methane_kills_red_leaves_blue():
    # Methane absorption should leave blue as the dominant channel.
    r, g, b = rgb_scale_for_temperature(5778, "neptune")
    assert b >= g > r


def test_every_atmosphere_produces_valid_rgb_across_range():
    for atmo in ATMOSPHERES:
        for k in (1500, 3000, 5778, 10000, 30000):
            r, g, b = rgb_scale_for_temperature(k, atmo.key)
            assert _in_unit(r) and _in_unit(g) and _in_unit(b)
            # Normalization contract: at least one channel is at max unless
            # the atmosphere is opaque (none of ours are).
            assert max(r, g, b) > 0.99
