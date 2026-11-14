"""Nastroje: nazwane, jawne zestawy ustawień całej palety (spec §5.5).

Nastrój wbudowany zależy od polaryzacji i metryki kontrastu sesji (zakresy jasności i progi
kontrastu muszą do nich pasować). Zastosowanie nastroju:

1. resetuje część „nastrojową” ustawień globalnych (``role_defaults`` → domyślne dla polaryzacji i
   metryki, ``hue_scheme`` → równo po kole, ``lightness_spread`` → brak),
2. nakłada nadpisania nastroju,
3. zapamiętuje je w ``Session.mood_snapshot`` (klucze ``role_defaults.<rola>.<pole>``,
   ``hue_scheme``, ``lightness_spread``), dzięki czemu UI pokazuje źródło wartości „nastrój”.

Ustawienia techniczne (metryki, daltonizm, gamut, optymalizator, polaryzacja) i sloty zostają.
Nastroje użytkownika to zapisane ustawienia globalne w ``config_dir()/moods.json``.
"""

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any, cast

from algopalette import io as aio
from algopalette.model import (
    ChromaRange,
    Cond,
    ContrastBound,
    ContrastMetric,
    GlobalSettings,
    HueRange,
    HueScheme,
    HueTarget,
    Interval,
    Role,
    Session,
    SlotConditions,
    default_role_defaults,
    snapshot_key,
)

Overrides = dict[str, Any]
Builder = Callable[[str, ContrastMetric], Overrides]


@dataclass(frozen=True)
class Mood:
    name: str
    description: str
    builtin: bool


def _pick(polarity: str, dark: tuple[float, float], light: tuple[float, float]) -> Interval:
    lo, hi = dark if polarity == "dark" else light
    return Interval(lo, hi)


def _contrast(metric: ContrastMetric, wcag: float, apca: float) -> Cond[ContrastBound]:
    return Cond(ContrastBound(None, wcag if metric == "wcag21" else apca, None))


def _neutral(pol: str, metric: ContrastMetric) -> Overrides:
    return {}


def _cool_misty(pol: str, metric: ContrastMetric) -> Overrides:
    return {
        "hue_scheme": HueScheme("analogous", center=220.0, spread=110.0, tol=15.0),
        "lightness_spread": Cond(Interval(None, 0.12), hard=False),
        snapshot_key("accent", "lightness"): Cond(_pick(pol, (0.66, 0.80), (0.40, 0.52))),
        snapshot_key("accent", "chroma"): Cond(ChromaRange("abs", 0.03, 0.09)),
        snapshot_key("bg", "chroma"): Cond(ChromaRange("abs", 0.01, 0.03)),
        snapshot_key("bg", "hue_range"): Cond(HueRange(200.0, 260.0), hard=False),
    }


def _neon(pol: str, metric: ContrastMetric) -> Overrides:
    return {
        "hue_scheme": HueScheme("equal", rotation=330.0, tol=20.0),
        snapshot_key("accent", "lightness"): Cond(_pick(pol, (0.66, 0.86), (0.45, 0.60))),
        snapshot_key("accent", "chroma"): Cond(ChromaRange("rel", 0.85, 1.0)),
        snapshot_key("bg", "lightness"): Cond(_pick(pol, (0.08, 0.14), (0.95, 0.99))),
        snapshot_key("bg", "chroma"): Cond(ChromaRange("abs", 0.0, 0.02)),
    }


EARTH = (30.0, 60.0, 90.0, 140.0, 15.0, 45.0, 75.0, 110.0, 25.0, 55.0, 125.0, 40.0, 95.0, 65.0)


def _earthy(pol: str, metric: ContrastMetric) -> Overrides:
    return {
        "hue_scheme": HueScheme("custom", custom=EARTH, tol=12.0),
        snapshot_key("accent", "lightness"): Cond(_pick(pol, (0.58, 0.78), (0.38, 0.55))),
        snapshot_key("accent", "chroma"): Cond(ChromaRange("abs", 0.04, 0.11)),
        snapshot_key("bg", "chroma"): Cond(ChromaRange("abs", 0.01, 0.03)),
        snapshot_key("bg", "hue_range"): Cond(HueRange(40.0, 80.0), hard=False),
    }


def _pastel(pol: str, metric: ContrastMetric) -> Overrides:
    return {
        "hue_scheme": HueScheme("equal", rotation=10.0, tol=15.0),
        snapshot_key("accent", "lightness"): Cond(_pick(pol, (0.84, 0.93), (0.55, 0.65))),
        snapshot_key("accent", "chroma"): Cond(ChromaRange("rel", 0.22, 0.42)),
    }


