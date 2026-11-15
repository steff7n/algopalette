"""Pasek kolorów z wielokrotnym zaznaczeniem (zastępuje zakładki ról w „Zasadach”)."""

from dataclasses import replace

import pytest
from PySide6.QtCore import Qt

from algopalette.gui.colorstrip import ColorStrip, Selection, StripEntry

CTRL = Qt.KeyboardModifier.ControlModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
LEFT = Qt.MouseButton.LeftButton


def entries(accents: int = 8) -> list[StripEntry]:
    out = [
        StripEntry("bg", "tło", "#101020", False),
        StripEntry("fg", "tekst", "#f0f0f0", False),
    ]
    out += [StripEntry(f"a{i}", f"akcent {i}", f"#{i:x}0a0c0", True) for i in range(1, accents + 1)]
    return out


@pytest.fixture
def strip(qtbot):
    w = ColorStrip()
    qtbot.addWidget(w)
    w.set_entries(entries())
    w.resize(1400, 80)
    with qtbot.waitActive(w):
        w.show()
        w.activateWindow()
    got = []
    w.selection_changed.connect(got.append)
    return w, got


def chip(w: ColorStrip, entry_id: str):
    return next(c for c in w.chips if c.entry_id == entry_id)


def test_starts_with_whole_palette(strip):
    w, got = strip
    assert w.selection() == Selection(True, ())
    assert w.palette_button.isChecked()
    assert [c.entry_id for c in w.chips] == [e.id for e in entries()]
    assert [c.text() for c in w.chips][:3] == ["tło", "tekst", "akcent 1"]
    assert not any(c.isChecked() for c in w.chips)
    assert got == []


def test_click_selects_one(qtbot, strip):
    w, got = strip
    qtbot.mouseClick(chip(w, "a2"), LEFT)
    assert got == [Selection(False, ("a2",))]
    assert chip(w, "a2").isChecked()
    assert not w.palette_button.isChecked()
    qtbot.mouseClick(chip(w, "a2"), LEFT)
    assert len(got) == 1  # to samo zaznaczenie → bez sygnału
    qtbot.mouseClick(chip(w, "fg"), LEFT)
    assert got[-1] == Selection(False, ("fg",))
    assert not chip(w, "a2").isChecked()


def test_ctrl_click_adds_and_removes_but_keeps_last(qtbot, strip):
    w, got = strip
    qtbot.mouseClick(chip(w, "a3"), LEFT)
    qtbot.mouseClick(chip(w, "a1"), LEFT, CTRL)
    assert got[-1] == Selection(False, ("a1", "a3"))  # kolejność wpisów, nie klikania
    qtbot.mouseClick(chip(w, "a3"), LEFT, CTRL)
    assert got[-1] == Selection(False, ("a1",))
    n = len(got)
    qtbot.mouseClick(chip(w, "a1"), LEFT, CTRL)  # ostatniego nie da się odjąć
    assert len(got) == n
    assert w.selection() == Selection(False, ("a1",))


def test_ctrl_click_from_whole_palette_selects_that_color(qtbot, strip):
    w, got = strip
    qtbot.mouseClick(chip(w, "a4"), LEFT, CTRL)
    assert got == [Selection(False, ("a4",))]


def test_shift_click_selects_range_from_last_clicked(qtbot, strip):
    w, got = strip
    qtbot.mouseClick(chip(w, "a5"), LEFT)
    qtbot.mouseClick(chip(w, "a2"), LEFT, SHIFT)
    assert got[-1] == Selection(False, ("a2", "a3", "a4", "a5"))
    qtbot.mouseClick(chip(w, "a7"), LEFT, SHIFT)  # kotwica zostaje na a5
    assert got[-1] == Selection(False, ("a5", "a6", "a7"))
    qtbot.mouseClick(chip(w, "bg"), LEFT, SHIFT)
    assert got[-1].ids[0] == "bg" and got[-1].ids[-1] == "a5"


def test_palette_and_colors_exclude_each_other(qtbot, strip):
    w, got = strip
    qtbot.mouseClick(chip(w, "a1"), LEFT)
    qtbot.mouseClick(chip(w, "a2"), LEFT, CTRL)
    qtbot.mouseClick(w.palette_button, LEFT)
    assert got[-1] == Selection(True, ())
    assert w.palette_button.isChecked()
    assert not any(c.isChecked() for c in w.chips)
    n = len(got)
    qtbot.mouseClick(w.palette_button, LEFT)
    assert len(got) == n


