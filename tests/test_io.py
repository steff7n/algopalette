"""Testy zapisu/odczytu sesji algopalette.v1 i ścieżek XDG."""

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from algopalette.io import (
    SessionFormatError,
    autosave_path,
    config_dir,
    default_palettes_dir,
    load_session,
    save_session,
    session_from_dict,
    session_to_dict,
)
from algopalette.model import (
    OKLCH,
    ChromaRange,
    Cond,
    ContrastBound,
    CvdSettings,
    FrozenMap,
    HueRange,
    HueScheme,
    HueTarget,
    Interval,
    OptimizerSettings,
    Relation,
    SlotConditions,
    default_session,
    snapshot_key,
    with_slot,
)


def full_session():
    s = default_session()
    cond = SlotConditions(
        hue_range=Cond(HueRange(330.0, 20.0), hard=False, weight=2.5),
        hue_target=Cond(HueTarget(200.0, 12.5), enabled=False),
        chroma=Cond(ChromaRange("rel", 0.3, None)),
        lightness=Cond(Interval(None, 0.8)),
        contrast_bg=Cond(ContrastBound("apca", 60.0, 90.0)),
        min_distance=Cond(0.1, hard=False, weight=0.5),
        cvd_min_distance=Cond(0.05),
        extreme=Cond("weakest"),
    )
    a, b, c, d = s.slots[2:6]
    rels = (
        Relation("hue", b.id, "eq", 180.0, tol=15.0),
        Relation("lightness", b.id, "le", -0.1),
        Relation("chroma", b.id, "ge", 0.8, chroma_op="mul", chroma_mode="rel"),
        Relation("contrast", b.id, "ge", 4.5, metric="wcag21", hard=False, weight=3.0),
        Relation("distance", c.id, "le", 0.08, metric="2000", enabled=False),
        Relation("mix", b.id, "eq", 0.0, tol=0.02, other=c.id, t=0.3),
        Relation("hue", "duch", "eq", 10.0),  # zerwana relacja też przechodzi roundtrip
    )
    s = with_slot(s, replace(a, name="komentarz", locked=True, conditions=cond, relations=rels))
    s = with_slot(s, replace(d, value=OKLCH(0.61234567891234, 0.31, 359.99999)))
    rd = dict(s.globals.role_defaults)
    g = replace(
        s.globals,
        polarity="light",
        role_defaults=rd,
        hue_scheme=HueScheme("custom", 10.0, 20.0, 30.0, (1.0, 2.5, 300.0), 5.0, 2.0, True, 0.7),
        lightness_spread=Cond(Interval(0.1, None), hard=False),
        contrast_metric="apca",
        delta_e="cam16",
        cvd=CvdSettings(frozenset({"protan", "tritan"}), "brettel", 0.6),
        fit_method="raytrace",
        avoid_colors=(OKLCH(0.5, 0.1, 30.0), OKLCH(0.7, 0.2, 200.0)),
        avoid_distance=0.07,
        optimizer=OptimizerSettings(3, 42, 1234, 2.5, 0.1, 500.0),
    )
    snap = {
        snapshot_key("accent", "lightness"): rd["accent"].lightness,
        snapshot_key("bg", "chroma"): Cond(ChromaRange("abs", 0.0, 0.02)),
        "hue_scheme": HueScheme("triad", custom=(1.0, 2.0)),
        "cvd": CvdSettings(frozenset({"deutan"})),
        "number": 3,
        "name": "x",
        "none": None,
        "nested": FrozenMap({"a": (1, 2.5)}),
    }
    return replace(s, globals=g, mood="neon", mood_snapshot=snap)


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
    assert d["format"] == "algopalette.v1"
    assert all("hex" in sl and sl["hex"].startswith("#") for sl in d["slots"])


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
        (["slots", 2, "conditions", "hue_range"], 7),
        (["slots", 2, "conditions", "hue_range", "value", "lo"], "x"),
        (["slots", 2, "conditions", "chroma", "value", "mode"], "huh"),
        (["slots", 2, "conditions", "extreme", "value"], "middle"),
        (["slots", 2, "conditions", "min_distance", "weight"], None),
        (["globals", "polarity"], "gray"),
        (["globals", "contrast_metric"], "wcag3"),
        (["globals", "cvd", "types"], ["alpha"]),
        (["globals", "cvd", "types"], "protan"),
        (["globals", "role_defaults", "bg"], DELETE),
        (["globals", "hue_scheme", "custom"], ["a"]),
        (["globals", "optimizer", "seed"], 1.5),
        (["globals", "optimizer", "n_proposals"], 0),
        (["globals", "optimizer", "max_evals"], True),
        (["globals"], DELETE),
        (["mood"], 5),
        (["mood_snapshot"], [1]),
        (["mood_snapshot", "x"], {"$type": "Nieznany", "fields": {}}),
        (["mood_snapshot", "x"], {"bez": "znacznika"}),
        (["mood_snapshot", "x"], [1, 2]),
        (["mood_snapshot", "x"], {"$type": "Interval", "fields": {"zly": 1}}),
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
    p.write_text(p.read_text("utf-8").replace('"severity": 1.0', '"severity": Infinity'), "utf-8")
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
