"""GUI — okno główne: Paleta, Propozycje, Analiza, Źródło, historia, pliki (model v2)."""

import inspect
import time
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QGuiApplication

from algopalette import _engine, color
from algopalette import io as aio
from algopalette.__main__ import fresh_session
from algopalette.gui import analysis_tab, proposals_tab
from algopalette.gui.analysis_tab import hue_segments
from algopalette.gui.app import MainWindow
from algopalette.gui.relations import RelationsEditor
from algopalette.model import (
    OKLCH,
    ContrastBound,
    HueArc,
    Rule,
    add_accent,
    default_rules,
    remove_slot,
    with_slot,
)

IMPLEMENTED = _engine.build_info()["implemented"]
needs_evaluate = pytest.mark.skipif("evaluate" not in IMPLEMENTED, reason="silnik nie ocenia")
needs_generate = pytest.mark.skipif("generate" not in IMPLEMENTED, reason="silnik nie generuje")


def select(win: MainWindow, row: int) -> str:
    win.palette_tab.table.setCurrentCell(row, 1)
    # stare widżety edytora znikają przez deleteLater — usuń je, zanim testy zaczną szukać
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    sid = win.selected_slot_id()
    assert sid == win.session.slots[row].id
    return sid


def slot(win: MainWindow, sid: str):
    return next(x for x in win.session.slots if x.id == sid)


# --- Paleta ----------------------------------------------------------------------------------


def test_starts_with_default(win):
    assert win.palette_tab.table.rowCount() == 10
    assert win.session.preset == "neutralny"
    assert win.palette_tab.editor.slot_id == win.session.slots[0].id
    assert "AlgoPalette" in win.windowTitle()


def test_table_shows_hex_and_values(win):
    t = win.palette_tab.table
    s = win.session
    assert t.item(2, 3).text().startswith(color.to_hex(s.slots[2].value, s.globals.fit_method))
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
    win.tabs.setCurrentWidget(win.palette_tab)
    t = win.palette_tab.table
    select(win, 4)
    t.setFocus()
    qtbot.keyClick(t, Qt.Key.Key_L)
    assert win.session.slots[4].locked
    qtbot.keyClick(t, Qt.Key.Key_Insert)
    assert len(win.session.slots) == 11


def test_value_slider_edits_and_coalesces(win, qtbot):
    win.tabs.setCurrentWidget(win.palette_tab)
    sid = select(win, 3)
    ed = win.palette_tab.editor
    n = len(win.history)
    bar = ed.value_sliders["val-l"].bar
    bar.setFocus()
    for _ in range(3):
        qtbot.keyClick(bar, Qt.Key.Key_Right)
    assert slot(win, sid).value.l == pytest.approx(0.75)
    assert len(win.history) == n + 1  # trzy kroki = jeden krok cofania
    assert ed.slot_id == sid  # edytor nie został przebudowany na inny kolor
    win.action_undo()
    assert slot(win, sid).value.l == pytest.approx(0.72)


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
    v = slot(win, sid).value
    assert color.to_hsl(v, win.session.globals.fit_method)[2] == pytest.approx(30, abs=0.6)


def test_palette_editor_has_value_only_and_links_to_rules(win):
    win.tabs.setCurrentWidget(win.palette_tab)
    sid = select(win, 4)
    ed = win.palette_tab.editor
    assert ed.name is not None and ed.lock is not None
    assert set(ed.value_sliders) == {"val-l", "val-c", "val-h"}
    assert ed.findChild(RelationsEditor) is None  # zasady i zależności są tylko w „Zasadach”
    assert not hasattr(ed, "conditions")
    ed.rules_link.click()
    assert win.tabs.currentWidget() is win.rules_tab
    assert win.rules_tab.strip.selection().ids == (sid,)
    assert next(iter(win.rules_tab.rows)) == "lightness"


def test_undo_redo_buttons_state(win):
    assert not win.act_undo.isEnabled()
    select(win, 2)
    win.palette_tab.toggle_lock()
    assert win.act_undo.isEnabled() and not win.act_redo.isEnabled()
    win.action_undo()
    assert not win.session.slots[2].locked and win.act_redo.isEnabled()
    win.action_redo()
    assert win.session.slots[2].locked


