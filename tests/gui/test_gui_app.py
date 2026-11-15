"""GUI — okno główne: paleta, edytor koloru, warunki, zależności, historia, pliki, zakładki."""

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from algopalette import io as aio
from algopalette.__main__ import fresh_session
from algopalette.gui.app import MainWindow
from algopalette.gui.conditions import ConditionRow
from algopalette.gui.relations import RelationRow
from algopalette.gui.widgets import RangeSlider, ValueSlider
from algopalette.model import Cond, ContrastBound, Relation, SlotConditions, with_slot


def select(win: MainWindow, row: int) -> str:
    from PySide6.QtCore import QCoreApplication, QEvent

    win.palette_tab.table.setCurrentCell(row, 1)
    # stare widżety edytora znikają przez deleteLater — usuń je, zanim testy zaczną szukać
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    sid = win.selected_slot_id()
    assert sid == win.session.slots[row].id
    return sid


def cond_row(win: MainWindow, field: str) -> ConditionRow:
    row = win.palette_tab.editor.findChild(ConditionRow, f"cond-{field}")
    assert row is not None
    return row


def flush(qtbot) -> None:
    from PySide6.QtCore import QCoreApplication, QEvent

    qtbot.wait(5)  # przebudowy odkładane przez QTimer.singleShot(0)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_starts_with_default(win):
    assert win.palette_tab.table.rowCount() == 10
    assert win.session.mood == "neutralny"
    assert win.palette_tab.editor.slot_id == win.session.slots[0].id
    assert "AlgoPalette" in win.windowTitle()


def test_table_shows_hex_and_values(win):
    t = win.palette_tab.table
    s = win.session
    from algopalette.color import to_hex

    assert t.item(2, 3).text().startswith(to_hex(s.slots[2].value, s.globals.fit_method))
    assert t.item(2, 4).text() == f"{s.slots[2].value.l:.3f}"


def test_add_remove_lock_move(win, qtbot):
    pt = win.palette_tab
    select(win, 9)
    pt.add_accent()
    assert len(win.session.slots) == 11
    assert win.selected_slot_id() == win.session.slots[-1].id
    sid = win.selected_slot_id()
    pt.move_selected(-1)
    assert win.session.slots[9].id == sid and win.selected_slot_id() == sid
    pt.toggle_lock()
    assert win.session.slots[9].locked
    assert win.palette_tab.table.item(9, 7).text() == "🔒"
    pt.remove_slot()
    assert len(win.session.slots) == 10 and sid not in {s.id for s in win.session.slots}


def test_cannot_remove_bg(win):
    select(win, 0)
    win.palette_tab.remove_slot()
    assert len(win.session.slots) == 10


def test_keyboard_shortcuts_on_table(win, qtbot):
    t = win.palette_tab.table
    select(win, 4)
    t.setFocus()
    qtbot.keyClick(t, Qt.Key.Key_L)
    assert win.session.slots[4].locked
    qtbot.keyClick(t, Qt.Key.Key_Insert)
    assert len(win.session.slots) == 11


def test_value_slider_edits_and_coalesces(win, qtbot):
    sid = select(win, 3)
    ed = win.palette_tab.editor
    n = len(win.history)
    bar = ed.value_sliders["val-l"].bar
    bar.setFocus()
    for _ in range(3):
        qtbot.keyClick(bar, Qt.Key.Key_Right)
    s = win.session
    slot = next(x for x in s.slots if x.id == sid)
    assert slot.value.l == pytest.approx(0.75)
    assert len(win.history) == n + 1  # trzy kroki = jeden krok cofania
    assert ed.slot_id == sid  # edytor nie został przebudowany na inny slot
    win.action_undo()
    assert next(x for x in win.session.slots if x.id == sid).value.l == pytest.approx(0.72)


def test_hsl_view_toggle_is_not_undo_step(win):
    n = len(win.history)
    win.toggle_view()
    assert win.session.view_model == "hsl" and len(win.history) == n
    assert win.palette_tab.table.horizontalHeaderItem(4).text() == "H°"
    select(win, 2)
    assert "hsl-h" in win.palette_tab.editor.value_sliders
    win.toggle_view()
    assert win.palette_tab.table.horizontalHeaderItem(4).text() == "L"


def test_hsl_slider_writes_oklch(win, qtbot):
    win.toggle_view()
    sid = select(win, 2)
    sl = win.palette_tab.editor.value_sliders["hsl-l"]
    sl.edit.setText("30")
    sl.edit.editingFinished.emit()
    from algopalette import color as col

    v = next(x for x in win.session.slots if x.id == sid).value
    assert col.to_hsl(v, win.session.globals.fit_method)[2] == pytest.approx(30, abs=0.6)


