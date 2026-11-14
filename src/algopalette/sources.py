"""Paleta wyjściowa: parsowanie wklejonych kolorów i trzy tryby startu (spec §6).

Każdy tryb tylko wypełnia warunki sesji — wynik jest jawny i edytowalny, silnik jest jeden.

* **uzupełnianie** (``apply_complete``) — podane kolory trafiają do kolejnych slotów z kłódką;
* **charakter** (``extract_profile`` + ``apply_character``) — profil palety źródłowej (dominujące
  odcienie, rozkład nasycenia i jasności, zabarwienie tła) ustawia ustawienia globalne;
* **przeniesienie** (``apply_transfer``) — nowe tło; każdy akcent trzyma odcień, nasycenie względne
  i kontrast ze źródła.
"""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

import numpy as np

from algopalette import color as col
from algopalette.model import (
    MAX_ACCENTS,
    OKLCH,
    ChromaRange,
    Cond,
    ContrastBound,
    ContrastMetric,
    HueScheme,
    HueTarget,
    Interval,
    Session,
    SlotConditions,
    add_accent,
    default_role_defaults,
    remove_slot,
)

MAX_COLORS = MAX_ACCENTS + 2
TOKEN = re.compile(r"[A-Za-z][\w-]*\([^)]*\)|[^\s,;]+")
HUE_MERGE_DEG = 25.0  # klastry odcieni bliższe niż tyle stopni łączą się
CHROMA_MIN = 0.03  # akcenty o mniejszej chromie nie wnoszą odcienia do profilu
TRANSFER_TOL: dict[str, float] = {"wcag21": 0.5, "apca": 5.0}


class ParseError(ValueError):
    """Błąd wklejonej listy kolorów; ``token`` = fragment, którego nie udało się odczytać."""

    def __init__(self, message: str, token: str | None = None) -> None:
        super().__init__(message)
        self.token = token


def parse_colors(text: str) -> list[OKLCH]:
    """Hexy, ``oklch()`` i inne zapisy CSS; separatory: spacje, przecinki, średniki, linie."""
    tokens = TOKEN.findall(text)
    if not tokens:
        raise ParseError("Brak kolorów do odczytania.")
    if len(tokens) > MAX_COLORS:
        raise ParseError(f"Najwyżej {MAX_COLORS} kolorów (podano {len(tokens)}).")
    out: list[OKLCH] = []
    for tok in tokens:
        try:
            out.append(col.from_css(tok))
        except ValueError:
            raise ParseError(f"Nie można odczytać koloru „{tok}”.", tok) from None
    return out


def colors_from_session(session: Session) -> list[OKLCH]:
    """Kolory slotów sesji w kolejności (tło = 0, tekst = 1)."""
    return [s.value for s in session.slots]


def _order(
    colors: Sequence[OKLCH], bg_index: int, fg_index: int
) -> tuple[OKLCH, OKLCH | None, list[OKLCH]]:
    if not colors:
        raise ParseError("Brak kolorów.")
    n = len(colors)
    if not 0 <= bg_index < n:
        raise ParseError("Indeks tła poza listą kolorów.")
    if n > 1 and (not 0 <= fg_index < n or fg_index == bg_index):
        raise ParseError("Indeks tekstu poza listą albo równy indeksowi tła.")
    bg = colors[bg_index]
    fg = colors[fg_index] if n > 1 else None
    rest = [c for i, c in enumerate(colors) if i not in (bg_index, fg_index if n > 1 else -1)]
    if len(rest) > MAX_ACCENTS:
        raise ParseError(f"Najwyżej {MAX_ACCENTS} akcentów.")
    return bg, fg, rest


def _ensure_accents(session: Session, count: int) -> Session:
    while len(session.slots) - 2 < count:
        session = add_accent(session)
    return session


