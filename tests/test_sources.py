"""Paleta wyjściowa — parsowanie i trzy tryby (Task 6)."""

from dataclasses import replace

import pytest

from algopalette import color as col
from algopalette.engine import generate
from algopalette.model import OKLCH, default_session
from algopalette.sources import (
    ParseError,
    apply_character,
    apply_complete,
    apply_transfer,
    colors_from_session,
    extract_profile,
    parse_colors,
)

# Ciemna paleta: tło, tekst + 6 akcentów (odcienie 30/35/200/210/120/300).
SRC = [
    OKLCH(0.20, 0.02, 250),
    OKLCH(0.90, 0.01, 250),
    OKLCH(0.72, 0.12, 30),
    OKLCH(0.68, 0.10, 35),
    OKLCH(0.75, 0.10, 200),
    OKLCH(0.70, 0.09, 210),
    OKLCH(0.78, 0.12, 120),
    OKLCH(0.70, 0.12, 300),
]


def _one(s, **opt):
    o = {"n_proposals": 1, **opt}
    return replace(s, globals=replace(s.globals, optimizer=replace(s.globals.optimizer, **o)))


def test_parse_mixed():
    got = parse_colors("#fff, #000000;oklch(0.7 0.1 200)\n oklch(70% 0.1 200deg)")
    assert len(got) == 4
    assert got[2] == got[3]
    assert got[0].l == pytest.approx(1.0)


def test_parse_rgb_with_commas():
    assert len(parse_colors("rgb(10, 20, 30); #abc")) == 2


def test_parse_bad_token():
    with pytest.raises(ParseError) as e:
        parse_colors("#fff zielony")
    assert e.value.token == "zielony"
    assert "zielony" in str(e.value)


def test_parse_limits():
    with pytest.raises(ParseError, match="Najwyżej 16 kolorów"):
        parse_colors(" ".join(["#123456"] * 17))
    with pytest.raises(ParseError, match="Brak"):
        parse_colors("  ,; \n")


def test_complete_locks_in_order():
    s = apply_complete(default_session(), SRC[:4])
    assert [sl.locked for sl in s.slots[:4]] == [True] * 4
    assert [sl.value for sl in s.slots[:4]] == SRC[:4]
    assert not any(sl.locked for sl in s.slots[4:])
    assert len(s.slots) == 10  # nadmiar wolnych slotów zostaje


def test_complete_custom_bg_fg_and_grows():
    many = [OKLCH(0.5 + 0.01 * i, 0.05, 20.0 * i) for i in range(14)]
    s = apply_complete(default_session(), many, bg_index=3, fg_index=0)
    assert s.slots[0].value == many[3]
    assert s.slots[1].value == many[0]
    assert len(s.slots) == 14  # 12 akcentów → dołożone sloty
    assert all(sl.locked for sl in s.slots)


def test_complete_then_generate_keeps_locks():
    s = _one(apply_complete(default_session(), SRC[:3]))
    p = generate(s)[0]
    for i in range(3):
        assert p.values[s.slots[i].id] == SRC[i]


def test_profile_hues():
    prof = extract_profile(SRC)
    for target in (32.0, 205.0):
        assert any(abs(col.hue_diff(h, target)) <= 10 for h in prof.hues)
    assert prof.lightness.lo is not None and prof.lightness.lo >= 0.6
    assert len(prof.contrasts) == 6


def test_character_avoids_source():
    s = apply_character(
        default_session(), extract_profile(SRC), avoid_source=True, avoid_distance=0.05
    )
    assert s.globals.hue_scheme.kind == "custom"
    p = generate(_one(s))[0]
    assert p.ok, p.violations
    for sl in s.slots[2:]:
        v = p.values[sl.id]
        assert all(col.delta_e(v, src, "ok") >= 0.05 - 1e-6 for src in SRC[2:])


def test_transfer_dark_to_light():
    s = apply_transfer(default_session(), SRC, polarity="light")
    assert len(s.slots) == 8
    p = generate(_one(s))[0]
    assert p.ok, p.violations
    bg = p.values[s.slots[0].id]
    assert bg.l >= 0.9
    for k, src in enumerate(SRC[2:]):
        v = p.values[s.slots[2 + k].id]
        assert abs(col.hue_diff(v.h, src.h)) <= 10
        c_src = col.contrast(src, SRC[0], "wcag21")
        assert abs(col.contrast(v, bg, "wcag21") - c_src) <= 0.5 + 1e-6


def test_session_as_source():
    s = default_session()
    assert colors_from_session(s) == [sl.value for sl in s.slots]


def test_bad_indices():
    with pytest.raises(ParseError):
        apply_complete(default_session(), SRC, bg_index=1, fg_index=1)
    with pytest.raises(ParseError):
        apply_complete(default_session(), SRC, bg_index=99)
