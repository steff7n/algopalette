"""Zakładka „Propozycje”: generowanie w tle, przegląd, przejmowanie palety lub jednego koloru."""

from __future__ import annotations

import threading
from collections.abc import Collection
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from algopalette import color as col
from algopalette.constraints import slot_label
from algopalette.engine import Proposal, apply_proposal, generate
from algopalette.gui import help, theme
from algopalette.gui.widgets import hbox, hint, vbox
from algopalette.model import Session

if TYPE_CHECKING:
    from algopalette.gui.app import MainWindow


class Strip(QWidget):
    """Pasek kolorów propozycji."""

    def __init__(self, hexes: list[str]) -> None:
        super().__init__()
        self.hexes = hexes
        self.setMinimumSize(QSize(18 * max(len(hexes), 1), 22))

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        n = max(len(self.hexes), 1)
        w = self.width() / n
        for i, hx in enumerate(self.hexes):
            p.fillRect(QRectF(i * w, 3, w + 0.5, self.height() - 6), QColor(hx))
        p.end()


class _Bridge(QObject):
    """Sygnały z wątku silnika do wątku GUI (połączenie kolejkowane)."""

    progress = Signal(float)
    done = Signal(list)
    failed = Signal(str)


class ProposalsTab(QWidget):
    def __init__(self, win: MainWindow) -> None:
        super().__init__()
        self.win = win
        self.proposals: list[Proposal] = []
        self.base: Session | None = None
        self._cancel = False
        self.running = False
        self._thread: threading.Thread | None = None
        self.bridge = _Bridge()
        self.bridge.progress.connect(self._set_progress)
        self.bridge.done.connect(self._done)
        self.bridge.failed.connect(self._failed)

        lay = vbox(self, margins=8, spacing=6)
        help.attach(self, "window.tab.proposals")
        self.gen_all = QPushButton("Generuj wszystkie wolne (Ctrl+G)")
        self.gen_all.setDefault(True)
        self.gen_all.clicked.connect(lambda: self.start())
        self.gen_one = QPushButton("Generuj tylko zaznaczony kolor")
        self.gen_one.clicked.connect(self._gen_one)
        self.cancel_btn = QPushButton("Przerwij")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumWidth(260)
        for w, key in (
            (self.gen_all, "proposals.generate_all"),
            (self.gen_one, "proposals.generate_one"),
            (self.cancel_btn, "proposals.cancel"),
            (self.progress, "proposals.progress"),
        ):
            help.attach(w, key)
        lay.addWidget(hbox(self.gen_all, self.gen_one, self.cancel_btn, self.progress))
        self.status = QLabel("Brak propozycji — naciśnij Ctrl+G.")
        help.attach(self.status, "proposals.status")
        lay.addWidget(self.status)

        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        ll = vbox(left, spacing=4)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "stan", "wynik", "naruszenia", "paleta"])
        self._setup_table(self.table)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        help.attach(self.table, "proposals.list")
        help.attach_header(
            self.table,
            [
                "proposals.list",
                "proposals.col.state",
                "proposals.col.score",
                "proposals.col.violations",
                "proposals.col.strip",
            ],
        )
        self.table.currentCellChanged.connect(lambda r, *_: self._detail(r))
        self.table.cellDoubleClicked.connect(lambda *_: self.take_whole())
        ll.addWidget(self.table, 1)
        self.take_all_btn = QPushButton("Przejmij całą propozycję")
        self.take_all_btn.clicked.connect(self.take_whole)
        help.attach(self.take_all_btn, "proposals.take_all")
        ll.addWidget(hbox(self.take_all_btn))
        split.addWidget(left)

        right = QWidget()
        rl = vbox(right, spacing=4)
        self.detail = QTableWidget(0, 5)
        self.detail.setHorizontalHeaderLabels(["kolor", "teraz", "propozycja", "hex", "Δ fit"])
        self._setup_table(self.detail)
        self.detail.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        help.attach(self.detail, "proposals.detail")
        help.attach_header(self.detail, "proposals.detail")
        self.detail.cellDoubleClicked.connect(lambda *_: self.take_color())
        rl.addWidget(self.detail, 1)
        self.take_color_btn = QPushButton("Przejmij zaznaczony kolor")
        self.take_color_btn.clicked.connect(self.take_color)
        help.attach(self.take_color_btn, "proposals.take_color")
        rl.addWidget(hbox(self.take_color_btn))
        self.detail_violations = QLabel()
        self.detail_violations.setWordWrap(True)
        self.detail_violations.setTextFormat(Qt.TextFormat.RichText)
        help.attach(self.detail_violations, "proposals.violations")
        rl.addWidget(self.detail_violations)
        split.addWidget(right)
        split.setSizes([620, 560])
        lay.addWidget(split, 1)
        tip = hint(
            "Dwuklik na propozycji = przejmij całą (kłódki bez zmian); dwuklik na kolorze = "
            "przejmij tylko ten kolor. Ctrl+Z cofa. Te same ustawienia i ziarno dają te same "
            "propozycje."
        )
        help.attach(tip, "proposals.list")
        lay.addWidget(tip)
        self._update_buttons()

    @staticmethod
    def _setup_table(t: QTableWidget) -> None:
        t.verticalHeader().setVisible(False)
        t.verticalHeader().setDefaultSectionSize(28)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        t.setAlternatingRowColors(True)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def refresh_from_session(self) -> None:
        r = self.table.currentRow()
        if r >= 0:
            self._detail(r)

    def _update_buttons(self) -> None:
        has = bool(self.proposals)
        self.take_all_btn.setEnabled(has and not self.running)
        self.take_color_btn.setEnabled(has and not self.running)
        self.gen_all.setEnabled(not self.running)
        self.gen_one.setEnabled(not self.running)
        self.cancel_btn.setEnabled(self.running)
        self.progress.setVisible(self.running)

    # --- generowanie ---
    def start(self, slot_ids: Collection[str] | None = None) -> None:
        if self.running:
            self.win.notify("Generowanie już trwa.")
            return
        self.running = True
        self._cancel = False
        self.base = self.win.session
        self.progress.setValue(0)
        self.status.setText("Generowanie…")
        self._update_buttons()
        ids = None if slot_ids is None else set(slot_ids)
        session = self.base
        bridge = self.bridge

        def work() -> None:
            try:
                result = generate(
                    session,
                    slot_ids=ids,
                    progress=lambda x: bridge.progress.emit(float(x)),
                    cancel=lambda: self._cancel,
                )
            except Exception as e:  # błąd silnika pokazujemy, nie wywracamy GUI
                bridge.failed.emit(str(e))
                return
            bridge.done.emit(result)

        self._thread = threading.Thread(target=work, daemon=True)
        self._thread.start()

    def _gen_one(self) -> None:
        sid = self.win.selected_slot_id()
        if sid is None:
            self.win.notify("Najpierw zaznacz kolor na zakładce Paleta.")
            return
        self.start({sid})

    def cancel(self) -> None:
        self._cancel = True

    def wait(self, timeout: float | None = None) -> None:
        """Do testów: czeka na koniec wątku silnika."""
        if self._thread is not None:
            self._thread.join(timeout)

    def _set_progress(self, x: float) -> None:
        self.progress.setValue(round(x * 1000))

    def _failed(self, msg: str) -> None:
        self.running = False
        self.status.setText(f"<span style='color:{theme.colors().hard}'>Błąd silnika: {msg}</span>")
        self._update_buttons()

    def _done(self, result: list[Proposal]) -> None:
        self.running = False
        self.proposals = result
        self.progress.setValue(1000)
        ok = sum(p.ok for p in result)
        cancelled = " (przerwano)" if self._cancel else ""
        seed = self.base.globals.optimizer.seed if self.base else "?"
        self.status.setText(
            f"{len(result)} propozycji, {ok} bez twardych naruszeń{cancelled}. Ziarno {seed}."
        )
        self._fill()
        self._update_buttons()

    def _fill(self) -> None:
        t = self.table
        t.setRowCount(0)
        t.setRowCount(len(self.proposals))
        ids = [s.id for s in (self.base.slots if self.base else ())]
        for i, p in enumerate(self.proposals):
            hard = sum(v.hard for v in p.violations)
            soft = len(p.violations) - hard
            if p.timed_out:
                state, color = "⏱ niepowtarzalna", theme.colors().soft
            elif hard:
                state, color = "✗ łamie twarde", theme.colors().hard
            else:
                state, color = "✓", theme.colors().ok
            t.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            st = QTableWidgetItem(state)
            st.setForeground(QColor(color))
            t.setItem(i, 1, st)
            t.setItem(i, 2, QTableWidgetItem(f"{p.score:.3g}"))
            t.setItem(i, 3, QTableWidgetItem(f"{hard} tw. / {soft} mi."))
            strip = Strip([p.hexes[sid] for sid in ids if sid in p.hexes])
            help.attach(strip, "proposals.col.strip")
            t.setCellWidget(i, 4, strip)
        if self.proposals:
            t.setCurrentCell(0, 0)
            self._detail(0)
            t.setFocus()

    def _detail(self, i: int) -> None:
        d = self.detail
        d.setRowCount(0)
        if self.base is None or not 0 <= i < len(self.proposals):
            self.detail_violations.setText("")
            return
        p = self.proposals[i]
        cur = self.win.session
        cur_ids = {s.id: s for s in cur.slots}
        d.setRowCount(len(self.base.slots))
        for k, s in enumerate(self.base.slots):
            now = cur_ids.get(s.id)
            name = QTableWidgetItem(f"{k}: {slot_label(self.base, k)}")
            name.setData(Qt.ItemDataRole.UserRole, s.id)
            d.setItem(k, 0, name)
            now_item = QTableWidgetItem("" if now else "—")
            if now:
                now_item.setBackground(QColor(col.to_hex(now.value, cur.globals.fit_method)))
            d.setItem(k, 1, now_item)
            prop = QTableWidgetItem()
            prop.setBackground(QColor(p.hexes[s.id]))
            d.setItem(k, 2, prop)
            d.setItem(k, 3, QTableWidgetItem(p.hexes[s.id]))
            fit = p.fit_deltas.get(s.id, 0.0)
            d.setItem(k, 4, QTableWidgetItem(f"{fit:.3f}" if fit > 0 else ""))
        d.setColumnWidth(1, 64)
        d.setColumnWidth(2, 64)
        if not p.violations:
            ok = theme.colors().ok
            self.detail_violations.setText(
                f"<span style='color:{ok}'>✓ propozycja spełnia wszystkie warunki</span>"
            )
        else:
            lines = []
            for x in p.violations[:12]:
                mark, c = ("✗", theme.colors().hard) if x.hard else ("~", theme.colors().soft)
                lines.append(
                    f"<span style='color:{c}'>{mark}</span> {x.label}: wymagane {x.required}, "
                    f"jest {x.achieved}"
                )
            if len(p.violations) > 12:
                lines.append(f"… i {len(p.violations) - 12} więcej")
            self.detail_violations.setText("<br>".join(lines))

    # --- przejmowanie ---
    def _current(self) -> int | None:
        r = self.table.currentRow()
        if not self.proposals or not 0 <= r < len(self.proposals):
            return None
        return r

    def take_whole(self) -> None:
        i = self._current()
        if i is None:
            return
        p = self.proposals[i]
        # Tylko sloty, które propozycja zmieniała — reszta zostaje z bieżącej sesji.
        self.win.replace_session(apply_proposal(self.win.session, p, slot_ids=p.slot_ids))
        self.win.notify(f"Przejęto propozycję {i + 1} (kłódki bez zmian).")
        self._detail(i)

    def take_color(self) -> None:
        i = self._current()
        r = self.detail.currentRow()
        if i is None or r < 0:
            return
        item = self.detail.item(r, 0)
        sid = item.data(Qt.ItemDataRole.UserRole) if item else None
        slots = {s.id: s for s in self.win.session.slots}
        if sid not in slots:
            self.win.notify("Tego koloru już nie ma w palecie.")
            return
        if slots[sid].locked:
            self.win.notify("Kolor ma kłódkę — zdejmij ją, żeby przejąć propozycję.")
            return
        self.win.replace_session(
            apply_proposal(self.win.session, self.proposals[i], slot_ids={sid})
        )
        self.win.notify("Przejęto kolor.")
        self._detail(i)
        self.detail.setCurrentCell(r, 0)
