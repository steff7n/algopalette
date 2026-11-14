"""Zapis i odczyt sesji (format ``algopalette.v1``), ścieżki XDG, autozapis.

Kodowanie JSON jest jawne (nazwy pól, brak pickle). Wczytanie waliduje strukturę: każdy zły lub
brakujący element kończy się ``SessionFormatError`` z polskim komunikatem (nigdy surowym
``KeyError``/``TypeError``). ``hex`` przy slotach jest informacją dla człowieka i jest pomijany
przy wczytaniu (źródłem prawdy jest OKLCH).
"""

import json
import math
import os
import tempfile
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, get_args

from algopalette.color import to_hex
from algopalette.model import (
    MAX_ACCENTS,
    MIN_ACCENTS,
    OKLCH,
    ChromaMode,
    ChromaRange,
    Cond,
    ContrastBound,
    ContrastMetric,
    CvdMethod,
    CvdSettings,
    CvdType,
    DeltaEMethod,
    FitMethod,
    FrozenMap,
    GlobalSettings,
    HueRange,
    HueScheme,
    HueTarget,
    Interval,
    OptimizerSettings,
    Relation,
    RelKind,
    RelOp,
    Role,
    Session,
    Slot,
    SlotConditions,
)

FORMAT = "algopalette.v1"
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

_ROLES: tuple[Role, ...] = ("bg", "fg", "accent")
_METRICS = get_args(ContrastMetric)
_DELTA_E = get_args(DeltaEMethod)
_CVD_TYPES = get_args(CvdType)
_CVD_METHODS = get_args(CvdMethod)
_FIT = get_args(FitMethod)
_CHROMA_MODES = get_args(ChromaMode)
_REL_KINDS = get_args(RelKind)
_REL_OPS = get_args(RelOp)
_REL_METRICS = (*_METRICS, *_DELTA_E)
_EXTREMES = ("weakest", "strongest")


def _enc_oklch(c: OKLCH) -> dict[str, Any]:
    return {"l": c.l, "c": c.c, "h": c.h}


def _dec_oklch(v: Any, path: str) -> OKLCH:
    d = _dict(v, path)
    return OKLCH(_num(d, "l", path), _nonneg(d, "c", path), _num(d, "h", path))


# Warunki: dla każdego pola SlotConditions osobny koder/dekoder wartości Cond.value.
def _enc_interval(v: Interval) -> dict[str, Any]:
    return {"lo": v.lo, "hi": v.hi}


def _dec_interval(d: dict[str, Any], p: str) -> Interval:
    return Interval(_opt_num(d, "lo", p), _opt_num(d, "hi", p))


_VALUE_CODECS: dict[str, tuple[Any, Any]] = {
    "hue_range": (
        lambda v: {"lo": v.lo, "hi": v.hi},
        lambda d, p: HueRange(_num(d, "lo", p), _num(d, "hi", p)),
    ),
    "hue_target": (
        lambda v: {"target": v.target, "tol": v.tol},
        lambda d, p: HueTarget(_num(d, "target", p), _nonneg(d, "tol", p)),
    ),
    "chroma": (
        lambda v: {"mode": v.mode, "lo": v.lo, "hi": v.hi},
        lambda d, p: ChromaRange(
            _lit(d, "mode", p, _CHROMA_MODES), _opt_num(d, "lo", p), _opt_num(d, "hi", p)
        ),
    ),
    "lightness": (_enc_interval, _dec_interval),
    "contrast_bg": (
        lambda v: {"metric": v.metric, "lo": v.lo, "hi": v.hi},
        lambda d, p: ContrastBound(
            _opt_lit(d, "metric", p, _METRICS), _opt_num(d, "lo", p), _opt_num(d, "hi", p)
        ),
    ),
}
_SCALAR_FIELDS = ("min_distance", "cvd_min_distance")


def _enc_cond(name: str, cond: Cond[Any] | None) -> dict[str, Any] | None:
    if cond is None:
        return None
    # pola bez kodera w _VALUE_CODECS to skalar albo „extreme” (kodowane wprost)
    value = _VALUE_CODECS[name][0](cond.value) if name in _VALUE_CODECS else cond.value
    return {"value": value, "enabled": cond.enabled, "hard": cond.hard, "weight": cond.weight}


