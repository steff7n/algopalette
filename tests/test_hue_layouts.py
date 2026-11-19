"""Generatory układów odcieni, port starej formuły i skupiska w kolejności akcentów."""

import pytest

from algopalette import color as col
from algopalette import hue_layouts as hl
from algopalette.hue_layouts import LegacyScheme
from algopalette.model import OKLCH


def approx(values):
    return pytest.approx(tuple(values), abs=1e-9)


def test_generators_from_30():
    assert hl.mono(30) == approx((30,))
    assert hl.complementary(30) == approx((30, 210))
    assert hl.split(30) == approx((30, 180, 240))
    assert hl.triad(30) == approx((30, 150, 270))
    assert hl.square(30) == approx((30, 120, 210, 300))
    assert hl.rectangle(30) == approx((30, 90, 210, 270))
    assert hl.analogous(30, n=3, spread=60) == approx((0, 30, 60))
    assert hl.analogous(30, n=1, spread=60) == approx((30,))
    assert hl.equal(30, n=4) == approx((30, 120, 210, 300))


def test_generators_wrap_into_range():
    for hues in (hl.triad(300), hl.analogous(10, n=5, spread=90), hl.equal(359, n=3)):
        assert all(0 <= h < 360 for h in hues)
    assert hl.triad(300) == approx((300, 60, 180))


def test_rotate():
    assert hl.rotate((350.0, 10.0), 20) == approx((10, 30))
    assert hl.rotate((10.0,), -20) == approx((350,))
    assert hl.rotate((), 45) == ()


def legacy(kind, n, **kw):
    return hl.legacy_targets(LegacyScheme(kind, **kw), n)


def test_legacy_matches_old_engine():
    # przypadki z crates/core/src/rules/hues.rs (targets_match_the_old_engine)
    assert legacy("equal", 8, rotation=10) == approx((10, 55, 100, 145, 190, 235, 280, 325))
    assert legacy("equal", 3, rotation=350) == approx((350, 110, 230))
    assert legacy("analogous", 5, center=200, spread=90) == approx((155, 177.5, 200, 222.5, 245))
    assert legacy("analogous", 1, center=30, spread=120) == approx((30,))
    assert legacy("complementary", 5, rotation=20) == approx((20, 200, 80, 260, 140))
    assert legacy("split", 7, rotation=0) == approx((0, 150, 210, 40, 190, 250, 80))
    assert legacy("triad", 8, rotation=45) == approx((45, 165, 285, 85, 205, 325, 125, 245))
    assert legacy("tetrad", 14, rotation=300) == approx(
        (300, 30, 120, 210, 322.5, 52.5, 142.5, 232.5, 345, 75, 165, 255, 7.5, 97.5)
    )
    assert legacy("custom", 8, custom=(15.0, 140.0, 280.0)) == approx(
        (15, 140, 280, 55, 180, 320, 95, 220)
    )
    assert legacy("custom", 4) == ()
    assert legacy("none", 6, custom=(10.0, 20.0)) == ()
    assert legacy("triad", 0, rotation=45) == ()


def test_legacy_custom_longer_than_n_kept_whole():
    hues = tuple(float(10 * i) for i in range(14))
    assert legacy("custom", 8, custom=hues) == approx(hues)
    assert legacy("custom", 0, custom=hues) == approx(hues)


DRACULA_ACCENTS = ("#ff5555", "#50fa7b", "#f1fa8c", "#bd93f9", "#ff79c6", "#8be9fd", "#ffb86c")


def test_ordered_clusters_first_occurrence():
    colors = [col.from_css(h) for h in DRACULA_ACCENTS]
    out = hl.ordered_clusters(colors)
    assert out[:3] == pytest.approx((24.4, 148.0, 112.8), abs=1.0)


def test_ordered_clusters_skips_greys():
    grey = OKLCH(0.5, 0.01, 200.0)
    red = OKLCH(0.6, 0.15, 25.0)
    assert hl.ordered_clusters([grey, red]) == pytest.approx((25.0,))
    assert hl.ordered_clusters([grey, grey]) == ()


def test_ordered_clusters_merges_close_hues_in_place_of_first():
    a = OKLCH(0.6, 0.15, 100.0)
    b = OKLCH(0.6, 0.15, 200.0)
    c = OKLCH(0.6, 0.15, 110.0)  # łączy się z a — skupisko stoi na miejscu a
    out = hl.ordered_clusters([a, b, c])
    assert len(out) == 2
    assert out[0] == pytest.approx(105.0, abs=1.0)
    assert out[1] == pytest.approx(200.0, abs=1e-6)
