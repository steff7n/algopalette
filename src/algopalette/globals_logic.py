"""Zmiany ustawień globalnych, które pociągają przeliczenie innych wartości (przegląd C4, I1)."""

from dataclasses import replace
from typing import Any

from algopalette.model import DeltaEMethod, Session, default_role_defaults
from algopalette.moods import BUILTIN, apply_mood
from algopalette.units import rescale_contrast_metric, rescale_delta_e


def change_polarity_or_metric(session: Session, **changes: Any) -> Session:
    """Polaryzacja i metryka kontrastu zmieniają liczby domyślnych zakresów.

    Nastrój wbudowany (liczony z polaryzacji i metryki) nakładamy ponownie. Nastrój użytkownika ma
    liczby dla swojej polaryzacji/metryki, więc zdejmujemy go i bierzemy domyślne warunki ról.
    Własne progi kontrastu slotów i relacji (metryka globalna) przeliczamy na nową metrykę.
    """
    old_metric = session.globals.contrast_metric
    g = replace(session.globals, **changes)
    s = replace(session, globals=g)
    if s.mood in BUILTIN:
        s = apply_mood(s, s.mood)
    else:
        g = replace(g, role_defaults=default_role_defaults(g.polarity, g.contrast_metric))
        s = replace(s, globals=g, mood=None, mood_snapshot=None)
    return rescale_contrast_metric(s, old_metric, s.globals.contrast_metric)


def change_delta_e(session: Session, method: DeltaEMethod) -> Session:
    """Nowa metoda ΔE z progami odległości przeliczonymi na jej skalę."""
    return rescale_delta_e(session, session.globals.delta_e, method)
