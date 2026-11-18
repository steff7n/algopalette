"""Zakładka „Zasady”: pasek kolorów, wiersze zasad, edycja zbiorcza, cała paleta, preset."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QAbstractButton, QComboBox, QGroupBox, QLabel, QWidget

from algopalette import engine, forms, presets
from algopalette.engine import Violation
from algopalette.gui import help as gh
from algopalette.gui.app import MainWindow, rule_owners
from algopalette.gui.band import BandSlider
from algopalette.gui.colorstrip import Selection
from algopalette.gui.picker import ListPicker
from algopalette.gui.relations import RelationsEditor
from algopalette.gui.widgets import NumEdit
from algopalette.model import (
    OKLCH,
    Band,
    ChromaBand,
    HueArc,
    Relation,
    Rule,
    default_rules,
    with_slot,
)

LEFT = Qt.MouseButton.LeftButton


def settle(win: MainWindow) -> None:
    """Odłożona przebudowa edytora + faktyczne usunięcie starych widżetów."""
    win.rules_tab.flush()
    QCoreApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def commit(edit: NumEdit, text: str) -> None:
    edit.setText(text)
    edit.editingFinished.emit()


def select(win: MainWindow, *indices: int) -> list[str]:
    ids = [win.session.slots[i].id for i in indices]
    win.show_rules(ids)
    settle(win)
    return ids


def rules(win: MainWindow, index: int):
    return win.session.slots[index].rules


def texts(root: QWidget) -> list[str]:
    out: list[str] = []
    for w in root.findChildren(QWidget):
        if isinstance(w, QLabel | QAbstractButton):
            out.append(w.text())
        elif isinstance(w, QGroupBox):
            out.append(w.title())
        elif isinstance(w, QComboBox):
            out.extend(w.itemText(i) for i in range(w.count()))
    return out


# --- okno ------------------------------------------------------------------------------------


def test_tab_order_and_shortcuts(win):
    names = [win.tabs.tabText(i).split("  ")[0] for i in range(win.tabs.count())]
    assert names == ["Zasady", "Propozycje", "Paleta", "Analiza", "Źródło"]
    assert [a.shortcut().toString() for a in win.act_tabs] == ["F2", "F3", "F4", "F5", "F6"]
    assert win.tabs.currentWidget() is win.rules_tab
    assert win.tabs.widget(0) is win.rules_tab


def test_no_legacy_words_anywhere(win):
    found: list[str] = []
    for i in range(win.tabs.count()):
        win.tabs.setCurrentIndex(i)
        settle(win)
        found += texts(win)
        found += [win.tabs.tabText(k) for k in range(win.tabs.count())]
    for indices in ((), (0,), (1,), (2,), (2, 3), (0, 2)):
        select(win, *indices)
        found += texts(win.rules_tab)
    assert found
    for text in found:
        low = text.casefold()
        assert "globaln" not in low, text
        assert "dziedzic" not in low, text
        assert "nastr" not in low, text


def test_show_rules_and_generate(win, monkeypatch):
    win.tabs.setCurrentWidget(win.palette_tab)
    ids = [win.session.slots[4].id, win.session.slots[2].id]
    win.show_rules(ids)
    assert win.tabs.currentWidget() is win.rules_tab
    assert win.rules_tab.strip.selection() == Selection(False, (ids[1], ids[0]))
    win.show_rules([])
    assert win.rules_tab.strip.selection() == Selection(True, ())

    started = []
    monkeypatch.setattr(win.proposals_tab, "start", lambda *a: started.append(a))
    win.tabs.setCurrentWidget(win.rules_tab)
    win.rules_tab.generate_btn.click()
    assert started == [()]
    assert win.tabs.currentWidget() is win.proposals_tab
    win.tabs.setCurrentWidget(win.rules_tab)
    win.act_generate.trigger()
    assert len(started) == 2
    assert win.tabs.currentWidget() is win.proposals_tab


def test_clicking_violation_opens_its_rule(win, qtbot):
    s = win.session
    a1, a2, bg = s.slots[2].id, s.slots[3].id, s.slots[0].id
    violations = [
        Violation("k1", (a1, bg), "contrast_bg", True, 0.5, 4.0, {"lo": 4.5, "hi": None}, {}),
        Violation("k2", (a1, a2), "pair_distance", False, 0.01, 0.07, {"min": 0.08}, {}),
        Violation("k3", (a1, a2), "spread", False, 0.1, 0.3, {"lo": None, "hi": 0.2}, {}),
    ]
    assert [rule_owners(v) for v in violations] == [(a1,), (a1, a2), ()]
    win.violations = violations
    win.violations_panel.show_violations(violations, s)
    table = win.violations_panel.table
    assert table.rowCount() == 3
    assert table.item(0, 1).text() == "kontrast z tłem"
    win.tabs.setCurrentWidget(win.palette_tab)
    table.cellClicked.emit(0, 1)
    assert win.tabs.currentWidget() is win.rules_tab
    assert win.rules_tab.strip.selection() == Selection(False, (a1,))
    table.cellClicked.emit(1, 0)  # miękkie naruszenie pary
    assert win.rules_tab.strip.selection() == Selection(False, (a1, a2))
    table.cellClicked.emit(2, 0)
    assert win.rules_tab.strip.selection() == Selection(True, ())


def test_loading_v1_file_reports_migration_notes(win, tmp_path, monkeypatch):
    reference = Path(__file__).parent.parent / "fixtures" / "v1_reference" / "quality.json"
    data = json.loads(reference.read_text(encoding="utf-8"))[0]["session"]  # „neutralny”, v1
    flags = {"enabled": True, "hard": True, "weight": 1.0}
    c = data["slots"][2]["conditions"]
    c["hue_range"] = {"value": {"lo": 0.0, "hi": 90.0}, **flags}
    c["hue_target"] = {"value": {"target": 60.0, "tol": 20.0}, **flags}
    path = tmp_path / "stara.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    said: list[str] = []
    monkeypatch.setattr(win, "notify", lambda msg, **_k: said.append(msg))
    assert win.open_path(path)
    assert win.migration_notes == ("akcent 1: zakres i cel odcienia scalono do 40–80°",)
    assert any("scalono do 40–80°" in msg for msg in said)
    assert win.session.slots[2].rules.hue == Rule(HueArc(40.0, 80.0))
    select(win, 2)
    assert win.rules_tab.rows["hue"].state == "same"


# --- pasek kolorów i liczba kolorów ----------------------------------------------------------


def test_start_strip_and_color_count(win):
    tab = win.rules_tab
    assert tab.strip.selection() == Selection(True, ())
    assert [c.text() for c in tab.strip.chips][:3] == ["tło", "tekst", "akcent 1"]
    assert len(tab.strip.chips) == 10
    assert tab.count_label.text() == "Kolory: 10"
    tab.minus_btn.click()
    assert len(win.session.slots) == 9
    assert len(tab.strip.chips) == 9
    win.action_undo()  # jeden krok cofania
    assert len(win.session.slots) == 10
    while len(win.session.slots) > 3:
        tab.minus_btn.click()
    assert not tab.minus_btn.isEnabled()
    assert tab.plus_btn.isEnabled()
    while len(win.session.slots) < 16:
        tab.plus_btn.click()
    assert not tab.plus_btn.isEnabled()
    assert tab.count_label.text() == "Kolory: 16"
    win.action_undo()
    assert len(win.session.slots) == 15


def test_new_accent_keeps_selection_and_removed_color_falls_back_to_palette(win):
    tab = win.rules_tab
    ids = select(win, 9)
    tab.plus_btn.click()
    assert tab.strip.selection() == Selection(False, tuple(ids))
    tab.minus_btn.click()
    tab.minus_btn.click()  # zaznaczony akcent 8 znika
    settle(win)
    assert tab.strip.selection() == Selection(True, ())
    assert tab.rows == {}


# --- edycja zbiorcza -------------------------------------------------------------------------


def test_bulk_edit_goes_to_all_selected_in_one_undo_step(win):
    select(win, 2, 3)
    row = win.rules_tab.rows["lightness"]
    assert row.state == "same"
    assert isinstance(row.slider, BandSlider)
    commit(row.slider.range.lo_edit, "0.5")
    assert rules(win, 2).lightness == Rule(Band(0.5, 0.85))
    assert rules(win, 3).lightness == Rule(Band(0.5, 0.85))
    assert rules(win, 4).lightness == Rule(Band(0.60, 0.85))  # niezaznaczony
    win.action_undo()
    assert rules(win, 2).lightness == Rule(Band(0.60, 0.85))
    assert rules(win, 3).lightness == Rule(Band(0.60, 0.85))


def test_slider_drag_is_one_undo_step(win, qtbot):
    select(win, 2)
    bar = win.rules_tab.rows["lightness"].slider.bar
    bar.setFocus()
    bar.active = 0
    before = win.session
    for _ in range(4):
        qtbot.keyClick(bar, Qt.Key.Key_Left)
    assert rules(win, 2).lightness == Rule(Band(0.56, 0.85))
    win.action_undo()
    assert win.session == before


def test_mixed_row_shows_values_and_unifies(win):
    s = win.session
    other = replace(s.slots[3].rules, chroma=Rule(ChromaBand("rel", 0.5, 0.7), hard=False))
    win.set_session(with_slot(s, replace(s.slots[3], rules=other)))
    select(win, 2, 3)
    row = win.rules_tab.rows["chroma"]
    assert row.state == "mixed"
    text = row.mixed_label.text()
    assert "różne" in text
    assert "akcent 1: 0.060–0.200" in text
    assert "akcent 2: 50–70% · miękka" in text
    assert row.slider is None
    before = win.session
    row.unify_btn.click()
    settle(win)
    first = Rule(ChromaBand("abs", 0.06, 0.20))
    assert rules(win, 2).chroma == first
    assert rules(win, 3).chroma == first
    assert win.rules_tab.rows["chroma"].state == "same"
    win.action_undo()
    assert win.session == before


def test_mixed_row_remove_everywhere(win):
    s = win.session
    win.set_session(
        with_slot(
            s, replace(s.slots[3], rules=replace(s.slots[3].rules, hue=Rule(HueArc(0.0, 60.0))))
        )
    )
    select(win, 2, 3)
    row = win.rules_tab.rows["hue"]
    assert row.state == "mixed"
    assert "akcent 1: brak" in row.mixed_label.text()
    row.remove_btn.click()
    settle(win)
    assert rules(win, 2).hue is None and rules(win, 3).hue is None
    assert win.rules_tab.rows["hue"].state == "absent"


def test_rows_follow_applicability_of_selection(win):
    tab = win.rules_tab
    select(win, 0, 2)  # tło + akcent
    assert list(tab.rows) == ["lightness", "chroma", "hue"]
    assert tab.relations is None
    assert tab.scheme_row is None
    select(win, 1, 2)  # tekst + akcent
    assert list(tab.rows) == ["lightness", "chroma", "hue", "contrast_bg"]
    assert tab.scheme_row is None
    select(win, 2, 5)
    assert list(tab.rows) == list(forms.DISPLAY_ORDER)
    assert tab.relations is None
    assert tab.scheme_row is not None
    select(win, 2)
    assert isinstance(tab.relations, RelationsEditor)
    assert tab.scheme_row is not None
    select(win, 0)
    assert list(tab.rows) == ["lightness", "chroma", "hue"]
    assert isinstance(tab.relations, RelationsEditor)
    assert "tło" in tab.editing_label.text()


# --- wiersz zasady ---------------------------------------------------------------------------


def test_rule_row_controls(win):
    tab = win.rules_tab
    select(win, 2)
    row = tab.rows["lightness"]
    row.hard_box.click()
    assert rules(win, 2).lightness == Rule(Band(0.60, 0.85), hard=False)
    row.enabled_box.click()
    assert rules(win, 2).lightness == Rule(Band(0.60, 0.85), enabled=False, hard=False)
    assert not row.value_box.isEnabled()
    commit(row.weight_edit, "2.5")
    assert rules(win, 2).lightness.weight == 2.5
    assert tab.rows["lightness"] is row  # zmiany wartości nie przebudowują wiersza
    row.remove_btn.click()
    settle(win)
    assert rules(win, 2).lightness is None
    row = tab.rows["lightness"]
    assert row.state == "absent"
    row.add_btn.click()
    settle(win)
    assert rules(win, 2).lightness == Rule(forms.default_for("lightness", win.session))
    assert tab.rows["lightness"].state == "same"


def test_hue_row_has_both_notations_and_exclusions_reach_session(win):
    tab = win.rules_tab
    select(win, 2, 3)
    tab.rows["hue"].add_btn.click()
    settle(win)
    slider = tab.rows["hue"].slider
    assert isinstance(slider, BandSlider)
    assert slider.center_edit is not None and slider.half_edit is not None
    commit(slider.center_edit, "350")
    commit(slider.half_edit, "20")
    assert rules(win, 2).hue == Rule(HueArc(330.0, 10.0))
    slider.set_values(0.0, 270.0, ())
    commit(slider.range.hi_edit, "270")
    commit(slider.range.lo_edit, "0")
    slider.add_button.click()
    arc = rules(win, 3).hue.value
    assert (arc.lo, arc.hi) == (0.0, 270.0)
    assert arc.exclude == ((117.0, 153.0),)
    assert rules(win, 2).hue == rules(win, 3).hue
    for name in ("lightness", "chroma"):
        assert isinstance(tab.rows[name].slider, BandSlider)
        assert tab.rows[name].slider.center_edit is None


def test_chroma_mode_change_rebuilds_row(win):
    tab = win.rules_tab
    select(win, 2)
    row = tab.rows["chroma"]
    row.mode_combo.setCurrentIndex(row.mode_combo.findData("rel"))
    row.mode_combo.activated.emit(row.mode_combo.currentIndex())
    settle(win)
    assert rules(win, 2).chroma == Rule(ChromaBand("rel", 0.2, 0.6))
    assert tab.rows["chroma"] is not row
    assert tab.rows["chroma"].slider.maximum == 1.0


def test_scheme_row(win):
    tab = win.rules_tab
    ids = select(win, 2, 3)
    row = tab.scheme_row
    assert row.check.isChecked()
    targets = engine.hue_targets(win.session)
    if targets:
        assert "°" in row.target.text()
    else:
        assert row.target.text().endswith("—")
    row.check.click()
    assert [win.session.slots[i].use_scheme for i in (2, 3, 4)] == [False, False, True]
    win.rules_tab.strip.select([ids[0], win.session.slots[4].id])
    settle(win)
    assert tab.scheme_row.check.checkState() == Qt.CheckState.PartiallyChecked
    tab.scheme_row.check.click()
    assert win.session.slots[2].use_scheme and win.session.slots[4].use_scheme
    tab.scheme_row.link.click()
    settle(win)
    assert tab.strip.selection() == Selection(True, ())
    assert tab.hue_box is not None


def test_relations_are_edited_for_single_color(win):
    tab = win.rules_tab
    select(win, 2)
    tab.relations.findChild(QAbstractButton).click()  # „+ dodaj zależność”
    settle(win)
    rel = win.session.slots[2].relations
    assert len(rel) == 1 and rel[0].kind == "hue"
    assert isinstance(tab.relations, RelationsEditor)


# --- cała paleta -----------------------------------------------------------------------------


def test_whole_palette_page(win, qtbot):
    tab = win.rules_tab
    select(win)
    w = tab.palette_widgets
    for key in (
        "contrast_metric",
        "delta_e",
        "fit_method",
        "hues.kind",
        "hues.rotation",
        "hues.tol",
        "hues.jitter",
        "spread.add",
        "avoid.distance",
        "gen.n_proposals",
        "gen.seed",
        "gen.budget",
        "gen.time_cap_s",
        "gen.min_diversity",
        "gen.hard_weight",
        "gen.threads",
    ):
        assert key in w, key
    assert "hues.center" not in w  # pola nie pasujące do rodzaju układu są schowane
    commit(w["gen.threads"], "4")
    commit(w["gen.budget"], "500")
    assert (win.session.globals.optimizer.threads, win.session.globals.optimizer.budget) == (4, 500)
    w["spread.add"].click()
    settle(win)
    assert win.session.globals.lightness_spread is not None
    assert "spread.range" in tab.palette_widgets


def test_custom_hue_list_uses_picker(win, qtbot):
    tab = win.rules_tab
    select(win)
    kind = tab.palette_widgets["hues.kind"]
    assert tab.custom_picker is None
    kind.setCurrentIndex(kind.findData("custom"))
    kind.activated.emit(kind.currentIndex())
    settle(win)
    picker = tab.custom_picker
    assert isinstance(picker, ListPicker) and picker.mode == "hue"
    qtbot.mouseClick(picker.wheel, LEFT, pos=picker.wheel.point_for(120.0).toPoint())
    qtbot.mouseClick(picker.wheel, LEFT, pos=picker.wheel.point_for(300.0).toPoint())
    scheme = win.session.globals.hue_scheme
    assert scheme.kind == "custom"
    assert [round(h) for h in scheme.custom] == [120, 300]
    assert tab.custom_picker is picker  # dodawanie odcieni nie przebudowuje strony
    kind = tab.palette_widgets["hues.kind"]
    kind.setCurrentIndex(kind.findData("analogous"))
    kind.activated.emit(kind.currentIndex())
    settle(win)
    assert tab.custom_picker is None
    assert "hues.center" in tab.palette_widgets and "hues.spread" in tab.palette_widgets


def test_avoid_colors_use_color_picker(win, qtbot):
    tab = win.rules_tab
    select(win)
    picker = tab.avoid_picker
    assert isinstance(picker, ListPicker) and picker.mode == "color"
    qtbot.mouseClick(picker.wheel, LEFT, pos=picker.wheel.point_for(40.0).toPoint())
    g = win.session.globals
    assert len(g.avoid_colors) == 1 and isinstance(g.avoid_colors[0], OKLCH)
    assert g.avoid_distance == 0.05  # lista bez odległości nic by nie robiła
    assert tab.palette_widgets["avoid.distance"].value() == 0.05
    commit(tab.palette_widgets["avoid.distance"], "0.08")
    assert win.session.globals.avoid_distance == 0.08


def test_metric_change_rescales_rules(win):
    select(win)
    met = win.rules_tab.palette_widgets["contrast_metric"]
    met.setCurrentIndex(met.findData("apca"))
    met.activated.emit(met.currentIndex())
    assert win.session.globals.contrast_metric == "apca"
    assert rules(win, 2).contrast_bg.value.lo == pytest.approx(60.0)


# --- preset ----------------------------------------------------------------------------------


def preset_names(win) -> list[str]:
    combo = win.rules_tab.preset_combo
    return [combo.itemData(i) for i in range(combo.count())]


def test_preset_search_category_and_apply(win):
    tab = win.rules_tab
    assert preset_names(win) == [p.name for p in presets.list_presets()]
    assert "neutralny" in tab.current_label.text()
    assert "(zmieniony)" not in tab.current_label.text()
    tab.search.setText("mgl")
    assert preset_names(win) == ["chłodny mglisty"]
    tab.search.setText("")
    tab.category.setCurrentIndex(tab.category.findData("Ciepłe"))
    assert set(preset_names(win)) >= {"ziemisty", "jesienny"}
    assert "neon" not in preset_names(win)
    tab.category.setCurrentIndex(0)
    tab.preset_combo.setCurrentIndex(preset_names(win).index("chłodny mglisty"))
    before = win.session
    tab.apply_btn.click()
    settle(win)
    assert win.session.preset == "chłodny mglisty"
    assert win.session == presets.apply_preset(before, "chłodny mglisty")
    assert "chłodny mglisty" in tab.current_label.text()
    assert "(zmieniony)" not in tab.current_label.text()
    select(win, 2)
    tab.rows["lightness"].hard_box.click()
    assert "(zmieniony)" in tab.current_label.text()
    win.action_undo()
    assert "(zmieniony)" not in tab.current_label.text()


def test_save_and_delete_own_preset(win):
    tab = win.rules_tab
    tab.preset_name.setText("mój zestaw")
    tab.save_btn.click()
    assert "mój zestaw" in preset_names(win)
    assert win.session.preset == "mój zestaw"
    assert "mój zestaw" in tab.current_label.text()
    assert "(zmieniony)" not in tab.current_label.text()
    tab.category.setCurrentIndex(tab.category.findData(presets.USER_CATEGORY))
    assert preset_names(win) == ["mój zestaw"]
    tab.delete_btn.click()
    assert preset_names(win) == []
    assert "(zmieniony)" in tab.current_label.text()  # presetu już nie ma


def test_polarity_with_fresh_preset_reapplies_without_asking(win, monkeypatch):
    tab = win.rules_tab
    monkeypatch.setattr(tab, "ask_polarity", lambda _p: pytest.fail("nie powinno pytać"))
    tab.pol_light.click()
    assert win.session.globals.polarity == "light"
    assert win.session.preset == "neutralny"
    assert rules(win, 0) == default_rules("bg", "light", "wcag21")
    assert tab.pol_light.isChecked()
    assert "(zmieniony)" not in tab.current_label.text()


@pytest.mark.parametrize("choice", ["replace", "mark", "cancel"])
def test_polarity_with_modified_rules_asks(win, monkeypatch, choice):
    tab = win.rules_tab
    s = win.session
    darker = replace(s.slots[2].rules, lightness=Rule(Band(0.4, 0.5)))
    win.set_session(with_slot(s, replace(s.slots[2], rules=darker)))
    asked = []
    monkeypatch.setattr(tab, "ask_polarity", lambda p: asked.append(p) or choice)
    tab.pol_light.click()
    assert asked == ["light"]
    if choice == "cancel":
        assert win.session.globals.polarity == "dark"
        assert tab.pol_dark.isChecked() and not tab.pol_light.isChecked()
        assert rules(win, 2).lightness == Rule(Band(0.4, 0.5))
    elif choice == "mark":
        assert win.session.globals.polarity == "light"
        assert rules(win, 2).lightness == Rule(Band(0.4, 0.5))
    else:
        assert win.session.globals.polarity == "light"
        assert rules(win, 2) == default_rules("accent", "light", "wcag21")


def test_polarity_without_preset_asks(win, monkeypatch):
    tab = win.rules_tab
    win.set_session(replace(win.session, preset=None))
    assert "własne zasady" in tab.current_label.text()
    monkeypatch.setattr(tab, "ask_polarity", lambda _p: "replace")
    tab.pol_light.click()
    assert win.session.preset == "neutralny"
    assert win.session.globals.polarity == "light"


# --- cofanie i pomoc -------------------------------------------------------------------------


def test_undo_refreshes_editor(win):
    tab = win.rules_tab
    select(win, 2)
    rel = Relation("hue", win.session.slots[3].id, "eq", 180.0, tol=15.0)
    win.set_session(with_slot(win.session, replace(win.session.slots[2], relations=(rel,))))
    settle(win)
    commit(tab.rows["lightness"].slider.range.lo_edit, "0.3")
    win.action_undo()
    settle(win)
    assert tab.rows["lightness"].slider.values()[0] == 0.60
    win.action_undo()
    settle(win)
    assert win.session.slots[2].relations == ()


@pytest.mark.parametrize("indices", [(), (0,), (1,), (2,), (2, 3), (0, 2)])
def test_every_element_has_help(win, indices):
    select(win, *indices)
    assert gh.uncovered(win.rules_tab) == []


def test_help_covers_elements_added_later(win, qtbot):
    tab = win.rules_tab
    select(win, 2)
    tab.rows["lightness"].slider.add_button.click()
    tab.rows["hue"].add_btn.click()
    tab.relations.findChild(QAbstractButton).click()
    settle(win)
    assert gh.uncovered(tab) == []
    select(win)
    kind = tab.palette_widgets["hues.kind"]
    kind.setCurrentIndex(kind.findData("custom"))
    kind.activated.emit(kind.currentIndex())
    settle(win)
    picker = tab.custom_picker
    qtbot.mouseClick(picker.wheel, LEFT, pos=picker.wheel.point_for(120.0).toPoint())
    tab.avoid_picker.add_button.click()
    tab.palette_widgets["spread.add"].click()
    settle(win)
    assert gh.uncovered(tab) == []
    for key, topic in gh.TOPICS.items():
        if key.startswith("rules."):
            assert topic.title and topic.short, key


def pick_lock(win: MainWindow, mode: str) -> None:
    box = win.rules_tab.lock_combo
    assert box is not None
    box.setCurrentIndex(box.findData(mode))
    box.activated.emit(box.currentIndex())
    settle(win)


def test_rules_lock_survives_preset_and_freezes_hue(win):
    tab = win.rules_tab
    (a1,) = select(win, 2)
    box = tab.lock_combo
    assert box is not None and [box.itemData(i) for i in range(box.count())] == [
        "off",
        "rules",
        "hue",
    ]
    target = tab.hue_targets()[a1]
    tol = win.session.globals.hue_scheme.tol
    pick_lock(win, "hue")
    slot = win.session.slots[2]
    assert slot.rules_lock == "hue" and slot.use_scheme is False
    assert slot.rules.hue is not None
    assert slot.rules.hue.value.lo == pytest.approx((target - tol) % 360, abs=1e-6)
    assert tab.strip.chips[2].text().endswith("🔒")
    assert tab.lock_combo is not None and tab.lock_combo.currentData() == "hue"
    kept = slot.rules
    tab.preset_combo.setCurrentIndex(tab.preset_combo.findData("pastel"))
    tab.apply_btn.click()
    settle(win)
    assert win.session.preset == "pastel"
    assert win.session.slots[2].rules == kept
    assert win.session.slots[3].rules == presets.apply_preset(win.session, "pastel").slots[3].rules
    assert "(zmieniony)" not in tab.current_label.text()


def test_rules_lock_mixed_selection_and_all_accents_skip_locked(win):
    tab = win.rules_tab
    ids = select(win, 2)
    pick_lock(win, "rules")
    tab.strip.select_all_accents()
    settle(win)
    assert ids[0] not in tab.ids
    assert len(tab.ids) == len(win.session.slots) - 3
    select(win, 2, 3)
    box = tab.lock_combo
    assert box is not None and box.currentData() is None  # „— różnie —”
    pick_lock(win, "off")
    assert {sl.rules_lock for sl in win.session.slots} == {"off"}
    select(win, 0, 2)
    box = tab.lock_combo
    assert box is not None and box.findData("hue") == -1  # tło: bez zamrażania odcienia
