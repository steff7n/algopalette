"""Wybierak listy: koło odcieni + lista pozycji. Dwa tryby:

* ``hue`` — lista odcieni (własna lista układu odcieni); elementy to stopnie ``float``;
* ``color`` — lista pełnych kolorów (unikane kolory); elementy to ``OKLCH``, dochodzą suwaki
  jasności i nasycenia zaznaczonej pozycji oraz pole przyjmujące hex i ``oklch(...)``.

Mysz: klik w koło dodaje pozycję na końcu listy (odcień zaokrąglony do 1°), przeciąganie znacznika
na kole zmienia odcień tej pozycji, przeciąganie próbki w wierszu przestawia pozycje.
Klawiatura: Tab po polach, Enter zatwierdza liczbę, Alt+↑/↓ przestawia pozycję, Delete na
przycisku ✕ ją usuwa.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Literal

import numpy as np
from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QConicalGradient, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from algopalette import color as col
from algopalette.gui import theme
from algopalette.gui.widgets import (
    NumEdit,
    Swatch,
    ValueSlider,
    channel_gradient,
    hint,
    lch_to_qcolors,
    vbox,
)
from algopalette.model import OKLCH

WHEEL_L = 0.75  # koło odcieni rysowane przy stałej jasności i nasyceniu (jak w Analizie)
WHEEL_C = 0.13
NEW_COLOR_L = 0.70  # jasność i nasycenie koloru dodanego kliknięciem w koło (tryb „color”)
NEW_COLOR_C = 0.10
MARKER_R = 7
RING_INNER = 0.62  # promień wewnętrzny pierścienia jako część zewnętrznego
DEAD_ZONE = 0.25  # bliżej środka kąt jest niepewny — klik ignorowany

Mode = Literal["hue", "color"]


def _qcolor(c: OKLCH) -> QColor:
    return lch_to_qcolors(np.array([[c.l, c.c, c.h]]))[0]


class _Wheel(QWidget):
    """Pierścień odcieni ze znacznikami pozycji listy."""

    clicked = Signal(float)  # klik poza znacznikiem: odcień zaokrąglony do 1°
    marker_pressed = Signal(int)
    marker_moved = Signal(int, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.colors: list[OKLCH] = []
        self.selected: int | None = None
        self._drag: int | None = None
        self.setFixedSize(QSize(200, 200))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_state(self, colors: Sequence[OKLCH], selected: int | None) -> None:
        self.colors, self.selected = list(colors), selected
        self.update()

    def _geometry(self) -> tuple[QPointF, float]:
        r = min(self.width(), self.height()) / 2 - MARKER_R - 4
        return QPointF(self.width() / 2, self.height() / 2), r

    def point_for(self, hue: float) -> QPointF:
        """Miejsce znacznika odcienia: 0° po prawej, kąty rosną przeciwnie do ruchu wskazówek."""
        center, r = self._geometry()
        radius = r * (1 + RING_INNER) / 2
        a = math.radians(hue)
        return QPointF(center.x() + radius * math.cos(a), center.y() - radius * math.sin(a))

    def hue_at(self, pos: Any) -> float | None:
        """Odcień pod punktem; ``None`` przy samym środku i poza kołem."""
        center, r = self._geometry()
        dx, dy = pos.x() - center.x(), center.y() - pos.y()
        dist = math.hypot(dx, dy)
        if dist < DEAD_ZONE * r or dist > r + MARKER_R + 2:
            return None
        return math.degrees(math.atan2(dy, dx)) % 360.0

    def _marker_at(self, pos: Any) -> int | None:
        best: tuple[float, int] | None = None
        for i, c in enumerate(self.colors):
            p = self.point_for(c.h)
            d = math.hypot(pos.x() - p.x(), pos.y() - p.y())
            if d <= MARKER_R + 3 and (best is None or d < best[0] or i == self.selected):
                best = (d, i)
        return None if best is None else best[1]

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        pos = e.position()
        marker = self._marker_at(pos)
        if marker is not None:
            self._drag = marker
            self.marker_pressed.emit(marker)
            return
        hue = self.hue_at(pos)
        if hue is not None:
            self.clicked.emit(float(round(hue) % 360))

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag is None:
            return
        hue = self.hue_at(e.position())
        if hue is not None:
            self.marker_moved.emit(self._drag, float(round(hue) % 360))

    def mouseReleaseEvent(self, _e: QMouseEvent) -> None:
        self._drag = None

    def paintEvent(self, _e: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        center, r = self._geometry()
        hues = np.arange(0.0, 361.0, 5.0)
        lch = np.stack([np.full_like(hues, WHEEL_L), np.full_like(hues, WHEEL_C), hues], axis=-1)
        grad = QConicalGradient(center, 0.0)
        for h, qc in zip(hues, lch_to_qcolors(lch), strict=True):
            grad.setColorAt(min(h / 360.0, 1.0), qc)
        pal = QApplication.palette()  # paleta widżetu dostaje nowy motyw z opóźnieniem
        p.setPen(QPen(pal.mid().color(), 1))
        p.setBrush(grad)
        p.drawEllipse(center, r, r)
        p.setBrush(pal.window())
        p.drawEllipse(center, r * RING_INNER, r * RING_INNER)
        order = [i for i in range(len(self.colors)) if i != self.selected]
        if self.selected is not None and self.selected < len(self.colors):
            order.append(self.selected)  # zaznaczony na wierzchu
        for i in order:
            pt = self.point_for(self.colors[i].h)
            chosen = i == self.selected
            if chosen:
                p.setPen(QPen(QColor("#000000"), 4))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(pt, MARKER_R + 2, MARKER_R + 2)
            p.setPen(QPen(QColor("#ffffff" if chosen else "#202020"), 2))
            p.setBrush(_qcolor(self.colors[i]))
            radius = MARKER_R + 2 if chosen else MARKER_R
            p.drawEllipse(pt, radius, radius)
        p.end()


class _Row(QWidget):
    """Pozycja listy: próbka (uchwyt do przeciągania), pole stopni, przycisk usunięcia."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.selected = False
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.setSpacing(4)
        self.handle = Swatch(size=QSize(30, 20))
        self.handle.setCursor(Qt.CursorShape.OpenHandCursor)
        self.edit = NumEdit(0.0, fmt="g", minimum=0.0, maximum=360.0, step=1.0, wrap=True, width=58)
        self.remove_button = QToolButton()
        self.remove_button.setText("✕")
        self.remove_button.setAutoRaise(True)
        self.remove_button.setAccessibleName("usuń pozycję")
        lay.addWidget(self.handle)
        lay.addWidget(self.edit)
        lay.addWidget(self.remove_button)
        lay.addStretch(1)

    def set_selected(self, on: bool) -> None:
        if on != self.selected:
            self.selected = on
            self.update()

    def paintEvent(self, _e: Any) -> None:
        if not self.selected:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        hl = QApplication.palette().highlight().color()  # z palety aplikacji: śledzi motyw
        fill = QColor(hl)
        fill.setAlpha(70)
        p.setPen(QPen(hl, 1.5))
        p.setBrush(fill)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 4, 4)
        p.end()


