"""Zakładka „Paleta”: lista slotów + edytor zaznaczonego slotu (wartość, warunki, zależności)."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from algopalette import color as col
from algopalette.constraints import slot_label
from algopalette.gui import help, theme
from algopalette.gui.conditions import ConditionsEditor
from algopalette.gui.relations import RelationsEditor
from algopalette.gui.widgets import (
    Swatch,
    ValueSlider,
    channel_gradient,
    clear_layout,
    form,
    hbox,
    hint,
    lch_to_qcolors,
    section,
    vbox,
)
from algopalette.model import (
    OKLCH,
    Session,
    ViewModel,
    add_accent,
    move_slot,
    remove_slot,
    role_of,
    slot_index,
    with_slot,
)

if TYPE_CHECKING:
    from algopalette.gui.app import MainWindow

ROLE_NAMES = {"bg": "tło", "fg": "tekst", "accent": "akcent"}


def column_labels(view: str) -> list[str]:
    """Nagłówki tabeli — kolumny wartości zależą od widoku (OKLCH: L C H, HSL: H S% L%)."""
    vals = ["H°", "S%", "L%"] if view == "hsl" else ["L", "C", "H"]
    return ["", "#", "nazwa", "hex", *vals, "🔒", "kontrast", "ΔE min"]


def _value_cells(v: OKLCH, session: Session) -> tuple[str, str, str]:
    if session.view_model == "hsl":
        h, s, l_ = col.to_hsl(v, session.globals.fit_method)
        return f"{h:.0f}", f"{s:.1f}", f"{l_:.1f}"
    return f"{v.l:.3f}", f"{v.c:.3f}", f"{v.h:.1f}"


def slot_rows(session: Session) -> list[tuple[str, str, list[str], float]]:
    """Wiersze tabeli: (id, hex, teksty komórek od kolumny 1, Δ fit)."""
    g = session.globals
    bg = session.slots[0].value
    accents = list(range(2, len(session.slots)))
    rows = []
    for i, s in enumerate(session.slots):
        v = s.value
        hx = col.to_hex(v, g.fit_method)
        contrast = "—" if i == 0 else f"{col.contrast(v, bg, g.contrast_metric):.2f}"
        de = "—"
        if i >= 2 and len(accents) > 1:
            dmin = min(col.delta_e(v, session.slots[j].value, g.delta_e) for j in accents if j != i)
            de = f"{dmin:.3f}" if g.delta_e in ("ok", "hyab") else f"{dmin:.1f}"
        fit = col.fit_delta(v, g.fit_method)
        hex_cell = hx + (f"  ⚠ {fit:.3f}" if fit > 0 else "")
        cells = [
            str(i),
            slot_label(session, i),
            hex_cell,
            *_value_cells(v, session),
            "🔒" if s.locked else "",
            contrast,
            de,
        ]
        rows.append((s.id, hx, cells, fit))
    return rows


class SwatchDelegate(QStyledItemDelegate):
    """Próbka koloru zawsze w swoim kolorze — także w zaznaczonym wierszu."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        color = index.data(Qt.ItemDataRole.BackgroundRole)
        rect = QRect(option.rect).adjusted(3, 3, -3, -3)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            painter.fillRect(option.rect, option.palette.highlight())
        if color is not None:
            painter.fillRect(rect, color)
        painter.setPen(option.palette.mid().color())
        painter.drawRect(rect)


