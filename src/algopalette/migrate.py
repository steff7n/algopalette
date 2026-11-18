"""Migracja dokumentu ``algopalette.v1`` do ``algopalette.v2``.

Działa na słownikach (nie odtwarza starych klas modelu). W v1 kolor dziedziczył warunki roli
(pole ``null`` w slocie = warunek z ``globals.role_defaults``), a odcień miał dwa osobne warunki
(``hue_range`` i ``hue_target``). W v2 każdy kolor ma komplet własnych zasad i jedną zasadę
odcienia. Migracja nigdy nie jest cicha: wszystko, co przepada albo zmienia twardość, trafia do
listy komunikatów (po jednym zdaniu, z nazwą koloru).

Wynik przechodzi jeszcze pełną walidację w ``io.session_from_dict``; tutaj sprawdzane jest tylko
to, na czym migracja liczy.
"""

from __future__ import annotations

import copy
import math
from typing import Any

from algopalette.io import SessionFormatError
from algopalette.model import (
    RULE_FIELDS,
    arc_from_center,
    arc_intersection,
    arc_width,
    role_of,
    rule_fields_for,
)

FORMAT_V1 = "algopalette.v1"
FORMAT_V2 = "algopalette.v2"

# Dziewięć nastrojów v1, które zostały presetami o tych samych nazwach.
OLD_MOODS = (
    "neutralny",
    "chłodny mglisty",
    "neon",
    "ziemisty",
    "pastel",
    "nocny wysoki kontrast",
    "monochromatyczny z jednym akcentem",
    "retro terminal",
    "jesienny",
)

# ``max_evals`` v1 liczył oceny funkcji celu (gradient różnicami skończonymi: D + 1 ocen na krok);
# ``budget`` v2 liczy oceny z gradientem na jeden przebieg.
BUDGET_DIVISOR = 10
BUDGET_MIN = 300
BUDGET_MAX = 100_000

_RULE_NAMES = {
    "lightness": "jasność L",
    "chroma": "nasycenie C",
    "contrast_bg": "kontrast z tłem",
    "min_distance": "odległość od innych akcentów",
    "extreme": "skrajny kontrast",
}


def _err(path: str, problem: str) -> SessionFormatError:
    return SessionFormatError(f"Uszkodzony plik sesji: pole „{path or '(korzeń)'}” {problem}.")


def _join(path: str, key: str | int) -> str:
    return f"{path}[{key}]" if isinstance(key, int) else (f"{path}.{key}" if path else key)


def _obj(v: Any, path: str) -> dict[str, Any]:
    if not isinstance(v, dict):
        raise _err(path, "powinno być obiektem JSON")
    return v


def _field(d: dict[str, Any], key: str, path: str) -> Any:
    if key not in d:
        raise _err(_join(path, key), "nie istnieje")
    return d[key]


def _number(v: Any, path: str) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
        raise _err(path, "powinno być liczbą")
    return float(v)


def _flags(cond: dict[str, Any]) -> dict[str, Any]:
    return {k: cond[k] for k in ("enabled", "hard", "weight") if k in cond}


def _label(slot: dict[str, Any], index: int) -> str:
    name = slot.get("name")
    if isinstance(name, str) and name:
        return name
    return ("tło", "tekst")[index] if index < 2 else f"akcent {index - 1}"


def _rule(field: str, cond: dict[str, Any], path: str) -> dict[str, Any]:
    """Warunek v1 → zasada v2 (zakresy jasności i nasycenia dostają pustą listę zakazów)."""
    out = copy.deepcopy(cond)
    if field in ("lightness", "chroma"):
        value = _obj(_field(out, "value", path), _join(path, "value"))
        out["value"] = {**value, "exclude": []}
    return out


def _arc_of_range(cond: dict[str, Any], path: str) -> tuple[float, float]:
    value = _obj(_field(cond, "value", path), _join(path, "value"))
    lo = _number(_field(value, "lo", path), _join(path, "value.lo"))
    hi = _number(_field(value, "hi", path), _join(path, "value.hi"))
    if arc_width(lo, hi) == 360.0:
        return 0.0, 360.0
    return lo % 360.0, hi % 360.0


