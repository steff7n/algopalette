"""Motyw okna: systemowy / jasny / ciemny, przełączany na żywo, zapamiętany w
``config_dir()/gui.json``.

Wszystkie kolory interfejsu (nie danych palety) żyją tutaj: palety Qt obu motywów i kolory
semantyczne (``colors()``). Widżety barwione arkuszem stylu robią to przez ``mark_error`` /
``mark_text`` — zmiana motywu przemalowuje je bez przebudowy (``restyle_all``).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast, get_args

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory, QToolTip, QWidget

from algopalette import io as aio

ThemeMode = Literal["system", "light", "dark"]
MODES: tuple[ThemeMode, ...] = get_args(ThemeMode)
SETTINGS_FILE = "gui.json"
ENV_VAR = "ALGOPALETTE_THEME"


@dataclass(frozen=True)
class Colors:
    """Kolory semantyczne jednego motywu (``#rrggbb``)."""

    hard: str  # naruszenie twarde (tekst, znacznik ✗)
    soft: str  # naruszenie miękkie (~)
    ok: str  # „spełnione”
    error_border: str  # ramka pola z błędną wartością
    warn_text: str  # ostrzeżenie w tekście (np. kolor poza gamutem)
    bad_cell_bg: str  # komórka macierzy poniżej wymagania (tło)
    bad_cell_fg: str  # … i jej tekst
    hint: str  # przygaszony tekst objaśnień (hint)
    # rysunki na kolorowym tle (gradienty, koło odcieni) — te same w obu motywach
    handle_ring: str = "#202020"
    handle_fill: str = "#f4f4f4"
    arc_range: str = "#f0c419"
    arc_target: str = "#ff7a1a"


LIGHT = Colors(
    hard="#b3261e",
    soft="#7d5800",
    ok="#1b6e36",
    error_border="#c62828",
    warn_text="#7d5800",
    bad_cell_bg="#b3261e",
    bad_cell_fg="#ffffff",
    hint="#575a60",
)
DARK = Colors(
    hard="#ff8a80",
    soft="#f2c14e",
    ok="#6fd08c",
    error_border="#ff6b6b",
    warn_text="#f2c14e",
    bad_cell_bg="#9e2b25",
    bad_cell_fg="#ffffff",
    hint="#a9acb2",
)


class _Notifier(QObject):
    changed = Signal()


notifier = _Notifier()
_state: dict[str, Any] = {"mode": "system", "dark": False, "hooked": False}


# --- ustawienia --------------------------------------------------------------------------------
def settings_path() -> Path:
    return aio.config_dir() / SETTINGS_FILE


def _read_settings() -> dict[str, Any]:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_mode() -> ThemeMode:
    """Zapisany motyw; brak pliku, uszkodzony plik albo nieznana wartość → ``"system"``."""
    m = _read_settings().get("theme")
    return cast(ThemeMode, m) if m in MODES else "system"


def read_setting(key: str, default: Any = None) -> Any:
    """Wartość z ``gui.json``; brak pliku, uszkodzony plik albo brak klucza → ``default``."""
    return _read_settings().get(key, default)


def write_setting(key: str, value: Any) -> None:
    """Zapisuje klucz, zachowując inne klucze pliku. Zapis atomowy; ``OSError`` idzie wyżej."""
    data = _read_settings()
    data[key] = value
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".gui-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def save_mode(mode: ThemeMode) -> None:
    """Zapisuje motyw okna, zachowując inne klucze pliku; ``OSError`` idzie wyżej."""
    write_setting("theme", mode)


def initial_mode() -> ThemeMode:
    """Motyw na starcie: ``ALGOPALETTE_THEME=dark|light`` ma pierwszeństwo przed zapisem."""
    env = os.environ.get(ENV_VAR, "").strip().lower()
    if env in ("dark", "light"):
        return cast(ThemeMode, env)
    return load_mode()


# --- stosowanie --------------------------------------------------------------------------------
def is_dark(mode: ThemeMode) -> bool:
    if mode == "system":
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    return mode == "dark"


def current_mode() -> ThemeMode:
    return cast(ThemeMode, _state["mode"])


def current_is_dark() -> bool:
    return bool(_state["dark"])


def colors() -> Colors:
    """Kolory semantyczne AKTUALNIE zastosowanego motywu."""
    return DARK if _state["dark"] else LIGHT


def light_palette() -> QPalette:
    style = QStyleFactory.create("Fusion")
    return style.standardPalette() if style is not None else QPalette()


def dark_palette() -> QPalette:
    p = QPalette()
    R = QPalette.ColorRole
    for role, hex_ in (
        (R.Window, "#2a2c31"),
        (R.WindowText, "#e6e6e6"),
        (R.Base, "#1f2125"),
        (R.AlternateBase, "#26282d"),
        (R.ToolTipBase, "#3b3f47"),  # wyraźnie jaśniejsze od okna — podpowiedź się odcina
        (R.ToolTipText, "#f2f2f2"),
        (R.Text, "#e6e6e6"),
        (R.Button, "#33363c"),
        (R.ButtonText, "#e6e6e6"),
        (R.BrightText, "#ffffff"),
        (R.Highlight, "#3a6bc0"),
        (R.HighlightedText, "#ffffff"),
        (R.PlaceholderText, "#9a9da3"),
        (R.Link, "#8ab4f8"),
        (R.LinkVisited, "#c58af9"),
        (R.Mid, "#4a4d54"),
        (R.Midlight, "#3f4248"),
        (R.Dark, "#15161a"),
        (R.Shadow, "#0c0d10"),
        (R.Light, "#55585f"),
    ):
        p.setColor(role, QColor(hex_))
    dis = QPalette.ColorGroup.Disabled
    for role in (R.Text, R.ButtonText, R.WindowText):
        p.setColor(dis, role, QColor("#75787e"))
    return p


def apply(app: QApplication, mode: ThemeMode) -> None:
    """Stosuje motyw od razu (bez restartu) i ogłasza zmianę przez ``notifier.changed``.
    Styl (Fusion) ustawia ``run()`` raz — tu tylko paleta, żeby nie zgubić proxy-stylu."""
    dark = is_dark(mode)
    _state["mode"], _state["dark"] = mode, dark
    pal = dark_palette() if dark else light_palette()
    app.setPalette(pal)
    QToolTip.setPalette(pal)  # paleta podpowiedzi jest osobna i statyczna — inaczej zostaje stara
    if not _state["hooked"]:
        _state["hooked"] = True
        QGuiApplication.styleHints().colorSchemeChanged.connect(_system_changed)
    restyle_all()
    notifier.changed.emit()


def _system_changed(*_args) -> None:
    app = QApplication.instance()
    if current_mode() == "system" and isinstance(app, QApplication):
        apply(app, "system")


# --- kolorowanie widżetów arkuszem stylu ---------------------------------------------------------
_ERR, _ERR_SEL, _TEXT = "ap_error", "ap_error_sel", "ap_text"


def mark_error(w: QWidget, bad: bool, selector: str | None = None) -> None:
    """Ramka błędu w kolorze motywu (``selector`` zawęża regułę, np. ``"RelationRow"``)."""
    w.setProperty(_ERR, bad)
    w.setProperty(_ERR_SEL, selector or "")
    _restyle(w)


def mark_text(w: QWidget, kind: str | None, *, bold: bool = False) -> None:
    """Kolor tekstu z ``colors()`` (``"hard"``/``"soft"``/``"ok"``/``"warn_text"``) albo zwykły."""
    w.setProperty(_TEXT, f"{kind}{'!' if bold else ''}" if kind else "")
    _restyle(w)


def _restyle(w: QWidget) -> None:
    c = colors()
    text = w.property(_TEXT)
    if text:
        kind, bold = text.rstrip("!"), text.endswith("!")
        w.setStyleSheet(f"color: {getattr(c, kind)};" + (" font-weight: bold;" if bold else ""))
        return
    if w.property(_ERR):
        sel = w.property(_ERR_SEL)
        rule = f"border: 2px solid {c.error_border};"
        w.setStyleSheet(f"{sel} {{ {rule} }}" if sel else rule)
        return
    # żaden znacznik nie jest aktywny (np. mark_text(w, None) po błędzie) → bez koloru z motywu
    if any(w.property(k) is not None for k in (_ERR, _TEXT)):
        w.setStyleSheet("")


def restyle_all() -> None:
    for w in QApplication.allWidgets():
        if any(w.property(k) is not None for k in (_ERR, _TEXT)):
            _restyle(w)
