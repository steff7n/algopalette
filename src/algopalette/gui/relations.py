"""Edytor zależności koloru od innych kolorów (zakładka „Zasady”, jeden zaznaczony kolor)."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QCheckBox, QFrame, QGridLayout, QLabel, QPushButton, QWidget

from algopalette.engine import slot_label
from algopalette.forms import (
    REL_CHROMA_MODES,
    REL_CHROMA_OPS,
    REL_CONTRAST_METRICS,
    REL_DISTANCE_METRICS,
    REL_KINDS,
    REL_OPS,
    relation_default_value,
)
from algopalette.gui import help, theme
from algopalette.gui.widgets import NumEdit, clear_layout, combo, hbox, hint, vbox
from algopalette.model import Relation, broken_relations, slot_index, with_slot

if TYPE_CHECKING:
    from algopalette.gui.app import MainWindow

HELP = (
    "Przykłady: „odcień przeciwny do akcentu 1” = odcień, =, 180, tol 15; „ciemniejszy od tekstu "
    "o ≥ 0.1” = jasność, ≤, −0.1; „w połowie między akcentem 1 a 4” = mieszanka, t = 0.5."
)


class RelationsEditor(QWidget):
    def __init__(self, win: MainWindow, slot_id: str, parent=None) -> None:
        super().__init__(parent)
        self.win, self.slot_id = win, slot_id
        self._lay = vbox(self, spacing=6)
        help.attach(self, "rel.overview")
        self.rebuild()

    def relations(self) -> tuple[Relation, ...]:
        s = self.win.session
        return s.slots[slot_index(s, self.slot_id)].relations

    def alive(self) -> bool:
        return self.slot_id in {s.id for s in self.win.session.slots}

    def rebuild(self) -> None:
        clear_layout(self._lay)
        if not self.alive():
            return
        s = self.win.session
        broken = {i for sid, i in broken_relations(s) if sid == self.slot_id}
        rels = self.relations()
        if not rels:
            empty = hint("Brak zależności. " + HELP)
            help.attach(empty, "rel.overview")
            self._lay.addWidget(empty)
        for i, rel in enumerate(rels):
            self._lay.addWidget(RelationRow(self, i, rel, i in broken))
        add = QPushButton("+ dodaj zależność")
        help.attach(add, "rel.add")
        add.clicked.connect(self._add)
        self._lay.addWidget(hbox(add))

    def write(self, rels: tuple[Relation, ...], *, coalesce: str | None = None) -> None:
        if not self.alive():
            return
        s = self.win.session
        slot = s.slots[slot_index(s, self.slot_id)]
        self.win.set_session(with_slot(s, replace(slot, relations=rels)), coalesce=coalesce)

    def set_relation(self, i: int, rel: Relation | None, *, rebuild: bool = False) -> None:
        rels = list(self.relations())
        if rel is None:
            del rels[i]
        else:
            rels[i] = rel
        self.write(
            tuple(rels), coalesce=None if rebuild or rel is None else f"rel:{self.slot_id}:{i}"
        )
        if rebuild or rel is None:
            QTimer.singleShot(0, self.rebuild)

    def _add(self) -> None:
        s = self.win.session
        others = [sl.id for sl in s.slots if sl.id != self.slot_id]
        if not others:
            return
        self.write((*self.relations(), Relation("hue", others[0], "eq", 180.0, tol=15.0)))
        QTimer.singleShot(0, self.rebuild)


class RelationRow(QFrame):
    def __init__(self, editor: RelationsEditor, index: int, rel: Relation, broken: bool) -> None:
        super().__init__()
        self.editor, self.index, self.rel, self.broken = editor, index, rel, broken
        self.setFrameShape(QFrame.Shape.StyledPanel)
        if broken:
            theme.mark_error(self, True, "RelationRow")
        self._lay = vbox(self, margins=6, spacing=4)
        help.attach(self, f"rel.{rel.kind}")
        self.build()

    def _slot_options(self) -> list[tuple[str, str]]:
        s = self.editor.win.session
        return [
            (f"{i}: {slot_label(s, i)}", sl.id)
            for i, sl in enumerate(s.slots)
            if sl.id != self.editor.slot_id
        ]

    def build(self) -> None:
        clear_layout(self._lay)
        r = self.rel
        opts = self._slot_options()
        ids = {v for _, v in opts}

        kind = combo(REL_KINDS, r.kind)
        help.attach(kind, "rel.kind")
        kind.currentIndexChanged.connect(lambda _: self._kind(kind.currentData()))
        target = combo(opts, r.target if r.target in ids else None)
        help.attach(target, "rel.target")
        target.currentIndexChanged.connect(lambda _: self._pick("target", target.currentData()))
        delete = QPushButton("✕")
        help.attach(delete, "rel.delete")
        delete.setFixedWidth(32)
        delete.clicked.connect(lambda: self.editor.set_relation(self.index, None))
        warn = None
        if self.broken:
            warn = QLabel("⚠ zerwana")
            theme.mark_text(warn, "hard")
            help.attach(warn, "rel.broken")
        against = QLabel("względem")
        help.attach(against, "rel.target")
        top = hbox(kind, against, target, warn, delete)
        self._lay.addWidget(top)

        grid = QWidget()
        g = QGridLayout(grid)
        g.setContentsMargins(0, 0, 0, 0)
        row: list[QWidget] = []
        if r.kind == "mix":
            other = combo(opts, r.other if r.other in ids else None)
            other.currentIndexChanged.connect(lambda _: self._pick("other", other.currentData()))
            t = NumEdit(r.t, minimum=0.0, maximum=1.0, step=0.05, width=56)
            t.committed.connect(lambda v: self._num("t", v))
            tol = NumEdit(r.tol, minimum=0.0, step=0.005, width=64)
            tol.committed.connect(lambda v: self._num("tol", v))
            row += [QLabel("i"), other, QLabel("t"), t, QLabel("tol ΔE"), tol]
            for w in row:
                help.attach(w, "rel.mix")
        else:
            op = combo(REL_OPS, r.op)
            op.currentIndexChanged.connect(lambda _: self._pick("op", op.currentData()))
            value = NumEdit(
                r.value, step=0.01 if r.kind in ("lightness", "chroma") else 1.0, width=72
            )
            value.committed.connect(lambda v: self._num("value", v))
            tol = NumEdit(r.tol, minimum=0.0, step=0.01, width=64)
            tol.committed.connect(lambda v: self._num("tol", v))
            tol_label = QLabel("tol")
            help.attach(op, "rel.op")
            help.attach(value, f"rel.{r.kind}")
            help.attach(tol_label, "rel.tol")
            help.attach(tol, "rel.tol")
            row += [op, value, tol_label, tol]
        if r.kind == "chroma":
            cop = combo(REL_CHROMA_OPS, r.chroma_op)
            cop.currentIndexChanged.connect(lambda _: self._pick("chroma_op", cop.currentData()))
            cm = combo(REL_CHROMA_MODES, r.chroma_mode)
            cm.currentIndexChanged.connect(lambda _: self._pick("chroma_mode", cm.currentData()))
            help.attach(cop, "rel.chroma")
            help.attach(cm, "rel.chroma")
            row += [cop, cm]
        if r.kind in ("contrast", "distance"):
            opts_m = REL_CONTRAST_METRICS if r.kind == "contrast" else REL_DISTANCE_METRICS
            metric = combo(opts_m, r.metric or "global")
            metric.currentIndexChanged.connect(lambda _: self._metric(metric.currentData()))
            metric_label = QLabel("metryka")
            help.attach(metric_label, "rel.metric")
            help.attach(metric, "rel.metric")
            row += [metric_label, metric]
        for col, w in enumerate(row):
            g.addWidget(w, 0, col)
        g.setColumnStretch(len(row), 1)
        self._lay.addWidget(grid)

        enabled = QCheckBox("włączona")
        enabled.setChecked(r.enabled)
        enabled.toggled.connect(lambda on: self._update(enabled=on))
        hard = QCheckBox("twarda")
        hard.setChecked(r.hard)
        hard.toggled.connect(lambda on: self._update(hard=on))
        weight = NumEdit(r.weight, minimum=0.0, step=0.1, width=56)
        weight.committed.connect(lambda v: self._num("weight", v))
        weight_label = QLabel("waga")
        for w, key in (
            (enabled, "rules.rule.enabled"),
            (hard, "rules.rule.hard"),
            (weight_label, "rules.rule.weight"),
            (weight, "rules.rule.weight"),
        ):
            help.attach(w, key)
        self._lay.addWidget(hbox(enabled, hard, weight_label, weight))

    def _update(self, rebuild: bool = False, **changes: Any) -> None:
        new = replace(self.rel, **changes)
        if new == self.rel:
            return
        self.rel = new
        self.editor.set_relation(self.index, new, rebuild=rebuild)

    def _kind(self, kind: str) -> None:
        if kind == self.rel.kind:
            return
        self._update(
            rebuild=True,
            kind=kind,
            value=relation_default_value(kind, self.editor.win.session),
            metric=None,
            other=self.rel.other if kind == "mix" else None,
        )

    def _pick(self, field: str, value: Any) -> None:
        if value is None:
            return
        self._update(rebuild=field in ("target", "other") and self.broken, **{field: value})

    def _metric(self, value: str) -> None:
        self._update(metric=None if value == "global" else value)

    def _num(self, key: str, v: float | None) -> None:
        if v is None:
            return
        if key in ("tol", "weight"):
            v = max(v, 0.0)
        if key == "t":
            v = min(max(v, 0.0), 1.0)
        changes: dict[str, Any] = {key: v}
        self._update(**changes)
