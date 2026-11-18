"""Zapis i odczyt sesji (format ``algopalette.v2``), wczytywanie v1, ścieżki XDG, autozapis.

Kodowanie JSON jest jawne (nazwy pól, brak pickle); ten sam dokument czyta silnik natywny
(``algopalette._engine``), więc kształt jest kontraktem. Wczytanie waliduje strukturę: każdy zły
lub brakujący element kończy się ``SessionFormatError`` z polskim komunikatem (nigdy surowym
``KeyError``/``TypeError``). ``hex`` przy kolorach jest informacją dla człowieka i jest pomijany
przy wczytaniu (źródłem prawdy jest OKLCH). Pliki ``algopalette.v1`` są migrowane przy wczytaniu
(``migrate.migrate_v1``); zapis jest zawsze w v2. Nieznane pola są pomijane — dzięki temu
starsze pliki v2 z usuniętą obsługą daltonizmu (``globals.cvd``, zasada ``cvd_min_distance``)
wczytują się bez błędu, a przy zapisie tych pól już nie ma.
"""

import json
import math
import os
import tempfile
from dataclasses import fields
from pathlib import Path
from typing import Any, get_args

from algopalette.color import to_hex
from algopalette.model import (
    MAX_ACCENTS,
    MIN_ACCENTS,
    OKLCH,
    RULE_FIELDS,
    Band,
    ChromaBand,
    ChromaMode,
    ContrastBound,
    ContrastMetric,
    DeltaEMethod,
    Exclusions,
    FitMethod,
    GlobalSettings,
    HueArc,
    HueScheme,
    Interval,
    OptimizerSettings,
    Relation,
    RelKind,
    RelOp,
    Role,
    Rule,
    RulesLock,
    Session,
    Slot,
    SlotRules,
    role_of,
    rule_fields_for,
)

FORMAT = "algopalette.v2"
FORMAT_V1 = "algopalette.v1"
MAX_FILE_BYTES = 16 * 1024 * 1024
APP_DIR = "algopalette"

_HUE_KINDS = get_args(HueScheme.__dataclass_fields__["kind"].type)


class SessionFormatError(ValueError):
    """Obcy, uszkodzony lub niekompletny plik sesji (komunikat po polsku)."""


# ---------------------------------------------------------------------------
# Ścieżki XDG
# ---------------------------------------------------------------------------


def _xdg(var: str, fallback: str) -> Path:
    """Katalog bazowy XDG; wartość pusta lub względna jest ignorowana (zgodnie ze specyfikacją)."""
    raw = os.environ.get(var, "")
    if raw and os.path.isabs(raw):
        return Path(raw)
    return Path.home() / fallback


def default_palettes_dir() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share") / APP_DIR / "palettes"


def autosave_path() -> Path:
    return _xdg("XDG_STATE_HOME", ".local/state") / APP_DIR / "last.json"


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / APP_DIR


# ---------------------------------------------------------------------------
# Walidujące gettery (jedyne miejsce, gdzie powstają komunikaty o błędach)
# ---------------------------------------------------------------------------


def _err(path: str, problem: str) -> SessionFormatError:
    return SessionFormatError(f"Uszkodzony plik sesji: pole „{path}” {problem}.")


def _join(path: str, key: str | int) -> str:
    return f"{path}[{key}]" if isinstance(key, int) else (f"{path}.{key}" if path else key)


def _dict(v: Any, path: str) -> dict[str, Any]:
    if not isinstance(v, dict):
        raise _err(path or "(korzeń)", "powinno być obiektem JSON")
    return v


def _list(v: Any, path: str) -> list[Any]:
    if not isinstance(v, list):
        raise _err(path, "powinno być listą")
    return v


def _get(d: dict[str, Any], key: str, path: str) -> Any:
    if key not in d:
        raise _err(_join(path, key), "nie istnieje")
    return d[key]


