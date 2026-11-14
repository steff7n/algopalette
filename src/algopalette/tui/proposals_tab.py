"""Zakładka „Propozycje”: generowanie w tle, przegląd, przejmowanie palety lub jednego koloru."""

from __future__ import annotations

from collections.abc import Collection
from typing import TYPE_CHECKING, cast

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, ProgressBar, Static

from algopalette import color as col
from algopalette.constraints import slot_label
from algopalette.engine import Proposal, apply_proposal, generate
from algopalette.model import Session
from algopalette.tui.widgets import swatch

if TYPE_CHECKING:
    from algopalette.tui.app import AlgoPaletteApp


def strip(p: Proposal, ids: list[str], width: int = 3) -> Text:
    t = Text()
    for sid in ids:
        if sid in p.hexes:
            t.append_text(swatch(p.hexes[sid], width))
    return t


def _tab(widget: DataTable) -> ProposalsTab:
    return next(a for a in widget.ancestors if isinstance(a, ProposalsTab))


class ProposalTable(DataTable):
    BINDINGS = [Binding("enter,t", "take_whole", "Przejmij całą")]

    def action_take_whole(self) -> None:
        _tab(self).take_whole()


class DetailTable(DataTable):
    BINDINGS = [Binding("enter,c", "take_color", "Przejmij kolor")]

    def action_take_color(self) -> None:
        _tab(self).take_color()


