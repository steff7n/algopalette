"""Pomoc na zakładce Globalne: każda kontrolka (w tym warunki ról) ma opis."""

from dataclasses import replace

from PySide6.QtCore import QCoreApplication, QEvent

from algopalette.gui import help as gh
from algopalette.gui.help_content import TOPICS
from algopalette.model import Cond, Interval


def _show(win, qtbot):
    win.tabs.setCurrentWidget(win.globals_tab)
    win.globals_tab.rebuild()
    qtbot.wait(5)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _check(win):
    rep = gh.uncovered(win.globals_tab)
    assert rep == [], "\n".join(rep)


def test_globals_covered(win, qtbot):
    _show(win, qtbot)
    _check(win)


def test_globals_covered_with_and_without_spread(win, qtbot):
    s = win.session
    for sp in (None, Cond(Interval(0.15, None), hard=False)):
        win.set_session(
            replace(s, globals=replace(s.globals, lightness_spread=sp)), structural=True
        )
        _show(win, qtbot)
        _check(win)


def test_globals_role_tabs_covered(win, qtbot):
    _show(win, qtbot)
    tabs = win.globals_tab.role_tabs
    for i in range(tabs.count()):
        assert tabs.tabBar().tabData(i) == "globals.roles"
        tabs.setCurrentIndex(i)
        _check(win)


def test_option_lists_described_in_body():
    from algopalette.forms import CVD, CVD_METHODS, DELTA_E, FITS, SCHEMES
    from algopalette.moods import BUILTIN

    def has(key, words):
        body = TOPICS[key].body
        missing = [w for w in words if w not in body]
        assert missing == [], (key, missing)

    has("globals.mood", list(BUILTIN))
    has("globals.hues", [label.split(" (")[0] for label, _ in SCHEMES])
    has("globals.delta_e", [v for _, v in DELTA_E])
    has("globals.fit", [v for _, v in FITS])
    has("globals.cvd", [label for label, _ in CVD] + [label for label, _ in CVD_METHODS])
