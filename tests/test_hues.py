"""Układy odcieni (Task 5)."""

import pytest

from algopalette.hues import scheme_targets, targets_for_session
from algopalette.model import HueScheme, default_session


@pytest.mark.parametrize(
    ("scheme", "n", "expected"),
    [
        (HueScheme("equal", rotation=10), 4, [10, 100, 190, 280]),
        (HueScheme("triad", rotation=0), 3, [0, 120, 240]),
        (HueScheme("complementary", rotation=30), 2, [30, 210]),
        (HueScheme("analogous", center=200, spread=60), 3, [170, 200, 230]),
        (HueScheme("custom", custom=(30, 200)), 2, [30, 200]),
        (HueScheme("none"), 5, []),
        (HueScheme("custom"), 3, []),
    ],
)
def test_scheme_values(scheme, n, expected):
    assert scheme_targets(scheme, n, seed=0) == pytest.approx(expected, abs=1e-9)


def test_cycle_rule():
    # triad, n=5: k=3, ⌈5/3⌉=2 obiegi → przesunięcie 360/(3·2)=60° w drugim obiegu
    got = scheme_targets(HueScheme("triad", rotation=0), 5, seed=0)
    assert got == pytest.approx([0, 120, 240, 60, 180])


def test_wraps_to_0_360():
    got = scheme_targets(HueScheme("complementary", rotation=300), 2, seed=0)
    assert got == pytest.approx([300, 120])


def test_jitter_deterministic_and_bounded():
    s = HueScheme("equal", jitter=5.0)
    a, b = scheme_targets(s, 6, seed=3), scheme_targets(s, 6, seed=3)
    assert a == b
    base = scheme_targets(HueScheme("equal"), 6, seed=3)
    assert a != base
    for x, y in zip(a, base, strict=True):
        assert abs((x - y + 180) % 360 - 180) <= 5.0 + 1e-9
    assert scheme_targets(s, 6, seed=4) != a


def test_targets_for_session_maps_accents():
    s = default_session()
    t = targets_for_session(s)
    assert list(t) == [sl.id for sl in s.slots[2:]]
    assert t[s.slots[2].id] == pytest.approx(0.0)
