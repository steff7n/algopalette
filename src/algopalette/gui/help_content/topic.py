"""Temat pomocy i stałe grup (osobny moduł, żeby moduły treści nie importowały pakietu w kółko)."""

from __future__ import annotations

from dataclasses import dataclass

GROUPS: tuple[str, ...] = (
    "Ogólne",
    "Okno i menu",
    "Zasady",
    "Zasady koloru",
    "Paleta",
    "Warunki i zależności",
    "Globalne",
    "Propozycje",
    "Źródło",
    "Analiza",
    "Pojęcia",
)


@dataclass(frozen=True)
class Topic:
    """``short`` trafia do podpowiedzi (1–2 zdania), ``body`` (Markdown) do panelu Pomocy.
    Linki między tematami: ``[tekst](help:klucz)``; rysunki: ``![opis](figure:nazwa)``
    (``gui/help_figures.py``).

    ``term=True`` oznacza temat pisany według wzorca terminu: ``body`` ma trzy części z
    pogrubionymi nagłówkami „Co to jest”, „Przykład” (z liczbami) i „Kiedy użyć”."""

    title: str
    short: str
    body: str
    group: str
    term: bool = False