class ListPicker(QWidget):
    """Lista odcieni albo kolorów z kołem do wybierania. ``changed(tuple)`` przy każdej zmianie."""

    changed = Signal(object)

    def __init__(
        self,
        items: Sequence[Any],
        *,
        mode: Mode,
        max_items: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.mode: Mode = mode
        self.max_items = max_items
        self._colors: list[OKLCH] = []
        self.rows: list[_Row] = []
        self.selected: int | None = None
        self._drag_row: int | None = None

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.wheel = _Wheel()
        outer.addWidget(self.wheel, 0, Qt.AlignmentFlag.AlignTop)
        right = vbox(spacing=4)
        outer.addLayout(right, 1)

        self.hint_label = hint("Lista jest pusta — kliknij koło, żeby dodać pozycję.")
        right.addWidget(self.hint_label)
        self._rows_host = QWidget()
        self._rows_lay = vbox(self._rows_host, spacing=0)
        self._rows_lay.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._rows_host)
        scroll.setMinimumHeight(60)
        self.scroll_area = scroll
        right.addWidget(scroll, 1)
        self.add_button = QPushButton("+ dodaj")
        self.add_button.clicked.connect(self.add_item)
        right.addWidget(self.add_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.l_slider: ValueSlider | None = None
        self.c_slider: ValueSlider | None = None
        self.css_edit: QLineEdit | None = None
        if mode == "color":
            self._build_color_editor(right)

        self.wheel.clicked.connect(self._wheel_clicked)
        self.wheel.marker_pressed.connect(self.select)
        self.wheel.marker_moved.connect(self._set_hue)
        self.set_items(items)

    def _build_color_editor(self, lay: Any) -> None:
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        self.l_slider = ValueSlider(None, minimum=0.0, maximum=1.0, step=0.01, allow_none=True)
        self.c_slider = ValueSlider(None, minimum=0.0, maximum=0.37, step=0.005, allow_none=True)
        self.css_edit = QLineEdit()
        self.css_edit.setPlaceholderText("#rrggbb albo oklch(0.7 0.1 30)")
        form.addRow("jasność L", self.l_slider)
        form.addRow("nasycenie C", self.c_slider)
        form.addRow("kolor", self.css_edit)
        self.color_form = form
        lay.addLayout(form)
        self.l_slider.changed.connect(lambda v: self._set_channel("l", v))
        self.c_slider.changed.connect(lambda v: self._set_channel("c", v))
        self.css_edit.returnPressed.connect(self._from_css)

    # --- odczyt / zapis -------------------------------------------------------------------------

    def items(self) -> tuple[Any, ...]:
        if self.mode == "hue":
            return tuple(c.h for c in self._colors)
        return tuple(self._colors)

    def set_items(self, items: Sequence[Any]) -> None:
        """Programowo (bez sygnału)."""
        if self.mode == "hue":
            self._colors = [OKLCH(WHEEL_L, WHEEL_C, float(h) % 360.0) for h in items]
        else:
            self._colors = list(items)
        if self.selected is not None and self.selected >= len(self._colors):
            self.selected = None
        self._refresh()

    def _emit(self) -> None:
        self._refresh()
        self.changed.emit(self.items())

    def _full(self) -> bool:
        return self.max_items is not None and len(self._colors) >= self.max_items

    # --- widok ----------------------------------------------------------------------------------

    def _refresh(self) -> None:
        while len(self.rows) > len(self._colors):
            row = self.rows.pop()
            self._rows_lay.removeWidget(row)
            row.hide()
            row.deleteLater()
        while len(self.rows) < len(self._colors):
            row = _Row(self._rows_host)
            for w in (row.edit, row.remove_button, row.handle):
                w.installEventFilter(self)
            row.edit.committed.connect(lambda v, r=row: self._row_edited(r, v))
            row.remove_button.clicked.connect(
                lambda _c=False, r=row: self.remove(self.rows.index(r))
            )
            self._rows_lay.insertWidget(len(self.rows), row)
            self.rows.append(row)
        for i, (row, c) in enumerate(zip(self.rows, self._colors, strict=True)):
            row.handle.set_hex(col.to_hex(c, "oklch-chroma"))
            row.edit.set_value(float(f"{c.h:.6g}"))
            row.edit._bad(False)
            row.set_selected(i == self.selected)
        self.hint_label.setVisible(not self._colors)
        full = self._full()
        reason = f"Lista ma już najwięcej pozycji ({self.max_items})." if full else ""
        self.add_button.setEnabled(not full)
        self.add_button.setToolTip(reason)
        self.wheel.setToolTip(reason)
        self.wheel.set_state(self._colors, self.selected)
        self._refresh_editor()

    def _show_fields(self) -> None:
        """Po przestawieniu albo usunięciu pozycji wiersze pokazują inne wartości niż przed
        chwilą. Pole z fokusem nie odświeża tekstu samo (żeby nie psuć wpisywania), więc bez
        tego przy utracie fokusu zatwierdziłoby stary tekst jako nową wartość."""
        for row in self.rows:
            row.edit._show(row.edit.value())

    def _refresh_editor(self) -> None:
        if self.l_slider is None or self.c_slider is None:
            return
        chosen = self._colors[self.selected] if self.selected is not None else None
        for slider in (self.l_slider, self.c_slider):
            slider.setEnabled(chosen is not None)
        self.l_slider.set_value(None if chosen is None else chosen.l)
        self.c_slider.set_value(None if chosen is None else chosen.c)
        if chosen is not None:
            self.l_slider.bar.set_gradient(channel_gradient(chosen, "l"))
            self.c_slider.bar.set_gradient(channel_gradient(chosen, "c"))

    # --- działania ------------------------------------------------------------------------------

    def select(self, index: int | None) -> None:
        if index is not None and not 0 <= index < len(self._colors):
            index = None
        if index == self.selected:
            return
        self.selected = index
        self._refresh()

    def _new_color(self, hue: float) -> OKLCH:
        if self.mode == "hue":
            return OKLCH(WHEEL_L, WHEEL_C, hue % 360.0)
        return OKLCH(NEW_COLOR_L, NEW_COLOR_C, hue % 360.0)

    def _append(self, c: OKLCH) -> None:
        if self._full():
            return
        self._colors.append(c)
        self.selected = len(self._colors) - 1
        self._emit()

    def _wheel_clicked(self, hue: float) -> None:
        self._append(self._new_color(hue))

    def add_item(self) -> None:
        """Nowa pozycja w środku największej przerwy między odcieniami listy (pusta lista: 0°)."""
        hues = sorted(c.h for c in self._colors)
        if not hues:
            self._append(self._new_color(0.0))
            return
        gaps = [
            ((b - a) % 360.0 or 360.0, a) for a, b in zip(hues, [*hues[1:], hues[0]], strict=True)
        ]
        width, start = max(gaps, key=lambda g: g[0])
        self._append(self._new_color(float(f"{(start + width / 2) % 360.0:.6g}")))

    def remove(self, index: int) -> None:
        if not 0 <= index < len(self._colors):
            return
        focused = self.rows[index].remove_button.hasFocus()
        del self._colors[index]
        if self.selected is not None:
            if self.selected == index:
                self.selected = None
            elif self.selected > index:
                self.selected -= 1
        self._emit()
        self._show_fields()
        if focused:  # fokus zostaje na liście
            nxt = self.rows[min(index, len(self.rows) - 1)].remove_button if self.rows else None
            (nxt or self.add_button).setFocus()

    def _remove_row(self, row: _Row) -> None:
        if row in self.rows:
            self.remove(self.rows.index(row))

    def move_item(self, index: int, target: int) -> bool:
        """Przenosi pozycję ``index`` na miejsce ``target``; zaznaczenie idzie za nią."""
        n = len(self._colors)
        if index == target or not (0 <= index < n and 0 <= target < n):
            return False
        self._colors.insert(target, self._colors.pop(index))
        self.selected = target
        self._emit()
        self._show_fields()
        return True

    def _set_color(self, index: int, c: OKLCH) -> None:
        if self._colors[index] == c:
            return
        self._colors[index] = c
        self._emit()

    def _set_hue(self, index: int, hue: float) -> None:
        if 0 <= index < len(self._colors):
            c = self._colors[index]
            self._set_color(index, OKLCH(c.l, c.c, hue % 360.0))

    def _row_edited(self, row: _Row, value: float | None) -> None:
        if value is not None and row in self.rows:
            self._set_hue(self.rows.index(row), value)

    def _set_channel(self, channel: str, value: float | None) -> None:
        if self.selected is None or value is None:
            return
        c = self._colors[self.selected]
        new = OKLCH(value, c.c, c.h) if channel == "l" else OKLCH(c.l, value, c.h)
        self._set_color(self.selected, new)

    def _from_css(self) -> None:
        assert self.css_edit is not None
        try:
            c = col.from_css(self.css_edit.text().strip())
        except ValueError:
            self._css_bad(True)
            return
        self._css_bad(False)
        if self.selected is None:
            self._append(c)
        else:
            self._set_color(self.selected, c)

    def _css_bad(self, bad: bool) -> None:
        assert self.css_edit is not None
        theme.mark_error(self.css_edit, bad)
        self.css_edit.setProperty("bad", bad)

    # --- zdarzenia wierszy ----------------------------------------------------------------------

    def _row_of(self, obj: QObject) -> int | None:
        for i, row in enumerate(self.rows):
            if obj in (row.edit, row.remove_button, row.handle):
                return i
        return None

    def _row_at(self, global_pos: Any) -> int | None:
        y = self._rows_host.mapFromGlobal(global_pos).y()
        for i, row in enumerate(self.rows):
            if y < row.geometry().bottom():
                return i
        return len(self.rows) - 1 if self.rows else None

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        index = self._row_of(obj)
        if index is None:
            return super().eventFilter(obj, event)
        row = self.rows[index]
        kind = event.type()
        if kind == QEvent.Type.FocusIn:
            self.select(index)
        elif kind == QEvent.Type.KeyPress:
            key, mods = event.key(), event.modifiers()  # ty: ignore[unresolved-attribute]
            if mods & Qt.KeyboardModifier.AltModifier and key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                target = index + (-1 if key == Qt.Key.Key_Up else 1)
                field = "edit" if obj is row.edit else "remove_button"
                if self.move_item(index, target):
                    getattr(self.rows[target], field).setFocus()
                return True
            if key == Qt.Key.Key_Delete and obj is row.remove_button:
                self.remove(index)
                return True
        elif obj is row.handle:
            return self._handle_event(index, event)
        return super().eventFilter(obj, event)

    def _handle_event(self, index: int, event: QEvent) -> bool:
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress:
            self._drag_row = index
            self.select(index)
            return True
        if kind == QEvent.Type.MouseMove and self._drag_row is not None:
            target = self._row_at(event.globalPosition().toPoint())  # ty: ignore[unresolved-attribute]
            if target is not None and self.move_item(self._drag_row, target):
                self._drag_row = target
            return True
        if kind == QEvent.Type.MouseButtonRelease:
            self._drag_row = None
            return True
        return False
