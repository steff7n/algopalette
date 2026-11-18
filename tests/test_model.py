"""Testy modelu sesji v2: zasady per kolor (bez dziedziczenia), łuki odcienia, limity, historia."""

from dataclasses import replace

import pytest

from algopalette.color import contrast, delta_e
from algopalette.model import (
    RULE_FIELDS,
    Band,
    ChromaBand,
    ContrastBound,
    History,
    HueArc,
    OptimizerSettings,
    Relation,
    Rule,
    Session,
    Slot,
    SlotRules,
    add_accent,
    arc_center_half,
    arc_from_center,
    arc_intersection,
    arc_width,
    broken_relations,
    default_rules,
    default_session,
    move_slot,
    remove_slot,
    role_of,
    rule_fields_for,
    with_slot,
)


def test_default_session_shape():
    s = default_session()
    assert len(s.slots) == 10
    assert len({sl.id for sl in s.slots}) == 10
    assert [role_of(i) for i in range(3)] == ["bg", "fg", "accent"]
    g = s.globals
    assert g.polarity == "dark"
    assert not hasattr(g, "role_defaults")
    assert g.hue_scheme.kind == "equal"
    assert (g.contrast_metric, g.delta_e, g.fit_method) == ("wcag21", "ok", "oklch-chroma")
    assert s.preset == "neutralny"
    assert not hasattr(s, "mood")
    bg = s.slots[0].value
    assert bg.l <= 0.25
    assert bg.c <= 0.04
    assert len({sl.value for sl in s.slots}) == 10  # nie wszystkie takie same


def test_default_session_rules_are_role_defaults():
    s = default_session()
    for i, sl in enumerate(s.slots):
        assert sl.rules == default_rules(role_of(i), "dark", "wcag21")
        assert sl.use_scheme is True
        assert sl.relations == ()


def test_default_values_satisfy_defaults():
    s = default_session()
    bg, fg, *accents = (sl.value for sl in s.slots)
    assert contrast(fg, bg, "wcag21") >= 7
    for a in accents:
        assert contrast(a, bg, "wcag21") >= 4.5
    for i, a in enumerate(accents):
        for b in accents[i + 1 :]:
            assert delta_e(a, b, "ok") >= 0.08


def test_default_rules_numbers_match_v1_role_defaults():
    """Liczby jak ``default_role_defaults`` z commita 4b71aeb."""
    tint = Rule(ChromaBand("abs", 0.0, 0.04))
    assert default_rules("bg", "dark", "wcag21") == SlotRules(
        lightness=Rule(Band(0.10, 0.25)), chroma=tint
    )
    assert default_rules("bg", "light", "apca") == SlotRules(
        lightness=Rule(Band(0.93, 0.99)), chroma=tint
    )
    assert default_rules("fg", "dark", "wcag21") == SlotRules(
        lightness=Rule(Band(0.85, 0.98)),
        chroma=tint,
        contrast_bg=Rule(ContrastBound(None, 7.0, None)),
    )
    assert default_rules("fg", "light", "apca") == SlotRules(
        lightness=Rule(Band(0.15, 0.30)),
        chroma=tint,
        contrast_bg=Rule(ContrastBound(None, 75.0, None)),
    )
    assert default_rules("accent", "dark", "wcag21") == SlotRules(
        lightness=Rule(Band(0.60, 0.85)),
        chroma=Rule(ChromaBand("abs", 0.06, 0.20)),
        contrast_bg=Rule(ContrastBound(None, 4.5, None)),
        min_distance=Rule(0.08, hard=False),
    )
    light = default_rules("accent", "light", "apca")
    assert light.lightness == Rule(Band(0.35, 0.60))
    assert light.contrast_bg == Rule(ContrastBound(None, 60.0, None))
    assert light.hue is None
    assert light.extreme is None


def test_rule_fields():
    assert RULE_FIELDS == (
        "lightness",
        "chroma",
        "hue",
        "contrast_bg",
        "min_distance",
        "extreme",
    )
    assert tuple(SlotRules.__dataclass_fields__) == RULE_FIELDS
    assert rule_fields_for("bg") == ("lightness", "chroma", "hue")
    assert rule_fields_for("fg") == ("lightness", "chroma", "hue", "contrast_bg")
    assert rule_fields_for("accent") == RULE_FIELDS