def test_condition_inherited_edit_creates_own_and_reset(win, qtbot):
    sid = select(win, 3)
    row = cond_row(win, "lightness")
    assert row.reset is not None
    assert row.src == "mood" and row.reset.isHidden()
    rs = row.findChild(RangeSlider)
    assert rs is not None
    rs.lo_edit.setText("0.65")
    rs.lo_edit.editingFinished.emit()
    slot = next(x for x in win.session.slots if x.id == sid)
    assert slot.conditions.lightness is not None
    assert slot.conditions.lightness.value.lo == 0.65
    assert row.src == "slot" and not row.reset.isHidden()
    row.reset.click()
    flush(qtbot)
    slot = next(x for x in win.session.slots if x.id == sid)
    assert slot.conditions.lightness is None


def test_condition_add_and_toggle(win, qtbot):
    sid = select(win, 3)
    row = cond_row(win, "hue_target")
    assert row.cond is None
    row._add()
    flush(qtbot)
    slot = next(x for x in win.session.slots if x.id == sid)
    assert slot.conditions.hue_target is not None
    row.hard.setChecked(False)
    slot = next(x for x in win.session.slots if x.id == sid)
    assert slot.conditions.hue_target.hard is False


def test_condition_metric_change_rebuilds(win, qtbot):
    sid = select(win, 3)
    row = cond_row(win, "contrast_bg")
    row._metric("apca")
    flush(qtbot)
    slot = next(x for x in win.session.slots if x.id == sid)
    assert slot.conditions.contrast_bg.value == ContrastBound("apca", 60.0, None)


def test_relations_add_change_kind_delete(win, qtbot):
    sid = select(win, 3)
    rel_ed = win.palette_tab.editor.relations
    rel_ed._add()
    flush(qtbot)
    rows = rel_ed.findChildren(RelationRow)
    assert len(rows) == 1
    rows[0]._kind("distance")
    flush(qtbot)
    slot = next(x for x in win.session.slots if x.id == sid)
    assert slot.relations[0].kind == "distance" and slot.relations[0].value == 0.08
    row = rel_ed.findChildren(RelationRow)[0]
    row._num("weight", 2.5)
    assert next(x for x in win.session.slots if x.id == sid).relations[0].weight == 2.5
    rel_ed.set_relation(0, None)
    flush(qtbot)
    assert next(x for x in win.session.slots if x.id == sid).relations == ()


def test_broken_relation_marked(qtbot):
    s = fresh_session()
    slot = s.slots[3]
    s = with_slot(s, replace(slot, relations=(Relation("hue", "nieistnieje", "eq", 180.0),)))
    w = MainWindow(s, autosave=False)
    qtbot.addWidget(w)
    select(w, 3)
    row = w.palette_tab.editor.relations.findChildren(RelationRow)[0]
    assert row.broken


def test_undo_redo_buttons_state(win):
    assert not win.act_undo.isEnabled()
    select(win, 2)
    win.palette_tab.toggle_lock()
    assert win.act_undo.isEnabled() and not win.act_redo.isEnabled()
    win.action_undo()
    assert not win.session.slots[2].locked and win.act_redo.isEnabled()
    win.action_redo()
    assert win.session.slots[2].locked


def test_violations_panel(qtbot):
    s = fresh_session()
    fg = s.slots[1]
    s = with_slot(
        s,
        replace(
            fg,
            conditions=SlotConditions(contrast_bg=Cond(ContrastBound(None, 30.0, None))),
        ),
    )
    w = MainWindow(s, autosave=False)
    qtbot.addWidget(w)
    p = w.violations_panel
    assert "1 twardych" in p.title.text()
    marks = [p.table.item(r, 0) for r in range(p.table.rowCount())]
    assert any(m is not None and m.text() == "✗" for m in marks)


def test_globals_polarity_and_mood(win, qtbot):
    win.tabs.setCurrentWidget(win.globals_tab)
    g = win.globals_tab
    g._polarity_metric("polarity", "light")
    assert win.session.globals.polarity == "light" and win.session.mood == "neutralny"
    idx = g.mood.findData("neon")
    g.mood.setCurrentIndex(idx)
    g._mood_apply()
    assert win.session.mood == "neon"
    g._opt("n_proposals", 3, True)
    assert win.session.globals.optimizer.n_proposals == 3
    g._cvd_type("deutan", True)
    assert "deutan" in win.session.globals.cvd.types


