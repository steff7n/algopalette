"""Suwak zakresu z zakazanymi przedziałami (jasność, nasycenie, odcień)."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from algopalette.gui.band import BandSlider
from algopalette.gui.widgets import NumEdit


def commit(edit: NumEdit, text: str) -> None:
    edit.setText(text)
    edit.editingFinished.emit()


def lightness(qtbot, lo=0.2, hi=0.8, exclude=(), **kw):
    w = BandSlider(lo, hi, exclude, minimum=0.0, maximum=1.0, step=0.01, allow_none=True, **kw)
    qtbot.addWidget(w)
    got = []
    w.changed.connect(lambda *a: got.append(a))
    return w, got


def hue(qtbot, lo=0.0, hi=270.0, exclude=(), **kw):
    w = BandSlider(
        lo, hi, exclude, minimum=0.0, maximum=360.0, step=1.0, fmt=".0f", wrap=True, **kw
    )
    qtbot.addWidget(w)
    got = []
    w.changed.connect(lambda *a: got.append(a))
    return w, got


def render(w) -> QImage:
    w.resize(400, w.sizeHint().height())
    return w.bar.grab().toImage()


def column(img: QImage, x: int) -> list[int]:
    return [img.pixel(x, y) for y in range(img.height())]


# --- wartości i sygnał -----------------------------------------------------------------------


def test_values_and_sorted_exclusions(qtbot):
    w, got = lightness(qtbot, exclude=((0.70, 0.74), (0.30, 0.35)))
    assert w.values() == (0.2, 0.8, ((0.30, 0.35), (0.70, 0.74)))
    assert got == []


def test_range_change_emits_all_three(qtbot):
    w, got = lightness(qtbot, exclude=((0.30, 0.35),))
    commit(w.range.lo_edit, "0.25")
    assert got == [(0.25, 0.8, ((0.30, 0.35),))]
    commit(w.range.hi_edit, "")
    assert got[-1] == (0.25, None, ((0.30, 0.35),))
    w.bar.setFocus()
    w.bar.active = 0
    qtbot.keyClick(w.bar, Qt.Key.Key_Right)
    assert got[-1] == (0.26, None, ((0.30, 0.35),))


def test_set_values_is_silent_and_updates_fields(qtbot):
    w, got = lightness(qtbot)
    w.set_values(0.1, 0.9, ((0.4, 0.5), (0.6, 0.7)))
    assert got == []
    assert w.values() == (0.1, 0.9, ((0.4, 0.5), (0.6, 0.7)))
    assert [(i.lo_edit.value(), i.hi_edit.value()) for i in w.items] == [(0.4, 0.5), (0.6, 0.7)]
    assert w.range.lo_edit.value() == 0.1
    w.set_values(0.1, 0.9, ((0.45, 0.5), (0.6, 0.7)))  # ta sama liczba pozycji → te same widżety
    first = w.items[0]
    w.set_values(0.1, 0.9, ((0.41, 0.5), (0.6, 0.7)))
    assert w.items[0] is first
    assert first.lo_edit.value() == 0.41
    w.set_values(0.1, 0.9, ())
    assert w.items == []
    assert got == []


# --- zakazy ----------------------------------------------------------------------------------


def test_add_exclusion_in_middle_of_allowed_range(qtbot):
    w, got = lightness(qtbot, lo=0.21, hi=0.81)
    w.add_button.click()
    lo, hi, ex = got[-1]
    assert (lo, hi) == (0.21, 0.81)
    assert ex == (pytest.approx((0.46, 0.56)),)  # 10% osi wokół środka 0.51
    assert len(w.items) == 1


def test_add_exclusion_picks_largest_free_gap(qtbot):
    w, got = lightness(qtbot, lo=0.0, hi=1.0, exclude=((0.1, 0.2), (0.5, 0.9)))
    w.add_button.click()  # luki: 0–0.1, 0.2–0.5 (największa), 0.9–1
    assert got[-1][2] == ((0.1, 0.2), pytest.approx((0.3, 0.4)), (0.5, 0.9))


def test_add_exclusion_with_open_bounds_uses_axis_range(qtbot):
    w, got = lightness(qtbot, lo=None, hi=None)
    w.add_button.click()
    assert got[-1][2] == (pytest.approx((0.45, 0.55)),)


def test_add_exclusion_shrinks_to_small_gap(qtbot):
    w, got = lightness(qtbot, lo=0.50, hi=0.56)
    w.add_button.click()
    (a, b) = got[-1][2][0]
    assert 0.50 <= a < b <= 0.56


def test_add_exclusion_on_wrapping_arc(qtbot):
    w, got = hue(qtbot, lo=300.0, hi=100.0)  # łuk 160° przez 0°, środek 20°
    w.add_button.click()
    assert got[-1][2] == ((2.0, 38.0),)
    w2, got2 = hue(qtbot, lo=0.0, hi=360.0, exclude=((350.0, 10.0),))
    w2.add_button.click()  # wolne 10–350, środek 180
    assert got2[-1][2] == ((162.0, 198.0), (350.0, 10.0))


def test_edit_exclusion_emits_sorted(qtbot):
    w, got = lightness(qtbot, exclude=((0.30, 0.35), (0.70, 0.74)))
    commit(w.items[0].hi_edit, "0.4")
    assert got[-1] == (0.2, 0.8, ((0.30, 0.4), (0.70, 0.74)))
    commit(w.items[0].lo_edit, "0.76")
    assert w.items[0].lo_edit.property("bad") is True  # od ≥ do
    assert len(got) == 1
    commit(w.items[0].hi_edit, "0.79")
    assert w.items[0].lo_edit.property("bad") is False
    assert got[-1] == (0.2, 0.8, ((0.70, 0.74), (0.76, 0.79)))


@pytest.mark.parametrize("text", ["0.35", "0.5"])
def test_invalid_linear_pair_is_rejected(qtbot, text):
    w, got = lightness(qtbot, exclude=((0.30, 0.35),))
    commit(w.items[0].lo_edit, text)
    assert w.items[0].lo_edit.property("bad") is True
    assert got == []
    assert w.values()[2] == ((0.30, 0.35),)


def test_hue_exclusion_may_wrap_but_not_be_empty(qtbot):
    w, got = hue(qtbot, exclude=((60.0, 85.0),))
    commit(w.items[0].lo_edit, "350")
    commit(w.items[0].hi_edit, "10")
    assert got[-1][2] == ((350.0, 10.0),)
    commit(w.items[0].hi_edit, "350")
    assert w.items[0].hi_edit.property("bad") is True
    assert got[-1][2] == ((350.0, 10.0),)


def test_remove_exclusion_by_button_and_delete_key(qtbot):
    w, got = lightness(qtbot, exclude=((0.30, 0.35), (0.50, 0.55), (0.70, 0.74)))
    w.items[1].remove_button.click()
    assert got[-1][2] == ((0.30, 0.35), (0.70, 0.74))
    assert len(w.items) == 2
    w.items[0].remove_button.setFocus()
    qtbot.keyClick(w.items[0].remove_button, Qt.Key.Key_Delete)
    assert got[-1][2] == ((0.70, 0.74),)
    assert [(i.lo_edit.value(), i.hi_edit.value()) for i in w.items] == [(0.70, 0.74)]


# --- pasek -----------------------------------------------------------------------------------


def test_exclusions_are_drawn_on_bar(qtbot):
    w, _ = lightness(qtbot)
    w.show()
    plain = render(w)
    w.set_values(0.2, 0.8, ((0.45, 0.55),))
    marked = render(w)
    mid, side = plain.width() // 2, int(plain.width() * 0.3)
    assert column(marked, mid) != column(plain, mid)
    assert column(marked, side) == column(plain, side)
    assert w.bar.excluded == ((0.45, 0.55),)


def test_wrapping_exclusion_is_drawn_at_both_ends(qtbot):
    w, _ = hue(qtbot, lo=0.0, hi=360.0)
    w.show()
    plain = render(w)
    w.set_values(0.0, 360.0, ((340.0, 20.0),))
    marked = render(w)
    width = plain.width()
    left, right, mid = int(width * 0.06), int(width * 0.94), width // 2
    assert column(marked, left) != column(plain, left)
    assert column(marked, right) != column(plain, right)
    assert column(marked, mid) == column(plain, mid)


# --- środek ± szerokość ----------------------------------------------------------------------


def test_center_fields_drive_arc(qtbot):
    w, got = hue(qtbot, lo=0.0, hi=60.0, center_fields=True)
    assert (w.center_edit.value(), w.half_edit.value()) == (30.0, 30.0)
    commit(w.half_edit, "20")
    assert got[-1][:2] == (10.0, 50.0)
    commit(w.center_edit, "350")
    assert got[-1][:2] == (330.0, 10.0)
    assert w.values()[:2] == (330.0, 10.0)
    assert (w.range.lo_edit.value(), w.range.hi_edit.value()) == (330.0, 10.0)


def test_center_fields_follow_range(qtbot):
    w, got = hue(qtbot, lo=0.0, hi=60.0, center_fields=True)
    commit(w.range.lo_edit, "340")
    assert got[-1][:2] == (340.0, 60.0)
    assert (w.center_edit.value(), w.half_edit.value()) == (20.0, 40.0)
    w.set_values(100.0, 140.0, ())
    assert (w.center_edit.value(), w.half_edit.value()) == (120.0, 20.0)
    w.set_values(0.0, 360.0, ())
    assert w.half_edit.value() == 180.0


def test_no_center_fields_by_default(qtbot):
    w, _ = lightness(qtbot)
    assert w.center_edit is None
    assert w.half_edit is None


# --- klawiatura ------------------------------------------------------------------------------


def test_everything_is_reachable_by_keyboard(qtbot):
    w, got = hue(qtbot, exclude=((60.0, 85.0),), center_fields=True)
    item = w.items[0]
    focusable = [
        w.range.lo_edit,
        w.bar,
        w.range.hi_edit,
        w.center_edit,
        w.half_edit,
        item.lo_edit,
        item.hi_edit,
        item.remove_button,
        w.add_button,
    ]
    for widget in focusable:
        assert widget.focusPolicy().value & Qt.FocusPolicy.TabFocus.value, widget
    w.show()
    item.lo_edit.setFocus()
    item.lo_edit.selectAll()
    qtbot.keyClicks(item.lo_edit, "70")
    qtbot.keyClick(item.lo_edit, Qt.Key.Key_Return)
    assert got[-1][2] == ((70.0, 85.0),)
    w.add_button.setFocus()
    qtbot.keyClick(w.add_button, Qt.Key.Key_Space)
    assert len(w.items) == 2


def test_add_exclusion_on_full_circle_uses_gap_across_zero(qtbot):
    w, got = hue(qtbot, lo=0.0, hi=360.0, exclude=((100.0, 200.0),))
    w.add_button.click()  # wolne 200–100 przez 0°, środek 330
    assert got[-1][2] == ((100.0, 200.0), (312.0, 348.0))
