"""Pure-math tests for spectrum.py. Runs on any OS."""

from __future__ import annotations

import math

import pytest

from starlight_filter.spectrum import (
    MAX_KELVIN,
    MIN_KELVIN,
    PRESETS,
    REFERENCE_KELVIN,
    apply_blue_reduction,
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


def test_blue_reduction_endpoints():
    rgb = (0.9, 0.8, 0.7)
    assert apply_blue_reduction(rgb, 0.0) == rgb
    r, g, b = apply_blue_reduction(rgb, 1.0)
    assert (r, g) == (0.9, 0.8)
    assert b == 0.0


def test_blue_reduction_is_monotonic():
    rgb = (1.0, 1.0, 1.0)
    prev = 1.0
    for amount in (0.1, 0.25, 0.5, 0.75, 0.9):
        _, _, b = apply_blue_reduction(rgb, amount)
        assert b < prev
        prev = b


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


@pytest.mark.parametrize("class_letter", ["K", "M"])
def test_cool_class_dwarfs_reduce_blue(class_letter):
    dwarf = next(
        p for p in PRESETS if p.class_letter == class_letter and p.luminosity == "V"
    )
    _, _, b = rgb_scale_for_temperature(dwarf.teff_k)
    _, _, b_ref = rgb_scale_for_temperature(REFERENCE_KELVIN)
    assert b < b_ref
