"""Opis formularzy interfejsu: etykiety, opcje list, domyślne wartości nowych zasad i zależności,
zakresy suwaków oraz teksty naruszeń. Bez zależności od bibliotek interfejsu."""

from __future__ import annotations

from typing import Any

from algopalette.engine import Violation, slot_label
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


# --- krótki opis zasady (wiersz „różne” przy edycji zbiorczej) ---------------------------------


def rule_summary(field: str, rule: Any, session: Session) -> str:
    """Zasada jednym wierszem tekstu: wartość + odstępstwa od „włączona, twarda, waga 1”."""
    if rule is None:
        return "brak"
    v = rule.value
    if field == "lightness":
        text = _fmt_interval(v.lo, v.hi, ".3f")
    elif field == "chroma":
        if v.mode == "rel":
            lo = None if v.lo is None else 100.0 * v.lo
            hi = None if v.hi is None else 100.0 * v.hi
            text = _fmt_interval(lo, hi, ".0f") + "%"
        else:
            text = _fmt_interval(v.lo, v.hi, ".3f")
    elif field == "hue":
        text = f"{v.lo:.0f}°–{v.hi:.0f}°"
    elif field == "contrast_bg":
        fmt, unit = _contrast_fmt(v.metric or session.globals.contrast_metric)
        text = _fmt_interval(v.lo, v.hi, fmt, unit)
    elif field in ("min_distance", "cvd_min_distance"):
        fine = session.globals.delta_e in ("ok", "hyab")
        text = f"ΔE ≥ {float(v):.3f}" if fine else f"ΔE ≥ {float(v):.1f}"
    else:  # extreme
        text = "najsłabszy" if v == "weakest" else "najmocniejszy"
    exclude = getattr(v, "exclude", ())
    if exclude:
        text += f", zakazy: {len(exclude)}"
    if not rule.enabled:
        text += " · wyłączona"
    if not rule.hard:
        text += " · miękka" + ("" if rule.weight == 1.0 else f" (waga {rule.weight:g})")
    return text


# --- teksty naruszeń ---------------------------------------------------------------------------

_CVD_NAMES = {"protan": "protanopii", "deutan": "deuteranopii", "tritan": "tritanopii"}
_REL_NAMES = {
    "hue": "odcień",
    "lightness": "jasność",
    "chroma": "nasycenie",
    "contrast": "kontrast",
    "distance": "odległość",
    "mix": "mieszanka",
}
_CHANNEL_NAMES = {"lightness": "jasność", "chroma": "nasycenie", "hue": "odcień"}


def _fmt_interval(lo: float | None, hi: float | None, fmt: str, unit: str = "") -> str:
    u = f" {unit}" if unit else ""
    if lo is not None and hi is not None:
        return f"{lo:{fmt}}–{hi:{fmt}}{u}"
    if lo is not None:
        return f"≥ {lo:{fmt}}{u}"
    if hi is not None:
        return f"≤ {hi:{fmt}}{u}"
    return "—"


def _contrast_fmt(metric: str) -> tuple[str, str]:
    return (".2f", "") if metric == "wcag21" else (".1f", "Lc")


def _with_unit(value: float, fmt: str, unit: str) -> str:
    return f"{value:{fmt}}" + (f" {unit}" if unit else "")


def _op_req(op: str, value: float, tol: float, fmt: str, unit: str = "") -> str:
    u = f" {unit}" if unit else ""
    if op == "eq":
        return f"{value:{fmt}} ± {tol:{fmt}}{u}"
    return f"{'≥' if op == 'ge' else '≤'} {value:{fmt}}{u}"


