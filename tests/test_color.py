"""Testy warstwy koloru: APCA, kontrast, gamut, fit, parsowanie."""

import random

import pytest
from pytest import approx

from algopalette.color import (
    Color,
    apca_signed,
    contrast,
    contrast_hex,
    delta_e,
    fit_delta,
    from_css,
    hue_diff,
    in_gamut,
    max_chroma,
    simulate_cvd,
    to_hex,
)
from algopalette.model import OKLCH


def test_apca_vectors():
    assert contrast_hex("#888888", "#ffffff", "apca") == approx(63.06, abs=0.1)  # |Lc|
    assert apca_signed("#ffffff", "#888888") == approx(-68.54, abs=0.1)
    assert apca_signed("#000000", "#aaaaaa") == approx(58.15, abs=0.1)
    assert apca_signed("#aaaaaa", "#000000") == approx(-56.24, abs=0.1)


def test_apca_plugin_registered_only_on_subclass():
    assert "apca" in Color.CONTRAST_MAP
    from coloraide.everything import ColorAll

    assert "apca" not in ColorAll.CONTRAST_MAP


def test_apca_identical_colors_zero():
    assert contrast_hex("#777777", "#777777", "apca") == 0.0


def test_wcag_black_white():
    assert contrast(from_css("#000"), from_css("#fff"), "wcag21") == approx(21.0)


def test_red_roundtrip():
    assert to_hex(OKLCH(0.62796, 0.25768, 29.2339), "clip") == "#ff0000"


def test_max_chroma_boundary():
    rng = random.Random(1)
    for _ in range(50):
        l, h = rng.uniform(0.05, 0.95), rng.uniform(0.0, 360.0)
        m = max_chroma(l, h)
        assert in_gamut(OKLCH(l, m * 0.999, h))
        assert not in_gamut(OKLCH(l, m * 1.01 + 1e-4, h))


def test_fit_delta_out_of_gamut():
    c = OKLCH(0.75, 0.30, 140)  # brief miał C=0.25, ale max C(0.75, 140)=0.2414: ΔE ≈ 0.006
    assert fit_delta(c, "oklch-chroma") > 0.01
    assert to_hex(c, "oklch-chroma").startswith("#")
    assert fit_delta(OKLCH(0.5, 0.05, 200), "clip") == 0.0


@pytest.mark.parametrize(
    "method", ["clip", "minde-chroma", "lch-chroma", "oklch-chroma", "raytrace", "scale"]
)
def test_all_fit_methods_give_valid_hex(method):
    h = to_hex(OKLCH(0.8, 0.35, 330), method)
    assert len(h) == 7
    assert fit_delta(OKLCH(0.8, 0.35, 330), method) >= 0.0


def test_hue_diff():
    assert hue_diff(350, 10) == approx(20)
    assert hue_diff(10, 350) == approx(-20)
    assert hue_diff(0, 180) == approx(180)


def test_from_css():
    assert from_css("oklch(70% 0.1 200deg)") == from_css("oklch(0.7 0.1 200)")
    with pytest.raises(ValueError, match="#ggg"):
        from_css("#ggg")


def test_from_css_gray_is_clean_and_hex_roundtrips():
    gray = from_css("#808080")
    assert gray.c == 0.0
    assert 0.0 <= gray.h < 360.0
    assert to_hex(from_css("#1e90ff"), "clip") == "#1e90ff"


def test_from_css_out_of_gamut_oklch_is_kept():
    c = from_css("oklch(0.75 0.4 140)")
    assert c.c == approx(0.4)
    assert not in_gamut(c)


def test_delta_e_and_cvd_smoke():
    a, b = from_css("#ff0000"), from_css("#00ff00")
    for method in ("ok", "2000", "hyab", "itp", "cam16"):
        assert delta_e(a, b, method) > 0.0
        assert delta_e(a, a, method) == approx(0.0, abs=1e-9)
    sim = simulate_cvd(a, "deutan", "machado", 1.0)
    assert sim != a
    assert simulate_cvd(a, "deutan", "machado", 0.0).l == approx(a.l, abs=1e-6)


def test_hsl_roundtrip():
    from algopalette.color import from_hsl, to_hsl

    c = from_css("#d49648")
    h, s, l_ = to_hsl(c, "clip")
    assert (h, s, l_) == (
        pytest.approx(33.43, abs=0.01),
        pytest.approx(61.95, abs=0.01),
        pytest.approx(55.69, abs=0.01),
    )
    assert to_hex(from_hsl(h, s, l_), "clip") == "#d49648"
    assert to_hsl(from_css("#808080"), "clip")[1] == pytest.approx(
        0.0, abs=1e-6
    )  # szarość: S = 0, H = 0
