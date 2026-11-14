"""GUI — pole liczby, pasek suwaka, suwaki wartości i zakresu."""

from PySide6.QtCore import Qt

from algopalette.gui.widgets import Bar, NumEdit, RangeSlider, ValueSlider


def commit(edit: NumEdit, text: str) -> None:
    edit.setText(text)
    edit.editingFinished.emit()


def test_numedit_commits_only_changes(qtbot):
    e = NumEdit(1.0, minimum=0.0, maximum=2.0)
    qtbot.addWidget(e)
    got = []
    e.committed.connect(got.append)
    commit(e, "1.5")
    commit(e, "1,5")  # przecinek = ta sama wartość → bez sygnału
    assert got == [1.5]


def test_numedit_rejects_garbage_and_inf(qtbot):
    e = NumEdit(1.0)
    qtbot.addWidget(e)
    got = []
    e.committed.connect(got.append)
    for bad in ("abc", "inf", "nan", "1e999"):
        commit(e, bad)
        assert e.property("bad") is True
    assert got == [] and e.value() == 1.0


def test_numedit_clamps_and_allows_none(qtbot):
    e = NumEdit(0.5, minimum=0.0, maximum=1.0, allow_none=True)
    qtbot.addWidget(e)
    got = []
    e.committed.connect(got.append)
    commit(e, "7")
    commit(e, "")
    assert got == [1.0, None]


def test_numedit_integer_rejects_fraction(qtbot):
    e = NumEdit(3, integer=True, minimum=1)
    qtbot.addWidget(e)
    commit(e, "2.5")
    assert e.property("bad") is True and e.value() == 3
    commit(e, "0")
    assert e.property("bad") is True


def test_numedit_arrow_keys_step(qtbot):
    e = NumEdit(0.5, minimum=0.0, maximum=1.0, step=0.01, fmt=".2f")
    qtbot.addWidget(e)
    got = []
    e.committed.connect(got.append)
    qtbot.keyClick(e, Qt.Key.Key_Up)
    qtbot.keyClick(e, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    assert got == [0.51, 0.41]


def test_bar_keyboard_and_wrap(qtbot):
    b = Bar([350.0], minimum=0, maximum=360, step=1, wrap=True)
    qtbot.addWidget(b)
    moves = []
    b.moved.connect(lambda k, v: moves.append(v))
    qtbot.keyClick(b, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)  # +10 → 360 → 0
    assert moves[-1] == 0.0
    qtbot.keyClick(b, Qt.Key.Key_Left)
    assert moves[-1] == 359.0
    qtbot.keyClick(b, Qt.Key.Key_End)
    assert moves[-1] == 0.0  # pojedynczy uchwyt: 360 = 0


def test_bar_range_keeps_order_without_wrap(qtbot):
    b = Bar([0.2, 0.4], minimum=0, maximum=1, step=0.1)
    qtbot.addWidget(b)
    b.active = 0
    b.set_active_value(0.7)
    assert b.values == [0.7, 0.7]


def test_bar_mouse_drag_picks_nearest(qtbot):
    b = Bar([0.0, 1.0], minimum=0, maximum=1, step=0.01)
    qtbot.addWidget(b)
    b.resize(300, 30)
    b.show()
    qtbot.mouseClick(b, Qt.MouseButton.LeftButton, pos=b.rect().center())
    assert b.values[0] == 0.0 or b.values[1] == 1.0
    moved = b.values[b.active]
    assert moved is not None and 0.4 <= moved <= 0.6


def test_value_slider_sync(qtbot):
    s = ValueSlider(0.5, minimum=0, maximum=1, step=0.1, fmt=".2f")
    qtbot.addWidget(s)
    got = []
    s.changed.connect(got.append)
    commit(s.edit, "0.8")
    assert s.bar.values == [0.8]
    qtbot.keyClick(s.bar, Qt.Key.Key_Right)
    assert s.edit.text() == "0.90" and got == [0.8, 0.9]


def test_range_slider_none_and_full_circle(qtbot):
    r = RangeSlider(None, 0.8, minimum=0, maximum=1, step=0.1, allow_none=True)
    qtbot.addWidget(r)
    assert r.values() == (None, 0.8)
    h = RangeSlider(330, 20, minimum=0, maximum=360, step=1, wrap=True)
    qtbot.addWidget(h)
    got = []
    h.changed.connect(lambda lo, hi: got.append((lo, hi)))
    commit(h.hi_edit, "360")
    assert got == [(330, 360.0)]  # 360 w górnym uchwycie = pełne koło, nie 0