@needs_evaluate
def test_violations_panel(qtbot):
    s = fresh_session()
    fg = s.slots[1]
    strict = replace(fg.rules, contrast_bg=Rule(ContrastBound(None, 30.0, None)))
    w = MainWindow(with_slot(s, replace(fg, rules=strict)), autosave=False)
    qtbot.addWidget(w)
    p = w.violations_panel
    assert "1 twardych" in p.title.text()
    assert p.table.rowCount() == 1
    mark, label = p.table.item(0, 0), p.table.item(0, 1)
    assert mark is not None and mark.text() == "✗"
    assert label is not None and label.text() == "kontrast z tłem"
    p.table.cellClicked.emit(0, 1)
    assert w.rules_tab.strip.selection().ids == (fg.id,)


def test_engine_rejection_does_not_break_window(win, monkeypatch):
    import algopalette.gui.app as gapp

    said = []
    monkeypatch.setattr(win, "notify", lambda msg, **_k: said.append(msg))

    def boom(_session):
        raise ValueError("slots[2].rules: zła wartość")

    monkeypatch.setattr(gapp, "current_violations", boom)
    win.palette_tab.table.setCurrentCell(2, 1)
    win.palette_tab.toggle_lock()
    assert win.session.slots[2].locked
    assert win.violations == []
    assert any("zła wartość" in m for m in said)


# --- Źródło ----------------------------------------------------------------------------------


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


def test_source_character_rules_show_in_rules_tab(win):
    src = win.source_tab
    src.paste.setPlainText("#1e1e2e #cdd6f4 #f38ba8 #a6e3a1 #89b4fa #f9e2af")
    src.mode.setCurrentIndex(src.mode.findData("character"))
    src.apply()
    s = win.session
    assert s.preset is None
    assert s.globals.hue_scheme.kind == "custom"
    accent = s.slots[2].rules
    assert accent.chroma is not None and accent.chroma.value.mode == "rel"
    assert all(sl.rules == accent and sl.use_scheme for sl in s.slots[2:])
    win.show_rules([s.slots[2].id, s.slots[3].id])
    row = win.rules_tab.rows["chroma"]
    assert row.state == "same"
    assert row.slider.values()[:2] == (accent.chroma.value.lo, accent.chroma.value.hi)
    assert "własne zasady" in win.rules_tab.current_label.text()


def test_source_transfer_rules_show_in_rules_tab(win):
    src = win.source_tab
    src.paste.setPlainText("#1e1e2e #cdd6f4 #f38ba8 #a6e3a1 #89b4fa")
    src.mode.setCurrentIndex(src.mode.findData("transfer"))
    src.polarity.setCurrentIndex(src.polarity.findData("light"))
    src.apply()
    s = win.session
    assert len(s.slots) == 5
    assert s.globals.polarity == "light"
    assert all(not sl.use_scheme and sl.rules.hue is not None for sl in s.slots[2:])
    win.show_rules([s.slots[2].id])
    assert win.rules_tab.rows["hue"].state == "same"
    assert not win.rules_tab.scheme_row.check.isChecked()
    assert win.rules_tab.pol_light.isChecked()


# --- Propozycje (zadanie silnika odpytywane zegarem) -----------------------------------------


def test_proposals_poll_engine_job_with_timer(win, fake_engine):
    pt = win.proposals_tab
    win.generate()
    assert win.tabs.currentWidget() is pt
    assert pt.running and pt._timer.isActive()
    assert pt._timer.interval() <= 40  # ok. 30 Hz
    assert fake_engine.calls == [None]
    assert not pt.gen_all.isEnabled() and pt.cancel_btn.isEnabled()
    gen = fake_engine.gen
    gen.fraction = 0.5
    pt._tick()
    assert pt.running and pt.progress.value() == 500
    gen.finish(3)
    pt._tick()
    assert not pt.running and not pt._timer.isActive()
    assert len(pt.proposals) == 3 and pt.table.rowCount() == 3
    assert "3 propozycji, 3 bez twardych naruszeń" in pt.status.text()
    assert pt.gen_all.isEnabled() and not pt.cancel_btn.isEnabled()


def test_proposals_tab_has_no_python_threads():
    source = inspect.getsource(proposals_tab)
    assert "threading" not in source
    assert "QThread" not in source


