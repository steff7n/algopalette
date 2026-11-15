"""Wybierak listy: odcienie (własna lista układu) i kolory (lista unikanych)."""

import pytest
from PySide6.QtCore import QPoint, Qt

from algopalette.color import from_css, hue_diff
from algopalette.gui.picker import ListPicker
from algopalette.gui.widgets import NumEdit
from algopalette.model import OKLCH


def commit(edit: NumEdit, text: str) -> None:
    edit.setText(text)
    edit.editingFinished.emit()


def make(qtbot, items=(), **kw):
    kw.setdefault("mode", "hue")
    w = ListPicker(items, **kw)
    qtbot.addWidget(w)
    with qtbot.waitActive(w):  # bez aktywnego okna setFocus nie dostarcza FocusIn
        w.show()
        w.activateWindow()
    got = []
    w.changed.connect(got.append)
    return w, got


def click_wheel(qtbot, w, hue: float) -> None:
    qtbot.mouseClick(w.wheel, Qt.MouseButton.LeftButton, pos=w.wheel.point_for(hue).toPoint())


# --- tryb odcieni ----------------------------------------------------------------------------


@pytest.mark.parametrize("hue", [0.0, 37.0, 120.0, 200.0, 315.0])
def test_click_on_wheel_adds_hue_at_end(qtbot, hue):
    w, got = make(qtbot, (10.0,))
    click_wheel(qtbot, w, hue)
    assert len(got) == 1
    items = got[-1]
    assert isinstance(items, tuple)
    assert items[0] == 10.0
    assert abs(hue_diff(items[1], hue)) <= 1.0
    assert items[1] == round(items[1])  # zaokrąglone do 1°
    assert w.items() == items
    assert w.selected == 1


def test_click_near_center_is_ignored(qtbot):
    w, got = make(qtbot)
    qtbot.mouseClick(w.wheel, Qt.MouseButton.LeftButton, pos=w.wheel.rect().center())
    assert got == []


def test_row_field_changes_value(qtbot):
    w, got = make(qtbot, (10.0, 200.0))
    commit(w.rows[1].edit, "222.5")
    assert got == [(10.0, 222.5)]
    commit(w.rows[0].edit, "360")
    assert got[-1] == (0.0, 222.5)  # 360° to ten sam odcień co 0°


def test_remove_by_button_and_delete_key(qtbot):
    w, got = make(qtbot, (10.0, 120.0, 200.0))
    w.rows[1].remove_button.click()
    assert got[-1] == (10.0, 200.0)
    assert len(w.rows) == 2
    w.rows[0].remove_button.setFocus()
    qtbot.keyClick(w.rows[0].remove_button, Qt.Key.Key_Delete)
    assert got[-1] == (200.0,)
    assert w.rows[0].edit.value() == 200.0


