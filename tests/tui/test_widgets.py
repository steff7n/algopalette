"""Suwaki (Task 8)."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input

from algopalette.tui.widgets import RangeSlider, ValueSlider, _Bar


class Harness(App[None]):
    def __init__(self, widget) -> None:
        super().__init__()
        self.widget = widget
        self.events: list = []

    def compose(self) -> ComposeResult:
        yield self.widget

    def on_value_slider_changed(self, e: ValueSlider.Changed) -> None:
        self.events.append(e.value)

    def on_range_slider_changed(self, e: RangeSlider.Changed) -> None:
        self.events.append((e.lo, e.hi))


async def test_hue_slider_wraps():
    s = ValueSlider(359.0, minimum=0.0, maximum=360.0, step=1.0, fmt=".0f", wrap=True)
    app = Harness(s)
    async with app.run_test(size=(60, 5)) as pilot:
        s.query_one(_Bar).focus()
        await pilot.press("right")
        await pilot.pause()
        assert s.value == pytest.approx(0.0)
        await pilot.press("left")
        await pilot.pause()
        assert s.value == pytest.approx(359.0)


async def test_value_slider_steps_and_input():
    s = ValueSlider(0.5, minimum=0.0, maximum=1.0, step=0.01, fmt=".3f")
    app = Harness(s)
    async with app.run_test(size=(60, 5)) as pilot:
        s.query_one(_Bar).focus()
        await pilot.press("shift+right", "ctrl+right", "end")
        await pilot.pause()
        assert s.value == pytest.approx(1.0)
        assert app.events[:2] == [pytest.approx(0.6), pytest.approx(0.601)]
        inp = s.query_one(Input)
        inp.focus()
        inp.value = "0,25"
        await pilot.press("enter")
        await pilot.pause()
        assert s.value == pytest.approx(0.25)
        inp.value = "abc"
        await pilot.press("enter")
        await pilot.pause()
        assert s.value == pytest.approx(0.25)
        assert inp.has_class("-bad")


async def test_range_slider_handles_and_none():
    s = RangeSlider(0.2, 0.8, minimum=0.0, maximum=1.0, step=0.1, fmt=".2f", allow_none=True)
    app = Harness(s)
    async with app.run_test(size=(60, 5)) as pilot:
        s.query_one(_Bar).focus()
        await pilot.press("right")
        await pilot.press("space", "left")
        await pilot.pause()
        assert (s.lo, s.hi) == (pytest.approx(0.3), pytest.approx(0.7))
        hi_input = list(s.query(Input))[1]
        hi_input.focus()
        hi_input.value = ""
        await pilot.press("enter")
        await pilot.pause()
        assert s.hi is None
        assert app.events[-1] == (pytest.approx(0.3), None)


async def test_range_slider_wrap_allows_lo_above_hi():
    s = RangeSlider(330.0, 20.0, minimum=0.0, maximum=360.0, step=1.0, fmt=".0f", wrap=True)
    app = Harness(s)
    async with app.run_test(size=(60, 5)) as pilot:
        s.query_one(_Bar).focus()
        await pilot.press("right")
        await pilot.pause()
        assert (s.lo, s.hi) == (pytest.approx(331.0), pytest.approx(20.0))


async def test_mouse_click_moves_nearest_handle():
    s = RangeSlider(0.0, 1.0, minimum=0.0, maximum=1.0, step=0.01, fmt=".2f")
    app = Harness(s)
    async with app.run_test(size=(60, 5)) as pilot:
        bar = s.query_one(_Bar)
        await pilot.click(bar, offset=(bar.size.width - 3, 0))
        await pilot.pause()
        assert s.lo == pytest.approx(0.0)
        assert s.hi is not None and 0.85 < s.hi < 1.0
