"""Układy odcieni jako generatory listy (spec 2026-11-19-uklad-odcieni-lista).

Układ odcieni palety to jedna jawna lista odcieni: akcent ``i`` dostaje cel ``hues[i mod k]``.
Harmonie (mono, triada, kwadrat…) są tu czystymi funkcjami, które tę listę budują od odcienia
bazowego. ``LegacyScheme`` + ``legacy_targets`` rozwijają dawny kształt „rodzaj + parametry”
(stare pliki v2 i deklaracje presetów) do listy dającej dokładnie te same cele co dawny silnik.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from algopalette import color as col
from algopalette.model import MAX_ACCENTS, OKLCH, HueScheme

Hues = tuple[float, ...]
LegacyKind = Literal[
    "equal", "analogous", "complementary", "split", "triad", "tetrad", "custom", "none"
]

BASE_EMPTY = 25.0  # baza generatora, gdy lista jest pusta
MERGE_DEG = 25.0  # skupiska odcieni bliższe niż tyle stopni łączą się
CHROMA_MIN = 0.03  # akcenty o mniejszej chromie nie wnoszą odcienia

# (etykieta w GUI, klucz) — kolejność przycisków „Wstaw:”
GENERATORS: tuple[tuple[str, str], ...] = (
    ("mono", "mono"),
    ("analogiczny", "analogous"),
    ("dopełniający", "complementary"),
    ("rozszczepiony", "split"),
    ("triada", "triad"),
    ("kwadrat", "square"),
    ("prostokąt", "rectangle"),
    ("równo po kole", "equal"),
    ("z bieżących kolorów", "current"),
)


def _wrap(hues: Sequence[float]) -> Hues:
    return tuple(float(h) % 360.0 for h in hues)


def _offsets(base: float, offsets: Sequence[float]) -> Hues:
    return _wrap([base + d for d in offsets])


def mono(base: float) -> Hues:
    return _offsets(base, (0,))


def complementary(base: float) -> Hues:
    return _offsets(base, (0, 180))


def split(base: float) -> Hues:
    return _offsets(base, (0, 150, 210))


def triad(base: float) -> Hues:
    return _offsets(base, (0, 120, 240))


def square(base: float) -> Hues:
    return _offsets(base, (0, 90, 180, 270))


def rectangle(base: float) -> Hues:
    return _offsets(base, (0, 60, 180, 240))


def analogous(base: float, n: int, spread: float) -> Hues:
    """``n`` punktów równo w ``base ± spread / 2``; ``n == 1`` → sama baza."""
    if n <= 1:
        return mono(base)
    lo = base - spread / 2.0
    return _wrap([lo + spread * i / (n - 1) for i in range(n)])


def equal(base: float, n: int) -> Hues:
    """``n`` punktów co ``360 / n`` od bazy."""
    if n <= 0:
        return ()
    return _wrap([base + 360.0 * i / n for i in range(n)])


def rotate(hues: Sequence[float], delta: float) -> Hues:
    return _wrap([h + delta for h in hues])


SIMPLE_GENERATORS: dict[str, Callable[[float], Hues]] = {
    "mono": mono,
    "complementary": complementary,
    "split": split,
    "triad": triad,
    "square": square,
    "rectangle": rectangle,
}


def family_counts(n_hues: int, use_scheme: Sequence[bool]) -> tuple[int, ...]:
    """Ile akcentów trafia do każdej pozycji listy (``use_scheme`` akcentów w kolejności)."""
    counts = [0] * n_hues
    if n_hues:
        for i, on in enumerate(use_scheme):
            if on:
                counts[i % n_hues] += 1
    return tuple(counts)


# ---------------------------------------------------------------------------
# Skupiska odcieni w kolejności akcentów
# ---------------------------------------------------------------------------


def _circ_mean(hues: Sequence[float], weights: Sequence[float]) -> float:
    s = sum(w * math.sin(math.radians(h)) for h, w in zip(hues, weights, strict=True))
    c = sum(w * math.cos(math.radians(h)) for h, w in zip(hues, weights, strict=True))
    return math.degrees(math.atan2(s, c)) % 360.0


def ordered_clusters(
    colors: Sequence[OKLCH], merge_deg: float = MERGE_DEG, chroma_min: float = CHROMA_MIN
) -> Hues:
    """Aglomeracja odcieni (ważonych chromą) bliższych niż ``merge_deg``; kolory szare
    (C < ``chroma_min``) pomijane. Wynik w kolejności pierwszego wystąpienia członka skupiska."""
    # (najmniejszy indeks, odcienie, wagi)
    clusters = [(i, [c.h], [c.c]) for i, c in enumerate(colors) if c.c >= chroma_min]
    while len(clusters) > 1:
        centers = [_circ_mean(h, w) for _, h, w in clusters]
        best: tuple[float, int, int] | None = None
        for a in range(len(clusters)):
            for b in range(a + 1, len(clusters)):
                d = abs(col.hue_diff(centers[a], centers[b]))
                if d < merge_deg and (best is None or d < best[0]):
                    best = (d, a, b)
        if best is None:
            break
        _, a, b = best
        ia, ha, wa = clusters[a]
        ib, hb, wb = clusters[b]
        clusters[a] = (min(ia, ib), ha + hb, wa + wb)
        del clusters[b]
    clusters.sort(key=lambda c: c[0])
    return tuple(_circ_mean(h, w) for _, h, w in clusters)


# ---------------------------------------------------------------------------
# Dawny kształt „rodzaj + parametry”
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LegacyScheme:
    """Dawny układ odcieni: przepis presetów wbudowanych i kształt starych plików/presetów."""

    kind: LegacyKind
    rotation: float = 0.0
    center: float = 0.0
    spread: float = 90.0
    custom: tuple[float, ...] = ()
    tol: float = 15.0
    jitter: float = 0.0
    hard: bool = False
    weight: float = 1.0


def _legacy_base(s: LegacyScheme, n: int) -> list[float]:
    r = s.rotation
    match s.kind:
        case "equal":
            return [r + 360.0 * i / n for i in range(n)]
        case "analogous":
            if n == 1:
                return [s.center]
            lo = s.center - s.spread / 2.0
            return [lo + s.spread * i / (n - 1) for i in range(n)]
        case "complementary":
            return [r, r + 180.0]
        case "split":
            return [r, r + 150.0, r + 210.0]
        case "triad":
            return [r, r + 120.0, r + 240.0]
        case "tetrad":
            return [r, r + 90.0, r + 180.0, r + 270.0]
        case "custom":
            return list(s.custom)
        case "none":
            return []


def legacy_targets(s: LegacyScheme, n: int) -> Hues:
    """Lista dająca dla akcentów ``0 … n−1`` te same cele co dawny silnik (bez jittera).

    ``custom`` dłuższa niż ``n`` zostaje cała (rodziny: ``hues[i mod k] = hues[i]``); krótsza —
    rozpisana do ``n`` z dawnymi „obiegami”. Pozostałe rodzaje → ``n`` pozycji.
    """
    if s.kind == "custom" and len(s.custom) >= n:
        return _wrap(s.custom)
    if n <= 0:
        return ()
    base = _legacy_base(s, n)
    k = len(base)
    if k == 0:
        return ()
    cycles = -(-n // k)
    step = 360.0 / (k * cycles)
    return _wrap([base[i % k] + (i // k) * step for i in range(n)])


def to_scheme(recipe: HueScheme | LegacyScheme, n_accents: int) -> HueScheme:
    """Układ sesji z przepisu: dawny kształt → ``legacy_targets`` dla ``n_accents`` akcentów."""
    if isinstance(recipe, HueScheme):
        return recipe
    hues = legacy_targets(recipe, n_accents)[:MAX_ACCENTS]
    return HueScheme(
        hues=hues, tol=recipe.tol, jitter=recipe.jitter, hard=recipe.hard, weight=recipe.weight
    )
