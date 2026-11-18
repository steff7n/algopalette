"""Pamięć podręczna znormalizowanych katalogów motywów (``$XDG_CACHE_HOME/algopalette/themes``).

Zapisujemy listę ``Theme`` jako JSON (nie surową odpowiedź), z datą pobrania. Uszkodzony plik
pamięci jest traktowany jak jej brak — ``load`` nigdy nie rzuca wyjątku.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from algopalette.io import _xdg
from algopalette.themes.model import Theme, theme_from_dict, theme_to_dict

_VERSION = 1


@dataclass(frozen=True)
class Cached:
    themes: tuple[Theme, ...]
    fetched_at: float  # epoch s
    total: int | None = None  # Lospec totalCount


def cache_dir() -> Path:
    return _xdg("XDG_CACHE_HOME", ".cache") / "algopalette" / "themes"


def _safe(key: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", key.lower())


def _path(key: str) -> Path:
    return cache_dir() / f"{_safe(key)}.json"


def load(key: str) -> Cached | None:
    """Brak pliku, błąd odczytu, zła wersja lub kształt → ``None`` (nigdy wyjątek)."""
    try:
        data = json.loads(_path(key).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != _VERSION:
            return None
        fetched_at = data["fetched_at"]
        total = data.get("total")
        raw = data["themes"]
        if isinstance(fetched_at, bool) or not isinstance(fetched_at, int | float):
            return None
        if total is not None and (isinstance(total, bool) or not isinstance(total, int)):
            return None
        if not isinstance(raw, list):
            return None
        themes = tuple(theme_from_dict(d) for d in raw)
        return Cached(themes, float(fetched_at), total)
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return None


def save(
    key: str, themes: Sequence[Theme], *, total: int | None = None, now: float | None = None
) -> None:
    """Zapis atomowy (plik tymczasowy obok + ``os.replace``); ``OSError`` idzie wyżej."""
    target = _path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _VERSION,
        "fetched_at": time.time() if now is None else now,
        "total": total,
        "themes": [theme_to_dict(t) for t in themes],
    }
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=target.stem + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # ensure_ascii: samotny surogat z danych źródła nie wywróci zapisu (przegląd M19)
            json.dump(payload, f, ensure_ascii=True)
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def is_fresh(c: Cached, ttl_s: float, now: float) -> bool:
    return 0 <= now - c.fetched_at < ttl_s


def clear(prefix: str = "") -> None:
    """Usuwa pliki kluczy zaczynających się od ``prefix`` (puste = wszystkie)."""
    d = cache_dir()
    pre = _safe(prefix)
    try:
        files = list(d.glob("*.json"))
    except OSError:
        return
    for p in files:
        if p.stem.startswith(pre):
            with contextlib.suppress(OSError):
                p.unlink()
