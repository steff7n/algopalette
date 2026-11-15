"""Pomoc na zakładce Paleta: każda kontrolka listy, edytora, warunków i zależności ma opis."""

from dataclasses import replace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from algopalette.forms import DISPLAY_ORDER, default_for
from algopalette.gui import help as gh
from algopalette.gui.conditions import ConditionRow
from algopalette.gui.help_content import TOPICS
from algopalette.gui.relations import RelationRow
from algopalette.model import Cond, ContrastBound, Relation, with_slot


def flush(qtbot) -> None:
    qtbot.wait(5)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def select(win, row: int, qtbot) -> None:
    win.palette_tab.table.setCurrentCell(row, 1)
    flush(qtbot)


def _rich_session(win):
    """Akcent 2: wszystkie 8 warunków (w tym kontrast z własną metryką) i zależności każdego
    typu + jedna zerwana."""
    s = win.session
    slot = s.slots[2]
    conds = {f: Cond(default_for(f, s)) for f in DISPLAY_ORDER}
    conds["contrast_bg"] = Cond(ContrastBound("apca", 60.0, None))
    sc = replace(slot.conditions, **conds)
    a, b = s.slots[3].id, s.slots[4].id
    rels = (
        Relation("hue", a, "eq", 180.0, tol=15.0),
        Relation("lightness", a, "le", -0.1),
        Relation("chroma", a, "ge", 1.0, chroma_op="mul", chroma_mode="rel"),
        Relation("contrast", s.slots[0].id, "ge", 4.5, metric="wcag21"),
        Relation("distance", b, "ge", 0.03, metric="ok"),
        Relation("mix", a, "eq", 0.0, tol=0.02, other=b, t=0.5),
        Relation("hue", "nie-ma-takiego", "eq", 30.0, tol=10.0),  # zerwana
    )
    return with_slot(s, replace(slot, conditions=sc, relations=rels))


def _check(win, qtbot) -> None:
    flush(qtbot)
    rep = gh.uncovered(win.palette_tab)
    assert rep == [], "\n".join(rep)


def test_slot_actions_have_keys(win):
    for a in win.palette_tab.slot_actions():
        assert gh.key_of(a) in TOPICS, a.text()


@pytest.mark.parametrize("view", ["oklch", "hsl"])
def test_palette_covered_each_role_and_view(win, qtbot, view):
    win.set_view_model(view)
    for row in (0, 1, 2):
        select(win, row, qtbot)
        _check(win, qtbot)


def test_conditions_each_field_covered(win, qtbot):
    win.set_session(_rich_session(win), structural=True)
    select(win, 2, qtbot)
    fields = {r.field for r in win.palette_tab.editor.findChildren(ConditionRow)}
    assert fields == set(DISPLAY_ORDER)
    for r in win.palette_tab.editor.findChildren(ConditionRow):
        assert r.cond is not None and gh.key_of(r) == f"cond.{r.field}"
    _check(win, qtbot)
    win.set_view_model("hsl")
    flush(qtbot)
    _check(win, qtbot)


def test_conditions_missing_rows_covered(win, qtbot):
    """Rola tła: wiersze „brak warunku / + dodaj”."""
    select(win, 0, qtbot)
    rows = win.palette_tab.editor.findChildren(ConditionRow)
    assert any(r.cond is None for r in rows)
    _check(win, qtbot)


def test_relations_each_kind_covered(win, qtbot):
    win.set_session(_rich_session(win), structural=True)
    select(win, 2, qtbot)
    rows = win.palette_tab.editor.findChildren(RelationRow)
    assert {r.rel.kind for r in rows} == {
        "hue",
        "lightness",
        "chroma",
        "contrast",
        "distance",
        "mix",
    }
    assert any(r.broken for r in rows)
    for r in rows:
        assert gh.key_of(r) == f"rel.{r.rel.kind}"
    _check(win, qtbot)


def test_palette_covered_after_undo_redo_add(win, qtbot):
    select(win, 2, qtbot)
    win.palette_tab.add_accent()
    _check(win, qtbot)
    win.action_undo()
    _check(win, qtbot)
    win.action_redo()
    _check(win, qtbot)
    win.toggle_view()
    _check(win, qtbot)


def test_swatch_tooltip_keeps_help_and_hex(win, qtbot):
    select(win, 1, qtbot)
    sw = win.palette_tab.editor.swatch
    tip = sw.toolTip()
    assert "F1 — więcej" in tip and sw.hex in tip


def test_cond_topics_explain_engine():
    for f in DISPLAY_ORDER:
        t = TOPICS[f"cond.{f}"]
        assert len(t.body) > 150, f
    assert "granic" in TOPICS["cond.lightness"].body  # twardy zakres = granica poszukiwań
    assert "help:concept.sources" in TOPICS["cond.overview"].body