def _to_num(v: Any, path: str) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float):
        raise _err(path, "powinno być liczbą")
    if not math.isfinite(v):
        raise _err(path, "musi być liczbą skończoną")
    return float(v)


def _num(d: dict[str, Any], key: str, path: str) -> float:
    return _to_num(_get(d, key, path), _join(path, key))


def _opt_num(d: dict[str, Any], key: str, path: str) -> float | None:
    v = _get(d, key, path)
    return None if v is None else _to_num(v, _join(path, key))


def _nonneg(d: dict[str, Any], key: str, path: str) -> float:
    v = _num(d, key, path)
    if v < 0:
        raise _err(_join(path, key), "nie może być ujemne")
    return v


def _int(d: dict[str, Any], key: str, path: str, *, minimum: int | None = None) -> int:
    v = _get(d, key, path)
    if isinstance(v, bool) or not isinstance(v, int):
        raise _err(_join(path, key), "powinno być liczbą całkowitą")
    if minimum is not None and v < minimum:
        raise _err(_join(path, key), f"musi wynosić co najmniej {minimum}")
    return v


def _bool(d: dict[str, Any], key: str, path: str) -> bool:
    v = _get(d, key, path)
    if not isinstance(v, bool):
        raise _err(_join(path, key), "powinno być wartością logiczną (true/false)")
    return v


def _str(d: dict[str, Any], key: str, path: str) -> str:
    v = _get(d, key, path)
    if not isinstance(v, str):
        raise _err(_join(path, key), "powinno być tekstem")
    return v


def _opt_str(d: dict[str, Any], key: str, path: str) -> str | None:
    v = _get(d, key, path)
    if v is not None and not isinstance(v, str):
        raise _err(_join(path, key), "powinno być tekstem lub null")
    return v


def _lit(d: dict[str, Any], key: str, path: str, allowed: tuple[Any, ...]) -> Any:
    v = _get(d, key, path)
    if not isinstance(v, str) or v not in allowed:
        raise _err(_join(path, key), f"musi mieć jedną z wartości: {', '.join(allowed)}")
    return v


def _opt_lit(d: dict[str, Any], key: str, path: str, allowed: tuple[Any, ...]) -> Any:
    return None if _get(d, key, path) is None else _lit(d, key, path, allowed)


# ---------------------------------------------------------------------------
# Kodowanie
# ---------------------------------------------------------------------------

_METRICS = get_args(ContrastMetric)
_DELTA_E = get_args(DeltaEMethod)
_FIT = get_args(FitMethod)
_CHROMA_MODES = get_args(ChromaMode)
_REL_KINDS = get_args(RelKind)
_RULES_LOCKS = get_args(RulesLock)
_REL_OPS = get_args(RelOp)
_REL_METRICS = (*_METRICS, *_DELTA_E)
_EXTREMES = ("weakest", "strongest")
_ROLE_NAMES: dict[Role, str] = {"bg": "tła", "fg": "tekstu", "accent": "akcentu"}


def _enc_oklch(c: OKLCH) -> dict[str, Any]:
    return {"l": c.l, "c": c.c, "h": c.h}


def _dec_oklch(v: Any, path: str) -> OKLCH:
    d = _dict(v, path)
    l_ = _num(d, "l", path)
    if not 0.0 <= l_ <= 1.0:
        raise _err(_join(path, "l"), "jasność L musi być w zakresie 0–1")
    return OKLCH(l_, _nonneg(d, "c", path), _num(d, "h", path) % 360.0)


# Zasady: dla każdego pola SlotRules osobny koder/dekoder wartości Rule.value.
def _enc_exclude(ex: Exclusions) -> list[list[float]]:
    return [[a, b] for a, b in ex]


