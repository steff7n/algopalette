"""Zakładka „Źródło”: paleta wyjściowa (wklejona lista lub plik sesji) i trzy tryby (spec §6)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, Input, Select, Static, TextArea

from algopalette import color as col
from algopalette import io as aio
from algopalette.model import OKLCH
from algopalette.sources import (
    ParseError,
    apply_character,
    apply_complete,
    apply_transfer,
    colors_from_session,
    extract_profile,
    parse_colors,
)
from algopalette.tui.dialogs import PathScreen
from algopalette.tui.widgets import Field, parse_finite, swatch

if TYPE_CHECKING:
    from algopalette.tui.app import AlgoPaletteApp

MODES = [
    ("uzupełnianie — podane kolory z kłódką, reszta generowana", "complete"),
    ("charakter — profil palety ustawia ustawienia globalne", "character"),
    ("przeniesienie — ta sama paleta na innym tle", "transfer"),
]


class SourceTab(VerticalScroll):
    DEFAULT_CSS = """
    SourceTab { padding: 0 1; }
    SourceTab .section { text-style: bold; color: $accent; margin-top: 1; }
    SourceTab TextArea { height: 8; }
    SourceTab #parse-result { height: auto; min-height: 2; }
    SourceTab #parse-result.-error { color: $error; }
    SourceTab Input { width: 8; height: 1; border: none; padding: 0; }
    SourceTab Select { width: 70; }
    SourceTab Checkbox { height: 1; border: none; padding: 0; width: auto; }
    SourceTab Horizontal { height: auto; }
    SourceTab Horizontal > Static { width: auto; }
    """

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.source_colors: list[OKLCH] = []
        self._colors_text: str | None = None  # tekst, z którego powstały source_colors

    @property
    def pal_app(self) -> AlgoPaletteApp:
        return cast("AlgoPaletteApp", self.app)

    def compose(self) -> ComposeResult:
        yield Static(
            "Kolory źródła (hex, oklch(), rgb()… — spacje, przecinki, średniki, linie)",
            classes="section",
        )
        yield TextArea(id="paste", placeholder="#1e1e2e #cdd6f4 #f38ba8 oklch(0.8 0.1 140) …")
        with Horizontal():
            yield Button("Odczytaj", id="parse", variant="primary", compact=True)
            yield Button("Z pliku sesji…", id="from-file", compact=True)
            yield Button("Z bieżącej palety", id="from-current", compact=True)
        yield Static("", id="parse-result")
        with Horizontal():
            yield Static("tło = nr ", classes="field-label")
            yield Input("1", id="bg-index", compact=True)
            yield Static("  tekst = nr ")
            yield Input("2", id="fg-index", compact=True)
        yield Static("Tryb", classes="section")
        yield Select(MODES, value="complete", allow_blank=False, id="mode", compact=True)
        yield Static("charakter:", classes="section")
        with Horizontal():
            yield Checkbox("unikaj kolorów źródła, min ΔE ok", False, id="avoid", compact=True)
            yield Input("0.05", id="avoid-distance", compact=True)
        yield Static("przeniesienie:", classes="section")
        yield Field(
            "nowe tło",
            Select(
                [("jasne", "light"), ("ciemne", "dark")],
                value="light",
                allow_blank=False,
                id="polarity",
                compact=True,
            ),
        )
        yield Field("tol. kontrastu", Input("", id="tol", placeholder="auto", compact=True))
        yield Button("Zastosuj tryb do sesji", id="apply", variant="warning", compact=True)

    # --- źródło ---
    def set_colors(self, colors: list[OKLCH]) -> None:
        self.source_colors = colors
        self._colors_text = self.query_one("#paste", TextArea).text
        res = self.query_one("#parse-result", Static)
        res.remove_class("-error")
        t = Text(f"{len(colors)} kolorów: ")
        fit = self.pal_app.session.globals.fit_method
        for i, c in enumerate(colors, 1):
            t.append(f" {i}:")
            t.append_text(swatch(col.to_hex(c, fit), 3))
        res.update(t)

    def parse(self) -> bool:
        text = self.query_one("#paste", TextArea).text
        res = self.query_one("#parse-result", Static)
        try:
            colors = parse_colors(text)
        except ParseError as e:
            self.source_colors = []
            res.add_class("-error")
            res.update(Text(f"✗ {e}", style="bold red"))
            return False
        self.set_colors(colors)
        return True

    def _indices(self) -> tuple[int, int] | None:
        try:
            bg = int(self.query_one("#bg-index", Input).value) - 1
            fg = int(self.query_one("#fg-index", Input).value) - 1
        except ValueError:
            self.notify("Numery tła i tekstu muszą być liczbami (od 1).", severity="error")
            return None
        return bg, fg

    def apply(self) -> None:
        stale = self.query_one("#paste", TextArea).text != self._colors_text
        if (stale or not self.source_colors) and not self.parse():  # tekst zmieniony → czytaj (I5)
            return
        idx = self._indices()
        if idx is None:
            return
        bg, fg = idx
        mode = self.query_one("#mode", Select).value
        s = self.pal_app.session
        try:
            if mode == "complete":
                new = apply_complete(s, self.source_colors, bg, fg)
            elif mode == "character":
                avoid = self.query_one("#avoid", Checkbox).value
                try:
                    dist = parse_finite(self.query_one("#avoid-distance", Input).value)
                except ValueError:
                    dist = 0.05
                new = apply_character(
                    s,
                    extract_profile(self.source_colors, bg, fg, s.globals.contrast_metric),
                    avoid,
                    dist,
                )
            else:
                pol = str(self.query_one("#polarity", Select).value)
                raw = self.query_one("#tol", Input).value.strip()
                tol = parse_finite(raw) if raw else None
                new = apply_transfer(s, self.source_colors, bg, fg, pol, tol)
        except (ParseError, ValueError) as e:
            self.notify(str(e), severity="error")
            return
        self.pal_app.replace_session(new)
        self.notify("Tryb zastosowany — sprawdź warunki na zakładkach i generuj (g).")

    @on(Button.Pressed)
    def _button(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid == "parse":
            self.parse()
        elif bid == "apply":
            self.apply()
        elif bid == "from-current":
            self._from_session_colors(colors_from_session(self.pal_app.session))
        elif bid == "from-file":
            self.app.push_screen(
                PathScreen("Plik sesji AlgoPalette jako źródło:", str(aio.default_palettes_dir())),
                self._load_file,
            )

    def _load_file(self, path: str | None) -> None:
        if not path:
            return
        try:
            s = aio.load_session(Path(path).expanduser())
        except (FileNotFoundError, aio.SessionFormatError, OSError) as e:
            self.notify(f"Nie można wczytać źródła: {e}", severity="error")
            return
        self._from_session_colors(colors_from_session(s))

    def _from_session_colors(self, colors: list[OKLCH]) -> None:
        fit = self.pal_app.session.globals.fit_method
        self.query_one("#paste", TextArea).text = " ".join(col.to_hex(c, fit) for c in colors)
        self.query_one("#bg-index", Input).value = "1"
        self.query_one("#fg-index", Input).value = "2"
        self.set_colors(colors)
