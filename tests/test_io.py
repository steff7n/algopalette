"""Testy zapisu/odczytu sesji algopalette.v2, wczytywania v1 i ścieżek XDG."""

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from algopalette.io import (
    FORMAT,
    SessionFormatError,
    autosave_path,
    config_dir,
    default_palettes_dir,
    load_session,
    load_session_ex,
    save_session,
    session_from_dict,
    session_to_dict,
)
from algopalette.model import (
    OKLCH,
    RULE_FIELDS,
    Band,
    ChromaBand,
    ContrastBound,
    HueArc,
    HueScheme,
    Interval,
    OptimizerSettings,
    Relation,
    Rule,
    SlotRules,
    default_session,
    with_slot,
)


def full_session():
    s = default_session()
    rules = SlotRules(
        lightness=Rule(Band(None, 0.8, exclude=((0.70, 0.74),))),
        chroma=Rule(ChromaBand("rel", 0.3, None, exclude=((0.5, 0.6), (0.8, 0.9)))),
        hue=Rule(
            HueArc(330.0, 270.0, exclude=((350.0, 10.0), (60.0, 85.0))), hard=False, weight=2.5
        ),
        contrast_bg=Rule(ContrastBound("apca", 60.0, 90.0)),
        min_distance=Rule(0.1, hard=False, weight=0.5),
        extreme=Rule("weakest"),
    )
    a, b, c, d = s.slots[2:6]
    rels = (
        Relation("hue", b.id, "eq", 180.0, tol=15.0),
        Relation("lightness", b.id, "le", -0.1),
        Relation("chroma", b.id, "ge", 0.8, chroma_op="mul", chroma_mode="rel"),
        Relation("contrast", b.id, "ge", 4.5, metric="wcag21", hard=False, weight=3.0),
        Relation("distance", c.id, "le", 0.08, metric="2000", enabled=False),
        Relation("mix", b.id, "eq", 0.0, tol=0.02, other=c.id, t=0.3),
        Relation("hue", "duch", "eq", 10.0),  # zerwana zależność też przechodzi roundtrip
    )
    s = with_slot(
        s,
        replace(a, name="komentarz", locked=True, rules=rules, use_scheme=False, relations=rels),
    )
    s = with_slot(s, replace(b, rules=SlotRules(hue=Rule(HueArc(0.0, 360.0)))))
    s = with_slot(s, replace(d, value=OKLCH(0.61234567891234, 0.31, 359.99999)))
    g = replace(
        s.globals,
        polarity="light",
        hue_scheme=HueScheme("custom", 10.0, 20.0, 30.0, (1.0, 2.5, 300.0), 5.0, 2.0, True, 0.7),
        lightness_spread=Rule(Interval(0.1, None), hard=False),
        contrast_metric="apca",
        delta_e="cam16",
        fit_method="raytrace",
        avoid_colors=(OKLCH(0.5, 0.1, 30.0), OKLCH(0.7, 0.2, 200.0)),
        avoid_distance=0.07,
        optimizer=OptimizerSettings(3, 42, 1234, 2.5, 0.1, 500.0, 4),
    )
    return replace(s, globals=g, preset="neon")


def test_roundtrip(tmp_path):
    s = full_session()
    p = tmp_path / "a" / "b" / "sesja.json"  # katalogi nadrzędne powstają
    save_session(s, p)
    assert load_session(p) == s
    assert load_session(p) == s  # idempotentne
    again = tmp_path / "again.json"
    save_session(load_session(p), again)
    assert json.loads(again.read_text("utf-8")) == json.loads(p.read_text("utf-8"))


def test_roundtrip_default_and_dict():
    s = default_session()
    assert session_from_dict(json.loads(json.dumps(session_to_dict(s)))) == s
    d = session_to_dict(s)
    assert d["format"] == FORMAT == "algopalette.v2"
    assert all("hex" in sl and sl["hex"].startswith("#") for sl in d["slots"])


def test_old_file_with_colorblindness_fields_loads_without_them():
    """Pliki zapisane przed usunięciem daltonizmu (``globals.cvd``, ``cvd_min_distance``)."""
    s = full_session()
    d = session_to_dict(s)
    d["globals"]["cvd"] = {"types": ["protan"], "method": "machado", "severity": 1.0}
    for slot in d["slots"]:
        slot["rules"]["cvd_min_distance"] = None
    d["slots"][2]["rules"]["cvd_min_distance"] = {
        "value": 0.04,
        "enabled": True,
        "hard": False,
        "weight": 1.0,
    }
    assert session_from_dict(d) == s
    again = session_to_dict(session_from_dict(d))
    assert "cvd" not in again["globals"]
    assert all("cvd_min_distance" not in slot["rules"] for slot in again["slots"])


