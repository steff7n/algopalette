"""Silnik optymalizacji (Task 4)."""

import time
from dataclasses import replace

import pytest

from algopalette.color import Color, from_css
from algopalette.engine import apply_proposal, generate
from algopalette.model import (
    OKLCH,
    Cond,
    ContrastBound,
    Interval,
    Session,
    Slot,
    SlotConditions,
    default_role_defaults,
    default_session,
)


def basic(n_accents: int = 4, **opt) -> Session:
    s = default_session()
    g = s.globals
    rd = dict(default_role_defaults("dark", "wcag21"))
    rd["accent"] = replace(
        rd["accent"],
        contrast_bg=Cond(ContrastBound(None, 4.5, None)),
        min_distance=Cond(0.08, hard=True),
    )
    g = replace(g, role_defaults=rd, optimizer=replace(g.optimizer, **opt))
    bg = Slot(id="bg", value=from_css("#1e1e2e"), locked=True)
    fg = Slot(id="fg", value=OKLCH(0.9, 0.01, 260))
    accents = [Slot(id=f"a{i}", value=OKLCH(0.7, 0.1, 40.0 * i)) for i in range(n_accents)]
    return replace(s, globals=g, slots=(bg, fg, *accents))


def test_feasible_basic():
    s = basic()
    props = generate(s)
    assert len(props) == 6
    for p in props:
        assert p.ok, p.violations
        bg = Color(p.hexes["bg"])
        acc = [Color(p.hexes[f"a{i}"]) for i in range(4)]
        for a in acc:
            assert a.contrast(bg, "wcag21") >= 4.5 - 0.05  # zaokrąglenie do hexa
        for i in range(4):
            for j in range(i + 1, 4):
                assert acc[i].delta_e(acc[j], method="ok") >= 0.08 - 0.005


def test_deterministic():
    s = basic(n_proposals=2)
    a = [p.hexes for p in generate(s)]
    b = [p.hexes for p in generate(s)]
    assert a == b


def test_seed_changes():
    s = basic(n_proposals=1)
    a = generate(s)[0].hexes
    b = generate(
        replace(s, globals=replace(s.globals, optimizer=replace(s.globals.optimizer, seed=7)))
    )[0].hexes
    assert a != b


def test_infeasible_reports():
    s = basic(n_proposals=2)
    rd = dict(s.globals.role_defaults)
    rd["accent"] = replace(rd["accent"], contrast_bg=Cond(ContrastBound(None, 15.0, None)))
    s = replace(s, globals=replace(s.globals, role_defaults=rd))
    s = replace(s, slots=(replace(s.slots[0], value=OKLCH(0.5, 0.0, 0.0)), *s.slots[1:]))
    props = generate(s)
    assert props
    for p in props:
        assert not p.ok
        hard = [v for v in p.violations if v.hard and v.key.endswith("contrast_bg")]
        assert hard and all(v.amount > 0 for v in hard)


def test_locked_untouched():
    s = basic(n_proposals=2)
    locked = replace(s.slots[3], locked=True, value=OKLCH(0.71, 0.123, 77.7))
    s = replace(s, slots=(*s.slots[:3], locked, *s.slots[4:]))
    for p in generate(s):
        assert p.values["bg"] == s.slots[0].value
        assert p.values[locked.id] == locked.value


def test_subset_generation():
    s = basic(n_proposals=1)
    p = generate(s, slot_ids={"a2"})[0]
    for sl in s.slots:
        if sl.id != "a2":
            assert p.values[sl.id] == sl.value
    assert p.values["a2"] != s.slots[4].value


def test_diversity():
    s = basic(n_proposals=4, min_diversity=0.05)
    props = generate(s)
    free = [f"a{i}" for i in range(4)] + ["fg"]
    for i in range(len(props)):
        for j in range(i + 1, len(props)):
            d = sum(
                Color("oklch", [*_t(props[i].values[k])]).delta_e(
                    Color("oklch", [*_t(props[j].values[k])]), method="ok"
                )
                for k in free
            ) / len(free)
            soft = [v for v in props[j].violations if v.key == "global:diversity"]
            assert d >= 0.05 - 1e-6 or soft


def _t(c: OKLCH) -> tuple[float, float, float]:
    return (c.l, c.c, c.h)


def test_cancel():
    s = basic(n_proposals=6)
    calls = {"n": 0}

    def cancel() -> bool:
        calls["n"] += 1
        return calls["n"] > 50

    t0 = time.monotonic()
    props = generate(s, cancel=cancel)
    assert time.monotonic() - t0 < 1.0
    assert len(props) <= 6


def test_time_cap():
    s = basic(n_proposals=3, time_cap_s=0.001)
    props = generate(s)
    assert props and props[-1].timed_out
    assert not props[-1].ok


def test_locked_out_of_gamut():
    s = basic(n_proposals=1)
    wild = replace(s.slots[2], locked=True, value=OKLCH(0.75, 0.30, 140))
    s = replace(s, slots=(*s.slots[:2], wild, *s.slots[3:]))
    p = generate(s)[0]
    assert p.hexes[wild.id].startswith("#") and len(p.hexes[wild.id]) == 7
    assert p.fit_deltas[wild.id] > 0.01


def test_progress_reaches_one():
    seen: list[float] = []
    generate(basic(n_proposals=2), progress=seen.append)
    assert seen and seen[-1] == pytest.approx(1.0)
    assert all(0.0 <= x <= 1.0 for x in seen)


def test_apply_proposal_respects_locks_and_subset():
    s = basic(n_proposals=1)
    p = generate(s)[0]
    s2 = apply_proposal(s, p, slot_ids={"a1"})
    assert s2.slots[3].value == p.values["a1"]
    assert s2.slots[2].value == s.slots[2].value
    assert s2.slots[0].value == s.slots[0].value


def test_soft_condition_does_not_fail_ok():
    s = basic(n_proposals=1)
    a = replace(
        s.slots[2], conditions=SlotConditions(lightness=Cond(Interval(0.95, 1.0), hard=False))
    )
    s = replace(s, slots=(*s.slots[:2], a, *s.slots[3:]))
    p = generate(s)[0]
    assert all(not v.hard for v in p.violations) == p.ok


@pytest.mark.slow
def test_perf_default():
    s = default_session()
    t0 = time.monotonic()
    props = generate(s)
    dt = time.monotonic() - t0
    print(f"\nperf default_session, 6 propozycji: {dt:.2f} s")
    assert len(props) == 6
    assert dt < 6.0
