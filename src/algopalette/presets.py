"""Presety: nazwane zestawy zasad całej palety.

Nałożenie presetu zastępuje zasady wszystkich kolorów, ich ``use_scheme``, układ odcieni i rozrzut
jasności (oraz metrykę kontrastu, jeśli preset ją określa). Nie rusza
wartości kolorów, kłódek, nazw, zależności, ustawień generowania ani listy unikanych kolorów.
Kolory z kłódką zasad (``Slot.rules_lock != "off"``) zachowują swoje zasady i ``use_scheme``.

Presety wbudowane są deklaracjami z ``presets_builtin`` (zależą od polaryzacji i metryki). Presety
użytkownika to zapisane zasady według pozycji koloru w ``config_dir()/presets.json``, ważne dla
polaryzacji i metryki, przy których je zapisano.
"""

from __future__ import annotations

import json
import os
import tempfile
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from algopalette import io as aio
from algopalette.globals_logic import change_metric
from algopalette.hue_layouts import LegacyScheme, to_scheme
from algopalette.model import (
    ContrastMetric,
    DeltaEMethod,
    HueScheme,
    Interval,
    Polarity,
    Rule,
    Session,
    SlotRules,
    role_of,
)
from algopalette.presets_builtin import BUILTIN, CATEGORIES, PresetDef
from algopalette.units import rules_in_method

__all__ = [
    "CATEGORIES",
    "USER_CATEGORY",
    "Preset",
    "apply_preset",
    "change_polarity",
    "delete_user_preset",
    "is_modified",
    "list_presets",
    "migrate_user_moods",
    "save_user_preset",
    "search",
    "supports",
]

USER_CATEGORY = "Własne"
DEFAULT_PRESET = "neutralny"
_FILE = "presets.json"
_FORMAT = "algopalette.presets.v1"
_BY_NAME: dict[str, PresetDef] = {p.name: p for p in BUILTIN}


@dataclass(frozen=True)
class Preset:
    name: str
    category: str
    description: str
    builtin: bool
    polarities: tuple[str, ...]


@dataclass(frozen=True)
class _Resolved:
    """Preset rozwinięty dla konkretnej polaryzacji, metryki i liczby kolorów."""

    polarity: Polarity
    contrast_metric: ContrastMetric
    hue_scheme: HueScheme
    lightness_spread: Rule[Interval] | None
    colors: tuple[tuple[SlotRules, bool], ...]  # (zasady, use_scheme) według pozycji
    recipe: HueScheme | LegacyScheme  # układ przed rozwinięciem (zależy od liczby akcentów)

    def scheme_for(self, current: HueScheme, n_accents: int) -> HueScheme:
        """Układ presetu rozwinięty do długości ``current`` — dodanie akcentu nie zmienia listy,
        więc nie oznacza presetu jako zmienionego. Pusta lista → dla ``n_accents``."""
        return to_scheme(self.recipe, len(current.hues) or n_accents)


# ---------------------------------------------------------------------------
# Plik presetów użytkownika
# ---------------------------------------------------------------------------


def _path() -> Path:
    return aio.config_dir() / _FILE


def _load_doc() -> dict[str, Any]:
    path = _path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"format": _FORMAT, "presets": {}}
    except (OSError, ValueError) as e:
        raise ValueError(f"Nie można odczytać pliku presetów {path}: {e}") from None
    if not isinstance(data, dict) or not isinstance(data.get("presets"), dict):
        raise ValueError(f"Plik presetów {path} ma zły format.")
    for name, entry in data["presets"].items():
        if not isinstance(entry, dict):
            raise ValueError(f"Plik presetów {path}: wpis „{name}” ma zły format.")
    return data


