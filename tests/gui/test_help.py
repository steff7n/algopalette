import re

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt, QUrl
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QPushButton,
    QStyle,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from algopalette.gui import help as gh
from algopalette.gui.help_content import GROUPS, TOPICS
from algopalette.gui.widgets import ValueSlider

LINK = re.compile(r"\(help:([^)\s]+)\)")


def test_topics_wellformed():
    for key, t in TOPICS.items():
        assert re.fullmatch(r"[a-z_]+(\.[a-z0-9_]+)+", key), key
        assert 0 < len(t.short) <= 200, key
        assert t.title.strip() and t.body.strip(), key
        assert t.group in GROUPS, key
        assert t.short.strip().casefold() != t.title.strip().casefold(), key
        for target in LINK.findall(t.body):
            assert target in TOPICS, (key, target)


def test_general_and_concept_topics_present():
    for k in (
        "general.start",
        "general.shortcuts",
        "general.help",
        "concept.oklch",
        "concept.delta_e",
        "concept.contrast",
        "concept.cvd",
        "concept.gamut",
        "concept.hard_soft",
        "concept.chroma_modes",
    ):
        assert k in TOPICS
    for k, t in TOPICS.items():
        if k.startswith("concept."):
            # pojęcia krótko (decyzja użytkownika); tematy wg wzorca terminu mają przykład z
            # liczbami, więc dostają więcej miejsca
            assert len(t.body.split()) <= (330 if t.term else 140), k


def test_attach_unknown_key_raises(qapp):
    with pytest.raises(KeyError):
        gh.attach(QPushButton(), "nie.ma")


def test_tooltip_html():
    tip = gh.tooltip_html("concept.gamut")
    t = TOPICS["concept.gamut"]
    assert t.title in tip and "F1 — więcej" in tip
    assert gh.tooltip_html("concept.gamut", extra="#ff0000").count("#ff0000") == 1


def test_key_at_walks_ancestors(qtbot):
    box = QWidget()
    lay = QVBoxLayout(box)
    lbl = QLabel("bez klucza")
    lay.addWidget(lbl)
    qtbot.addWidget(box)
    gh.attach(box, "general.start")
    box.show()
    qtbot.waitExposed(box)
    pos = lbl.mapToGlobal(lbl.rect().center())
    assert gh.key_at(pos) == "general.start"


def test_attach_children_and_uncovered(qtbot):
    box = QWidget()
    lay = QVBoxLayout(box)
    btn, lbl, deco = QPushButton("guzik"), QLabel("opis"), QLabel("ozdoba")
    slider = ValueSlider(0.5, minimum=0.0, maximum=1.0, step=0.01)
    for w in (btn, lbl, deco, slider):
        lay.addWidget(w)
    qtbot.addWidget(box)
    gh.decorative(deco)
    gh.attach(slider, "concept.oklch", children=True)
    rep = gh.uncovered(box)
    assert len(rep) == 2 and any("guzik" in r for r in rep) and any("opis" in r for r in rep)
    gh.attach(btn, "general.start")
    gh.attach(lbl, "general.start")
    assert gh.uncovered(box) == []


def test_uncovered_requires_header_columns(qtbot):
    t = QTableWidget(2, 3)
    qtbot.addWidget(t)
    gh.attach(t, "general.start")
    assert len(gh.uncovered(t)) == 3
    gh.attach_header(t, ["concept.oklch", "concept.gamut", None])
    assert len(gh.uncovered(t)) == 1
    gh.attach_header(t, "concept.oklch")
    assert gh.uncovered(t) == []


