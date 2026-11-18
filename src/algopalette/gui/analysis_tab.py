"""Zakładka „Analiza”: koło odcieni, przekrój jasność–nasycenie, macierz ΔE / kontrastu, próbki
„Aa” na tle.

Koło odcieni: 0° po prawej, kąty rosną przeciwnie do ruchu wskazówek zegara (90° u góry); odległość
od środka = nasycenie względne (C / maxC w sRGB). Tło koła i wykresu to prawdziwe kolory OKLCH.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from algopalette import color as col
from algopalette import engine
from algopalette.color import fast
from algopalette.engine import slot_label
from algopalette.gui import help, theme
from algopalette.gui.widgets import combo, hbox, hint, section, vbox
from algopalette.model import OKLCH, HueArc, Session, arc_width, role_of, slot_index

if TYPE_CHECKING:
    from algopalette.gui.app import MainWindow

MATRICES = [("ΔE akcentów", "de"), ("kontrast par akcentów", "contrast")]
AXES = [("C względne", "rel"), ("C bezwzględne", "abs")]
BG_OPACITY = 0.45


def hue_segments(arc: HueArc) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Łuk zasady odcienia pocięty zakazami: ``(dozwolone, zakazane)`` jako pary
    ``(początek°, rozpiętość°)``, w kolejności wzdłuż łuku (od ``lo`` w stronę rosnących kątów)."""
    width = arc_width(arc.lo, arc.hi)
    taken: list[tuple[float, float]] = []
    for a, b in arc.exclude:
        offset, span = (a - arc.lo) % 360.0, (b - a) % 360.0
        for shift in (-360.0, 0.0):
            x0, x1 = max(0.0, offset + shift), min(width, offset + shift + span)
            if x1 > x0:
                taken.append((x0, x1))
    allowed: list[tuple[float, float]] = []
    banned: list[tuple[float, float]] = []
    cursor = 0.0
    for x0, x1 in sorted(taken):
        if x0 > cursor:
            allowed.append((cursor, x0))
        if x1 > cursor:
            banned.append((max(x0, cursor), x1))
            cursor = x1
    if cursor < width or not taken:
        allowed.append((cursor, width))

    def place(parts: list[tuple[float, float]]) -> list[tuple[float, float]]:
        return [((arc.lo + x0) % 360.0, x1 - x0) for x0, x1 in parts]

    return place(allowed), place(banned)


def draw_point(p: QPainter, pt: QPointF, hex_: str, label: str, selected: bool) -> None:
    """Punkt koloru: biały i czarny pierścień (czytelny na każdym tle) + numer z obwódką."""
    rad = 10.0 if selected else 7.5
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor("#ffffff"), 5 if selected else 3.5))
    p.drawEllipse(pt, rad, rad)
    p.setBrush(QColor(hex_))
    p.setPen(QPen(QColor("#000000"), 2 if selected else 1.2))
    p.drawEllipse(pt, rad, rad)
    box = QRectF(pt.x() + rad + 1, pt.y() - rad - 14, 28, 16)
    p.setPen(QColor("#ffffff"))
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        p.drawText(box.translated(dx, dy), label)
    p.setPen(QColor("#000000"))
    p.drawText(box, label)


def _window_color() -> QColor:
    """Kolor okna z palety aplikacji (widżet dostaje nową paletę z opóźnieniem)."""
    return QApplication.palette().window().color()


def _hex(session: Session, c: OKLCH) -> str:
    return col.to_hex(c, session.globals.fit_method)


def rel_chroma(c: OKLCH) -> float:
    m = col.max_chroma(c.l, c.h)
    return min(c.c / m, 1.0) if m > 1e-9 else 0.0


def _to_image(lch: np.ndarray, mask: np.ndarray, empty: QColor) -> QImage:
    """Tablica OKLCH (H, W, 3) → QImage; ``mask`` False = piksel pusty."""
    h, w, _ = lch.shape
    flat = lch.reshape(-1, 3)
    lin = np.clip(fast.oklch_to_linear_srgb(flat), 0.0, 1.0)
    srgb = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
    rgb = np.clip(np.round(srgb * 255), 0, 255).astype(np.uint8).reshape(h, w, 3)
    rgb[~mask] = (empty.red(), empty.green(), empty.blue())
    rgb = np.ascontiguousarray(rgb)
    img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return img.copy()


