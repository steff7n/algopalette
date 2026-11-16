"""Import motywu jako bieżącej sesji (spec §7).

Kłódka zasad (``Slot.rules_lock``) chroni zasady koloru w obu trybach; nie chroni jego wartości.
"""

from __future__ import annotations

from dataclasses import replace

from algopalette.model import Session, Slot, add_accent, remove_slot
from algopalette.sources import character_settings, extract_profile
from algopalette.themes.model import Palette


def _accents(session: Session) -> int:
    return len(session.slots) - 2


def _fit_count(session: Session, n: int) -> Session:
    """``n`` akcentów: dokłada przez ``add_accent``, usuwa od końca z pominięciem kłódek zasad."""
    while _accents(session) < n:
        session = add_accent(session)
    i = len(session.slots) - 1
    while _accents(session) > n and i >= 2:
        slot = session.slots[i]
        if slot.rules_lock == "off":
            session = remove_slot(session, slot.id)
        i -= 1
    return session


def apply_theme(session: Session, palette: Palette, *, keep_settings: bool) -> Session:
    """Kolory motywu na kolejne pozycje; ``keep_settings=False`` dopasowuje też ustawienia.

    Kłódki wartości są zdejmowane wszędzie (to nowa paleta). Nadmiarowe akcenty z kłódką zasad,
    których nie dało się usunąć, zachowują poprzednią wartość.
    """
    s = _fit_count(session, len(palette.accents))
    values = (palette.bg, palette.fg, *palette.accents)
    names = ("tło", "tekst", *palette.accent_names)
    slots: list[Slot] = []
    for i, slot in enumerate(s.slots):
        if i < len(values):
            slot = replace(slot, value=values[i], name=names[i])
        slots.append(replace(slot, locked=False))
    if keep_settings:
        return replace(s, slots=tuple(slots))
    profile = extract_profile(values, metric=s.globals.contrast_metric)
    cs = character_settings(s, profile)
    by_role = (cs.bg, cs.fg)
    fitted = tuple(
        slot
        if slot.rules_lock != "off"
        else replace(slot, rules=by_role[i] if i < 2 else cs.accent, use_scheme=True)
        for i, slot in enumerate(slots)
    )
    return replace(s, globals=cs.globals, slots=fitted, preset=None)