class SlotTable(QTableWidget):
    def __init__(self, win: MainWindow) -> None:
        super().__init__(0, 10)
        self.win = win
        self._view: str | None = None
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(30)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        mono = QFont("monospace")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self._mono = mono
        h = self.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setMinimumSectionSize(24)
        self.setItemDelegateForColumn(0, SwatchDelegate(self))
        help.attach(self, "palette.list")
        help.attach_header(
            self,
            [
                "palette.col.swatch",
                "palette.col.index",
                "palette.col.name",
                "palette.col.hex",
                "palette.col.values",
                "palette.col.values",
                "palette.col.values",
                "palette.col.lock",
                "palette.col.contrast",
                "palette.col.de_min",
            ],
        )

    def ids(self) -> list[str]:
        out = []
        for r in range(self.rowCount()):
            it = self.item(r, 1)
            out.append(it.data(Qt.ItemDataRole.UserRole) if it else "")
        return out

    def selected_id(self) -> str | None:
        r = self.currentRow()
        if r < 0 or r >= self.rowCount():
            return None
        it = self.item(r, 1)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def select_id(self, sid: str | None) -> None:
        ids = self.ids()
        if sid in ids:
            self.setCurrentCell(ids.index(sid), 1)

    def populate(self, session: Session) -> None:
        """Ten sam zestaw slotów → aktualizacja komórek w miejscu (bez ruszania zaznaczenia)."""
        rows = slot_rows(session)
        ids = [sid for sid, *_ in rows]
        current = self.selected_id()
        if session.view_model != self._view:
            self._view = session.view_model
            self.setHorizontalHeaderLabels(column_labels(self._view))
        same = self.ids() == ids
        self.blockSignals(True)
        if not same:
            self.setRowCount(len(rows))
        for r, (sid, hx, cells, fit) in enumerate(rows):
            sw = self.item(r, 0)
            if sw is None:
                sw = QTableWidgetItem()
                self.setItem(r, 0, sw)
            sw.setBackground(QColor(hx))
            sw.setToolTip(hx)
            for c, text in enumerate(cells, start=1):
                it = self.item(r, c)
                if it is None:
                    it = QTableWidgetItem()
                    self.setItem(r, c, it)
                it.setText(text)
                if c == 1:
                    it.setData(Qt.ItemDataRole.UserRole, sid)
                if c in (3, 4, 5, 6, 8, 9):
                    it.setFont(self._mono)
                    it.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                        if c != 3
                        else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )
                if c == 3:
                    it.setForeground(
                        QColor(theme.colors().warn_text)
                        if fit > 0
                        else self.palette().text().color()
                    )
                    it.setToolTip(
                        f"kolor spoza sRGB — ściągnięty do gamutu o ΔE ok {fit:.3f}" if fit else ""
                    )
            self.setColumnWidth(0, 44)
        if not same:
            if current in ids:
                self.setCurrentCell(ids.index(current), 1)
            elif rows:
                self.setCurrentCell(0, 1)
        self.blockSignals(False)

    def sizeHint(self) -> QSize:
        return QSize(620, 400)


