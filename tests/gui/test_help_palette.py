"""Pomoc na zakładce Paleta: każda kontrolka listy i edytora ma opis."""

import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from algopalette.gui import help as gh
from algopalette.gui.help_content import TOPICS


def flush(qtbot) -> None:
    qtbot.wait(5)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def select(win, row: int, qtbot) -> None:
    win.palette_tab.table.setCurrentCell(row, 1)
    flush(qtbot)


def _check(win, qtbot) -> None:
    flush(qtbot)
    rep = gh.uncovered(win.palette_tab)
    assert rep == [], "\n".join(rep)


def test_slot_actions_have_keys(win):
    for a in win.palette_tab.slot_actions():
        assert gh.key_of(a) in TOPICS, a.text()


@pytest.mark.parametrize("view", ["oklch", "hsl"])
def test_palette_covered_each_role_and_view(win, qtbot, view):
    win.tabs.setCurrentWidget(win.palette_tab)
    win.set_view_model(view)
    for row in (0, 1, 2):
        select(win, row, qtbot)
        _check(win, qtbot)


def test_palette_covered_after_undo_redo_add(win, qtbot):
    win.tabs.setCurrentWidget(win.palette_tab)
    select(win, 2, qtbot)
    win.palette_tab.add_accent()
    _check(win, qtbot)
    win.action_undo()
    _check(win, qtbot)
    win.action_redo()
    _check(win, qtbot)
    win.toggle_view()
    _check(win, qtbot)


def test_rules_link_has_its_own_topic(win, qtbot):
    select(win, 3, qtbot)
    link = win.palette_tab.editor.rules_link
    assert gh.key_of(link) == "rules.palette_link"
    assert "F1 — więcej" in link.toolTip()


def test_swatch_tooltip_keeps_help_and_hex(win, qtbot):
    select(win, 1, qtbot)
    sw = win.palette_tab.editor.swatch
    tip = sw.toolTip()
    assert "F1 — więcej" in tip and sw.hex in tip


def test_palette_topics_point_to_rules_tab():
    assert "help:rules.tab" in TOPICS["palette.editor"].body
    assert "help:rules.palette_link" in TOPICS["palette.list"].body
    assert "help:rules.contrast_bg" in TOPICS["palette.col.contrast"].body
    assert "help:rules.min_distance" in TOPICS["palette.col.de_min"].body
    assert "kopię zasad" in TOPICS["palette.add"].body
