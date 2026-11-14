"""Widżety TUI: suwaki wartości i zakresu, próbki koloru, znacznik źródła wartości.

Suwak = pole liczby + pasek (klawiatura/mysz) [+ drugie pole]. Pasek: ←/→ krok, Shift = krok gruby
(×10), Ctrl = krok drobny (×0.1), Home/End = skraj, spacja = przełącz uchwyt (zakres). Mysz: klik i
przeciąganie przesuwa najbliższy uchwyt. Pola liczb: Enter lub wyjście z pola zatwierdza; puste pole
w zakresie = brak ograniczenia z tej strony (gdy ``allow_none``).
"""

from __future__ import annotations

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Static


def swatch(hex_: str, width: int = 4) -> Text:
    return Text(" " * width, style=f"on {hex_}")


SOURCE_LABELS = {"mood": "nastrój", "global": "globalne", "slot": "własne"}


def source_badge(src: str | None) -> Text:
    if src is None:
        return Text("")
    style = {"mood": "magenta", "global": "cyan", "slot": "bold yellow"}.get(src, "")
    return Text(f"[{SOURCE_LABELS.get(src, src)}]", style=style)


def _fmt(v: float | None, fmt: str) -> str:
    return "" if v is None else format(v, fmt)


class _Bar(Widget, can_focus=True):
    """Pasek suwaka; ``owner`` przechowuje wartości i reaguje na zmiany."""

    DEFAULT_CSS = """
    _Bar { width: 1fr; height: 1; min-width: 10; }
    _Bar:focus { background: $boost; }
    """
    BINDINGS = [
        Binding("left", "move(-1)", "−", show=False),
        Binding("right", "move(1)", "+", show=False),
        Binding("shift+left", "move(-10)", "−−", show=False),
        Binding("shift+right", "move(10)", "++", show=False),
        Binding("ctrl+left", "move(-0.1)", "−·", show=False),
        Binding("ctrl+right", "move(0.1)", "+·", show=False),
        Binding("home", "edge(0)", "min", show=False),
        Binding("end", "edge(1)", "max", show=False),
        Binding("space", "toggle_handle", "uchwyt", show=False),
    ]

    def __init__(self, owner: _SliderBase) -> None:
        super().__init__()
        self.owner = owner
        self._drag = False

    def render(self) -> Text:
        o = self.owner
        width = max(self.size.width, 10)
        span = o.maximum - o.minimum or 1.0

        def pos(v: float | None, default: float) -> int:
            x = default if v is None else v
            return round((x - o.minimum) / span * (width - 1))

        chars = ["─"] * width
        styles = ["dim"] * width
        values = o.handle_values()
        if len(values) == 2:
            a, b = pos(values[0], o.minimum), pos(values[1], o.maximum)
            fill = range(a, b + 1) if a <= b else [*range(a, width), *range(0, b + 1)]
            for i in fill:
                chars[i], styles[i] = "━", "bold"
        for k, v in enumerate(values):
            p = pos(v, o.minimum if k == 0 else o.maximum)
            chars[p] = "◆" if v is not None else "◇"
            styles[p] = "bold reverse" if (self.has_focus and k == o.active) else "bold"
        text = Text()
        for ch, st in zip(chars, styles, strict=True):
            text.append(ch, style=st)
        return text

    def action_move(self, mult: float) -> None:
        self.owner.nudge(mult)

    def action_edge(self, which: int) -> None:
        o = self.owner
        o.set_active(o.minimum if which == 0 else o.maximum)

    def action_toggle_handle(self) -> None:
        o = self.owner
        o.active = (o.active + 1) % len(o.handle_values())
        self.refresh()

    def _value_at(self, x: int) -> float:
        o = self.owner
        width = max(self.size.width, 10)
        frac = min(max(x / (width - 1), 0.0), 1.0)
        return o.snap(o.minimum + frac * (o.maximum - o.minimum))

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self.focus()
        self._drag = True
        self.capture_mouse()
        v = self._value_at(event.x)
        self.owner.pick_nearest(v)
        self.owner.set_active(v)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._drag:
            self.owner.set_active(self._value_at(event.x))

    def on_mouse_up(self, event: events.MouseUp) -> None:
        self._drag = False
        self.release_mouse()


