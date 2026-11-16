"""Przepływy całego programu: zasady → generowanie → przejęcie; pliki i autozapis w formacie v1."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

import algopalette.__main__ as main_mod
from algopalette import _engine
from algopalette import io as aio
from algopalette.gui.app import MainWindow, open_window
from algopalette.model import HueArc, Rule, default_session
from algopalette.rules_edit import set_rule

REFERENCE = Path(__file__).parent.parent / "fixtures" / "v1_reference" / "quality.json"
IMPLEMENTED = _engine.build_info()["implemented"]
needs_generate = pytest.mark.skipif("generate" not in IMPLEMENTED, reason="silnik nie generuje")
MERGED = "zakres i cel odcienia scalono"


def v1_document(*, with_note: bool = True) -> dict:
    """Sesja v1 z danych wzorcowych („chłodny mglisty”, ciemna); z ``with_note`` akcent 2 ma
    i zakres, i cel odcienia — migracja scala je i musi o tym powiedzieć."""
    data = json.loads(REFERENCE.read_text(encoding="utf-8"))[4]["session"]
    assert data["format"] == "algopalette.v1"
    if with_note:
        flags = {"enabled": True, "hard": True, "weight": 1.0}
        cond = data["slots"][3]["conditions"]
        cond["hue_range"] = {"value": {"lo": 0.0, "hi": 90.0}, **flags}
        cond["hue_target"] = {"value": {"target": 60.0, "tol": 20.0}, **flags}
    return data


def write_v1(path: Path, **kw) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(v1_document(**kw)), encoding="utf-8")
    return path


# --- plik v1 w oknie --------------------------------------------------------------------------


def test_v1_file_opens_with_rules_and_notes_and_saves_as_v2(win, tmp_path):
    path = write_v1(tmp_path / "stara.json")
    assert win.open_path(path)
    assert len(win.migration_notes) == 1 and MERGED in win.migration_notes[0]
    assert win._notes_box is not None and win._notes_box.isVisible()
    s = win.session
    assert s.preset == "chłodny mglisty"
    accent = s.slots[3]
    assert accent.rules.hue == Rule(HueArc(40.0, 80.0))  # zasady wpisane w kolor, nic wspólnego
    win.show_rules([accent.id])
    win.rules_tab.flush()
    row = win.rules_tab.rows["hue"]
    assert row.state == "same" and row.slider.values()[:2] == (40.0, 80.0)
    assert win.rules_tab.rows["lightness"].slider.values()[:2] == (0.66, 0.80)
    out = tmp_path / "nowa.json"
    assert win.save_to(out)
    assert json.loads(out.read_text(encoding="utf-8"))["format"] == "algopalette.v2"
    assert aio.load_session_ex(out) == (s, ())  # po zapisie nie ma już czego migrować


# --- start programu z plikiem albo autozapisem v1 ---------------------------------------------


def test_start_from_v1_autosave_migrates_keeps_copy_and_reports():
    auto = write_v1(aio.autosave_path())
    original = auto.read_bytes()
    st = main_mod.startup_session(None, fresh=False)
    backup = auto.with_name("last.v1.json")
    assert backup.read_bytes() == original  # stary plik został obok, bajt w bajt
    assert st.path is None
    assert st.session.preset == "chłodny mglisty" and st.session.slots[3].rules.hue is not None
    assert len(st.migration_notes) == 1 and MERGED in st.migration_notes[0]
    assert st.notice is not None and str(backup) in st.notice
    assert json.loads(auto.read_text(encoding="utf-8"))["format"] == "algopalette.v2"

    backup.write_bytes(b"kopia z pierwszego startu")  # znacznik: drugi start jej nie rusza
    again = main_mod.startup_session(None, fresh=False)
    assert again.session == st.session
    assert again.migration_notes == () and again.notice is None
    assert backup.read_bytes() == b"kopia z pierwszego startu"
    assert sorted(p.name for p in auto.parent.iterdir()) == ["last.json", "last.v1.json"]


def test_start_from_v1_autosave_without_losses_still_mentions_the_copy():
    auto = write_v1(aio.autosave_path(), with_note=False)
    st = main_mod.startup_session(None, fresh=False)
    assert st.migration_notes == ()
    assert st.notice is not None and "last.v1.json" in st.notice
    assert auto.with_name("last.v1.json").exists()


def test_existing_copy_is_never_overwritten():
    auto = write_v1(aio.autosave_path())
    backup = auto.with_name("last.v1.json")
    backup.write_bytes(b"wczesniejsza kopia")
    st = main_mod.startup_session(None, fresh=False)
    assert backup.read_bytes() == b"wczesniejsza kopia"
    assert st.session.preset == "chłodny mglisty"
    assert json.loads(auto.read_text(encoding="utf-8"))["format"] == "algopalette.v2"


def test_v2_autosave_starts_quietly():
    s = replace(default_session(), preset=None)
    aio.save_session(s, aio.autosave_path())
    st = main_mod.startup_session(None, fresh=False)
    assert (st.session, st.notice, st.path, st.migration_notes) == (s, None, None, ())
    assert not aio.autosave_path().with_name("last.v1.json").exists()


def test_start_with_v1_file_passes_notes_and_keeps_the_file(tmp_path):
    path = write_v1(tmp_path / "stara.json")
    before = path.read_bytes()
    st = main_mod.startup_session(path, fresh=False)
    assert st.path == path and path.read_bytes() == before
    assert len(st.migration_notes) == 1 and MERGED in st.migration_notes[0]


def test_main_hands_notes_to_the_window(monkeypatch, tmp_path):
    import algopalette.gui.app as gapp

    got = {}
    monkeypatch.setattr(gapp, "run", lambda session, **kw: got.update(kw, session=session) or 0)
    path = write_v1(tmp_path / "stara.json")
    with pytest.raises(SystemExit):
        main_mod.main([str(path)])
    assert got["file_path"] == path
    assert len(got["migration_notes"]) == 1 and MERGED in got["migration_notes"][0]


def test_window_shows_notes_after_opening(qtbot):
    w = open_window(default_session(), migration_notes=("akcent 2: coś przepadło",), autosave=False)
    qtbot.addWidget(w)
    assert w.isVisible()
    assert w.migration_notes == ("akcent 2: coś przepadło",)
    assert w._notes_box is not None and "coś przepadło" in w._notes_box.text()
    quiet = open_window(default_session(), autosave=False)
    qtbot.addWidget(quiet)
    assert quiet.migration_notes == () and quiet._notes_box is None


# --- zasady → propozycje → paleta -------------------------------------------------------------


def in_arc(h: float, lo: float, hi: float) -> bool:
    return (h - lo) % 360.0 <= (hi - lo) % 360.0


@needs_generate
def test_rules_to_proposals_to_palette(qtbot):
    w = MainWindow(default_session(), autosave=False)
    qtbot.addWidget(w)
    w.show()
    ids = [slot.id for slot in w.session.slots[2:5]]  # akcenty 1–3
    w.show_rules(ids)
    w.rules_tab.flush()
    banned = Rule(HueArc(0.0, 360.0, exclude=((60.0, 85.0),)))
    w.rules_tab.write(set_rule(w.session, ids, "hue", banned))
    assert all(w.session.slots[i].rules.hue == banned for i in (2, 3, 4))

    w.rules_tab.generate_btn.click()
    tab = w.proposals_tab
    assert w.tabs.currentWidget() is tab
    qtbot.waitUntil(lambda: not tab.running, timeout=60000)
    assert tab.table.rowCount() == 6
    for prop in tab.proposals:
        for sid in ids:
            assert not in_arc(prop.values[sid].h, 60.0, 85.0), (sid, prop.values[sid])

    before = w.session
    tab.table.selectRow(0)
    tab.take_whole()
    first = tab.proposals[0]
    assert w.session != before
    assert all(w.session.slots[i].value == first.values[w.session.slots[i].id] for i in range(10))
    w.tabs.setCurrentWidget(w.palette_tab)
    table = w.palette_tab.table
    shown = [it.text() for r in range(10) if (it := table.item(r, 3)) is not None]
    assert shown == [first.hexes[slot.id] for slot in w.session.slots]
    assert first.ok and w.violations == []