class SlotEditor(QScrollArea):
    """Edytor zaznaczonego slotu; zawartość budowana na nowo przy zmianie slotu/struktury."""

    def __init__(self, win: MainWindow) -> None:
        super().__init__()
        self.win = win
        self.slot_id: str | None = None
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        self._lay = vbox(body, margins=10, spacing=6)
        self.setWidget(body)
        help.attach(self, "palette.editor")
        self.value_sliders: dict[str, ValueSlider] = {}

    def alive(self) -> bool:
        return self.slot_id in {x.id for x in self.win.session.slots}

    def show_slot(self, sid: str | None) -> None:
        self.slot_id = sid
        self.rebuild()

    def rebuild(self) -> None:
        clear_layout(self._lay)
        self.value_sliders = {}
        s = self.win.session
        if not self.alive():
            empty = hint("Wybierz kolor z listy.")
            help.attach(empty, "palette.list")
            self._lay.addWidget(empty)
            self._lay.addStretch(1)
            return
        i = slot_index(s, self.slot_id or "")
        slot = s.slots[i]
        self.swatch = Swatch(col.to_hex(slot.value, s.globals.fit_method), QSize(96, 56))
        help.attach(self.swatch, "palette.editor")
        self.title = QLabel()
        f = self.title.font()
        f.setPointSizeF(f.pointSizeF() * 1.25)
        f.setBold(True)
        self.title.setFont(f)
        self.subtitle = QLabel()
        self.subtitle.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        titles = QWidget()
        tl = vbox(titles, spacing=2)
        tl.addWidget(self.title)
        tl.addWidget(self.subtitle)
        self._lay.addWidget(hbox(self.swatch, titles))
        help.attach(self.title, "palette.editor")
        help.attach(self.subtitle, "palette.editor")
        self._update_title()

        w, fl = form()
        self.name = QLineEdit(slot.name)
        self.name.setPlaceholderText(f"(bez nazwy — „{slot_label(s, i)}”)")
        self.name.editingFinished.connect(self._name)
        fl.addRow("nazwa", self.name)
        self.lock = QCheckBox("kłódka — generowanie nie zmienia tego koloru")
        self.lock.setChecked(slot.locked)
        self.lock.toggled.connect(self._lock)
        fl.addRow("", self.lock)
        help.attach(self.name, "palette.editor.name")
        help.attach(self.lock, "palette.lock")
        help.attach_form_labels(fl)
        self._lay.addWidget(w)

        v = slot.value
        hsl = s.view_model == "hsl"
        head = section("Wartość (HSL → zapis w OKLCH)" if hsl else "Wartość (OKLCH)")
        help.attach(head, "palette.value")
        self._lay.addWidget(head)
        w, fl = form()
        if hsl:
            hh, ss, ll = col.to_hsl(v, s.globals.fit_method)
            specs = [
                ("hsl-h", "H°", hh, 0.0, 360.0, 1.0, ".1f", True),
                ("hsl-s", "S%", ss, 0.0, 100.0, 1.0, ".1f", False),
                ("hsl-l", "L%", ll, 0.0, 100.0, 1.0, ".1f", False),
            ]
        else:
            specs = [
                ("val-l", "L", v.l, 0.0, 1.0, 0.01, ".3f", False),
                ("val-c", "C", v.c, 0.0, 0.37, 0.005, ".3f", False),
                ("val-h", "H", v.h, 0.0, 360.0, 1.0, ".1f", True),
            ]
        for key, label, val, lo, hi, step, fmt, wrap in specs:
            sl = ValueSlider(val, minimum=lo, maximum=hi, step=step, fmt=fmt, wrap=wrap)
            sl.setObjectName(key)
            sl.changed.connect(lambda x, key=key: self._value(key, x))
            self.value_sliders[key] = sl
            topic = "palette.value.hsl" if hsl else f"palette.value.{key[-1]}"
            help.attach(sl, topic, children=True)
            fl.addRow(label, sl)
        help.attach_form_labels(fl)
        self._lay.addWidget(w)
        self._update_gradients()

        head = section("Warunki (w OKLCH)" if hsl else "Warunki")
        help.attach(head, "cond.overview")
        self._lay.addWidget(head)
        self.conditions = ConditionsEditor(self.win, "slot", slot.id)
        self._lay.addWidget(self.conditions)
        head = section("Zależności od innych kolorów")
        help.attach(head, "rel.overview")
        self._lay.addWidget(head)
        self.relations = RelationsEditor(self.win, slot.id)
        self._lay.addWidget(self.relations)
        self._lay.addStretch(1)

    def _slot(self):
        s = self.win.session
        return s, s.slots[slot_index(s, self.slot_id or "")]

    def _update_title(self) -> None:
        s, slot = self._slot()
        i = slot_index(s, slot.id)
        hx = col.to_hex(slot.value, s.globals.fit_method)
        self.swatch.set_hex(hx)
        self.title.setText(f"{i}: {slot_label(s, i)}")
        v = slot.value
        self.subtitle.setText(
            f"{hx}   ·   oklch({v.l:.3f} {v.c:.3f} {v.h:.1f})   ·   rola: {ROLE_NAMES[role_of(i)]}"
        )

    def _update_gradients(self) -> None:
        s, slot = self._slot()
        v = slot.value
        if s.view_model == "hsl":
            import numpy as np

            hh, ss, ll = col.to_hsl(v, s.globals.fit_method)

            def hsl_grad(which: int):
                def make(xs):
                    out = []
                    for x in xs:
                        h_, s_, l_ = [hh, ss, ll]
                        if which == 0:
                            h_ = x
                        elif which == 1:
                            s_ = x
                        else:
                            l_ = x
                        c = col.from_hsl(h_, s_, l_)
                        out.append([c.l, c.c, c.h])
                    return lch_to_qcolors(np.array(out))

                return make

            for k, which in (("hsl-h", 0), ("hsl-s", 1), ("hsl-l", 2)):
                self.value_sliders[k].bar.set_gradient(hsl_grad(which))
        else:
            self.value_sliders["val-l"].bar.set_gradient(channel_gradient(v, "l"))
            self.value_sliders["val-c"].bar.set_gradient(channel_gradient(v, "c"))
            hue_base = v if v.c >= 0.03 else OKLCH(v.l, 0.1, v.h)
            self.value_sliders["val-h"].bar.set_gradient(channel_gradient(hue_base, "h"))

    def _name(self) -> None:
        if not self.alive():
            return
        s, slot = self._slot()
        name = self.name.text().strip()
        if name != slot.name:
            self.win.set_session(with_slot(s, replace(slot, name=name)))
            self._update_title()

    def _lock(self, on: bool) -> None:
        if not self.alive():
            return
        s, slot = self._slot()
        if slot.locked != on:
            self.win.set_session(with_slot(s, replace(slot, locked=on)))

    def _value(self, key: str, x: float | None) -> None:
        if x is None or not self.alive():
            return
        s, slot = self._slot()
        v = slot.value
        x = float(x)
        if key.startswith("hsl-"):
            hh, ss, ll = col.to_hsl(v, s.globals.fit_method)
            hsl = {"hsl-h": (x, ss, ll), "hsl-s": (hh, x, ll), "hsl-l": (hh, ss, x)}[key]
            new = col.from_hsl(*hsl)
        else:
            new = {
                "val-l": OKLCH(x, v.c, v.h),
                "val-c": OKLCH(v.l, x, v.h),
                "val-h": OKLCH(v.l, v.c, x % 360),
            }[key]
        self.win.set_session(
            with_slot(s, replace(slot, value=new)), coalesce=f"value:{slot.id}:{key}"
        )
        self._update_title()
        self._update_gradients()


