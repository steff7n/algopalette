"""Jakość presetów wbudowanych na prawdziwym silniku (spec §8): każdy preset, dla każdej
obsługiwanej polaryzacji i obu metryk, przy 10 i przy 7 kolorach, z domyślnymi ustawieniami
generowania daje co najmniej 5 z 6 propozycji bez twardych naruszeń.

Wolne (kilkaset generowań) — uruchamiać w tle: ``uv run pytest -q tests/test_presets_quality.py
-m slow``. Dopóki silnik nie generuje, testy są pomijane.
"""

from dataclasses import replace

import pytest

from algopalette import _engine, engine
from algopalette.model import ContrastMetric, Polarity, Session, default_session, remove_slot
from algopalette.presets import apply_preset
from algopalette.presets_builtin import BUILTIN, PresetDef

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        "generate" not in _engine.build_info()["implemented"], reason="silnik nie generuje"
    ),
]

METRICS: tuple[ContrastMetric, ...] = ("wcag21", "apca")
SIZES = (10, 7)
CASES = [
    pytest.param(p, pol, metric, size, id=f"{p.name}|{pol}|{metric}|{size}")
    for p in BUILTIN
    for pol in p.polarities
    for metric in METRICS
    for size in SIZES
]


def preset_session(p: PresetDef, polarity: Polarity, metric: ContrastMetric, size: int) -> Session:
    s = default_session()
    s = replace(s, globals=replace(s.globals, polarity=polarity, contrast_metric=metric))
    while len(s.slots) > size:
        s = remove_slot(s, s.slots[-1].id)
    return apply_preset(s, p.name, polarity=polarity)


def hard_summary(proposals: list[engine.Proposal]) -> list[str]:
    out = []
    for i, prop in enumerate(proposals):
        hard = [f"{v.kind}:{v.amount:.3g}" for v in prop.violations if v.hard]
        if hard or prop.timed_out:
            out.append(f"#{i + 1} {'⏱ ' if prop.timed_out else ''}{', '.join(hard)}")
    return out


@pytest.mark.parametrize(("p", "polarity", "metric", "size"), CASES)
def test_preset_gives_five_of_six_without_hard_violations(p, polarity, metric, size):
    s = preset_session(p, polarity, metric, size)
    assert s.globals.optimizer == default_session().globals.optimizer  # ustawienia domyślne
    proposals = engine.generate(s)
    assert len(proposals) == 6
    ok = sum(1 for prop in proposals if prop.ok)
    assert ok >= 5, hard_summary(proposals)
