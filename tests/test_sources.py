"""Paleta wyjściowa — parsowanie i trzy tryby na modelu v2 (zasady per kolor)."""

from dataclasses import replace

import numpy as np
import pytest

from algopalette import color as col
from algopalette.model import (
    OKLCH,
    Band,
    ChromaBand,
    ContrastBound,
    HueArc,
    Relation,
    Rule,
    default_rules,
    default_session,
    with_slot,
)
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


def _implemented() -> list[str]:
    try:
        from algopalette import _engine
    except ImportError:
        return []
    return _engine.build_info()["implemented"]


needs_generate = pytest.mark.skipif(
    "generate" not in _implemented(), reason="silnik natywny jeszcze nie generuje"
)


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


def test_complete_leaves_rules_and_preset():
    base = default_session()
    s = apply_complete(base, SRC[:4])
    assert [sl.rules for sl in s.slots] == [sl.rules for sl in base.slots]
    assert s.preset == base.preset
    assert s.globals == base.globals


@needs_generate
def test_complete_then_generate_keeps_locks():
    from algopalette.engine import generate

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


def test_character_writes_rules_of_every_color():
    base = default_session()
    rel = Relation("hue", base.slots[3].id, "eq", 180.0, tol=15.0)
    base = with_slot(base, replace(base.slots[2], locked=True, relations=(rel,)))
    prof = extract_profile(SRC)
    s = apply_character(base, prof)

    assert s.preset is None
    assert s.globals.polarity == "dark"
    assert not any(sl.locked for sl in s.slots)
    assert s.slots[2].relations == (rel,)
    scheme = s.globals.hue_scheme
    assert scheme.tol == 15.0
    # rodziny = skupiska odcieni źródła w kolejności akcentów (nie powielane — akcenty krążą)
    assert sorted(scheme.hues) == pytest.approx(sorted(prof.hues))
    assert s.globals.avoid_colors == ()

    contrasts = [col.contrast(a, SRC[0], "wcag21") for a in SRC[2:]]
    defaults = default_rules("accent", "dark", "wcag21")
    lo, hi = prof.lightness.lo, prof.lightness.hi
    rlo, rhi = prof.rel_chroma.lo, prof.rel_chroma.hi
    assert lo is not None and hi is not None and rlo is not None and rhi is not None
    expected = replace(
        defaults,
        lightness=Rule(Band(max(0.0, lo - 0.03), min(1.0, hi + 0.03))),
        chroma=Rule(ChromaBand("rel", max(0.0, rlo - 0.05), min(1.0, rhi + 0.05))),
        contrast_bg=Rule(ContrastBound(None, float(np.percentile(contrasts, 10)), None)),
    )
    for sl in s.slots[2:]:
        assert sl.rules == expected
        assert sl.rules.hue is None
        assert sl.use_scheme is True

    fg = s.slots[1].rules
    assert fg.contrast_bg == Rule(ContrastBound(None, col.contrast(SRC[1], SRC[0], "wcag21"), None))
    assert fg.lightness == default_rules("fg", "dark", "wcag21").lightness
    bg = s.slots[0].rules
    assert bg.lightness == Rule(Band(0.20 - 0.03, 0.20 + 0.03))
    assert bg.chroma == Rule(ChromaBand("abs", 0.02 - 0.01, 0.02 + 0.01))
    assert bg.hue == Rule(HueArc(230.0, 270.0), hard=False)


def test_character_gray_background_has_no_hue_rule_and_light_polarity():
    src = [OKLCH(0.97, 0.004, 100), *SRC[1:]]
    s = apply_character(default_session(), extract_profile(src), avoid_source=True)
    assert s.globals.polarity == "light"
    assert s.slots[0].rules.hue is None
    assert s.globals.avoid_colors == tuple(src[2:])
    assert s.globals.avoid_distance == 0.05
    assert s.slots[2].rules.min_distance == default_rules("accent", "light", "wcag21").min_distance


@needs_generate
def test_character_avoids_source():
    from algopalette.engine import generate

    s = apply_character(
        default_session(), extract_profile(SRC), avoid_source=True, avoid_distance=0.05
    )
    assert s.globals.hue_scheme.hues
    p = generate(_one(s))[0]
    assert p.ok, p.violations
    for sl in s.slots[2:]:
        v = p.values[sl.id]
        assert all(col.delta_e(v, src, "ok") >= 0.05 - 1e-6 for src in SRC[2:])


def test_transfer_writes_rules_per_accent():
    base = default_session()
    rel = Relation("hue", base.slots[3].id, "eq", 180.0, tol=15.0)
    base = with_slot(base, replace(base.slots[2], locked=True, relations=(rel,)))
    s = apply_transfer(base, SRC, polarity="light")

    assert len(s.slots) == 8  # liczba akcentów = liczba akcentów źródła
    assert s.preset is None
    assert s.globals.polarity == "light"
    assert s.globals.hue_scheme.hues == ()
    assert not any(sl.locked for sl in s.slots)
    defaults = default_rules("accent", "light", "wcag21")
    for k, src in enumerate(SRC[2:]):
        sl = s.slots[2 + k]
        r = sl.rules
        assert sl.use_scheme is False
        assert sl.relations == ()
        assert r.hue == Rule(HueArc((src.h - 8.0) % 360.0, (src.h + 8.0) % 360.0))
        rel_c = src.c / col.max_chroma(src.l, src.h)
        assert r.chroma is not None
        assert r.chroma.value.mode == "rel"
        assert r.chroma.value.lo == pytest.approx(rel_c - 0.08)
        assert r.chroma.value.hi == pytest.approx(rel_c + 0.08)
        c_src = col.contrast(src, SRC[0], "wcag21")
        assert r.contrast_bg == Rule(ContrastBound("wcag21", c_src - 0.5, c_src + 0.5))
        assert r.lightness is not None
        assert r.lightness.enabled is False
        assert r.min_distance == defaults.min_distance
    bg = s.slots[0].rules
    assert bg.lightness == default_rules("bg", "light", "wcag21").lightness
    assert bg.hue == Rule(HueArc(230.0, 270.0), hard=False)
    fg = s.slots[1].rules
    assert fg.hue is None  # tekst źródła ma C < 0.02
    assert fg.contrast_bg is not None
    assert fg.contrast_bg.value.metric == "wcag21"


def test_transfer_gray_accent_has_no_hue_rule_and_shrinks_palette():
    src = [SRC[0], SRC[1], OKLCH(0.7, 0.01, 40.0)]
    s = apply_transfer(default_session(), src, polarity="light", tol=1.0)
    assert len(s.slots) == 3
    r = s.slots[2].rules
    assert r.hue is None
    c_src = col.contrast(src[2], src[0], "wcag21")
    assert r.contrast_bg == Rule(ContrastBound("wcag21", c_src - 1.0, c_src + 1.0))
    with pytest.raises(ValueError, match="Polaryzacja"):
        apply_transfer(default_session(), src, polarity="szara")


@needs_generate
def test_transfer_dark_to_light():
    from algopalette.engine import generate

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
