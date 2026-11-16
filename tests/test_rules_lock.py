"""Kłódka zasad: preset omija zablokowane kolory, zamrożenie celu odcienia, zapis, silnik."""

from dataclasses import replace

import pytest

from algopalette import engine
from algopalette import io as aio
from algopalette.model import HueArc, HueScheme, Rule, default_session, with_slot
from algopalette.presets import apply_preset, is_modified
from algopalette.rules_edit import _intersect, merged_rules_lock, set_rules_lock


def session_with_scheme(tol: float = 4.0, hard: bool = True, weight: float = 2.0):
    s = default_session()
    scheme = HueScheme("equal", tol=tol, hard=hard, weight=weight)
    return replace(s, globals=replace(s.globals, hue_scheme=scheme))


def test_preset_keeps_locked_rules_and_use_scheme():
    s = apply_preset(default_session(), "neutralny")
    a1, a2 = s.slots[2], s.slots[3]
    custom = replace(a1.rules, hue=Rule(HueArc(10.0, 20.0)))
    s = with_slot(s, replace(a1, rules=custom, use_scheme=False))
    s = set_rules_lock(s, [a1.id], "rules", {})
    out = apply_preset(s, "pastel")
    assert out.slots[2].rules == custom
    assert out.slots[2].use_scheme is False
    assert out.slots[2].rules_lock == "rules"
    assert out.preset == "pastel"
    # Bez kłódki ten sam preset zastępuje zasady; pozostałe kolory dostają je tak samo.
    plain = apply_preset(set_rules_lock(s, [a1.id], "off", {}), "pastel")
    assert plain.slots[2].rules != custom
    assert out.slots[3] == plain.slots[3] != a2


def test_is_modified_ignores_locked_slots():
    s = apply_preset(default_session(), "pastel")
    a1 = s.slots[2]
    changed = with_slot(s, replace(a1, rules=replace(a1.rules, hue=Rule(HueArc(1.0, 2.0)))))
    assert is_modified(changed)
    assert not is_modified(set_rules_lock(changed, [a1.id], "rules", {}))


def test_freeze_turns_scheme_target_into_own_hue_rule():
    s = session_with_scheme()
    a = s.slots[2]
    assert a.rules.hue is None and a.use_scheme
    out = set_rules_lock(s, [a.id], "hue", {a.id: 70.0})
    slot = out.slots[2]
    assert slot.rules_lock == "hue"
    assert slot.use_scheme is False
    assert slot.rules.hue == Rule(HueArc(66.0, 74.0), hard=True, weight=2.0)


def test_freeze_wraps_through_zero():
    s = session_with_scheme(tol=4.0)
    a = s.slots[2]
    out = set_rules_lock(s, [a.id], "hue", {a.id: 2.0})
    assert out.slots[2].rules.hue is not None
    assert out.slots[2].rules.hue.value == HueArc(358.0, 6.0)


def test_freeze_intersects_with_own_arc_and_keeps_exclusions():
    s = session_with_scheme(tol=4.0, hard=False, weight=1.0)
    a = s.slots[2]
    own = Rule(HueArc(0.0, 68.0, exclude=((20.0, 30.0),)), hard=True, weight=3.0)
    s = with_slot(s, replace(a, rules=replace(a.rules, hue=own)))
    out = set_rules_lock(s, [a.id], "hue", {a.id: 70.0})
    hue = out.slots[2].rules.hue
    assert hue is not None
    assert (hue.value.lo, hue.value.hi) == (66.0, 68.0)
    assert hue.value.exclude == ((20.0, 30.0),)
    assert hue.hard is True and hue.weight == 3.0


def test_freeze_disjoint_own_arc_takes_scheme_target():
    s = session_with_scheme(tol=4.0)
    a = s.slots[2]
    s = with_slot(s, replace(a, rules=replace(a.rules, hue=Rule(HueArc(200.0, 220.0)))))
    out = set_rules_lock(s, [a.id], "hue", {a.id: 70.0})
    assert out.slots[2].rules.hue == Rule(HueArc(66.0, 74.0), hard=True, weight=2.0)


@pytest.mark.parametrize("case", ["no_target", "not_using_scheme", "scheme_none", "background"])
def test_freeze_without_target_only_locks(case):
    s = session_with_scheme()
    idx = 0 if case == "background" else 2
    slot = s.slots[idx]
    targets = {slot.id: 70.0}
    if case == "no_target":
        targets = {}
    elif case == "not_using_scheme":
        s = with_slot(s, replace(slot, use_scheme=False))
    elif case == "scheme_none":
        s = replace(s, globals=replace(s.globals, hue_scheme=HueScheme("none")))
    before = s.slots[idx]
    out = set_rules_lock(s, [slot.id], "hue", targets)
    assert out.slots[idx] == replace(before, rules_lock="hue")


def test_unlock_restores_nothing():
    s = session_with_scheme()
    a = s.slots[2]
    frozen = set_rules_lock(s, [a.id], "hue", {a.id: 70.0})
    off = set_rules_lock(frozen, [a.id], "off", {a.id: 70.0})
    assert off.slots[2] == replace(frozen.slots[2], rules_lock="off")


def test_merged_rules_lock():
    s = default_session()
    ids = [s.slots[2].id, s.slots[3].id]
    assert merged_rules_lock(s, ids) == "off"
    s = set_rules_lock(s, ids[:1], "rules", {})
    assert merged_rules_lock(s, ids) is None
    assert merged_rules_lock(s, ids[:1]) == "rules"


def test_set_rules_lock_same_mode_returns_same_session():
    s = default_session()
    s = set_rules_lock(s, [s.slots[2].id], "rules", {})
    assert set_rules_lock(s, [s.slots[2].id], "rules", {}) is s


def test_intersect_picks_longer_piece():
    # a = 350–30°, b = 340–30° → wspólne całe a
    assert _intersect((350.0, 40.0), (340.0, 50.0)) == (350.0, 40.0)
    assert _intersect((0.0, 100.0), (350.0, 120.0)) == (0.0, 100.0)
    assert _intersect((0.0, 100.0), (200.0, 10.0)) is None
    two = _intersect((0.0, 100.0), (90.0, 290.0))  # wspólne: 90–100 (10°) i 0–20 (20°)
    assert two == (0.0, 20.0)


def test_io_roundtrip_and_old_files_without_key():
    s = default_session()
    s = set_rules_lock(s, [s.slots[3].id], "hue", {})
    doc = aio.session_to_dict(s)
    assert doc["slots"][3]["rules_lock"] == "hue"
    assert aio.session_from_dict(doc) == s
    assert [("rules_lock" in sl) for sl in doc["slots"]] == [False, False, False, True] + [
        False
    ] * (len(s.slots) - 4)
    del doc["slots"][3]["rules_lock"]
    assert all(sl.rules_lock == "off" for sl in aio.session_from_dict(doc).slots)
    doc["slots"][0]["rules_lock"] = "zawsze"
    with pytest.raises(ValueError, match="rules_lock"):
        aio.session_from_dict(doc)


def test_engine_accepts_locked_session():
    s = default_session()
    locked = set_rules_lock(s, [sl.id for sl in s.slots], "rules", {})
    assert '"rules_lock"' not in engine.to_engine_json(locked, ())
    assert engine.objective(locked) == pytest.approx(engine.objective(s))
