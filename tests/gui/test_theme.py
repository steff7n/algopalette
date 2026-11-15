import json

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit

from algopalette.color import contrast_hex
from algopalette.gui import theme


@pytest.fixture(autouse=True)
def _restore_light(qapp):
    yield
    theme.apply(qapp, "light")


def _write(text: str) -> None:
    p = theme.settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("text", [None, "{nie json", '{"theme": "fiolet"}', "[1, 2]"])
def test_load_mode_missing_or_corrupt_is_system(text):
    if text is not None:
        _write(text)
    assert theme.load_mode() == "system"


def test_save_mode_keeps_other_keys():
    _write('{"x": 1}')
    theme.save_mode("dark")
    assert json.loads(theme.settings_path().read_text(encoding="utf-8")) == {
        "x": 1,
        "theme": "dark",
    }
    assert theme.load_mode() == "dark"


def test_env_overrides_saved(monkeypatch):
    theme.save_mode("light")
    monkeypatch.setenv("ALGOPALETTE_THEME", "dark")
    assert theme.initial_mode() == "dark"
    monkeypatch.setenv("ALGOPALETTE_THEME", "")
    assert theme.initial_mode() == "light"


@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
def test_semantic_contrast(dark):
    pal = theme.dark_palette() if dark else theme.light_palette()
    c = theme.DARK if dark else theme.LIGHT
    for bg in (pal.window().color().name(), pal.base().color().name()):
        for name in ("hard", "soft", "ok", "warn_text", "hint", *(f"badge:{k}" for k in c.badge)):
            fg = c.badge[name[6:]] if name.startswith("badge:") else getattr(c, name)
            assert contrast_hex(fg, bg, "wcag21") >= 4.5, (name, fg, bg)
        assert contrast_hex(c.error_border, bg, "wcag21") >= 3.0
    assert contrast_hex(c.bad_cell_fg, c.bad_cell_bg, "wcag21") >= 4.5
    tip = contrast_hex(pal.toolTipText().color().name(), pal.toolTipBase().color().name(), "wcag21")
    assert tip >= 7.0


def test_menu_switch_live(win):
    win.act_theme_dark.trigger()
    assert QApplication.palette().window().color().lightness() < 100
    assert theme.load_mode() == "dark"
    assert win.act_theme_dark.isChecked()
    win.act_theme_light.trigger()
    assert QApplication.palette().window().color().lightness() > 150
    assert theme.load_mode() == "light"
    assert win.violations_panel.title.text()  # przemalowany bez wyjątku


def test_error_border_and_text_follow_theme(qtbot, qapp):
    edit, lbl, badge = QLineEdit(), QLabel("x"), QLabel("nastrój")
    for w in (edit, lbl, badge):
        qtbot.addWidget(w)
    theme.apply(qapp, "light")
    theme.mark_error(edit, True)
    theme.mark_text(lbl, "hard", bold=True)
    theme.style_badge(badge, "mood")
    assert theme.LIGHT.error_border in edit.styleSheet()
    theme.apply(qapp, "dark")
    assert theme.DARK.error_border in edit.styleSheet()
    assert theme.DARK.hard in lbl.styleSheet() and "bold" in lbl.styleSheet()
    assert theme.DARK.badge["mood"] in badge.styleSheet()
    theme.mark_error(edit, False)
    assert edit.styleSheet() == ""
    theme.apply(qapp, "light")
    assert edit.styleSheet() == ""


def test_relation_selector_rule(qtbot, qapp):
    w = QLabel()
    qtbot.addWidget(w)
    theme.mark_error(w, True, "QLabel")
    assert w.styleSheet().startswith("QLabel {")


def test_save_failure_is_reported(win, monkeypatch):
    def boom(_mode):
        raise OSError("tylko do odczytu")

    monkeypatch.setattr(theme, "save_mode", boom)
    win.act_theme_dark.trigger()
    assert "tylko do odczytu" in win.statusBar().currentMessage()
    assert theme.current_mode() == "dark"


def test_system_follows_scheme(qapp, monkeypatch):
    from PySide6.QtCore import Qt

    theme.apply(qapp, "system")
    hints = type(qapp.styleHints())
    monkeypatch.setattr(hints, "colorScheme", lambda _self: Qt.ColorScheme.Dark)
    theme._system_changed()
    assert theme.current_is_dark()
    theme.apply(qapp, "light")
    theme._system_changed()  # tryb jasny ignoruje zmianę systemu
    assert not theme.current_is_dark()


def test_hint_follows_theme(qtbot, qapp):
    from algopalette.gui.widgets import hint

    lbl = hint("objaśnienie")
    qtbot.addWidget(lbl)
    theme.apply(qapp, "dark")
    assert theme.DARK.hint in lbl.styleSheet()
    theme.apply(qapp, "light")
    assert theme.LIGHT.hint in lbl.styleSheet()


def test_wheel_background_follows_theme(win, qtbot, qapp):
    tab = win.analysis_tab
    win.tabs.setCurrentWidget(tab)
    tab.refresh_from_session()
    light = tab.wheel._background(64).pixelColor(0, 0)
    theme.apply(qapp, "dark")
    dark = tab.wheel._background(64).pixelColor(0, 0)
    assert dark.lightness() < light.lightness()
