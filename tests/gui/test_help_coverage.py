"""Pokrycie pomocą całego okna (bez wyłączeń) i osiągalność każdego tematu."""

import re

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QMenu, QWidget

from algopalette.gui import help as gh
from algopalette.gui import theme
from algopalette.gui.help_content import TOPICS


@pytest.fixture(autouse=True)
def _light_after(qapp):
    yield
    theme.apply(qapp, "light")


def flush(qtbot) -> None:
    qtbot.wait(5)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_whole_window_covered(win, qtbot, qapp, mode):
    theme.apply(qapp, mode)
    for view in ("oklch", "hsl"):
        win.set_view_model(view)
        for i in range(win.tabs.count()):
            win.tabs.setCurrentIndex(i)
            if win.tabs.currentWidget() is win.palette_tab:
                for row in (0, 1, 2):
                    win.palette_tab.table.setCurrentCell(row, 1)
                    flush(qtbot)
                    rep = gh.uncovered(win)
                    assert rep == [], "\n".join(rep)
            flush(qtbot)
            rep = gh.uncovered(win)
            assert rep == [], "\n".join(rep)


def _used_keys(win) -> set[str]:
    used: set[str] = set()
    objs = [*win.findChildren(QWidget)]
    for m in win.findChildren(QMenu):
        objs += [a for a in m.actions()]
        objs.append(m.menuAction())
    objs += list(win.actions()) + list(win.palette_tab.slot_actions())
    for o in objs:
        k = gh.key_of(o)
        if k:
            used.add(k)
        for prop in (gh.COLUMNS_PROP, gh.ROWS_PROP):
            v = o.property(prop) if isinstance(o, QWidget) else None
            if isinstance(v, str):
                used.add(v)
            elif isinstance(v, list):
                used |= {x for x in v if isinstance(x, str)}
    for bar in (win.tabs.tabBar(), win.globals_tab.role_tabs.tabBar()):
        used |= {bar.tabData(i) for i in range(bar.count()) if isinstance(bar.tabData(i), str)}
    return used


def test_every_topic_reachable(win, qtbot):
    # zbuduj wszystkie zakładki i stany z elementami pojawiającymi się dynamicznie
    for i in range(win.tabs.count()):
        win.tabs.setCurrentIndex(i)
        flush(qtbot)
    win.proposals_tab.start()
    qtbot.waitUntil(lambda: not win.proposals_tab.running, timeout=30000)
    win.source_tab.paste.setPlainText("#101010 #eeeeee #ff0000")
    win.source_tab.parse()
    flush(qtbot)
    used = _used_keys(win)
    linked = {t for topic in TOPICS.values() for t in re.findall(r"\(help:([^)\s]+)\)", topic.body)}
    unreachable = sorted(set(TOPICS) - used - linked)
    assert unreachable == [], unreachable