def test_document_shape_matches_contract():
    """Kształt z I1 planu — ten sam dokument czyta silnik w Ruście."""
    d = json.loads(json.dumps(session_to_dict(full_session())))
    assert list(d) == ["format", "preset", "view_model", "globals", "slots"]
    assert set(d["globals"]) == {
        "polarity",
        "contrast_metric",
        "delta_e",
        "fit_method",
        "hue_scheme",
        "lightness_spread",
        "avoid_colors",
        "avoid_distance",
        "optimizer",
    }
    assert d["globals"]["optimizer"] == {
        "n_proposals": 3,
        "seed": 42,
        "budget": 1234,
        "time_cap_s": 2.5,
        "min_diversity": 0.1,
        "hard_weight": 500.0,
        "threads": 4,
    }
    assert d["globals"]["lightness_spread"] == {
        "value": {"lo": 0.1, "hi": None},
        "enabled": True,
        "hard": False,
        "weight": 1.0,
    }
    slot = d["slots"][2]
    assert set(slot) == {"id", "name", "locked", "value", "hex", "use_scheme", "rules", "relations"}
    assert slot["use_scheme"] is False
    assert tuple(slot["rules"]) == RULE_FIELDS
    assert slot["rules"]["lightness"] == {
        "value": {"lo": None, "hi": 0.8, "exclude": [[0.70, 0.74]]},
        "enabled": True,
        "hard": True,
        "weight": 1.0,
    }
    assert slot["rules"]["chroma"]["value"] == {
        "mode": "rel",
        "lo": 0.3,
        "hi": None,
        "exclude": [[0.5, 0.6], [0.8, 0.9]],
    }
    assert slot["rules"]["hue"]["value"] == {
        "lo": 330.0,
        "hi": 270.0,
        "exclude": [[350.0, 10.0], [60.0, 85.0]],
    }
    assert slot["rules"]["contrast_bg"]["value"] == {"metric": "apca", "lo": 60.0, "hi": 90.0}
    assert slot["rules"]["min_distance"]["value"] == 0.1
    assert slot["rules"]["extreme"]["value"] == "weakest"
    assert set(slot["relations"][0]) == {
        "kind",
        "target",
        "op",
        "value",
        "tol",
        "chroma_op",
        "chroma_mode",
        "metric",
        "other",
        "t",
        "enabled",
        "hard",
        "weight",
    }
    assert all(v is None for v in d["slots"][0]["rules"].values() if v is None)
    assert d["slots"][0]["rules"]["contrast_bg"] is None


def test_roundtrip_hash_preserved():
    s = full_session()
    s2 = session_from_dict(json.loads(json.dumps(session_to_dict(s))))
    assert hash(s2) == hash(s)


def test_bad_format(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"format": "palettebuilder.v3", "palette": []}), "utf-8")
    with pytest.raises(SessionFormatError, match="format"):
        load_session(p)


def test_truncated_json(tmp_path):
    p = tmp_path / "x.json"
    save_session(default_session(), p)
    p.write_text(p.read_text("utf-8")[:200], "utf-8")
    with pytest.raises(SessionFormatError):
        load_session(p)


@pytest.mark.parametrize("payload", [b"\xff\xfe\x00", b"", b"[]", b"42", b"null", b"NaN", b"{"])
def test_garbage_files(tmp_path, payload):
    p = tmp_path / "x.json"
    p.write_bytes(payload)
    with pytest.raises(SessionFormatError):
        load_session(p)