def test_optimizer_defaults():
    o = OptimizerSettings()
    assert (o.n_proposals, o.seed, o.budget, o.time_cap_s) == (6, 0, 3000, 30.0)
    assert (o.min_diversity, o.hard_weight, o.threads) == (0.05, 1000.0, 0)
    assert not hasattr(o, "max_evals")


def test_bands_normalize_exclusions_and_stay_hashable():
    band = Band(0.2, 0.8, exclude=[[0.4, 0.5]])  # ty: ignore[invalid-argument-type]
    assert band.exclude == ((0.4, 0.5),)
    arc = HueArc(0.0, 270.0, exclude=[(60, 85), (140, 155)])  # ty: ignore[invalid-argument-type]
    assert arc.exclude == ((60.0, 85.0), (140.0, 155.0))
    chroma = ChromaBand("rel", 0.2, None, exclude=[(0.5, 0.6)])  # ty: ignore[invalid-argument-type]
    assert isinstance(hash((band, arc, chroma)), int)


@pytest.mark.parametrize(
    ("lo", "hi", "width"),
    [(0, 60, 60), (330, 20, 50), (0, 360, 360), (10, 10, 0), (90, 30, 300), (20, 380, 360)],
)
def test_arc_width(lo, hi, width):
    assert arc_width(lo, hi) == pytest.approx(width)


def test_arc_center_conversions():
    assert arc_from_center(30, 20) == (10, 50)
    assert arc_from_center(350, 20) == (330, 10)
    assert arc_from_center(10, 20) == (350, 30)
    assert arc_from_center(100, 0) == (100, 100)
    assert arc_from_center(100, 180) == (0, 360)
    assert arc_from_center(100, 200) == (0, 360)
    assert arc_center_half(330, 10) == (350, 20)
    assert arc_center_half(10, 50) == (30, 20)
    assert arc_center_half(0, 360) == (180, 180)
    for center, half in [(0.0, 15.0), (359.0, 30.0), (123.5, 0.5), (200.0, 179.0)]:
        got_c, got_h = arc_center_half(*arc_from_center(center, half))
        assert (got_c, got_h) == pytest.approx((center, half))


def test_arc_intersection():
    assert arc_intersection((0, 90), (40, 80)) == [(40, 80)]
    assert arc_intersection((40, 80), (0, 90)) == [(40, 80)]
    assert arc_intersection((0, 60), (190, 210)) == []
    assert arc_intersection((300, 60), (30, 330)) == [(300, 330), (30, 60)]
    assert arc_intersection((330, 20), (350, 40)) == [(350, 20)]
    assert arc_intersection((0, 360), (350, 40)) == [(350, 40)]
    assert arc_intersection((350, 40), (0, 360)) == [(350, 40)]
    assert arc_intersection((0, 60), (60, 120)) == []  # samo dotknięcie to nie część wspólna
    assert arc_intersection((0, 60), (30, 30)) == [(30, 30)]  # łuk zerowy wewnątrz
    assert arc_intersection((0, 60), (90, 90)) == []


def test_accent_limit():
    s = default_session()
    for _ in range(6):
        s = add_accent(s)
    assert len(s.slots) == 16
    assert len({sl.id for sl in s.slots}) == 16
    with pytest.raises(ValueError, match="Najwyżej 14 akcentów"):
        add_accent(s)


def test_new_accent_copies_rules_of_last_accent():
    s = default_session()
    last = s.slots[-1]
    rules = replace(last.rules, hue=Rule(HueArc(0.0, 270.0, exclude=((60.0, 85.0),)), hard=False))
    rel = Relation("hue", s.slots[2].id, "eq", 180.0, tol=15.0)
    s = with_slot(s, replace(last, rules=rules, use_scheme=False, relations=(rel,)))
    s2 = add_accent(s)
    new = s2.slots[-1]
    assert new.id != last.id
    assert new.rules == rules
    assert new.use_scheme is False
    assert new.relations == ()
    assert new.value != last.value


