"""Temat pomocy i stałe grup (osobny moduł, żeby moduły treści nie importowały pakietu w kółko)."""

from __future__ import annotations

from dataclasses import dataclass

GROUPS: tuple[str, ...] = (
    "Ogólne",
    "Okno i menu",
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
    Linki między tematami: ``[tekst](help:klucz)``."""

    title: str
    short: str
    body: str
    group: str
