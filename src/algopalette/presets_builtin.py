"""Deklaracje presetów wbudowanych.

Preset to funkcja ``(polaryzacja, metryka kontrastu) → PresetRules``: zasady tła, tekstu i akcentu,
opcjonalne nadpisania dla konkretnych akcentów, układ odcieni i rozrzut jasności. Liczby zależą od
polaryzacji (zakresy jasności) i metryki (progi kontrastu), dlatego są funkcją, nie tabelą.
Nakładaniem zajmuje się ``presets.apply_preset``.

Dziewięć presetów o nazwach z ``migrate.OLD_MOODS`` to dawne nastroje — ich zasady są zamrożone
(test porównuje je z migracją sesji wzorcowych starego silnika).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from algopalette.model import (
    Band,
    ChromaBand,
    ContrastBound,
    ContrastMetric,
    CvdSettings,
    CvdType,
    HueArc,
    HueScheme,
    Interval,
    Polarity,
    Rule,
    SlotRules,
    arc_from_center,
    default_rules,
)

CATEGORIES: tuple[str, ...] = (
    "Podstawowe",
    "Chłodne",
    "Ciepłe",
    "Natura",
    "Pastelowe",
    "Świecące",
    "Retro i druk",
    "Ograniczone",
    "Harmonie",
    "Pory dnia",
    "Dostępność",
)


SchemeKind = Literal["complementary", "split", "triad", "tetrad", "analogous"]

EQUAL = HueScheme("equal")  # układ presetu, który nie podaje własnego


@dataclass(frozen=True)
class AccentOverride:
    """Nadpisanie zasad jednego akcentu: pola ``SlotRules`` do podmiany i ``use_scheme``."""

    changes: Mapping[str, Rule[Any] | None] = field(default_factory=dict)
    use_scheme: bool | None = None


@dataclass(frozen=True)
class PresetRules:
    bg: SlotRules
    fg: SlotRules
    accent: SlotRules  # ten sam zestaw dla każdego akcentu bez nadpisania
    overrides: Mapping[int, AccentOverride] = field(default_factory=dict)  # numer akcentu od 1
    hue_scheme: HueScheme = EQUAL
    lightness_spread: Rule[Interval] | None = None
    use_scheme: bool = True  # czy akcenty bez nadpisania biorą cel z układu odcieni
    cvd: CvdSettings | None = None  # None = preset nie rusza ustawień daltonizmu
    contrast_metric: ContrastMetric | None = None  # None = metryka sesji


Builder = Callable[[Polarity, ContrastMetric], PresetRules]


@dataclass(frozen=True)
class PresetDef:
    name: str
    category: str
    description: str
    polarities: tuple[Polarity, ...]
    build: Builder


BOTH: tuple[Polarity, ...] = ("dark", "light")


def _rules(
    pol: Polarity,
    metric: ContrastMetric,
    *,
    bg: Mapping[str, Any] | None = None,
    fg: Mapping[str, Any] | None = None,
    accent: Mapping[str, Any] | None = None,
    **extra: Any,
) -> PresetRules:
    """Zasady presetu „neutralny” z podmienionymi polami ról."""
    return PresetRules(
        bg=replace(default_rules("bg", pol, metric), **(bg or {})),
        fg=replace(default_rules("fg", pol, metric), **(fg or {})),
        accent=replace(default_rules("accent", pol, metric), **(accent or {})),
        **extra,
    )


def _pick(pol: Polarity, dark: tuple[float, float], light: tuple[float, float]) -> Rule[Band]:
    lo, hi = dark if pol == "dark" else light
    return Rule(Band(lo, hi))


def _contrast(metric: ContrastMetric, wcag: float, apca: float) -> Rule[ContrastBound]:
    return Rule(ContrastBound(None, wcag if metric == "wcag21" else apca, None))


def _abs(lo: float, hi: float) -> Rule[ChromaBand]:
    return Rule(ChromaBand("abs", lo, hi))


def _rel(lo: float, hi: float) -> Rule[ChromaBand]:
    return Rule(ChromaBand("rel", lo, hi))


def _arc(lo: float, hi: float, *, hard: bool = True) -> Rule[HueArc]:
    return Rule(HueArc(lo, hi), hard=hard)


def _around(center: float, half: float, *, hard: bool = True) -> Rule[HueArc]:
    return Rule(HueArc(*arc_from_center(center, half)), hard=hard)


# --- dziewięć dawnych nastrojów (zasady zamrożone) ---------------------------------------------


def _neutral(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(pol, metric)


def _cool_misty(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.01, 0.03), "hue": _arc(200.0, 260.0, hard=False)},
        accent={"lightness": _pick(pol, (0.66, 0.80), (0.40, 0.52)), "chroma": _abs(0.03, 0.09)},
        hue_scheme=HueScheme("analogous", center=220.0, spread=110.0, tol=15.0),
        lightness_spread=Rule(Interval(None, 0.12), hard=False),
    )


def _neon(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"lightness": _pick(pol, (0.08, 0.14), (0.95, 0.99)), "chroma": _abs(0.0, 0.02)},
        accent={"lightness": _pick(pol, (0.66, 0.86), (0.45, 0.60)), "chroma": _rel(0.85, 1.0)},
        hue_scheme=HueScheme("equal", rotation=330.0, tol=20.0),
    )


EARTH = (30.0, 60.0, 90.0, 140.0, 15.0, 45.0, 75.0, 110.0, 25.0, 55.0, 125.0, 40.0, 95.0, 65.0)


def _earthy(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.01, 0.03), "hue": _arc(40.0, 80.0, hard=False)},
        accent={"lightness": _pick(pol, (0.58, 0.78), (0.38, 0.55)), "chroma": _abs(0.04, 0.11)},
        hue_scheme=HueScheme("custom", custom=EARTH, tol=12.0),
    )


def _pastel(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        accent={"lightness": _pick(pol, (0.84, 0.93), (0.55, 0.65)), "chroma": _rel(0.22, 0.42)},
        hue_scheme=HueScheme("equal", rotation=10.0, tol=15.0),
    )


def _night_contrast(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"lightness": _pick(pol, (0.04, 0.10), (0.97, 1.0)), "chroma": _abs(0.0, 0.015)},
        fg={
            "lightness": _pick(pol, (0.95, 0.995), (0.05, 0.15)),
            "contrast_bg": _contrast(metric, 15.0, 100.0),
        },
        accent={
            # Ciemne tło + APCA: |Lc| ≥ 75 wymaga L ≥ 0.803, więc dawny zakres 0.70–0.80 był
            # niespełnialny (stary silnik: 0 z 6 propozycji bez twardych naruszeń).
            "lightness": _pick(
                pol, (0.80, 0.92) if metric == "apca" else (0.70, 0.80), (0.30, 0.42)
            ),
            "chroma": _abs(0.08, 0.16),
            "contrast_bg": _contrast(metric, 7.0, 75.0),
        },
        hue_scheme=HueScheme("equal", rotation=20.0, tol=15.0),
    )


MONO = (35.0,) + (220.0,) * 13


def _mono_accent(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        accent={
            "lightness": _pick(pol, (0.55, 0.92), (0.25, 0.60)),
            "chroma": _abs(0.02, 0.12),
            "min_distance": Rule(0.04, hard=False),
        },
        # Pierwszy akcent ciepły (35°), reszta w jednym odcieniu 220°.
        hue_scheme=HueScheme("custom", custom=MONO, tol=10.0, hard=True),
        lightness_spread=Rule(Interval(0.25, None), hard=False),
    )


PHOSPHOR = (
    145.0,
    120.0,
    85.0,
    60.0,
    170.0,
    100.0,
    135.0,
    75.0,
    155.0,
    110.0,
    95.0,
    65.0,
    180.0,
    125.0,
)


def _retro(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.01, 0.03), "hue": _around(145.0, 20.0, hard=False)},
        fg={"hue": _around(140.0, 25.0, hard=False)},
        accent={"lightness": _pick(pol, (0.62, 0.86), (0.35, 0.55)), "chroma": _abs(0.08, 0.18)},
        hue_scheme=HueScheme("custom", custom=PHOSPHOR, tol=10.0),
    )


AUTUMN = (30.0, 55.0, 80.0, 15.0, 45.0, 100.0, 65.0, 25.0, 40.0, 90.0, 20.0, 70.0, 50.0, 35.0)


def _autumn(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.01, 0.025), "hue": _arc(25.0, 60.0, hard=False)},
        accent={"lightness": _pick(pol, (0.60, 0.80), (0.38, 0.55)), "chroma": _abs(0.08, 0.16)},
        hue_scheme=HueScheme("custom", custom=AUTUMN, tol=10.0),
    )


# --- nowe presety (liczby strojone na silniku: każdy daje ≥ 5 z 6 propozycji bez twardych
# naruszeń dla każdej obsługiwanej polaryzacji, obu metryk, przy 10 i 7 kolorach) ---------------

DARK: tuple[Polarity, ...] = ("dark",)
LIGHT: tuple[Polarity, ...] = ("light",)


def _custom(hues: tuple[float, ...], tol: float = 12.0, *, hard: bool = False) -> HueScheme:
    return HueScheme("custom", custom=hues, tol=tol, hard=hard)


def _fan(center: float, spread: float, tol: float = 12.0) -> HueScheme:
    return HueScheme("analogous", center=center, spread=spread, tol=tol)


def _soft(value: Any, weight: float = 1.0) -> Rule[Any]:
    return Rule(value, hard=False, weight=weight)


def _contrast_band(
    metric: ContrastMetric, wcag: tuple[float, float | None], apca: tuple[float, float | None]
) -> Rule[ContrastBound]:
    lo, hi = wcag if metric == "wcag21" else apca
    return Rule(ContrastBound(None, lo, hi))


def _muted(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.0, 0.02)},
        accent={"lightness": _pick(pol, (0.62, 0.80), (0.40, 0.56)), "chroma": _abs(0.04, 0.10)},
        hue_scheme=HueScheme("equal", rotation=15.0, tol=20.0),
    )


def _vivid(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        accent={"lightness": _pick(pol, (0.64, 0.84), (0.42, 0.58)), "chroma": _rel(0.65, 0.95)},
        hue_scheme=HueScheme("equal", rotation=20.0, tol=15.0),
    )


def _high_contrast(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"lightness": _pick(pol, (0.08, 0.16), (0.96, 1.0)), "chroma": _abs(0.0, 0.02)},
        fg={
            "lightness": _pick(pol, (0.90, 0.98), (0.10, 0.22)),
            "contrast_bg": _contrast(metric, 12.0, 90.0),
        },
        accent={
            "lightness": _pick(pol, (0.72, 0.90), (0.28, 0.45)),
            "contrast_bg": _contrast(metric, 7.0, 75.0),
        },
        hue_scheme=HueScheme("equal", rotation=35.0, tol=15.0),
    )


def _low_contrast(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"lightness": _pick(pol, (0.20, 0.28), (0.90, 0.95))},
        fg={
            "lightness": _pick(pol, (0.72, 0.84), (0.34, 0.46)),
            "contrast_bg": _contrast_band(metric, (4.5, 8.0), (55.0, 80.0)),
        },
        accent={
            "lightness": _pick(pol, (0.56, 0.72), (0.46, 0.62)),
            "chroma": _abs(0.04, 0.12),
            "contrast_bg": _contrast_band(metric, (3.0, 5.5), (38.0, 62.0)),
        },
        hue_scheme=HueScheme("equal", rotation=50.0, tol=20.0),
        lightness_spread=_soft(Interval(None, 0.10)),
    )


def _max_distinct(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        accent={
            "lightness": _pick(pol, (0.60, 0.88), (0.32, 0.60)),
            "chroma": _rel(0.50, 0.90),
            "min_distance": _soft(0.12, 3.0),
        },
        hue_scheme=HueScheme("equal", rotation=5.0, tol=10.0),
        lightness_spread=_soft(Interval(0.15, None)),
    )


# Chłodne
def _arctic(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.005, 0.025), "hue": _arc(210.0, 250.0, hard=False)},
        fg={"hue": _arc(200.0, 260.0, hard=False)},
        accent={"lightness": _pick(pol, (0.72, 0.90), (0.38, 0.54)), "chroma": _abs(0.03, 0.08)},
        hue_scheme=_fan(215.0, 70.0),
    )


def _ocean(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={
            "lightness": _pick(pol, (0.10, 0.18), (0.93, 0.98)),
            "chroma": _abs(0.012, 0.04),
            "hue": _arc(220.0, 260.0, hard=False),
        },
        accent={"lightness": _pick(pol, (0.60, 0.80), (0.36, 0.54)), "chroma": _abs(0.08, 0.16)},
        hue_scheme=_fan(225.0, 90.0),
    )


def _steel(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.004, 0.02), "hue": _arc(230.0, 270.0, hard=False)},
        accent={
            "lightness": _pick(pol, (0.58, 0.90), (0.30, 0.58)),
            "chroma": _abs(0.015, 0.06),
            "min_distance": _soft(0.05),
        },
        hue_scheme=_fan(240.0, 50.0, 15.0),
        lightness_spread=_soft(Interval(0.20, None)),
    )


def _winter_morning(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.004, 0.02), "hue": _arc(230.0, 280.0, hard=False)},
        accent={"lightness": _pick(pol, (0.74, 0.90), (0.42, 0.58)), "chroma": _rel(0.25, 0.50)},
        hue_scheme=_fan(250.0, 140.0, 15.0),
    )


AURORA = (
    150.0,
    175.0,
    300.0,
    320.0,
    200.0,
    280.0,
    165.0,
    310.0,
    190.0,
    290.0,
    140.0,
    330.0,
    220.0,
    260.0,
)


def _aurora(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={
            "lightness": _pick(pol, (0.08, 0.15), (0.94, 0.99)),
            "chroma": _abs(0.008, 0.035),
            "hue": _arc(250.0, 290.0, hard=False),
        },
        accent={"lightness": _pick(pol, (0.66, 0.86), (0.42, 0.58)), "chroma": _rel(0.60, 0.90)},
        hue_scheme=_custom(AURORA),
    )


# Ciepłe
DESERT = (55.0, 75.0, 40.0, 95.0, 25.0, 65.0, 85.0, 35.0, 50.0, 100.0, 20.0, 70.0, 45.0, 90.0)


def _desert(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.01, 0.03), "hue": _arc(60.0, 95.0, hard=False)},
        accent={"lightness": _pick(pol, (0.68, 0.86), (0.42, 0.58)), "chroma": _abs(0.05, 0.11)},
        hue_scheme=_custom(DESERT),
    )


def _amber(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.01, 0.03), "hue": _arc(50.0, 90.0, hard=False)},
        accent={
            "lightness": _pick(pol, (0.62, 0.90), (0.34, 0.58)),
            "chroma": _abs(0.09, 0.17),
            "min_distance": _soft(0.05),
        },
        hue_scheme=_fan(70.0, 50.0, 10.0),
        lightness_spread=_soft(Interval(0.18, None)),
    )


CAMPFIRE = (25.0, 45.0, 65.0, 10.0, 35.0, 80.0, 55.0, 20.0, 350.0, 70.0, 30.0, 50.0, 5.0, 60.0)


def _campfire(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={
            "lightness": _pick(pol, (0.08, 0.16), (0.94, 0.99)),
            "chroma": _abs(0.008, 0.03),
            "hue": _arc(20.0, 50.0, hard=False),
        },
        accent={"lightness": _pick(pol, (0.58, 0.80), (0.38, 0.58)), "chroma": _rel(0.60, 0.95)},
        hue_scheme=_custom(CAMPFIRE, 10.0),
    )


def _terracotta(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.01, 0.03), "hue": _arc(35.0, 70.0, hard=False)},
        accent={
            "lightness": _pick(pol, (0.58, 0.78), (0.36, 0.56)),
            "chroma": _abs(0.07, 0.13),
            "min_distance": _soft(0.05),
        },
        hue_scheme=_fan(40.0, 50.0, 10.0),
        lightness_spread=_soft(Interval(0.12, None)),
    )


# Natura
FOREST = (
    140.0,
    120.0,
    160.0,
    95.0,
    150.0,
    110.0,
    175.0,
    130.0,
    85.0,
    165.0,
    105.0,
    145.0,
    125.0,
    155.0,
)
MOSS = (
    125.0,
    110.0,
    140.0,
    95.0,
    130.0,
    115.0,
    150.0,
    100.0,
    135.0,
    120.0,
    145.0,
    105.0,
    128.0,
    112.0,
)
MEADOW = (
    130.0,
    100.0,
    350.0,
    60.0,
    150.0,
    320.0,
    85.0,
    20.0,
    115.0,
    300.0,
    140.0,
    45.0,
    95.0,
    335.0,
)
LAVENDER = (
    300.0,
    285.0,
    140.0,
    310.0,
    270.0,
    125.0,
    295.0,
    320.0,
    150.0,
    280.0,
    305.0,
    135.0,
    290.0,
    315.0,
)
TROPICAL = (
    150.0,
    30.0,
    190.0,
    350.0,
    110.0,
    60.0,
    170.0,
    10.0,
    130.0,
    45.0,
    210.0,
    330.0,
    90.0,
    20.0,
)
SHORE = (200.0, 80.0, 185.0, 95.0, 215.0, 70.0, 195.0, 60.0, 225.0, 90.0, 175.0, 75.0, 205.0, 85.0)


def _forest(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.01, 0.03), "hue": _arc(120.0, 160.0, hard=False)},
        accent={"lightness": _pick(pol, (0.60, 0.82), (0.36, 0.56)), "chroma": _abs(0.05, 0.12)},
        hue_scheme=_custom(FOREST),
    )


def _moss_stone(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.0, 0.015)},
        accent={
            "lightness": _pick(pol, (0.58, 0.88), (0.30, 0.58)),
            "chroma": _abs(0.02, 0.08),
            "min_distance": _soft(0.05),
        },
        hue_scheme=_custom(MOSS, 15.0),
        lightness_spread=_soft(Interval(0.20, None)),
    )


def _meadow(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.005, 0.025), "hue": _arc(100.0, 150.0, hard=False)},
        accent={"lightness": _pick(pol, (0.70, 0.88), (0.42, 0.58)), "chroma": _rel(0.45, 0.75)},
        hue_scheme=_custom(MEADOW),
    )


def _lavender(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.008, 0.025), "hue": _arc(280.0, 320.0, hard=False)},
        accent={"lightness": _pick(pol, (0.66, 0.84), (0.40, 0.56)), "chroma": _abs(0.05, 0.12)},
        hue_scheme=_custom(LAVENDER, 10.0),
    )


def _tropical(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        accent={"lightness": _pick(pol, (0.66, 0.86), (0.42, 0.58)), "chroma": _rel(0.70, 1.0)},
        hue_scheme=_custom(TROPICAL),
    )


def _shore(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.006, 0.025), "hue": _arc(190.0, 230.0, hard=False)},
        accent={"lightness": _pick(pol, (0.66, 0.86), (0.42, 0.58)), "chroma": _abs(0.04, 0.10)},
        hue_scheme=_custom(SHORE),
    )


# Pastelowe: kontrast akcentów obniżony — pastele z natury są mało kontrastowe.
POWDER = (10.0, 350.0, 30.0, 330.0, 20.0, 300.0, 0.0, 340.0, 40.0, 320.0, 15.0, 310.0, 355.0, 25.0)
CANDY = (
    350.0,
    300.0,
    200.0,
    100.0,
    330.0,
    270.0,
    180.0,
    60.0,
    10.0,
    290.0,
    220.0,
    80.0,
    320.0,
    160.0,
)
SORBET = (20.0, 60.0, 350.0, 100.0, 40.0, 330.0, 80.0, 10.0, 120.0, 50.0, 340.0, 70.0, 30.0, 90.0)


def _pastel_like(
    pol: Polarity,
    metric: ContrastMetric,
    chroma: Rule[ChromaBand],
    scheme: HueScheme,
    dark: tuple[float, float],
    light: tuple[float, float],
    **extra: Any,
) -> PresetRules:
    return _rules(
        pol,
        metric,
        accent={
            "lightness": _pick(pol, dark, light),
            "chroma": chroma,
            "contrast_bg": _contrast(metric, 3.0, 45.0),
        },
        hue_scheme=scheme,
        **extra,
    )


def _powder(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _pastel_like(
        pol, metric, _rel(0.15, 0.32), _custom(POWDER, 10.0), (0.80, 0.92), (0.52, 0.66)
    )


def _watercolor(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _pastel_like(
        pol,
        metric,
        _rel(0.30, 0.55),
        HueScheme("equal", rotation=40.0, tol=25.0),
        (0.74, 0.90),
        (0.48, 0.66),
        lightness_spread=_soft(Interval(0.10, None)),
    )


def _candy(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _pastel_like(pol, metric, _rel(0.40, 0.65), _custom(CANDY), (0.78, 0.90), (0.52, 0.66))


def _sorbet(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _pastel_like(pol, metric, _rel(0.35, 0.60), _custom(SORBET), (0.78, 0.90), (0.52, 0.66))


# Świecące
SYNTHWAVE = (
    330.0,
    290.0,
    200.0,
    350.0,
    270.0,
    185.0,
    310.0,
    250.0,
    215.0,
    340.0,
    280.0,
    195.0,
    320.0,
    230.0,
)
CYBERPUNK = (
    100.0,
    330.0,
    195.0,
    60.0,
    300.0,
    180.0,
    85.0,
    350.0,
    210.0,
    110.0,
    315.0,
    170.0,
    70.0,
    340.0,
)
ACID = (
    115.0,
    130.0,
    100.0,
    340.0,
    145.0,
    90.0,
    320.0,
    125.0,
    105.0,
    350.0,
    140.0,
    95.0,
    330.0,
    120.0,
)


def _synthwave(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={
            "lightness": _pick(pol, (0.08, 0.15), (0.94, 0.99)),
            "chroma": _abs(0.015, 0.04) if pol == "dark" else _abs(0.004, 0.02),
            "hue": _arc(280.0, 310.0, hard=False),
        },
        accent={"lightness": _pick(pol, (0.62, 0.84), (0.42, 0.58)), "chroma": _rel(0.80, 1.0)},
        hue_scheme=_custom(SYNTHWAVE, 10.0),
    )


def _cyberpunk(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"lightness": _pick(pol, (0.06, 0.12), (0.95, 0.99)), "chroma": _abs(0.0, 0.02)},
        fg={"contrast_bg": _contrast(metric, 10.0, 85.0)},
        accent={"lightness": _pick(pol, (0.70, 0.90), (0.42, 0.58)), "chroma": _rel(0.85, 1.0)},
        hue_scheme=_custom(CYBERPUNK, 10.0),
    )


def _arcade(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"lightness": _pick(pol, (0.08, 0.14), (0.95, 0.99)), "chroma": _abs(0.0, 0.015)},
        accent={"lightness": _pick(pol, (0.64, 0.82), (0.44, 0.58)), "chroma": _rel(0.85, 1.0)},
        hue_scheme=HueScheme("tetrad", rotation=25.0, tol=10.0),
        lightness_spread=_soft(Interval(None, 0.15)),
    )


def _acid(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"lightness": _pick(pol, (0.08, 0.14), (0.95, 0.99)), "chroma": _abs(0.0, 0.02)},
        accent={"lightness": _pick(pol, (0.76, 0.92), (0.44, 0.58)), "chroma": _rel(0.85, 1.0)},
        hue_scheme=_custom(ACID, 10.0),
    )


# Retro i druk
AMBER_TERMINAL = (
    70.0,
    60.0,
    85.0,
    50.0,
    75.0,
    95.0,
    55.0,
    65.0,
    80.0,
    45.0,
    90.0,
    68.0,
    58.0,
    78.0,
)
CRT = (145.0, 200.0, 100.0, 30.0, 170.0, 250.0, 120.0, 60.0, 185.0, 320.0, 135.0, 80.0, 215.0, 45.0)
INK = (
    265.0,
    25.0,
    150.0,
    300.0,
    240.0,
    40.0,
    180.0,
    330.0,
    220.0,
    10.0,
    130.0,
    285.0,
    200.0,
    350.0,
)


def _amber_terminal(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.01, 0.03), "hue": _arc(60.0, 90.0, hard=False)},
        fg={"chroma": _abs(0.02, 0.06), "hue": _arc(55.0, 95.0, hard=False)},
        accent={
            "lightness": _pick(pol, (0.60, 0.90), (0.32, 0.58)),
            "chroma": _abs(0.10, 0.17),
            "min_distance": _soft(0.04),
        },
        hue_scheme=_custom(AMBER_TERMINAL, 8.0),
        lightness_spread=_soft(Interval(0.20, None)),
    )


def _crt(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={
            "lightness": _pick(pol, (0.10, 0.18), (0.92, 0.97)),
            "chroma": _abs(0.01, 0.03),
            "hue": _arc(180.0, 220.0, hard=False),
        },
        accent={"lightness": _pick(pol, (0.66, 0.86), (0.40, 0.58)), "chroma": _rel(0.55, 0.80)},
        hue_scheme=_custom(CRT),
    )


def _sepia(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.012, 0.04), "hue": _arc(60.0, 90.0, hard=False)},
        fg={"chroma": _abs(0.01, 0.05), "hue": _arc(50.0, 90.0, hard=False)},
        accent={
            "lightness": _pick(pol, (0.58, 0.88), (0.30, 0.58)),
            "chroma": _abs(0.03, 0.08),
            "min_distance": _soft(0.04),
        },
        hue_scheme=_fan(65.0, 40.0, 10.0),
        lightness_spread=_soft(Interval(0.22, None)),
    )


def _paper_ink(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={
            "lightness": Rule(Band(0.94, 0.98)),
            "chroma": _abs(0.008, 0.025),
            "hue": _arc(70.0, 100.0, hard=False),
        },
        fg={"lightness": Rule(Band(0.16, 0.28))},
        accent={
            "lightness": Rule(Band(0.32, 0.52)),
            "chroma": _abs(0.07, 0.14),
            "contrast_bg": _contrast(metric, 5.5, 65.0),
        },
        hue_scheme=_custom(INK),
    )


def _newspaper(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"lightness": Rule(Band(0.92, 0.97)), "chroma": _abs(0.0, 0.012)},
        fg={"lightness": Rule(Band(0.14, 0.24)), "chroma": _abs(0.0, 0.015)},
        accent={
            "lightness": Rule(Band(0.24, 0.58)),
            "chroma": _abs(0.0, 0.03),
            "min_distance": _soft(0.035),
        },
        overrides={
            1: AccentOverride(
                {
                    "lightness": Rule(Band(0.40, 0.56)),
                    "chroma": _abs(0.13, 0.20),
                    "hue": _arc(15.0, 40.0),
                },
                use_scheme=False,
            )
        },
        hue_scheme=HueScheme("none"),
        use_scheme=False,
        lightness_spread=_soft(Interval(0.22, None)),
    )


# Ograniczone
def _gray_accent(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.0, 0.012)},
        accent={
            "lightness": _pick(pol, (0.58, 0.94), (0.22, 0.58)),
            "chroma": _abs(0.0, 0.02),
            "min_distance": _soft(0.035),
        },
        overrides={
            1: AccentOverride(
                {
                    "lightness": _pick(pol, (0.66, 0.82), (0.40, 0.56)),
                    "chroma": _abs(0.13, 0.20),
                    "hue": _arc(15.0, 45.0),
                },
                use_scheme=False,
            )
        },
        hue_scheme=HueScheme("none"),
        use_scheme=False,
        lightness_spread=_soft(Interval(0.25, None)),
    )


DUOTONE = (220.0, 35.0) * 7
POLES = (35.0, 215.0) * 7


def _duotone(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        accent={
            "lightness": _pick(pol, (0.58, 0.90), (0.30, 0.58)),
            "chroma": _abs(0.06, 0.16),
            "min_distance": _soft(0.04),
        },
        hue_scheme=_custom(DUOTONE, 8.0, hard=True),
        lightness_spread=_soft(Interval(0.20, None)),
    )


def _one_hue(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.005, 0.03), "hue": _arc(230.0, 270.0, hard=False)},
        accent={
            "lightness": _pick(pol, (0.56, 0.94), (0.22, 0.60)),
            "chroma": _abs(0.04, 0.14),
            "min_distance": _soft(0.035),
        },
        hue_scheme=_custom((250.0,) * 14, 8.0, hard=True),
        lightness_spread=_soft(Interval(0.30, None)),
    )


def _two_poles(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        accent={
            "lightness": _pick(pol, (0.62, 0.86), (0.38, 0.58)),
            "chroma": _rel(0.55, 0.85),
            "min_distance": _soft(0.05),
        },
        hue_scheme=_custom(POLES, 20.0, hard=True),
    )


# Harmonie
def _harmony(
    kind: SchemeKind, *, rotation: float = 0.0, center: float = 0.0, spread: float = 90.0
) -> Builder:
    def build(pol: Polarity, metric: ContrastMetric) -> PresetRules:
        scheme = HueScheme(
            kind, rotation=rotation, center=center, spread=spread, tol=12.0, weight=2.0
        )
        return _rules(pol, metric, accent={"chroma": _abs(0.07, 0.17)}, hue_scheme=scheme)

    return build


# Pory dnia
DAWN = (20.0, 50.0, 350.0, 80.0, 330.0, 230.0, 35.0, 65.0, 5.0, 210.0, 340.0, 95.0, 250.0, 15.0)
DUSK = (
    300.0,
    270.0,
    30.0,
    330.0,
    250.0,
    50.0,
    285.0,
    345.0,
    235.0,
    15.0,
    315.0,
    260.0,
    40.0,
    290.0,
)


def _midnight(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={
            "lightness": Rule(Band(0.05, 0.11)),
            "chroma": _abs(0.005, 0.03),
            "hue": _arc(250.0, 285.0, hard=False),
        },
        fg={"lightness": Rule(Band(0.82, 0.92))},
        accent={"lightness": Rule(Band(0.62, 0.80)), "chroma": _abs(0.05, 0.12)},
        hue_scheme=_fan(255.0, 150.0, 15.0),
        lightness_spread=_soft(Interval(None, 0.14)),
    )


def _dawn(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.008, 0.03), "hue": _arc(20.0, 60.0, hard=False)},
        accent={"lightness": _pick(pol, (0.72, 0.88), (0.44, 0.58)), "chroma": _rel(0.30, 0.60)},
        hue_scheme=_custom(DAWN),
    )


def _dusk(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={"chroma": _abs(0.01, 0.035), "hue": _arc(270.0, 310.0, hard=False)},
        accent={"lightness": _pick(pol, (0.62, 0.80), (0.38, 0.56)), "chroma": _abs(0.07, 0.14)},
        hue_scheme=_custom(DUSK),
        lightness_spread=_soft(Interval(None, 0.15)),
    )


def _storm(pol: Polarity, metric: ContrastMetric) -> PresetRules:
    return _rules(
        pol,
        metric,
        bg={
            "lightness": _pick(pol, (0.12, 0.20), (0.90, 0.95)),
            "chroma": _abs(0.008, 0.025),
            "hue": _arc(235.0, 275.0, hard=False),
        },
        accent={"lightness": _pick(pol, (0.60, 0.82), (0.34, 0.56)), "chroma": _abs(0.02, 0.07)},
        overrides={
            1: AccentOverride(
                {
                    "lightness": _pick(pol, (0.82, 0.94), (0.46, 0.60)),
                    "chroma": _rel(0.70, 1.0),
                    "hue": _arc(90.0, 112.0),
                },
                use_scheme=False,
            )
        },
        hue_scheme=_fan(245.0, 60.0, 15.0),
    )


# Dostępność
RG_SAFE = (
    250.0,
    90.0,
    280.0,
    70.0,
    220.0,
    110.0,
    300.0,
    50.0,
    200.0,
    100.0,
    265.0,
    80.0,
    235.0,
    60.0,
)
TRITAN_SAFE = (
    25.0,
    150.0,
    350.0,
    170.0,
    10.0,
    135.0,
    40.0,
    160.0,
    330.0,
    145.0,
    20.0,
    180.0,
    0.0,
    125.0,
)


def _cvd_safe(types: tuple[CvdType, ...], hues: tuple[float, ...]) -> Builder:
    def build(pol: Polarity, metric: ContrastMetric) -> PresetRules:
        return _rules(
            pol,
            metric,
            accent={
                "lightness": _pick(pol, (0.58, 0.90), (0.30, 0.60)),
                "chroma": _abs(0.07, 0.18),
                "min_distance": _soft(0.10, 2.0),
                "cvd_min_distance": _soft(0.07, 4.0),
            },
            hue_scheme=_custom(hues, 15.0),
            lightness_spread=_soft(Interval(0.20, None)),
            cvd=CvdSettings(frozenset(types), "machado", 1.0),
        )

    return build


def _apca_reading(pol: Polarity, _metric: ContrastMetric) -> PresetRules:
    """Progi w APCA niezależnie od metryki sesji — preset sam ustawia metrykę APCA."""
    return _rules(
        pol,
        "apca",
        bg={"lightness": _pick(pol, (0.14, 0.22), (0.94, 0.98)), "chroma": _abs(0.0, 0.02)},
        fg={
            "lightness": _pick(pol, (0.84, 0.93), (0.18, 0.30)),
            "contrast_bg": Rule(ContrastBound(None, 82.0, 98.0)),
        },
        accent={
            "lightness": _pick(pol, (0.68, 0.86), (0.36, 0.54)),
            "chroma": _abs(0.05, 0.12),
            "contrast_bg": Rule(ContrastBound(None, 65.0, 90.0)),
        },
        hue_scheme=HueScheme("equal", rotation=25.0, tol=15.0),
        lightness_spread=_soft(Interval(None, 0.14)),
        contrast_metric="apca",
    )


_Entry = tuple[str, str, Builder, tuple[Polarity, ...]]


def _p(name: str, description: str, build: Builder, pols: tuple[Polarity, ...] = BOTH) -> _Entry:
    return (name, description, build, pols)


# Kolejność: kategorie jak w CATEGORIES, w kategorii najpierw dawne nastroje.
_REGISTRY: dict[str, tuple[_Entry, ...]] = {
    "Podstawowe": (
        _p(
            "neutralny",
            "Odcienie równo po kole, średnie nasycenie, zwykły kontrast — punkt wyjścia.",
            _neutral,
        ),
        _p(
            "stonowany",
            "Akcenty o małym nasyceniu i średniej jasności, tło prawie szare, odcienie równo po"
            " kole.",
            _muted,
        ),
        _p(
            "żywy",
            "Akcenty o dużym nasyceniu względnym w szerokim zakresie jasności, odcienie równo "
            "po kole.",
            _vivid,
        ),
        _p(
            "wysoki kontrast",
            "Tło skrajne i szare, tekst co najmniej 12:1 (APCA 90), akcenty co najmniej 7:1 "
            "(APCA 75).",
            _high_contrast,
        ),
        _p(
            "niski kontrast",
            "Tło bliżej środka skali, kontrast tekstu i akcentów ograniczony także z góry, "
            "akcenty blisko siebie jasnością.",
            _low_contrast,
        ),
        _p(
            "maksymalna rozróżnialność",
            "Duża wymagana odległość między akcentami, mocne nasycenie, wąska tolerancja "
            "odcieni i rozrzut jasności od 15 punktów.",
            _max_distinct,
        ),
    ),
    "Chłodne": (
        _p(
            "chłodny mglisty",
            "Błękity i zielenie o niskim nasyceniu, mały rozrzut jasności, tło z chłodną nutą.",
            _cool_misty,
        ),
        _p(
            "arktyczny",
            "Jasne, lodowe błękity o bardzo małym nasyceniu w wąskim wachlarzu wokół 215°, tło "
            "i tekst z niebieską nutą.",
            _arctic,
        ),
        _p(
            "głębia oceanu",
            "Granaty, błękity i morskie zielenie o średnim nasyceniu, tło ciemniejsze i "
            "wyraźnie niebieskie.",
            _ocean,
        ),
        _p(
            "stalowy",
            "Niebieskawe szarości różniące się głównie jasnością, wąski wachlarz odcieni wokół "
            "240°.",
            _steel,
        ),
        _p(
            "zimowy poranek",
            "Jasne, lekko nasycone błękity, fiolety i róże w szerokim wachlarzu wokół 250°.",
            _winter_morning,
        ),
        _p(
            "zorza",
            "Nasycone zielenie, turkusy, fiolety i magenty z własnej listy odcieni na bardzo "
            "ciemnym albo bardzo jasnym tle z fioletową nutą.",
            _aurora,
        ),
    ),
    "Ciepłe": (
        _p(
            "ziemisty",
            "Przygaszone brązy, oliwki i ochry z własnej listy odcieni, tło z ciepłą nutą.",
            _earthy,
        ),
        _p(
            "jesienny",
            "Pomarańcze, rudości i złoto o średnim nasyceniu, tło lekko rude.",
            _autumn,
        ),
        _p(
            "pustynny",
            "Jasne piaski, ochry i wyblakłe czerwienie o małym nasyceniu, tło w kolorze piasku.",
            _desert,
        ),
        _p(
            "bursztynowy",
            "Złoto i miód w wąskim wachlarzu wokół 70°, akcenty różnią się głównie jasnością.",
            _amber,
        ),
        _p(
            "ognisko",
            "Mocno nasycone czerwienie, pomarańcze i żółcie z własnej listy odcieni, tło "
            "skrajne z ciepłą nutą.",
            _campfire,
        ),
        _p(
            "terakota",
            "Ceglaste czerwienie i przygaszone pomarańcze w wąskim wachlarzu wokół 40°, tło "
            "gliniane.",
            _terracotta,
        ),
    ),
    "Natura": (
        _p(
            "leśny",
            "Zielenie od żółtawych po morskie o średnim nasyceniu, tło z zieloną nutą.",
            _forest,
        ),
        _p(
            "mech i kamień",
            "Przygaszone zielenie o bardzo małym nasyceniu w wielu jasnościach, tło szare.",
            _moss_stone,
        ),
        _p(
            "wiosenna łąka",
            "Świeże zielenie przeplatane różem, żółcią i fioletem kwiatów, jasne akcenty o "
            "średnim nasyceniu względnym.",
            _meadow,
        ),
        _p(
            "lawendowe pole",
            "Fiolety i lila z kilkoma zieleniami łodyg, średnie nasycenie, tło z fioletową nutą.",
            _lavender,
        ),
        _p(
            "tropikalny",
            "Bardzo nasycone turkusy, zielenie, pomarańcze i róże z własnej listy odcieni.",
            _tropical,
        ),
        _p(
            "morski brzeg",
            "Morskie błękity na przemian z piaskowymi żółciami, małe nasycenie, tło z błękitną "
            "nutą.",
            _shore,
        ),
    ),
    "Pastelowe": (
        _p(
            "pastel",
            "Jasne akcenty o małym nasyceniu względnym, odcienie równo po kole.",
            _pastel,
        ),
        _p(
            "pudrowy",
            "Bardzo jasne róże, brzoskwinie i lila o najmniejszym nasyceniu, kontrast akcentów "
            "obniżony do 3:1 (APCA 45).",
            _powder,
        ),
        _p(
            "akwarela",
            "Jasne akcenty o średnim nasyceniu względnym, luźna tolerancja odcieni i rozrzut "
            "jasności od 10 punktów; kontrast akcentów 3:1 (APCA 45).",
            _watercolor,
        ),
        _p(
            "cukierkowy",
            "Jasne róże, lila, błękity i limonki o wyraźnym nasyceniu względnym; kontrast "
            "akcentów 3:1 (APCA 45).",
            _candy,
        ),
        _p(
            "sorbet",
            "Jasne brzoskwinie, cytryny, maliny i limonki z własnej listy odcieni; kontrast "
            "akcentów 3:1 (APCA 45).",
            _sorbet,
        ),
    ),
    "Świecące": (
        _p(
            "neon",
            "Akcenty przy granicy możliwości ekranu, odcienie szeroko, tło skrajnie ciemne albo"
            " jasne.",
            _neon,
        ),
        _p(
            "synthwave",
            "Magenty, fiolety i cyjany przy granicy możliwości ekranu, tło z fioletową nutą.",
            _synthwave,
        ),
        _p(
            "cyberpunk",
            "Jaskrawe żółtozielenie, magenty i cyjany przy granicy możliwości ekranu, tło "
            "skrajne, tekst co najmniej 10:1 (APCA 85).",
            _cyberpunk,
        ),
        _p(
            "arcade",
            "Cztery grupy czystych barw co 90° przy granicy możliwości ekranu, wyrównane "
            "jasnością.",
            _arcade,
        ),
        _p(
            "kwaśny",
            "Jaskrawe limonki i żółtozielenie z kilkoma magentami, bardzo jasne akcenty przy "
            "granicy możliwości ekranu.",
            _acid,
        ),
    ),
    "Retro i druk": (
        _p(
            "retro terminal",
            "Fosforowe zielenie i bursztyny z własnej listy odcieni, tło i tekst z nutą zieleni.",
            _retro,
        ),
        _p(
            "bursztynowy terminal",
            "Same bursztyny i żółcie w wielu jasnościach, tło i tekst z żółtą nutą.",
            _amber_terminal,
        ),
        _p(
            "CRT",
            "Nasycone zielenie, cyjany i żółcie starego monitora z własnej listy odcieni, tło z"
            " niebieskozieloną nutą.",
            _crt,
        ),
        _p(
            "sepia",
            "Brązy starej fotografii o małym nasyceniu w wielu jasnościach, tło i tekst "
            "wyraźnie żółtawe.",
            _sepia,
        ),
        _p(
            "papier i atrament",
            "Kremowe tło, ciemny tekst i ciemne, przygaszone akcenty jak tusze — granat, "
            "czerwień, zieleń, fiolet; tylko jasne tło.",
            _paper_ink,
            LIGHT,
        ),
        _p(
            "gazeta",
            "Szare tło i tekst, akcenty szare w wielu jasnościach, tylko pierwszy akcent "
            "czerwony; tylko jasne tło.",
            _newspaper,
            LIGHT,
        ),
    ),
    "Ograniczone": (
        _p(
            "monochromatyczny z jednym akcentem",
            "Jeden odcień w wielu jasnościach, tylko pierwszy akcent ciepły; duży rozrzut "
            "jasności.",
            _mono_accent,
        ),
        _p(
            "szarości z akcentem",
            "Akcenty od drugiego w górę bez barwy (nasycenie do 0.02) w wielu jasnościach, "
            "pierwszy akcent nasycony, czerwono-pomarańczowy.",
            _gray_accent,
        ),
        _p(
            "duotone",
            "Tylko dwa odcienie — niebieski 220° i pomarańczowy 35° — na przemian, twardo; "
            "akcenty różnią się jasnością.",
            _duotone,
        ),
        _p(
            "jeden odcień, wiele jasności",
            "Wszystkie akcenty w odcieniu 250° (twardo), rozrzut jasności od 30 punktów, tło z "
            "tą samą nutą.",
            _one_hue,
        ),
        _p(
            "dwa bieguny",
            "Akcenty na przemian w dwóch przeciwnych grupach odcieni — wokół 35° i 215° — "
            "twardo, z tolerancją 20°.",
            _two_poles,
        ),
    ),
    "Harmonie": (
        _p(
            "dopełniający",
            "Dwie grupy odcieni naprzeciw siebie na kole (od 30°), układ z podwójną wagą.",
            _harmony("complementary", rotation=30.0),
        ),
        _p(
            "rozszczepiony dopełniający",
            "Odcień główny 200° i dwa sąsiadujące z jego przeciwieństwem, układ z podwójną wagą.",
            _harmony("split", rotation=200.0),
        ),
        _p(
            "triada",
            "Trzy grupy odcieni co 120° (od 20°), układ z podwójną wagą.",
            _harmony("triad", rotation=20.0),
        ),
        _p(
            "tetrada",
            "Cztery grupy odcieni co 90° (od 40°), układ z podwójną wagą.",
            _harmony("tetrad", rotation=40.0),
        ),
        _p(
            "analogiczny",
            "Wachlarz sąsiednich odcieni o rozpiętości 120° wokół 30°, układ z podwójną wagą.",
            _harmony("analogous", center=30.0, spread=120.0),
        ),
    ),
    "Pory dnia": (
        _p(
            "nocny wysoki kontrast",
            "Tło prawie czarne albo białe, bardzo wysoki kontrast tekstu i akcentów.",
            _night_contrast,
        ),
        _p(
            "północ",
            "Tło prawie czarne z granatową nutą, przygaszony tekst, chłodne akcenty o średnim "
            "nasyceniu i wyrównanej jasności; tylko ciemne tło.",
            _midnight,
            DARK,
        ),
        _p(
            "świt",
            "Jasne brzoskwinie, róże i złoto z kilkoma błękitami, małe nasycenie względne, tło "
            "z ciepłą nutą.",
            _dawn,
        ),
        _p(
            "zmierzch",
            "Fiolety i magenty z kilkoma pomarańczami, średnie nasycenie, wyrównana jasność, "
            "tło z fioletową nutą.",
            _dusk,
        ),
        _p(
            "burza",
            "Ołowiane, mało nasycone błękity i fiolety, a pierwszy akcent to jaskrawa żółć "
            "błyskawicy.",
            _storm,
        ),
    ),
    "Dostępność": (
        _p(
            "bezpieczny przy protanopii i deuteranopii",
            "Włącza symulację protanopii i deuteranopii, odcienie tylko niebieskie i żółte, "
            "akcenty rozsunięte jasnością, mocna zasada odróżnialności.",
            _cvd_safe(("protan", "deutan"), RG_SAFE),
        ),
        _p(
            "bezpieczny przy tritanopii",
            "Włącza symulację tritanopii, odcienie tylko czerwone i zielone, akcenty rozsunięte"
            " jasnością, mocna zasada odróżnialności.",
            _cvd_safe(("tritan",), TRITAN_SAFE),
        ),
        _p(
            "APCA do długiego czytania",
            "Ustawia metrykę APCA: tekst 82–98, akcenty 65–90, tło szare i nie skrajne, akcenty"
            " o małym nasyceniu i wyrównanej jasności.",
            _apca_reading,
        ),
    ),
}

BUILTIN: tuple[PresetDef, ...] = tuple(
    PresetDef(name, category, description, pols, build)
    for category in CATEGORIES
    for name, description, build, pols in _REGISTRY[category]
)
