"""Aplikacja TUI AlgoPalette: zakładki, stały panel naruszeń, historia, autozapis, skróty."""

from __future__ import annotations

import time
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane

from algopalette import io as aio
from algopalette.constraints import Violation, compile_terms, evaluate
from algopalette.hues import targets_for_session
from algopalette.model import History, Session
from algopalette.tui.dialogs import ConfirmScreen, HelpScreen, PathScreen
from algopalette.tui.palette_tab import PaletteTab

COALESCE_S = 1.5
AUTOSAVE_DELAY_S = 0.5


def current_violations(session: Session) -> list[Violation]:
    terms = compile_terms(session, hue_targets=targets_for_session(session))
    return evaluate(terms, {s.id: s.value for s in session.slots})


class ViolationsPanel(Vertical):
    DEFAULT_CSS = """
    ViolationsPanel { height: 10; border-top: solid $accent; }
    ViolationsPanel #viol-title { height: 1; text-style: bold; }
    ViolationsPanel DataTable { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="viol-title")
        yield DataTable(id="viol-table", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        t = self.query_one("#viol-table", DataTable)
        for c in ("", "warunek", "wymagane", "jest"):
            t.add_column(c)

    def show(self, violations: list[Violation]) -> None:
        hard = [v for v in violations if v.hard]
        soft = [v for v in violations if not v.hard]
        title = self.query_one("#viol-title", Static)
        if not violations:
            title.update(Text("✓ Bieżąca paleta spełnia wszystkie warunki", style="green"))
        else:
            title.update(
                Text.assemble(
                    ("Naruszenia bieżącej palety: ", "bold"),
                    (f"{len(hard)} twardych", "bold red" if hard else "green"),
                    ", ",
                    (f"{len(soft)} miękkich", "yellow" if soft else "green"),
                )
            )
        t = self.query_one("#viol-table", DataTable)
        t.clear()
        for v in [*hard, *soft]:
            mark = Text("✗", style="bold red") if v.hard else Text("~", style="yellow")
            t.add_row(mark, v.label, v.required, v.achieved)


class AlgoPaletteApp(App[None]):
    TITLE = "AlgoPalette"
    SUB_TITLE = "palety w OKLCH"
    CSS = """
    Screen { layout: vertical; }
    TabbedContent { height: 1fr; }
    .hint { color: $text-muted; height: 1; }
    Input.-invalid { background: $error 30%; }
    """
    BINDINGS = [
        Binding("ctrl+z", "undo", "Cofnij"),
        Binding("ctrl+y", "redo", "Ponów"),
        Binding("ctrl+s", "save", "Zapisz"),
        Binding("ctrl+o", "open", "Wczytaj"),
        Binding("g", "generate", "Generuj"),
        Binding("ctrl+e", "export", "→ PaletteBuilder"),
        Binding("f1", "help", "Pomoc"),
        Binding("f2", "tab('paleta')", "Paleta", show=False),
        Binding("f3", "tab('globalne')", "Globalne", show=False),
        Binding("f4", "tab('propozycje')", "Propozycje", show=False),
        Binding("f5", "tab('zrodlo')", "Źródło", show=False),
        Binding("f6", "tab('analiza')", "Analiza", show=False),
        Binding("ctrl+q", "quit", "Wyjście"),
    ]

    def __init__(
        self,
        session: Session,
        *,
        notice: str | None = None,
        autosave: bool = True,
        file_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.history = History(session)
        self.notice = notice
        self.autosave_enabled = autosave
        self.file_path = file_path
        self._last_key: str | None = None
        self._last_time = 0.0
        self._autosave_timer = None
        self.violations: list[Violation] = []
        self._ui_ready = False

    # --- stan ---
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

    def refresh_views(self, *, editor: bool) -> None:
        self.violations = current_violations(self.session)
        if self._ui_ready:
            self.query_one(ViolationsPanel).show(self.violations)
            self.query_one(PaletteTab).refresh_from_session(editor=editor)
            for tab in self.query(".session-view"):
                refresh = getattr(tab, "refresh_from_session", None)
                if refresh is not None:
                    refresh()
        self._schedule_autosave()

    def _schedule_autosave(self) -> None:
        if not self.autosave_enabled or not self._ui_ready:
            return
        if self._autosave_timer is not None:
            self._autosave_timer.stop()
        self._autosave_timer = self.set_timer(AUTOSAVE_DELAY_S, self.autosave_now)

    def autosave_now(self) -> None:
        try:
            aio.save_session(self.session, aio.autosave_path(), overwrite=True)
        except OSError as e:
            self.notify(f"Autozapis nie powiódł się: {e}", severity="error")

    # --- widok ---
    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="paleta"):
            with TabPane("Paleta (F2)", id="paleta"):
                yield PaletteTab(id="palette-tab")
            with TabPane("Globalne (F3)", id="globalne"):
                yield Static("(Task 9)", id="globals-placeholder")
            with TabPane("Propozycje (F4)", id="propozycje"):
                yield Static("(Task 9)", id="proposals-placeholder")
            with TabPane("Źródło (F5)", id="zrodlo"):
                yield Static("(Task 9)", id="source-placeholder")
            with TabPane("Analiza (F6)", id="analiza"):
                yield Static("(Task 10)", id="analysis-placeholder")
        yield ViolationsPanel(id="violations")
        yield Footer()

    def on_mount(self) -> None:
        self._ui_ready = True
        self.violations = current_violations(self.session)
        self.query_one(ViolationsPanel).show(self.violations)
        self.query_one("#slot-table").focus()
        if self.notice:
            self.notify(self.notice, severity="warning", timeout=8)

    # --- akcje ---
    def action_tab(self, tab: str) -> None:
        self.query_one(TabbedContent).active = tab

    def action_undo(self) -> None:
        if self.history.undo() is None:
            self.notify("Nie ma czego cofnąć.")
            return
        self._last_key = None
        self.refresh_views(editor=True)

    def action_redo(self) -> None:
        if self.history.redo() is None:
            self.notify("Nie ma czego ponowić.")
            return
        self._last_key = None
        self.refresh_views(editor=True)

    def action_help(self) -> None:
        rows = [(b.key, b.description) for b in self.BINDINGS if isinstance(b, Binding)]
        self.push_screen(HelpScreen(rows))

    def action_generate(self) -> None:
        self.notify("Generowanie: zakładka Propozycje (Task 9).")

    def action_export(self) -> None:
        self.notify("Eksport: Task 9.")

    def action_save(self) -> None:
        default = str(self.file_path or (aio.default_palettes_dir() / "paleta.json"))

        def done(path: str | None) -> None:
            if path:
                self.save_to(Path(path).expanduser())

        self.push_screen(PathScreen("Zapisz sesję AlgoPalette jako:", default), done)

    def save_to(self, path: Path, overwrite: bool = False) -> None:
        try:
            aio.save_session(self.session, path, overwrite=overwrite)
        except FileExistsError:

            def answer(yes: bool | None) -> None:
                if yes:
                    self.save_to(path, overwrite=True)

            self.push_screen(ConfirmScreen(f"Plik {path} istnieje. Nadpisać?"), answer)
            return
        except OSError as e:
            self.notify(f"Nie udało się zapisać {path}: {e.strerror or e}", severity="error")
            return
        self.file_path = path
        self.notify(f"Zapisano {path}")

    def action_open(self) -> None:
        default = str(self.file_path or aio.default_palettes_dir())

        def done(path: str | None) -> None:
            if path:
                self.open_path(Path(path).expanduser())

        self.push_screen(PathScreen("Wczytaj sesję AlgoPalette:", default), done)

    def open_path(self, path: Path) -> None:
        try:
            s = aio.load_session(path)
        except FileNotFoundError:
            self.notify(f"Nie ma pliku {path}", severity="error")
            return
        except aio.SessionFormatError as e:
            self.notify(str(e), severity="error")
            return
        except OSError as e:
            self.notify(f"Nie udało się odczytać {path}: {e.strerror or e}", severity="error")
            return
        self.file_path = path
        self.replace_session(s)
        self.notify(f"Wczytano {path}")
