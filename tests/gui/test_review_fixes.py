"""Regresje z przeglądu całości (2026-11-15): motyw na żywo, tryb Shift+F1, panel Pomocy, treść."""

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QGroupBox, QLabel, QToolTip, QVBoxLayout, QWidget

from algopalette.color import contrast_hex
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


# I1
def test_mark_text_none_clears_color(qtbot):
    lbl = QLabel("x")
    qtbot.addWidget(lbl)
    theme.mark_text(lbl, "hard", bold=True)
    assert lbl.styleSheet()
    theme.mark_text(lbl, None)
    assert lbl.styleSheet() == ""
    theme.style_badge(lbl, "mood")
    theme.style_badge(lbl, None)
    assert lbl.styleSheet() == ""


def test_source_result_not_red_after_error(win):
    tab = win.source_tab
    tab.paste.setPlainText("#zzz")
    assert not tab.parse()
    tab.paste.setPlainText("#101010 #eeeeee #ff0000")
    assert tab.parse()
    assert tab.result.styleSheet() == ""


# I2
def test_click_mode_blocks_shortcuts(win, qtbot):
    qtbot.waitExposed(win)
    win.activateWindow()
    n, view, tab = len(win.session.slots), win.session.view_model, win.tabs.currentIndex()
    win.palette_tab.table.setFocus()
    win.help.enter_click_mode()
    for key, mod in (
        (Qt.Key.Key_F7, Qt.KeyboardModifier.NoModifier),
        (Qt.Key.Key_Insert, Qt.KeyboardModifier.NoModifier),
        (Qt.Key.Key_F3, Qt.KeyboardModifier.NoModifier),
        (Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier),
    ):
        qtbot.keyClick(QApplication.focusWidget() or win, key, mod)
    assert len(win.session.slots) == n
    assert win.session.view_model == view
    assert win.tabs.currentIndex() == tab
    assert not win.proposals_tab.running
    assert win.help.click_mode
    qtbot.keyClick(QApplication.focusWidget() or win, Qt.Key.Key_Escape)
    assert not win.help.click_mode
    qtbot.keyClick(QApplication.focusWidget() or win, Qt.Key.Key_F7)  # po wyjściu skróty działają
    assert win.session.view_model != view


# I3a
def test_hex_column_follows_theme(win, qtbot, qapp):
    t = win.palette_tab.table
    theme.apply(qapp, "dark")
    flush(qtbot)
    it = t.item(1, 3)
    assert it is not None and it.data(Qt.ItemDataRole.ForegroundRole) is None


# I3b
def test_proposal_state_recolored(win, qapp, fake_engine):
    tab = win.proposals_tab
    tab.start()
    fake_engine.gen.finish(2, hard=True)
    tab._tick()
    assert tab.table.item(0, 1).foreground().color().name() == theme.LIGHT.hard
    theme.apply(qapp, "dark")
    assert tab.table.item(0, 1).foreground().color().name() == theme.DARK.hard
    assert tab.table.item(1, 1).foreground().color().name() == theme.DARK.ok


def test_engine_error_recolored(win, qapp):
    tab = win.proposals_tab
    tab._failed("<b>zły</b>")
    assert "&lt;b&gt;" in tab.status.text()
    theme.apply(qapp, "dark")
    assert theme.DARK.hard in tab.status.text()


# I3c
def test_help_links_rerendered_on_theme(win, qapp):
    p = win.help.panel
    p.show_topic("general.start")
    theme.apply(qapp, "dark")
    html = p.text.toHtml()
    assert "#0000ff" not in html.lower()
    assert p.current_key == "general.start"


# I3d
def test_tooltip_palette_follows_theme(qapp):
    theme.apply(qapp, "dark")
    pal = QToolTip.palette()
    assert pal.toolTipBase().color().name() == theme.dark_palette().toolTipBase().color().name()


# M1
def test_search_then_reopen_same_topic(win):
    p = win.help.panel
    p.show_topic("concept.gamut")
    p.query.setText("kontrast")
    assert p.current_key is None
    p.show_topic("concept.gamut")
    assert p.current_key == "concept.gamut"
    assert "Gamut" in p.text.toPlainText()
    p.query.setText("kontrast")
    p.query.clear()
    assert p.current_key == "concept.gamut"  # wraca do tematu sprzed wyszukiwania


# M2
def test_group_click_toggles_once(win):
    p = win.help.panel
    g = p.tree.topLevelItem(0)
    assert g is not None
    before = g.isExpanded()
    p.tree.itemClicked.emit(g, 0)
    p.tree.itemActivated.emit(g, 0)  # KDE: pojedynczy klik = klik + aktywacja
    assert g.isExpanded() != before


# M3
def test_help_menu_has_no_cursor_dependent_item(win):
    assert win.help.act_help not in win.help.actions()
    win.help.act_info.trigger()
    assert win.help.panel.current_key == "general.help"


# M6
def test_dark_highlight_contrast():
    pal = theme.dark_palette()
    hl, txt = pal.highlight().color().name(), pal.highlightedText().color().name()
    assert contrast_hex(txt, hl, "wcag21") >= 4.5


# M7
def test_uncovered_checks_groupbox_tabs_and_toolbar(qtbot, win):
    box = QWidget()
    lay = QVBoxLayout(box)
    gb = QGroupBox("sekcja")
    lay.addWidget(gb)
    qtbot.addWidget(box)
    assert any("QGroupBox" in r for r in gh.uncovered(box))
    gh.attach(gb, "general.start")
    assert gh.uncovered(box) == []
    # pasek narzędzi: przycisk akcji bez klucza zostaje zgłoszony
    a = win.toolbar.addAction("bez opisu")
    assert any("QToolButton" in r for r in gh.uncovered(win))
    win.toolbar.removeAction(a)


# C1, I4, I5
def test_content_matches_engine():
    start = TOPICS["general.start"].body
    assert "polaryzacj" in start and "nastrój" in start
    assert "nie zmienia" in TOPICS["globals.mood"].body
    assert "niewielkie" not in TOPICS["cond.weight"].short
    assert "CAŁE" in TOPICS["globals.opt.time_cap"].short