def test_deeply_nested_json(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("[" * 100000, "utf-8")
    with pytest.raises(SessionFormatError):
        load_session(p)


def test_missing_file_is_not_format_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_session(tmp_path / "brak.json")


def mutate(path, value):
    """Zwraca słownik sesji, w którym pod ścieżką (lista kluczy/indeksów) jest ``value``."""
    d = json.loads(json.dumps(session_to_dict(full_session())))
    cur = d
    for key in path[:-1]:
        cur = cur[key]
    if value is DELETE:
        del cur[path[-1]]
    else:
        cur[path[-1]] = value
    return d


DELETE = object()


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (["slots"], DELETE),
        (["slots"], "nie lista"),
        (["slots"], []),
        (["slots", 0, "id"], 5),
        (["slots", 0, "value", "l"], "0.5"),
        (["slots", 0, "value", "l"], True),
        (["slots", 0, "value", "c"], -0.1),
        (["slots", 0, "value"], DELETE),
        (["slots", 2, "relations", 0, "kind"], "teleport"),
        (["slots", 2, "relations", 0, "value"], None),
        (["slots", 2, "relations", 0, "enabled"], "tak"),
        (["slots", 2, "rules", "hue"], 7),
        (["slots", 2, "rules", "hue", "value", "lo"], "x"),
        (["slots", 2, "rules", "hue", "value", "hi"], 400.0),
        (["slots", 2, "rules", "hue", "value", "exclude"], [[10.0, 370.0]]),
        (["slots", 2, "rules", "hue", "value", "exclude"], [[10.0]]),
        (["slots", 2, "rules", "hue", "value", "exclude"], "x"),
        (["slots", 2, "rules", "hue", "value", "exclude"], DELETE),
        (["slots", 2, "rules", "chroma", "value", "mode"], "huh"),
        (["slots", 2, "rules", "chroma", "value", "exclude"], [[0.6, 0.5]]),
        (["slots", 2, "rules", "lightness", "value", "exclude"], [[0.74, 0.70]]),
        (["slots", 2, "rules", "lightness", "value", "exclude"], [[0.7, 0.7]]),
        (["slots", 2, "rules", "lightness", "value", "exclude"], [[0.7, "0.8"]]),
        (["slots", 2, "rules", "extreme", "value"], "middle"),
        (["slots", 2, "rules", "min_distance", "weight"], None),
        (["slots", 2, "rules", "min_distance", "weight"], -1.0),
        (["slots", 2, "rules", "extreme"], DELETE),
        (["slots", 2, "rules"], DELETE),
        (["slots", 2, "use_scheme"], "tak"),
        (["slots", 2, "use_scheme"], DELETE),
        (
            ["slots", 0, "rules", "contrast_bg"],
            {
                "value": {"metric": None, "lo": 4.5, "hi": None},
                "enabled": True,
                "hard": True,
                "weight": 1.0,
            },
        ),
        (
            ["slots", 1, "rules", "extreme"],
            {"value": "weakest", "enabled": True, "hard": True, "weight": 1.0},
        ),
        (["globals", "polarity"], "gray"),
        (["globals", "contrast_metric"], "wcag3"),
        (["globals", "hue_scheme", "custom"], ["a"]),
        (["globals", "lightness_spread"], 3),
        (["globals", "optimizer", "seed"], 1.5),
        (["globals", "optimizer", "n_proposals"], 0),
        (["globals", "optimizer", "budget"], True),
        (["globals", "optimizer", "budget"], 0),
        (["globals", "optimizer", "threads"], -1),
        (["globals", "optimizer", "threads"], DELETE),
        (["globals"], DELETE),
        (["preset"], 5),
        (["preset"], DELETE),
    ],
)
def test_bad_fields_raise_session_format_error(path, value):
    with pytest.raises(SessionFormatError) as exc:
        session_from_dict(mutate(path, value))
    assert exc.type is SessionFormatError
    assert str(exc.value)


def test_duplicate_slot_ids_rejected():
    d = session_to_dict(default_session())
    d["slots"][3]["id"] = d["slots"][2]["id"]
    with pytest.raises(SessionFormatError, match="id"):
        session_from_dict(d)


def test_too_many_slots_rejected():
    d = session_to_dict(default_session())
    for i in range(7):
        extra = json.loads(json.dumps(d["slots"][2]))
        extra["id"] = f"x{i}"
        d["slots"].append(extra)
    with pytest.raises(SessionFormatError):
        session_from_dict(d)


def test_error_message_is_polish_and_names_field():
    with pytest.raises(SessionFormatError) as exc:
        session_from_dict(mutate(["slots", 0, "value", "l"], "0.5"))
    msg = str(exc.value)
    assert "slots[0].value.l" in msg
    assert "liczb" in msg


def test_non_finite_numbers_rejected(tmp_path):
    p = tmp_path / "x.json"
    save_session(default_session(), p)
    text = p.read_text("utf-8")
    assert '"time_cap_s": 30.0' in text
    p.write_text(text.replace('"time_cap_s": 30.0', '"time_cap_s": Infinity'), "utf-8")
    with pytest.raises(SessionFormatError):
        load_session(p)


