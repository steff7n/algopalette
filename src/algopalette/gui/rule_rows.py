"""Wiersze zakładki „Zasady”: jedna zasada widziana przez całe zaznaczenie kolorów.

Wiersz ma trzy stany (``rules_edit.Merged``):

* ``same`` — wszystkie zaznaczone kolory mają identyczną zasadę: włączona, twarda, waga, edytor
  wartości, „✕ usuń”;
* ``mixed`` — kolory się różnią: wartość każdego koloru, „ustaw dla zaznaczonych” (ujednolica
  według pierwszego zaznaczonego koloru, który zasadę ma) i „usuń u wszystkich”;
* ``absent`` — żaden kolor nie ma tej zasady: „+ dodaj”.

Zmiana wartości aktualizuje widżety w miejscu (``sync``), żeby fokus nie uciekał; o przebudowie
przy zmianie struktury decyduje zakładka, porównując ``row_signature``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from algopalette import rules_edit
from algopalette.forms import (
    CHROMA_MODES,
    CONTRAST_METRICS,
    EXTREMES,
    LABELS,
    default_for,
    range_spec,
    rule_summary,
)
from algopalette.gui import help
from algopalette.gui.band import BandSlider
from algopalette.gui.widgets import (
    NumEdit,
    RangeSlider,
    ValueSlider,
    channel_gradient,
    combo,
    hbox,
    vbox,
)
from algopalette.model import (
    OKLCH,
    Band,
    ChromaBand,
    ChromaMode,
    ContrastBound,
    ContrastMetric,
    HueArc,
    Rule,
    Session,
)

if TYPE_CHECKING:
    from algopalette.gui.rules_tab import RulesTab

BAND_FIELDS = ("lightness", "chroma", "hue")


def row_signature(session: Session, ids: tuple[str, ...], field: str) -> tuple[Any, ...]:
    """Struktura wiersza: zmiana tej krotki wymaga przebudowy, reszta to aktualizacja w miejscu."""
    m = rules_edit.merged_rule(session, ids, field)
    if m.state == "absent":
        return ("absent",)
    if m.state == "mixed":
        return ("mixed", tuple(rule_summary(field, r, session) for _, r in m.per_slot))
    assert m.rule is not None
    v = m.rule.value
    g = session.globals
    if field == "chroma":
        return ("same", v.mode)
    if field == "contrast_bg":
        return ("same", v.metric, g.contrast_metric)
    if field == "min_distance":
        return ("same", g.delta_e)
    return ("same",)


class RuleRow(QFrame):
    def __init__(self, tab: RulesTab, field: str) -> None:
        super().__init__()
        self.tab, self.field = tab, field
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName(f"rule-{field}")
        self.topic = f"rules.{field}"
        help.attach(self, self.topic)
        self._lay = vbox(self, margins=6, spacing=4)
        self.state = "absent"
        self.enabled_box: QCheckBox | None = None
        self.hard_box: QCheckBox | None = None
        self.weight_edit: NumEdit | None = None
        self.remove_btn: QPushButton | None = None
        self.add_btn: QPushButton | None = None
        self.unify_btn: QPushButton | None = None
        self.mixed_label: QLabel | None = None
        self.value_box: QWidget | None = None
        self.slider: Any = None  # BandSlider | RangeSlider | ValueSlider
        self.mode_combo: Any = None
        self.metric_combo: Any = None
        self.extreme_combo: Any = None
        self._build()

    # --- dostęp --------------------------------------------------------------------------------

    @property
    def session(self) -> Session:
        return self.tab.win.session

    @property
    def ids(self) -> tuple[str, ...]:
        return self.tab.ids

    def merged(self) -> rules_edit.Merged:
        return rules_edit.merged_rule(self.session, self.ids, self.field)

    def _key(self) -> str:
        return f"rule:{self.field}:{'|'.join(sorted(self.ids))}"

    # --- budowa --------------------------------------------------------------------------------

    def _build(self) -> None:
        m = self.merged()
        self.state = m.state
        head = QWidget()
        h = QHBoxLayout(head)
        h.setContentsMargins(0, 0, 0, 0)
        name = QLabel(f"<b>{LABELS[self.field]}</b>")
        name.setMinimumWidth(200)
        help.attach(name, self.topic)
        h.addWidget(name)
        self._lay.addWidget(head)
        if m.state == "absent":
            none = QLabel("<i>brak zasady</i>")
            help.attach(none, "rules.rule.add")
            h.addWidget(none)
            h.addStretch(1)
            self.add_btn = QPushButton("+ dodaj")
            help.attach(self.add_btn, "rules.rule.add")
            self.add_btn.clicked.connect(self._add)
            h.addWidget(self.add_btn)
            return
        if m.state == "mixed":
            self._build_mixed(h, m)
            return
        assert m.rule is not None
        rule = m.rule
        h.addSpacing(8)
        self.enabled_box = QCheckBox("włączona")
        self.enabled_box.setChecked(rule.enabled)
        help.attach(self.enabled_box, "rules.rule.enabled")
        self.enabled_box.clicked.connect(lambda on: self._flag("enabled", on))
        h.addWidget(self.enabled_box)
        self.hard_box = QCheckBox("twarda")
        self.hard_box.setChecked(rule.hard)
        help.attach(self.hard_box, "rules.rule.hard")
        self.hard_box.clicked.connect(lambda on: self._flag("hard", on))
        h.addWidget(self.hard_box)
        weight_label = QLabel("waga")
        help.attach(weight_label, "rules.rule.weight")
        h.addWidget(weight_label)
        self.weight_edit = NumEdit(rule.weight, minimum=0.0, step=0.1, width=56)
        help.attach(self.weight_edit, "rules.rule.weight")
        self.weight_edit.committed.connect(self._weight)
        h.addWidget(self.weight_edit)
        h.addStretch(1)
        self.remove_btn = QPushButton("✕ usuń")
        help.attach(self.remove_btn, "rules.rule.remove")
        self.remove_btn.clicked.connect(self._remove)
        h.addWidget(self.remove_btn)

        self.value_box = QWidget()
        box = QHBoxLayout(self.value_box)
        box.setContentsMargins(12, 0, 0, 0)
        self._value_widgets(box, rule.value)
        self._lay.addWidget(self.value_box)
        self._attach_values()
        self.value_box.setEnabled(rule.enabled)

    def _build_mixed(self, h: QHBoxLayout, m: rules_edit.Merged) -> None:
        index = {s.id: i for i, s in enumerate(self.session.slots)}
        parts = [
            f"{self.tab.label(index[sid])}: {rule_summary(self.field, r, self.session)}"
            for sid, r in m.per_slot
        ]
        self.mixed_label = QLabel("<i>różne</i> — " + " · ".join(parts))
        self.mixed_label.setWordWrap(True)
        help.attach(self.mixed_label, "rules.rule.mixed")
        h.addWidget(self.mixed_label, 1)
        self.unify_btn = QPushButton("ustaw dla zaznaczonych")
        help.attach(self.unify_btn, "rules.rule.unify")
        self.unify_btn.clicked.connect(self._unify)
        h.addWidget(self.unify_btn)
        self.remove_btn = QPushButton("✕ usuń u wszystkich")
        help.attach(self.remove_btn, "rules.rule.remove")
        self.remove_btn.clicked.connect(self._remove)
        h.addWidget(self.remove_btn)

    def _gradient(self, channel: str, rel: bool = False) -> Any:
        base = self.tab.base_color()
        if base is None:
            return None
        if channel == "h" and base.c < 0.05:
            base = OKLCH(base.l, 0.12, base.h)  # szary kolor: pokaż odcienie przy C 0.12
        return channel_gradient(base, channel, rel)

    def _value_widgets(self, box: QHBoxLayout, v: Any) -> None:
        f = self.field
        spec = range_spec(f, v, self.session)
        if f in BAND_FIELDS:
            if f == "chroma":
                self.mode_combo = combo(CHROMA_MODES, v.mode)
                help.attach(self.mode_combo, "rules.chroma.mode")
                self.mode_combo.activated.connect(
                    lambda _i: self._mode(self.mode_combo.currentData())
                )
                box.addWidget(self.mode_combo, 0, Qt.AlignmentFlag.AlignTop)
            channel = {"lightness": "l", "chroma": "c", "hue": "h"}[f]
            rel = f == "chroma" and v.mode == "rel"
            self.slider = BandSlider(
                v.lo,
                v.hi,
                v.exclude,
                gradient=self._gradient(channel, rel),
                center_fields=f == "hue",
                **spec,
            )
            self.slider.changed.connect(self._band)
            box.addWidget(self.slider, 1)
        elif f == "contrast_bg":
            self.metric_combo = combo(CONTRAST_METRICS, v.metric or "global")
            help.attach(self.metric_combo, "rules.contrast_bg.metric")
            self.metric_combo.activated.connect(
                lambda _i: self._metric(self.metric_combo.currentData())
            )
            box.addWidget(self.metric_combo)
            self.slider = RangeSlider(v.lo, v.hi, **spec)
            self.slider.changed.connect(self._contrast)
            box.addWidget(self.slider, 1)
        elif f == "min_distance":
            self.slider = ValueSlider(float(v), **spec)
            self.slider.changed.connect(self._number)
            box.addWidget(self.slider, 1)
        else:  # extreme
            self.extreme_combo = combo(EXTREMES, v)
            self.extreme_combo.activated.connect(
                lambda _i: self._set_value(self.extreme_combo.currentData())
            )
            box.addWidget(self.extreme_combo)
            box.addStretch(1)

    def _attach_values(self) -> None:
        """Klucz pomocy dla wszystkiego w edytorze wartości (także zakazów dodanych później)."""
        if self.value_box is not None:
            help.attach(self.value_box, self.topic, children=True)

    # --- aktualizacja w miejscu ----------------------------------------------------------------

    def sync(self) -> None:
        """Pokazuje bieżącą zasadę bez przebudowy (struktura wiersza musi być ta sama)."""
        if self.state != "same":
            return
        rule = self.merged().rule
        if rule is None:
            return
        assert (
            self.enabled_box is not None
            and self.hard_box is not None
            and self.weight_edit is not None
        )
        self.enabled_box.setChecked(rule.enabled)
        self.hard_box.setChecked(rule.hard)
        self.weight_edit.set_value(rule.weight)
        if self.value_box is not None:
            self.value_box.setEnabled(rule.enabled)
        v = rule.value
        if isinstance(self.slider, BandSlider):
            self.slider.set_values(v.lo, v.hi, v.exclude)
            self._attach_values()
        elif isinstance(self.slider, RangeSlider):
            self.slider.set_values(v.lo, v.hi)
        elif isinstance(self.slider, ValueSlider):
            self.slider.set_value(float(v))
        elif self.extreme_combo is not None:
            self.extreme_combo.setCurrentIndex(max(self.extreme_combo.findData(v), 0))

    # --- zapis ---------------------------------------------------------------------------------

    def _write(self, new: Session, *, coalesce: bool = False) -> None:
        self.tab.write(new, coalesce=self._key() if coalesce else None)

    def _add(self) -> None:
        rule = Rule(default_for(self.field, self.session))
        self._write(rules_edit.set_rule(self.session, self.ids, self.field, rule))

    def _remove(self) -> None:
        self._write(rules_edit.set_rule(self.session, self.ids, self.field, None))

    def _unify(self) -> None:
        self._write(rules_edit.set_rule(self.session, self.ids, self.field, self.merged().rule))

    def _flag(self, name: str, on: bool) -> None:
        changes: dict[str, Any] = {name: on}
        self._write(rules_edit.update_rule(self.session, self.ids, self.field, **changes))

    def _weight(self, w: float | None) -> None:
        if w is not None:
            new = rules_edit.update_rule(self.session, self.ids, self.field, weight=max(0.0, w))
            self._write(new, coalesce=True)

    def _set_value(self, value: Any) -> None:
        new = rules_edit.update_rule(self.session, self.ids, self.field, value=value)
        self._write(new, coalesce=True)

    def _band(self, lo: float | None, hi: float | None, exclude: Any) -> None:
        rule = self.merged().rule
        if rule is None:
            return
        if self.field == "lightness":
            value: Any = Band(lo, hi, exclude)
        elif self.field == "chroma":
            value = ChromaBand(rule.value.mode, lo, hi, exclude)
        else:
            value = HueArc(0.0 if lo is None else lo, 360.0 if hi is None else hi, exclude)
        self._set_value(value)
        self._attach_values()

    def _contrast(self, lo: float | None, hi: float | None) -> None:
        rule = self.merged().rule
        if rule is not None:
            self._set_value(replace(rule.value, lo=lo, hi=hi))

    def _number(self, x: float | None) -> None:
        if x is not None:
            self._set_value(float(x))

    def _mode(self, mode: str) -> None:
        rule = self.merged().rule
        if rule is None or mode == rule.value.mode:
            return
        lo, hi = (0.2, 0.6) if mode == "rel" else (0.05, 0.15)
        self._set_value(ChromaBand(cast(ChromaMode, mode), lo, hi))  # zakazy były w starej skali

    def _metric(self, value: str) -> None:
        rule = self.merged().rule
        if rule is None:
            return
        metric = None if value == "global" else cast(ContrastMetric, value)
        if metric == rule.value.metric:
            return
        used = metric or self.session.globals.contrast_metric
        self._set_value(ContrastBound(metric, 4.5 if used == "wcag21" else 60.0, None))


class SchemeRow(QFrame):
    """„układ odcieni: ☑ stosuj → cel X° ± Y°” — czy zaznaczone akcenty biorą cel z układu."""

    def __init__(self, tab: RulesTab) -> None:
        super().__init__()
        self.tab = tab
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("rule-scheme")
        help.attach(self, "rules.scheme_use")
        lay = vbox(self, margins=6, spacing=4)
        self.check = QCheckBox("układ odcieni: stosuj")
        self.check.clicked.connect(self._clicked)
        self.target = QLabel()
        self.link = QPushButton("układ odcieni całej palety →")
        self.link.setFlat(True)
        self.link.clicked.connect(self.tab.show_scheme_settings)
        for w in (self.check, self.target, self.link):
            help.attach(w, "rules.scheme_use")
        lay.addWidget(hbox(self.check, self.target, None, self.link))
        self.sync()

    def sync(self) -> None:
        s, ids = self.tab.win.session, self.tab.ids
        on = rules_edit.merged_use_scheme(s, ids)
        self.check.setTristate(on is None)
        state = Qt.CheckState.PartiallyChecked if on is None else Qt.CheckState.Unchecked
        self.check.setCheckState(Qt.CheckState.Checked if on else state)
        targets = self.tab.hue_targets()
        mine = [targets[i] for i in ids if i in targets]
        if not s.globals.hue_scheme.hues:
            text = "→ układ odcieni jest pusty — brak celów"
        elif not mine:
            text = "→ cel: —"
        else:
            hues = " / ".join(f"{t:.0f}°" for t in mine)
            text = f"→ cel {hues} ± {s.globals.hue_scheme.tol:.0f}°"
        self.target.setText(text)
        self.target.setEnabled(on is not False)

    def _clicked(self, _checked: bool) -> None:
        on = self.check.checkState() != Qt.CheckState.Unchecked
        self.check.setTristate(False)
        self.tab.write(rules_edit.set_use_scheme(self.tab.win.session, self.tab.ids, on))
