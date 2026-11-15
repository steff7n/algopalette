"""Edytor warunków — wspólny dla slotu i dla domyślnych warunków roli (zakładka Globalne).

Wiersz warunku: nazwa, źródło wartości (nastrój / globalne / własne), włącz, twardy, waga, edytor
wartości i przycisk „↺ dziedzicz” (slot) albo „✕ usuń” (rola). Zmiana dziedziczonej wartości
w slocie tworzy jego własną kopię warunku.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Literal, cast

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from algopalette.forms import (
    CHROMA_MODES,
    CONTRAST_METRICS,
    EXTREMES,
    LABELS,
    default_for,
    fields_for,
    range_spec,
)
from algopalette.gui import help, theme
from algopalette.gui.widgets import (
    SOURCE_LABELS,
    NumEdit,
    RangeSlider,
    ValueSlider,
    channel_gradient,
    clear_layout,
    vbox,
)
from algopalette.model import (
    OKLCH,
    ChromaMode,
    ChromaRange,
    Cond,
    ContrastBound,
    ContrastMetric,
    HueRange,
    Role,
    effective_conditions,
    role_of,
    slot_index,
    snapshot_key,
    with_slot,
)

if TYPE_CHECKING:
    from algopalette.gui.app import MainWindow


def combo(options: list[tuple[str, Any]], value: Any) -> QComboBox:
    c = QComboBox()
    for label, data in options:
        c.addItem(label, data)
    i = c.findData(value)
    c.setCurrentIndex(max(i, 0) if value is not None else -1)
    c.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    return c


class ConditionsEditor(QWidget):
    """``mode="slot"`` (klucz = id slotu) albo ``mode="role"`` (klucz = rola)."""

    def __init__(self, win: MainWindow, mode: Literal["slot", "role"], key: str, parent=None):
        super().__init__(parent)
        self.win, self.mode, self.key = win, mode, key
        self._lay = vbox(self, spacing=6)
        help.attach(self, "cond.overview")
        self.rebuild()

    def role(self) -> Role:
        if self.mode == "role":
            return cast(Role, self.key)
        return role_of(slot_index(self.win.session, self.key))

    def alive(self) -> bool:
        return self.mode == "role" or self.key in {s.id for s in self.win.session.slots}

    def rebuild(self) -> None:
        clear_layout(self._lay)
        if not self.alive():
            return
        for f in fields_for(self.role()):
            self._lay.addWidget(ConditionRow(self, f))

    def base_color(self) -> OKLCH | None:
        if self.mode == "slot" and self.alive():
            s = self.win.session
            return s.slots[slot_index(s, self.key)].value
        return None

    # --- odczyt / zapis ---
    def read(self, field: str) -> tuple[Cond[Any] | None, str]:
        s = self.win.session
        if self.mode == "slot":
            eff, src = effective_conditions(s, self.key)
            return getattr(eff, field), src[field]
        role = cast(Role, self.key)
        cond = getattr(s.globals.role_defaults[role], field)
        snap = s.mood_snapshot
        k = snapshot_key(role, field)
        src = "mood" if snap is not None and k in snap and snap[k] == cond else "global"
        return cond, src

    def write(self, field: str, cond: Cond[Any] | None) -> None:
        if not self.alive():
            return
        s = self.win.session
        if self.mode == "slot":
            slot = s.slots[slot_index(s, self.key)]
            sc = replace(slot.conditions, **{field: cond})
            new = with_slot(s, replace(slot, conditions=sc))
        else:
            rd = dict(s.globals.role_defaults)
            role = cast(Role, self.key)
            rd[role] = replace(rd[role], **{field: cond})
            new = replace(s, globals=replace(s.globals, role_defaults=rd))
        self.win.set_session(new, coalesce=f"{self.mode}:{self.key}:{field}")


class ConditionRow(QFrame):
    def __init__(self, editor: ConditionsEditor, field: str) -> None:
        super().__init__()
        self.editor, self.field = editor, field
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName(f"cond-{field}")
        self._lay = vbox(self, margins=6, spacing=4)
        self.cond, self.src = editor.read(field)
        self.build()

    @property
    def win(self) -> MainWindow:
        return self.editor.win

    def build(self) -> None:
        clear_layout(self._lay)
        self.reset: QPushButton | None = None
        self.value_box: QWidget | None = None
        cond = self.cond
        topic = f"cond.{self.field}"
        help.attach(self, topic)
        head = QWidget()
        h = QHBoxLayout(head)
        h.setContentsMargins(0, 0, 0, 0)
        name = QLabel(f"<b>{LABELS[self.field]}</b>")
        help.attach(name, topic)
        name.setMinimumWidth(170)
        h.addWidget(name)
        self.badge = QLabel()
        help.attach(self.badge, "cond.badge")
        h.addWidget(self.badge)
        self._update_badge()
        if cond is None:
            none = QLabel("<i>brak warunku</i>")
            help.attach(none, "cond.add")
            h.addWidget(none)
            h.addStretch(1)
            add = QPushButton("+ dodaj")
            help.attach(add, "cond.add")
            add.clicked.connect(self._add)
            h.addWidget(add)
            self._lay.addWidget(head)
            return
        h.addSpacing(8)
        self.enabled = QCheckBox("włączony")
        self.enabled.setChecked(cond.enabled)
        help.attach(self.enabled, "cond.enabled")
        self.enabled.toggled.connect(self._enabled)
        h.addWidget(self.enabled)
        self.hard = QCheckBox("twardy")
        self.hard.setChecked(cond.hard)
        help.attach(self.hard, "cond.hard")
        self.hard.toggled.connect(self._hard)
        h.addWidget(self.hard)
        weight_label = QLabel("waga")
        help.attach(weight_label, "cond.weight")
        h.addWidget(weight_label)
        self.weight = NumEdit(cond.weight, minimum=0.0, step=0.1, width=56)
        help.attach(self.weight, "cond.weight")
        self.weight.committed.connect(self._weight)
        h.addWidget(self.weight)
        h.addStretch(1)
        self.reset = QPushButton("↺ dziedzicz" if self.editor.mode == "slot" else "✕ usuń")
        help.attach(self.reset, "cond.reset" if self.editor.mode == "slot" else "cond.remove")
        self.reset.clicked.connect(self._reset)
        h.addWidget(self.reset)
        self._update_reset()
        self._lay.addWidget(head)

        self.value_box = QWidget()
        g = QGridLayout(self.value_box)
        g.setContentsMargins(12, 0, 0, 0)
        self._value_widgets(g, cond.value)
        for i in range(g.count()):
            item = g.itemAt(i)
            w = item.widget() if item is not None else None
            if w is not None and help.key_of(w) is None:
                help.attach(w, topic, children=True)
        self._lay.addWidget(self.value_box)
        self._update_enabled()

    def _update_badge(self) -> None:
        src = self.src
        self.badge.setText(SOURCE_LABELS.get(src, src))
        theme.style_badge(self.badge, src)

    def _update_reset(self) -> None:
        if self.reset is not None:
            self.reset.setVisible(self.editor.mode == "role" or self.src == "slot")

    def _update_enabled(self) -> None:
        if self.value_box is not None and self.cond is not None:
            self.value_box.setEnabled(self.cond.enabled)

    def _gradient(self, channel: str, rel: bool = False):
        base = self.editor.base_color()
        if base is None:
            base = {
                "l": OKLCH(0.5, 0.0, 0.0),
                "c": OKLCH(0.7, 0.0, 250.0),
                "h": OKLCH(0.75, 0.13, 0.0),
            }[channel]
            if channel == "c":
                return None  # bez konkretnego koloru gradient nasycenia nic nie mówi
        elif channel == "h" and base.c < 0.05:
            base = OKLCH(base.l, 0.12, base.h)  # szary slot: pokaż odcienie przy C 0.12
        return channel_gradient(base, channel, rel)

    def _value_widgets(self, g: QGridLayout, v: Any) -> None:
        f = self.field
        spec = range_spec(f, v, self.win.session)
        if f == "lightness":
            w = RangeSlider(v.lo, v.hi, gradient=self._gradient("l"), **spec)
            w.changed.connect(self._range)
            g.addWidget(w, 0, 0, 1, 3)
        elif f == "chroma":
            mode = combo(CHROMA_MODES, v.mode)
            help.attach(mode, "cond.chroma.mode")
            mode.currentIndexChanged.connect(lambda _: self._mode(mode.currentData()))
            g.addWidget(mode, 0, 0)
            w = RangeSlider(v.lo, v.hi, gradient=self._gradient("c", v.mode == "rel"), **spec)
            w.changed.connect(self._range)
            g.addWidget(w, 0, 1, 1, 2)
        elif f == "hue_range":
            w = RangeSlider(v.lo, v.hi, gradient=self._gradient("h"), **spec)
            w.changed.connect(self._range)
            g.addWidget(w, 0, 0, 1, 3)
        elif f == "hue_target":
            w = ValueSlider(v.target, gradient=self._gradient("h"), **spec)
            w.changed.connect(self._value)
            g.addWidget(w, 0, 0)
            g.addWidget(QLabel("±"), 0, 1)
            tol = NumEdit(v.tol, minimum=0.0, maximum=180.0, step=1.0, width=56)
            tol.committed.connect(self._tol)
            g.addWidget(tol, 0, 2)
        elif f == "contrast_bg":
            metric = combo(CONTRAST_METRICS, v.metric or "global")
            help.attach(metric, "cond.contrast_bg.metric")
            metric.currentIndexChanged.connect(lambda _: self._metric(metric.currentData()))
            g.addWidget(metric, 0, 0)
            w = RangeSlider(v.lo, v.hi, **spec)
            w.changed.connect(self._range)
            g.addWidget(w, 0, 1, 1, 2)
        elif f in ("min_distance", "cvd_min_distance"):
            w = ValueSlider(float(v), **spec)
            w.changed.connect(self._value)
            g.addWidget(w, 0, 0, 1, 3)
        elif f == "extreme":
            ex = combo(EXTREMES, v)
            ex.currentIndexChanged.connect(lambda _: self._extreme(ex.currentData()))
            g.addWidget(ex, 0, 0, Qt.AlignmentFlag.AlignLeft)
        g.setColumnStretch(0 if f in ("hue_target",) else 1, 1)

    # --- zmiany ---
    def _commit(self, cond: Cond[Any] | None, *, rebuild: bool = False) -> None:
        self.editor.write(self.field, cond)
        self.cond, self.src = self.editor.read(self.field)  # slot: None → wartość dziedziczona
        if rebuild:
            QTimer.singleShot(0, self.build)
            return
        self._update_badge()
        self._update_reset()
        self._update_enabled()

    def _set_value(self, value: Any, *, rebuild: bool = False) -> None:
        if self.cond is not None:
            self._commit(replace(self.cond, value=value), rebuild=rebuild)

    def _add(self) -> None:
        self._commit(Cond(default_for(self.field, self.win.session)), rebuild=True)

    def _reset(self) -> None:
        self._commit(None, rebuild=True)

    def _enabled(self, on: bool) -> None:
        if self.cond is not None and self.cond.enabled != on:
            self._commit(replace(self.cond, enabled=on))

    def _hard(self, on: bool) -> None:
        if self.cond is not None and self.cond.hard != on:
            self._commit(replace(self.cond, hard=on))

    def _weight(self, w: float | None) -> None:
        if self.cond is not None and w is not None and w != self.cond.weight:
            self._commit(replace(self.cond, weight=max(0.0, w)))

    def _tol(self, tol: float | None) -> None:
        if self.cond is not None and tol is not None and tol != self.cond.value.tol:
            self._set_value(replace(self.cond.value, tol=max(0.0, tol)))

    def _range(self, lo: float | None, hi: float | None) -> None:
        if self.cond is None:
            return
        if self.field == "hue_range":
            self._set_value(HueRange(lo or 0.0, hi if hi is not None else 360.0))
        else:
            self._set_value(replace(self.cond.value, lo=lo, hi=hi))

    def _value(self, x: float | None) -> None:
        if self.cond is None or x is None:
            return
        if self.field == "hue_target":
            self._set_value(replace(self.cond.value, target=x))
        else:
            self._set_value(float(x))

    def _mode(self, mode: str) -> None:
        if self.cond is None or mode == self.cond.value.mode:
            return
        lo, hi = (0.2, 0.6) if mode == "rel" else (0.05, 0.15)
        self._set_value(ChromaRange(cast(ChromaMode, mode), lo, hi), rebuild=True)

    def _metric(self, value: str) -> None:
        if self.cond is None:
            return
        metric = None if value == "global" else cast(ContrastMetric, value)
        if metric == self.cond.value.metric:
            return
        eff = metric or self.win.session.globals.contrast_metric
        lo = 4.5 if eff == "wcag21" else 60.0
        self._set_value(ContrastBound(metric, lo, None), rebuild=True)

    def _extreme(self, value: str) -> None:
        if self.cond is not None and value != self.cond.value:
            self._set_value(value)
