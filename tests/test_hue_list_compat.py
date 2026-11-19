"""Układ odcieni jako lista: te same cele co przed zmianą (snapshot) i odczyt dawnych kształtów."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from algopalette import color as col
from algopalette import engine
from algopalette import io as aio
from algopalette.model import HueScheme, Session, default_session, remove_slot
from algopalette.presets import apply_preset, is_modified, save_user_preset
from algopalette.rules_edit import set_rules_lock
from algopalette.sources import character_settings, extract_profile

FIXTURES = Path(__file__).parent / "fixtures"
SNAPSHOT: dict[str, list[float]] = json.loads(
    (FIXTURES / "hue_targets_snapshot.json").read_text(encoding="utf-8")
)


@pytest.fixture(autouse=True)
def _cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))


def sized(n_colors: int) -> Session:
    s = default_session()
    while len(s.slots) > n_colors:
        s = remove_slot(s, s.slots[-1].id)
    return s


def targets(s: Session) -> list[float]:
    t = engine.hue_targets(s)
    return [t[sl.id] for sl in s.slots[2:] if sl.id in t]


def session_for(key: str) -> Session:
    if key == "default":
        return default_session()
    kind, rest = key.split(":", 1)
    if kind == "file":
        return aio.load_session(FIXTURES / "v2_contract" / rest)
    name, pol, n = rest.rsplit(":", 2)
    return apply_preset(sized(int(n)), name, polarity=pol)


@pytest.mark.parametrize("key", sorted(SNAPSHOT))
def test_targets_match_snapshot(key):
    assert targets(session_for(key)) == pytest.approx(SNAPSHOT[key], abs=1e-9)


def old_doc(scheme: dict, accents: int = 8) -> dict:
    doc = aio.session_to_dict(sized(accents + 2))
    doc["globals"]["hue_scheme"] = {
        "kind": "custom",
        "rotation": 0.0,
        "center": 0.0,
        "spread": 90.0,
        "custom": [],
        "tol": 15.0,
        "jitter": 0.0,
        "hard": False,
        "weight": 1.0,
        **scheme,
    }
    return doc


def test_old_v2_file_none_kind_gives_empty_list():
    s = aio.session_from_dict(old_doc({"kind": "none", "custom": [10.0, 20.0]}))
    assert s.globals.hue_scheme.hues == ()
    assert engine.hue_targets(s) == {}


def test_old_v2_triad_8_accents():
    s = aio.session_from_dict(old_doc({"kind": "triad", "rotation": 45.0, "tol": 9.0}))
    h = s.globals.hue_scheme
    assert h.hues == pytest.approx((45, 165, 285, 85, 205, 325, 125, 245))
    assert h.tol == 9.0


def test_save_has_no_kind():
    s = aio.session_from_dict(old_doc({"kind": "equal", "rotation": 10.0}))
    hs = aio.session_to_dict(s)["globals"]["hue_scheme"]
    assert "kind" not in hs and "custom" not in hs
    assert hs["hues"] == pytest.approx([10, 55, 100, 145, 190, 235, 280, 325])


def test_too_long_hue_list_rejected():
    doc = aio.session_to_dict(default_session())
    doc["globals"]["hue_scheme"]["hues"] = [1.0] * 15
    with pytest.raises(aio.SessionFormatError):
        aio.session_from_dict(doc)


def test_user_preset_old_shape():
    save_user_preset("stary", default_session(), "")
    path = aio.config_dir() / "presets.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["presets"]["stary"]["hue_scheme"] = old_doc({"kind": "equal", "rotation": 10.0})["globals"][
        "hue_scheme"
    ]
    path.write_text(json.dumps(doc), encoding="utf-8")
    out = apply_preset(default_session(), "stary")
    assert out.globals.hue_scheme.hues == pytest.approx((10, 55, 100, 145, 190, 235, 280, 325))
    assert is_modified(out) is False


def test_user_preset_saved_as_list():
    s = default_session()
    s = replace(s, globals=replace(s.globals, hue_scheme=HueScheme(hues=(10.0, 200.0))))
    save_user_preset("lista", s, "")
    saved = json.loads((aio.config_dir() / "presets.json").read_text(encoding="utf-8"))
    assert saved["presets"]["lista"]["hue_scheme"]["hues"] == [10.0, 200.0]
    out = apply_preset(default_session(), "lista")
    assert out.globals.hue_scheme.hues == (10.0, 200.0)


def test_hue_lock_with_empty_list():
    s = default_session()
    s = replace(s, globals=replace(s.globals, hue_scheme=HueScheme()))
    sid = s.slots[3].id
    out = set_rules_lock(s, [sid], "hue", {})
    after = out.slots[3]
    assert after.rules_lock == "hue"
    assert after.rules == s.slots[3].rules and after.use_scheme == s.slots[3].use_scheme


DRACULA = ("#282a36", "#f8f8f2", "#ff5555", "#50fa7b", "#f1fa8c", "#bd93f9", "#ff79c6", "#8be9fd")


def test_character_hues_in_accent_order():
    colors = [col.from_css(h) for h in DRACULA]
    cs = character_settings(default_session(), extract_profile(colors))
    assert cs.globals.hue_scheme.hues[:3] == pytest.approx((24.4, 148.0, 112.8), abs=1.0)
