"""Katalogi źródeł: świeża pamięć → bez sieci; inaczej pobierz, sparsuj, zapamiętaj (spec §9).

Sieć zawiodła, a jest (nawet przeterminowana) pamięć → wynik z pamięci z ``offline=True``.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from algopalette.themes import cache, net, parsers
from algopalette.themes.model import SourceId, Theme, ThemeError

CATALOG_URLS: dict[SourceId, str] = {
    "base16": "https://codeload.github.com/tinted-theming/schemes/tar.gz/HEAD",
    "gogh": "https://raw.githubusercontent.com/Gogh-Co/Gogh/master/data/themes.json",
    "wt": "https://raw.githubusercontent.com/atomcorp/themes/master/themes.json",
}
LOSPEC_LOAD = "https://lospec.com/palette-list/load"
CATALOG_TTL_S = 7 * 86400
LOSPEC_TTL_S = 86400
LOSPEC_PAGE_SIZE = 10  # palet na stronę po stronie serwera; strony liczone od 0

_PARSERS: dict[SourceId, Callable[[bytes], parsers.Parsed]] = {
    "base16": parsers.parse_tinted,
    "gogh": parsers.parse_gogh,
    "wt": parsers.parse_wt,
}

Progress = Callable[[int, int | None], None]
Cancelled = Callable[[], bool]


@dataclass(frozen=True)
class CatalogResult:
    themes: tuple[Theme, ...]
    fetched_at: float
    offline: bool  # True = przeterminowana pamięć, bo sieć zawiodła
    skipped: int = 0
    total: int | None = None  # Lospec: liczba palet po stronie serwera
    cache_error: str | None = None  # zapis do pamięci się nie udał


def lospec_tag(text: str) -> str:
    """Pierwsze słowo, małymi literami („Warm pastel” → „warm”)."""
    words = text.strip().lower().split()
    return words[0] if words else ""


def lospec_url(tag: str, page: int) -> str:
    q = {
        "colorNumberFilterType": "max",
        "colorNumber": 16,
        "page": page,
        "tag": lospec_tag(tag),
        "sortingType": "downloads",
    }
    return f"{LOSPEC_LOAD}?{urlencode(q)}"


def _lospec_key(tag: str, page: int) -> str:
    """Klucz pamięci bez kolizji po ``cache._safe``: tag trafia do nazwy jako skrót."""
    digest = hashlib.sha1(lospec_tag(tag).encode()).hexdigest()[:16]
    return f"lospec-{digest}-{page}"


def _get(
    key: str,
    ttl_s: float,
    url: str,
    parse: Callable[[bytes], tuple[parsers.Parsed, int | None]],
    client: httpx.Client,
    *,
    refresh: bool,
    now: float | None,
    on_progress: Progress | None,
    cancelled: Cancelled | None,
) -> CatalogResult:
    t = time.time() if now is None else now
    cached = cache.load(key)
    if cached is not None and not refresh and cache.is_fresh(cached, ttl_s, t):
        return CatalogResult(cached.themes, cached.fetched_at, False, total=cached.total)
    try:
        data = net.fetch(client, url, on_progress=on_progress, cancelled=cancelled)
    except net.FetchError as e:
        if e.kind != "cancelled" and cached is not None:
            return CatalogResult(cached.themes, cached.fetched_at, True, total=cached.total)
        raise
    try:
        parsed, total = parse(data)
    except ThemeError:
        if cached is not None:  # np. portal hotelowy zwrócił HTML z kodem 200
            return CatalogResult(cached.themes, cached.fetched_at, True, total=cached.total)
        raise
    error = None
    try:
        cache.save(key, parsed.themes, total=total, now=t)
    except (OSError, ValueError) as e:
        why = e.strerror if isinstance(e, OSError) and e.strerror else e
        error = f"Nie udało się zapisać katalogu w pamięci podręcznej: {why}"
    return CatalogResult(parsed.themes, t, False, parsed.skipped, total, error)


def load_catalog(
    source: SourceId,
    client: httpx.Client,
    *,
    refresh: bool = False,
    now: float | None = None,
    on_progress: Progress | None = None,
    cancelled: Cancelled | None = None,
) -> CatalogResult:
    """Katalog źródła plikowego (wszystko poza Lospec)."""
    if source not in _PARSERS:
        raise ValueError(f"{source!r} nie ma katalogu plikowego")
    parse = _PARSERS[source]
    return _get(
        source,
        CATALOG_TTL_S,
        CATALOG_URLS[source],
        lambda b: (parse(b), None),
        client,
        refresh=refresh,
        now=now,
        on_progress=on_progress,
        cancelled=cancelled,
    )


def lospec_page(
    tag: str,
    page: int,
    client: httpx.Client,
    *,
    refresh: bool = False,
    now: float | None = None,
    cancelled: Cancelled | None = None,
) -> CatalogResult:
    """Strona Lospec (``LOSPEC_PAGE_SIZE`` palet), najczęściej pobierane; pusty tag = bez filtra."""
    return _get(
        _lospec_key(tag, page),
        LOSPEC_TTL_S,
        lospec_url(tag, page),
        parsers.parse_lospec,
        client,
        refresh=refresh,
        now=now,
        on_progress=None,
        cancelled=cancelled,
    )


def refresh_all() -> None:
    """Czyści strony Lospec; katalogi plikowe odświeża ``load_catalog(refresh=True)``."""
    cache.clear("lospec")