class _SliderBase(Widget):
    DEFAULT_CSS = """
    _SliderBase { height: 1; width: 1fr; layout: horizontal; }
    _SliderBase Input { width: 9; height: 1; border: none; padding: 0; }
    _SliderBase Input.-invalid { background: $error 30%; }
    """

    def __init__(
        self,
        *,
        minimum: float,
        maximum: float,
        step: float,
        fmt: str = ".3f",
        wrap: bool = False,
        allow_none: bool = False,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.minimum, self.maximum, self.step = minimum, maximum, step
        self.fmt, self.wrap, self.allow_none = fmt, wrap, allow_none
        self.active = 0

    # --- do nadpisania ---
    def handle_values(self) -> list[float | None]:
        raise NotImplementedError

    def _store(self, k: int, v: float | None) -> None:
        raise NotImplementedError

    def _emit(self) -> None:
        raise NotImplementedError

    # --- wspólne ---
    def snap(self, v: float) -> float:
        if self.step > 0:
            v = round(v / self.step) * self.step
        return float(f"{v:.6g}") if v else 0.0

    def clamp(self, v: float) -> float:
        if self.wrap:
            span = self.maximum - self.minimum
            return self.minimum + (v - self.minimum) % span
        return min(max(v, self.minimum), self.maximum)

    def nudge(self, mult: float) -> None:
        cur = self.handle_values()[self.active]
        if cur is None:
            cur = self.minimum if self.active == 0 else self.maximum
        self.set_active(cur + self.step * mult)

    def set_active(self, v: float) -> None:
        v = float(f"{self.clamp(v):.6g}")
        self._store(self.active, v)
        self._sync_inputs()
        self.query_one(_Bar).refresh()
        self._emit()

    def pick_nearest(self, v: float) -> None:
        vals = self.handle_values()
        if len(vals) < 2:
            self.active = 0
            return
        d = [
            abs((x if x is not None else (self.minimum if i == 0 else self.maximum)) - v)
            for i, x in enumerate(vals)
        ]
        self.active = 0 if d[0] <= d[1] else 1

    def _sync_inputs(self) -> None:
        for k, inp in enumerate(self.query(Input).results(Input)):
            vals = self.handle_values()
            if k < len(vals) and not inp.has_focus:
                inp.value = _fmt(vals[k], self.fmt)
                inp.remove_class("-invalid")

    def _commit_input(self, inp: Input) -> None:
        k = int(inp.name or "0")
        raw = inp.value.strip().replace(",", ".")
        if raw == "" and self.allow_none:
            v: float | None = None
        else:
            try:
                v = self.clamp(float(raw))
            except ValueError:
                inp.add_class("-invalid")
                return
        inp.remove_class("-invalid")
        if self.handle_values()[k] == v:
            return
        self._store(k, v)
        self.query_one(_Bar).refresh()
        self._emit()

    @on(Input.Submitted)
    def _submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._commit_input(event.input)

    @on(Input.Blurred)
    def _blurred(self, event: Input.Blurred) -> None:
        self._commit_input(event.input)


class ValueSlider(_SliderBase):
    """Jedna wartość: pole + pasek."""

    class Changed(Message):
        def __init__(self, slider: ValueSlider, value: float | None) -> None:
            super().__init__()
            self.slider = slider
            self.value = value

        @property
        def control(self) -> ValueSlider:
            return self.slider

    def __init__(self, value: float | None, **kw) -> None:
        super().__init__(**kw)
        self.value = value

    def compose(self) -> ComposeResult:
        yield Input(_fmt(self.value, self.fmt), name="0", compact=True)
        yield _Bar(self)

    def handle_values(self) -> list[float | None]:
        return [self.value]

    def _store(self, k: int, v: float | None) -> None:
        self.value = v

    def _emit(self) -> None:
        self.post_message(self.Changed(self, self.value))


class RangeSlider(_SliderBase):
    """Zakres [lo, hi]: pole, pasek z dwoma uchwytami, pole. ``wrap``: lo > hi = zakres przez 0."""

    class Changed(Message):
        def __init__(self, slider: RangeSlider, lo: float | None, hi: float | None) -> None:
            super().__init__()
            self.slider = slider
            self.lo = lo
            self.hi = hi

        @property
        def control(self) -> RangeSlider:
            return self.slider

    def __init__(self, lo: float | None, hi: float | None, **kw) -> None:
        super().__init__(**kw)
        self.lo, self.hi = lo, hi

    def compose(self) -> ComposeResult:
        yield Input(_fmt(self.lo, self.fmt), name="0", compact=True)
        yield _Bar(self)
        yield Input(_fmt(self.hi, self.fmt), name="1", compact=True)

    def handle_values(self) -> list[float | None]:
        return [self.lo, self.hi]

    def _store(self, k: int, v: float | None) -> None:
        if k == 0:
            self.lo = v
            if not self.wrap and v is not None and self.hi is not None and v > self.hi:
                self.hi = v
        else:
            self.hi = v
            if not self.wrap and v is not None and self.lo is not None and v < self.lo:
                self.lo = v

    def _emit(self) -> None:
        self.post_message(self.Changed(self, self.lo, self.hi))


class Field(Horizontal):
    """Wiersz: etykieta + zawartość."""

    DEFAULT_CSS = """
    Field { height: auto; }
    Field > .field-label { width: 12; color: $text-muted; }
    """

    def __init__(self, label: str, *children: Widget, **kw) -> None:
        super().__init__(Static(label, classes="field-label"), *children, **kw)