def test_globals_role_conditions_editable(win, qtbot):
    win.tabs.setCurrentWidget(win.globals_tab)
    editors = win.globals_tab.role_tabs
    accent = editors.widget(2)
    row = accent.findChild(ConditionRow, "cond-min_distance")
    edit = row.findChild(ValueSlider).edit
    edit.setText("0.1")
    edit.editingFinished.emit()
    assert win.session.globals.role_defaults["accent"].min_distance.value == 0.1


def test_user_mood_save_and_delete(win, qtbot):
    win.tabs.setCurrentWidget(win.globals_tab)
    g = win.globals_tab
    g.mood_name.setText("mój")
    g._mood_save()
    flush(qtbot)
    g = win.globals_tab
    assert g.mood.findData("mój") >= 0
    g.mood.setCurrentIndex(g.mood.findData("mój"))
    g._mood_delete()
    flush(qtbot)
    assert win.globals_tab.mood.findData("mój") < 0


def test_source_complete_mode(win):
    src = win.source_tab
    src.paste.setPlainText("#101010 #eeeeee #ff0000 #00ff00")
    src.apply()
    s = win.session
    assert s.slots[0].locked and s.slots[3].locked
    assert src.result.text().startswith("4 kolorów")


def test_source_parse_error(win):
    src = win.source_tab
    src.paste.setPlainText("#101010 xyz")
    assert not src.parse()
    assert "xyz" in src.result.text()


def test_proposals_generate_and_take(win, qtbot):
    n = len(win.history)
    pt = win.proposals_tab
    win.action_generate()
    qtbot.waitUntil(lambda: not pt.running, timeout=60_000)
    assert pt.proposals and pt.table.rowCount() == len(pt.proposals)
    pt.table.setCurrentCell(0, 0)
    pt.take_whole()
    p = pt.proposals[0]
    assert all(win.session.slots[i].value == p.values[s.id] for i, s in enumerate(pt.base.slots))
    assert len(win.history) == n + 1
    pt.table.setCurrentCell(1, 0)
    pt.detail.setCurrentCell(3, 0)
    pt.take_color()
    assert win.session.slots[3].value == pt.proposals[1].values[win.session.slots[3].id]


def test_generate_only_selected(win, qtbot):
    sid = select(win, 4)
    pt = win.proposals_tab
    pt._gen_one()
    qtbot.waitUntil(lambda: not pt.running, timeout=60_000)
    assert all(p.slot_ids == (sid,) for p in pt.proposals)


def test_analysis_all_views(win, qtbot):
    win.tabs.setCurrentWidget(win.analysis_tab)
    a = win.analysis_tab
    for view in ("normal", "protan", "deutan", "tritan"):
        a.view.setCurrentIndex(a.view.findData(view))
        for kind in ("de", "contrast"):
            a.matrix_kind.setCurrentIndex(a.matrix_kind.findData(kind))
            for axis in ("rel", "abs"):
                a.axis.setCurrentIndex(a.axis.findData(axis))
                a.grab()  # rysuje koło i wykres
    assert a.matrix.rowCount() == 8


def test_save_open_roundtrip(win, tmp_path):
    p = tmp_path / "x.json"
    assert win.save_to(p)
    assert win.file_path == p and "x.json" in win.windowTitle()
    other = MainWindow(fresh_session(), autosave=False)
    assert other.open_path(p)
    assert other.session == win.session


def test_open_bad_file_shows_error(win, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(win, "notify", lambda msg, **kw: shown.append((msg, kw)))
    bad = tmp_path / "bad.json"
    bad.write_text("{nie json")
    assert not win.open_path(bad)
    assert shown and shown[0][1].get("error")


def test_export_to_clipboard(win):
    win.action_export()
    text = QGuiApplication.clipboard().text()
    assert '"palettebuilder.v3"' in text or "palettebuilder.v3" in text


def test_autosave_flush_on_close(qtbot):
    w = MainWindow(fresh_session(), autosave=True)
    qtbot.addWidget(w)
    w.palette_tab.table.setCurrentCell(2, 1)
    w.palette_tab.toggle_lock()
    assert w._autosave_pending
    w.close()
    saved = aio.load_session(aio.autosave_path())
    assert saved.slots[2].locked


def test_main_runs_gui(monkeypatch):
    import algopalette.__main__ as m
    import algopalette.gui.app as gapp

    monkeypatch.setattr(gapp, "run", lambda session, **kw: 0)
    with pytest.raises(SystemExit) as e:
        m.main(["--fresh"])
    assert e.value.code == 0


def test_path_type_is_path(win, tmp_path):
    p = tmp_path / "y.json"
    win.save_to(p)
    assert isinstance(win.file_path, Path)
