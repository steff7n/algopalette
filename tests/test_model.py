"""Testy modelu sesji: kształt domyślnej sesji, dziedziczenie, limity slotów, historia."""

from dataclasses import replace

import pytest

from algopalette.color import contrast, delta_e
from algopalette.model import (
    OKLCH,
    ChromaRange,
    Cond,
    FrozenMap,
    History,
    Interval,
    Relation,
    Session,
    Slot,
    SlotConditions,
    add_accent,
    broken_relations,
    default_role_defaults,
    default_session,
    effective_conditions,
    move_slot,
    remove_slot,
    role_of,
    snapshot_key,
    with_slot,
)


def test_default_session_shape():
    s = default_session()
    assert len(s.slots) == 10
    assert len({sl.id for sl in s.slots}) == 10
    assert [role_of(i) for i in range(3)] == ["bg", "fg", "accent"]
    g = s.globals
    assert g.polarity == "dark"
    assert set(g.role_defaults) == {"bg", "fg", "accent"}
    assert g.hue_scheme.kind == "equal"
    assert (g.contrast_metric, g.delta_e, g.fit_method) == ("wcag21", "ok", "oklch-chroma")
    assert s.mood is None
    assert s.mood_snapshot is None
    bg = s.slots[0].value
    assert bg.l <= 0.25
    assert bg.c <= 0.04
    assert len({sl.value for sl in s.slots}) == 10  # nie wszystkie takie same


def test_default_values_satisfy_defaults():
    s = default_session()
    bg, fg, *accents = (sl.value for sl in s.slots)
    assert contrast(fg, bg, "wcag21") >= 7
    for a in accents:
        assert contrast(a, bg, "wcag21") >= 4.5
    for i, a in enumerate(accents):
        for b in accents[i + 1 :]:
            assert delta_e(a, b, "ok") >= 0.08


@pytest.mark.parametrize("polarity", ["dark", "light"])
@pytest.mark.parametrize("metric", ["wcag21", "apca"])
def test_role_defaults_complete(polarity, metric):
    rd = default_role_defaults(polarity, metric)
    assert set(rd) == {"bg", "fg", "accent"}
    assert rd["fg"].contrast_bg is not None
    assert rd["accent"].min_distance is not None
    cb = rd["accent"].contrast_bg
    assert cb is not None
    bound = cb.value
    assert bound.lo == (4.5 if metric == "wcag21" else 60.0)


def test_effective_inherits_and_sources():
    s = default_session()
    acc = s.slots[2]
    own = Cond(ChromaRange("rel", 0.5, 0.9), hard=False)
    s = with_slot(s, replace(acc, conditions=SlotConditions(chroma=own)))
    glob_lightness = s.globals.role_defaults["accent"].lightness
    snap = {snapshot_key("accent", "lightness"): glob_lightness}
    s = replace(s, mood="x", mood_snapshot=snap)

    cond, src = effective_conditions(s, acc.id)
    assert cond.chroma == own
    assert src["chroma"] == "slot"
    assert cond.lightness == glob_lightness
    assert src["lightness"] == "mood"
    assert cond.contrast_bg == s.globals.role_defaults["accent"].contrast_bg
    assert src["contrast_bg"] == "global"
    assert set(src) == set(SlotConditions.__dataclass_fields__)

    # użytkownik zmienił wartość globalną po nastroju: źródło wraca do „global”
    changed = Cond(Interval(0.5, 0.7))
    rd = dict(s.globals.role_defaults)
    rd["accent"] = replace(rd["accent"], lightness=changed)
    s2 = replace(s, globals=replace(s.globals, role_defaults=rd))
    cond2, src2 = effective_conditions(s2, acc.id)
    assert cond2.lightness == changed
    assert src2["lightness"] == "global"


def test_effective_uses_role_of_slot():
    s = default_session()
    bg_cond, _ = effective_conditions(s, s.slots[0].id)
    fg_cond, _ = effective_conditions(s, s.slots[1].id)
    assert bg_cond.contrast_bg is None
    assert fg_cond.contrast_bg is not None
    with pytest.raises(ValueError, match="Nieznany slot"):
        effective_conditions(s, "nie-ma")


def test_accent_limit():
    s = default_session()
    for _ in range(6):
        s = add_accent(s)
    assert len(s.slots) == 16
    assert len({sl.id for sl in s.slots}) == 16
    with pytest.raises(ValueError, match="Najwyżej 14 akcentów"):
        add_accent(s)


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
    assert s.slots[2].relations == (rel,)  # relacja zostaje, nie jest po cichu usuwana


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
    states = [replace(base, mood=str(i)) for i in range(201)]
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
    a, b, c = (replace(default_session(), mood=m) for m in "abc")
    h = History(a)
    h.push(b)
    assert h.undo() == a
    h.push(c)
    assert h.redo() is None
    assert h.undo() == a
    assert h.can_redo


def test_frozen_map_eq_hash():
    m = FrozenMap({"a": 1, "b": 2})
    assert m == {"a": 1, "b": 2}
    assert m == {"b": 2, "a": 1}
    assert hash(m) == hash(FrozenMap({"b": 2, "a": 1}))
    assert len(m) == 2
    assert OKLCH(0.5, 0.1, 10.0) == OKLCH(0.5, 0.1, 10.0)


def test_session_hashable_and_normalized():
    s = default_session()
    assert isinstance(s.globals.role_defaults, FrozenMap)
    s2 = replace(s, mood_snapshot={"k": 1})
    assert isinstance(s2.mood_snapshot, FrozenMap)
    assert isinstance(hash(s2), int)
    assert isinstance(Session(s.globals, list(s.slots)).slots, tuple)  # ty: ignore[invalid-argument-type]


def test_history_replace_current():
    from algopalette.model import History, add_accent, default_session

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