def apply_complete(
    session: Session, colors: Sequence[OKLCH], bg_index: int = 0, fg_index: int = 1
) -> Session:
    """Uzupełnianie: kolory → kolejne sloty z kłódką (tło, tekst, akcenty); reszta zostaje wolna."""
    bg, fg, rest = _order(colors, bg_index, fg_index)
    session = _ensure_accents(session, len(rest))
    slots = list(session.slots)
    slots[0] = replace(slots[0], value=bg, locked=True)
    if fg is not None:
        slots[1] = replace(slots[1], value=fg, locked=True)
    for k, c in enumerate(rest):
        slots[2 + k] = replace(slots[2 + k], value=c, locked=True)
    return replace(session, slots=tuple(slots))


# ---------------------------------------------------------------------------
# Charakter
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Profile:
    hues: tuple[float, ...]  # dominujące odcienie, od najsilniejszego
    rel_chroma: Interval  # p10–p90 nasycenia względnego akcentów
    lightness: Interval  # p10–p90 jasności akcentów
    bg: OKLCH
    fg: OKLCH | None
    accents: tuple[OKLCH, ...]
    contrasts: tuple[float, ...]  # kontrast akcentów z tłem (metryka profilu)
    metric: ContrastMetric


def _circ_mean(hs: Sequence[float], ws: Sequence[float]) -> float:
    r = np.radians(np.asarray(hs))
    w = np.asarray(ws)
    return float(
        np.degrees(math.atan2(float((w * np.sin(r)).sum()), float((w * np.cos(r)).sum()))) % 360
    )


def cluster_hues(accents: Sequence[OKLCH], merge_deg: float = HUE_MERGE_DEG) -> list[float]:
    """Aglomeracyjne łączenie odcieni (ważonych chromą) bliższych niż ``merge_deg``."""
    clusters = [([a.h], [a.c]) for a in accents if a.c >= CHROMA_MIN]
    while len(clusters) > 1:
        centers = [_circ_mean(h, w) for h, w in clusters]
        best: tuple[float, int, int] | None = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                d = abs(col.hue_diff(centers[i], centers[j]))
                if d < merge_deg and (best is None or d < best[0]):
                    best = (d, i, j)
        if best is None:
            break
        _, i, j = best
        hi, wi = clusters[i]
        hj, wj = clusters[j]
        clusters[i] = (hi + hj, wi + wj)
        del clusters[j]
    clusters.sort(key=lambda c: -sum(c[1]))
    return [_circ_mean(h, w) for h, w in clusters]


def _pct(values: Sequence[float]) -> Interval:
    a = np.asarray(values, dtype=float)
    return Interval(float(np.percentile(a, 10)), float(np.percentile(a, 90)))


def extract_profile(
    colors: Sequence[OKLCH], bg_index: int = 0, fg_index: int = 1, metric: ContrastMetric = "wcag21"
) -> Profile:
    bg, fg, rest = _order(colors, bg_index, fg_index)
    if not rest:
        raise ParseError("Profil wymaga co najmniej jednego akcentu.")
    rel = [a.c / max(col.max_chroma(a.l, a.h), 1e-9) for a in rest]
    return Profile(
        hues=tuple(cluster_hues(rest)),
        rel_chroma=_pct([min(r, 1.0) for r in rel]),
        lightness=_pct([a.l for a in rest]),
        bg=bg,
        fg=fg,
        accents=tuple(rest),
        contrasts=tuple(col.contrast(a, bg, metric) for a in rest),
        metric=metric,
    )


def _widen(iv: Interval, by: float, lo: float = 0.0, hi: float = 1.0) -> Interval:
    a = iv.lo if iv.lo is not None else lo
    b = iv.hi if iv.hi is not None else hi
    return Interval(max(lo, a - by), min(hi, b + by))


