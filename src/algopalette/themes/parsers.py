"""Parsery odpowiedzi czterech źródeł motywów: ``bytes`` → ``Theme`` (spec §5–§6).

Bez Qt i bez sieci. Dokument nieczytelny jako całość (zły JSON, nie-gzip, zły kształt korzenia)
to ``ThemeError`` z nazwą źródła; pojedynczy zły wpis jest pomijany i liczony w ``Parsed.skipped``.
"""

from __future__ import annotations

import json
import re
import tarfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from io import BytesIO
from typing import Any
from urllib.parse import quote

import yaml

from algopalette.themes.model import SOURCES, SourceId, Theme, ThemeError

_HEX_RE = re.compile(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
# Plik motywu base16/base24 ma kilka KB; większy to śmieć albo próba nadużycia parsera YAML.
_MAX_YAML_BYTES = 256 * 1024
_LOSPEC_MIN, _LOSPEC_MAX = 3, 16

_BASE16_ACCENTS = tuple(f"base{c}" for c in ("08", "09", "0A", "0B", "0C", "0D", "0E", "0F"))
_BASE24_EXTRA = tuple(f"base{n}" for n in range(12, 18))
_TINTED_URL = "https://github.com/tinted-theming/schemes/blob/HEAD/{system}/{file}"

GOGH_URL = "https://gogh-co.github.io/Gogh/"
WT_URL = "https://windowsterminalthemes.dev/"
_LOSPEC_URL = "https://lospec.com/palette-list/"
ANSI_ACCENT_NAMES = (
    "czerwony",
    "zielony",
    "żółty",
    "niebieski",
    "magenta",
    "cyjan",
    "jasny czerwony",
    "jasny zielony",
    "jasny żółty",
    "jasny niebieski",
    "jasna magenta",
    "jasny cyjan",
)
_GOGH_KEYS = tuple(f"color_{i:02d}" for i in (*range(2, 8), *range(10, 16)))
_WT_KEYS = (
    "red",
    "green",
    "yellow",
    "blue",
    "purple",
    "cyan",
    "brightRed",
    "brightGreen",
    "brightYellow",
    "brightBlue",
    "brightPurple",
    "brightCyan",
)


@dataclass(frozen=True)
class Parsed:
    themes: tuple[Theme, ...]
    skipped: int


def normalize_hex(value: object) -> str | None:
    """``#rgb``/``#rrggbb`` (``#`` opcjonalny) → ``"#rrggbb"`` małymi literami; inaczej ``None``."""
    if not isinstance(value, str):
        return None
    m = _HEX_RE.fullmatch(value.strip())
    if m is None:
        return None
    h = m.group(1).lower()
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return "#" + h


def _roles_theme(
    *,
    source: SourceId,
    id_: str,
    name: str,
    author: str,
    url: str | None,
    bg: object,
    fg: object,
    accents: Iterable[tuple[str, object]],
) -> Theme | None:
    """Motyw z rolami albo ``None`` (zły hex tła/tekstu/akcentu, 0 akcentów po deduplikacji)."""
    bg_h, fg_h = normalize_hex(bg), normalize_hex(fg)
    if bg_h is None or fg_h is None:
        return None
    seen = {bg_h, fg_h}
    colors: list[str] = []
    names: list[str] = []
    for acc_name, raw in accents:
        h = normalize_hex(raw)
        if h is None:
            return None
        if h in seen:
            continue
        seen.add(h)
        colors.append(h)
        names.append(acc_name)
    if not colors:
        return None
    return Theme(
        source=source,
        id=id_,
        name=name,
        author=author,
        url=url,
        colors=(bg_h, fg_h, *colors),
        accent_names=tuple(names),
        has_roles=True,
    )


def _text(v: object) -> str:
    return v.strip() if isinstance(v, str) else ""


# --- base16 / base24 (tinted-theming) ------------------------------------------------------------


def _tinted_entry(system: str, stem: str, raw: bytes) -> Theme | None:
    try:
        doc = yaml.safe_load(raw)
    except (yaml.YAMLError, ValueError, RecursionError):
        return None
    if not isinstance(doc, dict):
        return None
    palette = doc.get("palette")
    if not isinstance(palette, dict):
        return None
    keys = _BASE16_ACCENTS + (_BASE24_EXTRA if system == "base24" else ())
    return _roles_theme(
        source="base16",
        id_=f"{system}/{stem}",
        name=_text(doc.get("name")) or stem,
        author=_text(doc.get("author")),
        url=_TINTED_URL.format(system=system, file=f"{stem}.yaml"),
        bg=palette.get("base00"),
        fg=palette.get("base05"),
        accents=((k, palette.get(k)) for k in keys),
    )


def parse_tinted(data: bytes) -> Parsed:
    """Archiwum ``.tar.gz`` schemes, czytane w pamięci; tylko ``<root>/base16|base24/*.yaml``."""
    name = SOURCES["base16"]
    themes: list[Theme] = []
    skipped = 0
    try:
        with tarfile.open(fileobj=BytesIO(data), mode="r:gz") as tar:
            for member in tar:
                if not member.isfile():
                    continue
                parts = member.name.split("/")
                if len(parts) != 3 or parts[1] not in ("base16", "base24"):
                    continue  # inne katalogi (tinted8, .github, …) ignorujemy bez liczenia
                root, system, file = parts
                if not root or not file.endswith(".yaml") or file == ".yaml":
                    continue
                f = tar.extractfile(member)
                if f is None or member.size > _MAX_YAML_BYTES:
                    skipped += 1
                    continue
                theme = _tinted_entry(system, file[: -len(".yaml")], f.read())
                if theme is None:
                    skipped += 1
                else:
                    themes.append(theme)
    except (tarfile.TarError, OSError, EOFError, ValueError) as e:
        raise ThemeError(f"{name}: nieczytelne archiwum motywów ({e}).") from e
    return Parsed(tuple(themes), skipped)


# --- Gogh i Windows Terminal ---------------------------------------------------------------------


def _json_list(data: bytes, source: SourceId) -> list[Any]:
    name = SOURCES[source]
    try:
        doc = json.loads(data)
    except (ValueError, RecursionError) as e:
        raise ThemeError(f"{name}: odpowiedź nie jest poprawnym JSON-em.") from e
    if not isinstance(doc, list):
        raise ThemeError(f"{name}: oczekiwano listy motywów.")
    return doc


def _gogh_entry(e: dict[str, Any]) -> Theme | None:
    name = _text(e.get("name"))
    if not name:
        return None
    return _roles_theme(
        source="gogh",
        id_=name,
        name=name,
        author=_text(e.get("author_name")) or _text(e.get("author")),
        url=GOGH_URL,
        bg=e.get("background"),
        fg=e.get("foreground"),
        accents=zip(ANSI_ACCENT_NAMES, (e.get(k) for k in _GOGH_KEYS), strict=True),
    )


def _wt_author(e: dict[str, Any]) -> str:
    meta = e.get("meta")
    credits = meta.get("credits") if isinstance(meta, dict) else None
    first = credits[0] if isinstance(credits, list) and credits else None
    return _text(first.get("name")) if isinstance(first, dict) else ""


def _wt_entry(e: dict[str, Any]) -> Theme | None:
    name = _text(e.get("name"))
    if not name:
        return None
    return _roles_theme(
        source="wt",
        id_=name,
        name=name,
        author=_wt_author(e),
        url=WT_URL,
        bg=e.get("background"),
        fg=e.get("foreground"),
        accents=zip(ANSI_ACCENT_NAMES, (e.get(k) for k in _WT_KEYS), strict=True),
    )


def _parse_entries(entries: list[Any], build: Callable[[dict[str, Any]], Theme | None]) -> Parsed:
    themes: list[Theme] = []
    skipped = 0
    for e in entries:
        t = build(e) if isinstance(e, dict) else None
        if t is None:
            skipped += 1
        else:
            themes.append(t)
    return Parsed(tuple(themes), skipped)


def parse_gogh(data: bytes) -> Parsed:
    return _parse_entries(_json_list(data, "gogh"), _gogh_entry)


def parse_wt(data: bytes) -> Parsed:
    return _parse_entries(_json_list(data, "wt"), _wt_entry)


# --- Lospec --------------------------------------------------------------------------------------


def _lospec_entry(e: dict[str, Any]) -> Theme | None:
    slug, title = _text(e.get("slug")), _text(e.get("title"))
    raw = e.get("colors")
    if not slug or not title or not isinstance(raw, list):
        return None
    if not _LOSPEC_MIN <= len(raw) <= _LOSPEC_MAX:
        return None
    colors = [normalize_hex(c) for c in raw]
    if any(c is None for c in colors):
        return None
    user = e.get("user")
    return Theme(
        source="lospec",
        id=slug,
        name=title,
        author=_text(user.get("name")) if isinstance(user, dict) else "",
        url=_LOSPEC_URL + quote(slug, safe=""),
        colors=tuple(c for c in colors if c is not None),
        accent_names=(),
        has_roles=False,
    )


def parse_lospec(data: bytes) -> tuple[Parsed, int]:
    """Jedna strona Lospec: ``(palety, totalCount)``; ``totalCount`` zlicza wszystkie strony."""
    name = SOURCES["lospec"]
    try:
        doc = json.loads(data)
    except (ValueError, RecursionError) as e:
        raise ThemeError(f"{name}: odpowiedź nie jest poprawnym JSON-em.") from e
    if not isinstance(doc, dict) or not isinstance(doc.get("palettes"), list):
        raise ThemeError(f"{name}: oczekiwano obiektu z listą „palettes”.")
    total = doc.get("totalCount")
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise ThemeError(f"{name}: brak liczby palet („totalCount”).")
    return _parse_entries(doc["palettes"], _lospec_entry), total
