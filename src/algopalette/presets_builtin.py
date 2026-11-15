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
from typing import Any

from algopalette.model import (
    Band,
    ChromaBand,
    ContrastBound,
    ContrastMetric,
    CvdSettings,
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
            "lightness": _pick(pol, (0.70, 0.80), (0.30, 0.42)),
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


BUILTIN: tuple[PresetDef, ...] = (
    PresetDef(
        "neutralny",
        "Podstawowe",
        "Odcienie równo po kole, średnie nasycenie, zwykły kontrast — punkt wyjścia.",
        BOTH,
        _neutral,
    ),
    PresetDef(
        "chłodny mglisty",
        "Chłodne",
        "Błękity i zielenie o niskim nasyceniu, mały rozrzut jasności, tło z chłodną nutą.",
        BOTH,
        _cool_misty,
    ),
    PresetDef(
        "ziemisty",
        "Ciepłe",
        "Przygaszone brązy, oliwki i ochry z własnej listy odcieni, tło z ciepłą nutą.",
        BOTH,
        _earthy,
    ),
    PresetDef(
        "jesienny",
        "Ciepłe",
        "Pomarańcze, rudości i złoto o średnim nasyceniu, tło lekko rude.",
        BOTH,
        _autumn,
    ),
    PresetDef(
        "pastel",
        "Pastelowe",
        "Jasne akcenty o małym nasyceniu względnym, odcienie równo po kole.",
        BOTH,
        _pastel,
    ),
    PresetDef(
        "neon",
        "Świecące",
        "Akcenty przy granicy możliwości ekranu, odcienie szeroko, tło skrajnie ciemne albo jasne.",
        BOTH,
        _neon,
    ),
    PresetDef(
        "retro terminal",
        "Retro i druk",
        "Fosforowe zielenie i bursztyny z własnej listy odcieni, tło i tekst z nutą zieleni.",
        BOTH,
        _retro,
    ),
    PresetDef(
        "monochromatyczny z jednym akcentem",
        "Ograniczone",
        "Jeden odcień w wielu jasnościach, tylko pierwszy akcent ciepły; duży rozrzut jasności.",
        BOTH,
        _mono_accent,
    ),
    PresetDef(
        "nocny wysoki kontrast",
        "Pory dnia",
        "Tło prawie czarne albo białe, bardzo wysoki kontrast tekstu i akcentów.",
        BOTH,
        _night_contrast,
    ),
)
