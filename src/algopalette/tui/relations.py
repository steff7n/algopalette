"""Edytor zależności slotu od innych slotów (spec §5.3)."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Input, Select, Static

from algopalette.constraints import slot_label
from algopalette.model import Relation, broken_relations, slot_index, with_slot
from algopalette.tui.widgets import parse_finite
from algopalette.units import default_distance

if TYPE_CHECKING:
    from algopalette.tui.app import AlgoPaletteApp

KINDS = [
    ("odcień (różnica °)", "hue"),
    ("jasność (różnica)", "lightness"),
    ("nasycenie", "chroma"),
    ("kontrast (ten → cel jako tło)", "contrast"),
    ("odległość ΔE", "distance"),
    ("mieszanka dwóch", "mix"),
]
OPS = [("= (± tol)", "eq"), ("≥", "ge"), ("≤", "le")]
DEFAULT_VALUE = {
    "hue": 180.0,
    "lightness": 0.0,
    "chroma": 1.0,
    "contrast": 4.5,
    "distance": 0.08,
    "mix": 0.0,
}


class RelationsEditor(Vertical):
    DEFAULT_CSS = """
    RelationsEditor { height: auto; }
    RelationsEditor > .rel-title { text-style: bold; margin-top: 1; }
    """

    def __init__(self, slot_id: str, **kw) -> None:
        super().__init__(**kw)
        self.slot_id = slot_id

    @property
    def pal_app(self) -> AlgoPaletteApp:
        return cast("AlgoPaletteApp", self.app)

    def relations(self) -> tuple[Relation, ...]:
        s = self.pal_app.session
        return s.slots[slot_index(s, self.slot_id)].relations

    def alive(self) -> bool:
        return self.slot_id in {s.id for s in self.pal_app.session.slots}

    def compose(self) -> ComposeResult:
        if not self.alive():
            return
        yield Static("Zależności od innych kolorów", classes="rel-title")
        s = self.pal_app.session
        broken = {i for sid, i in broken_relations(s) if sid == self.slot_id}
        for i, rel in enumerate(self.relations()):
            yield RelationRow(self, i, rel, i in broken, id=f"rel-{i}")
        yield Button("+ dodaj zależność", id="add-rel", compact=True)

    def write(self, rels: tuple[Relation, ...], *, coalesce: str | None = None) -> None:
        if not self.alive():
            return
        s = self.pal_app.session
        slot = s.slots[slot_index(s, self.slot_id)]
        self.pal_app.set_session(with_slot(s, replace(slot, relations=rels)), coalesce=coalesce)

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
            self.refresh(recompose=True)

    @on(Button.Pressed, "#add-rel")
    def _add(self, event: Button.Pressed) -> None:
        event.stop()
        s = self.pal_app.session
        others = [sl.id for sl in s.slots if sl.id != self.slot_id]
        if not others:
            return
        self.write((*self.relations(), Relation("hue", others[0], "eq", 180.0, tol=15.0)))
        self.refresh(recompose=True)


class RelationRow(Widget):
    DEFAULT_CSS = """
    RelationRow {
        height: auto; layout: vertical; border-left: tall $accent;
        padding-left: 1; margin-bottom: 1;
    }
    RelationRow.-broken { border-left: tall $error; }
    RelationRow Horizontal { height: auto; }
    RelationRow Select { width: 30; }
    RelationRow Select.narrow { width: 14; }
    RelationRow Input { width: 9; height: 1; border: none; padding: 0; }
    RelationRow .lbl { width: auto; padding: 0 1; color: $text-muted; }
    """

    def __init__(
        self, editor: RelationsEditor, index: int, rel: Relation, broken: bool, **kw
    ) -> None:
        super().__init__(**kw)
        self.editor, self.index, self.rel, self.broken = editor, index, rel, broken
        self.set_class(broken, "-broken")

    def _slot_options(self) -> list[tuple[str, str]]:
        s = self.editor.pal_app.session
        return [
            (slot_label(s, i), sl.id)
            for i, sl in enumerate(s.slots)
            if sl.id != self.editor.slot_id
        ]

    def compose(self) -> ComposeResult:
        r = self.rel
        opts = self._slot_options()
        ids = {v for _, v in opts}
        with Horizontal():
            yield Select(KINDS, value=r.kind, allow_blank=False, id="kind", compact=True)
            yield Static("względem", classes="lbl")
            yield Select(
                opts, value=r.target if r.target in ids else Select.NULL, id="target", compact=True
            )
            if self.broken:
                yield Static("⚠ zerwana", classes="lbl")
            yield Button("✕", id="del", compact=True)
        with Horizontal():
            if r.kind == "mix":
                yield Static("i", classes="lbl")
                yield Select(
                    opts, value=r.other if r.other in ids else Select.NULL, id="other", compact=True
                )
                yield Static("t", classes="lbl")
                yield Input(f"{r.t:g}", id="t", compact=True)
                yield Static("tol ΔE", classes="lbl")
                yield Input(f"{r.tol:g}", id="tol", compact=True)
            else:
                yield Select(
                    OPS, value=r.op, allow_blank=False, classes="narrow", id="op", compact=True
                )
                yield Input(f"{r.value:g}", id="value", compact=True)
                yield Static("tol", classes="lbl")
                yield Input(f"{r.tol:g}", id="tol", compact=True)
            if r.kind == "chroma":
                yield Select(
                    [("+ różnica", "add"), ("× mnożnik", "mul")],
                    value=r.chroma_op,
                    allow_blank=False,
                    classes="narrow",
                    id="chroma_op",
                    compact=True,
                )
                yield Select(
                    [("bezwzgl.", "abs"), ("względne", "rel")],
                    value=r.chroma_mode,
                    allow_blank=False,
                    classes="narrow",
                    id="chroma_mode",
                    compact=True,
                )
            if r.kind == "contrast":
                yield Select(
                    [("globalna", "global"), ("WCAG", "wcag21"), ("APCA", "apca")],
                    value=r.metric or "global",
                    allow_blank=False,
                    classes="narrow",
                    id="metric",
                    compact=True,
                )
            if r.kind == "distance":
                yield Select(
                    [
                        ("globalna", "global"),
                        ("ok", "ok"),
                        ("2000", "2000"),
                        ("hyab", "hyab"),
                        ("itp", "itp"),
                        ("cam16", "cam16"),
                    ],
                    value=r.metric or "global",
                    allow_blank=False,
                    classes="narrow",
                    id="metric",
                    compact=True,
                )
        with Horizontal():
            yield Static("wł.", classes="lbl")
            yield Checkbox("", r.enabled, id="enabled", compact=True)
            yield Static("twardy", classes="lbl")
            yield Checkbox("", r.hard, id="hard", compact=True)
            yield Static("waga", classes="lbl")
            yield Input(f"{r.weight:g}", id="weight", compact=True)

    def _update(self, rebuild: bool = False, **changes: Any) -> None:
        new = replace(self.rel, **changes)
        if new == self.rel:
            return
        self.rel = new
        self.editor.set_relation(self.index, new, rebuild=rebuild)

    @on(Button.Pressed, "#del")
    def _del(self, event: Button.Pressed) -> None:
        event.stop()
        self.editor.set_relation(self.index, None)

    @on(Select.Changed)
    def _select(self, event: Select.Changed) -> None:
        event.stop()
        sid = event.select.id
        val = event.value
        if val is Select.NULL or sid is None:
            return
        if sid == "kind":
            if val != self.rel.kind:
                g = self.editor.pal_app.session.globals
                value = DEFAULT_VALUE[str(val)]
                if val == "contrast" and g.contrast_metric == "apca":
                    value = 60.0
                elif val == "distance":
                    value = default_distance(g.delta_e, value)
                self._update(
                    rebuild=True,
                    kind=val,
                    value=value,
                    metric=None,
                    other=self.rel.other if val == "mix" else None,
                )
        elif sid == "metric":
            self._update(metric=None if val == "global" else val)
        elif sid in ("target", "other", "op", "chroma_op", "chroma_mode"):
            self._update(rebuild=sid in ("target", "other") and self.broken, **{sid: val})

    @on(Checkbox.Changed)
    def _switch(self, event: Checkbox.Changed) -> None:
        event.stop()
        if event.checkbox.id in ("enabled", "hard"):
            self._update(**{event.checkbox.id: event.value})

    @on(Input.Submitted)
    @on(Input.Blurred)
    def _input(self, event: Input.Submitted | Input.Blurred) -> None:
        event.stop()
        key = event.input.id
        if key not in ("value", "tol", "t", "weight"):
            return
        try:
            v = parse_finite(event.input.value)
        except ValueError:
            event.input.add_class("-bad")
            return
        event.input.remove_class("-bad")
        if key in ("tol", "weight"):
            v = max(v, 0.0)
        if key == "t":
            v = min(max(v, 0.0), 1.0)
        changes: dict[str, Any] = {key: v}
        self._update(**changes)
