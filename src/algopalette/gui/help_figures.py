"""Rysunki do tematów pomocy: liczone z kolorów programu przy każdym pokazaniu tematu (żaden
obrazek nie jest wklejony). Temat odwołuje się do rysunku przez ``![opis](figure:nazwa)``."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

from algopalette import color
from algopalette.gui.widgets import lch_to_qcolors

# --- nasycenie bezwzględne i względne ----------------------------------------------------------

CHROMA_L = 0.75
CHROMA_ABS = 0.10
CHROMA_REL = 0.60
CHROMA_HUES = tuple(float(h) for h in range(0, 360, 30))

_CELL = 31  # szerokość kolumny jednej próbki
_SWATCH = 26
_MARGIN = 4
_TITLE_H = 16
_LABEL_H = 13
_ROW_H = _TITLE_H + _SWATCH + _LABEL_H + 6
_HEAD_H = 14  # wiersz ze stopniami nad pierwszym rzędem


def chroma_modes_values() -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Nasycenie C każdej próbki: rząd bezwzględny (obcięty do możliwości ekranu) i względny."""
    maxc = [color.max_chroma(CHROMA_L, h) for h in CHROMA_HUES]
    return tuple(min(CHROMA_ABS, m) for m in maxc), tuple(CHROMA_REL * m for m in maxc)


def chroma_modes_rows() -> tuple[int, int]:
    """Współrzędne y środków próbek w rzędzie bezwzględnym i względnym."""
    first = _MARGIN + _HEAD_H + _TITLE_H + _SWATCH // 2
    return first, first + _ROW_H


def chroma_modes() -> QImage:
    """Dwa rzędy po 12 próbek w odcieniach co 30° przy L = 0.75: górny ze stałym C bezwzględnym,
    dolny ze stałym C względnym; pod każdą próbką jej C."""
    width = 2 * _MARGIN + _CELL * len(CHROMA_HUES)
    height = 2 * _MARGIN + _HEAD_H + 2 * _ROW_H
    img = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    text = QApplication.palette().text().color()  # paleta aplikacji: śledzi motyw od razu
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    small = QFont(QApplication.font())
    small.setPixelSize(9)
    normal = QFont(QApplication.font())
    normal.setPixelSize(11)
    center = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter

    p.setPen(text)
    p.setFont(small)
    for i, h in enumerate(CHROMA_HUES):
        p.drawText(QRectF(_MARGIN + i * _CELL, _MARGIN, _CELL, _HEAD_H), center, f"{h:.0f}°")

    absolute, relative = chroma_modes_values()
    titles = (
        f"stałe C = {CHROMA_ABS:.2f} (bezwzględne)",
        f"stałe {CHROMA_REL:.0%} największego C (względne)",
    )
    for row, (values, title) in enumerate(zip((absolute, relative), titles, strict=True)):
        top = _MARGIN + _HEAD_H + row * _ROW_H
        p.setPen(text)
        p.setFont(normal)
        left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        p.drawText(QRectF(_MARGIN, top, width - 2 * _MARGIN, _TITLE_H), left, title)
        lch = np.array([[CHROMA_L, c, h] for c, h in zip(values, CHROMA_HUES, strict=True)])
        for i, (qc, c) in enumerate(zip(lch_to_qcolors(lch), values, strict=True)):
            x = _MARGIN + i * _CELL + (_CELL - _SWATCH) / 2
            p.setPen(QPen(QColor("#808080"), 1))
            p.setBrush(qc)
            p.drawRect(QRectF(x, top + _TITLE_H, _SWATCH, _SWATCH))
            p.setPen(text)
            p.setFont(small)
            label = QRectF(_MARGIN + i * _CELL, top + _TITLE_H + _SWATCH + 1, _CELL, _LABEL_H)
            p.drawText(label, center, f"{c:.2f}")
    p.end()
    return img


FIGURES: dict[str, Callable[[], QImage]] = {"chroma_modes": chroma_modes}


def render(name: str) -> QImage:
    """Rysunek o podanej nazwie w kolorach bieżącego motywu (``KeyError`` dla nieznanej)."""
    return FIGURES[name]()