def test_reorder_with_alt_arrows(qtbot):
    w, got = make(qtbot, (10.0, 120.0, 200.0))
    w.rows[0].edit.setFocus()
    qtbot.keyClick(w.rows[0].edit, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
    assert got[-1] == (120.0, 10.0, 200.0)
    assert w.selected == 1
    assert w.rows[1].edit.hasFocus()  # fokus idzie za przesuwaną pozycją
    qtbot.keyClick(w.rows[1].edit, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
    assert got[-1] == (120.0, 200.0, 10.0)
    qtbot.keyClick(w.rows[2].edit, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
    assert len(got) == 2  # ostatniej nie da się przesunąć niżej
    qtbot.keyClick(w.rows[2].edit, Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
    assert got[-1] == (120.0, 10.0, 200.0)


def test_reorder_by_dragging_handle(qtbot):
    w, got = make(qtbot, (10.0, 120.0, 200.0))
    handle = w.rows[0].handle
    target = w.rows[2].handle
    pos = handle.mapFromGlobal(target.mapToGlobal(target.rect().center()))
    qtbot.mousePress(handle, Qt.MouseButton.LeftButton, pos=handle.rect().center())
    qtbot.mouseMove(handle, pos)
    qtbot.mouseRelease(handle, Qt.MouseButton.LeftButton, pos=pos)
    assert got[-1] == (120.0, 200.0, 10.0)
    assert w.selected == 2


def test_selected_item_is_marked_and_marker_drag_changes_it(qtbot):
    w, got = make(qtbot, (10.0, 120.0, 200.0))
    w.rows[1].edit.setFocus()
    assert w.selected == 1
    assert w.wheel.selected == 1
    start = w.wheel.point_for(120.0).toPoint()
    end = w.wheel.point_for(150.0).toPoint()
    qtbot.mousePress(w.wheel, Qt.MouseButton.LeftButton, pos=start)
    assert got == []  # naciśnięcie znacznika niczego nie dodaje
    qtbot.mouseMove(w.wheel, end)
    qtbot.mouseRelease(w.wheel, Qt.MouseButton.LeftButton, pos=end)
    assert len(got[-1]) == 3
    assert abs(hue_diff(got[-1][1], 150.0)) <= 1.0
    assert (got[-1][0], got[-1][2]) == (10.0, 200.0)
    assert w.rows[1].edit.value() == got[-1][1]


def test_add_button_puts_hue_in_largest_gap(qtbot):
    w, got = make(qtbot, (0.0, 90.0))
    w.add_button.click()
    assert got[-1] == (0.0, 90.0, 225.0)
    empty, got2 = make(qtbot)
    empty.add_button.click()
    assert got2[-1] == (0.0,)


def test_set_items_is_silent_and_hint_follows_emptiness(qtbot):
    w, got = make(qtbot)
    assert not w.hint_label.isHidden()
    assert "kliknij koło" in w.hint_label.text()
    w.set_items((30.0, 60.0))
    assert got == []
    assert w.items() == (30.0, 60.0)
    assert w.hint_label.isHidden()
    assert [r.edit.value() for r in w.rows] == [30.0, 60.0]
    w.set_items(())
    assert not w.hint_label.isHidden()
    assert w.selected is None
    assert got == []


def test_max_items_blocks_adding(qtbot):
    w, got = make(qtbot, (10.0, 120.0), max_items=3)
    assert w.add_button.isEnabled()
    click_wheel(qtbot, w, 250.0)
    assert len(got[-1]) == 3
    assert not w.add_button.isEnabled()
    assert "3" in w.add_button.toolTip()
    assert "3" in w.wheel.toolTip()
    click_wheel(qtbot, w, 300.0)
    w.add_button.click()
    assert len(got) == 1
    w.rows[0].remove_button.click()
    assert w.add_button.isEnabled()
    assert w.wheel.toolTip() == ""


# --- tryb kolorów ----------------------------------------------------------------------------


def test_color_mode_items_are_oklch(qtbot):
    start = (OKLCH(0.7, 0.1, 30.0),)
    w, got = make(qtbot, start, mode="color")
    assert w.items() == start
    click_wheel(qtbot, w, 200.0)
    new = got[-1][1]
    assert isinstance(new, OKLCH)
    assert abs(hue_diff(new.h, 200.0)) <= 1.0
    assert 0.0 < new.l < 1.0 and new.c > 0.0
    commit(w.rows[0].edit, "45")
    assert got[-1][0] == OKLCH(0.7, 0.1, 45.0)


def test_color_mode_lightness_and_chroma_of_selected(qtbot):
    w, got = make(qtbot, (OKLCH(0.7, 0.1, 30.0), OKLCH(0.5, 0.05, 200.0)), mode="color")
    assert not w.l_slider.isEnabled()  # nic nie zaznaczono
    w.select(1)
    assert w.l_slider.isEnabled()
    assert (w.l_slider.value(), w.c_slider.value()) == (0.5, 0.05)
    commit(w.l_slider.edit, "0.6")
    assert got[-1] == (OKLCH(0.7, 0.1, 30.0), OKLCH(0.6, 0.05, 200.0))
    commit(w.c_slider.edit, "0.12")
    assert got[-1][1] == OKLCH(0.6, 0.12, 200.0)
    w.select(0)
    assert (w.l_slider.value(), w.c_slider.value()) == (0.7, 0.1)


def test_color_mode_css_field_sets_selected_or_adds(qtbot):
    w, got = make(qtbot, (OKLCH(0.7, 0.1, 30.0),), mode="color")
    w.css_edit.setText("#336699")
    qtbot.keyClick(w.css_edit, Qt.Key.Key_Return)
    assert got[-1] == (OKLCH(0.7, 0.1, 30.0), from_css("#336699"))  # bez zaznaczenia: dodaje
    assert w.selected == 1
    w.css_edit.setText("oklch(0.8 0.05 120)")
    qtbot.keyClick(w.css_edit, Qt.Key.Key_Return)
    assert got[-1] == (OKLCH(0.7, 0.1, 30.0), from_css("oklch(0.8 0.05 120)"))  # podmienia
    n = len(got)
    w.css_edit.setText("zielonkawy")
    qtbot.keyClick(w.css_edit, Qt.Key.Key_Return)
    assert len(got) == n
    assert w.css_edit.property("bad") is True


def test_hue_mode_has_no_color_editor(qtbot):
    w, _ = make(qtbot, (10.0,))
    assert w.l_slider is None and w.c_slider is None and w.css_edit is None


def test_wheel_point_roundtrip(qtbot):
    w, _ = make(qtbot)
    for hue in (0.0, 45.0, 90.0, 180.0, 270.0, 359.0):
        p = w.wheel.point_for(hue)
        assert abs(hue_diff(w.wheel.hue_at(p), hue)) < 0.5
    assert w.wheel.hue_at(QPoint(w.wheel.width() // 2, w.wheel.height() // 2)) is None


def test_remove_keeps_following_row_value_when_its_field_has_focus(qtbot):
    w, got = make(qtbot, (10.0, 120.0, 200.0))
    w.rows[1].edit.setFocus()
    w.remove(1)  # wiersz 1 pokazuje teraz 200°
    w.rows[0].edit.setFocus()  # utrata fokusu nie może zatwierdzić starego tekstu „120”
    assert got[-1] == (10.0, 200.0)
    assert w.items() == (10.0, 200.0)