def test_key_at_tab_and_header(win, qtbot):
    gh.attach_tab(win.tabs, 1, "concept.cvd")
    bar = win.tabs.tabBar()
    qtbot.waitExposed(win)
    assert gh.key_at(bar.mapToGlobal(bar.tabRect(1).center())) == "concept.cvd"
    table = win.violations_panel.table
    gh.attach_header(table, ["concept.hard_soft", "concept.oklch", None, None])
    h = table.horizontalHeader()
    x = h.sectionViewportPosition(1) + h.sectionSize(1) // 2
    pt = h.viewport().mapToGlobal(QPoint(x, h.height() // 2))
    assert gh.key_at(pt) == "concept.oklch"


def _focus_key_widget(win):
    btn = QPushButton("x", win.violations_panel)
    gh.attach(btn, "concept.delta_e")
    btn.show()
    btn.setFocus()
    QApplication.processEvents()
    return btn


def test_f1_opens_and_toggles(win, qtbot, monkeypatch):
    monkeypatch.setattr(gh.QCursor, "pos", staticmethod(lambda: QPoint(-10000, -10000)))
    btn = _focus_key_widget(win)
    qtbot.waitUntil(lambda: QApplication.focusWidget() is btn)
    panel = win.help.panel
    assert panel.isHidden()
    win.help.help_here()
    assert not panel.isHidden() and panel.current_key == "concept.delta_e"
    win.help.help_here()
    assert panel.isHidden()
    btn.clearFocus()
    win.setFocus()
    monkeypatch.setattr(gh, "key_for_focus", lambda: None)
    win.help.help_here()
    assert not panel.isHidden() and panel.current_key is None  # spis treści


def test_f1_action_has_application_shortcut(win):
    assert win.help.act_help.shortcut().toString() == "F1"
    assert win.help.act_click.shortcut().toString() == "Shift+F1"
    titles = [a.text() for a in win.help.actions()]
    assert "Pierwsze kroki" in titles and "Skróty klawiszowe" in titles


def test_search_diacritics():
    assert any("jasność" in (TOPICS[k].body + TOPICS[k].title) for k in gh.search("jasnosc"))
    hits = gh.search("ZRODLO")
    assert hits and all(
        "zrodlo" in gh.normalize(TOPICS[k].title + TOPICS[k].short + TOPICS[k].body) for k in hits
    )
    hits = gh.search("gamut")
    title_hits = [k for k in hits if "gamut" in TOPICS[k].title.casefold()]
    assert "concept.gamut" in title_hits
    assert hits[: len(title_hits)] == title_hits  # trafienia w tytule pierwsze
    assert gh.search("   ") == []


def test_panel_search_filters_tree(win):
    p = win.help.panel
    p.query.setText("daltonizm")
    visible = []
    for i in range(p.tree.topLevelItemCount()):
        g = p.tree.topLevelItem(i)
        for j in range(g.childCount()):
            ch = g.child(j)
            if not ch.isHidden() and not g.isHidden():
                visible.append(ch.data(0, gh.HELP_ROLE))
    assert "concept.cvd" in visible and "general.shortcuts" not in visible
    p.query.clear()


def test_link_navigates_in_panel(win):
    p = win.help.panel
    p.show_topic("general.start")
    p.text.anchorClicked.emit(QUrl("help:concept.gamut"))
    assert p.current_key == "concept.gamut"
    assert p.back.isEnabled()
    p.go_back()
    assert p.current_key == "general.start"
    p.go_forward()
    assert p.current_key == "concept.gamut"


def test_click_mode_swallows_click(win, qtbot):
    btn = QPushButton("klik", win.violations_panel)
    gh.attach(btn, "concept.contrast")
    btn.show()
    qtbot.waitExposed(btn)
    clicks = []
    btn.clicked.connect(lambda: clicks.append(1))
    win.help.enter_click_mode()
    cur = QApplication.overrideCursor()
    assert cur is not None and cur.shape() == Qt.CursorShape.WhatsThisCursor
    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
    assert clicks == []
    assert win.help.panel.current_key == "concept.contrast"
    assert not win.help.click_mode and QApplication.overrideCursor() is None
    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)  # po wyjściu z trybu klik działa normalnie
    assert clicks == [1]


def test_click_mode_escape(win, qtbot):
    win.help.panel.show_topic("general.help")
    win.help.enter_click_mode()
    qtbot.keyClick(win, Qt.Key.Key_Escape)
    assert not win.help.click_mode
    assert win.help.panel.current_key == "general.help"
    assert QApplication.overrideCursor() is None


def test_f1_in_menu_opens_action_topic(win, qtbot):
    a = win.act_generate
    gh.attach(a, "concept.exclusion")
    menu = next(m for m in win.findChildren(QMenu) if a in m.actions())
    menu.popup(win.mapToGlobal(QPoint(10, 10)))
    qtbot.waitExposed(menu)
    menu.setActiveAction(a)
    qtbot.keyClick(menu, Qt.Key.Key_F1)
    assert win.help.panel.current_key == "concept.exclusion"
    assert not menu.isVisible()


def test_tooltip_delay(qapp):
    gh.install_tooltip_style(qapp)
    hint = QStyle.StyleHint.SH_ToolTip_WakeUpDelay
    assert qapp.style().styleHint(hint) == gh.TOOLTIP_DELAY_MS == 300


def test_deleted_rows_do_not_break_uncovered(win):
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert isinstance(gh.uncovered(win.help.panel), list)
