from PySide6.QtWidgets import QMenu

from algopalette.gui import help as gh
from algopalette.gui.help_content import TOPICS


def _menu_actions(menu: QMenu):
    for a in menu.actions():
        if a.isSeparator():
            continue
        sub = a.menu()
        if isinstance(sub, QMenu):
            yield a
            yield from _menu_actions(sub)
        else:
            yield a


def test_window_actions_and_tabs_covered(win):
    slot_actions = set(map(id, win.palette_tab.slot_actions()))  # zakładka Paleta (osobny test)
    missing = []
    for top in win.menuBar().actions():
        assert gh.key_of(top) in TOPICS, top.text()
        sub = top.menu()
        assert isinstance(sub, QMenu)
        for a in _menu_actions(sub):
            if id(a) not in slot_actions and gh.key_of(a) is None:
                missing.append(a.text())
    for a in win.toolbar.actions():
        if not a.isSeparator() and gh.key_of(a) is None:
            missing.append(a.text())
    assert missing == []
    bar = win.tabs.tabBar()
    for i in range(win.tabs.count()):
        assert bar.tabData(i) in TOPICS
        assert "F1 — więcej" in bar.tabToolTip(i)


def test_window_uncovered_outside_tabs(win):
    assert gh.uncovered(win, skip=[win.tabs]) == []


def test_violations_topic_mentions_marks_and_columns():
    body = TOPICS["window.violations"].body
    for word in ("✗", "~", "wymagane", "jest", "help:concept.hard_soft", "help:concept.gamut"):
        assert word in body


def test_theme_actions_keep_working_with_help(win):
    assert "F1 — więcej" in win.act_theme_dark.toolTip()
    win.act_theme_dark.trigger()
    win.act_theme_light.trigger()
