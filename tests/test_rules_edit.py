"""Logika edycji zbiorczej zasad (bez Qt) i opisy formularzy nowych zasad."""

from dataclasses import replace

import pytest

from algopalette import forms
from algopalette.globals_logic import change_delta_e, change_metric
from algopalette.model import (
    RULE_FIELDS,
    Band,
    ChromaBand,
    ContrastBound,
    HueArc,
    Rule,
    default_session,
    with_slot,
)
from algopalette.rules_edit import (
    Merged,
    applicable_fields,
    merged_rule,
    merged_use_scheme,
    set_rule,
    set_use_scheme,
    update_rule,
)


def ids_of(s, *indices):
    return [s.slots[i].id for i in indices]


def with_rule(s, index, field, rule):
    slot = s.slots[index]
    return with_slot(s, replace(slot, rules=replace(slot.rules, **{field: rule})))


# --- zastosowalność --------------------------------------------------------------------------


def test_applicable_fields_is_intersection_of_roles():
    s = default_session()
    assert applicable_fields(s, ids_of(s, 0, 2)) == ("lightness", "chroma", "hue")
    assert applicable_fields(s, ids_of(s, 1, 2)) == ("lightness", "chroma", "hue", "contrast_bg")
    assert applicable_fields(s, ids_of(s, 2, 5, 9)) == RULE_FIELDS
    assert applicable_fields(s, ids_of(s, 0)) == ("lightness", "chroma", "hue")
    assert applicable_fields(s, ids_of(s, 0, 1, 2)) == ("lightness", "chroma", "hue")
    assert applicable_fields(s, []) == ()
    with pytest.raises(ValueError):
        applicable_fields(s, ["nie-ma"])


# --- odczyt ----------------------------------------------------------------------------------


def test_merged_same():
    s = default_session()
    ids = ids_of(s, 2, 3, 4)
    m = merged_rule(s, ids, "lightness")
    assert m == Merged(
        "same", Rule(Band(0.60, 0.85)), tuple((i, Rule(Band(0.60, 0.85))) for i in ids)
    )


def test_merged_absent():
    s = default_session()
    ids = ids_of(s, 2, 3)
    assert merged_rule(s, ids, "hue") == Merged("absent", None, ((ids[0], None), (ids[1], None)))


@pytest.mark.parametrize(
    "other",
    [
        Rule(Band(0.50, 0.85)),  # inna wartość
        Rule(Band(0.60, 0.85, exclude=((0.70, 0.74),))),  # inny zakaz
        Rule(Band(0.60, 0.85), enabled=False),
        Rule(Band(0.60, 0.85), hard=False),
        Rule(Band(0.60, 0.85), weight=2.0),
        None,  # zasada tylko u części
    ],
)
def test_merged_mixed(other):
    s = with_rule(default_session(), 3, "lightness", other)
    ids = ids_of(s, 2, 3)
    m = merged_rule(s, ids, "lightness")
    assert m.state == "mixed"
    assert m.per_slot == ((ids[0], Rule(Band(0.60, 0.85))), (ids[1], other))
    assert m.rule == Rule(Band(0.60, 0.85))  # zasada pierwszego zaznaczonego, który ją ma


def test_merged_mixed_first_selected_without_rule():
    s = with_rule(default_session(), 2, "lightness", None)
    ids = ids_of(s, 2, 3)
    m = merged_rule(s, ids, "lightness")
    assert m.state == "mixed"
    assert m.rule == Rule(Band(0.60, 0.85))
    assert m.per_slot[0] == (ids[0], None)


def test_merged_per_slot_follows_ids_order():
    s = default_session()
    ids = ids_of(s, 5, 2)
    assert [i for i, _ in merged_rule(s, ids, "chroma").per_slot] == ids


def test_merged_chroma_abs_vs_rel_is_mixed_and_set_rule_unifies():
    """Review Focus 3: nasycenie bezwzględne u jednego, względne u drugiego."""
    s = with_rule(default_session(), 3, "chroma", Rule(ChromaBand("rel", 0.5, 0.7)))
    ids = ids_of(s, 2, 3)
    assert merged_rule(s, ids, "chroma").state == "mixed"
    target = Rule(ChromaBand("rel", 0.4, 0.8, exclude=((0.5, 0.6),)), hard=False)
    s2 = set_rule(s, ids, "chroma", target)
    assert merged_rule(s2, ids, "chroma") == Merged(
        "same", target, ((ids[0], target), (ids[1], target))
    )
    assert s2.slots[4].rules == s.slots[4].rules  # niezaznaczone bez zmian


# --- zapis -----------------------------------------------------------------------------------


def test_set_rule_none_removes_everywhere():
    s = default_session()
    ids = ids_of(s, 2, 3, 4)
    s2 = set_rule(s, ids, "min_distance", None)
    assert merged_rule(s2, ids, "min_distance").state == "absent"
    assert s2.slots[5].rules.min_distance is not None


def test_set_rule_returns_same_session_when_nothing_changes():
    s = default_session()
    ids = ids_of(s, 2, 3)
    assert set_rule(s, ids, "lightness", Rule(Band(0.60, 0.85))) is s
    assert update_rule(s, ids, "lightness", hard=True) is s
    assert update_rule(s, ids, "hue", hard=False) is s  # zasady nie ma — nic do zmiany


