"""Nastroje (Task 5)."""

import statistics
from dataclasses import replace

import pytest

from algopalette.color import max_chroma
from algopalette.engine import generate
from algopalette.model import default_session, effective_conditions
from algopalette.moods import BUILTIN, apply_mood, delete_user_mood, list_moods, save_user_mood

NAMES = [
    "neutralny",
    "chłodny mglisty",
    "neon",
    "ziemisty",
    "pastel",
    "nocny wysoki kontrast",
    "monochromatyczny z jednym akcentem",
    "retro terminal",
    "jesienny",
]


@pytest.fixture(autouse=True)
def _cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))


def test_builtin_names():
    assert list(BUILTIN) == NAMES
    assert [m.name for m in list_moods()] == NAMES


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("polarity", ["dark", "light"])
def test_apply_every_mood(name, polarity):
    s = default_session()
    s = replace(s, globals=replace(s.globals, polarity=polarity))
    m = apply_mood(s, name)
    assert m.mood == name
    assert m.slots == s.slots
    assert m.mood_snapshot is not None
    _, src = effective_conditions(m, m.slots[2].id)
    assert set(src.values()) == {"mood"}


def test_user_change_turns_source_global():
    m = apply_mood(default_session(), "pastel")
    rd = dict(m.globals.role_defaults)
    rd["accent"] = replace(rd["accent"], lightness=None)
    m2 = replace(m, globals=replace(m.globals, role_defaults=rd))
    _, src = effective_conditions(m2, m2.slots[2].id)
    assert src["lightness"] == "global"
    assert src["chroma"] == "mood"


def _medians(name: str) -> tuple[float, float]:
    s = apply_mood(default_session(), name)
    s = replace(
        s, globals=replace(s.globals, optimizer=replace(s.globals.optimizer, n_proposals=1))
    )
    p = generate(s)[0]
    acc = [p.values[sl.id] for sl in s.slots[2:]]
    rel = [c.c / max(max_chroma(c.l, c.h), 1e-9) for c in acc]
    return statistics.median(rel), statistics.median(c.l for c in acc)


def test_moods_match_names():
    neon_c, _ = _medians("neon")
    pastel_c, pastel_l = _medians("pastel")
    _, night_l = _medians("nocny wysoki kontrast")
    assert neon_c > pastel_c
    assert pastel_l > night_l


def test_user_moods_roundtrip():
    s = apply_mood(default_session(), "neon")
    save_user_mood("mój neon", s, "test")
    names = [m.name for m in list_moods()]
    assert names[-1] == "mój neon"
    back = apply_mood(default_session(), "mój neon")
    assert back.globals.role_defaults == s.globals.role_defaults
    assert back.globals.hue_scheme == s.globals.hue_scheme
    delete_user_mood("mój neon")
    assert "mój neon" not in [m.name for m in list_moods()]


def test_builtin_name_rejected():
    with pytest.raises(ValueError, match="wbudowany"):
        save_user_mood("neon", default_session())
    with pytest.raises(ValueError, match="wbudowany"):
        delete_user_mood("pastel")


def test_unknown_mood():
    with pytest.raises(ValueError, match="Nie ma nastroju"):
        apply_mood(default_session(), "nieistniejący")


def test_corrupt_moods_file(tmp_path):
    p = tmp_path / "cfg" / "algopalette"
    p.mkdir(parents=True)
    (p / "moods.json").write_text("{nie json", encoding="utf-8")
    with pytest.raises(ValueError, match="nastrojów"):
        list_moods()


@pytest.mark.parametrize("name", NAMES)
def test_mooded_session_roundtrip(tmp_path, name):
    from algopalette.io import load_session, save_session

    s = apply_mood(default_session(), name)
    save_session(s, tmp_path / "s.json")
    back = load_session(tmp_path / "s.json")
    assert back == s
    _, src = effective_conditions(back, back.slots[2].id)
    assert set(src.values()) == {"mood"}


def test_user_mood_restores_polarity_and_metric():
    from algopalette.globals_logic import change_polarity_or_metric

    s = default_session()
    s = replace(s, globals=replace(s.globals, contrast_metric="apca"))
    s = apply_mood(s, "neutralny")
    save_user_mood("apca-mood", s)
    w = apply_mood(default_session(), "apca-mood")  # sesja WCAG
    assert w.globals.contrast_metric == "apca"
    acc = w.globals.role_defaults["accent"].contrast_bg
    assert acc is not None and acc.value.lo == 60.0
    # zmiana polaryzacji przy nastroju użytkownika: domyślne zakresy, nastrój zdjęty
    light = change_polarity_or_metric(w, polarity="light")
    assert light.mood is None
    bg_l = light.globals.role_defaults["bg"].lightness
    assert bg_l is not None and bg_l.value.lo is not None and bg_l.value.lo > 0.9


def test_corrupt_mood_entry(tmp_path):
    p = tmp_path / "cfg" / "algopalette"
    p.mkdir(parents=True)
    (p / "moods.json").write_text('{"moods": {"x": "oops"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="zły format"):
        list_moods()
