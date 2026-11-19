"""Okienko parametrów generatora układu odcieni: liczba punktów (i rozpiętość dla analogicznego)."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QWidget

from algopalette.gui import help
from algopalette.model import MAX_ACCENTS

ANALOGOUS_SPREAD = 60
ANALOGOUS_POINTS = 3


class LayoutParamsDialog(QDialog):
    def __init__(self, parent: QWidget | None, key: str, points: int) -> None:
        super().__init__(parent)
        self.setWindowTitle("Analogiczny" if key == "analogous" else "Równo po kole")
        form = QFormLayout(self)
        self.points = QSpinBox()
        self.points.setRange(1, MAX_ACCENTS)
        self.points.setValue(points)
        form.addRow("liczba punktów", self.points)
        self.spread: QSpinBox | None = None
        if key == "analogous":
            self.spread = QSpinBox()
            self.spread.setRange(0, 360)
            self.spread.setSuffix("°")
            self.spread.setValue(ANALOGOUS_SPREAD)
            form.addRow("rozpiętość", self.spread)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        help.attach(self, "rules.hues.generate", children=True)

    def params(self) -> dict[str, float]:
        out: dict[str, float] = {"n": self.points.value()}
        if self.spread is not None:
            out["spread"] = self.spread.value()
        return out


def ask_layout_params(parent: QWidget | None, key: str, n_accents: int) -> dict[str, float] | None:
    """Pyta o parametry generatora ``analogous``/``equal``; ``None`` = anulowano."""
    points = ANALOGOUS_POINTS if key == "analogous" else max(1, n_accents)
    dlg = LayoutParamsDialog(parent, key, points)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return dlg.params()
