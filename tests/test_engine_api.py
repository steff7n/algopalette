"""Kontrakt z silnikiem natywnym: schemat v2, nakładka ``engine``, teksty naruszeń."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from algopalette import _engine, color, engine, forms
from algopalette import io as aio
from algopalette.engine import Proposal, Violation
from algopalette.migrate import migrate_v1
from algopalette.model import OKLCH, Relation, default_session, with_slot

FIXTURES = Path(__file__).parent / "fixtures"
CONTRACT = FIXTURES / "v2_contract"
IMPLEMENTED = _engine.build_info()["implemented"]


def _reference_documents() -> dict[str, str]:
    """40 sesji wzorcowych v1 po migracji, zakodowanych tak, jak koduje je program."""
    cases = json.loads((FIXTURES / "v1_reference" / "eval.json").read_text(encoding="utf-8"))
    out = {}
    for n in range(0, 280, 7):
        session = aio.session_from_dict(migrate_v1(cases[n]["session"])[0])
        doc = aio.session_to_dict(session)
        out[f"eval_{n:03d}.json"] = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    return out


def test_contract_files_are_what_python_encodes():
    """Pliki kontraktu czyta też test Rusta — muszą być dokładnie tym, co koduje Python."""
    docs = _reference_documents()
    assert len(docs) == 40
    CONTRACT.mkdir(parents=True, exist_ok=True)
    for name, text in docs.items():
        path = CONTRACT / name
        if not path.exists():
            path.write_text(text, encoding="utf-8")
        assert path.read_text(encoding="utf-8") == text, name


def test_build_info():
    info = _engine.build_info()
    assert info["profile"] == "release"
    assert "schema" in info["implemented"]
    assert isinstance(info["version"], str) and info["version"]


def test_validate_accepts_every_contract_file():
    files = sorted(CONTRACT.glob("*.json"))
    assert len(files) >= 43  # 40 z danych wzorcowych + ręczne
    assert any(f.name.startswith("manual_") for f in files)
    for path in files:
        _engine.validate(path.read_text(encoding="utf-8"))


def test_validate_accepts_default_and_engine_json():
    s = default_session()
    _engine.validate(json.dumps(aio.session_to_dict(s)))
    _engine.validate(engine.to_engine_json(s, ()))


def test_validate_rejects_unknown_field_with_path():
    doc = aio.session_to_dict(default_session())
    doc["slots"][2]["rules"]["hue"] = {
        "value": {"lo": 0.0, "hi": 270.0, "exclude": [], "foo": 1},
        "enabled": True,
        "hard": True,
        "weight": 1.0,
    }
    with pytest.raises(ValueError, match=r"slots\[2\]\.rules\.hue\.value\.foo"):
        _engine.validate(json.dumps(doc))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["slots"][2]["value"].update(l=1.5),
        lambda d: d["globals"]["optimizer"].update(budget=0),
        lambda d: d["slots"][3].update(id=d["slots"][2]["id"]),
        lambda d: d.update(slots=d["slots"][:2]),
        lambda d: d["slots"][2]["rules"]["lightness"]["value"].update(exclude=[[0.8, 0.7]]),
    ],
)
def test_validate_rejects_what_python_rejects(mutation):
    doc = aio.session_to_dict(default_session())
    mutation(doc)
    with pytest.raises(aio.SessionFormatError):
        aio.session_from_dict(doc)
    with pytest.raises(ValueError):
        _engine.validate(json.dumps(doc))


# --- nakładka --------------------------------------------------------------------------------


def test_to_engine_json_fits_fixed_colors_only():
    s = default_session()
    wild = OKLCH(0.75, 0.40, 150.0)  # poza gamutem
    a, b = s.slots[2], s.slots[3]
    s = with_slot(s, replace(a, value=wild))
    s = with_slot(s, replace(b, value=wild))
    doc = json.loads(engine.to_engine_json(s, free=[a.id]))
    assert doc["format"] == "algopalette.v2"
    free_value, fixed_value = doc["slots"][2]["value"], doc["slots"][3]["value"]
    assert free_value == {"l": 0.75, "c": 0.40, "h": 150.0}  # wolny: jak w sesji
    fitted = color.fitted(wild, s.globals.fit_method)
    assert fixed_value == {"l": fitted.l, "c": fitted.c, "h": fitted.h}
    assert fixed_value["c"] < 0.40
    assert doc["slots"][0]["value"] == {"l": 0.18, "c": 0.02, "h": 260.0}  # w gamucie: bez zmian


def test_slot_label():
    s = default_session()
    assert [engine.slot_label(s, i) for i in range(4)] == ["tło", "tekst", "akcent 1", "akcent 2"]
    s = with_slot(s, replace(s.slots[3], name="słowa kluczowe"))
    assert engine.slot_label(s, 3) == "słowa kluczowe"


def _proposal(s, values):
    return Proposal(values, {}, {}, 0.0, (), False, 0, tuple(values))


def test_apply_proposal_skips_locks_and_unknown_ids():
    s = default_session()
    a, b, c = s.slots[2:5]
    s = with_slot(s, replace(b, locked=True))
    new = OKLCH(0.5, 0.1, 10.0)
    p = _proposal(s, {a.id: new, b.id: new, c.id: new, "nie-ma": new})
    out = engine.apply_proposal(s, p)
    assert out.slots[2].value == new
    assert out.slots[3].value == b.value  # kłódka
    assert out.slots[4].value == new
    assert len(out.slots) == len(s.slots)
    only = engine.apply_proposal(s, p, slot_ids=[c.id])
    assert only.slots[2].value == a.value
    assert only.slots[4].value == new


def test_proposal_ok():
    hard = Violation("k", ("a",), "lightness", True, 0.1, 0.5, {"lo": 0.6, "hi": None}, {})
    soft = replace(hard, hard=False)
    base = Proposal({}, {}, {}, 0.0, (), False, 0)
    assert base.ok
    assert replace(base, violations=(soft,)).ok
    assert not replace(base, violations=(hard,)).ok
    assert not replace(base, timed_out=True).ok


@pytest.mark.skipif("generate" in IMPLEMENTED, reason="silnik już generuje naprawdę")
def test_generation_on_stub_is_done_and_empty():
    gen = engine.start(default_session())
    state = gen.poll()
    assert (state.state, state.error) == ("done", None)
    assert gen.result() == []
    assert engine.generate(default_session()) == []


@pytest.mark.skipif("evaluate" in IMPLEMENTED, reason="silnik już ocenia naprawdę")
def test_evaluation_on_stub_is_empty():
    s = default_session()
    assert engine.current_violations(s) == []
    assert engine.objective(s) == 0.0
    assert engine.hue_targets(s) == {}


# --- teksty naruszeń -------------------------------------------------------------------------


def _session():
    s = default_session()
    return with_slot(s, replace(s.slots[4], name="słowa"))


def _v(kind, slots, achieved, req, meta=None, key="k", hard=True, amount=0.1):
    return Violation(key, tuple(slots), kind, hard, amount, achieved, req, meta or {})


def test_violation_text_for_every_kind():
    s = _session()
    bg, fg, a1, a2, a3 = (sl.id for sl in s.slots[:5])
    text = forms.violation_text
    cases = [
        (
            _v("lightness", [a1], 0.58, {"lo": 0.6, "hi": 0.85}),
            ("jasność (akcent 1)", "0.600–0.850", "0.580"),
        ),
        (
            _v("lightness", [bg], 0.3, {"lo": None, "hi": 0.25}),
            ("jasność (tło)", "≤ 0.250", "0.300"),
        ),
        (
            _v("chroma", [a3], 0.31, {"lo": 0.5, "hi": None}, {"mode": "rel"}),
            ("nasycenie (słowa)", "≥ 0.500 względne", "0.310"),
        ),
        (
            _v("chroma", [fg], 0.05, {"lo": 0.0, "hi": 0.04}, {"mode": "abs"}),
            ("nasycenie (tekst)", "0.000–0.040", "0.050"),
        ),
        (
            _v("hue", [a1], 301.26, {"lo": 0.0, "hi": 270.0}),
            ("odcień (akcent 1)", "0°–270°", "301.3°"),
        ),
        (
            _v("exclude", [a2], 70.0, {"lo": 60.0, "hi": 85.0}, {"channel": "hue"}),
            ("zakazany przedział: odcień (akcent 2)", "poza 60°–85°", "70.0°"),
        ),
        (
            _v("exclude", [a2], 0.72, {"lo": 0.70, "hi": 0.74}, {"channel": "lightness"}),
            ("zakazany przedział: jasność (akcent 2)", "poza 0.700–0.740", "0.720"),
        ),
        (
            _v("exclude", [a2], 0.55, {"lo": 0.5, "hi": 0.6}, {"channel": "chroma", "mode": "rel"}),
            ("zakazany przedział: nasycenie (akcent 2)", "poza 0.500–0.600 względne", "0.550"),
        ),
        (
            _v("contrast_bg", [a1, bg], 3.917, {"lo": 4.5, "hi": None}, {"metric": "wcag21"}),
            ("kontrast z tłem", "≥ 4.50", "3.92"),
        ),
        (
            _v("contrast_bg", [fg, bg], 70.04, {"lo": 75.0, "hi": 90.0}, {"metric": "apca"}),
            ("kontrast z tłem", "75.0–90.0 Lc", "70.0 Lc"),
        ),
        (
            _v(
                "extreme",
                [a1, a2, a3],
                6.0,
                {"bound": 5.5},
                {"which": "weakest", "metric": "wcag21"},
            ),
            ("najsłabszy kontrast (akcent 1)", "< 5.50", "6.00"),
        ),
        (
            _v(
                "extreme", [a1, a2], 55.0, {"bound": 61.2}, {"which": "strongest", "metric": "apca"}
            ),
            ("najmocniejszy kontrast (akcent 1)", "> 61.2 Lc", "55.0 Lc"),
        ),
        (
            _v("pair_distance", [a1, a3], 0.0512, {"min": 0.08}, {"method": "ok"}),
            ("odległość akcent 1 – słowa", "ΔE ≥ 0.080", "0.051"),
        ),
        (
            _v("spread", [a1, a2, a3], 0.2, {"lo": None, "hi": 0.12}),
            ("rozrzut jasności akcentów", "≤ 0.120", "0.200"),
        ),
        (
            _v("scheme", [a2], 100.0, {"target": 70.0, "tol": 15.0}),
            ("układ odcieni (akcent 2)", "70° ± 15°", "100.0°"),
        ),
        (
            _v("avoid", [a1], 0.02, {"min": 0.05}),
            ("unikany kolor (akcent 1)", "ΔE ≥ 0.050", "0.020"),
        ),
        (_v("gamut", [a1], 0.25, {"hi": 0.2065}), ("gamut sRGB (akcent 1)", "C ≤ 0.206", "0.250")),
        (
            _v("diversity", [a1, a2], 0.03, {"min": 0.05}, hard=False),
            ("różnorodność", "średnie ΔE ≥ 0.050", "0.030"),
        ),
    ]
    for violation, expected in cases:
        assert text(violation, s) == expected, violation.kind


def test_violation_text_for_relations():
    s = _session()
    _bg, _fg, a1, a2, a3 = (sl.id for sl in s.slots[:5])
    text = forms.violation_text

    def rel(rel_kind, achieved, op, value, tol=0.0, slots=(a1, a2), **meta):
        base = {"rel_kind": rel_kind, "chroma_op": "add", "chroma_mode": "abs", "metric": None}
        req = {"op": op, "value": value, "tol": tol}
        return _v("rel", slots, achieved, req, {**base, **meta})

    head = "zależność: {} względem akcent 2 (akcent 1)"
    assert text(rel("hue", 120.0, "eq", 180.0, 15.0), s) == (
        head.format("odcień"),
        "180 ± 15°",
        "120°",
    )
    assert text(rel("hue", 20.0, "ge", 30.0), s) == (head.format("odcień"), "≥ 30°", "20°")
    assert text(rel("lightness", -0.05, "le", -0.1), s) == (
        head.format("jasność"),
        "≤ -0.100",
        "-0.050",
    )
    assert text(rel("chroma", 0.02, "eq", 0.05, 0.01), s) == (
        head.format("nasycenie"),
        "0.050 ± 0.010",
        "0.020",
    )
    assert text(rel("chroma", 0.1, "ge", 0.8, chroma_op="mul"), s) == (
        head.format("nasycenie"),
        "≥ 0.80 × akcent 2",
        "0.100",
    )
    assert text(rel("contrast", 3.0, "ge", 4.5, metric="wcag21"), s) == (
        head.format("kontrast"),
        "≥ 4.50",
        "3.00",
    )
    assert text(rel("contrast", 50.0, "eq", 60.0, 5.0, metric="apca"), s) == (
        head.format("kontrast"),
        "60.0 ± 5.0 Lc",
        "50.0 Lc",
    )
    assert text(rel("distance", 0.05, "ge", 0.08, metric="ok"), s) == (
        head.format("odległość"),
        "≥ 0.080",
        "0.050",
    )
    mix = rel("mix", 0.09, "eq", 0.0, 0.02, slots=(a1, a2, a3))
    assert text(mix, s) == (
        "zależność: mieszanka akcent 2 i słowa (akcent 1)",
        "ΔE od mieszanki ≤ 0.020",
        "0.090",
    )


def test_violation_text_survives_unknown_color_and_kind():
    s = _session()
    gone = _v("lightness", ["usunięty"], 0.5, {"lo": 0.6, "hi": None})
    assert forms.violation_text(gone, s) == ("jasność (?)", "≥ 0.600", "0.500")
    odd = _v("nowy_rodzaj", [s.slots[2].id], 1.5, {}, key="slot:x:nowy")
    assert forms.violation_text(odd, s) == ("slot:x:nowy", "—", "1.5")


def test_real_violations_have_texts():
    """Każde naruszenie zwrócone przez silnik da się opisać (gdy silnik już ocenia)."""
    s = default_session()
    rel = Relation("hue", s.slots[3].id, "eq", 180.0, tol=5.0)
    s = with_slot(s, replace(s.slots[2], value=OKLCH(0.3, 0.3, 10.0), relations=(rel,)))
    for v in engine.current_violations(s):
        label, required, achieved = forms.violation_text(v, s)
        assert label and required and achieved
        assert label != v.key