def test_second_start_while_running_is_refused(win, fake_engine, monkeypatch):
    said = []
    monkeypatch.setattr(win, "notify", lambda msg, **_k: said.append(msg))
    win.proposals_tab.start()
    win.proposals_tab.start()
    assert len(fake_engine.calls) == 1
    assert said == ["Generowanie już trwa."]


def test_cancel_keeps_finished_proposals(win, fake_engine):
    pt = win.proposals_tab
    pt.start()
    gen = fake_engine.gen
    gen.finish(2)
    gen.state = "running"  # dwie gotowe, liczenie trwa
    pt.cancel_btn.click()
    assert gen.cancelled
    pt._tick()
    assert not pt.running
    assert len(pt.proposals) == 2
    assert "(przerwano)" in pt.status.text()


def test_engine_failure_is_shown_in_tab(win, fake_engine):
    pt = win.proposals_tab
    pt.start()
    gen = fake_engine.gen
    gen.state, gen.error = "failed", "panika w funkcji celu <x>"
    pt._tick()
    assert not pt.running and not pt._timer.isActive()
    assert "Błąd silnika" in pt.status.text()
    assert "&lt;x&gt;" in pt.status.text()
    assert pt.gen_all.isEnabled()


def test_engine_refusing_session_is_shown_in_tab(win, fake_engine):
    fake_engine.fail_start = "slots[2]: zła zasada"
    pt = win.proposals_tab
    pt.start()
    assert not pt.running
    assert "zła zasada" in pt.status.text()


def test_generate_only_selected(win, fake_engine):
    sid = select(win, 4)
    pt = win.proposals_tab
    pt._gen_one()
    assert fake_engine.calls == [{sid}]
    fake_engine.gen.finish(2)
    pt._tick()
    assert all(p.slot_ids == (sid,) for p in pt.proposals)


def test_take_whole_and_single_color(win, fake_engine):
    n = len(win.history)
    pt = win.proposals_tab
    pt.start()
    fake_engine.gen.finish(3)
    pt._tick()
    pt.table.setCurrentCell(0, 0)
    pt.take_whole()
    p = pt.proposals[0]
    assert all(win.session.slots[i].value == p.values[s.id] for i, s in enumerate(pt.base.slots))
    assert len(win.history) == n + 1
    pt.table.setCurrentCell(1, 0)
    pt.detail.setCurrentCell(3, 0)
    pt.take_color()
    assert win.session.slots[3].value == pt.proposals[1].values[win.session.slots[3].id]
    assert win.session.slots[4].value == p.values[win.session.slots[4].id]


def test_take_after_palette_structure_changed(win, fake_engine, monkeypatch):
    """Review Focus 4: kolor usunięty albo dodany między generowaniem a przejęciem."""
    pt = win.proposals_tab
    pt.start()
    fake_engine.gen.finish(2)
    pt._tick()
    gone = win.session.slots[5].id
    win.set_session(remove_slot(win.session, gone), structural=True)
    win.set_session(add_accent(win.session), structural=True)
    new = win.session.slots[-1]
    said = []
    monkeypatch.setattr(win, "notify", lambda msg, **_k: said.append(msg))
    pt.table.setCurrentCell(1, 0)  # odświeża szczegóły na zmienionej palecie
    pt.take_whole()
    p = pt.proposals[1]
    ids = [s.id for s in win.session.slots]
    assert gone not in ids and len(ids) == 10
    assert all(s.value == p.values[s.id] for s in win.session.slots if s.id in p.values)
    assert win.session.slots[-1].value == new.value  # koloru, którego propozycja nie zna, nie rusza
    assert "pominięto 1" in said[-1]
    row = [s.id for s in pt.base.slots].index(gone)
    pt.detail.setCurrentCell(row, 0)
    pt.take_color()
    assert said[-1] == "Tego koloru już nie ma w palecie."


def test_closing_window_cancels_generation_and_autosaves(qtbot, fake_engine):
    w = MainWindow(fresh_session(), autosave=True)
    qtbot.addWidget(w)
    w.palette_tab.table.setCurrentCell(2, 1)
    w.palette_tab.toggle_lock()
    w.generate()
    gen = fake_engine.gen
    assert w.proposals_tab.running and w._autosave_pending
    started = time.monotonic()
    w.close()
    assert time.monotonic() - started < 1.0
    assert gen.cancelled
    assert not w.proposals_tab.running and not w.proposals_tab._timer.isActive()
    assert aio.load_session(aio.autosave_path()).slots[2].locked


