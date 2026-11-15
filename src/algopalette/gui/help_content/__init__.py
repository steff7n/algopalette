"""Treść pomocy: jeden moduł na obszar interfejsu, scalone w ``TOPICS`` (klucz → ``Topic``)."""

from __future__ import annotations

from algopalette.gui.help_content import (
    analysis,
    concepts,
    conditions,
    general,
    globals,
    palette,
    proposals,
    rules,
    source,
    window,
)
from algopalette.gui.help_content.topic import GROUPS, Topic

__all__ = ["GROUPS", "TOPICS", "Topic"]


def _merge() -> dict[str, Topic]:
    out: dict[str, Topic] = {}
    for mod in (
        general,
        window,
        rules,
        palette,
        conditions,
        globals,
        proposals,
        source,
        analysis,
        concepts,
    ):
        for key, topic in mod.TOPICS.items():
            if key in out:
                raise ValueError(f"powtórzony klucz pomocy: {key}")
            out[key] = topic
    return out


TOPICS: dict[str, Topic] = _merge()