def _dec_exclude(d: dict[str, Any], path: str, *, hue: bool) -> Exclusions:
    ep = _join(path, "exclude")
    out: list[tuple[float, float]] = []
    for i, pair in enumerate(_list(_get(d, "exclude", path), ep)):
        pp = _join(ep, i)
        if not isinstance(pair, list) or len(pair) != 2:
            raise _err(pp, "powinno być parą [od, do]")
        a, b = _to_num(pair[0], _join(pp, 0)), _to_num(pair[1], _join(pp, 1))
        if hue:
            if not (0.0 <= a <= 360.0 and 0.0 <= b <= 360.0):
                raise _err(pp, "odcienie muszą być w zakresie 0–360")
            if a % 360.0 == b % 360.0:
                raise _err(pp, "zakazany przedział odcienia musi mieć różne końce")
        elif not a < b:
            raise _err(pp, "zakazany przedział musi mieć „od” mniejsze niż „do”")
        out.append((a, b))
    return tuple(out)


def _dec_hue_arc(d: dict[str, Any], p: str) -> HueArc:
    lo, hi = _num(d, "lo", p), _num(d, "hi", p)
    for key, v in (("lo", lo), ("hi", hi)):
        if not 0.0 <= v <= 360.0:
            raise _err(_join(p, key), "odcień musi być w zakresie 0–360")
    return HueArc(lo, hi, _dec_exclude(d, p, hue=True))


_VALUE_CODECS: dict[str, tuple[Any, Any]] = {
    "lightness": (
        lambda v: {"lo": v.lo, "hi": v.hi, "exclude": _enc_exclude(v.exclude)},
        lambda d, p: Band(
            _opt_num(d, "lo", p), _opt_num(d, "hi", p), _dec_exclude(d, p, hue=False)
        ),
    ),
    "chroma": (
        lambda v: {"mode": v.mode, "lo": v.lo, "hi": v.hi, "exclude": _enc_exclude(v.exclude)},
        lambda d, p: ChromaBand(
            _lit(d, "mode", p, _CHROMA_MODES),
            _opt_num(d, "lo", p),
            _opt_num(d, "hi", p),
            _dec_exclude(d, p, hue=False),
        ),
    ),
    "hue": (
        lambda v: {"lo": v.lo, "hi": v.hi, "exclude": _enc_exclude(v.exclude)},
        _dec_hue_arc,
    ),
    "contrast_bg": (
        lambda v: {"metric": v.metric, "lo": v.lo, "hi": v.hi},
        lambda d, p: ContrastBound(
            _opt_lit(d, "metric", p, _METRICS), _opt_num(d, "lo", p), _opt_num(d, "hi", p)
        ),
    ),
    "lightness_spread": (
        lambda v: {"lo": v.lo, "hi": v.hi},
        lambda d, p: Interval(_opt_num(d, "lo", p), _opt_num(d, "hi", p)),
    ),
}
_SCALAR_FIELDS = ("min_distance",)


def _enc_rule(name: str, rule: Rule[Any] | None) -> dict[str, Any] | None:
    if rule is None:
        return None
    # pola bez kodera w _VALUE_CODECS to liczba albo „extreme” (kodowane wprost)
    value = _VALUE_CODECS[name][0](rule.value) if name in _VALUE_CODECS else rule.value
    return {"value": value, "enabled": rule.enabled, "hard": rule.hard, "weight": rule.weight}


def _dec_rule(name: str, v: Any, path: str) -> Rule[Any] | None:
    if v is None:
        return None
    d = _dict(v, path)
    vp = _join(path, "value")
    raw = _get(d, "value", path)
    if name in _VALUE_CODECS:
        value: Any = _VALUE_CODECS[name][1](_dict(raw, vp), vp)
    elif name in _SCALAR_FIELDS:
        value = _to_num(raw, vp)
    else:  # extreme
        if raw not in _EXTREMES:
            raise _err(vp, f"musi mieć jedną z wartości: {', '.join(_EXTREMES)}")
        value = raw
    return Rule(
        value, _bool(d, "enabled", path), _bool(d, "hard", path), _nonneg(d, "weight", path)
    )


def _enc_rules(rules: SlotRules) -> dict[str, Any]:
    return {name: _enc_rule(name, getattr(rules, name)) for name in RULE_FIELDS}


