"""Okna modalne: pomoc, potwierdzenie, ścieżka pliku."""

from __future__ import annotations

from collections.abc import Iterable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

HELP_EXTRA: list[tuple[str, str]] = [
    ("Suwak: ← / →", "krok"),
    ("Suwak: Shift+← / →", "krok gruby (×10)"),
    ("Suwak: Ctrl+← / →", "krok drobny (×0.1)"),
    ("Suwak: Home / End", "skraj zakresu"),
    ("Suwak: spacja", "przełącz uchwyt (zakres)"),
    ("Suwak: mysz", "klik / przeciągnięcie"),
    ("Pole liczby: Enter", "zatwierdź; puste = bez ograniczenia"),
    ("Lista slotów: a", "dodaj akcent"),
    ("Lista slotów: x / Delete", "usuń akcent"),
    ("Lista slotów: l", "kłódka"),
    ("Lista slotów: Shift+↑ / ↓", "przesuń akcent"),
]


class HelpScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    HelpScreen { align: center middle; }
    HelpScreen > Vertical {
        width: 80; height: 80%; border: thick $accent;
        background: $surface; padding: 1 2;
    }
    HelpScreen .key { width: 30; color: $accent; }
    """
    BINDINGS = [Binding("escape,f1,q", "close", "Zamknij")]

    def __init__(self, bindings: Iterable[tuple[str, str]]) -> None:
        super().__init__()
        self.rows = list(bindings) + HELP_EXTRA

    def compose(self) -> ComposeResult:
        with Vertical(id="help"):
            yield Label("[b]AlgoPalette — skróty[/b]  (Esc zamyka)")
            with VerticalScroll():
                for key, desc in self.rows:
                    yield Horizontal(Static(key, classes="key"), Static(desc), classes="help-row")

    def action_close(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmScreen { align: center middle; }
    ConfirmScreen > Vertical {
        width: 70; height: auto; border: thick $warning;
        background: $surface; padding: 1 2;
    }
    ConfirmScreen Horizontal { height: auto; margin-top: 1; }
    """
    BINDINGS = [Binding("escape", "no", "Nie")]

    def __init__(self, question: str) -> None:
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.question)
            with Horizontal():
                yield Button("Tak", id="yes", variant="warning", compact=True)
                yield Button("Nie", id="no", compact=True)

    def on_mount(self) -> None:
        self.query_one("#no", Button).focus()  # domyślnie „Nie” — Enter nie nadpisze pliku (M13)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_no(self) -> None:
        self.dismiss(False)


class PathScreen(ModalScreen[str | None]):
    """Pytanie o ścieżkę pliku (zapis/wczytanie/eksport)."""

    DEFAULT_CSS = """
    PathScreen { align: center middle; }
    PathScreen > Vertical {
        width: 90; height: auto; border: thick $accent;
        background: $surface; padding: 1 2;
    }
    PathScreen Horizontal { height: auto; margin-top: 1; }
    """
    BINDINGS = [Binding("escape", "cancel", "Anuluj")]

    def __init__(self, title: str, default: str) -> None:
        super().__init__()
        self.title_text = title
        self.default = default

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.title_text)
            yield Input(self.default, id="path")
            with Horizontal():
                yield Button("OK", id="ok", variant="primary", compact=True)
                yield Button("Anuluj", id="cancel", compact=True)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self.dismiss(self.query_one("#path", Input).value.strip() or None)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
