"""Pomoc kontekstowa: podpowiedzi „F1 — więcej”, F1 → panel Pomocy na temacie elementu, Shift+F1
(tryb „kliknij element”), wyszukiwarka i test pokrycia (``uncovered``).

Klucz pomocy żyje na obiekcie jako dynamiczna właściwość ``help_key`` (widżet, ``QAction``), dla
nagłówków tabel jako lista ``help_columns`` / ``help_rows`` na widoku, dla zakładek w ``tabData``.
"""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QEvent, QModelIndex, QObject, QPoint, Qt, QUrl
from PySide6.QtGui import (
    QAction,
    QCursor,
    QDesktopServices,
    QHelpEvent,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSlider,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDockWidget,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMenuBar,
    QPlainTextEdit,
    QProxyStyle,
    QScrollBar,
    QSplitter,
    QStyle,
    QStyleFactory,
    QTabBar,
    QTextBrowser,
    QTextEdit,
    QToolBar,
    QToolButton,
    QToolTip,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from algopalette.gui.help_content import GROUPS, TOPICS
from algopalette.gui.widgets import hbox, vbox

HELP_PROP = "help_key"
DECORATIVE_PROP = "help_decorative"
COLUMNS_PROP = "help_columns"
ROWS_PROP = "help_rows"
HELP_ROLE = int(Qt.ItemDataRole.UserRole) + 77
TOOLTIP_DELAY_MS = 300
PANEL_NAME = "help-panel"
MORE = "F1 — więcej"

# Klasy, których wnętrze nie wymaga własnych kluczy (części składowe jednego elementu).
_OPAQUE = (QComboBox, QAbstractSpinBox, QAbstractItemView, QTabBar, QMenu, QScrollBar, QToolBar)


# --- podpinanie ----------------------------------------------------------------------------------
def tooltip_html(key: str, extra: str = "") -> str:
    """Podpowiedź: tytuł, krótki opis, opcjonalny dopisek kontekstowy i „F1 — więcej”."""
    t = TOPICS[key]
    parts = [f"<b>{html.escape(t.title)}</b>", html.escape(t.short)]
    if extra:
        parts.append(f"<span style='font-family: monospace'>{html.escape(extra)}</span>")
    parts.append(f"<i>{MORE}</i>")
    return "<p style='white-space: normal'>" + "<br>".join(parts) + "</p>"


def _check(key: str) -> None:
    if key not in TOPICS:
        raise KeyError(f"brak tematu pomocy: {key}")


def attach(obj: QWidget | QAction, key: str, *, children: bool = False, extra: str = "") -> None:
    """Klucz pomocy + podpowiedź. ``children=True``: także potomkowie bez własnego klucza
    (części jednego elementu, np. pole liczbowe i pasek w suwaku). ``extra``: dopisek w podpowiedzi
    (np. hex próbki)."""
    _check(key)
    obj.setProperty(HELP_PROP, key)
    obj.setToolTip(tooltip_html(key, extra))
    if isinstance(obj, QAction):
        obj.setStatusTip(TOPICS[key].short)
    elif children:
        for ch in obj.findChildren(QWidget):
            if not ch.property(HELP_PROP):
                ch.setProperty(HELP_PROP, key)
                ch.setToolTip(tooltip_html(key, extra))


def key_of(obj: QObject | None) -> str | None:
    if obj is None:
        return None
    k = obj.property(HELP_PROP)
    return k if isinstance(k, str) and k else None


class _HeaderTips(QObject):
    """Podpowiedź sekcji nagłówka wg kluczy zapisanych na widoku (przeżywa przebudowę nagłówków)."""

    def eventFilter(self, obj: QObject, ev: QEvent) -> bool:
        if ev.type() == QEvent.Type.ToolTip and isinstance(obj, QWidget):
            header = obj.parentWidget()
            if isinstance(header, QHeaderView) and isinstance(ev, QHelpEvent):
                key = _header_key(header, ev.pos())
                if key is not None:
                    QToolTip.showText(ev.globalPos(), tooltip_html(key), obj)
                    return True
        return False


_header_tips = _HeaderTips()


def attach_header(
    view: QAbstractItemView, keys: str | Sequence[str | None], *, vertical: bool = False
) -> None:
    """Klucze kolumn (albo wierszy, ``vertical=True``): jeden klucz dla wszystkich albo lista."""
    seq = [keys] if isinstance(keys, str) else list(keys)
    for k in seq:
        if k is not None:
            _check(k)
    view.setProperty(
        ROWS_PROP if vertical else COLUMNS_PROP, keys if isinstance(keys, str) else seq
    )
    header = _header_of(view, vertical)
    if header is not None:
        header.viewport().installEventFilter(_header_tips)


def _header_of(view: QAbstractItemView, vertical: bool) -> QHeaderView | None:
    getter = getattr(view, "verticalHeader" if vertical else "horizontalHeader", None)
    if getter is None:
        getter = getattr(view, "header", None)
    h = getter() if getter is not None else None
    return h if isinstance(h, QHeaderView) else None


def _section_key(view: QWidget, vertical: bool, index: int) -> str | None:
    keys = view.property(ROWS_PROP if vertical else COLUMNS_PROP)
    if isinstance(keys, str):
        return keys
    if isinstance(keys, list) and 0 <= index < len(keys):
        k = keys[index]
        return k if isinstance(k, str) else None
    return None


def _header_key(header: QHeaderView, local: QPoint) -> str | None:
    view = header.parentWidget()
    if view is None:
        return None
    vertical = header.orientation() == Qt.Orientation.Vertical
    idx = header.logicalIndexAt(local)
    return _section_key(view, vertical, idx) or key_of(view)


def attach_tab(tabs: Any, index: int, key: str) -> None:
    """Klucz zakładki ``index`` w ``QTabWidget``/``QTabBar``."""
    _check(key)
    bar = tabs if isinstance(tabs, QTabBar) else tabs.tabBar()
    bar.setTabData(index, key)
    bar.setTabToolTip(index, tooltip_html(key))


def attach_form_labels(fl: QFormLayout) -> None:
    """Etykiety wierszy ``QFormLayout`` dostają klucz swojego pola (pole musi mieć klucz)."""
    for r in range(fl.rowCount()):
        label = fl.itemAt(r, QFormLayout.ItemRole.LabelRole)
        field = fl.itemAt(r, QFormLayout.ItemRole.FieldRole)
        lw = label.widget() if label is not None else None
        fw = field.widget() if field is not None else None
        k = key_of(fw)
        if isinstance(lw, QLabel) and k is not None:
            attach(lw, k)


def decorative(w: QWidget) -> None:
    """Jawne „ten element nie potrzebuje opisu” (np. odstęp, separator). Używać oszczędnie."""
    w.setProperty(DECORATIVE_PROP, True)


# --- rozstrzyganie klucza ------------------------------------------------------------------------
def _key_for(w: QWidget | None, global_pos: QPoint | None) -> str | None:
    while w is not None:
        if isinstance(w, QTabBar):
            idx = (
                w.tabAt(w.mapFromGlobal(global_pos)) if global_pos is not None else w.currentIndex()
            )
            d = w.tabData(idx) if idx >= 0 else None
            if isinstance(d, str) and d:
                return d
        elif isinstance(w, QHeaderView) and global_pos is not None:
            k = _header_key(w, w.viewport().mapFromGlobal(global_pos))
            if k is not None:
                return k
        elif isinstance(w, (QMenu, QMenuBar)):
            a = w.actionAt(w.mapFromGlobal(global_pos)) if global_pos is not None else None
            if a is None:
                a = w.activeAction()
            k = _action_key(a)
            if k is not None:
                return k
        elif isinstance(w, QToolButton) and w.defaultAction() is not None:
            k = key_of(w.defaultAction())
            if k is not None:
                return k
        k = key_of(w)
        if k is not None:
            return k
        w = w.parentWidget()
    return None


def _action_key(a: QAction | None) -> str | None:
    """Klucz akcji; dla pozycji otwierającej podmenu — klucz samego podmenu."""
    if a is None:
        return None
    k = key_of(a)
    sub = a.menu()
    if k is None and isinstance(sub, QMenu):
        k = key_of(sub.menuAction()) or key_of(sub)
    return k


def key_at(global_pos: QPoint) -> str | None:
    """Klucz elementu pod punktem ekranu (zakładka, sekcja nagłówka, akcja, widżet albo przodek)."""
    return _key_for(QApplication.widgetAt(global_pos), global_pos)


def key_for_focus() -> str | None:
    return _key_for(QApplication.focusWidget(), None)


# --- pokrycie ------------------------------------------------------------------------------------
def _needs_key(w: QWidget) -> bool:
    if isinstance(w, QScrollBar):
        return False
    if isinstance(w, QLabel):
        return bool(w.text().strip())
    if isinstance(
        w,
        (
            QAbstractButton,
            QComboBox,
            QLineEdit,
            QAbstractSlider,
            QAbstractItemView,
            QTextEdit,
            QPlainTextEdit,
        ),
    ):
        return True
    # własne, rysowane elementy obsługiwane klawiaturą/myszą (suwaki, wykresy)
    return w.focusPolicy() != Qt.FocusPolicy.NoFocus and type(w).__module__.startswith(
        "algopalette."
    )


def _describe(w: QWidget) -> str:
    text = ""
    for attr in ("text", "placeholderText", "currentText"):
        f = getattr(w, attr, None)
        if callable(f):
            try:
                text = str(f())
            except TypeError:
                continue
            if text:
                break
    chain = []
    p = w.parentWidget()
    while p is not None and len(chain) < 3:
        chain.append(type(p).__name__)
        p = p.parentWidget()
    return f"{type(w).__name__} {text[:40]!r} w {'/'.join(chain)}"


def uncovered(root: QWidget, skip: Sequence[QWidget] = ()) -> list[str]:
    """Elementy wymagające opisu, które go nie mają (puste = pełne pokrycie). ``skip``: poddrzewa
    sprawdzane osobno (np. zakładki w teście samego okna)."""
    out: list[str] = []
    skipped = set(map(id, skip))
    for w in [root, *root.findChildren(QWidget)]:
        if w.objectName() == PANEL_NAME or w.objectName().startswith("qt_") or id(w) in skipped:
            continue
        anc, skip_w = w.parentWidget(), False
        while anc is not None:
            if isinstance(anc, _OPAQUE) or anc.objectName() == PANEL_NAME or id(anc) in skipped:
                skip_w = True
                break
            if anc is root:
                break
            anc = anc.parentWidget()
        if skip_w or w.property(DECORATIVE_PROP) or not _needs_key(w):
            continue
        if isinstance(w, QToolButton) and w.defaultAction() is not None:
            if key_of(w.defaultAction()) is None:
                out.append(_describe(w))
            continue
        if key_of(w) is None:
            out.append(_describe(w))
        if isinstance(w, QAbstractItemView):
            header = _header_of(w, False)
            if header is not None and not header.isHidden():
                for col in range(header.count()):
                    if not header.isSectionHidden(col) and _section_key(w, False, col) is None:
                        out.append(f"{_describe(w)} — kolumna {col}")
    return out


# --- styl: szybkie podpowiedzi ------------------------------------------------------------------
class _TooltipStyle(QProxyStyle):
    def styleHint(self, hint, option=None, widget=None, returnData=None) -> int:
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return TOOLTIP_DELAY_MS
        return super().styleHint(hint, option, widget, returnData)


_style_ref: list[QProxyStyle] = []


def install_tooltip_style(app: QApplication) -> None:
    """Styl Fusion z podpowiedziami po ``TOOLTIP_DELAY_MS`` (domyślnie Qt ~700 ms)."""
    base = QStyleFactory.create("Fusion")
    style = _TooltipStyle(base) if base is not None else _TooltipStyle()
    _style_ref[:] = [style]
    app.setStyle(style)


# --- wyszukiwanie --------------------------------------------------------------------------------
def normalize(text: str) -> str:
    """Bez polskich znaków i wielkości liter: „Źródło” → „zrodlo”."""
    t = text.replace("ł", "l").replace("Ł", "L")
    t = unicodedata.normalize("NFKD", t)
    return "".join(ch for ch in t if not unicodedata.combining(ch)).casefold()


_MD = re.compile(r"\(help:[^)]*\)|[*`#|]")


def search(text: str) -> list[str]:
    """Klucze tematów zawierających wszystkie słowa zapytania; trafienia w tytule najpierw."""
    words = normalize(text).split()
    if not words:
        return []
    title_hits, other = [], []
    for key, t in TOPICS.items():
        title = normalize(t.title)
        hay = " ".join((title, normalize(t.short), normalize(_MD.sub(" ", t.body))))
        if all(w in hay for w in words):
            (title_hits if all(w in title for w in words) else other).append(key)
    return title_hits + other


# --- panel ---------------------------------------------------------------------------------------
class HelpPanel(QDockWidget):
    """Panel Pomocy przypięty z prawej: wstecz/dalej, wyszukiwarka, spis tematów, treść."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Pomoc", parent)
        self.setObjectName(PANEL_NAME)
        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.current_key: str | None = None
        self._history: list[str | None] = []
        self._pos = -1

        body = QWidget()
        lay = vbox(body, margins=6, spacing=4)
        self.back = QToolButton()
        self.back.setText("◀")
        self.back.setToolTip("Wstecz")
        self.back.clicked.connect(self.go_back)
        self.forward = QToolButton()
        self.forward.setText("▶")
        self.forward.setToolTip("Dalej")
        self.forward.clicked.connect(self.go_forward)
        self.home = QToolButton()
        self.home.setText("Spis treści")
        self.home.clicked.connect(self.show_index)
        self.query = QLineEdit()
        self.query.setPlaceholderText("Szukaj w pomocy…")
        self.query.setClearButtonEnabled(True)
        self.query.textChanged.connect(self._filter)
        lay.addWidget(hbox(self.back, self.forward, self.home, self.query, stretch=False))

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemActivated.connect(self._pick)
        self.tree.itemClicked.connect(self._pick)
        self.text = QTextBrowser()
        self.text.setOpenLinks(False)
        self.text.anchorClicked.connect(self._link)
        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.tree)
        split.addWidget(self.text)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 3)
        split.setSizes([200, 600])
        lay.addWidget(split, 1)
        self.setWidget(body)
        self._build_tree()
        self.show_index()
        self._history, self._pos = [None], 0
        self._update_nav()

    # spis tematów
    def _build_tree(self) -> None:
        self.tree.clear()
        self._items: dict[str, QTreeWidgetItem] = {}
        groups: dict[str, QTreeWidgetItem] = {}
        for g in GROUPS:
            gi = QTreeWidgetItem([g])
            f = gi.font(0)
            f.setBold(True)
            gi.setFont(0, f)
            gi.setFlags(Qt.ItemFlag.ItemIsEnabled)
            groups[g] = gi
        for key, t in TOPICS.items():
            it = QTreeWidgetItem([t.title])
            it.setData(0, HELP_ROLE, key)
            it.setToolTip(0, t.short)
            groups[t.group].addChild(it)
            self._items[key] = it
        for g in GROUPS:
            if groups[g].childCount():
                self.tree.addTopLevelItem(groups[g])
        self.tree.collapseAll()

    def _filter(self, text: str) -> None:
        hits = set(search(text)) if text.strip() else None
        for i in range(self.tree.topLevelItemCount()):
            g = self.tree.topLevelItem(i)
            if g is None:
                continue
            visible = 0
            for j in range(g.childCount()):
                ch = g.child(j)
                if ch is None:
                    continue
                show = hits is None or ch.data(0, HELP_ROLE) in hits
                ch.setHidden(not show)
                visible += show
            g.setHidden(visible == 0)
            g.setExpanded(hits is not None and visible > 0)
        if hits is not None:
            self._render_results(text, search(text))

    def search(self, text: str) -> list[str]:
        return search(text)

    def _pick(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        key = item.data(0, HELP_ROLE)
        if isinstance(key, str):
            self.show_topic(key)
        else:
            item.setExpanded(not item.isExpanded())

    def _link(self, url: QUrl) -> None:
        if url.scheme() == "help":
            self.show_topic(url.path())
        elif url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)

    # treść
    def _render(self, key: str | None) -> None:
        self.current_key = key
        if key is None:
            lines = [
                "# Pomoc AlgoPalette",
                "",
                "Najedź kursorem na element okna i wciśnij **F1**, "
                "żeby przeczytać o nim więcej. [Jak korzystać z pomocy](help:general.help).",
            ]
            for g in GROUPS:
                items = [(k, t) for k, t in TOPICS.items() if t.group == g]
                if items:
                    lines += ["", f"### {g}", ""]
                    lines += [f"- [{t.title}](help:{k})" for k, t in items]
            self.text.setMarkdown("\n".join(lines))
            self.tree.clearSelection()
            self.tree.setCurrentIndex(QModelIndex())
            return
        t = TOPICS[key]
        self.text.setMarkdown(f"## {t.title}\n\n*{t.short}*\n\n{t.body}\n")
        it = self._items.get(key)
        if it is not None:
            parent = it.parent()
            if parent is not None:
                parent.setExpanded(True)
            self.tree.setCurrentItem(it)
            self.tree.scrollToItem(it)

    def _render_results(self, text: str, keys: list[str]) -> None:
        if not keys:
            self.text.setMarkdown(f"Nic nie znaleziono dla „{text}”.")
            return
        lines = [f"### Wyniki dla „{text}”", ""]
        lines += [f"- [{TOPICS[k].title}](help:{k}) — {TOPICS[k].short}" for k in keys]
        self.text.setMarkdown("\n".join(lines))

    def _go(self, key: str | None) -> None:
        if self._history and self._history[self._pos] == key and self.current_key == key:
            return
        del self._history[self._pos + 1 :]
        self._history.append(key)
        self._pos = len(self._history) - 1
        self._render(key)
        self._update_nav()

    def show_topic(self, key: str) -> None:
        _check(key)
        self._go(key)

    def show_index(self) -> None:
        self._go(None)

    def go_back(self) -> None:
        if self._pos > 0:
            self._pos -= 1
            self._render(self._history[self._pos])
            self._update_nav()

    def go_forward(self) -> None:
        if self._pos < len(self._history) - 1:
            self._pos += 1
            self._render(self._history[self._pos])
            self._update_nav()

    def _update_nav(self) -> None:
        self.back.setEnabled(self._pos > 0)
        self.forward.setEnabled(self._pos < len(self._history) - 1)


# --- sterowanie ----------------------------------------------------------------------------------
class HelpController(QObject):
    """F1, Shift+F1, akcje menu Pomoc i F1 wewnątrz otwartych menu."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.panel = HelpPanel(window)
        window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.panel)
        self.panel.hide()
        self.panel.resize(380, self.panel.height())
        self.click_mode = False
        self._swallow_release = False

        def act(text: str, slot, shortcut: str | None = None) -> QAction:
            a = QAction(text, window)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
                a.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            a.triggered.connect(slot)
            window.addAction(a)
            return a

        self.act_help = act("Pomoc", self.help_here, "F1")
        self.act_click = act(
            "Kliknij element, żeby zobaczyć pomoc…", self.enter_click_mode, "Shift+F1"
        )
        self.act_start = act("Pierwsze kroki", lambda: self.open_topic("general.start"))
        self.act_shortcuts = act("Skróty klawiszowe", lambda: self.open_topic("general.shortcuts"))
        self.act_index = act("Spis treści pomocy", self.open_index)
        self.panel.setProperty(HELP_PROP, "general.help")  # F1 w panelu → jak korzystać z pomocy

    def actions(self) -> list[QAction]:
        return [self.act_help, self.act_click, self.act_start, self.act_shortcuts, self.act_index]

    def watch_menus(self) -> None:
        """F1 w otwartym menu → temat podświetlonej akcji (wołać po zbudowaniu menu)."""
        for m in self.window.findChildren(QMenu):
            m.setToolTipsVisible(True)
            m.installEventFilter(self)

    # otwieranie
    def _show_panel(self) -> None:
        self.panel.show()
        self.panel.raise_()

    def open_topic(self, key: str) -> None:
        self.panel.show_topic(key)
        self._show_panel()

    def open_index(self) -> None:
        self.panel.show_index()
        self._show_panel()

    def _in_app_window(self, w: QWidget | None) -> bool:
        return w is not None and w.window() in (self.window, self.panel)

    def help_here(self) -> None:
        pos = QCursor.pos()
        under = QApplication.widgetAt(pos)
        key = key_at(pos) if self._in_app_window(under) else None
        if key is None:
            key = key_for_focus()
        visible = not self.panel.isHidden()
        if visible and self.panel.current_key == key:
            self.panel.hide()
            return
        if key is None:
            self.open_index()
        else:
            self.open_topic(key)

    # tryb „kliknij element”
    def enter_click_mode(self) -> None:
        if self.click_mode:
            return
        self.click_mode = True
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self.window.statusBar().showMessage(
            "Kliknij element, żeby zobaczyć jego pomoc (Esc — anuluj)", 8000
        )

    def leave_click_mode(self) -> None:
        if not self.click_mode:
            return
        self.click_mode = False
        QApplication.restoreOverrideCursor()
        app = QApplication.instance()
        if app is not None and not self._swallow_release:
            app.removeEventFilter(self)
        self.window.statusBar().clearMessage()

    def eventFilter(self, obj: QObject, ev: QEvent) -> bool:
        t = ev.type()
        if self._swallow_release and t in (
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseButtonDblClick,
        ):
            self._swallow_release = False
            app = QApplication.instance()
            if app is not None and not self.click_mode:
                app.removeEventFilter(self)
            return True
        if self.click_mode:
            if t == QEvent.Type.MouseButtonPress and isinstance(ev, QMouseEvent):
                gp = ev.globalPosition().toPoint()
                left = ev.button() == Qt.MouseButton.LeftButton
                self._swallow_release = True
                self.leave_click_mode()
                if left:
                    key = key_at(gp)
                    if key is None:
                        self.open_index()
                    else:
                        self.open_topic(key)
                return True
            if isinstance(ev, QKeyEvent) and t == QEvent.Type.KeyPress:
                if ev.key() == Qt.Key.Key_Escape:
                    self.leave_click_mode()
                return True  # w trybie wskazywania klawisze nie zmieniają palety
            return False
        if not (isinstance(obj, QMenu) and isinstance(ev, QKeyEvent) and ev.key() == Qt.Key.Key_F1):
            return False
        if t == QEvent.Type.ShortcutOverride:
            ev.accept()  # F1 w menu ma trafić do menu (temat akcji), nie do skrótu okna
            return True
        if t != QEvent.Type.KeyPress:
            return False
        # wyszarzone pozycje nie dostają podświetlenia — wtedy pozycja pod kursorem
        key = _action_key(obj.activeAction() or obj.actionAt(obj.mapFromGlobal(QCursor.pos())))
        popup = QApplication.activePopupWidget()
        while popup is not None:
            popup.close()
            popup = QApplication.activePopupWidget()
        if key is None:
            self.open_index()
        else:
            self.open_topic(key)
        return True


def install(window: QMainWindow) -> HelpController:
    return HelpController(window)