def _dec_rules(v: Any, path: str, role: Role) -> SlotRules:
    d = _dict(v, path)
    applicable = rule_fields_for(role)
    kwargs: dict[str, Any] = {}
    for name in RULE_FIELDS:
        rule = _dec_rule(name, _get(d, name, path), _join(path, name))
        if rule is not None and name not in applicable:
            raise _err(_join(path, name), f"ta zasada nie dotyczy {_ROLE_NAMES[role]}")
        kwargs[name] = rule
    return SlotRules(**kwargs)


def _enc_relation(r: Relation) -> dict[str, Any]:
    return {f.name: getattr(r, f.name) for f in fields(Relation)}


def _dec_relation(v: Any, path: str) -> Relation:
    d = _dict(v, path)
    rel = _dec_relation_raw(d, path)
    allowed = {"contrast": ("wcag21", "apca"), "distance": ("ok", "2000", "hyab", "itp", "cam16")}
    if rel.metric is not None and rel.metric not in allowed.get(rel.kind, ()):
        raise _err(
            _join(path, "metric"), f"metryka „{rel.metric}” nie pasuje do relacji „{rel.kind}”"
        )
    if not 0.0 <= rel.t <= 1.0:
        raise _err(_join(path, "t"), "t mieszanki musi być w zakresie 0–1")
    return rel


def _dec_relation_raw(d: dict[str, Any], path: str) -> Relation:
    return Relation(
        kind=_lit(d, "kind", path, _REL_KINDS),
        target=_str(d, "target", path),
        op=_lit(d, "op", path, _REL_OPS),
        value=_num(d, "value", path),
        tol=_nonneg(d, "tol", path),
        chroma_op=_lit(d, "chroma_op", path, ("add", "mul")),
        chroma_mode=_lit(d, "chroma_mode", path, _CHROMA_MODES),
        metric=_opt_lit(d, "metric", path, _REL_METRICS),
        other=_opt_str(d, "other", path),
        t=_num(d, "t", path),
        enabled=_bool(d, "enabled", path),
        hard=_bool(d, "hard", path),
        weight=_nonneg(d, "weight", path),
    )


def _enc_slot(s: Slot, fit: FitMethod) -> dict[str, Any]:
    out = {
        "id": s.id,
        "name": s.name,
        "locked": s.locked,
        "value": _enc_oklch(s.value),
        "hex": to_hex(s.value, fit),  # tylko informacyjnie
        "use_scheme": s.use_scheme,
        "rules": _enc_rules(s.rules),
        "relations": [_enc_relation(r) for r in s.relations],
    }
    if s.rules_lock != "off":  # klucz opcjonalny: bez kłódki dokument jak przed jej dodaniem
        out["rules_lock"] = s.rules_lock
    return out


def _dec_slot(v: Any, path: str, role: Role) -> Slot:
    d = _dict(v, path)
    rels = _list(_get(d, "relations", path), _join(path, "relations"))
    return Slot(
        id=_str(d, "id", path),
        name=_str(d, "name", path),
        locked=_bool(d, "locked", path),
        value=_dec_oklch(_get(d, "value", path), _join(path, "value")),
        rules=_dec_rules(_get(d, "rules", path), _join(path, "rules"), role),
        use_scheme=_bool(d, "use_scheme", path),
        relations=tuple(
            _dec_relation(r, _join(_join(path, "relations"), i)) for i, r in enumerate(rels)
        ),
        # Pole dopisane po wydaniu v2: starsze pliki go nie mają.
        rules_lock=_lit(d, "rules_lock", path, _RULES_LOCKS) if "rules_lock" in d else "off",
    )


def _enc_hue_scheme(h: HueScheme) -> dict[str, Any]:
    out = {f.name: getattr(h, f.name) for f in fields(HueScheme)}
    out["custom"] = list(h.custom)
    return out