def _dec_cond(name: str, v: Any, path: str) -> Cond[Any] | None:
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
    return Cond(
        value, _bool(d, "enabled", path), _bool(d, "hard", path), _nonneg(d, "weight", path)
    )


def _enc_conditions(sc: SlotConditions) -> dict[str, Any]:
    return {f.name: _enc_cond(f.name, getattr(sc, f.name)) for f in fields(SlotConditions)}


def _dec_conditions(v: Any, path: str) -> SlotConditions:
    d = _dict(v, path)
    kwargs = {
        f.name: _dec_cond(f.name, _get(d, f.name, path), _join(path, f.name))
        for f in fields(SlotConditions)
    }
    return SlotConditions(**kwargs)


def _enc_relation(r: Relation) -> dict[str, Any]:
    return {f.name: getattr(r, f.name) for f in fields(Relation)}


def _dec_relation(v: Any, path: str) -> Relation:
    d = _dict(v, path)
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
    return {
        "id": s.id,
        "name": s.name,
        "locked": s.locked,
        "value": _enc_oklch(s.value),
        "hex": to_hex(s.value, fit),  # tylko informacyjnie
        "conditions": _enc_conditions(s.conditions),
        "relations": [_enc_relation(r) for r in s.relations],
    }


def _dec_slot(v: Any, path: str) -> Slot:
    d = _dict(v, path)
    rels = _list(_get(d, "relations", path), _join(path, "relations"))
    return Slot(
        id=_str(d, "id", path),
        name=_str(d, "name", path),
        locked=_bool(d, "locked", path),
        value=_dec_oklch(_get(d, "value", path), _join(path, "value")),
        conditions=_dec_conditions(_get(d, "conditions", path), _join(path, "conditions")),
        relations=tuple(
            _dec_relation(r, _join(_join(path, "relations"), i)) for i, r in enumerate(rels)
        ),
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


def _enc_cvd(c: CvdSettings) -> dict[str, Any]:
    return {"types": sorted(c.types), "method": c.method, "severity": c.severity}


def _dec_cvd(v: Any, path: str) -> CvdSettings:
    d = _dict(v, path)
    tp = _join(path, "types")
    types: list[Any] = []
    for i, t in enumerate(_list(_get(d, "types", path), tp)):
        if not isinstance(t, str) or t not in _CVD_TYPES:
            raise _err(_join(tp, i), f"musi mieć jedną z wartości: {', '.join(_CVD_TYPES)}")
        types.append(t)
    return CvdSettings(
        frozenset(types), _lit(d, "method", path, _CVD_METHODS), _nonneg(d, "severity", path)
    )


def _enc_optimizer(o: OptimizerSettings) -> dict[str, Any]:
    return {f.name: getattr(o, f.name) for f in fields(OptimizerSettings)}


def _dec_optimizer(v: Any, path: str) -> OptimizerSettings:
    d = _dict(v, path)
    return OptimizerSettings(
        n_proposals=_int(d, "n_proposals", path, minimum=1),
        seed=_int(d, "seed", path),
        max_evals=_int(d, "max_evals", path, minimum=1),
        time_cap_s=_nonneg(d, "time_cap_s", path),
        min_diversity=_nonneg(d, "min_diversity", path),
        hard_weight=_nonneg(d, "hard_weight", path),
    )


def _enc_globals(g: GlobalSettings) -> dict[str, Any]:
    return {
        "polarity": g.polarity,
        "role_defaults": {r: _enc_conditions(g.role_defaults[r]) for r in _ROLES},
        "hue_scheme": _enc_hue_scheme(g.hue_scheme),
        "lightness_spread": _enc_cond("lightness", g.lightness_spread),
        "contrast_metric": g.contrast_metric,
        "delta_e": g.delta_e,
        "cvd": _enc_cvd(g.cvd),
        "fit_method": g.fit_method,
        "avoid_colors": [_enc_oklch(c) for c in g.avoid_colors],
        "avoid_distance": g.avoid_distance,
        "optimizer": _enc_optimizer(g.optimizer),
    }


def _dec_globals(v: Any, path: str) -> GlobalSettings:
    d = _dict(v, path)
    rp = _join(path, "role_defaults")
    rd = _dict(_get(d, "role_defaults", path), rp)
    role_defaults = {r: _dec_conditions(_get(rd, r, rp), _join(rp, r)) for r in _ROLES}
    ap = _join(path, "avoid_colors")
    avoid = tuple(
        _dec_oklch(c, _join(ap, i)) for i, c in enumerate(_list(_get(d, "avoid_colors", path), ap))
    )
    return GlobalSettings(
        polarity=_lit(d, "polarity", path, ("dark", "light")),
        role_defaults=FrozenMap(role_defaults),
        hue_scheme=_dec_hue_scheme(_get(d, "hue_scheme", path), _join(path, "hue_scheme")),
        lightness_spread=_dec_cond(
            "lightness", _get(d, "lightness_spread", path), _join(path, "lightness_spread")
        ),
        contrast_metric=_lit(d, "contrast_metric", path, _METRICS),
        delta_e=_lit(d, "delta_e", path, _DELTA_E),
        cvd=_dec_cvd(_get(d, "cvd", path), _join(path, "cvd")),
        fit_method=_lit(d, "fit_method", path, _FIT),
        avoid_colors=avoid,
        avoid_distance=_nonneg(d, "avoid_distance", path),
        optimizer=_dec_optimizer(_get(d, "optimizer", path), _join(path, "optimizer")),
    )


# ``mood_snapshot`` ma wartości dowolnego typu modelu (np. ``Cond``, ``HueScheme``): kodowanie
# ogólne z jawnymi znacznikami ``$type``/``$tuple``/``$frozenset``/``$map``.
_SNAPSHOT_TYPES: dict[str, type] = {
    t.__name__: t
    for t in (
        OKLCH,
        Interval,
        Cond,
        HueRange,
        HueTarget,
        ChromaRange,
        ContrastBound,
        SlotConditions,
        Relation,
        HueScheme,
        CvdSettings,
        OptimizerSettings,
    )
}


def _enc_any(v: Any) -> Any:
    if v is None or isinstance(v, bool | int | float | str):
        return v
    if isinstance(v, tuple | list):
        return {"$tuple": [_enc_any(x) for x in v]}
    if isinstance(v, frozenset | set):
        items = [_enc_any(x) for x in v]
        return {"$frozenset": sorted(items, key=lambda x: json.dumps(x, sort_keys=True))}
    if isinstance(v, Mapping):
        return {"$map": [[_enc_any(k), _enc_any(x)] for k, x in v.items()]}
    if is_dataclass(v) and not isinstance(v, type) and type(v).__name__ in _SNAPSHOT_TYPES:
        return {
            "$type": type(v).__name__,
            "fields": {f.name: _enc_any(getattr(v, f.name)) for f in fields(v)},
        }
    raise TypeError(f"Nieobsługiwany typ w mood_snapshot: {type(v).__name__}")


def _dec_any(v: Any, path: str) -> Any:
    if v is None or isinstance(v, bool | int | float | str):
        if isinstance(v, float) and not math.isfinite(v):
            raise _err(path, "musi być liczbą skończoną")
        return v
    if not isinstance(v, dict) or len(v) not in (1, 2):
        raise _err(path, "ma nieznaną strukturę (brak znacznika typu)")
    if "$tuple" in v:
        items = _list(v["$tuple"], _join(path, "$tuple"))
        return tuple(_dec_any(x, _join(path, i)) for i, x in enumerate(items))
    if "$frozenset" in v:
        items = _list(v["$frozenset"], _join(path, "$frozenset"))
        try:
            return frozenset(_dec_any(x, _join(path, i)) for i, x in enumerate(items))
        except TypeError as e:
            raise _err(path, "zawiera niehashowalny element zbioru") from e
    if "$map" in v:
        pairs = _list(v["$map"], _join(path, "$map"))
        out: dict[Any, Any] = {}
        for i, pair in enumerate(pairs):
            pp = _join(path, i)
            if not isinstance(pair, list) or len(pair) != 2:
                raise _err(pp, "powinno być parą [klucz, wartość]")
            out[_dec_any(pair[0], pp)] = _dec_any(pair[1], pp)
        try:
            return FrozenMap(out)
        except TypeError as e:  # pragma: no cover - klucze dict są już hashowalne
            raise _err(path, "ma niehashowalny klucz") from e
    if "$type" in v:
        name = v["$type"]
        cls = _SNAPSHOT_TYPES.get(name) if isinstance(name, str) else None
        if cls is None:
            raise _err(_join(path, "$type"), "ma nieznany typ")
        raw = _dict(v.get("fields"), _join(path, "fields"))
        try:
            return cls(**{k: _dec_any(x, _join(path, k)) for k, x in raw.items()})
        except TypeError as e:
            raise _err(path, f"nie pasuje do typu {name}") from e
    raise _err(path, "ma nieznaną strukturę (nieznany znacznik)")


# ---------------------------------------------------------------------------
# Sesja <-> słownik
# ---------------------------------------------------------------------------


def session_to_dict(s: Session) -> dict[str, Any]:
    snap = s.mood_snapshot
    return {
        "format": FORMAT,
        "mood": s.mood,
        "mood_snapshot": None if snap is None else {k: _enc_any(v) for k, v in snap.items()},
        "globals": _enc_globals(s.globals),
        "slots": [_enc_slot(sl, s.globals.fit_method) for sl in s.slots],
    }


def session_from_dict(data: Any) -> Session:
    """Waliduje i buduje ``Session``; każdy błąd to ``SessionFormatError``."""
    d = _dict(data, "")
    fmt = d.get("format")
    if fmt != FORMAT:
        raise SessionFormatError(
            f"To nie jest plik sesji AlgoPalette: pole „format” ma wartość {fmt!r}, "
            f"oczekiwano „{FORMAT}”."
        )
    snap_raw = _get(d, "mood_snapshot", "")
    snapshot: FrozenMap[str, Any] | None = None
    if snap_raw is not None:
        sd = _dict(snap_raw, "mood_snapshot")
        snapshot = FrozenMap({k: _dec_any(v, _join("mood_snapshot", k)) for k, v in sd.items()})
    slots_raw = _list(_get(d, "slots", ""), "slots")
    slots = tuple(_dec_slot(v, _join("slots", i)) for i, v in enumerate(slots_raw))
    accents = len(slots) - 2
    if not MIN_ACCENTS <= accents <= MAX_ACCENTS:
        raise _err(
            "slots",
            f"ma {len(slots)} slotów; wymagane: tło, tekst i {MIN_ACCENTS}–{MAX_ACCENTS} akcentów",
        )
    if len({s.id for s in slots}) != len(slots):
        raise _err("slots", "zawiera powtórzone „id” slotów")
    return Session(
        globals=_dec_globals(_get(d, "globals", ""), "globals"),
        slots=slots,
        mood=_opt_str(d, "mood", ""),
        mood_snapshot=snapshot,
    )


# ---------------------------------------------------------------------------
# Plik
# ---------------------------------------------------------------------------


def _no_constant(name: str) -> Any:
    raise ValueError(f"niedozwolona stała JSON: {name}")


def save_session(s: Session, path: str | os.PathLike[str], overwrite: bool = False) -> None:
    """Zapisuje sesję atomowo (plik tymczasowy w tym samym katalogu + ``os.replace``).

    Istniejący plik bez ``overwrite=True`` → ``FileExistsError`` (plik nietknięty). Brakujące
    katalogi nadrzędne są tworzone. Błędy wejścia/wyjścia (brak uprawnień itp.) lecą jako
    ``OSError`` — łapie je warstwa TUI.
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


def load_session(path: str | os.PathLike[str]) -> Session:
    """Wczytuje sesję. Brak pliku: ``FileNotFoundError``; zły format: ``SessionFormatError``."""
    p = Path(path)
    if p.stat().st_size > MAX_FILE_BYTES:
        raise SessionFormatError("Plik jest zbyt duży, by był plikiem sesji AlgoPalette.")
    raw = p.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8"), parse_constant=_no_constant)
    except UnicodeDecodeError as e:
        raise SessionFormatError(
            "Plik nie jest poprawnym tekstem UTF-8 (to nie jest sesja)."
        ) from e
    except (ValueError, RecursionError) as e:
        raise SessionFormatError(
            f"Plik nie jest poprawnym JSON-em (uszkodzony lub ucięty): {e}"
        ) from e
    return session_from_dict(data)