class ProposalsTab(Vertical):
    DEFAULT_CSS = """
    ProposalsTab { padding: 0 1; }
    ProposalsTab #controls { height: 1; }
    ProposalsTab ProgressBar { width: 40; }
    ProposalsTab #status { height: 1; }
    ProposalsTab #lists { height: 1fr; }
    ProposalsTab ProposalTable { width: 1fr; height: 1fr; }
    ProposalsTab Vertical#detail { width: 1fr; }
    ProposalsTab DetailTable { height: 1fr; }
    ProposalsTab #detail-violations { height: auto; max-height: 8; }
    """

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.proposals: list[Proposal] = []
        self.base: Session | None = None  # sesja, z której wygenerowano propozycje
        self._cancel = False
        self.running = False

    @property
    def pal_app(self) -> AlgoPaletteApp:
        return cast("AlgoPaletteApp", self.app)

    def compose(self) -> ComposeResult:
        with Horizontal(id="controls"):
            yield Button(
                "Generuj wszystkie wolne (g)", id="gen-all", variant="primary", compact=True
            )
            yield Button("Generuj tylko wybrany slot", id="gen-one", compact=True)
            yield Button("Przerwij", id="cancel", disabled=True, compact=True)
            yield ProgressBar(total=1.0, show_eta=False, id="progress")
        yield Static("Brak propozycji — naciśnij g.", id="status")
        with Horizontal(id="lists"):
            yield ProposalTable(id="prop-table", cursor_type="row", zebra_stripes=True)
            with Vertical(id="detail"):
                yield DetailTable(id="detail-table", cursor_type="row", zebra_stripes=True)
                yield Static("", id="detail-violations")
        yield Static(
            "Enter/t na propozycji = przejmij całą · Enter/c na kolorze = przejmij do slotu"
            " · Ctrl+Z cofa",
            classes="hint",
        )

    def on_mount(self) -> None:
        pt = self.query_one(ProposalTable)
        for c in ("#", "stan", "wynik", "naruszenia", "paleta"):
            pt.add_column(c, key=c)
        dt = self.query_one(DetailTable)
        for c in ("slot", "teraz", "propozycja", "hex", "Δ fit"):
            dt.add_column(c, key=c)

    # --- generowanie ---
    def start(self, slot_ids: Collection[str] | None = None) -> None:
        if self.running:
            self.notify("Generowanie już trwa.", severity="warning")
            return
        self.running = True
        self._cancel = False
        self.base = self.pal_app.session
        self.query_one("#cancel", Button).disabled = False
        self.query_one(ProgressBar).update(progress=0.0)
        self.query_one("#status", Static).update("Generowanie…")
        self._run(self.base, None if slot_ids is None else set(slot_ids))

    @work(thread=True, exclusive=True, group="generate")
    def _run(self, session: Session, slot_ids: set[str] | None) -> None:
        def progress(x: float) -> None:
            self.app.call_from_thread(self.query_one(ProgressBar).update, progress=x)

        try:
            result = generate(
                session, slot_ids=slot_ids, progress=progress, cancel=lambda: self._cancel
            )
        except Exception as e:
            self.app.call_from_thread(self._failed, str(e))
            return
        self.app.call_from_thread(self._done, result)

    def _failed(self, msg: str) -> None:
        self.running = False
        self.query_one("#cancel", Button).disabled = True
        self.query_one("#status", Static).update(Text(f"Błąd silnika: {msg}", style="red"))

    def _done(self, result: list[Proposal]) -> None:
        self.running = False
        self.query_one("#cancel", Button).disabled = True
        self.proposals = result
        ok = sum(p.ok for p in result)
        cancelled = " (przerwano)" if self._cancel else ""
        seed = self.base.globals.optimizer.seed if self.base else "?"
        self.query_one("#status", Static).update(
            f"{len(result)} propozycji, {ok} bez twardych naruszeń{cancelled}. Ziarno {seed}."
        )
        self._fill()

    def cancel(self) -> None:
        self._cancel = True

    def _fill(self) -> None:
        pt = self.query_one(ProposalTable)
        pt.clear()
        ids = [s.id for s in (self.base.slots if self.base else ())]
        for i, p in enumerate(self.proposals):
            hard = sum(v.hard for v in p.violations)
            soft = len(p.violations) - hard
            if p.timed_out:
                state = Text("⏱ niepowtarzalna", style="yellow")
            elif hard:
                state = Text("✗ łamie twarde", style="bold red")
            else:
                state = Text("✓", style="green")
            pt.add_row(
                str(i + 1),
                state,
                f"{p.score:.3g}",
                f"{hard} tw. / {soft} mi.",
                strip(p, ids),
                key=str(i),
            )
        if self.proposals:
            pt.move_cursor(row=0)
            self._detail(0)
            pt.focus()

    def _current(self) -> int | None:
        pt = self.query_one(ProposalTable)
        if not self.proposals or pt.row_count == 0:
            return None
        return pt.cursor_row

    def _detail(self, i: int) -> None:
        dt = self.query_one(DetailTable)
        dt.clear()
        if self.base is None or not 0 <= i < len(self.proposals):
            return
        p = self.proposals[i]
        cur = self.pal_app.session
        cur_ids = {s.id: s for s in cur.slots}
        for k, s in enumerate(self.base.slots):
            now = cur_ids.get(s.id)
            now_cell = (
                swatch(col.to_hex(now.value, cur.globals.fit_method), 6) if now else Text("—")
            )
            fit = p.fit_deltas.get(s.id, 0.0)
            dt.add_row(
                slot_label(self.base, k),
                now_cell,
                swatch(p.hexes[s.id], 6),
                p.hexes[s.id],
                f"{fit:.3f}" if fit > 0 else "",
                key=s.id,
            )
        v = self.query_one("#detail-violations", Static)
        if not p.violations:
            v.update(Text("✓ propozycja spełnia wszystkie warunki", style="green"))
        else:
            t = Text()
            for x in p.violations[:12]:
                t.append("✗ " if x.hard else "~ ", style="red" if x.hard else "yellow")
                t.append(f"{x.label}: wymagane {x.required}, jest {x.achieved}\n")
            v.update(t)

    @on(DataTable.RowHighlighted, "#prop-table")
    def _highlight(self, event: DataTable.RowHighlighted) -> None:
        self._detail(event.cursor_row)

    # --- przejmowanie ---
    def take_whole(self) -> None:
        i = self._current()
        if i is None:
            return
        self.pal_app.replace_session(apply_proposal(self.pal_app.session, self.proposals[i]))
        self.notify(f"Przejęto propozycję {i + 1} (kłódki bez zmian).")
        self._detail(i)

    def take_color(self) -> None:
        i = self._current()
        dt = self.query_one(DetailTable)
        if i is None or dt.row_count == 0:
            return
        sid = str(dt.coordinate_to_cell_key(dt.cursor_coordinate).row_key.value)
        if sid not in {s.id for s in self.pal_app.session.slots}:
            self.notify("Tego slotu już nie ma w palecie.", severity="warning")
            return
        locked = next(s.locked for s in self.pal_app.session.slots if s.id == sid)
        if locked:
            self.notify("Slot ma kłódkę — zdejmij ją, żeby przejąć kolor.", severity="warning")
            return
        self.pal_app.replace_session(
            apply_proposal(self.pal_app.session, self.proposals[i], slot_ids={sid})
        )
        self.notify("Przejęto kolor do slotu.")
        self._detail(i)

    @on(Button.Pressed)
    def _button(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "gen-all":
            self.start()
        elif event.button.id == "gen-one":
            sid = self.pal_app.selected_slot_id()
            if sid is None:
                self.notify("Najpierw wybierz slot na zakładce Paleta.", severity="warning")
                return
            self.start({sid})
        elif event.button.id == "cancel":
            self.cancel()
