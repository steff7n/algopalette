"""Pasek kolorów z wielokrotnym zaznaczeniem — wybór, czyje zasady edytuje zakładka „Zasady”.

Pasek: „cała paleta”, przycisk na każdy kolor (próbka + etykieta), „wszystkie akcenty”.
Zaznaczenie to albo cała paleta, albo co najmniej jeden kolor (jedno wyklucza drugie).

Mysz: klik = jeden kolor; Ctrl+klik = dołóż/odejmij (ostatniego zaznaczonego nie da się odjąć);
Shift+klik = zakres od ostatnio klikniętego koloru.
Klawiatura: pasek jest jednym przystankiem Tab; ←/→ przenosi fokus, spacja zaznacza jeden kolor,
Ctrl+spacja dokłada/odejmuje, Ctrl+A zaznacza wszystkie akcenty.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFocusEvent, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QLayout,
    QLayoutItem,
    QSizePolicy,
    QWidget,
)

SWATCH = 16
PAD_X = 8
PAD_Y = 5


@dataclass(frozen=True)
class StripEntry:
    id: str
    label: str
    hex: str
    accent: bool


@dataclass(frozen=True)
class Selection:
    """``palette=True`` ⇒ ``ids == ()``; inaczej ``ids`` niepuste, w kolejności wpisów paska."""

    palette: bool
    ids: tuple[str, ...]


class _Chip(QAbstractButton):
    """Przycisk paska: opcjonalna próbka koloru + etykieta; stan „zaznaczony” ustawia pasek."""

    triggered = Signal(object, object)  # (przycisk, modyfikatory klawiatury)
    navigate = Signal(object, int)  # (przycisk, −1 / +1)
    select_accents = Signal()

    def __init__(self, text: str, hex_: str | None = None, entry_id: str | None = None) -> None:
        super().__init__()
        self.entry_id = entry_id
        self.hex = hex_
        self.setText(text)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_hex(self, hex_: str | None) -> None:
        if hex_ != self.hex:
            self.hex = hex_
            self.update()

    def nextCheckState(self) -> None:
        """Klik nie przełącza stanu sam — o zaznaczeniu decyduje pasek."""

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        width = fm.horizontalAdvance(self.text()) + 2 * PAD_X
        if self.hex is not None:
            width += SWATCH + 6
        return QSize(width, max(fm.height(), SWATCH) + 2 * PAD_Y)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        inside = self.rect().contains(e.position().toPoint())
        super().mouseReleaseEvent(e)
        if e.button() == Qt.MouseButton.LeftButton and inside:
            self.triggered.emit(self, e.modifiers())

    def keyPressEvent(self, e: QKeyEvent) -> None:
        key, mods = e.key(), e.modifiers()
        if key == Qt.Key.Key_Space:
            self.triggered.emit(self, mods)
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.navigate.emit(self, -1 if key == Qt.Key.Key_Left else 1)
        elif key == Qt.Key.Key_A and mods & Qt.KeyboardModifier.ControlModifier:
            self.select_accents.emit()
        else:
            super().keyPressEvent(e)

    def keyReleaseEvent(self, e: QKeyEvent) -> None:
        if e.key() != Qt.Key.Key_Space:  # spacja obsłużona przy naciśnięciu
            super().keyReleaseEvent(e)

    def focusInEvent(self, e: QFocusEvent) -> None:
        super().focusInEvent(e)
        self.navigate.emit(self, 0)  # pasek zapamiętuje przystanek Tab

    def paintEvent(self, _e: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = QApplication.palette()  # paleta aplikacji: od razu śledzi zmianę motywu
        hl = pal.highlight().color()
        box = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        if self.isChecked():
            fill = QColor(hl)
            fill.setAlpha(95)
            p.setBrush(fill)
            p.setPen(QPen(hl, 1.5))
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(pal.mid().color(), 1))
        p.drawRoundedRect(box, 5, 5)
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(pal.windowText().color(), 1, Qt.PenStyle.DotLine))
            p.drawRoundedRect(box.adjusted(2, 2, -2, -2), 3, 3)
        x = PAD_X
        if self.hex is not None:
            sw = QRectF(x, (self.height() - SWATCH) / 2, SWATCH, SWATCH)
            p.setPen(QPen(QColor("#808080"), 1))
            p.setBrush(QColor(self.hex))
            p.drawRect(sw)
            x += SWATCH + 6
        p.setPen(pal.windowText().color())
        text_rect = QRectF(x, 0, self.width() - x - PAD_X + 2, self.height())
        p.drawText(
            text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text()
        )
        p.end()


class _FlowLayout(QLayout):
    """Układa elementy w wierszach i zawija je do szerokości (żadna etykieta nie jest obcinana)."""

    def __init__(self, parent: QWidget, spacing: int = 4) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._gap = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._place(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._place(rect, apply=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize(0, 0)
        for item in self._items:
            size = size.expandedTo(item.sizeHint())
        return size

    def _place(self, rect: QRect, *, apply: bool) -> int:
        x, y, row_h = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x > rect.x() and x + hint.width() > rect.right() + 1:
                x, y, row_h = rect.x(), y + row_h + self._gap, 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._gap
            row_h = max(row_h, hint.height())
        return y + row_h - rect.y()


class ColorStrip(QWidget):
    selection_changed = Signal(object)  # Selection

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[StripEntry] = []
        self._selected: set[str] = set()
        self._anchor: str | None = None
        self.chips: list[_Chip] = []
        self._lay = _FlowLayout(self)
        self.palette_button = _Chip("cała paleta")
        self.accents_button = _Chip("wszystkie akcenty")
        for b in (self.palette_button, self.accents_button):
            self._wire(b)
        self._tab_stop: _Chip = self.palette_button
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self._rebuild()
        self._sync()

    # --- odczyt -------------------------------------------------------------------------------

    def selection(self) -> Selection:
        if not self._selected:
            return Selection(True, ())
        return Selection(False, tuple(e.id for e in self._entries if e.id in self._selected))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._lay.heightForWidth(width)

    # --- zapis --------------------------------------------------------------------------------

    def set_entries(self, entries: Sequence[StripEntry]) -> None:
        """Nowa lista kolorów. Zaznaczenie zostaje dla ``id``, które nadal istnieją; gdy żadne
        nie zostało — zaznaczona jest cała paleta. Ten sam zestaw ``id`` → te same przyciski."""
        before = self.selection()
        same = [e.id for e in entries] == [e.id for e in self._entries]
        self._entries = list(entries)
        ids = {e.id for e in self._entries}
        self._selected &= ids
        if self._anchor not in ids:
            self._anchor = None
        if same:
            for chip, entry in zip(self.chips, self._entries, strict=True):
                chip.set_hex(entry.hex)
                if chip.text() != entry.label:
                    chip.setText(entry.label)
                    chip.updateGeometry()
            self._lay.invalidate()
        else:
            self._rebuild()
        self._sync()
        if self.selection() != before:
            self.selection_changed.emit(self.selection())

    def select(self, ids: Sequence[str]) -> None:
        """Zaznacza podane kolory (nieistniejące pomija); pusta lista = cała paleta."""
        known = {e.id for e in self._entries}
        self._apply({i for i in ids if i in known})

    def select_palette(self) -> None:
        self._apply(set())

    def select_all_accents(self) -> None:
        self._apply({e.id for e in self._entries if e.accent})

    def _apply(self, selected: set[str]) -> None:
        if selected == self._selected:
            return
        self._selected = selected
        self._sync()
        self.selection_changed.emit(self.selection())

    # --- budowa -------------------------------------------------------------------------------

    def _wire(self, chip: _Chip) -> None:
        chip.triggered.connect(self._triggered)
        chip.navigate.connect(self._navigate)
        chip.select_accents.connect(self.select_all_accents)

    def _buttons(self) -> list[_Chip]:
        return [self.palette_button, *self.chips, self.accents_button]

    def _rebuild(self) -> None:
        focused = next((c.entry_id for c in self.chips if c.hasFocus()), None)
        while self._lay.count():
            self._lay.takeAt(0)
        for chip in self.chips:
            chip.hide()
            chip.setParent(None)
            chip.deleteLater()
        self.chips = []
        for entry in self._entries:
            chip = _Chip(entry.label, entry.hex, entry.id)
            self._wire(chip)
            self.chips.append(chip)
        for b in self._buttons():
            self._lay.addWidget(b)
            b.show()
        if self._tab_stop not in self._buttons():
            self._tab_stop = self.palette_button
        for chip in self.chips:
            if chip.entry_id == focused:
                chip.setFocus()
        self._lay.invalidate()
        self.updateGeometry()

    def _sync(self) -> None:
        self.palette_button.setChecked(not self._selected)
        accents = {e.id for e in self._entries if e.accent}
        self.accents_button.setChecked(bool(accents) and self._selected == accents)
        for chip in self.chips:
            chip.setChecked(chip.entry_id in self._selected)
        for b in self._buttons():
            stop = b is self._tab_stop
            b.setFocusPolicy(Qt.FocusPolicy.StrongFocus if stop else Qt.FocusPolicy.ClickFocus)

    # --- zdarzenia ----------------------------------------------------------------------------

    def _triggered(self, chip: _Chip, mods: Qt.KeyboardModifier) -> None:
        if chip is self.palette_button:
            self.select_palette()
            return
        if chip is self.accents_button:
            self.select_all_accents()
            return
        cid = chip.entry_id
        assert cid is not None
        order = [e.id for e in self._entries]
        if mods & Qt.KeyboardModifier.ShiftModifier and self._anchor in order:
            a, b = sorted((order.index(self._anchor), order.index(cid)))
            self._apply(set(order[a : b + 1]))
            return
        self._anchor = cid
        if mods & Qt.KeyboardModifier.ControlModifier and self._selected:
            new = set(self._selected)
            if cid in new:
                if len(new) > 1:  # ostatniego zaznaczonego nie da się odjąć
                    new.discard(cid)
            else:
                new.add(cid)
            self._apply(new)
        else:
            self._apply({cid})

    def _navigate(self, chip: _Chip, step: int) -> None:
        buttons = self._buttons()
        if chip not in buttons:
            return
        target = buttons[min(max(buttons.index(chip) + step, 0), len(buttons) - 1)]
        self._tab_stop = target
        self._sync()
        if step and target is not chip:
            target.setFocus()
