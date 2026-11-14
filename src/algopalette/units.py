"""Przeliczanie progów przy zmianie metody ΔE albo metryki kontrastu (przegląd I1).

Progi warunków są liczbami w jednostkach metody/metryki. Po zmianie metody 0.08 „ok” nie może
zostać 0.08 „2000” — przeliczamy przybliżonymi skalami (mediana stosunku na bliskich parach
kolorów, zmierzona 2026-11-14:
hyab 1.3, 2000 156, itp 426, cam16 156 × ΔE ok) i odwzorowaniem WCAG ↔ APCA (punkty orientacyjne).
"""

from dataclasses import replace

import numpy as np

from algopalette.model import (
    Cond,
    ContrastBound,
    ContrastMetric,
    DeltaEMethod,
    Relation,
    Session,
    Slot,
)

DE_SCALE: dict[str, float] = {"ok": 1.0, "hyab": 1.3, "2000": 156.0, "itp": 426.0, "cam16": 156.0}
# WCAG ratio ↔ APCA |Lc| (orientacyjne odpowiedniki progów czytelności).
_WCAG = np.array([1.0, 3.0, 4.5, 7.0, 10.0, 15.0, 21.0])
_APCA = np.array([0.0, 45.0, 60.0, 75.0, 90.0, 100.0, 106.0])


def convert_de(v: float, old: str, new: str) -> float:
    return v * DE_SCALE[new] / DE_SCALE[old]


def convert_contrast(v: float, old: str, new: str) -> float:
    if old == new:
        return v
    if old == "wcag21":
        return float(np.interp(v, _WCAG, _APCA))
    return float(np.interp(v, _APCA, _WCAG))


def default_distance(method: str, ok_value: float) -> float:
    return ok_value * DE_SCALE[method]


def _c(cond, fn):
    return None if cond is None else replace(cond, value=fn(cond.value))


def _bound(b: ContrastBound, f) -> ContrastBound:
    return ContrastBound(
        b.metric, None if b.lo is None else f(b.lo), None if b.hi is None else f(b.hi)
    )


def rescale_delta_e(session: Session, old: DeltaEMethod, new: DeltaEMethod) -> Session:
    """Progi odległości w metodzie globalnej (role, sloty, relacje bez metody) → nowa metoda."""
    if old == new:
        return session

    def f(v: float) -> float:
        return convert_de(float(v), old, new)

    g = session.globals
    rd = {
        r: replace(
            sc, min_distance=_c(sc.min_distance, f), cvd_min_distance=_c(sc.cvd_min_distance, f)
        )
        for r, sc in g.role_defaults.items()
    }

    def slot(s: Slot) -> Slot:
        sc = s.conditions
        sc = replace(
            sc, min_distance=_c(sc.min_distance, f), cvd_min_distance=_c(sc.cvd_min_distance, f)
        )
        rels = tuple(
            replace(r, value=f(r.value), tol=f(r.tol))
            if r.kind == "distance" and r.metric is None
            else r
            for r in s.relations
        )
        return replace(s, conditions=sc, relations=rels)

    return replace(
        session,
        globals=replace(g, delta_e=new, role_defaults=rd),
        slots=tuple(slot(s) for s in session.slots),
    )


def rescale_contrast_metric(session: Session, old: ContrastMetric, new: ContrastMetric) -> Session:
    """Własne warunki kontrastu slotów i relacje kontrastu z metryką globalną → nowa metryka.
    (Domyślne warunki ról przelicza osobno zmiana metryki: nastrój / ``default_role_defaults``.)"""
    if old == new:
        return session

    def f(v: float) -> float:
        return convert_contrast(v, old, new)

    def slot(s: Slot) -> Slot:
        cb = s.conditions.contrast_bg
        sc = s.conditions
        if cb is not None and cb.value.metric is None:
            sc = replace(sc, contrast_bg=Cond(_bound(cb.value, f), cb.enabled, cb.hard, cb.weight))
        rels = tuple(_rel(r, f) for r in s.relations)
        return replace(s, conditions=sc, relations=rels)

    return replace(session, slots=tuple(slot(s) for s in session.slots))


def _rel(r: Relation, f) -> Relation:
    if r.kind != "contrast" or r.metric is not None:
        return r
    lo, hi = f(r.value - r.tol), f(r.value + r.tol)
    return replace(r, value=f(r.value), tol=max(0.0, (hi - lo) / 2))
