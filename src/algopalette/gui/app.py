"""Główne okno GUI: zakładki, panel naruszeń, historia (cofnij/ponów), autozapis, menu, skróty."""

from __future__ import annotations

import sys
import time
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QWidget,
)

from algopalette import io as aio
from algopalette.color import to_hex
from algopalette.engine import Violation, current_violations
from algopalette.forms import violation_text
from algopalette.gui import help, theme
from algopalette.gui.widgets import vbox
from algopalette.model import History, Session, ViewModel
from algopalette.pb_export import default_pb_dir, pb_json, write_pb_file

COALESCE_S = 1.5
AUTOSAVE_DELAY_MS = 500


PAIR_KINDS = ("pair_distance", "pair_cvd")
PALETTE_KINDS = ("spread", "diversity")


def rule_owners(v: Violation) -> tuple[str, ...]:
    """Kolory, w których zasadach leży przyczyna naruszenia (pusta krotka = cała paleta).

    Zasada kontrastu, zależność czy cel układu należą do pierwszego koloru naruszenia (tło albo
    cel zależności są tylko punktem odniesienia); próg pary akcentów — do obu."""
    if v.kind in PALETTE_KINDS:
        return ()
    return v.slot_ids[:2] if v.kind in PAIR_KINDS else v.slot_ids[:1]


class ViolationsPanel(QWidget):
    """Naruszenia bieżącej palety: ✗ twarde, ~ miękkie. Klik w wiersz prowadzi do zasady."""

    activated = Signal(object)  # Violation

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.shown: list[Violation] = []
        lay = vbox(self, margins=6, spacing=4)
        self.title = QLabel()
        f = self.title.font()
        f.setBold(True)
        self.title.setFont(f)
        lay.addWidget(self.title)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", "zasada", "wymagane", "jest"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.cellClicked.connect(self._activate)
        self.table.cellActivated.connect(self._activate)
        lay.addWidget(self.table, 1)

    def _activate(self, row: int, _column: int) -> None:
        if 0 <= row < len(self.shown):
            self.activated.emit(self.shown[row])

    def show_violations(self, violations: list[Violation], session: Session) -> None:
        hard = [v for v in violations if v.hard]
        soft = [v for v in violations if not v.hard]
        self.shown = [*hard, *soft]
        c = theme.colors()
        if not violations:
            self.title.setText(
                f"<span style='color:{c.ok}'>✓ Bieżąca paleta spełnia wszystkie zasady</span>"
            )
        else:
            hc = c.hard if hard else c.ok
            sc = c.soft if soft else c.ok
            self.title.setText(
                "Naruszenia bieżącej palety: "
                f"<span style='color:{hc}'>{len(hard)} twardych</span>, "
                f"<span style='color:{sc}'>{len(soft)} miękkich</span>"
            )
        t = self.table
        t.setRowCount(0)
        t.setRowCount(len(violations))
        for r, v in enumerate(self.shown):
            label, required, achieved = violation_text(v, session)
            mark = QTableWidgetItem("✗" if v.hard else "~")
            mark.setForeground(QColor(c.hard if v.hard else c.soft))
            mark.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setItem(r, 0, mark)
            t.setItem(r, 1, QTableWidgetItem(label))
            t.setItem(r, 2, QTableWidgetItem(required))
            t.setItem(r, 3, QTableWidgetItem(achieved))