def _dec_hue_scheme(v: Any, path: str) -> HueScheme:
    d = _dict(v, path)
    cp = _join(path, "custom")
    custom = tuple(
        _to_num(x, _join(cp, i)) for i, x in enumerate(_list(_get(d, "custom", path), cp))
    )
    return HueScheme(
        kind=_lit(d, "kind", path, _HUE_KINDS),
        rotation=_num(d, "rotation", path),
        center=_num(d, "center", path),
        spread=_num(d, "spread", path),
        custom=custom,
        tol=_nonneg(d, "tol", path),
        jitter=_nonneg(d, "jitter", path),
        hard=_bool(d, "hard", path),
        weight=_nonneg(d, "weight", path),
    )


def _enc_optimizer(o: OptimizerSettings) -> dict[str, Any]:
    return {f.name: getattr(o, f.name) for f in fields(OptimizerSettings)}


def _dec_optimizer(v: Any, path: str) -> OptimizerSettings:
    d = _dict(v, path)
    return OptimizerSettings(
        n_proposals=_int(d, "n_proposals", path, minimum=1),
        seed=_int(d, "seed", path, minimum=0),
        budget=_int(d, "budget", path, minimum=1),
        time_cap_s=_nonneg(d, "time_cap_s", path),
        min_diversity=_nonneg(d, "min_diversity", path),
        hard_weight=_nonneg(d, "hard_weight", path),
        threads=_int(d, "threads", path, minimum=0),
    )


def _enc_globals(g: GlobalSettings) -> dict[str, Any]:
    return {
        "polarity": g.polarity,
        "contrast_metric": g.contrast_metric,
        "delta_e": g.delta_e,
        "fit_method": g.fit_method,
        "hue_scheme": _enc_hue_scheme(g.hue_scheme),
        "lightness_spread": _enc_rule("lightness_spread", g.lightness_spread),
        "avoid_colors": [_enc_oklch(c) for c in g.avoid_colors],
        "avoid_distance": g.avoid_distance,
        "optimizer": _enc_optimizer(g.optimizer),
    }


def _dec_globals(v: Any, path: str) -> GlobalSettings:
    d = _dict(v, path)
    ap = _join(path, "avoid_colors")
    avoid = tuple(
        _dec_oklch(c, _join(ap, i)) for i, c in enumerate(_list(_get(d, "avoid_colors", path), ap))
    )
    return GlobalSettings(
        polarity=_lit(d, "polarity", path, ("dark", "light")),
        hue_scheme=_dec_hue_scheme(_get(d, "hue_scheme", path), _join(path, "hue_scheme")),
        lightness_spread=_dec_rule(
            "lightness_spread", _get(d, "lightness_spread", path), _join(path, "lightness_spread")
        ),
        contrast_metric=_lit(d, "contrast_metric", path, _METRICS),
        delta_e=_lit(d, "delta_e", path, _DELTA_E),
        fit_method=_lit(d, "fit_method", path, _FIT),
        avoid_colors=avoid,
        avoid_distance=_nonneg(d, "avoid_distance", path),
        optimizer=_dec_optimizer(_get(d, "optimizer", path), _join(path, "optimizer")),
    )


# ---------------------------------------------------------------------------
# Sesja <-> słownik
# ---------------------------------------------------------------------------


def session_to_dict(s: Session) -> dict[str, Any]:
    return {
        "format": FORMAT,
        "preset": s.preset,
        "view_model": s.view_model,
        "globals": _enc_globals(s.globals),
        "slots": [_enc_slot(sl, s.globals.fit_method) for sl in s.slots],
    }


