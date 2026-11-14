"""TUI — Globalne, nastroje, Propozycje, Źródło, zapis, eksport (Task 9)."""

import json
from dataclasses import replace

import pytest
from textual.widgets import Button, Checkbox, DataTable, Input, Select, TextArea

from algopalette import io as aio
from algopalette.__main__ import fresh_session
from algopalette.color import to_hex
from algopalette.model import OKLCH
from algopalette.pb_export import pb_json
from algopalette.tui.app import AlgoPaletteApp
from algopalette.tui.globals_tab import GlobalsTab
from algopalette.tui.proposals_tab import ProposalsTab


@pytest.fixture(autouse=True)
def _xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))


def small(n: int = 2):
    s = fresh_session()
    return replace(
        s, globals=replace(s.globals, optimizer=replace(s.globals.optimizer, n_proposals=n))
    )


def make_app(session=None) -> AlgoPaletteApp:
    return AlgoPaletteApp(session or small(), autosave=False)


async def wait_generation(app, pilot) -> ProposalsTab:
    await app.workers.wait_for_complete()
    await pilot.pause()
    return app.query_one(ProposalsTab)


async def test_generate_fills_proposals():
    app = make_app()
    async with app.run_test(size=(150, 45)) as pilot:
        await pilot.press("g")
        tab = await wait_generation(app, pilot)
        assert len(tab.proposals) == 2
        assert app.query_one("#prop-table", DataTable).row_count == 2
        assert app.query_one("#detail-table", DataTable).row_count == len(app.session.slots)


async def test_cancel_generation():
    app = make_app(small(6))
    async with app.run_test(size=(150, 45)) as pilot:
        tab = app.query_one(ProposalsTab)
        tab._cancel = True  # przerwanie od razu
        tab.running = False
        tab.start()
        tab.cancel()
        tab = await wait_generation(app, pilot)
        assert len(tab.proposals) <= 6
        assert not tab.running


async def test_take_whole_and_single_color():
    app = make_app()
    async with app.run_test(size=(150, 45)) as pilot:
        before = app.session
        await pilot.press("g")
        tab = await wait_generation(app, pilot)
        p = tab.proposals[0]
        tab.take_whole()
        await pilot.pause()
        for sl in app.session.slots:
            assert sl.value == (sl.value if sl.locked else p.values[sl.id])
        await pilot.press("ctrl+z")
        await pilot.pause()
        assert app.session == before
        dt = app.query_one("#detail-table", DataTable)
        dt.move_cursor(row=3)
        tab.take_color()
        await pilot.pause()
        sid = app.session.slots[3].id
        assert app.session.slots[3].value == p.values[sid]
        assert app.session.slots[4].value == before.slots[4].value


async def test_generate_only_selected_slot():
    app = make_app(small(1))
    async with app.run_test(size=(150, 45)) as pilot:
        table = app.query_one("#slot-table", DataTable)
        table.focus()
        table.move_cursor(row=5)
        await pilot.pause()
        app.action_tab("propozycje")
        await pilot.pause()
        app.query_one("#gen-one", Button).press()
        tab = await wait_generation(app, pilot)
        p = tab.proposals[0]
        target = app.session.slots[5].id
        assert p.slot_ids == (target,)
        assert p.values[target] != app.session.slots[5].value  # wybrany slot naprawdę się zmienił
        for sl in app.session.slots:
            if sl.id != target:
                assert p.values[sl.id] == sl.value


async def test_mood_apply_and_user_mood():
    app = make_app()
    async with app.run_test(size=(150, 60)) as pilot:
        app.action_tab("globalne")
        await pilot.pause()
        g = app.query_one(GlobalsTab)
        g.query_one("#mood", Select).value = "neon"
        g.query_one("#mood-apply", Button).press()
        await pilot.pause()
        assert app.session.mood == "neon"
        g = app.query_one(GlobalsTab)
        g.query_one("#mood-name", Input).value = "mój"
        g.query_one("#mood-save", Button).press()
        await pilot.pause()
        from algopalette.moods import list_moods

        assert "mój" in [m.name for m in list_moods()]