def test_all_accents_button_and_ctrl_a(qtbot, strip):
    w, got = strip
    all_accents = tuple(f"a{i}" for i in range(1, 9))
    qtbot.mouseClick(w.accents_button, LEFT)
    assert got[-1] == Selection(False, all_accents)
    assert w.accents_button.isChecked()
    qtbot.mouseClick(chip(w, "bg"), LEFT)
    assert not w.accents_button.isChecked()
    chip(w, "bg").setFocus()
    qtbot.keyClick(chip(w, "bg"), Qt.Key.Key_A, CTRL)
    assert got[-1] == Selection(False, all_accents)


def test_keyboard_navigation_and_selection(qtbot, strip):
    w, got = strip
    w.palette_button.setFocus()
    qtbot.keyClick(w.palette_button, Qt.Key.Key_Right)
    assert chip(w, "bg").hasFocus()
    qtbot.keyClick(chip(w, "bg"), Qt.Key.Key_Right)
    qtbot.keyClick(chip(w, "fg"), Qt.Key.Key_Right)
    assert chip(w, "a1").hasFocus()
    assert got == []  # samo przenoszenie fokusu niczego nie zaznacza
    qtbot.keyClick(chip(w, "a1"), Qt.Key.Key_Space)
    assert got[-1] == Selection(False, ("a1",))
    qtbot.keyClick(chip(w, "a1"), Qt.Key.Key_Right)
    qtbot.keyClick(chip(w, "a2"), Qt.Key.Key_Space, CTRL)
    assert got[-1] == Selection(False, ("a1", "a2"))
    qtbot.keyClick(chip(w, "a2"), Qt.Key.Key_Space, CTRL)
    assert got[-1] == Selection(False, ("a1",))
    qtbot.keyClick(chip(w, "a2"), Qt.Key.Key_Left)
    assert chip(w, "a1").hasFocus()
    w.accents_button.setFocus()
    qtbot.keyClick(w.accents_button, Qt.Key.Key_Right)  # koniec paska: fokus zostaje
    assert w.accents_button.hasFocus()
    qtbot.keyClick(w.accents_button, Qt.Key.Key_Space)
    assert len(got[-1].ids) == 8


def test_only_one_tab_stop(strip):
    w, _ = strip
    buttons = [w.palette_button, *w.chips, w.accents_button]
    tab_stops = [b for b in buttons if b.focusPolicy().value & Qt.FocusPolicy.TabFocus.value]
    assert len(tab_stops) == 1


def test_programmatic_selection(strip):
    w, got = strip
    w.select(["a3", "a1", "nie-ma"])
    assert got[-1] == Selection(False, ("a1", "a3"))
    w.select(["a3", "a1"])
    assert len(got) == 1
    w.select_palette()
    assert got[-1] == Selection(True, ())
    w.select_all_accents()
    assert len(got[-1].ids) == 8
    w.select([])
    assert got[-1] == Selection(True, ())


def test_set_entries_keeps_selection_of_existing_ids(strip):
    w, got = strip
    w.select(["a2", "a8"])
    w.set_entries(entries(accents=7))  # a8 znika
    assert got[-1] == Selection(False, ("a2",))
    assert [c.entry_id for c in w.chips][-1] == "a7"
    w.select(["a7"])
    w.set_entries(entries(accents=6))  # żaden zaznaczony nie został
    assert got[-1] == Selection(True, ())
    assert w.palette_button.isChecked()


def test_set_entries_updates_swatches_in_place(strip):
    w, got = strip
    w.select(["a1"])
    before = list(w.chips)
    changed = [replace(e, hex="#abcdef", label="słowa") if e.id == "a1" else e for e in entries()]
    w.set_entries(changed)
    assert w.chips == before  # te same widżety — bez przebudowy
    assert (chip(w, "a1").hex, chip(w, "a1").text()) == ("#abcdef", "słowa")
    assert len(got) == 1  # zaznaczenie bez zmian → bez sygnału
    w.set_entries(changed)
    assert len(got) == 1


def test_sixteen_entries_wrap_without_clipping(qtbot):
    w = ColorStrip()
    qtbot.addWidget(w)
    w.set_entries(entries(accents=14))
    assert len(w.chips) == 16
    width = 420
    w.resize(width, w.heightForWidth(width))
    w.show()
    qtbot.waitExposed(w)
    for b in (w.palette_button, *w.chips, w.accents_button):
        assert b.width() >= b.sizeHint().width()  # etykieta nieobcięta
        assert b.sizeHint().width() >= b.fontMetrics().horizontalAdvance(b.text())
        assert w.rect().contains(b.geometry()), b.text()
    rows = {b.y() for b in w.chips}
    assert len(rows) > 1  # zawinięte do kilku wierszy
