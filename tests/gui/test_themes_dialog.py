"""Okno „Motywy z sieci”: pobieranie (MockTransport z fixture), filtry, import, stany błędów."""

import io
import json
import tarfile
import threading
from pathlib import Path

import httpx
import pytest

from algopalette.gui import help as gh
from algopalette.gui import theme
from algopalette.gui.themes_dialog import KEEP_SETTINGS_KEY, ThemesDialog
from algopalette.model import add_accent
from algopalette.themes import Theme, is_dark, net

FIX = Path(__file__).parent.parent / "fixtures" / "themes"


def tinted_archive() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in sorted((FIX / "tinted").rglob("*")):
            if p.is_file():
                tar.add(p, arcname=f"schemes-HEAD/{p.relative_to(FIX / 'tinted').as_posix()}")
    return buf.getvalue()


class Server:
    """Odpowiedzi źródeł z fixture; ``hold`` wstrzymuje wybrany host do ``release``."""

    def __init__(self, *, fail: Exception | None = None, lospec: bytes | None = None):
        self.fail = fail
        self.lospec = lospec or (FIX / "lospec_page.json").read_bytes()
        self.requests: list[str] = []
        self.hold: dict[str, threading.Event] = {}
        self.tinted = tinted_archive()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url)
        if self.fail is not None:
            raise self.fail
        for key, ev in self.hold.items():
            if key in url:
                ev.wait(5)
        if "codeload" in url:
            return httpx.Response(200, content=self.tinted)
        if "Gogh" in url:
            return httpx.Response(200, content=(FIX / "gogh.json").read_bytes())
        if "atomcorp" in url:
            return httpx.Response(200, content=(FIX / "wt.json").read_bytes())
        if "lospec" in url:
            return httpx.Response(200, content=self.lospec)
        return httpx.Response(404)

    def factory(self):
        return lambda: net.make_client(transport=httpx.MockTransport(self))


def open_dialog(win, qtbot, srv: Server) -> ThemesDialog:
    win.themes_client_factory = srv.factory()
    win.open_themes()
    d = win.themes_dialog
    assert d is not None
    qtbot.waitUntil(lambda: not d._loading, timeout=5000)
    return d


def names(d: ThemesDialog) -> list[str]:
    return [d.model.item(i).data(0) for i in range(d.model.rowCount())]


def themes(d: ThemesDialog) -> list[Theme]:
    from algopalette.gui.theme_preview import THEME_ROLE

    return [d.model.item(i).data(THEME_ROLE) for i in range(d.model.rowCount())]


def set_combo(combo, data) -> None:
    combo.setCurrentIndex(combo.findData(data))


@pytest.fixture(autouse=True)
def _wait_pool(win):
    yield
    d = win.themes_dialog
    if d is not None:
        d.shutdown()
        d._pool.waitForDone(5000)


def test_single_non_modal_instance(win, qtbot):
    d = open_dialog(win, qtbot, Server())
    win.open_themes()
    assert win.themes_dialog is d
    assert d.isModal() is False and d.isVisible()


def test_all_sources_and_filters(win, qtbot):
    d = open_dialog(win, qtbot, Server())
    assert {t.source for t in themes(d)} == {"base16", "gogh", "wt"}
    d.search.setText("NORD")
    qtbot.waitUntil(lambda: names(d) == ["Nord"], timeout=2000)
    d.search.setText("")
    set_combo(d.bg_filter, "light")
    qtbot.waitUntil(lambda: bool(names(d)), timeout=2000)
    assert set(names(d)) >= {"1984 Light", "3024 Day"}
    assert all(is_dark(t) is False for t in themes(d))


def test_lospec_requested_by_downloads(win, qtbot):
    srv = Server()
    d = open_dialog(win, qtbot, srv)
    set_combo(d.source, "lospec")
    qtbot.waitUntil(lambda: bool(names(d)) and not d._loading, timeout=3000)
    lospec_urls = [u for u in srv.requests if "lospec" in u]
    assert lospec_urls and "sortingType=downloads" in lospec_urls[-1]
    assert "tag=&" in lospec_urls[-1]
    assert d.light_bg.isVisibleTo(d) and d.hint.isVisibleTo(d)
    assert d.more.isVisibleTo(d)  # totalCount 3171 > 6
    d.search.setText("Warm colours")
    qtbot.waitUntil(lambda: "tag=warm&" in srv.requests[-1], timeout=3000)


