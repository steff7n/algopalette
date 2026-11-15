"""Opis formularzy interfejsu: etykiety, opcje list, domyślne wartości nowych zasad i zależności
oraz zakresy suwaków. Bez zależności od bibliotek interfejsu."""

from __future__ import annotations

from typing import Any

from algopalette.model import (
    ACCENT_ONLY_FIELDS,
    RULE_FIELDS,
    Band,
    ChromaBand,
    ContrastBound,
    HueArc,
    Role,
    Session,
    rule_fields_for,
)
from algopalette.units import default_distance

# --- zasady koloru -----------------------------------------------------------------------------

LABELS = {
    "lightness": "jasność L",
    "chroma": "nasycenie C",
    "hue": "odcień",
    "contrast_bg": "kontrast z tłem",
    "min_distance": "odległość od innych akcentów",
    "cvd_min_distance": "odróżnialność (daltonizm)",
    "extreme": "skrajny kontrast",
}

DESCRIPTIONS = {
    "lightness": "Dozwolony zakres jasności OKLCH (0 = czerń, 1 = biel).",
    "chroma": (
        "Dozwolony zakres nasycenia: w jednostkach C albo jako część największego nasycenia, "
        "jakie ekran pokaże przy tej jasności i odcieniu."
    ),
    "hue": "Dozwolony łuk odcienia w stopniach; „od” większe niż „do” to łuk przez 0°.",
    "contrast_bg": "Kontrast tego koloru z tłem (WCAG 2.1 albo APCA |Lc|).",
    "min_distance": "Najmniejsza odległość ΔE od każdego innego akcentu.",
    "cvd_min_distance": "Najmniejsza odległość ΔE od innych akcentów przy symulacji daltonizmu.",
    "extreme": "Ten akcent ma najsłabszy albo najmocniejszy kontrast z tłem spośród akcentów.",
}

DEFAULTS: dict[str, Any] = {
    "lightness": Band(0.5, 0.8),
    "chroma": ChromaBand("abs", 0.05, 0.15),
    "hue": HueArc(0.0, 60.0),
    "contrast_bg": ContrastBound(None, 4.5, None),
    "min_distance": 0.08,
    "cvd_min_distance": 0.04,
    "extreme": "weakest",
}

ACCENT_ONLY = ACCENT_ONLY_FIELDS

DISPLAY_ORDER = RULE_FIELDS


def default_for(field: str, session: Session) -> Any:
    """Wartość nowej zasady w jednostkach bieżącej metryki kontrastu / metody ΔE."""
    g = session.globals
    if field == "contrast_bg":
        return ContrastBound(None, 4.5 if g.contrast_metric == "wcag21" else 60.0, None)
    if field in ("min_distance", "cvd_min_distance"):
        return default_distance(g.delta_e, float(DEFAULTS[field]))
    return DEFAULTS[field]


def fields_for(role: Role) -> list[str]:
    return list(rule_fields_for(role))


def range_spec(field: str, cond_value: Any, session: Session) -> dict[str, Any]:
    """Zakres, krok i format suwaka wartości zasady."""
    g = session.globals
    if field == "lightness":
        return {"minimum": 0.0, "maximum": 1.0, "step": 0.01, "fmt": ".3f", "allow_none": True}
    if field == "chroma":
        if cond_value.mode == "rel":
            return {"minimum": 0.0, "maximum": 1.0, "step": 0.01, "fmt": ".2f", "allow_none": True}
        return {"minimum": 0.0, "maximum": 0.37, "step": 0.005, "fmt": ".3f", "allow_none": True}
    if field == "hue":
        return {"minimum": 0.0, "maximum": 360.0, "step": 1.0, "fmt": ".0f", "wrap": True}
    if field == "contrast_bg":
        metric = cond_value.metric or g.contrast_metric
        if metric == "wcag21":
            return {"minimum": 1.0, "maximum": 21.0, "step": 0.1, "fmt": ".2f", "allow_none": True}
        return {"minimum": 0.0, "maximum": 108.0, "step": 1.0, "fmt": ".1f", "allow_none": True}
    # min_distance / cvd_min_distance
    if g.delta_e in ("ok", "hyab"):
        return {"minimum": 0.0, "maximum": 0.5, "step": 0.005, "fmt": ".3f"}
    return {"minimum": 0.0, "maximum": 100.0, "step": 0.5, "fmt": ".1f"}