def _night_contrast(pol: str, metric: ContrastMetric) -> Overrides:
    return {
        "hue_scheme": HueScheme("equal", rotation=20.0, tol=15.0),
        snapshot_key("bg", "lightness"): Cond(_pick(pol, (0.04, 0.10), (0.97, 1.0))),
        snapshot_key("bg", "chroma"): Cond(ChromaRange("abs", 0.0, 0.015)),
        snapshot_key("fg", "lightness"): Cond(_pick(pol, (0.95, 0.995), (0.05, 0.15))),
        snapshot_key("fg", "contrast_bg"): _contrast(metric, 15.0, 100.0),
        snapshot_key("accent", "lightness"): Cond(_pick(pol, (0.70, 0.80), (0.30, 0.42))),
        snapshot_key("accent", "chroma"): Cond(ChromaRange("abs", 0.08, 0.16)),
        snapshot_key("accent", "contrast_bg"): _contrast(metric, 7.0, 75.0),
    }


MONO = (35.0,) + (220.0,) * 13


def _mono_accent(pol: str, metric: ContrastMetric) -> Overrides:
    return {
        # Pierwszy akcent ciepły (35°), reszta w jednym odcieniu 220°.
        "hue_scheme": HueScheme("custom", custom=MONO, tol=10.0, hard=True),
        "lightness_spread": Cond(Interval(0.25, None), hard=False),
        snapshot_key("accent", "lightness"): Cond(_pick(pol, (0.55, 0.92), (0.25, 0.60))),
        snapshot_key("accent", "chroma"): Cond(ChromaRange("abs", 0.02, 0.12)),
        snapshot_key("accent", "min_distance"): Cond(0.04, hard=False),
    }


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


def _retro(pol: str, metric: ContrastMetric) -> Overrides:
    return {
        "hue_scheme": HueScheme("custom", custom=PHOSPHOR, tol=10.0),
        snapshot_key("accent", "lightness"): Cond(_pick(pol, (0.62, 0.86), (0.35, 0.55))),
        snapshot_key("accent", "chroma"): Cond(ChromaRange("abs", 0.08, 0.18)),
        snapshot_key("bg", "chroma"): Cond(ChromaRange("abs", 0.01, 0.03)),
        snapshot_key("bg", "hue_target"): Cond(HueTarget(145.0, 20.0), hard=False),
        snapshot_key("fg", "hue_target"): Cond(HueTarget(140.0, 25.0), hard=False),
    }


AUTUMN = (30.0, 55.0, 80.0, 15.0, 45.0, 100.0, 65.0, 25.0, 40.0, 90.0, 20.0, 70.0, 50.0, 35.0)


def _autumn(pol: str, metric: ContrastMetric) -> Overrides:
    return {
        "hue_scheme": HueScheme("custom", custom=AUTUMN, tol=10.0),
        snapshot_key("accent", "lightness"): Cond(_pick(pol, (0.60, 0.80), (0.38, 0.55))),
        snapshot_key("accent", "chroma"): Cond(ChromaRange("abs", 0.08, 0.16)),
        snapshot_key("bg", "chroma"): Cond(ChromaRange("abs", 0.01, 0.025)),
        snapshot_key("bg", "hue_range"): Cond(HueRange(25.0, 60.0), hard=False),
    }


BUILTIN: dict[str, tuple[str, Builder]] = {
    "neutralny": ("Równo po kole, średnie nasycenie — punkt wyjścia.", _neutral),
    "chłodny mglisty": (
        "Błękity i zielenie, niskie nasycenie, mały rozrzut jasności.",
        _cool_misty,
    ),
    "neon": ("Maksymalne nasycenie w gamucie, odcienie szeroko, bardzo ciemne tło.", _neon),
    "ziemisty": ("Ciepłe, przygaszone brązy, oliwki i ochry.", _earthy),
    "pastel": ("Jasne, mało nasycone akcenty.", _pastel),
    "nocny wysoki kontrast": (
        "Prawie czarne tło, bardzo wysoki kontrast tekstu i akcentów.",
        _night_contrast,
    ),
    "monochromatyczny z jednym akcentem": (
        "Jeden odcień w wielu jasnościach + pierwszy akcent ciepły.",
        _mono_accent,
    ),
    "retro terminal": ("Fosforowe zielenie i bursztyny, tło z nutą zieleni.", _retro),
    "jesienny": ("Pomarańcze, rudości i złoto.", _autumn),
}


