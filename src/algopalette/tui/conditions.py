"""Edytor warunków (spec §5.2) — wspólny dla slotu i dla domyślnych warunków roli (Globalne).

Wiersz warunku: nazwa, źródło wartości (nastrój / globalne / własne), włącz, twardy, waga,
edytor wartości i przycisk „↺” (slot: wróć do dziedziczenia; rola: usuń warunek).
Zmiana dziedziczonej wartości w slocie
tworzy jego własną kopię warunku.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Literal, cast

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Input, Select, Static, Switch

from algopalette.model import (
    CONDITION_FIELDS,
    ChromaMode,
    ChromaRange,
    Cond,
    ContrastBound,
    ContrastMetric,
    HueRange,
    HueTarget,
    Interval,
    Role,
    Session,
    SlotConditions,
    effective_conditions,
    role_of,
    slot_index,
    snapshot_key,
    with_slot,
)
from algopalette.tui.widgets import RangeSlider, ValueSlider, source_badge

if TYPE_CHECKING:
    from algopalette.tui.app import AlgoPaletteApp

LABELS = {
    "lightness": "jasność L",
    "chroma": "nasycenie C",
    "hue_range": "zakres odcienia",
    "hue_target": "cel odcienia",
    "contrast_bg": "kontrast z tłem",
    "min_distance": "odległość od akcentów",
    "cvd_min_distance": "odróżnialność (daltonizm)",
    "extreme": "skrajny kontrast",
}

DEFAULTS: dict[str, Any] = {
    "lightness": Interval(0.5, 0.8),
    "chroma": ChromaRange("abs", 0.05, 0.15),
    "hue_range": HueRange(0.0, 60.0),
    "hue_target": HueTarget(0.0, 15.0),
    "contrast_bg": ContrastBound(None, 4.5, None),
    "min_distance": 0.08,
    "cvd_min_distance": 0.04,
    "extreme": "weakest",
}

ACCENT_ONLY = {"min_distance", "cvd_min_distance", "extreme"}


DISPLAY_ORDER = (
    "lightness",
    "chroma",
    "hue_range",
    "hue_target",
    "contrast_bg",
    "min_distance",
    "cvd_min_distance",
    "extreme",
)
assert set(DISPLAY_ORDER) == set(CONDITION_FIELDS)


def fields_for(role: Role) -> list[str]:
    out = []
    for f in DISPLAY_ORDER:
        if role != "accent" and f in ACCENT_ONLY:
            continue
        if role == "bg" and f == "contrast_bg":
            continue
        out.append(f)
    return out


class ConditionsEditor(Vertical):
    """``mode="slot"`` (klucz = id slotu) albo ``mode="role"`` (klucz = rola)."""

    DEFAULT_CSS = """
    ConditionsEditor { height: auto; }
    """

    def __init__(self, mode: Literal["slot", "role"], key: str, **kw) -> None:
        super().__init__(**kw)
        self.mode = mode
        self.key = key

    @property
    def pal_app(self) -> AlgoPaletteApp:
        return cast("AlgoPaletteApp", self.app)

    def role(self) -> Role:
        if self.mode == "role":
            return cast(Role, self.key)
        return role_of(slot_index(self.pal_app.session, self.key))

    def alive(self) -> bool:
        return self.mode == "role" or self.key in {s.id for s in self.pal_app.session.slots}

    def compose(self) -> ComposeResult:
        if not self.alive():  # slot usunięty, zanim edytor się zamontował
            return
        for f in fields_for(self.role()):
            yield ConditionRow(self, f, id=f"cond-{f}")

    # --- odczyt / zapis ---
    def read(self, field: str) -> tuple[Cond[Any] | None, str]:
        s = self.pal_app.session
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
        s = self.pal_app.session
        if self.mode == "slot":
            slot = s.slots[slot_index(s, self.key)]
            sc = replace(slot.conditions, **{field: cond})
            new = with_slot(s, replace(slot, conditions=sc))
        else:
            rd = dict(s.globals.role_defaults)
            role = cast(Role, self.key)
            rd[role] = replace(rd[role], **{field: cond})
            new = replace(s, globals=replace(s.globals, role_defaults=rd))
        self.pal_app.set_session(new, coalesce=f"{self.mode}:{self.key}:{field}")


def _range_spec(field: str, cond_value: Any, session: Session) -> dict[str, Any]:
    g = session.globals
    if field == "lightness":
        return {"minimum": 0.0, "maximum": 1.0, "step": 0.01, "fmt": ".3f", "allow_none": True}
    if field == "chroma":
        if cond_value.mode == "rel":
            return {"minimum": 0.0, "maximum": 1.0, "step": 0.01, "fmt": ".2f", "allow_none": True}
        return {"minimum": 0.0, "maximum": 0.37, "step": 0.005, "fmt": ".3f", "allow_none": True}
    if field == "hue_range":
        return {"minimum": 0.0, "maximum": 360.0, "step": 1.0, "fmt": ".0f", "wrap": True}
    if field == "hue_target":
        return {"minimum": 0.0, "maximum": 360.0, "step": 1.0, "fmt": ".0f", "wrap": True}
    if field == "contrast_bg":
        metric = cond_value.metric or g.contrast_metric
        if metric == "wcag21":
            return {"minimum": 1.0, "maximum": 21.0, "step": 0.1, "fmt": ".2f", "allow_none": True}
        return {"minimum": 0.0, "maximum": 108.0, "step": 1.0, "fmt": ".1f", "allow_none": True}
    # min_distance / cvd_min_distance
    if g.delta_e in ("ok", "hyab"):
        return {"minimum": 0.0, "maximum": 0.5, "step": 0.005, "fmt": ".3f"}
    return {"minimum": 0.0, "maximum": 100.0, "step": 0.5, "fmt": ".1f"}


class ConditionRow(Widget):
    DEFAULT_CSS = """
    ConditionRow { height: auto; layout: vertical; margin-bottom: 1; }
    ConditionRow .head { height: 1; }
    ConditionRow .name { width: 22; text-style: bold; }
    ConditionRow .badge { width: 11; }
    ConditionRow .lbl { width: auto; padding: 0 1; color: $text-muted; }
    ConditionRow Switch { height: 1; border: none; padding: 0; width: 5; }
    ConditionRow Input.weight, ConditionRow Input.tol {
        width: 7; height: 1; border: none; padding: 0;
    }
    ConditionRow Button { height: 1; min-width: 5; border: none; }
    ConditionRow .value { height: auto; padding-left: 2; }
    ConditionRow Select { width: 22; }
    ConditionRow.-off .value { opacity: 50%; }
    """

    def __init__(self, editor: ConditionsEditor, field: str, **kw) -> None:
        super().__init__(**kw)
        self.editor = editor
        self.field = field
        self.cond, self.src = editor.read(field)

    def compose(self) -> ComposeResult:
        cond = self.cond
        with Horizontal(classes="head"):
            yield Static(LABELS[self.field], classes="name")
            yield Static(source_badge(self.src), classes="badge", id="badge")
            if cond is None:
                yield Static("— brak —", classes="lbl")
                yield Button("+ dodaj", id="add")
                return
            yield Static("wł.", classes="lbl")
            yield Switch(cond.enabled, id="enabled", animate=False)
            yield Static("twardy", classes="lbl")
            yield Switch(cond.hard, id="hard", animate=False)
            yield Static("waga", classes="lbl")
            yield Input(f"{cond.weight:g}", id="weight", classes="weight", compact=True)
            reset = "↺ dziedzicz" if self.editor.mode == "slot" else "✕ usuń"
            if self.editor.mode == "role" or self.src == "slot":
                yield Button(reset, id="reset")
        with Horizontal(classes="value"):
            yield from self._value_widgets(cond.value)
        self.set_class(not cond.enabled, "-off")

    def _value_widgets(self, v: Any) -> ComposeResult:
        f = self.field
        spec = _range_spec(f, v, self.editor.pal_app.session)
        if f in ("lightness",):
            yield RangeSlider(v.lo, v.hi, id="v", **spec)
        elif f == "chroma":
            yield Select(
                [("bezwzgl.", "abs"), ("względne", "rel")],
                value=v.mode,
                allow_blank=False,
                id="mode",
                compact=True,
            )
            yield RangeSlider(v.lo, v.hi, id="v", **spec)
        elif f == "hue_range":
            yield RangeSlider(v.lo, v.hi, id="v", **spec)
        elif f == "hue_target":
            yield ValueSlider(v.target, id="v", **spec)
            yield Static("±", classes="lbl")
            yield Input(f"{v.tol:g}", id="tol", classes="tol", compact=True)
        elif f == "contrast_bg":
            yield Select(
                [("globalna", "global"), ("WCAG 2.1", "wcag21"), ("APCA", "apca")],
                value=v.metric or "global",
                allow_blank=False,
                id="metric",
                compact=True,
            )
            yield RangeSlider(v.lo, v.hi, id="v", **spec)
        elif f in ("min_distance", "cvd_min_distance"):
            yield ValueSlider(float(v), id="v", **spec)
        elif f == "extreme":
            yield Select(
                [("najsłabszy z akcentów", "weakest"), ("najmocniejszy z akcentów", "strongest")],
                value=v,
                allow_blank=False,
                id="extreme",
                compact=True,
            )

    # --- zmiany ---
    def _commit(self, cond: Cond[Any] | None, *, rebuild: bool = False) -> None:
        self.editor.write(self.field, cond)
        self.cond, self.src = self.editor.read(self.field)  # slot: None → wartość dziedziczona
        cond = self.cond
        if rebuild:
            self.refresh(recompose=True)
            return
        self.query_one("#badge", Static).update(source_badge(self.src))
        if cond is not None:
            self.set_class(not cond.enabled, "-off")
        has_reset = bool(self.query("#reset"))
        if self.editor.mode == "slot" and has_reset != (self.src == "slot"):
            self.refresh(recompose=True)

    def _set_value(self, value: Any, *, rebuild: bool = False) -> None:
        if self.cond is not None:
            self._commit(replace(self.cond, value=value), rebuild=rebuild)

    @on(Button.Pressed, "#add")
    def _add(self, event: Button.Pressed) -> None:
        event.stop()
        self._commit(Cond(DEFAULTS[self.field]), rebuild=True)

    @on(Button.Pressed, "#reset")
    def _reset(self, event: Button.Pressed) -> None:
        event.stop()
        self._commit(None, rebuild=True)

    @on(Switch.Changed, "#enabled")
    def _enabled(self, event: Switch.Changed) -> None:
        event.stop()
        if self.cond is not None and self.cond.enabled != event.value:
            self._commit(replace(self.cond, enabled=event.value))

    @on(Switch.Changed, "#hard")
    def _hard(self, event: Switch.Changed) -> None:
        event.stop()
        if self.cond is not None and self.cond.hard != event.value:
            self._commit(replace(self.cond, hard=event.value))

    @on(Input.Submitted, "#weight")
    @on(Input.Blurred, "#weight")
    def _weight(self, event: Input.Submitted | Input.Blurred) -> None:
        event.stop()
        try:
            w = max(0.0, float(event.input.value.replace(",", ".")))
        except ValueError:
            event.input.add_class("-invalid")
            return
        if self.cond is not None and w != self.cond.weight:
            self._commit(replace(self.cond, weight=w))

    @on(Input.Submitted, "#tol")
    @on(Input.Blurred, "#tol")
    def _tol(self, event: Input.Submitted | Input.Blurred) -> None:
        event.stop()
        try:
            tol = max(0.0, float(event.input.value.replace(",", ".")))
        except ValueError:
            return
        if self.cond is not None and tol != self.cond.value.tol:
            self._set_value(replace(self.cond.value, tol=tol))

    @on(RangeSlider.Changed, "#v")
    def _range(self, event: RangeSlider.Changed) -> None:
        event.stop()
        if self.cond is None:
            return
        v = self.cond.value
        if self.field == "hue_range":
            self._set_value(HueRange(event.lo or 0.0, event.hi if event.hi is not None else 360.0))
        else:
            self._set_value(replace(v, lo=event.lo, hi=event.hi))

    @on(ValueSlider.Changed, "#v")
    def _value(self, event: ValueSlider.Changed) -> None:
        event.stop()
        if self.cond is None or event.value is None:
            return
        if self.field == "hue_target":
            self._set_value(replace(self.cond.value, target=event.value))
        else:
            self._set_value(float(event.value))

    @on(Select.Changed, "#mode")
    def _mode(self, event: Select.Changed) -> None:
        event.stop()
        if self.cond is None or event.value == self.cond.value.mode:
            return
        lo, hi = (0.2, 0.6) if event.value == "rel" else (0.05, 0.15)
        mode = cast(ChromaMode, event.value)
        self._set_value(ChromaRange(mode, lo, hi), rebuild=True)

    @on(Select.Changed, "#metric")
    def _metric(self, event: Select.Changed) -> None:
        event.stop()
        if self.cond is None:
            return
        metric = None if event.value == "global" else cast(ContrastMetric, event.value)
        if metric == self.cond.value.metric:
            return
        session = self.editor.pal_app.session
        eff = metric or session.globals.contrast_metric
        lo = 4.5 if eff == "wcag21" else 60.0
        self._set_value(ContrastBound(metric, lo, None), rebuild=True)

    @on(Select.Changed, "#extreme")
    def _extreme(self, event: Select.Changed) -> None:
        event.stop()
        if self.cond is not None and event.value != self.cond.value:
            self._set_value(event.value)


__all__ = ["DEFAULTS", "LABELS", "ConditionsEditor", "SlotConditions", "fields_for"]