def test_import_replaces_session_and_undo_restores(win, qtbot):
    d = open_dialog(win, qtbot, Server())
    before = win.session
    path_before = win.file_path
    hist = len(win.history)
    d.search.setText("nord")
    qtbot.waitUntil(lambda: names(d) == ["Nord"], timeout=2000)
    d.load.click()
    s = win.session
    assert s != before
    assert len(win.history) == hist + 1
    assert win.file_path == path_before
    assert win.tabs.currentWidget() is win.palette_tab
    assert len(s.slots) == 10 and s.slots[0].name == "tło"
    assert s.globals.hue_scheme.kind == "custom"
    win.action_undo()
    assert win.session == before


def test_keep_settings_mode_and_persistence(win, qtbot):
    d = open_dialog(win, qtbot, Server())
    g = win.session.globals
    d.keep_settings.setChecked(True)
    assert theme.read_setting(KEEP_SETTINGS_KEY) is True
    d.load.click()
    assert win.session.globals == g
    d.close()
    d.deleteLater()
    win.themes_dialog = None
    d2 = open_dialog(win, qtbot, Server())
    assert d2.keep_settings.isChecked()


def test_network_error_without_cache_shows_message(win, qtbot):
    d = open_dialog(win, qtbot, Server(fail=httpx.ConnectError("down")))
    assert names(d) == []
    assert "Nie udało się pobrać katalogu" in d.status.text()
    assert d.load.isEnabled() is False


def test_late_result_does_not_change_list(win, qtbot):
    srv = Server()
    gate = threading.Event()
    srv.hold["Gogh"] = gate
    win.themes_client_factory = srv.factory()
    win.open_themes()
    d = win.themes_dialog
    set_combo(d.source, "wt")
    qtbot.waitUntil(lambda: "wt" not in d._loading and bool(names(d)), timeout=3000)
    shown = names(d)
    gate.set()
    qtbot.waitUntil(lambda: "gogh" not in d._loading, timeout=3000)
    qtbot.wait(50)
    assert names(d) == shown
    assert {t.source for t in themes(d)} == {"wt"}


def test_close_while_loading_is_safe(win, qtbot):
    srv = Server()
    gate = threading.Event()
    srv.hold["codeload"] = gate
    win.themes_client_factory = srv.factory()
    win.open_themes()
    d = win.themes_dialog
    d.close()
    gate.set()
    d._pool.waitForDone(5000)
    qtbot.wait(50)
    assert not d._loading


def test_import_removing_selected_rule_colors(win, qtbot):
    s = win.session
    while len(s.slots) < 12:
        s = add_accent(s)
    win.replace_session(s)
    win.show_rules([win.session.slots[11].id])
    d = open_dialog(win, qtbot, Server())
    d.search.setText("3024")
    qtbot.waitUntil(lambda: "3024" in names(d), timeout=2000)
    d.view.setCurrentIndex(d.model.index(names(d).index("3024"), 0))
    d.load.click()
    assert len(win.session.slots) == 8
    win.tabs.setCurrentWidget(win.rules_tab)
    qtbot.wait(20)
    ids = {sl.id for sl in win.session.slots}
    assert set(win.rules_tab.strip.selection().ids) <= ids


def test_lospec_palette_with_too_few_colors(win, qtbot):
    page = {
        "palettes": [
            {"title": "Dwa", "slug": "dwa", "colors": ["000000", "000000", "ffffff"], "user": None}
        ],
        "totalCount": 1,
    }
    d = open_dialog(win, qtbot, Server(lospec=json.dumps(page).encode()))
    set_combo(d.source, "lospec")
    qtbot.waitUntil(lambda: names(d) == ["Dwa"] and not d._loading, timeout=3000)
    assert d.load.isEnabled() is False
    assert "Za mało" in d.preview.message
    assert not d.more.isVisibleTo(d)


def test_dialog_help_coverage(win, qtbot):
    d = open_dialog(win, qtbot, Server())
    assert gh.uncovered(d) == [], "\n".join(gh.uncovered(d))
    set_combo(d.source, "lospec")
    qtbot.waitUntil(lambda: not d._loading, timeout=3000)
    assert gh.uncovered(d) == [], "\n".join(gh.uncovered(d))
