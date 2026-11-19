"""Odczyt i zapis zasad dla kilku kolorów naraz (edycja zbiorcza w zakładce „Zasady”). Bez Qt.

Zaznaczenie to lista ``id`` kolorów. Zasadę można pokazać i zmienić tylko wtedy, gdy dotyczy
każdego zaznaczonego koloru (``applicable_fields``). Każda funkcja zapisująca zwraca nową sesję
jednym przebiegiem (jeden krok cofania po stronie interfejsu) albo tę samą, gdy nic się nie zmienia.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

from algopalette.model import (
    RULE_FIELDS,
    HueArc,
    HueScheme,
    Rule,
    RulesLock,
    Session,
    Slot,
    role_of,
    rule_fields_for,
    slot_index,
)


@dataclass(frozen=True)
class Merged:
    """Zasada jednego pola widziana przez całe zaznaczenie.

    ``same`` — wszystkie kolory mają identyczną zasadę (``rule``); ``absent`` — żaden jej nie ma;
    ``mixed`` — kolory różnią się wartością, włączeniem, twardością, wagą albo samą obecnością
    zasady; ``rule`` to wtedy zasada pierwszego zaznaczonego koloru, który ją ma.
    """

    state: Literal["same", "mixed", "absent"]
    rule: Rule[Any] | None
    per_slot: tuple[tuple[str, Rule[Any] | None], ...]


def _indices(session: Session, ids: Sequence[str]) -> list[int]:
    if not ids:
        raise ValueError("Brak zaznaczonych kolorów")
    return [slot_index(session, sid) for sid in ids]


def _check_field(session: Session, ids: Sequence[str], field: str) -> list[int]:
    if field not in RULE_FIELDS:
        raise ValueError(f"Nieznana zasada: {field}")
    indices = _indices(session, ids)
    for i in indices:
        if field not in rule_fields_for(role_of(i)):
            raise ValueError(f"Zasada „{field}” nie dotyczy koloru {session.slots[i].id}")
    return indices


def applicable_fields(session: Session, ids: Sequence[str]) -> tuple[str, ...]:
    """Zasady dotyczące każdego z zaznaczonych kolorów (część wspólna ról), w kolejności pól."""
    if not ids:
        return ()
    allowed = [rule_fields_for(role_of(slot_index(session, sid))) for sid in ids]
    return tuple(f for f in RULE_FIELDS if all(f in a for a in allowed))


def merged_rule(session: Session, ids: Sequence[str], field: str) -> Merged:
    indices = _check_field(session, ids, field)
    rules = [getattr(session.slots[i].rules, field) for i in indices]
    per_slot = tuple(zip(ids, rules, strict=True))
    present = [r for r in rules if r is not None]
    if not present:
        return Merged("absent", None, per_slot)
    if len(present) == len(rules) and all(r == present[0] for r in present):
        return Merged("same", present[0], per_slot)
    return Merged("mixed", present[0], per_slot)


def _rewrite(session: Session, indices: Sequence[int], change: Callable[[Slot], Slot]) -> Session:
    """Podmienia kolory o podanych indeksach na ``change(slot)``; bez zmian → ta sama sesja."""
    slots = list(session.slots)
    dirty = False
    for i in indices:
        new = change(slots[i])
        if new != slots[i]:
            slots[i] = new
            dirty = True
    return replace(session, slots=tuple(slots)) if dirty else session


def set_rule(session: Session, ids: Sequence[str], field: str, rule: Rule[Any] | None) -> Session:
    """Nadaje wszystkim zaznaczonym tę samą zasadę; ``None`` usuwa ją u wszystkich."""
    indices = _check_field(session, ids, field)
    return _rewrite(session, indices, lambda s: replace(s, rules=replace(s.rules, **{field: rule})))


def update_rule(session: Session, ids: Sequence[str], field: str, **changes: Any) -> Session:
    """Zmienia pola zasady (``value``, ``enabled``, ``hard``, ``weight``) tam, gdzie zasada
    istnieje; koloru bez tej zasady nie rusza (zasada nie powstaje)."""
    indices = _check_field(session, ids, field)
    unknown = set(changes) - {"value", "enabled", "hard", "weight"}
    if unknown:
        raise ValueError(f"Nieznane pole zasady: {', '.join(sorted(unknown))}")

    def change(slot: Slot) -> Slot:
        rule = getattr(slot.rules, field)
        if rule is None:
            return slot
        return replace(slot, rules=replace(slot.rules, **{field: replace(rule, **changes)}))

    return _rewrite(session, indices, change)


def _accent_indices(session: Session, ids: Sequence[str]) -> list[int]:
    indices = _indices(session, ids)
    for i in indices:
        if role_of(i) != "accent":
            raise ValueError("Układ odcieni dotyczy tylko akcentów")
    return indices


def merged_use_scheme(session: Session, ids: Sequence[str]) -> bool | None:
    """Czy zaznaczone akcenty biorą cel z układu odcieni; ``None`` = różnie."""
    values = {session.slots[i].use_scheme for i in _accent_indices(session, ids)}
    return values.pop() if len(values) == 1 else None


def set_use_scheme(session: Session, ids: Sequence[str], on: bool) -> Session:
    return _rewrite(session, _accent_indices(session, ids), lambda s: replace(s, use_scheme=on))


# ---------------------------------------------------------------------------
# Kłódka zasad
# ---------------------------------------------------------------------------


def merged_rules_lock(session: Session, ids: Sequence[str]) -> RulesLock | None:
    """Kłódka zasad zaznaczonych kolorów; ``None`` = różnie."""
    values = {session.slots[i].rules_lock for i in _indices(session, ids)}
    return values.pop() if len(values) == 1 else None


def set_rules_lock(
    session: Session, ids: Sequence[str], mode: RulesLock, targets: Mapping[str, float]
) -> Session:
    """Zakłada (``"rules"``, ``"hue"``) albo zdejmuje (``"off"``) kłódkę zasad zaznaczonym.

    ``"hue"`` zamraża przy tym bieżący cel układu odcieni (``targets``: ``id`` → stopnie, jak
    ``engine.hue_targets``) we własnej zasadzie odcienia akcentu i wyłącza mu ``use_scheme`` — po
    zmianie presetu (i układu) kolor trzyma ten sam odcień. Kolor bez celu (tło, tekst, akcent bez
    ``use_scheme``, pusta lista układu) dostaje samą kłódkę. Zdjęcie kłódki niczego nie przywraca.
    """
    scheme = session.globals.hue_scheme
    indices = _indices(session, ids)
    accents = {session.slots[i].id for i in indices if role_of(i) == "accent"}

    def change(slot: Slot) -> Slot:
        slot = replace(slot, rules_lock=mode)
        target = targets.get(slot.id)
        frozen = mode == "hue" and slot.id in accents and slot.use_scheme
        if not frozen or not scheme.hues or target is None:
            return slot
        return replace(
            slot,
            rules=replace(slot.rules, hue=_frozen_hue(slot.rules.hue, target, scheme)),
            use_scheme=False,
        )

    return _rewrite(session, indices, change)


def _frozen_hue(own: Rule[HueArc] | None, target: float, scheme: HueScheme) -> Rule[HueArc]:
    """Zasada odcienia równoważna dotychczasowym ograniczeniom: cel układu ± tolerancja, zawężony do
    własnego łuku koloru (gdy był włączony i łuki się przecinają; własne zakazy zostają)."""
    # (początek, szerokość)
    arc = (0.0, 360.0) if scheme.tol >= 180.0 else ((target - scheme.tol) % 360.0, 2.0 * scheme.tol)
    if own is None or not own.enabled:
        return Rule(_arc(*arc), hard=scheme.hard, weight=scheme.weight)
    common = _intersect(arc, (own.value.lo, _width(own.value.lo, own.value.hi)))
    if common is None:  # sprzeczne już wcześniej — wygrywa cel, który widać w edytorze
        return Rule(_arc(*arc), hard=scheme.hard, weight=scheme.weight)
    return Rule(
        replace(_arc(*common), exclude=own.value.exclude),
        hard=own.hard or scheme.hard,
        weight=max(own.weight, scheme.weight),
    )


def _width(lo: float, hi: float) -> float:
    """Szerokość łuku jak ``arc_width`` w silniku: ``lo > hi`` przez 0°, ``0, 360`` = pełne koło."""
    w = (hi - lo) % 360.0
    return 360.0 if w == 0.0 and lo != hi else w


def _arc(start: float, width: float) -> HueArc:
    if width >= 360.0:
        return HueArc(0.0, 360.0)
    start %= 360.0
    return HueArc(round(start, 6), round((start + width) % 360.0, 6))


def _intersect(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float] | None:
    """Część wspólna łuków ``(początek, szerokość)``; z dwóch kawałków — dłuższy."""
    (a0, aw), (b0, bw) = a, b
    if aw >= 360.0:
        return b
    if bw >= 360.0:
        return a
    d = (b0 - a0) % 360.0  # początek b w układzie, w którym a = [0, aw]
    pieces = []
    for lo in (d - 360.0, d):
        start, end = max(0.0, lo), min(aw, lo + bw)
        if end >= start:
            pieces.append((start, end - start))
    if not pieces:
        return None
    start, width = max(pieces, key=lambda p: p[1])
    return ((a0 + start) % 360.0, width)