def apply_character(
    session: Session, profile: Profile, avoid_source: bool = False, avoid_distance: float = 0.05
) -> Session:
    """Charakter: ustawienia globalne z profilu (odcienie, zakresy, tło); sloty wolne."""
    g = session.globals
    polarity = "dark" if profile.bg.l < 0.5 else "light"
    rd = dict(default_role_defaults(polarity, g.contrast_metric))
    rd["accent"] = replace(
        rd["accent"],
        lightness=Cond(_widen(profile.lightness, 0.03)),
        chroma=Cond(ChromaRange("rel", *_bounds(_widen(profile.rel_chroma, 0.05)))),
    )
    bg = profile.bg
    rd["bg"] = replace(
        rd["bg"],
        lightness=Cond(Interval(max(0.0, bg.l - 0.03), min(1.0, bg.l + 0.03))),
        chroma=Cond(ChromaRange("abs", max(0.0, bg.c - 0.01), bg.c + 0.01)),
        hue_target=Cond(HueTarget(bg.h, 20.0), hard=False) if bg.c >= 0.01 else None,
    )
    hues = profile.hues or (0.0,)
    custom = tuple((list(hues) * MAX_ACCENTS)[:MAX_ACCENTS])
    g2 = replace(
        g,
        polarity=polarity,
        role_defaults=rd,
        hue_scheme=HueScheme("custom", custom=custom, tol=15.0),
        avoid_colors=profile.accents if avoid_source else (),
        avoid_distance=avoid_distance if avoid_source else 0.0,
    )
    slots = tuple(replace(s, locked=False) for s in session.slots)
    return replace(session, globals=g2, slots=slots, mood=None, mood_snapshot=None)


def _bounds(iv: Interval) -> tuple[float | None, float | None]:
    return iv.lo, iv.hi


# ---------------------------------------------------------------------------
# Przeniesienie
# ---------------------------------------------------------------------------


def apply_transfer(
    session: Session,
    colors: Sequence[OKLCH],
    bg_index: int = 0,
    fg_index: int = 1,
    polarity: str = "light",
    tol: float | None = None,
) -> Session:
    """Przeniesienie na tło o innej polaryzacji: odcień, nasycenie wzgl. i kontrast ze źródła."""
    if polarity not in ("dark", "light"):
        raise ValueError("Polaryzacja musi być „dark” albo „light”.")
    g = session.globals
    metric = g.contrast_metric
    tol = TRANSFER_TOL[metric] if tol is None else tol
    src_bg, src_fg, rest = _order(colors, bg_index, fg_index)
    session = _ensure_accents(session, len(rest))
    while len(session.slots) - 2 > max(len(rest), 1):
        session = remove_slot(session, session.slots[-1].id)
    rd = default_role_defaults(polarity, metric)  # type: ignore[arg-type]
    rd_bg = rd["bg"]
    if src_bg.c >= 0.01:
        rd_bg = replace(rd_bg, hue_target=Cond(HueTarget(src_bg.h, 20.0), hard=False))
    g2 = replace(
        g,
        polarity=polarity,  # type: ignore[arg-type]
        role_defaults={**rd, "bg": rd_bg},
        hue_scheme=HueScheme("none"),
        avoid_colors=(),
        avoid_distance=0.0,
    )
    slots = list(session.slots)
    slots[0] = replace(slots[0], locked=False, conditions=SlotConditions())
    if src_fg is not None:
        slots[1] = replace(
            slots[1], locked=False, conditions=_transfer_conditions(src_fg, src_bg, metric, tol)
        )
    for k, c in enumerate(rest):
        slots[2 + k] = replace(
            slots[2 + k],
            locked=False,
            conditions=_transfer_conditions(c, src_bg, metric, tol),
            relations=(),
        )
    return replace(session, globals=g2, slots=tuple(slots), mood=None, mood_snapshot=None)


def _transfer_conditions(
    c: OKLCH, src_bg: OKLCH, metric: ContrastMetric, tol: float
) -> SlotConditions:
    rel = min(c.c / max(col.max_chroma(c.l, c.h), 1e-9), 1.0)
    contrast = col.contrast(c, src_bg, metric)
    return SlotConditions(
        hue_target=Cond(HueTarget(c.h, 8.0)) if c.c >= 0.02 else None,
        chroma=Cond(ChromaRange("rel", max(0.0, rel - 0.08), min(1.0, rel + 0.08))),
        # Jasność wynika z kontrastu — wyłączamy zakres dziedziczony z roli.
        lightness=Cond(Interval(None, None), enabled=False),
        contrast_bg=Cond(
            ContrastBound(
                metric, max(1.0 if metric == "wcag21" else 0.0, contrast - tol), contrast + tol
            )
        ),
    )
