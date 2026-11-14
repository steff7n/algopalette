"""TUI — szkielet, zakładka Paleta, panel naruszeń, historia, autozapis (Task 8)."""

from dataclasses import replace
from pathlib import Path

import pytest
from textual.widgets import Button, DataTable

from algopalette import io as aio
from algopalette.__main__ import fresh_session, startup_session
from algopalette.model import (
    OKLCH,
    Cond,
    ContrastBound,
    Relation,
    SlotConditions,
    with_slot,
)
from algopalette.tui.app import AlgoPaletteApp, ViolationsPanel
from algopalette.tui.conditions import ConditionRow
from algopalette.tui.dialogs import HelpScreen
from algopalette.tui.palette_tab import SlotEditor, SlotTable
from algopalette.tui.relations import RelationRow
from algopalette.tui.widgets import _Bar


@pytest.fixture(autouse=True)
def _xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))


def app_for(session=None, **kw) -> AlgoPaletteApp:
    return AlgoPaletteApp(session or fresh_session(), autosave=kw.pop("autosave", False), **kw)


async def select_row(pilot, app, row: int) -> None:
    table = app.query_one(SlotTable)
    table.focus()
    table.move_cursor(row=row)
    await pilot.pause()


@pytest.mark.parametrize("size", [(120, 40), (80, 24)])
async def test_starts_with_default(size):
    app = app_for()
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        assert app.query_one(SlotTable).row_count == 10
        assert app.session.mood == "neutralny"


def test_open_file_arg(tmp_path):
    s = fresh_session()
    p = tmp_path / "s.json"
    aio.save_session(s, p)
    got, notice, path = startup_session(p, fresh=False)
    assert got == s and notice is None and path == p


def test_missing_file_arg(tmp_path):
    got, notice, path = startup_session(tmp_path / "brak.json", fresh=False)
    assert notice and "Nie ma pliku" in notice and path is None
    assert len(got.slots) == 10


def test_corrupt_autosave_falls_back():
    p = aio.autosave_path()
    p.parent.mkdir(parents=True)
    p.write_text("{zepsute", encoding="utf-8")
    got, notice, _ = startup_session(None, fresh=False)
    assert notice and "Autozapis" in notice
    assert got.mood == "neutralny"
    _, notice2, _ = startup_session(None, fresh=True)
    assert notice2 is None


def test_autosave_restored():
    s = replace(fresh_session(), mood=None, mood_snapshot=None)
    p = aio.autosave_path()
    aio.save_session(s, p)
    got, notice, _ = startup_session(None, fresh=False)
    assert got == s and notice is None


async def test_editor_follows_selection():
    app = app_for()
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        await pilot.press("down", "down")
        await pilot.pause()
        assert app.query_one(SlotEditor).slot_id == app.session.slots[2].id


async def test_slider_keyboard_changes_lightness_and_undo():
    app = app_for()
    async with app.run_test(size=(140, 45)) as pilot:
        await select_row(pilot, app, 2)
        sid = app.session.slots[2].id
        before = app.session.slots[2].value
        bar = app.query_one("#val-l").query_one(_Bar)
        bar.focus()
        await pilot.press("right", "right", "shift+right")
        await pilot.pause()
        after = app.session.slots[2].value
        assert after.l == pytest.approx(before.l + 0.12, abs=1e-6)
        assert app.session.slots[2].id == sid
        await pilot.press("ctrl+z")
        await pilot.pause()
        assert app.session.slots[2].value == before  # seria zmian = jeden krok cofania
        await pilot.press("ctrl+y")
        await pilot.pause()
        assert app.session.slots[2].value.l == pytest.approx(after.l)


async def test_add_remove_accent_limits():
    app = app_for()
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        table = app.query_one(SlotTable)
        table.focus()
        for _ in range(7):
            await pilot.press("a")
        await pilot.pause()
        assert len(app.session.slots) == 16  # limit 14 akcentów
        assert table.row_count == 16
        for _ in range(20):
            table.move_cursor(row=table.row_count - 1)
            await pilot.press("x")
        await pilot.pause()
        assert len(app.session.slots) == 3  # co najmniej 1 akcent


