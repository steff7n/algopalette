"""Regresje z przeglądu całości 2026-11-18 (bez GUI); GUI: `tests/gui/test_review_2026_11_18.py`."""

import pytest

from algopalette import presets, sources
from algopalette.globals_logic import change_delta_e
from algopalette.model import OKLCH, default_session

SRC = [
    OKLCH(0.2, 0.02, 260.0),
    OKLCH(0.9, 0.01, 260.0),
    OKLCH(0.7, 0.12, 30.0),
    OKLCH(0.7, 0.12, 150.0),
    OKLCH(0.7, 0.12, 260.0),
]


@pytest.fixture(autouse=True)
def _cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))


def _distances(s):
    return {sl.rules.min_distance.value for sl in s.slots[2:] if sl.rules.min_distance}


# C1
@pytest.mark.parametrize("method", ["2000", "itp", "hyab", "cam16"])
def test_preset_and_polarity_keep_distance_in_session_method(method):
    s = change_delta_e(default_session(), method)
    want = _distances(s)
    assert want and min(want) > 0.09  # 0.08 ok przeliczone na skalę metody
    assert _distances(presets.apply_preset(s, "neutralny")) == want
    assert not presets.is_modified(presets.apply_preset(s, "neutralny"))
    assert _distances(presets.change_polarity(s, "light", reapply=True)) == want


def test_user_preset_converts_between_methods():
    s = change_delta_e(default_session(), "2000")
    presets.save_user_preset("mój", s)
    ok = presets.apply_preset(default_session(), "mój")
    assert sorted(_distances(ok)) == pytest.approx([0.08])
    assert not presets.is_modified(ok)


def test_round_trip_through_methods_is_not_a_modification():
    s = presets.apply_preset(default_session(), "stonowany")
    s = change_delta_e(change_delta_e(s, "2000"), "hyab")
    assert not presets.is_modified(s)


@pytest.mark.parametrize("method", ["2000", "itp"])
def test_source_modes_use_session_method(method):
    s = change_delta_e(default_session(), method)
    want = _distances(s)
    char = sources.apply_character(s, sources.extract_profile(SRC))
    assert _distances(char) == want
    moved = sources.apply_transfer(s, SRC, polarity="light")
    assert _distances(moved) == want
