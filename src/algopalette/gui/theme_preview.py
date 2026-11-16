"""Podgląd motywu z sieci i wiersz listy z próbkami (spec §8).

Oba rysują ``QPainter`` kolorami *motywu*, nie palety Qt okna — podgląd wygląda tak samo w oknie
jasnym i ciemnym. Wyjątek: komunikat zastępczy (brak palety) i delegat wiersza, które żyją w
oknie z motywem i biorą kolory tekstu z ``QPalette`` widoku.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QPainter,
    QPaintEvent,
    QPalette,
)
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from algopalette import color
from algopalette.color import fast
from algopalette.model import OKLCH
from algopalette.themes.model import SOURCES, Palette, Theme

THEME_ROLE = int(Qt.ItemDataRole.UserRole) + 1  # Theme w modelu listy
PALETTE_ROLE = int(Qt.ItemDataRole.UserRole) + 2  # Palette | None (po resolve; None = błąd)

ROLES = ("keyword", "string", "number", "comment", "function", "type", "added", "removed")
# Kolejność, w jakiej role kodu biorą kolejne akcenty, gdy motyw nie ma nazw base16.
_SEQUENCE = ("keyword", "string", "number", "function", "type", "added", "removed")
# Kanoniczne role base16/base24 (spec §8); ``string`` i ``added`` dzielą base0B.
_BASE16 = {
    "removed": "base08",
    "number": "base09",
    "type": "base0A",
    "string": "base0B",
    "added": "base0B",
    "function": "base0D",
    "keyword": "base0E",
}

# Linijki podglądu: (tekst, rola) — rola ``None`` = zwykły tekst motywu.
_Token = tuple[str, str | None]
_LINES: tuple[tuple[_Token, ...], ...] = (
    (("$ ", "string"), ("git", "function"), (" status", None)),
    (("On branch main", None),),
    (("  modified:", "removed"), ("   src/app.py", None)),
    (("  new file:", "added"), ("   src/theme.py", None)),
    (("+ ", "added"), ("def ", "keyword"), ("build", "function"), ("(x)", None)),
    (("- ", "removed"), ("lines = ", None), ("14", "number")),
    (),
    (
        ("def ", "keyword"),
        ("build", "function"),
        ("(x: ", None),
        ("int", "type"),
        (") -> ", None),
        ("str", "type"),
        (":", None),
    ),
    (
        ("    return ", "keyword"),
        ('f"#{x}"', "string"),
        ("  ", None),
        ("# komentarz", "comment"),
    ),
)
_FIT = "oklch-chroma"
_PAD = 14
_STRIP_H = 22
_SWATCH_MAX = 30


def _hex(c: OKLCH) -> str:
    return color.to_hex(c, _FIT)


@lru_cache(maxsize=1024)
def palette_hexes(p: Palette) -> tuple[str, ...]:
    """Hexy (tło, tekst, *akcenty) — z pamięcią, bo delegat woła to przy każdym przemalowaniu."""
    return tuple(_hex(c) for c in (p.bg, p.fg, *p.accents))


def comment_color(p: Palette) -> OKLCH:
    """Tekst zmieszany w połowie z tłem w OKLab (przygaszony, ale czytelny komentarz)."""
    lab = (
        fast.oklch_to_oklab([p.fg.l, p.fg.c, p.fg.h])
        + fast.oklch_to_oklab([p.bg.l, p.bg.c, p.bg.h])
    ) / 2
    l_, c, h = (float(v) for v in fast.oklab_to_oklch(lab))
    return OKLCH(l_, c, h)


def role_colors(p: Palette) -> dict[str, QColor]:
    """Rola podglądu → kolor. base16/base24 wg nazw akcentów, inaczej kolejne akcenty (modulo)."""
    out: dict[str, QColor] = {}
    names = {n: a for n, a in zip(p.accent_names, p.accents, strict=False) if n}
    n = len(p.accents)
    for i, role in enumerate(_SEQUENCE):
        canon = names.get(_BASE16.get(role, "")) if "base08" in names else None
        out[role] = QColor(_hex(canon if canon is not None else p.accents[i % n]))
    out["comment"] = QColor(_hex(comment_color(p)))
    return {r: out[r] for r in ROLES}


def _akcenty(n: int) -> str:
    if n == 1:
        return "1 akcent"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} akcenty"
    return f"{n} akcentów"


class ThemePreview(QWidget):
    """Kilka linijek terminala i kodu w kolorach motywu + pasek ról pod spodem."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette: Palette | None = None
        self._message = ""
        self._roles: dict[str, QColor] = {}
        self.setObjectName("themePreview")
        self.setAccessibleName("Podgląd motywu")

    # --- dane ------------------------------------------------------------------------------
    @property
    def message(self) -> str:
        """Komunikat zastępczy (gdy brak palety); pusty, gdy podgląd pokazuje motyw."""
        return self._message

    def set_palette(self, palette: Palette | None, *, message: str = "") -> None:
        """``None`` → zamiast podglądu centrowany ``message`` (np. powód błędu motywu)."""
        if palette is not None and not palette.accents:
            palette = None  # bez akcentu nie ma czego pokazać w rolach kodu
        self._palette = palette
        self._roles = role_colors(palette) if palette is not None else {}
        self._message = "" if palette is not None else message
        self.setAccessibleDescription(self._message)
        self.update()

    def snippet_colors(self) -> dict[str, QColor]:
        """Rola podglądu → kolor (kopia; pusty przy braku palety)."""
        return dict(self._roles)

    # --- rozmiar ---------------------------------------------------------------------------
    def _font(self) -> QFont:
        f = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        f.setPointSizeF(max(self.font().pointSizeF(), 9.0) * 1.05)
        return f

    def minimumSizeHint(self) -> QSize:
        lh = QFontMetrics(self._font()).lineSpacing()
        h = 2 * _PAD + len(_LINES) * lh + 12 + _STRIP_H + 6 + QFontMetrics(self.font()).height()
        return QSize(340, h)

    def sizeHint(self) -> QSize:
        return self.minimumSizeHint() + QSize(120, 20)

    # --- rysowanie -------------------------------------------------------------------------
    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            if self._palette is None:
                self._paint_message(p)
            else:
                self._paint_theme(p, self._palette)
        finally:
            p.end()

    def _paint_message(self, p: QPainter) -> None:
        pal = self.palette()
        p.fillRect(self.rect(), pal.color(QPalette.ColorRole.Window))
        if self._message:
            p.setPen(pal.color(QPalette.ColorRole.WindowText))
            box = self.rect().adjusted(_PAD, _PAD, -_PAD, -_PAD)
            flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap
            p.drawText(box, int(flags), self._message)

    def _paint_theme(self, p: QPainter, pal: Palette) -> None:
        hexes = palette_hexes(pal)
        bg, fg = QColor(hexes[0]), QColor(hexes[1])
        dim = self._roles["comment"]
        p.fillRect(self.rect(), bg)

        font = self._font()
        p.setFont(font)
        lh = QFontMetrics(font).lineSpacing()
        y = _PAD
        for line in _LINES:
            x = _PAD
            base = y + QFontMetrics(font).ascent()
            for text, role in line:
                p.setPen(self._roles[role] if role else fg)
                p.drawText(QPoint(x, base), text)
                x += QFontMetrics(font).horizontalAdvance(text)
            y += lh

        # pasek ról: tło, tekst, akcenty
        small = self.font()
        sfm = QFontMetrics(small)
        strip_y = self.height() - _PAD - sfm.height() - 6 - _STRIP_H
        cells = len(hexes)
        w = max(4, min(_SWATCH_MAX, (self.width() - 2 * _PAD - 8) // cells))
        x = _PAD
        for i, h in enumerate(hexes):
            if i == 2:
                x += 8  # odstęp między „tło · tekst” a akcentami
            r = QRect(x, strip_y, w, _STRIP_H)
            p.fillRect(r, QColor(h))
            p.setPen(dim)
            p.drawRect(r.adjusted(0, 0, -1, -1))
            x += w
        p.setFont(small)
        p.setPen(dim)
        dark = "ciemny" if pal.bg.l < 0.5 else "jasny"
        caption = f"tło · tekst · {_akcenty(len(pal.accents))} · {dark}"
        cap_box = QRect(_PAD, strip_y + _STRIP_H + 6, self.width() - 2 * _PAD, sfm.height())
        p.drawText(
            cap_box, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), caption
        )


class SwatchDelegate(QStyledItemDelegate):
    """Wiersz listy: nazwa, plakietka źródła, pasek próbek (tło, tekst, akcenty)."""

    _SW_H = 14
    _SW_MAX = 22
    _PADX, _PADY = 8, 5

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        fm = option.fontMetrics
        return QSize(220, fm.height() + self._SW_H + 3 * self._PADY)

    @staticmethod
    def _swatches(theme: Theme, palette: Palette | None) -> tuple[str, ...]:
        return palette_hexes(palette) if isinstance(palette, Palette) else tuple(theme.colors)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        theme = index.data(THEME_ROLE)
        if not isinstance(theme, Theme):
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        widget = option.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)

        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        role = QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        text = opt.palette.color(QPalette.ColorGroup.Active, role)
        r = opt.rect.adjusted(self._PADX, self._PADY, -self._PADX, -self._PADY)

        painter.save()
        try:
            # plakietka źródła (po prawej)
            badge_font = QFont(opt.font)
            badge_font.setPointSizeF(max(badge_font.pointSizeF() * 0.82, 7.0))
            bfm = QFontMetrics(badge_font)
            label = SOURCES[theme.source]
            bw = bfm.horizontalAdvance(label) + 12
            bh = bfm.height() + 2
            name_h = opt.fontMetrics.height()
            badge = QRect(r.right() - bw + 1, r.top() + (name_h - bh) // 2, bw, bh)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            edge = QColor(text)
            edge.setAlphaF(0.55)
            painter.setPen(edge)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(badge).adjusted(0.5, 0.5, -0.5, -0.5), bh / 2, bh / 2)
            painter.setFont(badge_font)
            painter.setPen(text)
            painter.drawText(badge, int(Qt.AlignmentFlag.AlignCenter), label)

            # nazwa (po lewej, skrócona do miejsca przed plakietką)
            painter.setFont(opt.font)
            avail = max(0, badge.left() - 8 - r.left())
            name = opt.fontMetrics.elidedText(theme.name, Qt.TextElideMode.ElideRight, avail)
            name_box = QRect(r.left(), r.top(), avail, name_h)
            painter.drawText(
                name_box, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), name
            )

            # pasek próbek
            hexes = self._swatches(theme, index.data(PALETTE_ROLE))
            if hexes:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                w = max(2, min(self._SW_MAX, r.width() // len(hexes)))
                y = r.top() + name_h + self._PADY
                x = r.left()
                for h in hexes:
                    painter.fillRect(QRect(x, y, w, self._SW_H), QColor(h))
                    x += w
                outline = QColor(text)
                outline.setAlphaF(0.35)  # tło motywu bywa równe tłu listy
                painter.setPen(outline)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRect(r.left(), y, x - r.left() - 1, self._SW_H - 1))
        finally:
            painter.restore()
