"""Zakładka „Analiza”: koło odcieni, wykres L–C, macierz ΔE / kontrastu (także przy daltonizmie),
próbki „Aa” na tle. Zamiast podglądu kodu (decyzja użytkownika: program do palet, nie IDE).

Orientacja koła odcieni: 0° po prawej, kąty rosną przeciwnie do ruchu wskazówek zegara (90° u góry).
Odległość od środka = nasycenie względne (C / maxC w sRGB). Funkcje rysujące są czyste.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal, cast

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Select, Static

from algopalette import color as col
from algopalette.constraints import slot_label
from algopalette.model import OKLCH, Session, effective_conditions

if TYPE_CHECKING:
    from algopalette.tui.app import AlgoPaletteApp

View = Literal["normal", "protan", "deutan", "tritan"]


def _hex(session: Session, c: OKLCH) -> str:
    return col.to_hex(c, session.globals.fit_method)


def view_value(session: Session, c: OKLCH, view: View) -> OKLCH:
    if view == "normal":
        return c
    cvd = session.globals.cvd
    return col.simulate_cvd(c, view, cvd.method, cvd.severity)


def rel_chroma(c: OKLCH) -> float:
    m = col.max_chroma(c.l, c.h)
    return min(c.c / m, 1.0) if m > 1e-9 else 0.0


def wheel_cell(h: float, r: float, width: int, height: int) -> tuple[int, int]:
    """(kolumna, wiersz) punktu o odcieniu h i promieniu r ∈ [0, 1]."""
    cx, cy = (width - 1) / 2, (height - 1) / 2
    rx, ry = cx, cy
    a = math.radians(h)
    return round(cx + r * rx * math.cos(a)), round(cy - r * ry * math.sin(a))


def hue_wheel(
    session: Session,
    width: int = 41,
    height: int = 21,
    selected: str | None = None,
    view: View = "normal",
) -> Text:
    grid: list[list[tuple[str, str]]] = [[(" ", "")] * width for _ in range(height)]
    for deg in range(0, 360, 3):  # obwód
        x, y = wheel_cell(deg, 1.0, width, height)
        grid[y][x] = ("·", "dim")
    if selected is not None and selected in {s.id for s in session.slots}:
        eff, _ = effective_conditions(session, selected)
        arcs: list[tuple[float, float]] = []
        if eff.hue_range is not None and eff.hue_range.enabled:
            hr = eff.hue_range.value
            arcs.append((hr.lo, hr.hi))
        if eff.hue_target is not None and eff.hue_target.enabled:
            ht = eff.hue_target.value
            arcs.append((ht.target - ht.tol, ht.target + ht.tol))
        for lo, hi in arcs:
            width_deg = (hi - lo) % 360 or 360
            for k in range(int(width_deg) + 1):
                x, y = wheel_cell(lo + k, 1.0, width, height)
                grid[y][x] = ("━", "bold yellow")
    cx, cy = wheel_cell(0, 0.0, width, height)
    grid[cy][cx] = ("+", "dim")
    for i, s in enumerate(session.slots):
        if i < 2 and s.value.c < 0.02:
            continue
        v = view_value(session, s.value, view)
        x, y = wheel_cell(v.h, rel_chroma(v), width, height)
        mark = "◉" if s.id == selected else "●"
        grid[y][x] = (mark, f"bold {_hex(session, v)}")
    t = Text()
    for row in grid:
        for ch, st in row:
            t.append(ch, style=st)
        t.append("\n")
    return t


def lc_plot(
    session: Session, width: int = 41, height: int = 21, mode: str = "rel", view: View = "normal"
) -> Text:
    """Oś pionowa: L (góra = 1). Oś pozioma: C względne (0–1) albo bezwzględne (0–0.37)."""
    grid: list[list[tuple[str, str]]] = [[(" ", "")] * width for _ in range(height)]
    for y in range(height):
        grid[y][0] = ("│", "dim")
    for x in range(width):
        grid[height - 1][x] = ("─", "dim")
    for i, s in enumerate(session.slots):
        v = view_value(session, s.value, view)
        c = rel_chroma(v) if mode == "rel" else min(v.c / 0.37, 1.0)
        x = min(max(1 + round(c * (width - 2)), 1), width - 1)
        y = min(max(round((1.0 - min(max(v.l, 0.0), 1.0)) * (height - 2)), 0), height - 2)
        label = str(i)
        grid[y][min(x, width - 1)] = ("●", f"bold {_hex(session, v)}")
        if x + 1 < width:
            grid[y][x + 1] = (label[-1], "dim")
    t = Text()
    for row in grid:
        for ch, st in row:
            t.append(ch, style=st)
        t.append("\n")
    t.append(f"L↑  C{' względne' if mode == 'rel' else ' bezwzgl.'}→", style="dim")
    return t


def pair_requirement(session: Session, i: int, j: int, view: View) -> float | None:
    if view != "normal" and view not in session.globals.cvd.types:
        return None  # ten typ daltonizmu nie jest włączony — warunek nie działa (przegląd M4)
    field = "min_distance" if view == "normal" else "cvd_min_distance"
    reqs = []
    for k in (i, j):
        eff, _ = effective_conditions(session, session.slots[k].id)
        c = getattr(eff, field)
        if c is not None and c.enabled:
            reqs.append(float(c.value))
    return max(reqs) if reqs else None


def de_matrix(session: Session, view: View = "normal") -> tuple[Text, set[tuple[int, int]]]:
    """Macierz ΔE akcentów (metoda globalna; po symulacji dla widoku CVD) + kontrast z tłem.
    Zwraca też pary (i, j) łamiące wymaganą odległość."""
    g = session.globals
    acc = list(range(2, len(session.slots)))
    vals = {i: view_value(session, session.slots[i].value, view) for i in acc}
    bg = view_value(session, session.slots[0].value, view)
    bad: set[tuple[int, int]] = set()
    t = Text()
    t.append(f"{'':>12}", style="bold")
    for j in acc:
        t.append(f"{j:>7}", style="bold")
    t.append(f"  │ kontrast ({g.contrast_metric})\n", style="bold")
    for i in acc:
        t.append(f"{slot_label(session, i)[:10]:>10} ", style="bold")
        t.append(" ", style=f"on {_hex(session, vals[i])}")
        for j in acc:
            if i == j:
                t.append(f"{'—':>7}", style="dim")
                continue
            d = col.delta_e(vals[i], vals[j], g.delta_e)
            req = pair_requirement(session, i, j, view)
            style = ""
            if req is not None and d < req:
                bad.add((min(i, j), max(i, j)))
                style = "bold white on red"
            t.append(f"{d:>7.3f}" if g.delta_e in ("ok", "hyab") else f"{d:>7.1f}", style=style)
        t.append(f"  │ {col.contrast(vals[i], bg, g.contrast_metric):.2f}\n")
    return t, bad


def contrast_matrix(session: Session, view: View = "normal") -> Text:
    """Kontrast każdej pary akcentów (wiersz = tekst, kolumna = tło), metryka globalna."""
    g = session.globals
    acc = list(range(2, len(session.slots)))
    vals = {i: view_value(session, session.slots[i].value, view) for i in acc}
    t = Text()
    t.append(f"{'tekst \\ tło':>12}", style="bold")
    for j in acc:
        t.append(f"{j:>7}", style="bold")
    t.append("\n")
    for i in acc:
        t.append(f"{slot_label(session, i)[:10]:>10} ", style="bold")
        t.append(" ", style=f"on {_hex(session, vals[i])}")
        for j in acc:
            if i == j:
                t.append(f"{'—':>7}", style="dim")
            else:
                t.append(f"{col.contrast(vals[i], vals[j], g.contrast_metric):>7.2f}")
        t.append("\n")
    return t


def samples(session: Session, view: View = "normal") -> Text:
    bg = _hex(session, view_value(session, session.slots[0].value, view))
    t = Text()
    for i, s in enumerate(session.slots[1:], start=1):
        hx = _hex(session, view_value(session, s.value, view))
        t.append(f" Aa {slot_label(session, i)} ", style=f"bold {hx} on {bg}")
        t.append("██", style=hx)
        t.append("  ")
        if i % 4 == 0:
            t.append("\n")
    return t


class AnalysisTab(VerticalScroll):
    DEFAULT_CSS = """
    AnalysisTab { padding: 0 1; }
    AnalysisTab Horizontal { height: auto; }
    AnalysisTab Select { width: 30; margin-right: 2; }
    AnalysisTab .plot { width: auto; margin-right: 4; }
    AnalysisTab .section { text-style: bold; color: $accent; margin-top: 1; }
    """

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.view: View = "normal"
        self.mode = "rel"
        self.matrix = "de"

    @property
    def pal_app(self) -> AlgoPaletteApp:
        return cast("AlgoPaletteApp", self.app)

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Select(
                [
                    ("widok: normalny", "normal"),
                    ("protanopia", "protan"),
                    ("deuteranopia", "deutan"),
                    ("tritanopia", "tritan"),
                ],
                value=self.view,
                allow_blank=False,
                id="view",
                compact=True,
            )
            yield Select(
                [("macierz: ΔE", "de"), ("macierz: kontrast par", "contrast")],
                value=self.matrix,
                allow_blank=False,
                id="matrix-kind",
                compact=True,
            )
            yield Select(
                [("C względne", "rel"), ("C bezwzględne", "abs")],
                value=self.mode,
                allow_blank=False,
                id="axis",
                compact=True,
            )
        with Horizontal():
            yield Static(id="wheel", classes="plot")
            yield Static(id="lc", classes="plot")
        yield Static(
            "Macierz akcentów (ΔE: czerwone = poniżej wymaganej; kontrast: wiersz na tle kolumny)",
            classes="section",
        )
        yield Static(id="matrix")
        yield Static("Próbki na tle", classes="section")
        yield Static(id="samples")

    def on_mount(self) -> None:
        self.redraw()

    def refresh_from_session(self) -> None:
        self.redraw()

    def redraw(self) -> None:
        s = self.pal_app.session
        try:
            sel = self.pal_app.selected_slot_id()
        except Exception:
            sel = None
        self.query_one("#wheel", Static).update(hue_wheel(s, selected=sel, view=self.view))
        self.query_one("#lc", Static).update(lc_plot(s, mode=self.mode, view=self.view))
        if self.matrix == "contrast":
            self.query_one("#matrix", Static).update(contrast_matrix(s, self.view))
        else:
            self.query_one("#matrix", Static).update(de_matrix(s, self.view)[0])
        self.query_one("#samples", Static).update(samples(s, self.view))

    @on(Select.Changed)
    def _select(self, event: Select.Changed) -> None:
        event.stop()
        if event.select.id == "view" and event.value is not Select.NULL:
            self.view = cast(View, event.value)
        elif event.select.id == "axis" and event.value is not Select.NULL:
            self.mode = str(event.value)
        elif event.select.id == "matrix-kind" and event.value is not Select.NULL:
            self.matrix = str(event.value)
        self.redraw()