def violation_text(v: Violation, session: Session) -> tuple[str, str, str]:
    """Naruszenie po polsku: ``(etykieta, wymagane, osiągnięte)``.

    Silnik zwraca same liczby (``Violation.req``/``meta``/``achieved``); tu powstają napisy do
    panelu naruszeń i szczegółów propozycji.
    """
    index = {s.id: i for i, s in enumerate(session.slots)}

    def name(k: int) -> str:
        sid = v.slot_ids[k] if k < len(v.slot_ids) else ""
        return slot_label(session, index[sid]) if sid in index else "?"

    req, meta, got = v.req, v.meta, v.achieved
    kind = v.kind
    if kind == "lightness":
        return f"jasność ({name(0)})", _fmt_interval(req["lo"], req["hi"], ".3f"), f"{got:.3f}"
    if kind == "chroma":
        unit = "względne" if meta.get("mode") == "rel" else ""
        return (
            f"nasycenie ({name(0)})",
            _fmt_interval(req["lo"], req["hi"], ".3f", unit),
            f"{got:.3f}",
        )
    if kind == "hue":
        return f"odcień ({name(0)})", f"{req['lo']:.0f}°–{req['hi']:.0f}°", f"{got:.1f}°"
    if kind == "exclude":
        channel = meta.get("channel", "")
        label = f"zakazany przedział: {_CHANNEL_NAMES.get(channel, channel)} ({name(0)})"
        if channel == "hue":
            return label, f"poza {req['lo']:.0f}°–{req['hi']:.0f}°", f"{got:.1f}°"
        unit = " względne" if meta.get("mode") == "rel" else ""
        return label, f"poza {req['lo']:.3f}–{req['hi']:.3f}{unit}", f"{got:.3f}"
    if kind == "contrast_bg":
        fmt, unit = _contrast_fmt(meta.get("metric", "wcag21"))
        return (
            "kontrast z tłem",
            _fmt_interval(req["lo"], req["hi"], fmt, unit),
            _with_unit(got, fmt, unit),
        )
    if kind == "extreme":
        fmt, unit = _contrast_fmt(meta.get("metric", "wcag21"))
        weakest = meta.get("which") == "weakest"
        return (
            f"{'najsłabszy' if weakest else 'najmocniejszy'} kontrast ({name(0)})",
            f"{'<' if weakest else '>'} {_with_unit(req['bound'], fmt, unit)}",
            _with_unit(got, fmt, unit),
        )
    if kind == "pair_distance":
        return f"odległość {name(0)} – {name(1)}", f"ΔE ≥ {req['min']:.3f}", f"{got:.3f}"
    if kind == "pair_cvd":
        cvd = _CVD_NAMES.get(meta.get("cvd", ""), "daltonizmie")
        return (
            f"odróżnialność przy {cvd}: {name(0)} – {name(1)}",
            f"ΔE ≥ {req['min']:.3f}",
            f"{got:.3f}",
        )
    if kind == "rel":
        return _relation_text(v, name)
    if kind == "spread":
        return (
            "rozrzut jasności akcentów",
            _fmt_interval(req["lo"], req["hi"], ".3f"),
            f"{got:.3f}",
        )
    if kind == "scheme":
        return (
            f"układ odcieni ({name(0)})",
            f"{req['target']:.0f}° ± {req['tol']:.0f}°",
            f"{got:.1f}°",
        )
    if kind == "avoid":
        return f"unikany kolor ({name(0)})", f"ΔE ≥ {req['min']:.3f}", f"{got:.3f}"
    if kind == "gamut":
        return f"gamut sRGB ({name(0)})", f"C ≤ {req['hi']:.3f}", f"{got:.3f}"
    if kind == "diversity":
        return "różnorodność", f"średnie ΔE ≥ {req['min']:.3f}", f"{got:.3f}"
    return v.key, "—", f"{got:g}"  # nieznany rodzaj (nowszy silnik): pokaż chociaż klucz


def _relation_text(v: Violation, name: Any) -> tuple[str, str, str]:
    req, meta, got = v.req, v.meta, v.achieved
    rel_kind = meta.get("rel_kind", "")
    op, value, tol = req["op"], req["value"], req["tol"]
    if rel_kind == "mix":
        label = f"zależność: mieszanka {name(1)} i {name(2)} ({name(0)})"
        return label, f"ΔE od mieszanki ≤ {tol:.3f}", f"{got:.3f}"
    label = f"zależność: {_REL_NAMES.get(rel_kind, rel_kind)} względem {name(1)} ({name(0)})"
    if rel_kind == "hue":
        return label, _op_req(op, value, tol, ".0f") + "°", f"{got:.0f}°"
    if rel_kind == "contrast":
        fmt, unit = _contrast_fmt(meta.get("metric", "wcag21"))
        return label, _op_req(op, value, tol, fmt, unit), _with_unit(got, fmt, unit)
    if rel_kind == "chroma" and meta.get("chroma_op") == "mul":
        sign = "=" if op == "eq" else "≥" if op == "ge" else "≤"
        return label, f"{sign} {value:.2f} × {name(1)}", f"{got:.3f}"
    return label, _op_req(op, value, tol, ".3f"), f"{got:.3f}"  # jasność, nasycenie, odległość
