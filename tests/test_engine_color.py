"""Matematyka koloru silnika natywnego wobec wyroczni (Task 5, spec §9.3).

Wyrocznią jest dotychczasowy kod Pythona: ``algopalette.color`` (coloraide) i
``algopalette.color.fast`` (numpy). Tolerancje ze speca: przekształcenia, największe C i kontrast
≤ 1e-9; ΔE ``ok``/``hyab`` ≤ 1e-6; ΔE ``2000``/``itp``/``cam16`` ≤ 1e-4.
"""

import math
from collections.abc import Sequence

import numpy as np
import pytest
from numpy.typing import ArrayLike

from algopalette import _engine
from algopalette import color as slow
from algopalette.color import fast
from algopalette.model import OKLCH

pytestmark = pytest.mark.skipif(
    "color" not in _engine.build_info()["implemented"],
    reason="matematyka koloru silnika jeszcze niezaimplementowana",
)

N = 2000
SEED = 20261115

Lch = list[float]


def _random_in_gamut(n: int, seed: int) -> list[Lch]:
    """Losowe kolory w gamucie sRGB: L i H równomiernie, C jako ułamek największego C."""
    rng = np.random.default_rng(seed)
    l = rng.uniform(0.0, 1.0, n)
    h = rng.uniform(0.0, 360.0, n)
    c = rng.uniform(0.0, 1.0, n) * fast.max_chroma(l, h)
    return [[float(a), float(b), float(d)] for a, b, d in zip(l, c, h, strict=True)]


COLORS = _random_in_gamut(N, SEED)
OTHERS = _random_in_gamut(N, SEED + 1)

# Brzegi: szarości (C = 0), czerń, biel, kolory o L = 0 i L = 1 z niezerowym C w danych.
EDGES: list[Lch] = [
    [0.0, 0.0, 0.0],
    [1.0, 0.0, 0.0],
    [0.5, 0.0, 0.0],
    [0.5, 0.0, 217.0],
    [0.0, 0.0, 123.0],
    [1.0, 0.0, 300.0],
    [0.0, 0.005, 40.0],
    [1.0, 0.0005, 110.0],
    [0.25, 0.0, 359.9],
    [0.7, 0.1, 0.0],
    [0.7, 0.1, 360.0],
]
EDGE_PAIRS = [(a, b) for a in EDGES for b in EDGES]


def _ok(c: Sequence[float]) -> OKLCH:
    return OKLCH(c[0], c[1], c[2])


def _lab(lch: ArrayLike) -> np.ndarray:
    return fast.oklch_to_oklab(np.asarray(lch, dtype=np.float64))


def _max_abs(a: object, b: object) -> float:
    return float(np.max(np.abs(np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64))))


def _non_negative(c: Sequence[float]) -> bool:
    """Czy wszystkie kanały liniowe sRGB koloru są ≥ 0."""
    return bool(np.all(fast.oklch_to_linear_srgb(c) >= 0.0))


def _oracle_pairs(pairs: list[tuple[Lch, Lch]], method: str) -> list[tuple[Lch, Lch]]:
    """Pary, na których silnik ma się zgadzać z coloraide.

    ΔE ``itp`` koloru z ujemnym kanałem liniowym (np. prawie czarnego, w tolerancji gamutu 1e-6)
    wybucha w coloraide do ~1e60: mianownik krzywej PQ przechodzi przez zero dla ujemnego LMS.
    Silnik obcina LMS do ≥ 0 przed krzywą PQ, więc porównanie ma sens tylko dla kanałów ≥ 0.
    """
    if method != "itp":
        return pairs
    return [(a, b) for a, b in pairs if _non_negative(a) and _non_negative(b)]


# ---------------------------------------------------------------------------
# Przekształcenia i gamut
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("colors", [COLORS, EDGES], ids=["losowe", "brzegi"])
def test_oklch_to_linear_srgb_matches_oracle(colors: list[Lch]) -> None:
    got = [_engine.oklch_to_linear_srgb(c) for c in colors]
    assert _max_abs(got, fast.oklch_to_linear_srgb(colors)) <= 1e-9


