"""Presety: deklaracje wbudowane, nakładanie, „(zmieniony)”, polaryzacja, presety użytkownika."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from algopalette import io as aio
from algopalette import presets
from algopalette.migrate import migrate_v1
from algopalette.model import (
    OKLCH,
    Band,
    HueArc,
    Interval,
    Relation,
    Rule,
    add_accent,
    default_rules,
    default_session,
    remove_slot,
    with_slot,
)
from algopalette.presets import (
    CATEGORIES,
    Preset,
    apply_preset,
    change_polarity,
    delete_user_preset,
    is_modified,
    list_presets,
    migrate_user_moods,
    save_user_preset,
    search,
)
from algopalette.presets_builtin import BUILTIN, PresetDef

REFERENCE = Path(__file__).parent / "fixtures" / "v1_reference" / "quality.json"
OLD_NINE = [
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


# Akcenty L 0.70–0.80 na ciemnym tle nie osiągają |Lc| ≥ 75 (potrzeba L ≥ 0.803): stary silnik
# dawał tu 0 z 6 propozycji bez twardych naruszeń, a spec §8 wymaga 5 z 6 dla każdego presetu.
FIXED_OLD_CASE = ("nocny wysoki kontrast", "dark", "apca")


@pytest.fixture(autouse=True)
def _cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))


def start(polarity="dark", metric="wcag21"):
    s = default_session()
    return replace(s, globals=replace(s.globals, polarity=polarity, contrast_metric=metric))


def quality_cases():
    return json.loads(REFERENCE.read_text(encoding="utf-8"))


# --- deklaracje ------------------------------------------------------------------------------


def test_builtin_declarations():
    assert len(CATEGORIES) == 11
    names = [p.name for p in BUILTIN]
    assert len(set(names)) == len(names)
    assert set(OLD_NINE) <= set(names)
    for p in BUILTIN:
        assert isinstance(p, PresetDef)
        assert p.category in CATEGORIES
        assert p.description.endswith(".")
        assert p.polarities
        assert set(p.polarities) <= {"dark", "light"}


def test_list_presets_builtin_first_then_user():
    save_user_preset("żółw", default_session(), "opis ż")
    save_user_preset("alfa", default_session())
    listed = list_presets()
    builtin = [p for p in listed if p.builtin]
    assert [p.name for p in builtin] == [p.name for p in BUILTIN]
    assert listed[: len(builtin)] == builtin
    user = listed[len(builtin) :]
    assert [p.name for p in user] == ["alfa", "żółw"]
    assert user[1] == Preset("żółw", presets.USER_CATEGORY, "opis ż", False, ("dark",))


def test_search_ignores_case_and_diacritics():
    assert [p.name for p in search("CHLODNY")] == ["chłodny mglisty"]
    assert "pastel" in [p.name for p in search("jasne")]  # szuka też w opisie
    assert search("nie ma takiego") == []
    warm = search("", "Ciepłe")
    assert {"ziemisty", "jesienny"} <= {p.name for p in warm}
    assert all(p.category == "Ciepłe" for p in warm)
    assert search("neon", "Ciepłe") == []
    assert [p.name for p in search("")] == [p.name for p in list_presets()]


# --- dziewięć dawnych = migracja sesji wzorcowych --------------------------------------------


@pytest.mark.parametrize(
    "case", quality_cases(), ids=lambda c: f"{c['mood']}/{c['polarity']}/{c['metric']}"
)
def test_old_nine_equal_migrated_reference(case):
    out, notes = migrate_v1(case["session"])
    assert notes == []
    expected = aio.session_from_dict(out)
    got = apply_preset(start(case["polarity"], case["metric"]), case["mood"])
    assert got.preset == case["mood"] == expected.preset
    wanted = [s.rules for s in expected.slots]
    if (case["mood"], case["polarity"], case["metric"]) == FIXED_OLD_CASE:
        # jedyne odstępstwo od dawnych nastrojów: wariant, który był niespełnialny
        assert case["ok_count"] == 0
        assert all(r.lightness == Rule(Band(0.70, 0.80)) for r in wanted[2:])
        wanted[2:] = [replace(r, lightness=Rule(Band(0.80, 0.92))) for r in wanted[2:]]
    assert [s.rules for s in got.slots] == wanted
    assert [s.use_scheme for s in got.slots] == [s.use_scheme for s in expected.slots]
    assert got.globals.hue_scheme == expected.globals.hue_scheme
    assert got.globals.lightness_spread == expected.globals.lightness_spread
    assert got.globals.polarity == expected.globals.polarity
    assert got.globals.contrast_metric == expected.globals.contrast_metric


def test_neutral_equals_default_session():
    s = default_session()
    assert apply_preset(s, "neutralny") == s


# --- nakładanie ------------------------------------------------------------------------------


def test_apply_keeps_everything_but_rules():
    s = default_session()
    rel = Relation("hue", s.slots[3].id, "eq", 180.0, tol=15.0)
    s = with_slot(
        s,
        replace(
            s.slots[2], name="słowa", locked=True, value=OKLCH(0.7, 0.1, 10.0), relations=(rel,)
        ),
    )
    g = replace(
        s.globals,
        avoid_colors=(OKLCH(0.5, 0.1, 30.0),),
        avoid_distance=0.07,
        optimizer=replace(s.globals.optimizer, n_proposals=128, seed=7, budget=500, threads=2),
        delta_e="2000",
        fit_method="raytrace",
    )
    s = replace(s, globals=g, view_model="hsl")
    out = apply_preset(s, "chłodny mglisty")
    assert out.preset == "chłodny mglisty"
    for a, b in zip(s.slots, out.slots, strict=True):
        assert (a.id, a.name, a.locked, a.value, a.relations) == (
            b.id,
            b.name,
            b.locked,
            b.value,
            b.relations,
        )
    assert out.globals.optimizer == g.optimizer
    assert out.globals.avoid_colors == g.avoid_colors
    assert out.globals.avoid_distance == g.avoid_distance
    assert (out.globals.delta_e, out.globals.fit_method, out.globals.cvd) == (
        "2000",
        "raytrace",
        g.cvd,
    )
    assert out.view_model == "hsl"
    assert out.slots[2].rules != s.slots[2].rules


def test_apply_replaces_own_rules_and_use_scheme():
    s = default_session()
    hue = Rule(HueArc(0.0, 60.0))
    s = with_slot(
        s, replace(s.slots[4], rules=replace(s.slots[4].rules, hue=hue), use_scheme=False)
    )
    out = apply_preset(s, "pastel")
    assert out.slots[4].rules == out.slots[5].rules
    assert out.slots[4].use_scheme is True


def test_apply_works_for_any_palette_size():
    s = default_session()
    for sl in s.slots[3:]:
        s = remove_slot(s, sl.id)
    small = apply_preset(s, "jesienny")
    assert len(small.slots) == 3
    big = default_session()
    for _ in range(6):
        big = add_accent(big)
    out = apply_preset(big, "jesienny")
    assert len(out.slots) == 16
    assert len({sl.rules for sl in out.slots[2:]}) == 1


def test_apply_unknown_preset_raises():
    with pytest.raises(ValueError, match="nie-ma"):
        apply_preset(default_session(), "nie-ma")


def test_apply_with_explicit_polarity():
    out = apply_preset(default_session(), "neutralny", polarity="light")
    assert out.globals.polarity == "light"
    assert out.slots[0].rules == default_rules("bg", "light", "wcag21")
    assert out.slots[2].rules == default_rules("accent", "light", "wcag21")


# --- (zmieniony) -----------------------------------------------------------------------------


def test_is_modified():
    s = apply_preset(default_session(), "chłodny mglisty")
    assert is_modified(s) is False
    sl = s.slots[3]
    changed_rule = with_slot(
        s, replace(sl, rules=replace(sl.rules, lightness=Rule(Band(0.1, 0.2))))
    )
    assert is_modified(changed_rule) is True
    assert is_modified(with_slot(s, replace(sl, use_scheme=False))) is True
    g = s.globals
    assert is_modified(replace(s, globals=replace(g, hue_scheme=replace(g.hue_scheme, tol=3.0))))
    assert is_modified(replace(s, globals=replace(g, lightness_spread=Rule(Interval(None, 0.5)))))
    # rzeczy, których preset nie ustawia, nie liczą się
    assert is_modified(with_slot(s, replace(sl, value=OKLCH(0.5, 0.1, 5.0), locked=True))) is False
    assert (
        is_modified(replace(s, globals=replace(g, optimizer=replace(g.optimizer, seed=9)))) is False
    )
    assert is_modified(add_accent(s)) is False  # nowy akcent kopiuje zasady ostatniego


def test_is_modified_without_or_with_unknown_preset():
    s = default_session()
    assert is_modified(replace(s, preset=None)) is False
    assert is_modified(replace(s, preset="skasowany")) is True


# --- polaryzacja -----------------------------------------------------------------------------


def test_change_polarity_reapply():
    s = apply_preset(default_session(), "neon")
    out = change_polarity(s, "light", reapply=True)
    assert out.globals.polarity == "light"
    assert out.preset == "neon"
    assert [x.rules for x in out.slots] == [
        x.rules for x in apply_preset(start("light"), "neon").slots
    ]
    assert is_modified(out) is False


def test_change_polarity_mark_only():
    s = apply_preset(default_session(), "neon")
    out = change_polarity(s, "light", reapply=False)
    assert out.globals.polarity == "light"
    assert out.slots == s.slots
    assert out.preset == "neon"
    assert is_modified(out) is True  # zasady zostały z ciemnej wersji


def test_change_polarity_reapply_without_preset_uses_neutral():
    s = replace(default_session(), preset=None)
    out = change_polarity(s, "light", reapply=True)
    assert out.preset == "neutralny"
    assert out.slots[0].rules == default_rules("bg", "light", "wcag21")


# --- presety użytkownika ---------------------------------------------------------------------


def test_user_preset_roundtrip():
    s = apply_preset(start("light", "apca"), "retro terminal")
    sl = s.slots[2]
    arc = Rule(HueArc(25.0, 45.0, exclude=((30.0, 35.0),)), hard=False)
    s = with_slot(s, replace(sl, rules=replace(sl.rules, hue=arc), use_scheme=False))
    save_user_preset("  mój retro ", s, "z poprawką")
    path = aio.config_dir() / "presets.json"
    assert json.loads(path.read_text(encoding="utf-8"))["presets"]["mój retro"]["description"] == (
        "z poprawką"
    )
    assert [p.name for p in path.parent.iterdir()] == ["presets.json"]  # bez pliku tymczasowego

    out = apply_preset(default_session(), "mój retro")
    assert out.preset == "mój retro"
    assert (out.globals.polarity, out.globals.contrast_metric) == ("light", "apca")
    assert [x.rules for x in out.slots] == [x.rules for x in s.slots]
    assert [x.use_scheme for x in out.slots] == [x.use_scheme for x in s.slots]
    assert out.globals.hue_scheme == s.globals.hue_scheme
    assert out.globals.lightness_spread == s.globals.lightness_spread
    assert is_modified(out) is False
    assert [x.value for x in out.slots] == [x.value for x in default_session().slots]


def test_user_preset_on_bigger_palette_repeats_last_accent():
    base = default_session()
    for sl in base.slots[4:]:
        base = remove_slot(base, sl.id)  # 2 akcenty
    last = base.slots[3]
    base = with_slot(base, replace(last, rules=replace(last.rules, lightness=Rule(Band(0.3, 0.4)))))
    save_user_preset("dwa", base)
    out = apply_preset(default_session(), "dwa")
    assert out.slots[2].rules == base.slots[2].rules
    assert all(sl.rules == base.slots[3].rules for sl in out.slots[3:])
    assert is_modified(out) is False


def test_user_preset_name_rules():
    with pytest.raises(ValueError, match="wbudowany"):
        save_user_preset("neon", default_session())
    with pytest.raises(ValueError, match="pusta"):
        save_user_preset("   ", default_session())
    with pytest.raises(ValueError, match="wbudowany"):
        delete_user_preset("neon")
    with pytest.raises(ValueError, match="nie-ma"):
        delete_user_preset("nie-ma")
    save_user_preset("a", default_session())
    delete_user_preset("a")
    assert all(p.builtin for p in list_presets())


def test_user_preset_changes_metric_and_rescales_relations():
    apca = start("dark", "apca")
    apca = apply_preset(apca, "neutralny")
    save_user_preset("apca", apca)
    s = default_session()  # wcag21
    rel = Relation("contrast", s.slots[3].id, "ge", 4.5)
    s = with_slot(s, replace(s.slots[2], relations=(rel,)))
    out = apply_preset(s, "apca")
    assert out.globals.contrast_metric == "apca"
    assert out.slots[2].relations[0].value == pytest.approx(60.0)


def test_broken_presets_file_is_reported(tmp_path):
    path = aio.config_dir() / "presets.json"
    path.parent.mkdir(parents=True)
    path.write_text("{to nie json", encoding="utf-8")
    with pytest.raises(ValueError, match=r"presets\.json"):
        list_presets()


# --- przeniesienie nastrojów użytkownika -----------------------------------------------------


def _write_moods(case):
    path = aio.config_dir() / "moods.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "format": "algopalette.moods.v1",
        "moods": {"mój nastrój": {"description": "stary", "globals": case["session"]["globals"]}},
    }
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_migrate_user_moods():
    case = next(
        c
        for c in quality_cases()
        if (c["mood"], c["polarity"], c["metric"]) == ("retro terminal", "light", "apca")
    )
    path = _write_moods(case)
    before = path.read_bytes()
    assert migrate_user_moods() == 1
    assert path.read_bytes() == before  # stary plik nietknięty
    assert migrate_user_moods() == 0  # drugi raz nic nie dopisuje
    user = [p for p in list_presets() if not p.builtin]
    assert user == [Preset("mój nastrój", presets.USER_CATEGORY, "stary", False, ("light",))]

    expected = aio.session_from_dict(migrate_v1(case["session"])[0])
    out = apply_preset(default_session(), "mój nastrój")
    assert (out.globals.polarity, out.globals.contrast_metric) == ("light", "apca")
    assert out.slots[0].rules == expected.slots[0].rules
    assert out.slots[1].rules == expected.slots[1].rules
    assert all(sl.rules == expected.slots[2].rules for sl in out.slots[2:])
    assert [sl.use_scheme for sl in out.slots] == [sl.use_scheme for sl in expected.slots]
    assert out.globals.hue_scheme == expected.globals.hue_scheme
    assert out.globals.lightness_spread == expected.globals.lightness_spread


def test_migrate_user_moods_not_repeated_after_delete():
    _write_moods(quality_cases()[0])
    assert migrate_user_moods() == 1
    delete_user_preset("mój nastrój")
    assert migrate_user_moods() == 0
    assert all(p.builtin for p in list_presets())


def test_migrate_user_moods_without_file_or_with_garbage():
    assert migrate_user_moods() == 0
    path = aio.config_dir() / "moods.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]", encoding="utf-8")
    assert migrate_user_moods() == 0


def test_migrate_user_moods_keeps_existing_user_preset():
    save_user_preset("mój nastrój", default_session(), "nowy")
    _write_moods(quality_cases()[0])
    assert migrate_user_moods() == 0
    user = [p for p in list_presets() if not p.builtin]
    assert [p.description for p in user] == ["nowy"]


# --- komplet presetów wbudowanych (Task 19) --------------------------------------------------


def applied(pdef, polarity, metric="wcag21", accents=8):
    s = start(polarity, metric)
    while len(s.slots) - 2 > accents:
        s = remove_slot(s, s.slots[-1].id)
    return apply_preset(s, pdef.name, polarity=polarity)


def test_at_least_48_presets_in_every_category():
    assert len(BUILTIN) >= 48
    per_category = {c: [p.name for p in BUILTIN if p.category == c] for c in CATEGORIES}
    assert all(len(names) >= 3 for names in per_category.values()), per_category
    # kolejność rejestru = kolejność kategorii (tak je wypisuje pomoc i lista w oknie)
    order = [CATEGORIES.index(p.category) for p in BUILTIN]
    assert order == sorted(order)


def test_descriptions_say_what_the_preset_sets():
    for p in BUILTIN:
        text = p.description
        assert len(text.split()) >= 6, p.name
        assert text[0].isupper() and text.endswith("."), p.name
        assert text.count(".") == 1 or "°" in text or "0." in text, p.name  # jedno zdanie
        assert p.name.casefold() not in text.casefold(), p.name


@pytest.mark.parametrize("polarity", ["dark", "light"])
@pytest.mark.parametrize("metric", ["wcag21", "apca"])
def test_presets_are_pairwise_different(polarity, metric):
    seen: dict[object, str] = {}
    for p in BUILTIN:
        if polarity not in p.polarities:
            continue
        s = applied(p, polarity, metric)
        g = s.globals
        key = (
            tuple((slot.rules, slot.use_scheme) for slot in s.slots),
            g.hue_scheme,
            g.lightness_spread,
        )
        assert key not in seen, (p.name, seen.get(key))
        seen[key] = p.name


@pytest.mark.parametrize("p", BUILTIN, ids=lambda p: p.name)
def test_every_preset_applies_and_roundtrips(p, tmp_path):
    for polarity in p.polarities:
        for metric in ("wcag21", "apca"):
            for accents in (1, 5, 8, 14):
                s = applied(p, polarity, metric, accents) if accents <= 8 else None
                if s is None:
                    s = start(polarity, metric)
                    while len(s.slots) - 2 < accents:
                        s = add_accent(s)
                    s = apply_preset(s, p.name, polarity=polarity)
                assert s.preset == p.name and not is_modified(s)
                path = tmp_path / "s.json"
                aio.save_session(s, path, overwrite=True)
                assert aio.load_session(path) == s
                for slot in s.slots:  # zakresy mają sens
                    r = slot.rules
                    for rule in (r.lightness, r.chroma):
                        if rule is not None:
                            lo, hi = rule.value.lo, rule.value.hi
                            assert lo is None or hi is None or lo < hi, (p.name, slot.name)


def by_name(name):
    return next(p for p in BUILTIN if p.name == name)


def chroma_hi(slot):
    band = slot.rules.chroma.value
    assert band.mode == "abs"
    return band.hi


@pytest.mark.parametrize("name", ["szarości z akcentem", "gazeta"])
def test_gray_presets_have_one_saturated_accent(name):
    p = by_name(name)
    for polarity in p.polarities:
        s = applied(p, polarity)
        first, rest = s.slots[2], s.slots[3:]
        assert first.rules.chroma.value.lo >= 0.10 and first.rules.hue is not None
        assert first.rules.hue.hard and not first.use_scheme
        assert all(chroma_hi(slot) <= 0.03 for slot in rest)
        if name == "szarości z akcentem":
            assert all(chroma_hi(slot) <= 0.02 for slot in rest)


def test_limited_presets_pin_hues_with_a_hard_scheme():
    cases = {"duotone": 2, "jeden odcień, wiele jasności": 1, "dwa bieguny": 2}
    for name, n_hues in cases.items():
        p = by_name(name)
        assert p.category == "Ograniczone"
        s = applied(p, "dark")
        scheme = s.globals.hue_scheme
        assert scheme.kind == "custom" and scheme.hard
        assert len(set(scheme.custom)) == n_hues
        assert all(slot.use_scheme for slot in s.slots[2:])
    poles = set(applied(by_name("dwa bieguny"), "dark").globals.hue_scheme.custom)
    lo, hi = sorted(poles)
    assert hi - lo == 180.0


@pytest.mark.parametrize(
    ("name", "types"),
    [
        ("bezpieczny przy protanopii i deuteranopii", {"protan", "deutan"}),
        ("bezpieczny przy tritanopii", {"tritan"}),
    ],
)
def test_accessibility_presets_turn_on_cvd(name, types):
    p = by_name(name)
    assert p.category == "Dostępność"
    for polarity in p.polarities:
        s = applied(p, polarity)
        assert s.globals.cvd.types == frozenset(types)
        for slot in s.slots[2:]:
            rule = slot.rules.cvd_min_distance
            assert rule is not None and rule.enabled and rule.value >= 0.06 and rule.weight >= 2.0


def test_apca_reading_sets_the_metric():
    p = by_name("APCA do długiego czytania")
    for polarity in p.polarities:
        s = applied(p, polarity, "wcag21")
        assert s.globals.contrast_metric == "apca"
        assert s.slots[1].rules.contrast_bg.value.lo >= 80.0
        assert s.slots[1].rules.contrast_bg.value.hi is not None  # bez oślepiającego kontrastu
        assert not is_modified(s)


def test_fixed_polarity_presets():
    assert by_name("północ").polarities == ("dark",)
    assert by_name("papier i atrament").polarities == ("light",)
    assert by_name("gazeta").polarities == ("light",)
    s = apply_preset(start("dark"), "gazeta")  # bez wersji ciemnej bierze jasną i zmienia tło
    assert s.globals.polarity == "light"