class HueWheel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.session: Session | None = None
        self.selected: str | None = None
        self.targets: dict[str, float] = {}
        self._bg: QImage | None = None
        self._bg_key: tuple | None = None
        self.setMinimumSize(QSize(320, 320))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_state(
        self,
        session: Session,
        selected: str | None,
        targets: dict[str, float] | None = None,
    ) -> None:
        self.session, self.selected = session, selected
        self.targets = dict(targets or {})
        self.update()

    def _arc(self, p: QPainter, radius: float, start: float, span: float, pen: QPen) -> None:
        center, _ = self._geometry()
        p.setPen(pen)
        box = QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius)
        p.drawArc(box, int(start * 16), int(max(span, 1.0) * 16))  # choćby 1°, żeby było widać

    def _geometry(self) -> tuple[QPointF, float]:
        r = min(self.width(), self.height()) / 2 - 26
        return QPointF(self.width() / 2, self.height() / 2), max(r, 20)

    def _background(self, size: int) -> QImage:
        assert self.session is not None
        key = (size, _window_color().rgb())
        if self._bg is not None and self._bg_key == key:
            return self._bg
        ys, xs = np.mgrid[0:size, 0:size]
        cx = cy = (size - 1) / 2
        dx, dy = (xs - cx) / cx, (cy - ys) / cy
        r = np.hypot(dx, dy)
        h = np.degrees(np.arctan2(dy, dx)) % 360
        L = 0.75
        maxc = fast.max_chroma(np.full(360, L), np.arange(360.0))
        c = np.minimum(r, 1.0) * maxc[np.round(h).astype(int) % 360]
        lch = np.stack([np.full_like(r, L), c, h], axis=-1)
        img = _to_image(lch, r <= 1.0, _window_color())
        self._bg, self._bg_key = img, key
        return img

    def _point(self, hue: float, radius: float) -> QPointF:
        center, R = self._geometry()
        a = math.radians(hue)
        return QPointF(center.x() + radius * R * math.cos(a), center.y() - radius * R * math.sin(a))

    def paintEvent(self, _e) -> None:
        if self.session is None:
            return
        s = self.session
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        center, R = self._geometry()
        size = int(2 * R)
        p.setOpacity(BG_OPACITY)  # przygaszone tło: punkty nie zlewają się z kolorem pod nimi
        p.drawImage(QRectF(center.x() - R, center.y() - R, size, size), self._background(size))
        p.setOpacity(1.0)
        p.setPen(QPen(self.palette().mid().color(), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(center, R, R)
        p.drawEllipse(center, R / 2, R / 2)
        # opisy kątów
        p.setPen(self.palette().text().color())
        for deg in (0, 90, 180, 270):
            pt = self._point(deg, 1.0)
            off = QPointF(math.cos(math.radians(deg)) * 16, -math.sin(math.radians(deg)) * 12)
            p.drawText(
                QRectF(pt.x() + off.x() - 20, pt.y() + off.y() - 8, 40, 16),
                Qt.AlignmentFlag.AlignCenter,
                f"{deg}°",
            )
        # zasada odcienia zaznaczonego koloru: dozwolone kawałki łuku i wycięte z niego zakazy;
        # dalej od koła — cel z układu odcieni ± tolerancja (gdy kolor go stosuje)
        if self.selected is not None and self.selected in {x.id for x in s.slots}:
            index = slot_index(s, self.selected)
            slot = s.slots[index]
            tc = theme.colors()
            flat = Qt.PenCapStyle.FlatCap
            rule = slot.rules.hue
            if rule is not None and rule.enabled:
                allowed, banned = hue_segments(rule.value)
                for start, span in allowed:
                    pen = QPen(QColor(tc.arc_range), 5, Qt.PenStyle.SolidLine, flat)
                    self._arc(p, R + 6, start, span, pen)
                for start, span in banned:
                    self._arc(p, R + 6, start, span, QPen(QColor(tc.hard), 3, Qt.PenStyle.DotLine))
            target = self.targets.get(slot.id)
            scheme = s.globals.hue_scheme
            if target is not None and role_of(index) == "accent" and slot.use_scheme:
                pen = QPen(QColor(tc.arc_target), 4, Qt.PenStyle.SolidLine, flat)
                self._arc(p, R + 13, target - scheme.tol, 2 * scheme.tol, pen)
        # punkty
        f = QFont(self.font())
        f.setBold(True)
        p.setFont(f)
        for i, sl in enumerate(s.slots):
            if i < 2 and sl.value.c < 0.02:
                continue
            v = sl.value
            pt = self._point(v.h, rel_chroma(v))
            draw_point(p, pt, _hex(s, v), str(i), sl.id == self.selected)
        p.end()


class LCPlot(QWidget):
    """Oś pionowa: L (góra = 1). Oś pozioma: C względne (0–1) albo bezwzględne (0–0.37).

    Tło = przekrój przez odcień zaznaczonego koloru."""

    MARGIN = 34

    def __init__(self) -> None:
        super().__init__()
        self.session: Session | None = None
        self.selected: str | None = None
        self.mode = "rel"
        self.setMinimumSize(QSize(320, 320))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_state(self, session: Session, selected: str | None, mode: str) -> None:
        self.session, self.selected, self.mode = session, selected, mode
        self.update()

    def _rect(self) -> QRectF:
        m = self.MARGIN
        side = min(self.width(), self.height()) - m - 10
        return QRectF(m, 10, max(side, 40), max(side, 40))

    def _hue(self) -> float:
        s = self.session
        assert s is not None
        for sl in s.slots:
            if sl.id == self.selected and sl.value.c >= 0.02:
                return sl.value.h
        return 250.0

    def _background(self, w: int, h: int) -> QImage:
        assert self.session is not None
        hue = self._hue()
        ys, xs = np.mgrid[0:h, 0:w]
        L = 1.0 - ys / max(h - 1, 1)
        t = xs / max(w - 1, 1)
        if self.mode == "rel":
            maxc = fast.max_chroma(L[:, 0], np.full(h, hue))
            c = t * maxc[:, None]
            mask = np.ones_like(c, dtype=bool)
        else:
            c = t * 0.37
            mask = fast.in_gamut(np.stack([L, c, np.full_like(L, hue)], axis=-1))
        lch = np.stack([L, c, np.full_like(L, hue)], axis=-1)
        return _to_image(lch, mask, _window_color())

    def paintEvent(self, _e) -> None:
        if self.session is None:
            return
        s = self.session
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._rect()
        p.setOpacity(BG_OPACITY)
        p.drawImage(r, self._background(int(r.width()), int(r.height())))
        p.setOpacity(1.0)
        p.setPen(QPen(self.palette().mid().color(), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(r)
        p.setPen(self.palette().text().color())
        for k in range(0, 11, 2):
            y = r.bottom() - k / 10 * r.height()
            p.drawText(
                QRectF(0, y - 8, self.MARGIN - 4, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{k / 10:.1f}",
            )
        p.drawText(
            QRectF(r.left(), r.bottom() + 2, r.width(), 18),
            Qt.AlignmentFlag.AlignRight,
            "C względne →" if self.mode == "rel" else "C 0–0.37 →",
        )
        p.drawText(QRectF(2, 0, 30, 12), Qt.AlignmentFlag.AlignLeft, "L")
        f = QFont(self.font())
        f.setBold(True)
        p.setFont(f)
        for i, sl in enumerate(s.slots):
            v = sl.value
            x = rel_chroma(v) if self.mode == "rel" else min(v.c / 0.37, 1.0)
            pt = QPointF(
                r.left() + x * r.width(), r.bottom() - min(max(v.l, 0.0), 1.0) * r.height()
            )
            draw_point(p, pt, _hex(s, v), str(i), sl.id == self.selected)
        p.end()


class Samples(QWidget):
    """„Aa nazwa” w każdym kolorze na tle palety."""

    def __init__(self) -> None:
        super().__init__()
        self.session: Session | None = None
        self.setMinimumHeight(120)

    def set_state(self, session: Session) -> None:
        self.session = session
        cols = 4
        rows = math.ceil((len(session.slots) - 1) / cols)
        self.setMinimumHeight(24 + rows * 34)
        self.update()

    def paintEvent(self, _e) -> None:
        if self.session is None:
            return
        s = self.session
        p = QPainter(self)
        bg = _hex(s, s.slots[0].value)
        p.fillRect(self.rect(), QColor(bg))
        f = QFont(self.font())
        f.setPointSizeF(f.pointSizeF() * 1.2)
        cols = 4
        cw = (self.width() - 20) / cols
        for k, sl in enumerate(s.slots[1:], start=1):
            r, c = divmod(k - 1, cols)
            hx = _hex(s, sl.value)
            x, y = 12 + c * cw, 12 + r * 34
            p.fillRect(QRectF(x, y + 4, 18, 18), QColor(hx))
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(hx))
            p.drawText(
                QRectF(x + 26, y, cw - 30, 28),
                Qt.AlignmentFlag.AlignVCenter,
                f"Aa {slot_label(s, k)}",
            )
        p.end()


def pair_requirement(session: Session, i: int, j: int) -> float | None:
    reqs = []
    for k in (i, j):
        c = session.slots[k].rules.min_distance
        if c is not None and c.enabled:
            reqs.append(float(c.value))
    return max(reqs) if reqs else None


def _icon(hex_: str) -> QIcon:
    pm = QPixmap(14, 14)
    pm.fill(QColor(hex_))
    return QIcon(pm)


class AnalysisTab(QScrollArea):
    def __init__(self, win: MainWindow) -> None:
        super().__init__()
        self.win = win
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        self.setWidget(body)
        help.attach(self, "window.tab.analysis")
        lay = vbox(body, margins=8, spacing=6)
        self.matrix_kind = combo(MATRICES, "de")
        self.axis = combo(AXES, "rel")
        for c in (self.matrix_kind, self.axis):
            c.currentIndexChanged.connect(lambda _: self.redraw())
        controls = []
        for text, w, key in (
            ("macierz:", self.matrix_kind, "analysis.matrix_kind"),
            ("oś C:", self.axis, "analysis.axis"),
        ):
            label = QLabel(text)
            help.attach(label, key)
            help.attach(w, key)
            controls += [label, w]
        lay.addWidget(hbox(*controls))
        self.wheel = HueWheel()
        help.attach(self.wheel, "analysis.wheel")
        self.lc = LCPlot()
        help.attach(self.lc, "analysis.lc")
        plots = hbox(self.wheel, self.lc, stretch=False, spacing=16)
        plots.setFixedHeight(380)
        lay.addWidget(plots)
        legend = hint(
            "Koło: 0° po prawej, promień = nasycenie względne; żółty łuk = zasada odcienia "
            "zaznaczonego koloru (czerwone kropki = zakazane przedziały), pomarańczowy = cel "
            "z układu odcieni ± tolerancja. "
            "Wykres L–C: przekrój gamutu sRGB przez odcień zaznaczonego koloru."
        )
        help.attach(legend, "analysis.overview")
        lay.addWidget(legend)
        self.matrix_title = section("")
        lay.addWidget(self.matrix_title)
        self.matrix = QTableWidget()
        self.matrix.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.matrix.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.matrix.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.matrix.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for w in (self.matrix, self.matrix_title):
            help.attach(w, "analysis.matrix.de")
        help.attach_header(self.matrix, "analysis.matrix.de")
        help.attach_header(self.matrix, "analysis.matrix.de", vertical=True)
        lay.addWidget(self.matrix)
        samples_title = section("Próbki na tle")
        help.attach(samples_title, "analysis.samples")
        lay.addWidget(samples_title)
        self.samples = Samples()
        help.attach(self.samples, "analysis.samples")
        lay.addWidget(self.samples)

    def refresh_from_session(self) -> None:
        self.redraw()

    def redraw(self) -> None:
        s = self.win.session
        sel = self.win.selected_slot_id()
        try:
            targets = engine.hue_targets(s)
        except ValueError:  # silnik nie przyjął sesji — naruszenia pokażą dlaczego
            targets = {}
        self.wheel.set_state(s, sel, targets)
        self.lc.set_state(s, sel, self.axis.currentData())
        if self.matrix_kind.currentData() == "contrast":
            self._contrast_matrix(s)
            key = "analysis.matrix.contrast"
        else:
            self._de_matrix(s)
            key = "analysis.matrix.de"
        for w in (self.matrix, self.matrix_title):
            help.attach(w, key)
        help.attach_header(self.matrix, key)
        help.attach_header(self.matrix, key, vertical=True)
        self.samples.set_state(s)
        m = self.matrix
        m.resizeRowsToContents()
        height = m.horizontalHeader().height() + sum(m.rowHeight(r) for r in range(m.rowCount()))
        m.setFixedHeight(height + 2 * m.frameWidth() + 4)

    def _headers(self, s: Session, acc: list[int], vals: dict[int, OKLCH]) -> None:
        m = self.matrix
        for k, i in enumerate(acc):
            hx = _hex(s, vals[i])
            h = QTableWidgetItem(_icon(hx), str(i))
            m.setHorizontalHeaderItem(k, h)
            v = QTableWidgetItem(_icon(hx), f"{i}: {slot_label(s, i)}")
            m.setVerticalHeaderItem(k, v)

    def _de_matrix(self, s: Session) -> None:
        g = s.globals
        acc = list(range(2, len(s.slots)))
        vals = {i: engine.measured(s.slots[i].value, g.fit_method) for i in acc}
        bg = engine.measured(s.slots[0].value, g.fit_method)
        self.matrix_title.setText(
            f"ΔE akcentów ({g.delta_e}) — czerwone = poniżej wymaganej odległości; "
            f"ostatnia kolumna: kontrast z tłem ({g.contrast_metric})"
        )
        m = self.matrix
        m.clear()
        m.setRowCount(len(acc))
        m.setColumnCount(len(acc) + 1)
        self._headers(s, acc, vals)
        m.setHorizontalHeaderItem(len(acc), QTableWidgetItem("kontrast z tłem"))
        fmt = ".3f" if g.delta_e in ("ok", "hyab") else ".1f"
        for r, i in enumerate(acc):
            for c, j in enumerate(acc):
                if i == j:
                    it = QTableWidgetItem("—")
                else:
                    d = engine.pair_delta_e(vals[i], vals[j], s)
                    it = QTableWidgetItem(format(d, fmt))
                    req = pair_requirement(s, i, j)
                    if req is not None and d < req:
                        it.setBackground(QColor(theme.colors().bad_cell_bg))
                        it.setForeground(QColor(theme.colors().bad_cell_fg))
                        it.setToolTip(f"wymagane ≥ {req:g}")
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                m.setItem(r, c, it)
            it = QTableWidgetItem(f"{engine.pair_contrast(vals[i], bg, s):.2f}")
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            m.setItem(r, len(acc), it)

    def _contrast_matrix(self, s: Session) -> None:
        g = s.globals
        acc = list(range(2, len(s.slots)))
        vals = {i: engine.measured(s.slots[i].value, g.fit_method) for i in acc}
        self.matrix_title.setText(
            f"Kontrast par akcentów ({g.contrast_metric}) — wiersz = tekst, kolumna = tło"
        )
        m = self.matrix
        m.clear()
        m.setRowCount(len(acc))
        m.setColumnCount(len(acc))
        self._headers(s, acc, vals)
        for r, i in enumerate(acc):
            for c, j in enumerate(acc):
                text = "—" if i == j else f"{engine.pair_contrast(vals[i], vals[j], s):.2f}"
                it = QTableWidgetItem(text)
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if i != j:
                    it.setBackground(QColor(_hex(s, vals[j])))
                    it.setForeground(QColor(_hex(s, vals[i])))
                m.setItem(r, c, it)
