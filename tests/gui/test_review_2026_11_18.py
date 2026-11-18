"""Regresje z przeglądu całości 2026-11-18 (raport: `.superpowers/sdd/2026-11-18-*`)."""

from dataclasses import replace

from algopalette import io as aio
from algopalette.color import to_hsl
from algopalette.engine import Violation
from algopalette.gui.app import rule_owners
from algopalette.model import OKLCH, with_slot


def _edited(win):
    s = win.session
    a = s.slots[2]
    win.set_session(with_slot(s, replace(a, value=OKLCH(0.7, 0.1, a.value.h + 3.0))))


# C2
def test_undo_past_open_restores_previous_file_path(win, tmp_path):
    other = tmp_path / "b.json"
    s = win.session
    aio.save_session(replace(s, slots=s.slots[:-1]), other)
    before = other.read_text("utf-8")
    assert win.file_path is None
    assert win.open_path(other)
    assert win.file_path == other
    win.action_undo()
    assert win.file_path is None  # cofnięcie poza „Wczytaj” — sesja nie należy do b.json
    assert "nowa paleta" in win.windowTitle()
    win.action_redo()
    assert win.file_path == other
    win.action_undo()
    _edited(win)
    assert win.file_path is None
    assert other.read_text("utf-8") == before


def test_save_as_moves_whole_document_but_not_earlier_file(win, tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    aio.save_session(win.session, a)
    win.open_path(a)
    _edited(win)
    assert win.file_path == a
    assert win.save_to(b)
    win.action_undo()  # stan przed edycją — ten sam dokument, już pod b.json
    assert win.file_path == b
    win.action_undo()  # przed wczytaniem a.json
    assert win.file_path is None


# I5
def test_undo_with_other_view_keeps_redo(win):
    for _ in range(3):
        _edited(win)
    win.set_view_model("hsl")
    win.action_undo()
    assert win.session.view_model == "hsl"
    assert win.history.can_redo
    win.action_redo()
    assert win.session.view_model == "hsl"


# M9
def test_replace_with_same_session_adds_no_undo_step(win):
    n = len(win.history)
    win.replace_session(win.session)
    assert len(win.history) == n


# M5
def test_avoid_violation_belongs_to_whole_palette():
    v = Violation("global:avoid:x:0", ("x",), "avoid", True, 0.1, 0.0, {}, {})
    assert rule_owners(v) == ()


# M6
def test_hsl_edit_of_gray_keeps_hue(win):
    s = win.session
    gray = replace(s.slots[2], value=OKLCH(0.6, 0.0, 0.0), locked=False)
    win.replace_session(with_slot(s, gray))
    win.set_view_model("hsl")
    win.palette_tab.table.setCurrentCell(2, 1)
    sliders = win.palette_tab.editor.value_sliders
    for key, text in (("hsl-h", "200"), ("hsl-s", "60")):
        e = sliders[key].edit
        e.setText(text)
        e.editingFinished.emit()
    h, sat, _ = to_hsl(win.session.slots[2].value, win.session.globals.fit_method)
    assert abs(h - 200.0) < 1.0 and abs(sat - 60.0) < 1.0


# I1
def test_engine_rejection_is_shown_in_panel_not_as_ok(win):
    s = win.session
    o = replace(s.globals.optimizer, seed=2**70)
    win.set_session(replace(s, globals=replace(s.globals, optimizer=o)))
    title = win.violations_panel.title.text()
    assert "Silnik nie przyjął zasad" in title and "✓" not in title
    win.action_undo()
    assert "Silnik nie przyjął" not in win.violations_panel.title.text()


def test_generation_fields_have_upper_bounds(win, tmp_path):
    from algopalette.gui.widgets import NumEdit

    win.tabs.setCurrentWidget(win.rules_tab)
    win.rules_tab.strip.select_palette()
    win.rules_tab.flush()
    seed = win.rules_tab.palette_widgets["gen.seed"]
    assert isinstance(seed, NumEdit)
    seed.setText(str(2**64))
    seed.editingFinished.emit()
    assert win.session.globals.optimizer.seed == 0
    seed.setText(str(2**64 - 1))
    seed.editingFinished.emit()
    assert win.session.globals.optimizer.seed == 2**64 - 1  # dokładnie, bez float
    p = tmp_path / "s.json"
    aio.save_session(win.session, p)
    assert aio.load_session(p).globals.optimizer.seed == 2**64 - 1