def _arc_of_target(cond: dict[str, Any], path: str) -> tuple[float, float]:
    value = _obj(_field(cond, "value", path), _join(path, "value"))
    target = _number(_field(value, "target", path), _join(path, "value.target"))
    tol = _number(_field(value, "tol", path), _join(path, "value.tol"))
    if tol < 0:
        raise _err(_join(path, "value.tol"), "nie może być ujemne")
    return arc_from_center(target % 360.0, tol)


def _hue_rule(arc: tuple[float, float], flags: dict[str, Any]) -> dict[str, Any]:
    return {"value": {"lo": arc[0], "hi": arc[1], "exclude": []}, **flags}


def _fmt_arc(arc: tuple[float, float]) -> str:
    return f"{arc[0]:.0f}–{arc[1]:.0f}°"


def _merge_hue(
    rng: Any, tgt: Any, label: str, path: str, notes: list[str]
) -> dict[str, Any] | None:
    """Jedna zasada odcienia z ``hue_range`` i ``hue_target`` (reguły ze speca §10)."""
    if rng is None and tgt is None:
        return None
    if tgt is None:
        cond = _obj(rng, _join(path, "hue_range"))
        return _hue_rule(_arc_of_range(cond, _join(path, "hue_range")), _flags(cond))
    if rng is None:
        cond = _obj(tgt, _join(path, "hue_target"))
        return _hue_rule(_arc_of_target(cond, _join(path, "hue_target")), _flags(cond))
    r = _obj(rng, _join(path, "hue_range"))
    t = _obj(tgt, _join(path, "hue_target"))
    r_arc = _arc_of_range(r, _join(path, "hue_range"))
    t_arc = _arc_of_target(t, _join(path, "hue_target"))
    r_on, t_on = r.get("enabled") is True, t.get("enabled") is True
    if r_on and not t_on:
        notes.append(
            f"{label}: wyłączony cel odcienia pominięto, została zasada z zakresu "
            f"({_fmt_arc(r_arc)})"
        )
        return _hue_rule(r_arc, _flags(r))
    if t_on and not r_on:
        notes.append(
            f"{label}: wyłączony zakres odcienia pominięto, została zasada z celu "
            f"({_fmt_arc(t_arc)})"
        )
        return _hue_rule(t_arc, _flags(t))
    if not r_on and not t_on:
        notes.append(
            f"{label}: zakres i cel odcienia były wyłączone — została wyłączona zasada z zakresu "
            f"({_fmt_arc(r_arc)}), cel pominięto"
        )
        return _hue_rule(r_arc, _flags(r))
    common = arc_intersection(r_arc, t_arc)
    if len(common) != 1:
        notes.append(
            f"{label}: zakres i cel odcienia nie mają jednej części wspólnej — została zasada "
            f"z zakresu ({_fmt_arc(r_arc)}), cel pominięto"
        )
        return _hue_rule(r_arc, _flags(r))
    r_hard, t_hard = r.get("hard") is True, t.get("hard") is True
    weights = [w for w in (r.get("weight"), t.get("weight")) if isinstance(w, int | float)]
    note = f"{label}: zakres i cel odcienia scalono do {_fmt_arc(common[0])}"
    if r_hard != t_hard:
        note += ", zasada jest teraz twarda"
    notes.append(note)
    merged = {"enabled": True, "hard": r_hard or t_hard, "weight": max(weights, default=1.0)}
    return _hue_rule(common[0], merged)


