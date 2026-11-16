"""Pomoc na zakładkach Propozycje i Źródło — przed i po wynikach / odczycie."""

from PySide6.QtCore import QCoreApplication, QEvent

from algopalette.gui import help as gh


def flush(qtbot) -> None:
    qtbot.wait(5)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _check(root) -> None:
    rep = gh.uncovered(root)
    assert rep == [], "\n".join(rep)


def test_proposals_covered_before_and_after(win, qtbot, fake_engine):
    tab = win.proposals_tab
    _check(tab)
    win.tabs.setCurrentWidget(tab)
    tab.start()
    _check(tab)  # w trakcie generowania (pasek postępu, „Przerwij”)
    fake_engine.gen.finish(3, hard=True)
    tab._tick()
    flush(qtbot)
    assert tab.proposals
    _check(tab)
    strip = tab.table.cellWidget(0, 4)
    assert gh.key_of(strip) == "proposals.col.strip"
    tab.take_whole()
    flush(qtbot)
    _check(tab)


def test_source_covered_ok_and_error(win, qtbot):
    tab = win.source_tab
    _check(tab)
    tab.paste.setPlainText("#1e1e2e #cdd6f4 #f38ba8 oklch(0.8 0.1 140)")
    assert tab.parse()
    flush(qtbot)
    _check(tab)
    tips = [w.toolTip() for w in tab.swatches.findChildren(gh.QWidget) if gh.key_of(w)]
    assert any("#f38ba8" in t and "F1 — więcej" in t for t in tips)
    tab.paste.setPlainText("#zzz nie-kolor")
    assert not tab.parse()
    flush(qtbot)
    _check(tab)
