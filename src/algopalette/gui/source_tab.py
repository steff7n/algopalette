"""Zakładka „Źródło”: paleta wyjściowa (wklejona lista lub plik sesji) i trzy tryby."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QWidget,
)

from algopalette import color as col
from algopalette import io as aio
from algopalette.forms import POLARITIES, SOURCE_MODES
from algopalette.gui import help, theme
from algopalette.gui.widgets import NumEdit, Swatch, clear_layout, combo, form, hbox, hint, vbox
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

if TYPE_CHECKING:
    from algopalette.gui.app import MainWindow


class SourceTab(QScrollArea):
    def __init__(self, win: MainWindow) -> None:
        super().__init__()
        self.win = win
        self.source_colors: list[OKLCH] = []
        self._colors_text: str | None = None
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        lay = vbox(body, margins=10, spacing=10)
        self.setWidget(body)
        help.attach(self, "window.tab.source")

        box = QGroupBox("Kolory źródła")
        help.attach(box, "source.colors")
        bl = vbox(box, margins=10, spacing=6)
        formats = hint(
            "hex, oklch(…), rgb(…) — rozdzielone spacjami, przecinkami, średnikami "
            "albo liniami; najwyżej 16."
        )
        help.attach(formats, "source.paste")
        bl.addWidget(formats)
        self.paste = QPlainTextEdit()
        self.paste.setPlaceholderText("#1e1e2e #cdd6f4 #f38ba8 oklch(0.8 0.1 140) …")
        self.paste.setFixedHeight(110)
        help.attach(self.paste, "source.paste")
        bl.addWidget(self.paste)
        parse = QPushButton("Odczytaj")
        parse.clicked.connect(self.parse)
        from_file = QPushButton("Z pliku sesji…")
        from_file.clicked.connect(self._from_file)
        from_cur = QPushButton("Z bieżącej palety")
        from_cur.clicked.connect(
            lambda: self._from_session_colors(colors_from_session(self.win.session))
        )
        help.attach(parse, "source.parse")
        help.attach(from_file, "source.from_file")
        help.attach(from_cur, "source.from_current")
        bl.addWidget(hbox(parse, from_file, from_cur))
        self.result = QLabel()
        help.attach(self.result, "source.result")
        self.result.setWordWrap(True)
        bl.addWidget(self.result)
        self.swatches = QWidget()
        self._sw_lay = QHBoxLayout(self.swatches)
        self._sw_lay.setContentsMargins(0, 0, 0, 0)
        help.attach(self.swatches, "source.swatch")
        bl.addWidget(self.swatches)
        self.bg_index = QSpinBox()
        self.bg_index.setRange(1, 16)
        self.bg_index.setValue(1)
        self.fg_index = QSpinBox()
        self.fg_index.setRange(1, 16)
        self.fg_index.setValue(2)
        roles = hbox(QLabel("tło = nr"), self.bg_index, QLabel("tekst = nr"), self.fg_index)
        help.attach(roles, "source.roles", children=True)
        bl.addWidget(roles)
        lay.addWidget(box)

        box = QGroupBox("Tryb")
        help.attach(box, "source.mode")
        bl = vbox(box, margins=10, spacing=6)
        self.mode = combo(SOURCE_MODES, "complete")
        help.attach(self.mode, "source.mode")
        bl.addWidget(self.mode)
        w, fl = form()
        self.avoid = QCheckBox("unikaj kolorów źródła, min ΔE ok")
        self.avoid_distance = NumEdit(0.05, minimum=0.0, step=0.005, width=64)
        avoid_row = hbox(self.avoid, self.avoid_distance)
        help.attach(avoid_row, "source.avoid", children=True)
        fl.addRow("charakter:", avoid_row)
        self.polarity = combo([(label, v) for label, v in POLARITIES], "light")
        self.tol = NumEdit(None, minimum=0.0, step=0.1, allow_none=True, width=64)
        self.tol.setPlaceholderText("auto")
        transfer_row = hbox(
            QLabel("nowe tło"), self.polarity, QLabel("tolerancja kontrastu"), self.tol
        )
        help.attach(transfer_row, "source.transfer_options", children=True)
        fl.addRow("przeniesienie:", transfer_row)
        help.attach_form_labels(fl)
        bl.addWidget(w)
        modes = hint(
            "uzupełnianie — kolory trafiają do kolejnych miejsc z kłódką, resztę generujesz; "
            "charakter — profil palety (odcienie, nasycenie, jasność, zabarwienie tła) staje się "
            "zasadami kolorów; przeniesienie — każdy akcent zachowuje odcień, nasycenie "
            "względne i kontrast z nowym tłem."
        )
        help.attach(modes, "source.mode")
        bl.addWidget(modes)
        apply_btn = QPushButton("Zastosuj tryb do sesji")
        help.attach(apply_btn, "source.apply")
        apply_btn.clicked.connect(self.apply)
        bl.addWidget(hbox(apply_btn))
        lay.addWidget(box)
        lay.addStretch(1)

    # --- źródło ---
    def set_colors(self, colors: list[OKLCH]) -> None:
        self.source_colors = colors
        self._colors_text = self.paste.toPlainText()
        theme.mark_text(self.result, None)
        self.result.setText(f"{len(colors)} kolorów:")
        clear_layout(self._sw_lay)
        fit = self.win.session.globals.fit_method
        for i, c in enumerate(colors, 1):
            hx = col.to_hex(c, fit)
            sw = Swatch(hx, QSize(34, 26))
            help.attach(sw, "source.swatch", extra=f"{i}: {hx}")
            num = QLabel(str(i))
            help.attach(num, "source.swatch")
            self._sw_lay.addWidget(hbox(num, sw, stretch=False, spacing=2))
        self._sw_lay.addStretch(1)

    def parse(self) -> bool:
        try:
            colors = parse_colors(self.paste.toPlainText())
        except ParseError as e:
            self.source_colors = []
            clear_layout(self._sw_lay)
            theme.mark_text(self.result, "hard", bold=True)
            self.result.setText(f"✗ {e}")
            return False
        self.set_colors(colors)
        return True

    def apply(self) -> None:
        stale = self.paste.toPlainText() != self._colors_text
        if (stale or not self.source_colors) and not self.parse():
            return
        bg, fg = self.bg_index.value() - 1, self.fg_index.value() - 1
        mode = self.mode.currentData()
        s = self.win.session
        try:
            if mode == "complete":
                new = apply_complete(s, self.source_colors, bg, fg)
            elif mode == "character":
                dist = self.avoid_distance.value()
                new = apply_character(
                    s,
                    extract_profile(self.source_colors, bg, fg, s.globals.contrast_metric),
                    self.avoid.isChecked(),
                    0.05 if dist is None else dist,
                )
            else:
                new = apply_transfer(
                    s,
                    self.source_colors,
                    bg,
                    fg,
                    str(self.polarity.currentData()),
                    self.tol.value(),
                )
        except (ParseError, ValueError) as e:
            self.win.notify(str(e), error=True)
            return
        self.win.replace_session(new)
        self.win.notify("Tryb zastosowany — sprawdź zasady (F2) i generuj (Ctrl+G).")

    def _from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Plik sesji AlgoPalette jako źródło",
            str(aio.default_palettes_dir()),
            "Sesja AlgoPalette (*.json)",
        )
        if path:
            self.load_file(Path(path))

    def load_file(self, path: Path) -> None:
        try:
            s = aio.load_session(path)
        except (FileNotFoundError, aio.SessionFormatError, OSError) as e:
            self.win.notify(f"Nie można wczytać źródła: {e}", error=True)
            return
        self._from_session_colors(colors_from_session(s))

    def _from_session_colors(self, colors: list[OKLCH]) -> None:
        fit = self.win.session.globals.fit_method
        self.paste.setPlainText(" ".join(col.to_hex(c, fit) for c in colors))
        self.bg_index.setValue(1)
        self.fg_index.setValue(2)
        self.set_colors(colors)