@pytest.mark.parametrize("colors", [COLORS, EDGES], ids=["losowe", "brzegi"])
def test_linear_srgb_to_oklch_matches_oracle(colors: list[Lch]) -> None:
    lin = fast.oklch_to_linear_srgb(colors)
    got = _lab([_engine.linear_srgb_to_oklch([float(v) for v in row]) for row in lin])
    assert _max_abs(got, fast.linear_srgb_to_oklab(lin)) <= 1e-9


def test_round_trip_returns_the_same_color() -> None:
    back = [_engine.linear_srgb_to_oklch(_engine.oklch_to_linear_srgb(c)) for c in COLORS]
    assert _max_abs(_lab(back), _lab(COLORS)) <= 1e-9


def test_max_chroma_matches_oracle() -> None:
    rng = np.random.default_rng(SEED + 2)
    l = np.concatenate([rng.uniform(0.0, 1.0, N), [0.0, 1.0, 0.5, 1e-9, 1.0 - 1e-9]])
    h = np.concatenate([rng.uniform(0.0, 360.0, N), [0.0, 0.0, 360.0, 123.0, 45.0]])
    got = np.array([_engine.max_chroma(float(a), float(b)) for a, b in zip(l, h, strict=True)])
    exact = fast.max_chroma(l, h, tol=1e-13)  # ta sama bisekcja wyroczni, doprowadzona do końca
    assert _max_abs(got, exact) <= 1e-9
    # wyrocznia z domyślną tolerancją (1e-5) zwraca dolny koniec przedziału bisekcji
    default = fast.max_chroma(l, h)
    assert np.all(default <= got + 1e-12)
    assert np.all(got - default <= 1e-5)


def test_max_chroma_is_the_gamut_boundary() -> None:
    for l, _, h in COLORS[:300]:
        c = _engine.max_chroma(l, h)
        assert _engine.in_gamut([l, c * (1 - 1e-9), h])
        assert not _engine.in_gamut([l, c + 1e-6, h])


def test_in_gamut_matches_oracle() -> None:
    rng = np.random.default_rng(SEED + 3)
    pts = np.stack(
        [rng.uniform(-0.05, 1.05, N), rng.uniform(0.0, 0.45, N), rng.uniform(0.0, 360.0, N)],
        axis=-1,
    )
    want = fast.in_gamut(pts)
    got = [_engine.in_gamut([float(v) for v in p]) for p in pts]
    assert got == [bool(w) for w in want]
    assert 0.1 < float(np.mean(want)) < 0.9  # próbka pokrywa oba przypadki
    for p in pts[:200]:
        c = [float(v) for v in p]
        assert _engine.in_gamut(c) == slow.in_gamut(_ok(c))


# ---------------------------------------------------------------------------
# Kontrast
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("metric", ["wcag21", "apca"])
def test_contrast_matches_fast_oracle(metric: str) -> None:
    got = [_engine.contrast(t, b, metric) for t, b in zip(COLORS, OTHERS, strict=True)]
    assert _max_abs(got, fast.contrast(COLORS, OTHERS, metric)) <= 1e-9  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize("metric", ["wcag21", "apca"])
def test_contrast_matches_coloraide(metric: str) -> None:
    pairs = list(zip(COLORS[:500], OTHERS[:500], strict=True)) + EDGE_PAIRS
    got = [_engine.contrast(t, b, metric) for t, b in pairs]
    want = [slow.contrast(_ok(t), _ok(b), metric) for t, b in pairs]  # ty: ignore[invalid-argument-type]
    assert _max_abs(got, want) <= 1e-9


