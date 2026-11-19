"""Ramka „Układ odcieni”: koło zawsze, generatory jednorazowe, obrót listy, liczniki ×N."""

from dataclasses import replace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from algopalette.gui.app import MainWindow
from algopalette.gui.picker import ListPicker
from algopalette.gui.widgets import ValueSlider
from algopalette.model import OKLCH, HueScheme, Session, with_slot


def settle(win: MainWindow) -> None:
    win.rules_tab.flush()
    QCoreApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def palette_page(win: MainWindow) -> ListPicker:
    win.show_rules([])
    settle(win)
    picker = win.rules_tab.custom_picker
    assert isinstance(picker, ListPicker)
    return picker


def with_hues(win: MainWindow, hues: tuple[float, ...]) -> None:
    s = win.session
    win.set_session(replace(s, globals=replace(s.globals, hue_scheme=HueScheme(hues=hues))))
    settle(win)


def hues(win: MainWindow) -> tuple[float, ...]:
    return win.session.globals.hue_scheme.hues


def test_wheel_always_present_without_kind_combo(win):
    with_hues(win, ())
    palette_page(win)
    w = win.rules_tab.palette_widgets
    assert "hues.kind" not in w and "hues.rotate" in w
    assert set(win.rules_tab.gen_buttons) == {
        "mono",
        "analogous",
        "complementary",
        "split",
        "triad",
        "square",
        "rectangle",
        "equal",
        "current",
    }


def test_triad_from_selected_point_is_one_undo_step(win):
    with_hues(win, (10.0, 40.0))
    picker = palette_page(win)
    before = hues(win)
    picker.select(1)
    win.rules_tab.gen_buttons["triad"].click()
    assert hues(win) == pytest.approx((40, 160, 280))
    assert picker.items() == pytest.approx((40, 160, 280))
    win.action_undo()
    assert hues(win) == before


def test_mono_on_empty_list_uses_25(win):
    with_hues(win, ())
    palette_page(win)
    win.rules_tab.gen_buttons["mono"].click()
    assert hues(win) == pytest.approx((25,))


def test_analogous_and_equal_ask_for_parameters(win):
    with_hues(win, (100.0,))
    palette_page(win)
    tab = win.rules_tab
    asked: list[tuple[str, int]] = []

    def ask(_parent, key, n_accents):
        asked.append((key, n_accents))
        return {"n": 5, "spread": 40.0} if key == "analogous" else {"n": 4}

    tab.ask_layout = ask
    tab.gen_buttons["analogous"].click()
    assert hues(win) == pytest.approx((80, 90, 100, 110, 120))
    tab.gen_buttons["equal"].click()
    assert hues(win) == pytest.approx((80, 170, 260, 350))
    assert asked == [("analogous", 8), ("equal", 8)]
    tab.ask_layout = lambda *_a: None  # anulowanie nic nie zmienia
    tab.gen_buttons["equal"].click()
    assert hues(win) == pytest.approx((80, 170, 260, 350))


def grey_accents(s: Session) -> Session:
    for sl in s.slots[2:]:
        s = with_slot(s, replace(sl, value=OKLCH(0.7, 0.0, 0.0)))
    return s


def test_current_colors_without_hue_keeps_list_and_notifies(win):
    with_hues(win, (10.0, 200.0))
    win.set_session(grey_accents(win.session))
    palette_page(win)
    seen: list[tuple[str, bool]] = []
    win.notify = lambda msg, error=False, **_kw: seen.append((msg, error))
    win.rules_tab.gen_buttons["current"].click()
    assert hues(win) == (10.0, 200.0)
    assert seen and "szare" in seen[0][0]


def test_current_colors_in_accent_order(win):
    s = win.session
    for sl, h in zip(s.slots[2:5], (300.0, 30.0, 150.0), strict=True):
        s = with_slot(s, replace(sl, value=OKLCH(0.7, 0.12, h)))
    for sl in s.slots[5:]:
        s = with_slot(s, replace(sl, value=OKLCH(0.7, 0.0, 0.0)))
    win.set_session(s)
    palette_page(win)
    win.rules_tab.gen_buttons["current"].click()
    assert hues(win) == pytest.approx((300, 30, 150))


def test_rotate_all_is_relative_and_one_undo_step(win):
    with_hues(win, (30.0, 150.0, 270.0))
    picker = palette_page(win)
    rot = win.rules_tab.palette_widgets["hues.rotate"]
    assert isinstance(rot, ValueSlider)
    before = hues(win)
    rot.bar.moved.emit(0, 10.0)
    rot.bar.moved.emit(0, 30.0)
    assert hues(win) == pytest.approx((60, 180, 300))
    assert picker.items() == pytest.approx((60, 180, 300))
    win.action_undo()
    assert hues(win) == before


def test_counts_follow_accents_and_use_scheme(win):
    with_hues(win, (10.0, 130.0, 250.0))
    picker = palette_page(win)
    assert picker.counts == (3, 3, 2)
    s = win.session
    win.set_session(with_slot(s, replace(s.slots[3], use_scheme=False)))  # akcent 2 → pozycja 1
    settle(win)
    assert win.rules_tab.custom_picker is not None
    assert win.rules_tab.custom_picker.counts == (3, 2, 2)


def test_long_list_rows_beyond_accents_are_zero(win):
    with_hues(win, tuple(float(20 * i) for i in range(14)))
    picker = palette_page(win)
    assert picker.counts == (1,) * 8 + (0,) * 6
    assert not picker.rows[10].count.isEnabled()
    assert picker.rows[0].count.text() == "×1"


def test_empty_list_rule_row_says_no_targets(win):
    with_hues(win, ())
    win.show_rules([win.session.slots[2].id])
    settle(win)
    row = win.rules_tab.scheme_row
    assert row is not None
    assert "pusty" in row.target.text()