def _slot(
    raw: Any, index: int, roles: dict[str, dict[str, Any]], notes: list[str]
) -> dict[str, Any]:
    path = _join("slots", index)
    slot = _obj(raw, path)
    cpath = _join(path, "conditions")
    own = _obj(_field(slot, "conditions", path), cpath)
    role = role_of(index)
    label = _label(slot, index)
    applicable = rule_fields_for(role)

    def effective(name: str) -> Any:
        value = _field(own, name, cpath)
        if value is None:
            value = _field(roles[role], name, _join("globals.role_defaults", role))
        return value

    rng, tgt = effective("hue_range"), effective("hue_target")
    rules: dict[str, Any] = {}
    for name in RULE_FIELDS:
        if name == "hue":
            rules[name] = _merge_hue(rng, tgt, label, cpath, notes)
            continue
        cond = effective(name)
        if cond is not None and name not in applicable:
            notes.append(
                f"{label}: zasada „{_RULE_NAMES[name]}” nie dotyczy tego koloru — pominięto"
            )
            cond = None
        rules[name] = None if cond is None else _rule(name, _obj(cond, _join(cpath, name)), cpath)

    value = copy.deepcopy(_field(slot, "value", path))
    hue = value.get("h") if isinstance(value, dict) else None
    if isinstance(hue, int | float) and not isinstance(hue, bool) and math.isfinite(hue):
        value["h"] = float(hue) % 360.0
    had_hue = rng is not None or tgt is not None
    return {
        "id": _field(slot, "id", path),
        "name": _field(slot, "name", path),
        "locked": _field(slot, "locked", path),
        "value": value,
        "hex": slot.get("hex", ""),
        "use_scheme": not (had_hue and role == "accent"),
        "rules": rules,
        "relations": copy.deepcopy(_field(slot, "relations", path)),
    }


def _optimizer(raw: Any, notes: list[str]) -> dict[str, Any]:
    path = "globals.optimizer"
    opt = _obj(raw, path)
    max_evals = _field(opt, "max_evals", path)
    if isinstance(max_evals, bool) or not isinstance(max_evals, int):
        raise _err(_join(path, "max_evals"), "powinno być liczbą całkowitą")
    budget = min(max(round(max_evals / BUDGET_DIVISOR), BUDGET_MIN), BUDGET_MAX)
    if not BUDGET_MIN <= max_evals / BUDGET_DIVISOR <= BUDGET_MAX:
        notes.append(
            f"budżet generowania {max_evals} (stara jednostka) przeliczono na {budget} — "
            f"dozwolony zakres to {BUDGET_MIN}–{BUDGET_MAX}"
        )
    return {
        "n_proposals": _field(opt, "n_proposals", path),
        "seed": _field(opt, "seed", path),
        "budget": budget,
        "time_cap_s": _field(opt, "time_cap_s", path),
        "min_diversity": _field(opt, "min_diversity", path),
        "hard_weight": _field(opt, "hard_weight", path),
        "threads": 0,
    }


def migrate_v1(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Dokument v1 → ``(dokument v2, komunikaty)``. Wejście nie jest modyfikowane.

    Zły kształt wejścia → ``SessionFormatError`` ze ścieżką pola.
    """
    d = _obj(data, "")
    notes: list[str] = []
    g = _obj(_field(d, "globals", ""), "globals")
    rpath = "globals.role_defaults"
    roles_raw = _obj(_field(g, "role_defaults", "globals"), rpath)
    roles = {r: _obj(_field(roles_raw, r, rpath), _join(rpath, r)) for r in ("bg", "fg", "accent")}
    slots_raw = _field(d, "slots", "")
    if not isinstance(slots_raw, list):
        raise _err("slots", "powinno być listą")
    slots = [_slot(raw, i, roles, notes) for i, raw in enumerate(slots_raw)]

    mood = d.get("mood")
    preset: str | None = None
    if isinstance(mood, str):
        if mood in OLD_MOODS:
            preset = mood
        else:
            notes.append(
                f"nastrój „{mood}” nie ma odpowiednika wśród presetów — zasady kolorów zostały, "
                "oznaczenie presetu przepadło"
            )
    elif mood is not None:
        raise _err("mood", "powinno być tekstem lub null")

    def keep(key: str) -> Any:
        return copy.deepcopy(_field(g, key, "globals"))

    out_globals = {
        "polarity": keep("polarity"),
        "contrast_metric": keep("contrast_metric"),
        "delta_e": keep("delta_e"),
        "fit_method": keep("fit_method"),
        "hue_scheme": keep("hue_scheme"),
        "lightness_spread": keep("lightness_spread"),
        "avoid_colors": keep("avoid_colors"),
        "avoid_distance": keep("avoid_distance"),
        "optimizer": _optimizer(_field(g, "optimizer", "globals"), notes),
    }
    out = {
        "format": FORMAT_V2,
        "preset": preset,
        "view_model": d.get("view_model", "oklch"),
        "globals": out_globals,
        "slots": slots,
    }
    return out, notes