@pytest.mark.parametrize("metric", ["wcag21", "apca"])
def test_contrast_with_itself(metric: str) -> None:
    for c in COLORS[:50] + EDGES:
        assert _engine.contrast(c, c, metric) == (1.0 if metric == "wcag21" else 0.0)


# ---------------------------------------------------------------------------
# ΔE
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "tol"),
    [("ok", 1e-6), ("hyab", 1e-6), ("2000", 1e-4), ("itp", 1e-4), ("cam16", 1e-4)],
)
def test_delta_e_matches_coloraide(method: str, tol: float) -> None:
    pairs = _oracle_pairs(list(zip(COLORS, OTHERS, strict=True)) + EDGE_PAIRS, method)
    assert len(pairs) > 1900
    got = [_engine.delta_e(a, b, method) for a, b in pairs]
    want = [slow.delta_e(_ok(a), _ok(b), method) for a, b in pairs]  # ty: ignore[invalid-argument-type]
    assert all(math.isfinite(g) for g in got)
    assert _max_abs(got, want) <= tol


def test_delta_e_itp_of_near_black_with_negative_channel_is_small_and_finite() -> None:
    """Kolor prawie czarny z kanałami ≈ −4e-7 (w tolerancji gamutu): coloraide daje ~3e62."""
    dark = [0.00025226392678323606, 0.016693928320144356, 154.00122067068102]
    mid = [0.7218156380507523, 0.11816813009406159, 156.9038883531302]
    assert _engine.in_gamut(dark) and not _non_negative(dark)
    assert slow.delta_e(_ok(dark), _ok(mid), "itp") > 1e30
    assert 0.0 < _engine.delta_e(dark, mid, "itp") < 400.0
    assert 0.0 <= _engine.delta_e(dark, [0.0, 0.0, 0.0], "itp") < 5.0
    # dla wszystkich losowych kolorów w gamucie wartości są zwykłej wielkości
    got = [_engine.delta_e(a, b, "itp") for a, b in zip(COLORS, OTHERS, strict=True)]
    assert max(got) < 1000.0


@pytest.mark.parametrize("method", ["ok", "hyab"])
def test_delta_e_matches_fast_oracle(method: str) -> None:
    got = [_engine.delta_e(a, b, method) for a, b in zip(COLORS, OTHERS, strict=True)]
    assert _max_abs(got, fast.delta_e(COLORS, OTHERS, method)) <= 1e-6


@pytest.mark.parametrize("method", ["ok", "hyab", "2000", "itp", "cam16"])
def test_delta_e_of_identical_colors_is_zero(method: str) -> None:
    for c in COLORS[:100] + EDGES:
        assert _engine.delta_e(c, c, method) == 0.0


@pytest.mark.parametrize("method", ["ok", "hyab", "2000", "itp", "cam16"])
def test_delta_e_of_close_colors_matches_coloraide(method: str) -> None:
    """Bardzo bliskie pary — okolica, w której liczy się kara za zbyt małą odległość."""
    rng = np.random.default_rng(SEED + 4)
    tol = 1e-6 if method in ("ok", "hyab") else 1e-4
    for a in COLORS[:300]:
        b = [
            min(max(a[0] + rng.normal(0, 0.01), 0.0), 1.0),
            max(a[1] + rng.normal(0, 0.005), 0.0),
            a[2] + rng.normal(0, 3.0),
        ]
        if not _oracle_pairs([(a, b)], method):
            continue
        want = slow.delta_e(_ok(a), _ok(b), method)  # ty: ignore[invalid-argument-type]
        assert abs(_engine.delta_e(a, b, method) - want) <= tol


# ---------------------------------------------------------------------------
# Błędne argumenty
# ---------------------------------------------------------------------------


def test_unknown_names_raise_value_error() -> None:
    c = [0.5, 0.1, 30.0]
    with pytest.raises(ValueError, match="method"):
        _engine.delta_e(c, c, "76")
    with pytest.raises(ValueError, match="metric"):
        _engine.contrast(c, c, "wcag3")