async def test_violation_panel_updates():
    app = app_for()
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        s = app.session
        fg = s.slots[1]
        bad = with_slot(
            s,
            replace(
                fg,
                value=OKLCH(0.25, 0.0, 0.0),
                conditions=SlotConditions(contrast_bg=Cond(ContrastBound(None, 7.0, None))),
            ),
        )
        app.set_session(bad)
        await pilot.pause()
        table = app.query_one(ViolationsPanel).query_one("#viol-table", DataTable)
        labels = [str(table.get_row_at(i)[1]) for i in range(table.row_count)]
        assert "kontrast z tłem" in labels


async def test_reset_to_inherited():
    app = app_for()
    async with app.run_test(size=(140, 60)) as pilot:
        await select_row(pilot, app, 2)
        row = app.query_one("#cond-lightness", ConditionRow)
        assert row.src == "mood"
        bar = row.query_one(_Bar)
        bar.focus()
        await pilot.press("right")
        await pilot.pause()
        row = app.query_one("#cond-lightness", ConditionRow)
        assert row.src == "slot"
        assert app.session.slots[2].conditions.lightness is not None
        app.query_one("#cond-lightness #reset", Button).press()
        await pilot.pause()
        row = app.query_one("#cond-lightness", ConditionRow)
        assert row.src == "mood"
        assert app.session.slots[2].conditions.lightness is None


async def test_add_missing_condition():
    app = app_for()
    async with app.run_test(size=(140, 60)) as pilot:
        await select_row(pilot, app, 2)
        app.query_one("#cond-hue_range #add", Button).press()
        await pilot.pause()
        assert app.session.slots[2].conditions.hue_range is not None


async def test_broken_relation_marked():
    s = fresh_session()
    a = replace(s.slots[2], relations=(Relation("hue", "nieistnieje", "eq", 180.0, tol=10.0),))
    s = with_slot(s, a)
    app = app_for(s)
    async with app.run_test(size=(140, 60)) as pilot:
        await select_row(pilot, app, 2)
        rows = list(app.query(RelationRow))
        assert len(rows) == 1 and rows[0].has_class("-broken")


async def test_add_relation_button():
    app = app_for()
    async with app.run_test(size=(140, 80)) as pilot:
        await select_row(pilot, app, 3)
        app.query_one("#add-rel", Button).press()
        await pilot.pause()
        assert len(app.session.slots[3].relations) == 1
        assert len(list(app.query(RelationRow))) == 1


async def test_help_screen():
    app = app_for()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f1")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, HelpScreen)


async def test_lock_toggle_key():
    app = app_for()
    async with app.run_test(size=(140, 45)) as pilot:
        await select_row(pilot, app, 4)
        await pilot.press("l")
        await pilot.pause()
        assert app.session.slots[4].locked


async def test_autosave_written():
    app = app_for(autosave=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await select_row(pilot, app, 3)
        await pilot.press("l")
        await pilot.pause(0.8)
    p: Path = aio.autosave_path()
    assert p.exists()
    assert aio.load_session(p).slots[3].locked


async def test_save_and_open(tmp_path):
    app = app_for()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        path = tmp_path / "x.json"
        app.save_to(path)
        await pilot.pause()
        assert path.exists()
        app.save_to(path)  # istnieje → pytanie o nadpisanie
        await pilot.pause()
        assert type(app.screen).__name__ == "ConfirmScreen"
        await pilot.click("#yes")
        await pilot.pause()
        app.open_path(path)
        await pilot.pause()
        assert app.file_path == path


def test_failed_file_arg_keeps_previous_autosave(tmp_path):
    prev = replace(fresh_session(), mood=None, mood_snapshot=None)
    aio.save_session(prev, aio.autosave_path())
    _, notice, _ = startup_session(tmp_path / "literowka.jsn", fresh=False)
    kept = aio.autosave_path().with_name("last.prev.json")
    assert notice and "last.prev.json" in notice
    assert not aio.autosave_path().exists() and aio.load_session(kept) == prev


def test_corrupt_autosave_is_kept_aside():
    p = aio.autosave_path()
    p.parent.mkdir(parents=True)
    p.write_text("{zepsute", encoding="utf-8")
    _, notice, _ = startup_session(None, fresh=False)
    assert notice and "corrupt" in notice
    assert list(p.parent.glob("last.corrupt-*.json"))


async def test_quit_flushes_pending_autosave():
    app = app_for(autosave=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await select_row(pilot, app, 3)
        await pilot.press("l")
        await pilot.press("ctrl+q")  # natychmiast, przed upływem 0.5 s
        await pilot.pause()
    assert aio.load_session(aio.autosave_path()).slots[3].locked