def _save_doc(doc: dict[str, Any]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _encode_entry(session: Session, description: str) -> dict[str, Any]:
    g = session.globals
    return {
        "description": description,
        "polarity": g.polarity,
        "contrast_metric": g.contrast_metric,
        "delta_e": g.delta_e,  # skala progów odległości w „colors” (przegląd 2026-11-18 C1)
        "hue_scheme": aio._enc_hue_scheme(g.hue_scheme),
        "lightness_spread": aio._enc_rule("lightness_spread", g.lightness_spread),
        "colors": [
            {"rules": aio._enc_rules(s.rules), "use_scheme": s.use_scheme} for s in session.slots
        ],
    }


def _decode_entry(
    name: str, entry: dict[str, Any], n_slots: int, delta_e: DeltaEMethod
) -> _Resolved:
    """Preset użytkownika z progami odległości przeliczonymi na ``delta_e`` sesji (wpisy sprzed
    2026-11-18 nie mają ``delta_e`` — traktowane jako ``ok``)."""
    try:
        raw = entry["colors"]
        if not isinstance(raw, list) or len(raw) < 3:
            raise aio.SessionFormatError("lista kolorów musi mieć co najmniej 3 pozycje")
        saved_de = aio._lit(entry, "delta_e", "", aio._DELTA_E) if "delta_e" in entry else "ok"
        colors: list[tuple[SlotRules, bool]] = []
        for i in range(n_slots):
            item = raw[min(i, len(raw) - 1)]  # brakujące akcenty = ostatni zapisany
            rules = aio._dec_rules(item["rules"], f"colors[{i}].rules", role_of(i))
            rules = rules_in_method(rules, saved_de, delta_e)
            use_scheme = item["use_scheme"]
            if not isinstance(use_scheme, bool):
                raise aio.SessionFormatError(f"colors[{i}].use_scheme powinno być true/false")
            colors.append((rules, use_scheme))
        recipe = aio._dec_hue_recipe(entry["hue_scheme"], "hue_scheme")
        return _Resolved(
            recipe=recipe,
            polarity=aio._lit(entry, "polarity", "", ("dark", "light")),
            contrast_metric=aio._lit(entry, "contrast_metric", "", ("wcag21", "apca")),
            hue_scheme=to_scheme(recipe, n_slots - 2),
            lightness_spread=aio._dec_rule(
                "lightness_spread", entry["lightness_spread"], "lightness_spread"
            ),
            colors=tuple(colors),
        )
    except (aio.SessionFormatError, KeyError, TypeError) as e:
        raise ValueError(f"Preset „{name}” w pliku {_FILE} ma zły format: {e}") from None


# ---------------------------------------------------------------------------
# Lista i wyszukiwanie
# ---------------------------------------------------------------------------


def _fold(text: str) -> str:
    """Do porównań bez względu na wielkość liter i polskie znaki („chlodny” = „chłodny”)."""
    text = text.casefold().replace("ł", "l")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def list_presets() -> list[Preset]:
    """Wbudowane (w stałej kolejności), potem użytkownika (alfabetycznie)."""
    out = [Preset(p.name, p.category, p.description, True, tuple(p.polarities)) for p in BUILTIN]
    user = _load_doc()["presets"]
    for name in sorted(user, key=_fold):
        entry = user[name]
        polarity = entry.get("polarity")
        out.append(
            Preset(
                name,
                USER_CATEGORY,
                str(entry.get("description", "")),
                False,
                (polarity,) if polarity in ("dark", "light") else (),
            )
        )
    return out


def search(query: str, category: str | None = None) -> list[Preset]:
    """Presety, których nazwa albo opis zawiera ``query``; ``category`` zawęża do kategorii."""
    needle = _fold(query.strip())
    return [
        p
        for p in list_presets()
        if (category is None or p.category == category)
        and (not needle or needle in _fold(p.name) or needle in _fold(p.description))
    ]


def supports(name: str, polarity: str) -> bool:
    """Czy preset da się nałożyć dla tej polaryzacji (nieznany preset → ``False``)."""
    return any(p.name == name and polarity in p.polarities for p in list_presets())


# ---------------------------------------------------------------------------
# Nakładanie
# ---------------------------------------------------------------------------


def _resolve(
    name: str,
    polarity: Polarity,
    metric: ContrastMetric,
    n_slots: int,
    *,
    strict: bool,
    delta_e: DeltaEMethod = "ok",
) -> _Resolved:
    """``strict`` — polaryzacja nieobsługiwana przez preset to błąd; inaczej bierze pierwszą
    obsługiwaną. Progi odległości wychodzą w skali ``delta_e`` (metoda ΔE sesji)."""
    pdef = _BY_NAME.get(name)
    if pdef is None:
        user = _load_doc()["presets"]
        if name not in user:
            raise ValueError(f"Nie ma presetu „{name}”.")
        res = _decode_entry(name, user[name], n_slots, delta_e)
        if strict and res.polarity != polarity:
            raise ValueError(f"Preset „{name}” zapisano dla innej polaryzacji tła.")
        return res
    if polarity not in pdef.polarities:
        if strict:
            raise ValueError(f"Preset „{name}” nie ma wersji dla tej polaryzacji tła.")
        polarity = pdef.polarities[0]
    rules = pdef.build(polarity, metric)
    if rules.contrast_metric is not None and rules.contrast_metric != metric:
        metric = rules.contrast_metric
        rules = pdef.build(polarity, metric)
    colors: list[tuple[SlotRules, bool]] = [(rules.bg, True), (rules.fg, True)]
    for number in range(1, n_slots - 1):
        accent, use_scheme = rules.accent, rules.use_scheme
        override = rules.overrides.get(number)
        if override is not None:
            accent = replace(accent, **override.changes)
            if override.use_scheme is not None:
                use_scheme = override.use_scheme
        colors.append((accent, use_scheme))
    # deklaracje presetów mają progi odległości w skali ΔE ok
    colors = [(rules_in_method(r, "ok", delta_e), u) for r, u in colors]
    scheme = to_scheme(rules.hue_scheme, n_slots - 2)
    return _Resolved(
        polarity, metric, scheme, rules.lightness_spread, tuple(colors), rules.hue_scheme
    )


def apply_preset(session: Session, name: str, *, polarity: str | None = None) -> Session:
    """Nakłada preset. Bez ``polarity`` bierze polaryzację sesji (a gdy preset jej nie obsługuje —
    własną); z ``polarity`` wymaga, żeby preset ją obsługiwał (``ValueError``)."""
    if polarity is not None and polarity not in ("dark", "light"):
        raise ValueError("Polaryzacja musi być „dark” albo „light”.")
    g = session.globals
    wanted: Polarity = (
        g.polarity if polarity is None else ("dark" if polarity == "dark" else "light")
    )
    res = _resolve(
        name,
        wanted,
        g.contrast_metric,
        len(session.slots),
        strict=polarity is not None,
        delta_e=g.delta_e,
    )
    s = change_metric(session, res.contrast_metric)  # przelicza progi zależności
    g2 = replace(
        s.globals,
        polarity=res.polarity,
        hue_scheme=res.hue_scheme,
        lightness_spread=res.lightness_spread,
    )
    slots = tuple(
        slot if slot.rules_lock != "off" else replace(slot, rules=rules, use_scheme=use_scheme)
        for slot, (rules, use_scheme) in zip(s.slots, res.colors, strict=True)
    )
    return replace(s, globals=g2, slots=slots, preset=name)


def is_modified(session: Session) -> bool:
    """Czy zasady sesji różnią się od świeżo nałożonego ``session.preset``.

    Liczą się zasady kolorów, ``use_scheme``, układ odcieni i rozrzut jasności (oraz metryka,
    jeśli preset ją określa). Kolory z kłódką zasad się nie liczą (ich odstępstwo od
    presetu jest zamierzone). Bez presetu → ``False``; preset, którego już nie ma albo który nie
    pasuje do polaryzacji sesji → ``True``.
    """
    if session.preset is None:
        return False
    g = session.globals
    try:
        res = _resolve(
            session.preset,
            g.polarity,
            g.contrast_metric,
            len(session.slots),
            strict=True,
            delta_e=g.delta_e,
        )
    except ValueError:
        return True
    if res.contrast_metric != g.contrast_metric:
        return True
    scheme = res.scheme_for(g.hue_scheme, len(session.slots) - 2)
    if scheme != g.hue_scheme or res.lightness_spread != g.lightness_spread:
        return True
    return any(
        (_comparable(slot.rules), slot.use_scheme) != (_comparable(rules), use_scheme)
        for slot, (rules, use_scheme) in zip(session.slots, res.colors, strict=True)
        if slot.rules_lock == "off"
    )


def _comparable(rules: SlotRules) -> SlotRules:
    """Próg odległości zaokrąglony do 9 cyfr znaczących: przeliczenia między metodami ΔE
    (ok → 2000 → hyab) różnią się od przeliczenia wprost o błąd zaokrągleń float."""
    r = rules.min_distance
    if r is None:
        return rules
    return replace(rules, min_distance=replace(r, value=float(f"{r.value:.9g}")))


def change_polarity(session: Session, polarity: str, *, reapply: bool) -> Session:
    """Zmiana polaryzacji tła.

    ``reapply=True`` nakłada dla nowej polaryzacji bieżący preset (albo „neutralny”, gdy presetu
    nie ma lub nie obsługuje tej polaryzacji); ``reapply=False`` zmienia tylko oznaczenie
    polaryzacji, zasady zostają.
    """
    if polarity not in ("dark", "light"):
        raise ValueError("Polaryzacja musi być „dark” albo „light”.")
    if not reapply:
        pol: Polarity = "dark" if polarity == "dark" else "light"
        return replace(session, globals=replace(session.globals, polarity=pol))
    name = session.preset
    if name is None or not supports(name, polarity):
        name = DEFAULT_PRESET
    return apply_preset(session, name, polarity=polarity)


# ---------------------------------------------------------------------------
# Presety użytkownika
# ---------------------------------------------------------------------------


def save_user_preset(name: str, session: Session, description: str = "") -> None:
    """Zapisuje zasady wszystkich kolorów (wg pozycji), układ, rozrzut, polaryzację i metrykę."""
    name = name.strip()
    if not name:
        raise ValueError("Nazwa presetu nie może być pusta.")
    if name in _BY_NAME:
        raise ValueError(f"„{name}” to preset wbudowany — wybierz inną nazwę.")
    doc = _load_doc()
    doc["presets"][name] = _encode_entry(session, description)
    _save_doc(doc)


def delete_user_preset(name: str) -> None:
    if name in _BY_NAME:
        raise ValueError(f"„{name}” to preset wbudowany — nie można go usunąć.")
    doc = _load_doc()
    if name not in doc["presets"]:
        raise ValueError(f"Nie ma presetu „{name}”.")
    del doc["presets"][name]
    _save_doc(doc)


def _mood_as_session(v1_globals: Any) -> Session:
    """Nastrój v1 (warunki ról) → sesja v2 z tłem, tekstem i jednym akcentem (przez migrację)."""
    from algopalette.migrate import migrate_v1

    blank = dict.fromkeys(
        (
            "hue_range",
            "hue_target",
            "chroma",
            "lightness",
            "contrast_bg",
            "min_distance",
            "extreme",
        )
    )
    slots = [
        {
            "id": f"m{i}",
            "name": "",
            "locked": False,
            "value": {"l": 0.5, "c": 0.0, "h": 0.0},
            "conditions": dict(blank),
            "relations": [],
        }
        for i in range(3)
    ]
    doc = {"format": "algopalette.v1", "mood": None, "globals": v1_globals, "slots": slots}
    return aio.session_from_dict(migrate_v1(doc)[0])


def migrate_user_moods() -> int:
    """Jednorazowo przenosi nastroje użytkownika (``moods.json``) do presetów; zwraca ich liczbę.

    Nastrój trzymał warunki ról, więc powstaje preset z tłem, tekstem i jednym akcentem (przy
    nakładaniu powielanym na wszystkie akcenty). Stary plik zostaje nietknięty. Drugie wywołanie
    niczego nie dopisuje — także wtedy, gdy przeniesiony preset został potem usunięty.
    """
    path = aio.config_dir() / "moods.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    moods = data.get("moods") if isinstance(data, dict) else None
    if not isinstance(moods, dict):
        return 0
    doc = _load_doc()
    if doc.get("migrated_moods"):
        return 0
    count = 0
    for name, entry in moods.items():
        if not isinstance(name, str) or name in _BY_NAME or name in doc["presets"]:
            continue
        if not isinstance(entry, dict):
            continue
        try:
            session = _mood_as_session(entry.get("globals"))
        except aio.SessionFormatError:
            continue
        doc["presets"][name] = _encode_entry(session, str(entry.get("description", "")))
        count += 1
    doc["migrated_moods"] = True
    _save_doc(doc)
    return count