CHROMA_MODES = [("bezwzględne (C)", "abs"), ("względne (% największego)", "rel")]
CONTRAST_METRICS = [("metryka palety", "global"), ("WCAG 2.1", "wcag21"), ("APCA", "apca")]
EXTREMES = [("najsłabszy z akcentów", "weakest"), ("najmocniejszy z akcentów", "strongest")]

# --- zależności między kolorami ----------------------------------------------------------------

REL_KINDS = [
    ("odcień (różnica °)", "hue"),
    ("jasność (różnica)", "lightness"),
    ("nasycenie", "chroma"),
    ("kontrast (ten → cel jako tło)", "contrast"),
    ("odległość ΔE", "distance"),
    ("mieszanka dwóch", "mix"),
]
REL_OPS = [("= (± tol)", "eq"), ("≥", "ge"), ("≤", "le")]
REL_DEFAULT_VALUE = {
    "hue": 180.0,
    "lightness": 0.0,
    "chroma": 1.0,
    "contrast": 4.5,
    "distance": 0.08,
    "mix": 0.0,
}
REL_CHROMA_OPS = [("+ różnica", "add"), ("× mnożnik", "mul")]
REL_CHROMA_MODES = [("bezwzgl.", "abs"), ("względne", "rel")]
REL_CONTRAST_METRICS = [("metryka palety", "global"), ("WCAG", "wcag21"), ("APCA", "apca")]
REL_DISTANCE_METRICS = [
    ("metoda palety", "global"),
    ("ok", "ok"),
    ("2000", "2000"),
    ("hyab", "hyab"),
    ("itp", "itp"),
    ("cam16", "cam16"),
]


def relation_default_value(kind: str, session: Session) -> float:
    g = session.globals
    value = REL_DEFAULT_VALUE[kind]
    if kind == "contrast" and g.contrast_metric == "apca":
        return 60.0
    if kind == "distance":
        return default_distance(g.delta_e, value)
    return value


# --- ustawienia całej palety -------------------------------------------------------------------

SCHEMES = [
    ("równo po kole", "equal"),
    ("analogiczny", "analogous"),
    ("dopełniający", "complementary"),
    ("rozszczepiony dopełniający", "split"),
    ("triada", "triad"),
    ("tetrada", "tetrad"),
    ("własna lista", "custom"),
    ("brak (bez celów)", "none"),
]
DELTA_E = [
    ("ok (OKLab, 0–1)", "ok"),
    ("hyab (OKLab)", "hyab"),
    ("2000 (CIE, ~0–100)", "2000"),
    ("itp (ICtCp)", "itp"),
    ("cam16 (CAM16-UCS)", "cam16"),
]
FITS = [(m, m) for m in ("oklch-chroma", "raytrace", "minde-chroma", "lch-chroma", "scale", "clip")]
CVD = [("protanopia", "protan"), ("deuteranopia", "deutan"), ("tritanopia", "tritan")]
CVD_METHODS = [("Machado", "machado"), ("Viénot", "vienot"), ("Brettel", "brettel")]
POLARITIES = [("ciemne tło", "dark"), ("jasne tło", "light")]
CONTRAST_GLOBAL = [("WCAG 2.1 (1–21)", "wcag21"), ("APCA |Lc| (0–108)", "apca")]

# --- źródło ------------------------------------------------------------------------------------

SOURCE_MODES = [
    ("uzupełnianie — podane kolory z kłódką, reszta generowana", "complete"),
    ("charakter — profil palety staje się zasadami kolorów", "character"),
    ("przeniesienie — ta sama paleta na innym tle", "transfer"),
]
