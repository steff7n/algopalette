"""Widżety GUI: próbki koloru, pola liczb, suwaki wartości i zakresu z gradientem, znacznik źródła.

Suwak = pole liczby + pasek [+ drugie pole]. Pasek: ←/→ krok, Shift = ×10, Ctrl = ×0.1, Home/End =
skraj, spacja = przełącz uchwyt (zakres); mysz: klik/przeciąganie przesuwa najbliższy uchwyt,
kółko = krok. Pole liczby: Enter lub wyjście z pola zatwierdza, ↑/↓ = krok; puste pole w zakresie
= brak ograniczenia z tej strony (gdy ``allow_none``).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from algopalette.color import fast
from algopalette.model import OKLCH

# --- kolory ------------------------------------------------------------------------------------


def qcolor(hex_: str) -> QColor:
    return QColor(hex_)


def lch_to_qcolors(lch: np.ndarray) -> list[QColor]:
    """Szybki podgląd (numpy, przycięcie do sRGB) — tylko do gradientów i tła wykresów."""
    lin = np.clip(fast.oklch_to_linear_srgb(lch), 0.0, 1.0)
    srgb = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
    rgb = np.clip(np.round(srgb * 255), 0, 255).astype(int)
    return [QColor(int(r), int(g), int(b)) for r, g, b in rgb.reshape(-1, 3)]


Gradient = Callable[[np.ndarray], list[QColor]]  # wartości osi (N,) → kolory (N)


def channel_gradient(base: OKLCH, channel: str, rel: bool = False) -> Gradient:
    """Gradient paska: ``base`` z jedną zmienianą składową (``l``/``c``/``h``).

    ``rel``: oś C jako ułamek maksymalnego nasycenia w sRGB przy (L, H) bazy.
    """

    def make(xs: np.ndarray) -> list[QColor]:
        n = len(xs)
        lch = np.tile(np.array([base.l, base.c, base.h], dtype=float), (n, 1))
        if channel == "l":
            lch[:, 0] = xs
        elif channel == "c":
            if rel:
                m = fast.max_chroma(np.full(n, base.l), np.full(n, base.h))
                lch[:, 1] = xs * m
            else:
                lch[:, 1] = xs
        else:
            lch[:, 2] = xs
        return lch_to_qcolors(lch)

    return make


def parse_finite(text: str) -> float:
    """Liczba z pola tekstowego (przecinek OK). ``inf``/``nan`` → ``ValueError``."""
    v = float(text.strip().replace(",", "."))
    if not math.isfinite(v):
        raise ValueError(f"Wartość musi być skończoną liczbą: {text!r}")
    return v


# --- proste widżety ----------------------------------------------------------------------------


class Swatch(QFrame):
    """Prostokąt w kolorze ``hex``."""

    def __init__(self, hex_: str = "#000000", size: QSize | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.Box)
        self.setLineWidth(1)
        s = size or QSize(28, 18)
        self.setFixedSize(s)
        self.set_hex(hex_)

    def set_hex(self, hex_: str) -> None:
        self.hex = hex_
        self.setStyleSheet(f"background: {hex_}; border: 1px solid palette(mid);")
        self.setToolTip(hex_)


SOURCE_LABELS = {"mood": "nastrój", "global": "globalne", "slot": "własne"}
SOURCE_COLORS = {"mood": "#b26bd6", "global": "#3fa7c4", "slot": "#d6a000"}


def source_badge(src: str | None) -> QLabel:
    lbl = QLabel("" if src is None else SOURCE_LABELS.get(src, src))
    if src is not None:
        c = SOURCE_COLORS.get(src, "#888")
        lbl.setStyleSheet(
            f"color: {c}; border: 1px solid {c}; border-radius: 6px; padding: 0 6px;"
            " font-size: 11px;"
        )
        lbl.setToolTip(
            {
                "mood": "wartość ustawił nastrój",
                "global": "wartość z ustawień globalnych (zmieniona ręcznie)",
                "slot": "wartość ustawiona w tym kolorze",
            }.get(src, "")
        )
    lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return lbl


def section(title: str) -> QLabel:
    lbl = QLabel(title)
    f = lbl.font()
    f.setBold(True)
    f.setPointSizeF(f.pointSizeF() * 1.1)
    lbl.setFont(f)
    lbl.setContentsMargins(0, 10, 0, 2)
    return lbl


def hint(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: palette(placeholder-text);")
    return lbl


def hbox(*widgets: QWidget | None, stretch: bool = True, spacing: int = 6) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for x in widgets:
        if x is not None:
            lay.addWidget(x)
    if stretch:
        lay.addStretch(1)
    return w


def form() -> tuple[QWidget, QFormLayout]:
    w = QWidget()
    lay = QFormLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    lay.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    return w, lay


def clear_layout(lay) -> None:
    while lay.count():
        item = lay.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()
            w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def vbox(parent: QWidget | None = None, margins: int = 0, spacing: int = 6) -> QVBoxLayout:
    lay = QVBoxLayout(parent) if parent is not None else QVBoxLayout()
    lay.setContentsMargins(margins, margins, margins, margins)
    lay.setSpacing(spacing)
    return lay


# --- pole liczby -------------------------------------------------------------------------------


class NumEdit(QLineEdit):
    """Pole liczby: Enter / wyjście z pola zatwierdza, ↑/↓ krok (Shift ×10, Ctrl ×0.1).

    ``committed(value)`` — tylko przy zmianie; ``value`` = ``None`` dla pustego pola, gdy
    ``allow_none``. Błędny tekst → czerwona ramka, wartość bez zmian.
    """

    committed = Signal(object)

    def __init__(
        self,
        value: float | None,
        *,
        fmt: str = "g",
        minimum: float | None = None,
        maximum: float | None = None,
        step: float = 0.0,
        allow_none: bool = False,
        integer: bool = False,
        wrap: bool = False,
        width: int = 72,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.fmt, self.minimum, self.maximum = fmt, minimum, maximum
        self.step, self.allow_none, self.integer, self.wrap = step, allow_none, integer, wrap
        self._value = value
        self.setFixedWidth(width)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        if allow_none:
            self.setPlaceholderText("brak")
        self._show(value)
        self.editingFinished.connect(self._commit)

    def value(self) -> float | None:
        return self._value

    def _show(self, v: float | None) -> None:
        self.setText("" if v is None else format(v, self.fmt))
        self._bad(False)

    def set_value(self, v: float | None) -> None:
        """Programowo (bez sygnału)."""
        self._value = v
        if not self.hasFocus():
            self._show(v)

    def _bad(self, bad: bool) -> None:
        self.setStyleSheet("border: 2px solid #d04040;" if bad else "")
        self.setProperty("bad", bad)

    def _clamp(self, v: float) -> float:
        lo, hi = self.minimum, self.maximum
        if self.wrap and lo is not None and hi is not None:
            if v == hi:
                return v
            return lo + (v - lo) % (hi - lo)
        if lo is not None:
            v = max(v, lo)
        if hi is not None:
            v = min(v, hi)
        return v

    def _parse(self) -> tuple[bool, float | None]:
        raw = self.text().strip()
        if raw == "":
            return (True, None) if self.allow_none else (False, None)
        try:
            v = parse_finite(raw)
        except ValueError:
            return False, None
        if self.integer:
            if v != int(v):
                return False, None
            v = int(v)
        if not self.wrap and (
            (self.minimum is not None and v < self.minimum)
            or (self.maximum is not None and v > self.maximum)
        ):
            if self.integer:
                return False, None
            v = self._clamp(v)
        return True, self._clamp(v) if self.wrap else v

    def _commit(self) -> None:
        ok, v = self._parse()
        if not ok:
            self._bad(True)
            return
        self._bad(False)
        self._show(v)
        if v != self._value:
            self._value = v
            self.committed.emit(v)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if self.step and e.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            mult = 10.0 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0
            if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
                mult = 0.1
            sign = 1 if e.key() == Qt.Key.Key_Up else -1
            ok, cur = self._parse()
            base = cur if ok and cur is not None else (self._value or self.minimum or 0.0)
            v = self._clamp(base + sign * self.step * mult)
            v = float(f"{v:.6g}")
            self.setText(format(v, self.fmt))
            self._commit()
            return
        super().keyPressEvent(e)


# --- pasek suwaka ------------------------------------------------------------------------------

HANDLE_R = 7
GRADIENT_STOPS = 48


class Bar(QWidget):
    """Pasek z jednym albo dwoma uchwytami; tło może być gradientem koloru.

    ``moved(handle, value)`` przy każdej zmianie myszą/klawiaturą. ``wrap``: oś okrężna (odcień);
    przy dwóch uchwytach lo > hi oznacza zakres przez 0.
    """

    moved = Signal(int, float)

    def __init__(
        self,
        values: Sequence[float | None],
        *,
        minimum: float,
        maximum: float,
        step: float,
        wrap: bool = False,
        gradient: Gradient | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.values: list[float | None] = list(values)
        self.minimum, self.maximum, self.step, self.wrap = minimum, maximum, step, wrap
        self.gradient = gradient
        self._stops: list[QColor] | None = None
        self.active = 0
        self._drag = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(140)
        self.setFixedHeight(2 * HANDLE_R + 8)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_gradient(self, gradient: Gradient | None) -> None:
        self.gradient = gradient
        self._stops = None
        self.update()

    def set_values(self, values: Sequence[float | None]) -> None:
        self.values = list(values)
        self.update()

    # geometria
    def _track(self) -> QRectF:
        return QRectF(HANDLE_R + 1, self.height() / 2 - 5, self.width() - 2 * HANDLE_R - 2, 10)

    def _x(self, v: float) -> float:
        t = self._track()
        span = (self.maximum - self.minimum) or 1.0
        return t.left() + (v - self.minimum) / span * t.width()

    def _value_at(self, x: float) -> float:
        t = self._track()
        frac = min(max((x - t.left()) / max(t.width(), 1.0), 0.0), 1.0)
        return self.snap(self.minimum + frac * (self.maximum - self.minimum))

    def snap(self, v: float) -> float:
        if self.step > 0:
            v = round(v / self.step) * self.step
        return float(f"{v:.6g}") if v else 0.0

    def _default(self, k: int) -> float:
        return self.minimum if k == 0 else self.maximum

    def clamp(self, v: float, k: int) -> float:
        if self.wrap:
            if v == self.maximum and len(self.values) == 2 and k == 1:
                return v  # 360 w górnym uchwycie = pełne koło, nie 0
            span = self.maximum - self.minimum
            return self.minimum + (v - self.minimum) % span
        return min(max(v, self.minimum), self.maximum)

    # rysowanie
    def paintEvent(self, e: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self._track()
        pal = self.palette()
        if self.gradient is not None:
            if self._stops is None:
                xs = np.linspace(self.minimum, self.maximum, GRADIENT_STOPS)
                self._stops = self.gradient(xs)
            g = QLinearGradient(t.left(), 0, t.right(), 0)
            for i, c in enumerate(self._stops):
                g.setColorAt(i / (len(self._stops) - 1), c)
            p.setBrush(QBrush(g))
        else:
            p.setBrush(pal.mid())
        p.setPen(QPen(pal.dark().color(), 1))
        p.drawRoundedRect(t, 4, 4)

        vals = self.values
        if len(vals) == 2:
            a = vals[0] if vals[0] is not None else self.minimum
            b = vals[1] if vals[1] is not None else self.maximum
            hl = pal.highlight().color()
            if self.gradient is not None:
                # poza zakresem przyciemniamy gradient
                shade = QColor(0, 0, 0, 150)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(shade)
                for lo, hi in self._outside(a, b):
                    p.drawRect(QRectF(self._x(lo), t.top(), self._x(hi) - self._x(lo), t.height()))
            else:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(hl)
                for lo, hi in self._inside(a, b):
                    p.drawRect(QRectF(self._x(lo), t.top(), self._x(hi) - self._x(lo), t.height()))
        for k, v in enumerate(vals):
            x = self._x(v if v is not None else self._default(k))
            center = QPointF(x, self.height() / 2)
            focus = self.hasFocus() and k == self.active
            p.setPen(QPen(pal.highlight().color() if focus else QColor("#202020"), 2.5))
            p.setBrush(QColor("#f4f4f4") if v is not None else Qt.BrushStyle.NoBrush)
            r = HANDLE_R if v is not None else HANDLE_R - 2
            p.drawEllipse(center, r, r)
        p.end()

    def _inside(self, a: float, b: float) -> list[tuple[float, float]]:
        if a <= b or not self.wrap:
            return [(min(a, b), max(a, b))]
        return [(a, self.maximum), (self.minimum, b)]

    def _outside(self, a: float, b: float) -> list[tuple[float, float]]:
        if a <= b or not self.wrap:
            lo, hi = min(a, b), max(a, b)
            return [(self.minimum, lo), (hi, self.maximum)]
        return [(b, a)]

    # sterowanie
    def set_active_value(self, v: float) -> None:
        v = float(f"{self.clamp(v, self.active):.6g}")
        if self.values[self.active] == v:
            return
        self.values[self.active] = v
        if not self.wrap and len(self.values) == 2:
            lo, hi = self.values
            if lo is not None and hi is not None and lo > hi:
                other = 1 - self.active
                self.values[other] = v
                self.moved.emit(other, v)
        self.update()
        self.moved.emit(self.active, v)

    def nudge(self, mult: float) -> None:
        cur = self.values[self.active]
        if cur is None:
            cur = self._default(self.active)
        self.set_active_value(cur + self.step * mult)

    def _pick_nearest(self, v: float) -> None:
        if len(self.values) < 2:
            self.active = 0
            return
        d = [abs((x if x is not None else self._default(i)) - v) for i, x in enumerate(self.values)]
        self.active = 0 if d[0] <= d[1] else 1

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self.setFocus()
        self._drag = True
        v = self._value_at(e.position().x())
        self._pick_nearest(v)
        self.set_active_value(v)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag:
            self.set_active_value(self._value_at(e.position().x()))

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        self._drag = False

    def wheelEvent(self, e: QWheelEvent) -> None:
        if not self.hasFocus():
            e.ignore()  # przewijanie strony nie zmienia wartości przypadkiem
            return
        self.nudge(1 if e.angleDelta().y() > 0 else -1)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        k, mods = e.key(), e.modifiers()
        mult = 1.0
        if mods & Qt.KeyboardModifier.ShiftModifier:
            mult = 10.0
        elif mods & Qt.KeyboardModifier.ControlModifier:
            mult = 0.1
        if k in (Qt.Key.Key_Left, Qt.Key.Key_Down):
            self.nudge(-mult)
        elif k in (Qt.Key.Key_Right, Qt.Key.Key_Up):
            self.nudge(mult)
        elif k == Qt.Key.Key_Home:
            self.set_active_value(self.minimum)
        elif k == Qt.Key.Key_End:
            self.set_active_value(self.maximum)
        elif k == Qt.Key.Key_Space and len(self.values) == 2:
            self.active = 1 - self.active
            self.update()
        else:
            super().keyPressEvent(e)

    def sizeHint(self) -> QSize:
        return QSize(220, 2 * HANDLE_R + 8)


class ValueSlider(QWidget):
    """Jedna wartość: pole + pasek. ``changed(value)``."""

    changed = Signal(object)

    def __init__(
        self,
        value: float | None,
        *,
        minimum: float,
        maximum: float,
        step: float,
        fmt: str = ".3f",
        wrap: bool = False,
        allow_none: bool = False,
        gradient: Gradient | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = NumEdit(
            value,
            fmt=fmt,
            minimum=minimum,
            maximum=maximum,
            step=step,
            wrap=wrap,
            allow_none=allow_none,
        )
        self.bar = Bar(
            [value], minimum=minimum, maximum=maximum, step=step, wrap=wrap, gradient=gradient
        )
        lay.addWidget(self.edit)
        lay.addWidget(self.bar, 1)
        self.edit.committed.connect(self._from_edit)
        self.bar.moved.connect(self._from_bar)

    def value(self) -> float | None:
        return self.bar.values[0]

    def set_value(self, v: float | None) -> None:
        self.edit.set_value(v)
        self.bar.set_values([v])

    def _from_edit(self, v: float | None) -> None:
        self.bar.set_values([v])
        self.changed.emit(v)

    def _from_bar(self, _k: int, v: float) -> None:
        self.edit.set_value(v)
        self.changed.emit(v)


class RangeSlider(QWidget):
    """Zakres [lo, hi]: pole, pasek z dwoma uchwytami, pole. ``changed(lo, hi)``."""

    changed = Signal(object, object)

    def __init__(
        self,
        lo: float | None,
        hi: float | None,
        *,
        minimum: float,
        maximum: float,
        step: float,
        fmt: str = ".3f",
        wrap: bool = False,
        allow_none: bool = False,
        gradient: Gradient | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        kw: dict[str, Any] = {
            "fmt": fmt,
            "minimum": minimum,
            "maximum": maximum,
            "step": step,
            "wrap": wrap,
            "allow_none": allow_none,
        }
        self.lo_edit = NumEdit(lo, **kw)
        self.hi_edit = NumEdit(hi, **kw)
        self.bar = Bar(
            [lo, hi], minimum=minimum, maximum=maximum, step=step, wrap=wrap, gradient=gradient
        )
        lay.addWidget(self.lo_edit)
        lay.addWidget(self.bar, 1)
        lay.addWidget(self.hi_edit)
        self.wrap = wrap
        self.lo_edit.committed.connect(lambda v: self._from_edit(0, v))
        self.hi_edit.committed.connect(lambda v: self._from_edit(1, v))
        self.bar.moved.connect(self._from_bar)

    def values(self) -> tuple[float | None, float | None]:
        lo, hi = self.bar.values
        return lo, hi

    def _sync_edits(self) -> None:
        lo, hi = self.bar.values
        self.lo_edit.set_value(lo)
        self.hi_edit.set_value(hi)

    def _from_edit(self, k: int, v: float | None) -> None:
        vals = list(self.bar.values)
        vals[k] = v
        lo, hi = vals
        if not self.wrap and lo is not None and hi is not None and lo > hi:
            vals[1 - k] = v
        self.bar.set_values(vals)
        self._sync_edits()
        self.changed.emit(*vals)

    def _from_bar(self, _k: int, _v: float) -> None:
        self._sync_edits()
        self.changed.emit(*self.bar.values)