def session_from_dict(data: Any) -> Session:
    """Waliduje dokument ``algopalette.v2`` i buduje ``Session``; błąd to ``SessionFormatError``."""
    d = _dict(data, "")
    fmt = d.get("format")
    if fmt != FORMAT:
        raise SessionFormatError(
            f"To nie jest plik sesji AlgoPalette: pole „format” ma wartość {fmt!r}, "
            f"oczekiwano „{FORMAT}”."
        )
    slots_raw = _list(_get(d, "slots", ""), "slots")
    accents = len(slots_raw) - 2
    if not MIN_ACCENTS <= accents <= MAX_ACCENTS:
        raise _err(
            "slots",
            f"ma {len(slots_raw)} kolorów; wymagane: tło, tekst i "
            f"{MIN_ACCENTS}–{MAX_ACCENTS} akcentów",
        )
    slots = tuple(_dec_slot(v, _join("slots", i), role_of(i)) for i, v in enumerate(slots_raw))
    if len({s.id for s in slots}) != len(slots):
        raise _err("slots", "zawiera powtórzone „id” kolorów")
    return Session(
        globals=_dec_globals(_get(d, "globals", ""), "globals"),
        slots=slots,
        preset=_opt_str(d, "preset", ""),
        view_model=_lit(d, "view_model", "", ("oklch", "hsl")) if "view_model" in d else "oklch",
    )


def decode_session(data: Any) -> tuple[Session, tuple[str, ...]]:
    """Dokument v2 albo v1 → ``(sesja, komunikaty migracji)``; dla v2 komunikatów nie ma."""
    if isinstance(data, dict) and data.get("format") == FORMAT_V1:
        from algopalette.migrate import migrate_v1  # import zwrotny: migrate korzysta z io

        migrated, notes = migrate_v1(data)
        return session_from_dict(migrated), tuple(notes)
    return session_from_dict(data), ()


# ---------------------------------------------------------------------------
# Plik
# ---------------------------------------------------------------------------


def _no_constant(name: str) -> Any:
    raise ValueError(f"niedozwolona stała JSON: {name}")


def save_session(s: Session, path: str | os.PathLike[str], overwrite: bool = False) -> None:
    """Zapisuje sesję atomowo (plik tymczasowy w tym samym katalogu + ``os.replace``).

    Istniejący plik bez ``overwrite=True`` → ``FileExistsError`` (plik nietknięty). Brakujące
    katalogi nadrzędne są tworzone. Błędy wejścia/wyjścia (brak uprawnień itp.) lecą jako
    ``OSError`` — łapie je warstwa interfejsu.
    """
    target = Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(f"Plik już istnieje: {target}")
    text = json.dumps(session_to_dict(s), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = target.stat().st_mode & 0o777 if target.exists() else 0o644
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, target)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _read_document(path: str | os.PathLike[str]) -> Any:
    p = Path(path)
    if p.stat().st_size > MAX_FILE_BYTES:
        raise SessionFormatError("Plik jest zbyt duży, by był plikiem sesji AlgoPalette.")
    raw = p.read_bytes()
    try:
        return json.loads(raw.decode("utf-8"), parse_constant=_no_constant)
    except UnicodeDecodeError as e:
        raise SessionFormatError(
            "Plik nie jest poprawnym tekstem UTF-8 (to nie jest sesja)."
        ) from e
    except (ValueError, RecursionError) as e:
        raise SessionFormatError(
            f"Plik nie jest poprawnym JSON-em (uszkodzony lub ucięty): {e}"
        ) from e


def load_session_ex(path: str | os.PathLike[str]) -> tuple[Session, tuple[str, ...]]:
    """Wczytuje sesję v2 albo v1; zwraca też komunikaty migracji (co przepadło albo się zmieniło).

    Brak pliku: ``FileNotFoundError``; zły format: ``SessionFormatError``.
    """
    return decode_session(_read_document(path))


def is_v1_file(path: str | os.PathLike[str]) -> bool:
    """Czy plik jest sesją w starym formacie ``algopalette.v1`` (nieczytelny plik → ``False``)."""
    try:
        data = _read_document(path)
    except (SessionFormatError, OSError):
        return False
    return isinstance(data, dict) and data.get("format") == FORMAT_V1


def load_session(path: str | os.PathLike[str]) -> Session:
    """Jak ``load_session_ex``, ale bez komunikatów migracji."""
    return load_session_ex(path)[0]
