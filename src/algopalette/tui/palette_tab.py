"""Zakładka „Paleta”: lista slotów + edytor zaznaczonego slotu (wartość, warunki, zależności)."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, cast

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import DataTable, Input, Static, Switch

from algopalette import color as col
from algopalette.constraints import slot_label
from algopalette.model import (
    OKLCH,
    Session,
    add_accent,
    move_slot,
    remove_slot,
    role_of,
    slot_index,
    with_slot,
)
from algopalette.tui.conditions import ConditionsEditor
from algopalette.tui.relations import RelationsEditor
from algopalette.tui.widgets import Field, ValueSlider, swatch

if TYPE_CHECKING:
    from algopalette.tui.app import AlgoPaletteApp

COLUMNS = ("", "#", "nazwa", "hex", "L", "C", "H", "🔒", "kontrast", "ΔE min")


def slot_rows(session: Session) -> list[tuple[str, tuple[object, ...]]]:
    """Wiersze tabeli slotów: (id, komórki)."""
    g = session.globals
    bg = session.slots[0].value
    rows = []
    accents = list(range(2, len(session.slots)))
    for i, s in enumerate(session.slots):
        v = s.value
        hx = col.to_hex(v, g.fit_method)
        contrast = "—" if i == 0 else f"{col.contrast(v, bg, g.contrast_metric):.2f}"
        de = "—"
        if i >= 2 and len(accents) > 1:
            dmin = min(col.delta_e(v, session.slots[j].value, g.delta_e) for j in accents if j != i)
            de = f"{dmin:.3f}"
        fit = col.fit_delta(v, g.fit_method)
        hex_cell = Text(hx + (" ⚠" if fit > 0 else ""), style="yellow" if fit > 0 else "")
        rows.append(
            (
                s.id,
                (
                    swatch(hx, 6),
                    str(i),
                    slot_label(session, i),
                    hex_cell,
                    f"{v.l:.3f}",
                    f"{v.c:.3f}",
                    f"{v.h:.1f}",
                    "🔒" if s.locked else "",
                    contrast,
                    de,
                ),
            )
        )
    return rows


class SlotTable(DataTable):
    BINDINGS = [
        Binding("a", "add_accent", "Dodaj akcent"),
        Binding("x,delete", "remove_slot", "Usuń akcent"),
        Binding("l", "toggle_lock", "Kłódka"),
        Binding("shift+up", "move(-1)", "Wyżej", show=False),
        Binding("shift+down", "move(1)", "Niżej", show=False),
    ]

    @property
    def pal_app(self) -> AlgoPaletteApp:
        return cast("AlgoPaletteApp", self.app)

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        for c in COLUMNS:
            self.add_column(c, key=c or "swatch")
        self.populate(self.pal_app.session)

    def populate(self, session: Session) -> None:
        """Ten sam zestaw slotów → aktualizacja komórek w miejscu (bez ruszania kursora)."""
        rows = slot_rows(session)
        ids = [sid for sid, _ in rows]
        existing = [str(k.value) for k in self.rows]
        if existing == ids:
            keys = [c.key for c in self.columns.values()]
            for sid, cells in rows:
                for key, cell in zip(keys, cells, strict=True):
                    self.update_cell(sid, key, cell)
            return
        current = self.selected_id()
        with self.prevent(DataTable.RowHighlighted):
            self.clear()
            for sid, cells in rows:
                self.add_row(*cells, key=sid)
            if current in ids:
                self.move_cursor(row=ids.index(current))

    def selected_id(self) -> str | None:
        if self.row_count == 0:
            return None
        try:
            key = self.coordinate_to_cell_key(self.cursor_coordinate).row_key
        except Exception:
            return None
        return str(key.value) if key.value is not None else None

    def _apply(self, fn, *args) -> None:
        try:
            new = fn(self.pal_app.session, *args)
        except ValueError as e:
            self.notify(str(e), severity="warning")
            return
        self.pal_app.set_session(new, structural=True)

    def action_add_accent(self) -> None:
        self._apply(add_accent)
        self.move_cursor(row=self.row_count - 1)

    def action_remove_slot(self) -> None:
        sid = self.selected_id()
        if sid is not None:
            self._apply(remove_slot, sid)

    def action_toggle_lock(self) -> None:
        sid = self.selected_id()
        if sid is None:
            return
        s = self.pal_app.session
        slot = s.slots[slot_index(s, sid)]
        self.pal_app.set_session(with_slot(s, replace(slot, locked=not slot.locked)))

    def action_move(self, delta: int) -> None:
        sid = self.selected_id()
        if sid is None:
            return
        i = slot_index(self.pal_app.session, sid)
        self._apply(move_slot, sid, i + delta)
        self.move_cursor(row=slot_index(self.pal_app.session, sid))


class SlotEditor(VerticalScroll):
    DEFAULT_CSS = """
    SlotEditor { width: 1fr; padding: 0 1; }
    SlotEditor .title { text-style: bold; margin-bottom: 1; }
    SlotEditor Input#name { width: 30; height: 1; border: none; padding: 0; }
    SlotEditor Switch { height: 1; border: none; padding: 0; width: 5; }
    SlotEditor .section { text-style: bold; margin-top: 1; color: $accent; }
    """

    def __init__(self, slot_id: str | None, **kw) -> None:
        super().__init__(**kw)
        self.slot_id = slot_id

    @property
    def pal_app(self) -> AlgoPaletteApp:
        return cast("AlgoPaletteApp", self.app)

    def compose(self) -> ComposeResult:
        s = self.pal_app.session
        if self.slot_id is None or self.slot_id not in {x.id for x in s.slots}:
            yield Static("Wybierz slot z listy.")
            return
        i = slot_index(s, self.slot_id)
        slot = s.slots[i]
        role = role_of(i)
        hx = col.to_hex(slot.value, s.globals.fit_method)
        yield Static(
            Text.assemble(swatch(hx, 8), f"  {slot_label(s, i)}  {hx}  ({role})"),
            classes="title",
            id="title",
        )
        yield Field("nazwa", Input(slot.name, id="name", placeholder="(bez nazwy)", compact=True))
        yield Field("kłódka", Switch(slot.locked, id="lock", animate=False))
        yield Static("Wartość (OKLCH) — edycja ręczna", classes="section")
        v = slot.value
        yield Field(
            "L", ValueSlider(v.l, minimum=0.0, maximum=1.0, step=0.01, fmt=".3f", id="val-l")
        )
        yield Field(
            "C", ValueSlider(v.c, minimum=0.0, maximum=0.37, step=0.005, fmt=".3f", id="val-c")
        )
        yield Field(
            "H",
            ValueSlider(
                v.h, minimum=0.0, maximum=360.0, step=1.0, fmt=".1f", wrap=True, id="val-h"
            ),
        )
        yield Static("Warunki", classes="section")
        yield ConditionsEditor("slot", self.slot_id, id="conditions")
        if i >= 0:
            yield RelationsEditor(self.slot_id, id="relations")

    def _slot(self):
        s = self.pal_app.session
        return s, s.slots[slot_index(s, self.slot_id or "")]

    def alive(self) -> bool:
        return self.slot_id in {x.id for x in self.pal_app.session.slots}

    @on(Input.Submitted, "#name")
    @on(Input.Blurred, "#name")
    def _name(self, event: Input.Submitted | Input.Blurred) -> None:
        event.stop()
        if not self.alive():
            return
        s, slot = self._slot()
        if event.input.value != slot.name:
            self.pal_app.set_session(with_slot(s, replace(slot, name=event.input.value.strip())))

    @on(Switch.Changed, "#lock")
    def _lock(self, event: Switch.Changed) -> None:
        event.stop()
        if not self.alive():
            return
        s, slot = self._slot()
        if slot.locked != event.value:
            self.pal_app.set_session(with_slot(s, replace(slot, locked=event.value)))

    @on(ValueSlider.Changed)
    def _value(self, event: ValueSlider.Changed) -> None:
        sid = event.slider.id or ""
        if not sid.startswith("val-") or event.value is None:
            return
        event.stop()
        if not self.alive():
            return
        s, slot = self._slot()
        v = slot.value
        x = float(event.value)
        new = {
            "val-l": OKLCH(x, v.c, v.h),
            "val-c": OKLCH(v.l, x, v.h),
            "val-h": OKLCH(v.l, v.c, x % 360),
        }[sid]
        self.pal_app.set_session(
            with_slot(s, replace(slot, value=new)), coalesce=f"value:{slot.id}:{sid}"
        )
        hx = col.to_hex(new, s.globals.fit_method)
        i = slot_index(s, slot.id)
        self.query_one("#title", Static).update(
            Text.assemble(
                swatch(hx, 8), f"  {slot_label(self.pal_app.session, i)}  {hx}  ({role_of(i)})"
            )
        )


class PaletteTab(Horizontal):
    DEFAULT_CSS = """
    PaletteTab { height: 1fr; }
    PaletteTab > Vertical#slots { width: 78; }
    PaletteTab SlotTable { height: 1fr; }
    """

    @property
    def pal_app(self) -> AlgoPaletteApp:
        return cast("AlgoPaletteApp", self.app)

    def compose(self) -> ComposeResult:
        with Vertical(id="slots"):
            yield SlotTable(id="slot-table")
            yield Static("a = dodaj · x = usuń · l = kłódka · Shift+↑/↓ = przesuń", classes="hint")
        first = self.pal_app.session.slots[0].id
        yield SlotEditor(first, id="slot-editor")

    def refresh_from_session(self, *, editor: bool) -> None:
        table = self.query_one(SlotTable)
        table.populate(self.pal_app.session)
        if editor:
            self._show(table.selected_id())

    def _show(self, sid: str | None) -> None:
        ed = self.query_one(SlotEditor)
        ed.slot_id = sid
        ed.refresh(recompose=True)

    @on(DataTable.RowHighlighted)
    def _row(self, event: DataTable.RowHighlighted) -> None:
        sid = str(event.row_key.value) if event.row_key is not None else None
        ed = self.query_one(SlotEditor)
        if sid != ed.slot_id:
            self._show(sid)
