"""Przeliczanie progów przy zmianie metody ΔE albo metryki kontrastu.

Progi zasad są liczbami w jednostkach metody/metryki. Po zmianie metody 0.08 „ok” nie może
zostać 0.08 „2000” — przeliczamy przybliżonymi skalami (mediana stosunku na bliskich parach
kolorów, zmierzona 2026-11-14:
hyab 1.3, 2000 156, itp 426, cam16 156 × ΔE ok) i odwzorowaniem WCAG ↔ APCA (punkty orientacyjne).
"""

from collections.abc import Callable
from dataclasses import replace

import numpy as np

from algopalette.model import (
    ContrastBound,
    ContrastMetric,
    DeltaEMethod,
    Relation,
    Rule,
    Session,
    Slot,
    SlotRules,
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


def rules_in_method(rules: SlotRules, old: str, new: str) -> SlotRules:
    """Zasady koloru z progiem odległości przeliczonym z metody ``old`` na ``new``.

    Zasady budowane od zera (``default_rules``, presety wbudowane, tryby Źródła) mają progi
    w skali ``ok``; trafiają do sesji z inną metodą ΔE tylko przez tę funkcję (przegląd
    2026-11-18 C1: inaczej 0.08 lądowało jako „0.08 CIEDE2000” i zasada przestawała działać)."""
    if old == new or rules.min_distance is None:
        return rules
    scaled = _scaled(rules.min_distance, lambda v: convert_de(v, old, new))
    return replace(rules, min_distance=scaled)


def _scaled(rule: Rule[float] | None, f: Callable[[float], float]) -> Rule[float] | None:
    return None if rule is None else replace(rule, value=f(rule.value))


def _bound(b: ContrastBound, f: Callable[[float], float]) -> ContrastBound:
    return ContrastBound(
        b.metric, None if b.lo is None else f(b.lo), None if b.hi is None else f(b.hi)
    )


def rescale_delta_e(session: Session, old: DeltaEMethod, new: DeltaEMethod) -> Session:
    """Ustawia metodę ΔE i przelicza na jej skalę progi odległości w zasadach każdego koloru
    oraz w zależnościach bez własnej metody. Odległość unikania kolorów zostaje (zawsze ΔE ok)."""
    if old == new:
        return session

    def f(v: float) -> float:
        return convert_de(float(v), old, new)

    def slot(s: Slot) -> Slot:
        rules = replace(
            s.rules,
            min_distance=_scaled(s.rules.min_distance, f),
        )
        rels = tuple(
            replace(r, value=f(r.value), tol=f(r.tol))
            if r.kind == "distance" and r.metric is None
            else r
            for r in s.relations
        )
        return replace(s, rules=rules, relations=rels)

    return replace(
        session,
        globals=replace(session.globals, delta_e=new),
        slots=tuple(slot(s) for s in session.slots),
    )


def rescale_contrast_metric(session: Session, old: ContrastMetric, new: ContrastMetric) -> Session:
    """Przelicza progi kontrastu w zasadach kolorów i zależnościach, które używają metryki
    palety (bez własnej). Samej metryki nie zmienia — robi to ``globals_logic.change_metric``."""
    if old == new:
        return session

    def f(v: float) -> float:
        return convert_contrast(v, old, new)

    def slot(s: Slot) -> Slot:
        cb = s.rules.contrast_bg
        rules = s.rules
        if cb is not None and cb.value.metric is None:
            rules = replace(rules, contrast_bg=replace(cb, value=_bound(cb.value, f)))
        return replace(s, rules=rules, relations=tuple(_rel(r, f) for r in s.relations))

    return replace(session, slots=tuple(slot(s) for s in session.slots))


def _rel(r: Relation, f: Callable[[float], float]) -> Relation:
    if r.kind != "contrast" or r.metric is not None:
        return r
    lo, hi = f(r.value - r.tol), f(r.value + r.tol)
    return replace(r, value=f(r.value), tol=max(0.0, (hi - lo) / 2))