async def test_polarity_change_recomputes_defaults():
    app = make_app()
    async with app.run_test(size=(150, 60)) as pilot:
        app.action_tab("globalne")
        await pilot.pause()
        app.query_one(GlobalsTab).query_one("#polarity", Select).value = "light"
        await pilot.pause()
        g = app.session.globals
        assert g.polarity == "light"
        bg_l = g.role_defaults["bg"].lightness
        assert bg_l is not None and bg_l.value.lo is not None and bg_l.value.lo > 0.9


async def test_cvd_checkbox_and_optimizer_input():
    app = make_app()
    async with app.run_test(size=(150, 80)) as pilot:
        app.action_tab("globalne")
        await pilot.pause()
        gt = app.query_one(GlobalsTab)
        gt.query_one("#cvd-deutan", Checkbox).value = True
        await pilot.pause()
        assert "deutan" in app.session.globals.cvd.types
        inp = gt.query_one("#opt-n_proposals", Input)
        inp.value = "3"
        inp.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert app.session.globals.optimizer.n_proposals == 3
        inp.value = "0"
        await pilot.press("enter")
        await pilot.pause()
        assert app.session.globals.optimizer.n_proposals == 3
        assert inp.has_class("-bad")


async def test_source_paste_error_shown():
    app = make_app()
    async with app.run_test(size=(150, 45)) as pilot:
        app.action_tab("zrodlo")
        await pilot.pause()
        app.query_one("#paste", TextArea).text = "#fff zielony"
        app.query_one("#parse", Button).press()
        await pilot.pause()
        res = app.query_one("#parse-result")
        assert res.has_class("-error")
        assert "zielony" in str(res.render())


async def test_source_complete_locks():
    app = make_app()
    async with app.run_test(size=(150, 45)) as pilot:
        app.action_tab("zrodlo")
        await pilot.pause()
        app.query_one("#paste", TextArea).text = "#101418 #e8e8e8 #ff8080"
        app.query_one("#parse", Button).press()
        app.query_one("#apply", Button).press()
        await pilot.pause()
        s = app.session
        assert [sl.locked for sl in s.slots[:3]] == [True, True, True]
        assert to_hex(s.slots[2].value, "clip") == "#ff8080"
        await pilot.press("ctrl+z")
        await pilot.pause()
        assert not app.session.slots[2].locked


async def test_source_transfer_mode():
    app = make_app()
    async with app.run_test(size=(150, 45)) as pilot:
        app.action_tab("zrodlo")
        await pilot.pause()
        app.query_one("#from-current", Button).press()
        app.query_one("#mode", Select).value = "transfer"
        await pilot.pause()
        app.query_one("#apply", Button).press()
        await pilot.pause()
        assert app.session.globals.polarity == "light"


async def test_save_load_roundtrip(tmp_path):
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        p = tmp_path / "s.json"
        app.save_to(p)
        await pilot.pause()
        assert aio.load_session(p) == app.session


async def test_save_unwritable_dir_message(tmp_path, monkeypatch):
    app = make_app()
    msgs: list[str] = []
    async with app.run_test(size=(120, 40)) as pilot:
        monkeypatch.setattr(app, "notify", lambda m, **kw: msgs.append(str(m)))

        def boom(*a, **kw):
            raise PermissionError(13, "Brak uprawnień")

        monkeypatch.setattr(aio, "save_session", boom)
        app.save_to(tmp_path / "ro" / "x.json")
        await pilot.pause()
    assert any("Nie udało się zapisać" in m for m in msgs)