@needs_generate
def test_real_engine_generates_and_window_takes(win, qtbot):
    pt = win.proposals_tab
    win.generate()
    qtbot.waitUntil(lambda: not pt.running, timeout=60_000)
    assert pt.proposals and pt.table.rowCount() == len(pt.proposals)
    pt.table.setCurrentCell(0, 0)
    pt.take_whole()
    p = pt.proposals[0]
    assert all(win.session.slots[i].value == p.values[s.id] for i, s in enumerate(pt.base.slots))


# --- Analiza ---------------------------------------------------------------------------------


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


def test_hue_segments_cut_exclusions_out_of_the_arc():
    assert hue_segments(HueArc(0.0, 270.0)) == ([(0.0, 270.0)], [])
    allowed, banned = hue_segments(HueArc(0.0, 270.0, ((60.0, 85.0), (140.0, 155.0))))
    assert allowed == [(0.0, 60.0), (85.0, 55.0), (155.0, 115.0)]
    assert banned == [(60.0, 25.0), (140.0, 15.0)]
    # łuk i zakaz przez 0°
    allowed, banned = hue_segments(HueArc(330.0, 30.0, ((350.0, 10.0),)))
    assert allowed == [(330.0, 20.0), (10.0, 20.0)]
    assert banned == [(350.0, 20.0)]
    # pełne koło; zakaz wystający poza łuk jest przycinany do łuku
    assert hue_segments(HueArc(0.0, 360.0, ((350.0, 10.0),))) == (
        [(10.0, 340.0)],
        [(0.0, 10.0), (350.0, 10.0)],
    )
    assert hue_segments(HueArc(0.0, 60.0, ((50.0, 90.0),))) == ([(0.0, 50.0)], [(50.0, 10.0)])
    # zakazy pokrywające cały łuk: nic dozwolonego
    assert hue_segments(HueArc(10.0, 50.0, ((0.0, 60.0),))) == ([], [(10.0, 40.0)])


def test_analysis_wheel_draws_rule_arc_and_scheme_target(win, monkeypatch):
    sid = select(win, 3)
    s = win.session
    rule = Rule(HueArc(0.0, 270.0, exclude=((60.0, 85.0),)))
    plain = win.session
    marked = with_slot(s, replace(s.slots[3], rules=replace(s.slots[3].rules, hue=rule)))
    monkeypatch.setattr(analysis_tab.engine, "hue_targets", lambda _s: {sid: 135.0})
    win.tabs.setCurrentWidget(win.analysis_tab)
    wheel = win.analysis_tab.wheel
    assert wheel.targets == {sid: 135.0}  # cele układu przychodzą z silnika
    with_target = wheel.grab().toImage()
    monkeypatch.setattr(analysis_tab.engine, "hue_targets", lambda _s: {})
    win.analysis_tab.redraw()
    without = wheel.grab().toImage()
    assert with_target != without
    win.set_session(marked, structural=True)
    assert wheel.grab().toImage() != without  # łuk zasady z zakazem
    assert win.session != plain


# --- pliki, schowek, start -------------------------------------------------------------------


def test_save_open_roundtrip(win, tmp_path):
    p = tmp_path / "x.json"
    assert win.save_to(p)
    assert win.file_path == p and "x.json" in win.windowTitle()
    assert '"algopalette.v2"' in p.read_text(encoding="utf-8")
    other = MainWindow(fresh_session(), autosave=False)
    assert other.open_path(p)
    assert other.session == win.session
    assert other.migration_notes == ()


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


def test_fresh_session_is_neutral_preset():
    s = fresh_session()
    assert s.preset == "neutralny"
    assert s.slots[2].rules == default_rules("accent", "dark", "wcag21")
    assert s.slots[2].value == OKLCH(0.78, 0.12, 25.0)


def test_path_type_is_path(win, tmp_path):
    p = tmp_path / "y.json"
    win.save_to(p)
    assert isinstance(win.file_path, Path)