def test_no_overwrite(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("stare", "utf-8")
    with pytest.raises(FileExistsError):
        save_session(default_session(), p)
    assert p.read_text("utf-8") == "stare"
    save_session(default_session(), p, overwrite=True)
    assert load_session(p) == load_session(p)
    assert p.read_text("utf-8") != "stare"
    assert list(tmp_path.iterdir()) == [p]  # brak resztek pliku tymczasowego


def test_failed_write_leaves_original_and_no_temp(tmp_path, monkeypatch):
    p = tmp_path / "x.json"
    p.write_text("stare", "utf-8")

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        save_session(default_session(), p, overwrite=True)
    assert p.read_text("utf-8") == "stare"
    assert list(tmp_path.iterdir()) == [p]


def test_save_preserves_existing_mode_and_default_readable(tmp_path):
    p = tmp_path / "x.json"
    save_session(default_session(), p)
    assert p.stat().st_mode & 0o777 == 0o644
    p.chmod(0o600)
    save_session(default_session(), p, overwrite=True)
    assert p.stat().st_mode & 0o777 == 0o600


def test_xdg_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert default_palettes_dir() == tmp_path / "data" / "algopalette" / "palettes"
    assert autosave_path() == tmp_path / "state" / "algopalette" / "last.json"
    assert config_dir() == tmp_path / "cfg" / "algopalette"


def test_xdg_fallbacks(monkeypatch, tmp_path):
    for var in ("XDG_DATA_HOME", "XDG_STATE_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", "wzgledna/sciezka")  # względne = ignorowane (spec XDG)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_palettes_dir() == Path(tmp_path, ".local/share/algopalette/palettes")
    assert autosave_path() == Path(tmp_path, ".local/state/algopalette/last.json")
    assert config_dir() == Path(tmp_path, ".config/algopalette")


def _mutate(tmp_path, fn):
    import json

    from algopalette.io import load_session, save_session
    from algopalette.model import default_session

    p = tmp_path / "s.json"
    save_session(default_session(), p)
    d = json.loads(p.read_text())
    fn(d)
    p.write_text(json.dumps(d))
    return lambda: load_session(p)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["slots"][2]["value"].update(l=-0.5),
        lambda d: d["globals"]["optimizer"].update(seed=-3),
        lambda d: d["slots"][2]["value"].update(l=1.5),
        lambda d: d["slots"][2]["relations"].append(
            {
                "kind": "contrast",
                "target": d["slots"][3]["id"],
                "op": "ge",
                "value": 1,
                "tol": 0,
                "chroma_op": "add",
                "chroma_mode": "abs",
                "metric": "ok",
                "other": None,
                "t": 0.5,
                "enabled": True,
                "hard": True,
                "weight": 1,
            }
        ),
    ],
)
def test_rejects_out_of_range_values(tmp_path, mutation):
    from algopalette.io import SessionFormatError

    load = _mutate(tmp_path, mutation)
    with pytest.raises(SessionFormatError):
        load()


def test_view_model_roundtrip_and_default(tmp_path):
    from algopalette.io import load_session, save_session
    from algopalette.model import default_session

    s = replace(default_session(), view_model="hsl")
    p = tmp_path / "s.json"
    save_session(s, p)
    assert load_session(p).view_model == "hsl"
    d = json.loads(p.read_text())
    del d["view_model"]
    p.write_text(json.dumps(d))
    assert load_session(p).view_model == "oklch"  # starsze pliki


def test_v1_document_is_not_accepted_by_strict_decoder():
    d = session_to_dict(default_session())
    d["format"] = "algopalette.v1"
    with pytest.raises(SessionFormatError, match="format"):
        session_from_dict(d)


def test_load_session_ex_v2_has_no_messages(tmp_path):
    p = tmp_path / "s.json"
    s = full_session()
    save_session(s, p)
    assert load_session_ex(p) == (s, ())


def test_hue_full_circle_and_wrapping_exclusion_roundtrip():
    s = default_session()
    arc = HueArc(0.0, 360.0, exclude=((350.0, 10.0),))
    s = with_slot(s, replace(s.slots[2], rules=replace(s.slots[2].rules, hue=Rule(arc))))
    s2 = session_from_dict(json.loads(json.dumps(session_to_dict(s))))
    assert s2 == s
    rule = s2.slots[2].rules.hue
    assert rule is not None
    assert rule.value.exclude == ((350.0, 10.0),)


def test_save_refuses_session_that_could_not_be_loaded(tmp_path):
    """Przegląd 2026-11-18 C3: zapis nie może tworzyć pliku, którego „Wczytaj” nie otworzy."""
    s = default_session()
    bad = replace(s, globals=replace(s.globals, avoid_colors=(OKLCH(70.0, 0.1, 30.0),)))
    p = tmp_path / "x.json"
    save_session(s, p)
    before = p.read_text("utf-8")
    with pytest.raises(SessionFormatError, match="avoid_colors"):
        save_session(bad, p, overwrite=True)
    assert p.read_text("utf-8") == before
    assert list(tmp_path.iterdir()) == [p]
