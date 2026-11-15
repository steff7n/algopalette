"""Odczyt i zapis zasad dla kilku kolorów naraz (edycja zbiorcza w zakładce „Zasady”). Bez Qt.

Zaznaczenie to lista ``id`` kolorów. Zasadę można pokazać i zmienić tylko wtedy, gdy dotyczy
każdego zaznaczonego koloru (``applicable_fields``). Każda funkcja zapisująca zwraca nową sesję
jednym przebiegiem (jeden krok cofania po stronie interfejsu) albo tę samą, gdy nic się nie zmienia.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

from algopalette.model import (
    RULE_FIELDS,
    Rule,
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
