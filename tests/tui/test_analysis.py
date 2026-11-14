"""Zakładka Analiza (Task 10)."""

from dataclasses import replace

import pytest
from textual.widgets import Select, Static

from algopalette.__main__ import fresh_session
from algopalette.model import OKLCH, add_accent, remove_slot, with_slot
from algopalette.tui.analysis_tab import (
    AnalysisTab,
    de_matrix,
    hue_wheel,
    lc_plot,
    samples,
    wheel_cell,
)
from algopalette.tui.app import AlgoPaletteApp


@pytest.fixture(autouse=True)
def _xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))


def accents(n: int):
    s = fresh_session()
    while len(s.slots) - 2 > n:
        s = remove_slot(s, s.slots[-1].id)
    while len(s.slots) - 2 < n:
        s = add_accent(s)
    return s


def test_hue_point_position():
    # 0° po prawej, 90° u góry (przeciwnie do wskazówek zegara)
    w, h = 41, 21
    cx, cy = wheel_cell(0, 0.0, w, h)
    x90, y90 = wheel_cell(90, 1.0, w, h)
    x0, y0 = wheel_cell(0, 1.0, w, h)
    assert y90 < cy and x90 == cx
    assert x0 > cx and y0 == cy


def test_matrix_highlights_violation():
    s = accents(3)
    same = OKLCH(0.7, 0.1, 100)
    s = with_slot(s, replace(s.slots[2], value=same))
    s = with_slot(s, replace(s.slots[3], value=same))
    _, bad = de_matrix(s)
    assert (2, 3) in bad


def test_cvd_toggle_changes_matrix():
    s = accents(2)
    s = with_slot(s, replace(s.slots[2], value=OKLCH(0.6, 0.12, 30)))
    s = with_slot(s, replace(s.slots[3], value=OKLCH(0.6, 0.12, 140)))
    normal, _ = de_matrix(s, "normal")
    deutan, _ = de_matrix(s, "deutan")
    assert normal.plain != deutan.plain


@pytest.mark.parametrize("n", [1, 14])
def test_render_functions_any_size(n):
    s = accents(n)
    for w, h in ((21, 11), (61, 31)):
        assert hue_wheel(s, w, h, selected=s.slots[2].id).plain.count("\n") == h
        assert lc_plot(s, w, h).plain
    assert de_matrix(s)[0].plain
    assert samples(s).plain


@pytest.mark.parametrize("size", [(80, 24), (200, 60)])
@pytest.mark.parametrize("n", [1, 14])
async def test_renders_sizes(size, n):
    app = AlgoPaletteApp(accents(n), autosave=False)
    async with app.run_test(size=size) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        tab = app.query_one(AnalysisTab)
        assert str(tab.query_one("#matrix", Static).render())


async def test_view_select_redraws():
    app = AlgoPaletteApp(accents(3), autosave=False)
    async with app.run_test(size=(150, 50)) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        tab = app.query_one(AnalysisTab)
        before = str(tab.query_one("#samples", Static).render())
        tab.query_one("#view", Select).value = "tritan"
        await pilot.pause()
        assert tab.view == "tritan"
        assert (
            str(tab.query_one("#samples", Static).render()) == before
        )  # tekst ten sam, kolory inne


def test_cvd_view_without_enabled_type_flags_nothing():
    s = accents(3)
    same = OKLCH(0.7, 0.1, 100)
    s = with_slot(s, replace(s.slots[2], value=same))
    s = with_slot(s, replace(s.slots[3], value=same))
    _, bad = de_matrix(s, "deutan")  # deutan nie jest włączony w ustawieniach
    assert bad == set()  # przegląd M4


def test_contrast_matrix_renders():
    from algopalette.tui.analysis_tab import contrast_matrix

    assert "—" in contrast_matrix(accents(3)).plain
