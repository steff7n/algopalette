"""Regresje z przeglądu 2026-11-18 (bez GUI); GUI: `tests/gui/test_gui_regressions_*.py`."""

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


# M4
def test_gui_measurements_match_engine_report():
    from dataclasses import replace

    from algopalette import engine
    from algopalette.model import Rule, with_slot

    s = default_session()
    a, b = s.slots[2], s.slots[3]
    far = Rule(0.5, hard=False)
    s = with_slot(
        s, replace(a, value=OKLCH(0.62, 0.37, 300.0), rules=replace(a.rules, min_distance=far))
    )
    s = with_slot(
        s, replace(b, value=OKLCH(0.62, 0.37, 320.0), rules=replace(b.rules, min_distance=far))
    )
    v = next(
        v
        for v in engine.current_violations(s)
        if v.kind == "pair_distance" and set(v.slot_ids) == {a.id, b.id}
    )
    fit = s.globals.fit_method
    pa, pb = (engine.measured(s.slots[k].value, fit) for k in (2, 3))
    assert engine.pair_delta_e(pa, pb, s) == pytest.approx(v.achieved)


# M14
def test_starting_with_a_file_twice_keeps_both_previous_autosaves(tmp_path, monkeypatch):
    from algopalette import io as aio
    from algopalette.__main__ import startup_session

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    f = tmp_path / "s.json"
    aio.save_session(default_session(), f)
    auto = aio.autosave_path()
    for n in range(2):
        aio.save_session(
            change_delta_e(default_session(), "2000" if n else "hyab"), auto, overwrite=True
        )
        startup_session(f, fresh=False)
    kept = sorted(auto.parent.glob(f"{auto.stem}.prev-*.json"))
    assert len(kept) == 2
    assert {aio.load_session(p).globals.delta_e for p in kept} == {"hyab", "2000"}


# M16
def test_huge_integer_in_file_is_a_format_error(tmp_path):
    import json

    from algopalette import io as aio

    p = tmp_path / "s.json"
    aio.save_session(default_session(), p)
    doc = json.loads(p.read_text("utf-8"))
    doc["slots"][2]["value"]["l"] = 10**400
    p.write_text(json.dumps(doc), "utf-8")
    with pytest.raises(aio.SessionFormatError, match="zbyt duża"):
        aio.load_session(p)


# M17
def test_save_through_symlink_keeps_the_link(tmp_path):
    from algopalette import io as aio
    from algopalette.pb_export import write_pb_file

    real = tmp_path / "real.json"
    link = tmp_path / "link.json"
    aio.save_session(default_session(), real)
    link.symlink_to(real)
    aio.save_session(change_delta_e(default_session(), "2000"), link, overwrite=True)
    assert link.is_symlink()
    assert aio.load_session(real).globals.delta_e == "2000"
    pb_real, pb_link = tmp_path / "pb.json", tmp_path / "pb-link.json"
    pb_real.write_text("{}", "utf-8")
    pb_real.chmod(0o600)
    pb_link.symlink_to(pb_real)
    write_pb_file('{"a": 1}', pb_link, overwrite=True)
    assert pb_link.is_symlink() and pb_real.read_text("utf-8") == '{"a": 1}'
    assert pb_real.stat().st_mode & 0o777 == 0o600