async def test_export_clipboard(tmp_path, monkeypatch):
    app = make_app()
    copied: list[str] = []
    async with app.run_test(size=(120, 40)) as pilot:
        monkeypatch.setattr(app, "copy_to_clipboard", copied.append)
        monkeypatch.setattr("algopalette.tui.app.default_pb_dir", lambda: tmp_path / "motifs")
        await pilot.press("ctrl+e")
        await pilot.pause()
        s = app.session
        expected = pb_json(
            [to_hex(sl.value, s.globals.fit_method) for sl in s.slots], s.globals.polarity
        )
        assert copied == [expected]
        await pilot.press("enter")  # zapis pliku pod domyślną ścieżką
        await pilot.pause()
    files = list((tmp_path / "motifs").glob("*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text())["format"] == "palettebuilder.v3"


async def test_value_edit_marks_out_of_gamut():
    app = make_app()
    async with app.run_test(size=(150, 45)) as pilot:
        s = app.session
        from algopalette.model import with_slot

        app.set_session(
            with_slot(s, replace(s.slots[2], value=OKLCH(0.75, 0.30, 140))), structural=True
        )
        await pilot.pause()
        hex_cell = app.query_one("#slot-table", DataTable).get_row_at(2)[3]
        assert "⚠" in str(hex_cell)


async def test_take_whole_keeps_slots_outside_proposal():
    app = make_app(small(1))
    async with app.run_test(size=(150, 45)) as pilot:
        table = app.query_one("#slot-table", DataTable)
        table.focus()
        table.move_cursor(row=5)
        await pilot.pause()
        app.query_one(ProposalsTab).start({app.session.slots[5].id})
        tab = await wait_generation(app, pilot)
        s = app.session
        edited = replace(s.slots[3], value=OKLCH(0.5, 0.05, 10))
        from algopalette.model import with_slot

        app.set_session(with_slot(s, edited), structural=True)  # edycja w trakcie przeglądania
        tab.take_whole()
        await pilot.pause()
        assert app.session.slots[3].value == OKLCH(0.5, 0.05, 10)  # przegląd I6


@pytest.mark.parametrize("raw", ["inf", "nan", "1e999"])
async def test_non_finite_inputs_rejected(raw):
    app = make_app()
    async with app.run_test(size=(150, 80)) as pilot:
        await pilot.press("f3")
        await pilot.pause()
        gt = app.query_one(GlobalsTab)
        for fid in ("#opt-time_cap_s", "#opt-n_proposals"):
            inp = gt.query_one(fid, Input)
            inp.focus()
            inp.value = raw
            await pilot.press("enter")
            await pilot.pause()
            assert inp.has_class("-bad")
        o = app.session.globals.optimizer
        assert o.time_cap_s == 30.0 and o.n_proposals == 2
        app.autosave_now()  # nic nie-skończonego w sesji → zapis działa (przegląd C2)


async def test_negative_seed_rejected_in_ui():
    app = make_app()
    async with app.run_test(size=(150, 80)) as pilot:
        await pilot.press("f3")
        await pilot.pause()
        inp = app.query_one(GlobalsTab).query_one("#opt-seed", Input)
        inp.focus()
        inp.value = "-3"
        await pilot.press("enter")
        await pilot.pause()
        assert inp.has_class("-bad") and app.session.globals.optimizer.seed == 0


async def test_delta_e_change_rescales_thresholds():
    app = make_app()
    async with app.run_test(size=(150, 60)) as pilot:
        await pilot.press("f3")
        await pilot.pause()
        app.query_one(GlobalsTab).query_one("#delta_e", Select).value = "2000"
        await pilot.pause()
        g = app.session.globals
        md = g.role_defaults["accent"].min_distance
        assert g.delta_e == "2000" and md is not None and md.value == pytest.approx(0.08 * 156)


async def test_source_reparses_edited_text():
    app = make_app()
    async with app.run_test(size=(150, 45)) as pilot:
        await pilot.press("f5")
        await pilot.pause()
        ta = app.query_one("#paste", TextArea)
        ta.text = "#101418 #e8e8e8 #ff8080"
        app.query_one("#parse", Button).press()
        await pilot.pause()
        ta.text = "#101418 #e8e8e8 #80ff80"  # zmiana bez „Odczytaj”
        await pilot.pause()
        app.query_one("#apply", Button).press()
        await pilot.pause()
        assert to_hex(app.session.slots[2].value, "clip") == "#80ff80"  # przegląd I5


async def test_overwrite_confirm_defaults_to_no(tmp_path):
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        p = tmp_path / "x.json"
        app.save_to(p)
        before = p.read_text()
        s = app.session
        app.set_session(replace(s, slots=(replace(s.slots[0], name="zmiana"), *s.slots[1:])))
        app.save_to(p)
        await pilot.pause()
        await pilot.press("enter")  # odruchowy Enter = „Nie” (przegląd M13)
        await pilot.pause()
        assert p.read_text() == before
