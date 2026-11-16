"""Motyw z sieci: znormalizowany zapis (``Theme``), kolory z rolami (``Palette``), filtr listy.

``Theme`` trzyma hexy, żeby katalog dało się zapisać w pamięci podręcznej bez zależności od sesji.
Role kolorów palet bez ról (Lospec) przydziela dopiero ``resolve`` — zależą od metryki kontrastu
sesji i od wyboru „tło jasne” (spec §6).
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast, get_args

from algopalette import color as col
from algopalette.model import MAX_ACCENTS, OKLCH, ContrastMetric

SourceId = Literal["base16", "gogh", "wt", "lospec"]
BgFilter = Literal["any", "dark", "light"]

SOURCES: dict[SourceId, str] = {
    "base16": "base16 / base24",
    "gogh": "Gogh",
    "wt": "Windows Terminal",
    "lospec": "Lospec",
}
FULL_CATALOG_SOURCES: tuple[SourceId, ...] = ("base16", "gogh", "wt")
_SOURCE_ORDER = {s: i for i, s in enumerate(SOURCES)}
TOO_FEW = "Za mało różnych kolorów: motyw musi mieć tło, tekst i co najmniej 1 akcent."


class ThemeError(ValueError):
    """Motyw albo katalog, którego nie da się użyć; komunikat po polsku dla użytkownika."""


@dataclass(frozen=True)
class Theme:
    source: SourceId
    id: str  # unikalny w źródle
    name: str
    author: str  # "" gdy brak
    url: str | None
    colors: tuple[str, ...]  # "#rrggbb"; has_roles → (tło, tekst, *akcenty)
    accent_names: tuple[str, ...]  # has_roles → len(colors) - 2; inaczej ()
    has_roles: bool
    license: str | None = None


@dataclass(frozen=True)
class Palette:
    bg: OKLCH
    fg: OKLCH
    accents: tuple[OKLCH, ...]
    accent_names: tuple[str, ...]


def theme_to_dict(t: Theme) -> dict[str, Any]:
    return {
        "source": t.source,
        "id": t.id,
        "name": t.name,
        "author": t.author,
        "url": t.url,
        "colors": list(t.colors),
        "accent_names": list(t.accent_names),
        "has_roles": t.has_roles,
        "license": t.license,
    }


def _str_list(v: Any, key: str) -> tuple[str, ...]:
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ValueError(f"pole {key}: oczekiwano listy napisów")
    return tuple(v)


def _opt_str(d: Mapping[str, Any], key: str) -> str | None:
    v = d.get(key)
    if v is not None and not isinstance(v, str):
        raise ValueError(f"pole {key}: oczekiwano napisu")
    return v


def theme_from_dict(d: Mapping[str, Any]) -> Theme:
    """Odwrotność ``theme_to_dict``; ``ValueError`` przy złym kształcie."""
    if not isinstance(d, Mapping):
        raise ValueError("motyw: oczekiwano obiektu")
    source = d.get("source")
    if source not in get_args(SourceId):
        raise ValueError(f"nieznane źródło: {source!r}")
    for key in ("id", "name", "author"):
        if not isinstance(d.get(key), str):
            raise ValueError(f"pole {key}: oczekiwano napisu")
    has_roles = d.get("has_roles")
    if not isinstance(has_roles, bool):
        raise ValueError("pole has_roles: oczekiwano wartości logicznej")
    return Theme(
        source=cast(SourceId, source),
        id=d["id"],
        name=d["name"],
        author=d["author"],
        url=_opt_str(d, "url"),
        colors=_str_list(d.get("colors"), "colors"),
        accent_names=_str_list(d.get("accent_names"), "accent_names"),
        has_roles=has_roles,
        license=_opt_str(d, "license"),
    )


def _oklch(hex_: str) -> OKLCH:
    try:
        return col.from_css(hex_)
    except ValueError:
        raise ThemeError(f"Nieczytelny kolor „{hex_}”.") from None


def _check_count(n: int) -> None:
    if n < 1:
        raise ThemeError(
            "Za mało różnych kolorów: motyw musi mieć tło, tekst i co najmniej 1 akcent."
        )
    if n > MAX_ACCENTS:
        raise ThemeError(f"Za dużo kolorów: najwyżej {MAX_ACCENTS} akcentów (motyw ma {n}).")


def resolve(t: Theme, *, light_bg: bool = False, metric: ContrastMetric = "wcag21") -> Palette:
    """Kolory z rolami. Bez ról: tło skrajne (ciemne/jasne), tekst najbardziej kontrastowy."""
    if t.has_roles:
        if len(t.colors) < 2:
            raise ThemeError("Motyw nie ma tła i tekstu.")
        bg, fg, *accents = (_oklch(h) for h in t.colors)
        _check_count(len(accents))
        names = t.accent_names if len(t.accent_names) == len(accents) else ("",) * len(accents)
        return Palette(bg, fg, tuple(accents), tuple(names))
    uniq = list(dict.fromkeys(h.lower() for h in t.colors))
    if len(uniq) < 2:
        raise ThemeError(
            "Za mało różnych kolorów: motyw musi mieć tło, tekst i co najmniej 1 akcent."
        )
    cols = [_oklch(h) for h in uniq]
    pick = max if light_bg else min
    bi = pick(range(len(cols)), key=lambda i: cols[i].l)
    rest = [i for i in range(len(cols)) if i != bi]
    fi = max(rest, key=lambda i: col.contrast(cols[i], cols[bi], metric))
    accents = tuple(cols[i] for i in rest if i != fi)
    _check_count(len(accents))
    return Palette(cols[bi], cols[fi], accents, ("",) * len(accents))


def is_dark(t: Theme) -> bool | None:
    """Ciemny = L OKLCH tła < 0,5 (jedyne źródło prawdy); ``None`` dla palet bez ról."""
    if not t.has_roles or not t.colors:
        return None
    try:
        return _oklch(t.colors[0]).l < 0.5
    except ThemeError:
        return None


def fold(text: str) -> str:
    """Do porównań: bez wielkości liter i diakrytyków (także „ł”)."""
    s = unicodedata.normalize("NFKD", text.casefold().replace("ł", "l"))
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def filter_themes(themes: Sequence[Theme], query: str, bg: BgFilter) -> list[Theme]:
    """Podciąg nazwy lub autora + filtr tła; palety bez ról przechodzą każdy filtr tła."""
    q = fold(query.strip())
    out: list[Theme] = []
    for t in themes:
        if q and q not in fold(t.name) and q not in fold(t.author):
            continue
        if bg != "any":
            dark = is_dark(t)
            if dark is not None and dark != (bg == "dark"):
                continue
        out.append(t)
    out.sort(key=lambda t: (_SOURCE_ORDER[t.source], fold(t.name)))
    return out