def test_cannot_remove_bg_fg():
    s = default_session()
    for i in (0, 1):
        with pytest.raises(ValueError):
            remove_slot(s, s.slots[i].id)
    assert len(remove_slot(s, s.slots[5].id).slots) == 9


def test_cannot_remove_last_accent():
    s = default_session()
    for sl in s.slots[3:]:
        s = remove_slot(s, sl.id)
    assert len(s.slots) == 3
    with pytest.raises(ValueError):
        remove_slot(s, s.slots[2].id)


def test_broken_relation_after_remove():
    s = default_session()
    a, b = s.slots[2], s.slots[3]
    rel = Relation(kind="hue", target=b.id, op="eq", value=180.0, tol=15.0)
    s = with_slot(s, replace(a, relations=(rel,)))
    assert broken_relations(s) == []
    s = remove_slot(s, b.id)
    assert broken_relations(s) == [(a.id, 0)]
    assert s.slots[2].relations == (rel,)  # zależność zostaje, nie jest po cichu usuwana


def test_broken_relation_mix_other():
    s = default_session()
    a, b = s.slots[2], s.slots[3]
    ok = Relation(kind="mix", target=b.id, other=s.slots[4].id, op="eq", value=0.0)
    no_other = Relation(kind="mix", target=b.id, op="eq", value=0.0)
    ghost = Relation(kind="mix", target=b.id, other="duch", op="eq", value=0.0)
    s = with_slot(s, replace(a, relations=(ok, no_other, ghost)))
    assert broken_relations(s) == [(a.id, 1), (a.id, 2)]


def test_cycle_relations_not_broken():
    s = default_session()
    a, b = s.slots[2], s.slots[3]
    s = with_slot(s, replace(a, relations=(Relation("hue", b.id, "eq", 30.0),)))
    s = with_slot(s, replace(b, relations=(Relation("hue", a.id, "eq", 30.0),)))
    assert broken_relations(s) == []


def test_move_slot():
    s = default_session()
    ids = [sl.id for sl in s.slots]
    moved = move_slot(s, ids[4], 2)
    assert [sl.id for sl in moved.slots][:5] == [ids[0], ids[1], ids[4], ids[2], ids[3]]
    with pytest.raises(ValueError):
        move_slot(s, ids[0], 3)
    with pytest.raises(ValueError):
        move_slot(s, ids[4], 1)
    with pytest.raises(ValueError):
        move_slot(s, ids[4], 10)


def test_with_slot_unknown():
    s = default_session()
    with pytest.raises(ValueError):
        with_slot(s, Slot(id="zzz"))


def test_history_undo_redo_limit():
    base = default_session()
    h = History(limit=200)
    assert h.current is None
    assert h.undo() is None
    states = [replace(base, preset=str(i)) for i in range(201)]
    for st in states:
        h.push(st)
    assert len(h) == 200
    assert h.current == states[200]
    seen = [h.current]
    while (prev := h.undo()) is not None:
        seen.append(prev)
    assert seen[-1] == states[1]  # najstarszy (states[0]) zniknął
    assert len(seen) == 200
    assert h.redo() == states[2]


def test_history_push_truncates_redo():
    a, b, c = (replace(default_session(), preset=m) for m in "abc")
    h = History(a)
    h.push(b)
    assert h.undo() == a
    h.push(c)
    assert h.redo() is None
    assert h.undo() == a
    assert h.can_redo


def test_session_hashable_and_normalized():
    s = default_session()
    assert isinstance(hash(s), int)
    assert isinstance(Session(s.globals, list(s.slots)).slots, tuple)  # ty: ignore[invalid-argument-type]


def test_history_replace_current():
    a = default_session()
    b = add_accent(a)
    c = add_accent(b)
    h = History(a)
    h.push(b)
    h.replace_current(c)
    assert h.current == c
    assert h.undo() == a
    assert h.redo() == c
    assert not h.can_redo