# ---------------------------------------------------------------------------
# Nastroje użytkownika
# ---------------------------------------------------------------------------


def _load_user() -> dict[str, dict[str, Any]]:
    path = aio.config_dir() / "moods.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise ValueError(f"Nie można odczytać pliku nastrojów {path}: {e}") from None
    if not isinstance(data, dict) or not isinstance(data.get("moods"), dict):
        raise ValueError(f"Plik nastrojów {path} ma zły format.")
    return data["moods"]


def _save_user(moods: Mapping[str, Any]) -> None:
    path = aio.config_dir() / "moods.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(
            {"format": "algopalette.moods.v1", "moods": dict(moods)}, ensure_ascii=False, indent=1
        ),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def list_moods() -> list[Mood]:
    """Wbudowane (w stałej kolejności), potem użytkownika (alfabetycznie)."""
    out = [Mood(name, desc, True) for name, (desc, _) in BUILTIN.items()]
    for name, entry in sorted(_load_user().items()):
        out.append(Mood(name, str(entry.get("description", "")), False))
    return out


def save_user_mood(name: str, session: Session, description: str = "") -> None:
    name = name.strip()
    if not name:
        raise ValueError("Nazwa nastroju nie może być pusta.")
    if name in BUILTIN:
        raise ValueError(f"„{name}” to nastrój wbudowany — wybierz inną nazwę.")
    moods = _load_user()
    moods[name] = {"description": description, "globals": aio._enc_globals(session.globals)}
    _save_user(moods)


def delete_user_mood(name: str) -> None:
    if name in BUILTIN:
        raise ValueError(f"„{name}” to nastrój wbudowany — nie można go usunąć.")
    moods = _load_user()
    if name not in moods:
        raise ValueError(f"Nie ma nastroju „{name}”.")
    del moods[name]
    _save_user(moods)


# ---------------------------------------------------------------------------
# Zastosowanie
# ---------------------------------------------------------------------------


def _user_overrides(entry: Mapping[str, Any]) -> Overrides:
    g: GlobalSettings = aio._dec_globals(entry["globals"], "nastrój")
    out: Overrides = {"hue_scheme": g.hue_scheme, "lightness_spread": g.lightness_spread}
    for role, sc in g.role_defaults.items():
        for field in SlotConditions.__dataclass_fields__:
            out[snapshot_key(role, field)] = getattr(sc, field)
    return out


def mood_overrides(name: str, session: Session) -> Overrides:
    g = session.globals
    if name in BUILTIN:
        return BUILTIN[name][1](g.polarity, g.contrast_metric)
    user = _load_user()
    if name not in user:
        raise ValueError(f"Nie ma nastroju „{name}”.")
    return _user_overrides(user[name])


def apply_mood(session: Session, name: str) -> Session:
    """Nakłada nastrój na ustawienia globalne (jawnie, z ``mood_snapshot``); sloty bez zmian."""
    ov = mood_overrides(name, session)
    g = session.globals
    roles: dict[str, SlotConditions] = dict(default_role_defaults(g.polarity, g.contrast_metric))
    hue_scheme = HueScheme("equal")
    spread = None
    snapshot: dict[str, Any] = {}
    for key, value in ov.items():
        if key == "hue_scheme":
            hue_scheme = value
        elif key == "lightness_spread":
            spread = value
        elif key.startswith("role_defaults."):
            _, role, field = key.split(".")
            roles[role] = replace(roles[role], **{field: value})
        else:
            raise ValueError(f"Nieznany klucz nastroju: {key}")
        snapshot[key] = value
    # Snapshot obejmuje też wartości zresetowane do domyślnych (pokazywane jako „nastrój”).
    for role, sc in roles.items():
        for field in SlotConditions.__dataclass_fields__:
            snapshot.setdefault(snapshot_key(cast(Role, role), field), getattr(sc, field))
    snapshot.setdefault("hue_scheme", hue_scheme)
    snapshot.setdefault("lightness_spread", spread)
    g2 = replace(
        g,
        role_defaults=cast("dict[Role, SlotConditions]", roles),
        hue_scheme=hue_scheme,
        lightness_spread=spread,
    )
    return replace(session, globals=g2, mood=name, mood_snapshot=snapshot)
