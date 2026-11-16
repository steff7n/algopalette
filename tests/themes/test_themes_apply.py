from dataclasses import replace

import pytest

from algopalette import color as col
from algopalette.model import OKLCH, Relation, default_session
from algopalette.rules_edit import set_rules_lock
from algopalette.themes import Palette
from algopalette.themes.apply import apply_theme


def palette(n: int, *, light: bool = False) -> Palette:
    bg = col.from_css("#fafafa" if light else "#1e1e2e")
    fg = col.from_css("#202020" if light else "#cdd6f4")
    accents = tuple(OKLCH(0.6 if light else 0.75, 0.12, (30.0 + 25.0 * k) % 360) for k in range(n))
    return Palette(bg, fg, accents, tuple(f"a{k}" for k in range(n)))


def session_with_lock(mode="rules", index=2):
    s = default_session()
    sid = s.slots[index].id
    rel = Relation("contrast", s.slots[0].id, "ge", 3.0)
    s = replace(
        s,
        slots=tuple(
            replace(sl, relations=(rel,), locked=True) if sl.id == sid else sl for sl in s.slots
        ),
        globals=replace(s.globals, avoid_colors=(OKLCH(0.5, 0.1, 10.0),), avoid_distance=0.07),
    )
    return set_rules_lock(s, [sid], mode, {sid: 40.0}), sid


def by_id(s, sid):
    return next(sl for sl in s.slots if sl.id == sid)


def test_default_mode_fits_settings_to_theme():
    s = default_session()
    s = replace(
        s, globals=replace(s.globals, avoid_colors=(OKLCH(0.5, 0.1, 10.0),), avoid_distance=0.07)
    )
    assert s.globals.polarity == "dark"
    out = apply_theme(s, palette(5, light=True), keep_settings=False)
    g = out.globals
    assert g.polarity == "light"
    assert g.hue_scheme.kind == "custom"
    assert out.preset is None
    assert g.avoid_colors == s.globals.avoid_colors and g.avoid_distance == 0.07
    assert g.contrast_metric == s.globals.contrast_metric
    assert [sl.name for sl in out.slots] == ["tło", "tekst", "a0", "a1", "a2", "a3", "a4"]
    assert all(sl.use_scheme for sl in out.slots[2:])


@pytest.mark.parametrize("mode", ["rules", "hue"])
@pytest.mark.parametrize("keep", [False, True])
def test_rules_lock_protects_rules_not_value(mode, keep):
    s, sid = session_with_lock(mode)
    before = by_id(s, sid)
    p = palette(8)
    out = apply_theme(s, p, keep_settings=keep)
    after = by_id(out, sid)
    assert (after.rules, after.use_scheme, after.relations, after.rules_lock) == (
        before.rules,
        before.use_scheme,
        before.relations,
        before.rules_lock,
    )
    assert after.value == p.accents[0]
    assert after.locked is False


def test_keep_settings_changes_only_values_count_and_value_locks():
    s, _ = session_with_lock("rules")
    out = apply_theme(s, palette(5), keep_settings=True)
    assert out.globals == s.globals
    assert out.preset == s.preset
    for old, new in zip(s.slots, out.slots, strict=False):
        assert old.id == new.id
        assert (old.rules, old.use_scheme, old.relations, old.rules_lock) == (
            new.rules,
            new.use_scheme,
            new.relations,
            new.rules_lock,
        )
    assert len(out.slots) == 7


@pytest.mark.parametrize(("n", "expected"), [(12, 14), (3, 5), (14, 16), (1, 3)])
def test_count(n, expected):
    out = apply_theme(default_session(), palette(n), keep_settings=False)
    assert len(out.slots) == expected


def test_locked_last_accent_is_kept_and_gets_value():
    s = default_session()
    last = s.slots[-1].id
    s = set_rules_lock(s, [last], "rules", {})
    p = palette(3)
    out = apply_theme(s, p, keep_settings=False)
    assert len(out.slots) == 5
    assert out.slots[-1].id == last
    assert out.slots[-1].value == p.accents[2]


def test_too_many_locked_accents_keep_old_values():
    s = default_session()  # 8 akcentów
    locked = [sl.id for sl in s.slots[6:]]  # a5..a8
    s = set_rules_lock(s, locked, "rules", {})
    old = {sl.id: sl.value for sl in s.slots}
    p = palette(2)
    out = apply_theme(s, p, keep_settings=False)
    assert [sl.id for sl in out.slots[2:]] == locked
    assert out.slots[2].value == p.accents[0] and out.slots[3].value == p.accents[1]
    assert out.slots[4].value == old[locked[2]] and out.slots[5].value == old[locked[3]]


def test_value_locks_removed_everywhere():
    s = default_session()
    s = replace(s, slots=tuple(replace(sl, locked=True) for sl in s.slots))
    for keep in (False, True):
        out = apply_theme(s, palette(4), keep_settings=keep)
        assert not any(sl.locked for sl in out.slots)
