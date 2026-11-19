"""Import motywu jako bieżącej sesji (spec §7; warianty: spec 2026-11-19-import-motywu-warianty).

Kłódka zasad (``Slot.rules_lock``) chroni zasady koloru w obu trybach; nie chroni jego wartości.
Tryb domyślny daje każdemu kolorowi własne zasady wokół jego wartości z motywu, więc generowanie
zwraca warianty motywu różniące się odcieniem o najwyżej ``spread_deg``.
"""

from __future__ import annotations

from dataclasses import replace
from itertools import combinations

from algopalette import color as col
from algopalette.model import (
    OKLCH,
    Band,
    ChromaBand,
    ContrastBound,
    ContrastMetric,
    HueArc,
    HueScheme,
    Polarity,
    Rule,
    Session,
    Slot,
    SlotRules,
    add_accent,
    arc_from_center,
    default_rules,
    remove_slot,
)
from algopalette.sources import TRANSFER_TOL
from algopalette.themes.model import Palette
from algopalette.units import convert_de

DEFAULT_SPREAD_DEG = 10.0
MAX_SPREAD_DEG = 45.0
# Widełki na każde 10° swobody (skalowane liniowo); minima — żeby zasady nie zwężały się do punktu.
L_PER_10 = 0.05
ACCENT_CHROMA_PER_10 = 0.025  # bezwzględnie: względne przy L ≈ 1 pozwala zbielić kolor
NEUTRAL_CHROMA_PER_10 = 0.01
MIN_HALF_HUE = 0.5
MIN_HALF_L = 0.005
MIN_HALF_CHROMA = 0.002
GREY_CHROMA = 0.02  # poniżej tego odcień nie ma znaczenia — bez zasady odcienia
CONTRAST_FLOOR: dict[str, float] = {"wcag21": 1.0, "apca": 0.0}


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


def _band(center: float, half: float, lo: float = 0.0, hi: float = 1.0) -> tuple[float, float]:
    return max(lo, center - half), min(hi, center + half)


def _variant_rules(
    x: OKLCH,
    bg: OKLCH,
    base: SlotRules,
    *,
    k: float,
    spread_deg: float,
    accent: bool,
    metric: ContrastMetric,
    min_distance: float | None,
) -> SlotRules:
    """Zasady jednego koloru: odcień ± swoboda, jasność/nasycenie blisko ``x``, kontrast ≥ motyw."""
    hue = (
        Rule(HueArc(*arc_from_center(x.h, max(spread_deg, MIN_HALF_HUE))))
        if x.c >= GREY_CHROMA
        else None
    )
    l_lo, l_hi = _band(x.l, max(L_PER_10 * k, MIN_HALF_L))
    per_10 = ACCENT_CHROMA_PER_10 if accent else NEUTRAL_CHROMA_PER_10
    c_lo, c_hi = _band(x.c, max(per_10 * k, MIN_HALF_CHROMA), hi=0.5)
    chroma = Rule(ChromaBand("abs", c_lo, c_hi))
    contrast_bg = None
    if base.contrast_bg is not None:
        c = col.contrast(x, bg, metric)
        floor = max(CONTRAST_FLOOR[metric], c - TRANSFER_TOL[metric] * k)
        contrast_bg = Rule(ContrastBound(None, floor, None))
    return replace(
        base,
        hue=hue,
        lightness=Rule(Band(l_lo, l_hi)),
        chroma=chroma,
        contrast_bg=contrast_bg,
        min_distance=None if min_distance is None else Rule(min_distance, hard=False),
        extreme=None,
    )


def _min_distance(session: Session, accents: tuple[OKLCH, ...]) -> float | None:
    """Miękka odległość akcentów: domyślna, ale nie większa niż najmniejsza ΔE w motywie."""
    base = default_rules("accent").min_distance
    if base is None:
        return None
    method = session.globals.delta_e
    limit = convert_de(base.value, "ok", method)
    gaps = [col.delta_e(a, b, method) for a, b in combinations(accents, 2)]
    return min([limit, *(0.9 * g for g in gaps)])


def variant_session(
    s: Session, values: tuple[OKLCH, ...], spread_deg: float = DEFAULT_SPREAD_DEG
) -> Session:
    """Sesja „pod motyw”: każdy kolor bez kłódki zasad dostaje zasady wokół swojej wartości."""
    spread = min(max(spread_deg, 0.0), MAX_SPREAD_DEG)
    k = spread / 10.0
    g = s.globals
    metric = g.contrast_metric
    bg = values[0]
    polarity: Polarity = "dark" if bg.l < 0.5 else "light"
    min_d = _min_distance(s, values[2:])
    roles = ("bg", "fg")
    slots: list[Slot] = []
    for i, slot in enumerate(s.slots):
        if slot.rules_lock != "off" or i >= len(values):
            slots.append(slot)
            continue
        role = roles[i] if i < 2 else "accent"
        base = default_rules(role, polarity, metric)
        rules = _variant_rules(
            values[i],
            bg,
            base,
            k=k,
            spread_deg=spread,
            accent=role == "accent",
            metric=metric,
            min_distance=min_d if role == "accent" else None,
        )
        slots.append(replace(slot, rules=rules, use_scheme=False))
    g2 = replace(g, polarity=polarity, hue_scheme=HueScheme(), lightness_spread=None)
    return replace(s, globals=g2, slots=tuple(slots), preset=None)


def apply_theme(
    session: Session,
    palette: Palette,
    *,
    keep_settings: bool,
    spread_deg: float = DEFAULT_SPREAD_DEG,
) -> Session:
    """Kolory motywu na kolejne pozycje; ``keep_settings=False`` dopasowuje też ustawienia
    (zasady każdego koloru wokół jego wartości, odcień ± ``spread_deg``).

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
    return variant_session(replace(s, slots=tuple(slots)), values, spread_deg)
