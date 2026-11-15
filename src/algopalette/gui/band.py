"""Suwak zakresu z zakazanymi przedziałami — jasność, nasycenie i odcień w zakładce „Zasady”.

Wiersz 1: zakres dozwolony (``RangeSlider``: pole „od”, pasek z dwoma uchwytami, pole „do”), a na
osi okrężnej z ``center_fields`` dodatkowo ten sam łuk zapisany jako „środek ± połowa szerokości”
(dwa zapisy jednej wartości — edycja jednego przelicza drugi).
Wiersz 2: zakazane przedziały — pozycja „od – do ✕” na każdy i przycisk „+ zakaz”. Zakazy są
kreskowane na pasku.

Klawiatura: Tab przechodzi po polach, Enter zatwierdza pole, Delete na przycisku ✕ pozycji usuwa
zakaz, spacja na „+ zakaz” dodaje.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QToolButton, QWidget

from algopalette.gui.widgets import Gradient, NumEdit, RangeSlider, vbox
from algopalette.model import Exclusions, arc_center_half, arc_from_center

NEW_EXCLUSION_FRACTION = 0.1  # szerokość nowego zakazu jako część zakresu osi


class _Item(QWidget):
    """Jedna pozycja listy zakazów: pola „od” i „do” oraz przycisk usunięcia."""

    def __init__(self, pair: tuple[float, float], kw: dict[str, Any], parent: QWidget) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.lo_edit = NumEdit(pair[0], width=58, **kw)
        self.hi_edit = NumEdit(pair[1], width=58, **kw)
        self.remove_button = QToolButton()
        self.remove_button.setText("✕")
        self.remove_button.setAutoRaise(True)
        self.remove_button.setAccessibleName("usuń zakazany przedział")
        lay.addWidget(self.lo_edit)
        lay.addWidget(QLabel("–"))
        lay.addWidget(self.hi_edit)
        lay.addWidget(self.remove_button)

    def pair(self) -> tuple[float | None, float | None]:
        return self.lo_edit.value(), self.hi_edit.value()


class BandSlider(QWidget):
    """Zakres dozwolony + zakazane przedziały. ``changed(lo, hi, exclude)`` przy każdej zmianie.

    ``exclude`` w sygnale i w ``values()`` jest posortowane według „od”. Para z „od” ≥ „do” na osi
    liniowej (albo „od” = „do” na okrężnej) jest odrzucana: pole dostaje oznaczenie błędu, sygnał
    nie wychodzi, a wartość zostaje poprzednia.
    """

    changed = Signal(object, object, object)

    def __init__(
        self,
        lo: float | None,
        hi: float | None,
        exclude: Exclusions = (),
        *,
        minimum: float,
        maximum: float,
        step: float,
        fmt: str = ".3f",
        wrap: bool = False,
        allow_none: bool = False,
        gradient: Gradient | None = None,
        center_fields: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.minimum, self.maximum, self.step, self.wrap = minimum, maximum, step, wrap
        self._edit_kw: dict[str, Any] = {
            "fmt": fmt,
            "minimum": minimum,
            "maximum": maximum,
            "step": step,
            "wrap": wrap,
        }
        self._exclude: list[tuple[float, float]] = []
        self.items: list[_Item] = []

        lay = vbox(self, spacing=4)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self.range = RangeSlider(
            lo,
            hi,
            minimum=minimum,
            maximum=maximum,
            step=step,
            fmt=fmt,
            wrap=wrap,
            allow_none=allow_none,
            gradient=gradient,
        )
        self.bar = self.range.bar
        top.addWidget(self.range, 1)
        self.center_edit: NumEdit | None = None
        self.half_edit: NumEdit | None = None
        if center_fields:
            self.center_edit = NumEdit(0.0, width=58, **self._edit_kw)
            self.half_edit = NumEdit(0.0, fmt=fmt, minimum=0.0, maximum=180.0, step=step, width=58)
            self.center_label, self.half_label = QLabel("środek"), QLabel("±")
            for w in (self.center_label, self.center_edit, self.half_label, self.half_edit):
                top.addWidget(w)
            self.center_edit.committed.connect(self._from_center)
            self.half_edit.committed.connect(self._from_center)
        lay.addLayout(top)

        self._row = QHBoxLayout()
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(8)
        self.exclude_label = QLabel("zakazane:")
        self._row.addWidget(self.exclude_label)
        self.add_button = QPushButton("+ zakaz")
        self.add_button.clicked.connect(self.add_exclusion)
        self._row.addWidget(self.add_button)
        self._row.addStretch(1)
        lay.addLayout(self._row)

        self.range.changed.connect(self._from_range)
        self._set_exclusions(exclude)
        self._sync_center()

    # --- odczyt / zapis -------------------------------------------------------------------------

    def values(self) -> tuple[float | None, float | None, Exclusions]:
        lo, hi = self.range.values()
        return lo, hi, tuple(sorted(self._exclude))

    def set_values(self, lo: float | None, hi: float | None, exclude: Exclusions) -> None:
        """Programowo (bez sygnału). Ta sama liczba zakazów → te same widżety (fokus zostaje)."""
        self.range.set_values(lo, hi)
        self._set_exclusions(exclude)
        self._sync_center()

    def set_gradient(self, gradient: Gradient | None) -> None:
        self.bar.set_gradient(gradient)

    def _emit(self) -> None:
        self.changed.emit(*self.values())

    # --- zakres ---------------------------------------------------------------------------------

    def _from_range(self, _lo: float | None, _hi: float | None) -> None:
        self._sync_center()
        self._emit()

    def _sync_center(self) -> None:
        if self.center_edit is None or self.half_edit is None:
            return
        lo, hi = self.range.values()
        if lo is None or hi is None:
            return
        center, half = arc_center_half(lo, hi)
        self.center_edit.set_value(float(f"{center:.6g}"))
        self.half_edit.set_value(float(f"{half:.6g}"))

    def _from_center(self, _value: float | None) -> None:
        assert self.center_edit is not None and self.half_edit is not None
        center, half = self.center_edit.value(), self.half_edit.value()
        if center is None or half is None:
            return
        lo, hi = arc_from_center(center, half)
        self.range.set_values(float(f"{lo:.6g}"), float(f"{hi:.6g}"))
        self._emit()

    # --- zakazy ---------------------------------------------------------------------------------

    def _valid(self, pair: tuple[float | None, float | None]) -> bool:
        a, b = pair
        if a is None or b is None:
            return False
        if self.wrap:
            span = self.maximum - self.minimum
            return (a - self.minimum) % span != (b - self.minimum) % span
        return a < b

    def _set_exclusions(self, exclude: Exclusions) -> None:
        pairs = [(float(a), float(b)) for a, b in exclude]
        if len(pairs) == len(self.items):
            for item, (a, b) in zip(self.items, pairs, strict=True):
                item.lo_edit.set_value(a)
                item.hi_edit.set_value(b)
                item.lo_edit._bad(False)
                item.hi_edit._bad(False)
        else:
            for item in self.items:
                self._drop_widget(item)
            self.items = []
            for pair in pairs:
                self._append_item(pair)
        self._exclude = pairs
        self.bar.set_excluded(tuple(pairs))

    def _append_item(self, pair: tuple[float, float]) -> _Item:
        item = _Item(pair, self._edit_kw, self)
        item.lo_edit.committed.connect(lambda _v, it=item: self._item_edited(it, it.lo_edit))
        item.hi_edit.committed.connect(lambda _v, it=item: self._item_edited(it, it.hi_edit))
        item.remove_button.clicked.connect(lambda _checked=False, it=item: self._remove(it))
        item.remove_button.installEventFilter(self)
        self._row.insertWidget(self._row.indexOf(self.add_button), item)
        self.items.append(item)
        return item

    def _drop_widget(self, item: _Item) -> None:
        item.remove_button.removeEventFilter(self)
        self._row.removeWidget(item)
        item.hide()
        item.deleteLater()

    def _item_edited(self, item: _Item, edit: NumEdit) -> None:
        pair = item.pair()
        if not self._valid(pair):
            edit._bad(True)
            return
        item.lo_edit._bad(False)
        item.hi_edit._bad(False)
        a, b = pair
        assert a is not None and b is not None
        self._exclude[self.items.index(item)] = (a, b)
        self.bar.set_excluded(tuple(self._exclude))
        self._emit()

    def _remove(self, item: _Item) -> None:
        if item not in self.items:
            return
        k = self.items.index(item)
        had_focus = item.remove_button.hasFocus()
        del self.items[k]
        del self._exclude[k]
        self._drop_widget(item)
        self.bar.set_excluded(tuple(self._exclude))
        if had_focus:  # fokus nie ucieka z listy zakazów
            nxt = self.items[min(k, len(self.items) - 1)].remove_button if self.items else None
            (nxt or self.add_button).setFocus()
        self._emit()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Delete:  # ty: ignore[unresolved-attribute]
            for item in self.items:
                if item.remove_button is obj:
                    self._remove(item)
                    return True
        return super().eventFilter(obj, event)

    def add_exclusion(self) -> None:
        """Nowy zakaz o szerokości 10% osi w środku największej wolnej luki dozwolonego zakresu."""
        pair = self._new_exclusion()
        if pair is None:
            return
        self._exclude.append(pair)
        self._append_item(pair)
        self.bar.set_excluded(tuple(self._exclude))
        self._emit()

    def _free_gaps(self) -> tuple[float, list[tuple[float, float]]]:
        """Początek dozwolonego zakresu i wolne luki jako odcinki liczone od tego początku."""
        lo, hi = self.range.values()
        start = self.minimum if lo is None else lo
        end = self.maximum if hi is None else hi
        span = self.maximum - self.minimum
        if self.wrap:
            width = (end - start) % span
            if width == 0.0 and start != end:
                width = span  # pełne koło
            taken: list[tuple[float, float]] = []
            for a, b in self._exclude:
                off = (a - start) % span
                w = (b - a) % span
                for shift in (-span, 0.0):
                    x0, x1 = max(0.0, off + shift), min(width, off + shift + w)
                    if x1 > x0:
                        taken.append((x0, x1))
        else:
            width = max(end - start, 0.0)
            taken = [
                (max(a - start, 0.0), min(b - start, width))
                for a, b in self._exclude
                if min(b - start, width) > max(a - start, 0.0)
            ]
        gaps: list[tuple[float, float]] = []
        cursor = 0.0
        for x0, x1 in sorted(taken):
            if x0 > cursor:
                gaps.append((cursor, x0))
            cursor = max(cursor, x1)
        if cursor < width:
            gaps.append((cursor, width))
        seam = self.wrap and width == span and len(gaps) >= 2
        if seam and gaps[0][0] == 0.0 and gaps[-1][1] == width:
            first = gaps.pop(0)  # pełne koło: luka przechodzi przez szew
            last = gaps.pop()
            gaps.append((last[0], width + first[1]))
        return start, gaps

    def _new_exclusion(self) -> tuple[float, float] | None:
        start, gaps = self._free_gaps()
        if not gaps:
            return None
        g0, g1 = max(gaps, key=lambda g: g[1] - g[0])
        gap = g1 - g0
        width = NEW_EXCLUSION_FRACTION * (self.maximum - self.minimum)
        if width > gap:
            width = gap / 2
        mid = start + (g0 + g1) / 2
        a, b = self.bar.snap(mid - width / 2), self.bar.snap(mid + width / 2)
        if self.wrap:
            span = self.maximum - self.minimum
            a = self.minimum + (a - self.minimum) % span
            b = self.minimum + (b - self.minimum) % span
        return (a, b) if self._valid((a, b)) else None