def test_update_rule_changes_only_existing():
    s = with_rule(default_session(), 3, "contrast_bg", None)
    ids = ids_of(s, 2, 3, 4)
    s2 = update_rule(s, ids, "contrast_bg", hard=False, weight=2.0)
    assert s2.slots[2].rules.contrast_bg == Rule(
        ContrastBound(None, 4.5, None), hard=False, weight=2.0
    )
    assert s2.slots[3].rules.contrast_bg is None  # nie powstała
    assert s2.slots[4].rules.contrast_bg == s2.slots[2].rules.contrast_bg
    s3 = update_rule(s2, ids, "contrast_bg", enabled=False)
    assert s3.slots[2].rules.contrast_bg == Rule(
        ContrastBound(None, 4.5, None), enabled=False, hard=False, weight=2.0
    )
    with pytest.raises(ValueError):
        update_rule(s, ids, "contrast_bg", kolor="zielony")


def test_writes_are_one_step_and_keep_other_data():
    s = default_session()
    ids = ids_of(s, 2, 9)
    s2 = set_rule(s, ids, "hue", Rule(HueArc(0.0, 270.0, exclude=((60.0, 85.0), (140.0, 155.0)))))
    assert [a.id for a in s2.slots] == [a.id for a in s.slots]
    assert [a.value for a in s2.slots] == [a.value for a in s.slots]
    assert s2.globals == s.globals
    assert s2.preset == s.preset
    changed = [i for i, (a, b) in enumerate(zip(s.slots, s2.slots, strict=True)) if a != b]
    assert changed == [2, 9]


@pytest.mark.parametrize(
    ("indices", "field"),
    [
        ((0, 2), "contrast_bg"),
        ((1, 2), "min_distance"),
        ((0,), "extreme"),
        ((1,), "min_distance"),
    ],
)
def test_field_not_applicable_raises(indices, field):
    s = default_session()
    ids = ids_of(s, *indices)
    with pytest.raises(ValueError):
        set_rule(s, ids, field, None)
    with pytest.raises(ValueError):
        update_rule(s, ids, field, hard=False)
    with pytest.raises(ValueError):
        merged_rule(s, ids, field)


def test_unknown_field_and_empty_selection_raise():
    s = default_session()
    with pytest.raises(ValueError):
        merged_rule(s, ids_of(s, 2), "hue_range")
    with pytest.raises(ValueError):
        set_rule(s, [], "lightness", None)
    with pytest.raises(ValueError):
        merged_rule(s, [], "lightness")
    with pytest.raises(ValueError):
        set_rule(s, ["nie-ma"], "lightness", None)


def test_use_scheme():
    s = default_session()
    ids = ids_of(s, 2, 3)
    assert merged_use_scheme(s, ids) is True
    s2 = set_use_scheme(s, ids_of(s, 3), False)
    assert merged_use_scheme(s2, ids) is None
    assert merged_use_scheme(s2, ids_of(s, 3)) is False
    s3 = set_use_scheme(s2, ids, True)
    assert merged_use_scheme(s3, ids) is True
    assert set_use_scheme(s, ids, True) is s
    with pytest.raises(ValueError):
        set_use_scheme(s, ids_of(s, 0, 2), False)
    with pytest.raises(ValueError):
        merged_use_scheme(s, ids_of(s, 1))


# --- opisy formularzy ------------------------------------------------------------------------


def test_form_labels_cover_rule_fields():
    assert forms.LABELS == {
        "lightness": "jasność L",
        "chroma": "nasycenie C",
        "hue": "odcień",
        "contrast_bg": "kontrast z tłem",
        "min_distance": "odległość od innych akcentów",
        "extreme": "skrajny kontrast",
    }
    assert set(forms.DESCRIPTIONS) == set(RULE_FIELDS)
    assert set(forms.DEFAULTS) == set(RULE_FIELDS)
    assert tuple(forms.DISPLAY_ORDER) == RULE_FIELDS
    for text in (*forms.LABELS.values(), *forms.DESCRIPTIONS.values()):
        assert "dziedzic" not in text


def test_default_for_in_current_units():
    s = default_session()
    assert forms.default_for("hue", s) == HueArc(0.0, 60.0)
    assert forms.default_for("lightness", s) == Band(0.5, 0.8)
    assert forms.default_for("chroma", s) == ChromaBand("abs", 0.05, 0.15)
    assert forms.default_for("contrast_bg", s) == ContrastBound(None, 4.5, None)
    assert forms.default_for("min_distance", s) == pytest.approx(0.08)
    assert forms.default_for("extreme", s) == "weakest"
    apca = change_metric(s, "apca")
    assert forms.default_for("contrast_bg", apca) == ContrastBound(None, 60.0, None)
    de = change_delta_e(s, "2000")
    assert forms.default_for("min_distance", de) == pytest.approx(12.48)


def test_range_spec_for_new_fields():
    s = default_session()
    hue = forms.range_spec("hue", HueArc(0.0, 60.0), s)
    assert (hue["minimum"], hue["maximum"], hue["wrap"]) == (0.0, 360.0, True)
    rel = forms.range_spec("chroma", ChromaBand("rel", 0.2, 0.8), s)
    assert rel["maximum"] == 1.0
    assert forms.range_spec("chroma", ChromaBand("abs", 0.05, 0.15), s)["maximum"] == 0.37
    assert forms.range_spec("lightness", Band(0.5, 0.8), s)["allow_none"] is True