class PaletteTab(QSplitter):
    def __init__(self, win: MainWindow) -> None:
        super().__init__(Qt.Orientation.Horizontal)
        self.win = win
        left = QWidget()
        lay = vbox(left, margins=8, spacing=6)
        self.view_combo = QComboBox()
        self.view_combo.addItem("OKLCH", "oklch")
        self.view_combo.addItem("HSL", "hsl")
        help.attach(self.view_combo, "menu.view.values")
        self.view_combo.currentIndexChanged.connect(self._view_changed)
        view_label = QLabel("widok wartości:")
        help.attach(view_label, "menu.view.values")
        lay.addWidget(hbox(view_label, self.view_combo))
        self.table = SlotTable(win)
        self.table.currentCellChanged.connect(self._row_changed)
        lay.addWidget(self.table, 1)

        self.act_add = QAction("+ akcent", self)
        self.act_add.setShortcuts([QKeySequence("Ins"), QKeySequence("A")])
        self.act_add.triggered.connect(self.add_accent)
        self.act_remove = QAction("Usuń", self)
        self.act_remove.setShortcut(QKeySequence("Del"))
        self.act_remove.triggered.connect(self.remove_slot)
        self.act_lock = QAction("Kłódka", self)
        self.act_lock.setShortcut(QKeySequence("L"))
        self.act_lock.triggered.connect(self.toggle_lock)
        self.act_up = QAction("▲ wyżej", self)
        self.act_up.setShortcut(QKeySequence("Alt+Up"))
        self.act_up.triggered.connect(lambda: self.move_selected(-1))
        self.act_down = QAction("▼ niżej", self)
        self.act_down.setShortcut(QKeySequence("Alt+Down"))
        self.act_down.triggered.connect(lambda: self.move_selected(1))
        buttons = []
        keys = ("palette.add", "palette.remove", "palette.lock", "palette.move", "palette.move")
        for a, key in zip(self.slot_actions(), keys, strict=True):
            a.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            self.table.addAction(a)
            help.attach(a, key)
            b = QPushButton(a.text())
            help.attach(b, key)
            b.clicked.connect(a.trigger)
            buttons.append(b)
        gen = QPushButton("Generuj propozycje (Ctrl+G)")
        help.attach(gen, "palette.generate")
        gen.setDefault(True)
        gen.clicked.connect(win.action_generate)
        lay.addWidget(hbox(*buttons))
        lay.addWidget(hbox(gen))
        tip = hint(
            "Tło i tekst mają stałe miejsca 0 i 1; akcenty można dodawać (do 14), usuwać i "
            "przesuwać. Kolor spoza sRGB ma ⚠ i ΔE ściągnięcia do gamutu."
        )
        help.attach(tip, "palette.list")
        lay.addWidget(tip)
        self.editor = SlotEditor(win)
        self.addWidget(left)
        self.addWidget(self.editor)
        self.setStretchFactor(0, 5)
        self.setStretchFactor(1, 6)
        self.setSizes([620, 740])

    def slot_actions(self) -> list[QAction]:
        return [self.act_add, self.act_remove, self.act_lock, self.act_up, self.act_down]

    def refresh_from_session(self, *, editor: bool) -> None:
        s = self.win.session
        i = self.view_combo.findData(s.view_model)
        if self.view_combo.currentIndex() != i:
            self.view_combo.blockSignals(True)
            self.view_combo.setCurrentIndex(i)
            self.view_combo.blockSignals(False)
        before = self.table.selected_id()
        self.table.populate(s)
        after = self.table.selected_id()
        if editor or before != after or self.editor.slot_id != after:
            self.editor.show_slot(after)

    def _view_changed(self, _i: int) -> None:
        mode = self.view_combo.currentData()
        if mode in ("oklch", "hsl") and mode != self.win.session.view_model:
            self.win.set_view_model(cast(ViewModel, mode))

    def _row_changed(self, *_args) -> None:
        sid = self.table.selected_id()
        if sid != self.editor.slot_id:
            self.editor.show_slot(sid)

    # --- akcje listy ---
    def _apply(self, fn, *args) -> bool:
        try:
            new = fn(self.win.session, *args)
        except ValueError as e:
            self.win.notify(str(e))
            return False
        self.win.set_session(new, structural=True)
        return True

    def add_accent(self) -> None:
        if self._apply(add_accent):
            self.table.select_id(self.win.session.slots[-1].id)

    def remove_slot(self) -> None:
        sid = self.table.selected_id()
        if sid is not None:
            self._apply(remove_slot, sid)

    def toggle_lock(self) -> None:
        sid = self.table.selected_id()
        if sid is None:
            return
        s = self.win.session
        slot = s.slots[slot_index(s, sid)]
        self.win.set_session(with_slot(s, replace(slot, locked=not slot.locked)), structural=True)

    def move_selected(self, delta: int) -> None:
        sid = self.table.selected_id()
        if sid is None:
            return
        i = slot_index(self.win.session, sid)
        if self._apply(move_slot, sid, i + delta):
            self.table.select_id(sid)
