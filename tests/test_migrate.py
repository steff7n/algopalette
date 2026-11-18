"""Migracja plików ``algopalette.v1`` do ``algopalette.v2``: wierna i nigdy cicha."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from algopalette.io import SessionFormatError, load_session_ex, session_from_dict
from algopalette.migrate import migrate_v1
from algopalette.model import Band, ChromaBand, ContrastBound, HueArc, Rule

REFERENCE = Path(__file__).parent / "fixtures" / "v1_reference"
V1_FIELDS = (
    "hue_range",
    "hue_target",
    "chroma",
    "lightness",
    "contrast_bg",
    "min_distance",
    "cvd_min_distance",
    "extreme",
)
V2_FIELDS = (
    "lightness",
    "chroma",
    "hue",
    "contrast_bg",
    "min_distance",
    "extreme",
)


def cond(value: Any, enabled: bool = True, hard: bool = True, weight: float = 1.0) -> dict:
    return {"value": value, "enabled": enabled, "hard": hard, "weight": weight}


def conditions(**fields: Any) -> dict:
    return {**dict.fromkeys(V1_FIELDS), **fields}


def v1_session(accents: int = 3, **role_accent: Any) -> dict:
    """Minimalna poprawna sesja v1: role bez warunków poza podanymi dla roli „accent”."""
    slots = [
        {
            "id": f"s{i}",
            "name": "",
            "locked": False,
            "value": {"l": 0.2 if i == 0 else 0.8, "c": 0.05, "h": 40.0 * i},
            "hex": "#000000",
            "conditions": conditions(),
            "relations": [],
        }
        for i in range(accents + 2)
    ]
    return {
        "format": "algopalette.v1",
        "mood": None,
        "mood_snapshot": None,
        "globals": {
            "polarity": "dark",
            "role_defaults": {
                "bg": conditions(),
                "fg": conditions(),
                "accent": conditions(**role_accent),
            },
            "hue_scheme": {
                "kind": "equal",
                "rotation": 0.0,
                "center": 0.0,
                "spread": 90.0,
                "custom": [],
                "tol": 15.0,
                "jitter": 0.0,
                "hard": False,
                "weight": 1.0,
            },
            "lightness_spread": None,
            "contrast_metric": "wcag21",
            "delta_e": "ok",
            "cvd": {"types": [], "method": "machado", "severity": 1.0},
            "fit_method": "oklch-chroma",
            "avoid_colors": [],
            "avoid_distance": 0.0,
            "optimizer": {
                "n_proposals": 6,
                "seed": 0,
                "max_evals": 8000,
                "time_cap_s": 30.0,
                "min_diversity": 0.05,
                "hard_weight": 1000.0,
            },
        },
        "slots": slots,
        "view_model": "oklch",
    }


def migrated(data: dict) -> tuple[Any, list[str]]:
    out, notes = migrate_v1(copy.deepcopy(data))
    return session_from_dict(json.loads(json.dumps(out))), notes


HUE_RANGE = {"lo": 0.0, "hi": 90.0}
HUE_TARGET = {"target": 60.0, "tol": 20.0}


def test_result_is_v2_document():
    out, notes = migrate_v1(v1_session())
    assert notes == []
    assert out["format"] == "algopalette.v2"
    assert out["preset"] is None
    assert "mood" not in out
    assert "mood_snapshot" not in out
    assert "role_defaults" not in out["globals"]
    opt = out["globals"]["optimizer"]
    assert "max_evals" not in opt
    assert opt["threads"] == 0
    for slot in out["slots"]:
        assert tuple(slot["rules"]) == V2_FIELDS
        assert "conditions" not in slot
        assert slot["use_scheme"] is True


def test_migration_does_not_modify_input():
    data = v1_session(lightness=cond({"lo": 0.6, "hi": 0.85}))
    before = copy.deepcopy(data)
    migrate_v1(data)
    assert data == before


def test_null_field_takes_role_condition():
    data = v1_session(
        lightness=cond({"lo": 0.6, "hi": 0.85}, hard=False, weight=2.0),
        chroma=cond({"mode": "rel", "lo": 0.3, "hi": None}),
        contrast_bg=cond({"metric": None, "lo": 4.5, "hi": None}),
        min_distance=cond(0.08, hard=False),
        cvd_min_distance=cond(0.04, enabled=False),  # daltonizm usunięty — pole przepada
        extreme=cond("weakest"),
    )
    s, notes = migrated(data)
    assert notes == []
    for slot in s.slots[2:]:
        assert slot.rules.lightness == Rule(Band(0.6, 0.85), hard=False, weight=2.0)
        assert slot.rules.chroma == Rule(ChromaBand("rel", 0.3, None))
        assert slot.rules.contrast_bg == Rule(ContrastBound(None, 4.5, None))
        assert slot.rules.min_distance == Rule(0.08, hard=False)
        assert slot.rules.extreme == Rule("weakest")
    assert s.slots[0].rules.lightness is None
    assert s.slots[1].rules.lightness is None


def test_own_field_wins_over_role():
    data = v1_session(lightness=cond({"lo": 0.6, "hi": 0.85}))
    data["slots"][3]["conditions"]["lightness"] = cond({"lo": 0.1, "hi": None}, enabled=False)
    s, notes = migrated(data)
    assert notes == []
    assert s.slots[2].rules.lightness == Rule(Band(0.6, 0.85))
    assert s.slots[3].rules.lightness == Rule(Band(0.1, None), enabled=False)


def test_hue_range_only():
    data = v1_session()
    data["slots"][2]["conditions"]["hue_range"] = cond(
        {"lo": 330.0, "hi": 20.0}, hard=False, weight=2.0
    )
    s, notes = migrated(data)
    assert notes == []
    assert s.slots[2].rules.hue == Rule(HueArc(330.0, 20.0), hard=False, weight=2.0)


def test_hue_target_only_becomes_arc():
    data = v1_session()
    data["slots"][2]["conditions"]["hue_target"] = cond({"target": 30.0, "tol": 15.0})
    data["slots"][3]["conditions"]["hue_target"] = cond({"target": 350.0, "tol": 20.0}, hard=False)
    data["slots"][4]["conditions"]["hue_target"] = cond({"target": 100.0, "tol": 200.0})
    s, notes = migrated(data)
    assert notes == []
    assert s.slots[2].rules.hue == Rule(HueArc(15.0, 45.0))
    assert s.slots[3].rules.hue == Rule(HueArc(330.0, 10.0), hard=False)
    assert s.slots[4].rules.hue == Rule(HueArc(0.0, 360.0))  # tolerancja ≥ 180° = pełne koło


def test_both_only_target_enabled():
    data = v1_session()
    c = data["slots"][2]["conditions"]
    c["hue_range"] = cond(HUE_RANGE, enabled=False)
    c["hue_target"] = cond(HUE_TARGET, hard=False, weight=0.5)
    s, notes = migrated(data)
    assert s.slots[2].rules.hue == Rule(HueArc(40.0, 80.0), hard=False, weight=0.5)
    assert len(notes) == 1
    assert "akcent 1" in notes[0]


def test_both_only_range_enabled():
    data = v1_session()
    c = data["slots"][3]["conditions"]
    c["hue_range"] = cond(HUE_RANGE, weight=2.0)
    c["hue_target"] = cond(HUE_TARGET, enabled=False)
    s, notes = migrated(data)
    assert s.slots[3].rules.hue == Rule(HueArc(0.0, 90.0), weight=2.0)
    assert len(notes) == 1
    assert "akcent 2" in notes[0]


def test_both_disabled_keeps_range():
    data = v1_session()
    c = data["slots"][2]["conditions"]
    c["hue_range"] = cond(HUE_RANGE, enabled=False, hard=False)
    c["hue_target"] = cond(HUE_TARGET, enabled=False)
    s, notes = migrated(data)
    assert s.slots[2].rules.hue == Rule(HueArc(0.0, 90.0), enabled=False, hard=False)
    assert len(notes) == 1
    assert "akcent 1" in notes[0]


def test_both_enabled_single_intersection_strictest_wins():
    data = v1_session()
    c = data["slots"][4]["conditions"]
    c["hue_range"] = cond(HUE_RANGE, hard=False, weight=1.0)
    c["hue_target"] = cond(HUE_TARGET, hard=True, weight=2.0)
    s, notes = migrated(data)
    assert s.slots[4].rules.hue == Rule(HueArc(40.0, 80.0), hard=True, weight=2.0)
    assert notes == ["akcent 3: zakres i cel odcienia scalono do 40–80°, zasada jest teraz twarda"]


def test_both_enabled_disjoint_keeps_range():
    data = v1_session()
    c = data["slots"][2]["conditions"]
    c["hue_range"] = cond({"lo": 0.0, "hi": 60.0}, hard=False, weight=0.5)
    c["hue_target"] = cond({"target": 200.0, "tol": 10.0})
    s, notes = migrated(data)
    assert s.slots[2].rules.hue == Rule(HueArc(0.0, 60.0), hard=False, weight=0.5)
    assert len(notes) == 1
    assert "akcent 1" in notes[0]


def test_both_enabled_two_arcs_keeps_range():
    data = v1_session()
    c = data["slots"][2]["conditions"]
    c["hue_range"] = cond({"lo": 300.0, "hi": 60.0})
    c["hue_target"] = cond({"target": 180.0, "tol": 150.0}, hard=False)
    s, notes = migrated(data)
    assert s.slots[2].rules.hue == Rule(HueArc(300.0, 60.0))
    assert len(notes) == 1
    assert "akcent 1" in notes[0]


def test_hue_conditions_from_role_and_slot_are_merged_per_color():
    data = v1_session(hue_range=cond(HUE_RANGE, hard=False))
    data["slots"][2]["conditions"]["hue_target"] = cond(HUE_TARGET, weight=2.0)
    data["slots"][3]["name"] = "komentarz"
    s, notes = migrated(data)
    assert s.slots[2].rules.hue == Rule(HueArc(40.0, 80.0), weight=2.0)
    assert s.slots[3].rules.hue == Rule(HueArc(0.0, 90.0), hard=False)
    assert len(notes) == 1  # tylko kolor, w którym coś scalono
    assert "akcent 1" in notes[0]


def test_message_uses_slot_name():
    data = v1_session()
    data["slots"][2]["name"] = "słowa kluczowe"
    c = data["slots"][2]["conditions"]
    c["hue_range"] = cond(HUE_RANGE)
    c["hue_target"] = cond(HUE_TARGET)
    _, notes = migrated(data)
    assert notes == ["słowa kluczowe: zakres i cel odcienia scalono do 40–80°"]


def test_use_scheme_false_when_any_hue_condition_existed():
    data = v1_session(accents=4)
    data["slots"][2]["conditions"]["hue_range"] = cond(HUE_RANGE, enabled=False)
    data["slots"][3]["conditions"]["hue_target"] = cond(HUE_TARGET)
    s, _ = migrated(data)
    assert [sl.use_scheme for sl in s.slots[2:]] == [False, False, True, True]

    role = v1_session(hue_target=cond(HUE_TARGET, enabled=False))
    s, _ = migrated(role)
    assert all(not sl.use_scheme for sl in s.slots[2:])
    assert all(sl.use_scheme for sl in s.slots[:2])


@pytest.mark.parametrize(
    ("mood", "preset", "noted"),
    [
        ("chłodny mglisty", "chłodny mglisty", False),
        ("neutralny", "neutralny", False),
        ("jesienny", "jesienny", False),
        ("mój własny", None, True),
        (None, None, False),
    ],
)
def test_mood_becomes_preset(mood, preset, noted):
    data = v1_session()
    data["mood"] = mood
    data["mood_snapshot"] = {"cokolwiek": 1}
    s, notes = migrated(data)
    assert s.preset == preset
    assert bool(notes) is noted
    if noted:
        assert "mój własny" in notes[0]


@pytest.mark.parametrize(
    ("max_evals", "budget", "noted"),
    [(30000, 3000, False), (8000, 800, False), (100, 300, True), (5_000_000, 100_000, True)],
)
def test_budget_conversion(max_evals, budget, noted):
    data = v1_session()
    data["globals"]["optimizer"]["max_evals"] = max_evals
    s, notes = migrated(data)
    assert s.globals.optimizer.budget == budget
    assert s.globals.optimizer.threads == 0
    assert bool(notes) is noted


def test_unusual_content_is_preserved():
    data = v1_session()
    rel = {
        "kind": "hue",
        "target": "duch",
        "op": "eq",
        "value": 180.0,
        "tol": 15.0,
        "chroma_op": "add",
        "chroma_mode": "abs",
        "metric": None,
        "other": None,
        "t": 0.5,
        "enabled": True,
        "hard": True,
        "weight": 1.0,
    }
    data["slots"][2]["relations"] = [rel]
    data["slots"][2]["value"]["h"] = -30.0
    data["slots"][2]["locked"] = True
    del data["view_model"]
    data["globals"]["lightness_spread"] = cond({"lo": None, "hi": 0.12}, hard=False)
    s, notes = migrated(data)
    assert notes == []
    assert s.slots[2].relations[0].target == "duch"
    assert s.slots[2].value.h == 330.0
    assert s.slots[2].locked
    assert s.view_model == "oklch"
    spread = s.globals.lightness_spread
    assert spread is not None
    assert (spread.value.lo, spread.value.hi, spread.hard) == (None, 0.12, False)


def test_rule_not_applicable_to_role_is_dropped_loudly():
    data = v1_session()
    data["globals"]["role_defaults"]["bg"]["contrast_bg"] = cond(
        {"metric": None, "lo": 4.5, "hi": None}
    )
    data["slots"][1]["conditions"]["min_distance"] = cond(0.1)
    s, notes = migrated(data)
    assert s.slots[0].rules.contrast_bg is None
    assert s.slots[1].rules.min_distance is None
    assert len(notes) == 2
    assert "tło" in notes[0]
    assert "tekst" in notes[1]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.pop("globals"),
        lambda d: d.pop("slots"),
        lambda d: d.update(slots="nie lista"),
        lambda d: d["slots"][2].pop("conditions"),
        lambda d: d["slots"][2]["conditions"].update(hue_target=cond({"target": "x", "tol": 1})),
        lambda d: d["slots"][2]["conditions"].update(hue_range=7),
        lambda d: d["globals"].pop("role_defaults"),
        lambda d: d["globals"]["role_defaults"].pop("accent"),
        lambda d: d["globals"]["optimizer"].update(max_evals="dużo"),
        lambda d: d["globals"].update(optimizer=None),
    ],
)
def test_malformed_v1_raises_format_error(mutation):
    data = v1_session()
    mutation(data)
    with pytest.raises(SessionFormatError) as exc:
        out, _ = migrate_v1(data)
        session_from_dict(out)
    assert exc.type is SessionFormatError


def _reference(name: str) -> list[dict]:
    return json.loads((REFERENCE / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["eval.json", "quality.json"])
def test_reference_sessions_migrate_silently(name):
    cases = _reference(name)
    assert len(cases) == (300 if name == "eval.json" else 36)
    for n, case in enumerate(cases):
        out, notes = migrate_v1(case["session"])
        assert notes == [], f"{name}[{n}]: {notes}"
        s = session_from_dict(json.loads(json.dumps(out)))
        assert len(s.slots) == len(case["session"]["slots"])
        if name == "quality.json":
            assert s.preset == case["mood"]
            assert s.globals.optimizer.budget == 3000


def test_load_session_ex_reads_v1_and_reports(tmp_path):
    data = v1_session()
    c = data["slots"][2]["conditions"]
    c["hue_range"] = cond(HUE_RANGE)
    c["hue_target"] = cond(HUE_TARGET)
    p = tmp_path / "stara.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    s, notes = load_session_ex(p)
    assert s.slots[2].rules.hue == Rule(HueArc(40.0, 80.0))
    assert isinstance(notes, tuple)
    assert len(notes) == 1
