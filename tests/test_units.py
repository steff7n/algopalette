"""Przeliczanie progów zasad i zależności przy zmianie metryki kontrastu albo metody ΔE."""

from dataclasses import replace

import pytest

from algopalette.globals_logic import change_delta_e, change_metric
from algopalette.model import (
    Band,
    ChromaBand,
    ContrastBound,
    HueArc,
    Interval,
    Relation,
    Rule,
    SlotRules,
    default_session,
    with_slot,
)
from algopalette.units import (
    DE_SCALE,
    convert_contrast,
    convert_de,
    default_distance,
    rescale_contrast_metric,
    rescale_delta_e,
)


def session():
    s = default_session()
    a, b, c = s.slots[2:5]
    rules = SlotRules(
        lightness=Rule(Band(0.6, 0.85, exclude=((0.70, 0.74),))),
        chroma=Rule(ChromaBand("abs", 0.06, 0.2, exclude=((0.1, 0.12),))),
        hue=Rule(HueArc(0.0, 270.0, exclude=((60.0, 85.0),))),
        contrast_bg=Rule(ContrastBound(None, 4.5, 7.0), hard=False, weight=2.0),
        min_distance=Rule(0.08, hard=False),
        cvd_min_distance=Rule(0.04, enabled=False),
        extreme=Rule("weakest"),
    )
    rels = (
        Relation("contrast", b.id, "ge", 4.5, tol=0.5),
        Relation("contrast", b.id, "ge", 4.5, metric="wcag21"),
        Relation("distance", b.id, "ge", 0.08, tol=0.01),
        Relation("distance", b.id, "ge", 0.08, metric="ok"),
        Relation("hue", c.id, "eq", 180.0, tol=15.0),
    )
    s = with_slot(s, replace(a, rules=rules, relations=rels))
    own_metric = replace(b.rules, contrast_bg=Rule(ContrastBound("wcag21", 4.5, None)))
    s = with_slot(s, replace(b, rules=own_metric))
    g = replace(s.globals, lightness_spread=Rule(Interval(None, 0.12)), avoid_distance=0.05)
    return replace(s, globals=g)


def test_conversion_tables():
    assert convert_contrast(4.5, "wcag21", "apca") == pytest.approx(60.0)
    assert convert_contrast(7.0, "wcag21", "apca") == pytest.approx(75.0)
    assert convert_contrast(60.0, "apca", "wcag21") == pytest.approx(4.5)
    assert convert_contrast(5.0, "apca", "apca") == 5.0
    assert convert_de(0.08, "ok", "2000") == pytest.approx(0.08 * DE_SCALE["2000"])
    assert convert_de(0.08, "ok", "2000") == pytest.approx(12.48)
    assert default_distance("hyab", 0.08) == pytest.approx(0.104)


def test_rescale_contrast_metric_touches_rules_and_relations():
    s = session()
    out = rescale_contrast_metric(s, "wcag21", "apca")
    a, b = out.slots[2], out.slots[3]
    assert a.rules.contrast_bg == Rule(ContrastBound(None, 60.0, 75.0), hard=False, weight=2.0)
    assert b.rules.contrast_bg == Rule(ContrastBound("wcag21", 4.5, None))  # własna metryka
    assert out.slots[1].rules.contrast_bg == Rule(ContrastBound(None, 75.0, None))  # tekst
    assert out.slots[5].rules.contrast_bg == Rule(ContrastBound(None, 60.0, None))
    r0, r1 = a.relations[0], a.relations[1]
    assert r0.value == pytest.approx(60.0)
    assert r0.tol == pytest.approx(4.0)  # 4.0–5.0 WCAG → 55–63 Lc
    assert r1 == s.slots[2].relations[1]
    assert a.relations[2:] == s.slots[2].relations[2:]
    # zasady L/C/H, zakazy i progi odległości bez zmian
    for name in ("lightness", "chroma", "hue", "min_distance", "cvd_min_distance", "extreme"):
        assert getattr(a.rules, name) == getattr(s.slots[2].rules, name)
    assert out.globals == s.globals
    assert rescale_contrast_metric(s, "apca", "apca") is s


def test_rescale_delta_e_touches_rules_and_relations():
    s = session()
    out = rescale_delta_e(s, "ok", "2000")
    assert out.globals.delta_e == "2000"
    a = out.slots[2]
    assert a.rules.min_distance == Rule(pytest.approx(12.48), hard=False)
    assert a.rules.cvd_min_distance == Rule(pytest.approx(6.24), enabled=False)
    assert out.slots[5].rules.min_distance == Rule(pytest.approx(12.48), hard=False)
    assert a.relations[2].value == pytest.approx(12.48)
    assert a.relations[2].tol == pytest.approx(1.56)
    assert a.relations[3] == s.slots[2].relations[3]  # własna metoda
    assert a.relations[:2] == s.slots[2].relations[:2]
    for name in ("lightness", "chroma", "hue", "contrast_bg", "extreme"):
        assert getattr(a.rules, name) == getattr(s.slots[2].rules, name)
    assert out.globals.avoid_distance == 0.05  # zawsze ΔE ok
    assert out.globals.lightness_spread == s.globals.lightness_spread
    assert rescale_delta_e(s, "ok", "ok") is s


def test_change_metric_sets_metric_and_rescales():
    s = session()
    out = change_metric(s, "apca")
    assert out.globals.contrast_metric == "apca"
    assert out.slots[2].rules.contrast_bg == Rule(
        ContrastBound(None, 60.0, 75.0), hard=False, weight=2.0
    )
    assert out.preset == s.preset
    assert change_metric(s, "wcag21") == s
    back = change_metric(out, "wcag21")
    assert back.slots[2].rules.contrast_bg == s.slots[2].rules.contrast_bg


def test_change_delta_e_sets_method_and_rescales():
    s = session()
    out = change_delta_e(s, "hyab")
    assert out.globals.delta_e == "hyab"
    assert out.slots[2].rules.min_distance == Rule(pytest.approx(0.104), hard=False)
    assert change_delta_e(s, "ok") == s