class MainWindow(QMainWindow):
    def __init__(
        self,
        session: Session,
        *,
        notice: str | None = None,
        autosave: bool = True,
        file_path: Path | None = None,
    ) -> None:
        super().__init__()
        from algopalette.gui.analysis_tab import AnalysisTab
        from algopalette.gui.palette_tab import PaletteTab
        from algopalette.gui.proposals_tab import ProposalsTab
        from algopalette.gui.rules_tab import RulesTab
        from algopalette.gui.source_tab import SourceTab

        self.history = History(session)
        self.autosave_enabled = autosave
        self.file_path = file_path
        self._last_key: str | None = None
        self._last_time = 0.0
        self._autosave_pending = False
        self.violations: list[Violation] = []
        self.migration_notes: tuple[str, ...] = ()
        self._notes_box: QMessageBox | None = None

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(AUTOSAVE_DELAY_MS)
        self._autosave_timer.timeout.connect(self.autosave_now)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.rules_tab = RulesTab(self)
        self.proposals_tab = ProposalsTab(self)
        self.palette_tab = PaletteTab(self)
        self.analysis_tab = AnalysisTab(self)
        self.source_tab = SourceTab(self)
        for w, title in (
            (self.rules_tab, "Zasady"),
            (self.proposals_tab, "Propozycje"),
            (self.palette_tab, "Paleta"),
            (self.analysis_tab, "Analiza"),
            (self.source_tab, "Źródło"),
        ):
            self.tabs.addTab(w, title)
        self.tabs.currentChanged.connect(self._tab_changed)

        self.violations_panel = ViolationsPanel()
        self.violations_panel.activated.connect(self._violation_activated)
        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.tabs)
        split.addWidget(self.violations_panel)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 1)
        split.setSizes([640, 170])
        self.setCentralWidget(split)

        self._build_actions()
        self.resize(1360, 900)
        self._update_title()
        self.refresh_views(editor=True)
        theme.notifier.changed.connect(self._theme_changed)
        self._ui_ready = True
        if notice:
            self.notify(notice, timeout=12000)

    _ui_ready = False

    # --- stan -----------------------------------------------------------------------------
    @property
    def session(self) -> Session:
        cur = self.history.current
        assert cur is not None
        return cur

    def set_session(
        self, new: Session, *, coalesce: str | None = None, structural: bool = False
    ) -> None:
        """Nowy stan sesji. ``coalesce``: seria zmian tego samego pola = jeden krok cofania."""
        if new == self.session:
            return
        now = time.monotonic()
        if (
            coalesce is not None
            and coalesce == self._last_key
            and now - self._last_time < COALESCE_S
        ):
            self.history.replace_current(new)
        else:
            self.history.push(new)
        self._last_key, self._last_time = coalesce, now
        self.refresh_views(editor=structural)

    def replace_session(self, new: Session) -> None:
        """Podmiana całej sesji (wczytanie, przejęcie propozycji) — osobny krok cofania."""
        self.history.push(new)
        self._last_key = None
        self.refresh_views(editor=True)

    def set_view_model(self, mode: ViewModel) -> None:
        """Widok wartości (OKLCH/HSL) — preferencja widoku, NIE krok cofania."""
        if mode == self.session.view_model:
            return
        self.history.replace_current(replace(self.session, view_model=mode))
        self.refresh_views(editor=True)
        self.notify(
            "Widok wartości: " + ("HSL (zasady dalej w OKLCH)" if mode == "hsl" else "OKLCH")
        )

    def set_theme(self, mode: theme.ThemeMode) -> None:
        """Motyw z menu: stosowany od razu i zapamiętywany (błąd zapisu → pasek stanu)."""
        app = QApplication.instance()
        if isinstance(app, QApplication):
            theme.apply(app, mode)
        try:
            theme.save_mode(mode)
        except OSError as e:
            self.notify(f"Nie udało się zapamiętać motywu: {e}")

    def _theme_changed(self) -> None:
        """Przemalowanie po zmianie motywu: elementy z kolorami liczonymi przy budowie."""
        self.violations_panel.show_violations(self.violations, self.session)
        self.palette_tab.refresh_from_session(editor=True)
        self.proposals_tab.restyle()
        self._refresh_current_tab()
        self._update_actions()

    def toggle_view(self) -> None:
        self.set_view_model("oklch" if self.session.view_model == "hsl" else "hsl")

    def _keep_view(self, mode: ViewModel) -> None:
        if self.session.view_model != mode:
            self.history.replace_current(replace(self.session, view_model=mode))

    def refresh_views(self, *, editor: bool) -> None:
        """Po każdej zmianie sesji. ``editor``: zmiana przyszła spoza edytowanego właśnie pola
        (cofnij, wczytanie, zmiana struktury) — widoki budują się od nowa."""
        try:
            self.violations = current_violations(self.session)
        except ValueError as e:  # silnik odrzucił sesję — pokaż, nie wywracaj okna
            self.violations = []
            self.notify(f"Silnik nie przyjął zasad: {e}")
        self.violations_panel.show_violations(self.violations, self.session)
        self.palette_tab.refresh_from_session(editor=editor)
        if self.tabs.currentWidget() is self.rules_tab:
            self.rules_tab.refresh_from_session(force=editor)
        elif editor:
            self._refresh_current_tab()
        self._update_actions()
        self._schedule_autosave()

    def _refresh_current_tab(self) -> None:
        w = self.tabs.currentWidget()
        if w is self.rules_tab:
            self.rules_tab.refresh_from_session(force=True)
        elif w is self.analysis_tab:
            self.analysis_tab.refresh_from_session()
        elif w is self.proposals_tab:
            self.proposals_tab.refresh_from_session()

    def _tab_changed(self, _index: int) -> None:
        if self.tabs.currentWidget() is self.palette_tab:
            self.palette_tab.refresh_from_session(editor=True)
        else:
            self._refresh_current_tab()

    def show_rules(self, ids: Sequence[str]) -> None:
        """Otwiera zakładkę „Zasady” z zaznaczonymi kolorami (pusta lista = cała paleta)."""
        self.tabs.setCurrentWidget(self.rules_tab)
        self.rules_tab.strip.select(list(ids))
        self.rules_tab.flush()

    def _violation_activated(self, v: Violation) -> None:
        self.show_rules(rule_owners(v))

    def generate(self) -> None:
        """Start generowania dla kolorów bez kłódki + przejście do Propozycji."""
        self.tabs.setCurrentWidget(self.proposals_tab)
        self.proposals_tab.start()

    def show_migration_notes(self, notes: Sequence[str]) -> None:
        """Co przepadło albo zmieniło się przy wczytaniu pliku w starym formacie (nigdy cicho)."""
        self.migration_notes = tuple(notes)
        if not notes:
            return
        text = "Plik był w starszym formacie. Przy przenoszeniu zasad:\n• " + "\n• ".join(notes)
        self.notify(text.replace("\n", " "), timeout=30000)
        box = QMessageBox(
            QMessageBox.Icon.Information,
            "Wczytano starszy plik",
            text,
            QMessageBox.StandardButton.Ok,
            self,
        )
        box.setModal(False)
        box.show()
        self._notes_box = box

    def selected_slot_id(self) -> str | None:
        return self.palette_tab.table.selected_id()

    def notify(self, msg: str, *, error: bool = False, timeout: int = 6000) -> None:
        if error:
            QMessageBox.warning(self, "AlgoPalette", msg)
            return
        self.statusBar().showMessage(msg, timeout)

    # --- autozapis --------------------------------------------------------------------------
    def _schedule_autosave(self) -> None:
        if not self.autosave_enabled or not self._ui_ready:
            return
        self._autosave_pending = True
        self._autosave_timer.start()

    def autosave_now(self) -> None:
        self._autosave_pending = False
        try:
            aio.save_session(self.session, aio.autosave_path(), overwrite=True)
        except (OSError, ValueError) as e:
            self.notify(f"Autozapis nie powiódł się: {e}")

    def closeEvent(self, event) -> None:
        """Wyjście zapisuje zaległą zmianę (autozapis ma opóźnienie)."""
        self._autosave_timer.stop()
        if self.autosave_enabled and self._autosave_pending:
            self.autosave_now()
        self.proposals_tab.cancel()
        super().closeEvent(event)

    # --- akcje ------------------------------------------------------------------------------
    def _action(self, text: str, slot, shortcut: Any = None, tip: str = "") -> QAction:
        a = QAction(text, self)
        if shortcut is not None:
            if isinstance(shortcut, list):
                a.setShortcuts([QKeySequence(s) for s in shortcut])
            else:
                a.setShortcut(QKeySequence(shortcut))
        a.setToolTip(tip or text)
        a.setStatusTip(tip)
        a.triggered.connect(slot)
        self.addAction(a)
        return a

    def _build_actions(self) -> None:
        K = QKeySequence.StandardKey
        self.act_new = self._action("Nowa paleta", self.action_new, K.New)
        self.act_open = self._action("Wczytaj sesję…", self.action_open, K.Open)
        self.act_save = self._action("Zapisz", self.action_save, K.Save)
        self.act_save_as = self._action("Zapisz jako…", self.action_save_as, "Ctrl+Shift+S")
        self.act_export = self._action(
            "→ PaletteBuilder (schowek)",
            self.action_export,
            "Ctrl+E",
            "Skopiuj paletę do schowka w formacie okna „Wczytaj…” PaletteBuildera",
        )
        self.act_export_file = self._action(
            "Zapisz plik dla PaletteBuildera…", self.action_export_file, "Ctrl+Shift+E"
        )
        self.act_quit = self._action("Wyjście", self.close, K.Quit)
        self.act_undo = self._action("Cofnij", self.action_undo, "Ctrl+Z")
        self.act_redo = self._action("Ponów", self.action_redo, ["Ctrl+Y", "Ctrl+Shift+Z"])
        self.act_generate = self._action(
            "Generuj propozycje",
            self.generate,
            "Ctrl+G",
            "Policz propozycje dla wszystkich kolorów bez kłódki",
        )
        self.act_view = self._action(
            "Widok wartości HSL / OKLCH", self.toggle_view, "F7", "Przełącz widok wartości"
        )
        self.act_view.setCheckable(True)
        self.theme_group = QActionGroup(self)
        self.act_theme: dict[str, QAction] = {}
        for mode, text in (("system", "Systemowy"), ("light", "Jasny"), ("dark", "Ciemny")):
            a = self._action(
                text, lambda _=False, m=mode: self.set_theme(m), tip=f"Motyw okna: {text.lower()}"
            )
            a.setCheckable(True)
            self.theme_group.addAction(a)
            self.act_theme[mode] = a
        self.act_theme_system = self.act_theme["system"]
        self.act_theme_light = self.act_theme["light"]
        self.act_theme_dark = self.act_theme["dark"]
        for a in (self.act_undo, self.act_redo):
            a.setShortcutContext(Qt.ShortcutContext.WindowShortcut)

        mb = self.menuBar()
        self.menus: dict[str, QMenu] = {}
        m = self.menus["file"] = mb.addMenu("&Plik")
        for a in (
            self.act_new,
            self.act_open,
            None,
            self.act_save,
            self.act_save_as,
            None,
            self.act_export,
            self.act_export_file,
            None,
            self.act_quit,
        ):
            m.addSeparator() if a is None else m.addAction(a)
        m = self.menus["edit"] = mb.addMenu("&Edycja")
        m.addAction(self.act_undo)
        m.addAction(self.act_redo)
        m = self.menus["palette"] = mb.addMenu("P&aleta")
        m.addAction(self.act_generate)
        m.addSeparator()
        for a in self.palette_tab.slot_actions():
            m.addAction(a)
        m = self.menus["view"] = mb.addMenu("&Widok")
        m.addAction(self.act_view)
        self.theme_menu = m.addMenu("&Motyw")
        for a in self.act_theme.values():
            self.theme_menu.addAction(a)
        m.addSeparator()
        self.act_tabs: list[QAction] = []
        for i in range(self.tabs.count()):
            a = self._action(
                self.tabs.tabText(i), lambda _=False, i=i: self.tabs.setCurrentIndex(i), f"F{i + 2}"
            )
            m.addAction(a)
            self.act_tabs.append(a)
            self.tabs.setTabText(i, f"{self.tabs.tabText(i)}  (F{i + 2})")
        self.help = help.install(self)
        m = self.menus["help"] = mb.addMenu("Pomo&c")
        for a in self.help.actions():
            m.addAction(a)
        self.help.watch_menus()

        tb = QToolBar("Główne")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        for a in (
            self.act_undo,
            self.act_redo,
            None,
            self.act_generate,
            None,
            self.act_save,
            self.act_export,
            None,
            self.act_view,
        ):
            tb.addSeparator() if a is None else tb.addAction(a)
        self.addToolBar(tb)
        self.toolbar = tb
        self._attach_help()

    def _attach_help(self) -> None:
        """Klucze pomocy okna: akcje menu i paska, menu, zakładki, panel naruszeń."""
        for name, menu in self.menus.items():
            help.attach(menu.menuAction(), f"menu.{name}")
        help.attach(self.theme_menu.menuAction(), "menu.view.theme")
        for a, key in (
            (self.act_new, "menu.file.new"),
            (self.act_open, "menu.file.open"),
            (self.act_save, "menu.file.save"),
            (self.act_save_as, "menu.file.save_as"),
            (self.act_export, "menu.file.export"),
            (self.act_export_file, "menu.file.export_file"),
            (self.act_quit, "menu.file.quit"),
            (self.act_undo, "menu.edit.undo"),
            (self.act_redo, "menu.edit.redo"),
            (self.act_generate, "menu.generate"),
            (self.act_view, "menu.view.values"),
            (self.help.act_help, "general.help"),
            (self.help.act_info, "general.help"),
            (self.help.act_click, "general.help"),
            (self.help.act_start, "general.start"),
            (self.help.act_shortcuts, "general.shortcuts"),
            (self.help.act_index, "general.help"),
        ):
            help.attach(a, key)
        for a in self.act_theme.values():
            help.attach(a, "menu.view.theme")
        tab_keys = (
            "rules.tab",
            "window.tab.proposals",
            "window.tab.palette",
            "window.tab.analysis",
            "window.tab.source",
        )
        for i, (a, k) in enumerate(zip(self.act_tabs, tab_keys, strict=True)):
            help.attach(a, k)
            help.attach_tab(self.tabs, i, k)
        help.attach(self.toolbar, "window.toolbar")
        vp = self.violations_panel
        help.attach(vp, "window.violations")
        help.attach(vp.title, "window.violations")
        help.attach(vp.table, "window.violations")
        help.attach_header(
            vp.table,
            [
                "concept.hard_soft",
                "window.violations",
                "window.violations.values",
                "window.violations.values",
            ],
        )

    def _update_actions(self) -> None:
        self.act_undo.setEnabled(self.history.can_undo)
        self.act_redo.setEnabled(self.history.can_redo)
        self.act_view.setChecked(self.session.view_model == "hsl")
        self.act_view.setText("Widok: HSL" if self.session.view_model == "hsl" else "Widok: OKLCH")
        self.act_theme[theme.current_mode()].setChecked(True)

    def _update_title(self) -> None:
        name = self.file_path.name if self.file_path else "nowa paleta (autozapis)"
        self.setWindowTitle(f"AlgoPalette — {name}")

    def action_undo(self) -> None:
        mode = self.session.view_model
        if self.history.undo() is None:
            self.notify("Nie ma czego cofnąć.")
            return
        self._keep_view(mode)
        self._last_key = None
        self.refresh_views(editor=True)

    def action_redo(self) -> None:
        mode = self.session.view_model
        if self.history.redo() is None:
            self.notify("Nie ma czego ponowić.")
            return
        self._keep_view(mode)
        self._last_key = None
        self.refresh_views(editor=True)

    def action_new(self) -> None:
        from algopalette.__main__ import fresh_session

        ans = QMessageBox.question(
            self,
            "Nowa paleta",
            "Zacząć od nowej palety? Bieżącą przywrócisz przez Cofnij (Ctrl+Z).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans == QMessageBox.StandardButton.Yes:
            self.file_path = None
            self._update_title()
            self.replace_session(fresh_session())

    # --- pliki ------------------------------------------------------------------------------
    def _pb_text(self) -> str:
        s = self.session
        hexes = [to_hex(sl.value, s.globals.fit_method) for sl in s.slots]
        return pb_json(hexes, s.globals.polarity)

    def action_export(self) -> None:
        """Jednokierunkowo do PaletteBuildera: schowek."""
        QGuiApplication.clipboard().setText(self._pb_text())
        self.notify("Paleta w schowku — wklej w PaletteBuilderze: „Wczytaj…”.")

    def action_export_file(self) -> None:
        name = (self.file_path.stem if self.file_path else "algopalette") + ".json"
        default = default_pb_dir() / name
        path, _ = QFileDialog.getSaveFileName(
            self, "Plik dla PaletteBuildera", str(default), "JSON (*.json)"
        )
        if path:
            self.write_pb(Path(path), self._pb_text())

    def write_pb(self, path: Path, text: str) -> None:
        try:
            # okno wyboru pliku już zapytało o nadpisanie
            write_pb_file(text, path, overwrite=True)
        except OSError as e:
            self.notify(f"Nie udało się zapisać {path}: {e.strerror or e}", error=True)
            return
        self.notify(f"Zapisano {path}")

    def action_save(self) -> None:
        if self.file_path is None:
            self.action_save_as()
            return
        self.save_to(self.file_path)

    def action_save_as(self) -> None:
        default = self.file_path or (aio.default_palettes_dir() / "paleta.json")
        default.parent.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Zapisz sesję AlgoPalette", str(default), "Sesja AlgoPalette (*.json)"
        )
        if path:
            p = Path(path)
            if p.suffix == "":
                p = p.with_suffix(".json")
            self.save_to(p)

    def save_to(self, path: Path) -> bool:
        try:
            aio.save_session(self.session, path, overwrite=True)
        except (OSError, ValueError) as e:
            msg = e.strerror if isinstance(e, OSError) and e.strerror else e
            self.notify(f"Nie udało się zapisać {path}: {msg}", error=True)
            return False
        self.file_path = path
        self._update_title()
        self.notify(f"Zapisano {path}")
        return True

    def action_open(self) -> None:
        start = self.file_path or aio.default_palettes_dir()
        path, _ = QFileDialog.getOpenFileName(
            self, "Wczytaj sesję AlgoPalette", str(start), "Sesja AlgoPalette (*.json)"
        )
        if path:
            self.open_path(Path(path))

    def open_path(self, path: Path) -> bool:
        try:
            s, notes = aio.load_session_ex(path)
        except FileNotFoundError:
            self.notify(f"Nie ma pliku {path}", error=True)
            return False
        except aio.SessionFormatError as e:
            self.notify(str(e), error=True)
            return False
        except OSError as e:
            self.notify(f"Nie udało się odczytać {path}: {e.strerror or e}", error=True)
            return False
        self.file_path = path
        self._update_title()
        self.replace_session(s)
        self.notify(f"Wczytano {path}")
        self.show_migration_notes(notes)
        return True


def run(session: Session, *, notice: str | None = None, file_path: Path | None = None) -> int:
    app = cast(QApplication, QApplication.instance() or QApplication(sys.argv))
    app.setApplicationName("AlgoPalette")
    app.setDesktopFileName("algopalette")
    help.install_tooltip_style(app)
    theme.apply(app, theme.initial_mode())
    win = MainWindow(session, notice=notice, file_path=file_path)
    win.show()
    return app.exec()
