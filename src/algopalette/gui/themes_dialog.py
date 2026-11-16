"""Okno „Motywy z sieci”: lista motywów z kilku źródeł, filtry, duży podgląd, import (spec §8).

Pobieranie idzie w wątkach ``QThreadPool``; każde zadanie ma własną flagę anulowania. Katalog
źródła plikowego zapamiętujemy po źródle, więc spóźniony wynik niczego nie psuje (lista pokazuje
tylko źródła bieżącego wyboru). Strony Lospec mają numer generacji — wynik starszego wyszukiwania
jest odrzucany.
"""

from __future__ import annotations

import html
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

import httpx
from PySide6.QtCore import QEvent, QModelIndex, QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from algopalette.gui import help, theme
from algopalette.gui.theme_preview import THEME_ROLE, SwatchDelegate, ThemePreview
from algopalette.themes import catalog, net
from algopalette.themes.model import (
    FULL_CATALOG_SOURCES,
    SOURCES,
    BgFilter,
    SourceId,
    Theme,
    ThemeError,
    filter_themes,
    resolve,
)

if TYPE_CHECKING:
    from algopalette.gui.app import MainWindow

KEEP_SETTINGS_KEY = "themes_keep_settings"
PAGE_SIZE = 50
LOSPEC_DEBOUNCE_MS = 400
LOCAL_DEBOUNCE_MS = 150
CANCELLED = "pobieranie przerwane — kliknij „Odśwież katalogi”"
LOSPEC_HINT = (
    "Lospec szuka po tagach (np. warm, gameboy, pastel); puste pole = najczęściej pobierane."
)

Job = Callable[[Callable[[], bool], Callable[[int, int | None], None]], catalog.CatalogResult]


class _Signals(QObject):
    progress = Signal(int, object)
    done = Signal(object)
    failed = Signal(str)


class _Worker(QRunnable):
    """Jedno pobranie w wątku puli; wynik i błąd wracają sygnałami do wątku okna."""

    def __init__(self, job: Job) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.job = job
        self.signals = _Signals()
        self.cancel = threading.Event()

    def run(self) -> None:
        try:
            res = self.job(
                self.cancel.is_set, lambda n, total: self.signals.progress.emit(n, total)
            )
        except (net.FetchError, ThemeError) as e:
            self.signals.failed.emit(str(e))
        except Exception as e:  # nic nie może wywrócić wątku puli
            self.signals.failed.emit(f"Nieoczekiwany błąd: {e}")
        else:
            self.signals.done.emit(res)


def _date(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


class ThemesDialog(QDialog):
    def __init__(
        self,
        win: MainWindow,
        *,
        client_factory: Callable[[], httpx.Client] = net.make_client,
    ) -> None:
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Motywy z sieci")
        self.setModal(False)
        self.resize(1000, 640)
        self._client = client_factory()
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(4)
        self._jobs: set[_Worker] = set()
        self._loading: dict[str, _Worker] = {}  # źródło albo "lospec" → trwające pobranie
        self._catalogs: dict[SourceId, catalog.CatalogResult] = {}
        self._errors: dict[str, str] = {}
        self._lospec: list[Theme] = []
        self._lospec_total: int | None = None
        self._lospec_page = -1
        self._lospec_gen = 0
        self._lospec_tag = ""
        self._lospec_done = False  # ostatnia strona serwera już pobrana
        self._lospec_skipped = 0
        self._lospec_res: catalog.CatalogResult | None = None
        self._filtered: list[Theme] = []
        self._shown = 0
        self._build()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._query_changed)
        # Ctrl+Z / Ctrl+Y działają także w tym oknie (komunikat importu o nie prosi)
        self.addAction(win.act_undo)
        self.addAction(win.act_redo)
        self._source_changed()

    # --- budowa ------------------------------------------------------------------------------
    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Szukaj nazwy lub autora…")
        self.search.textChanged.connect(self._schedule_query)
        self.source = QComboBox()
        self.source.addItem("wszystkie", "all")
        for sid, label in SOURCES.items():
            self.source.addItem(label, sid)
        self.source.currentIndexChanged.connect(self._source_changed)
        self.bg_filter = QComboBox()
        for data, label in (("any", "dowolne"), ("dark", "ciemne"), ("light", "jasne")):
            self.bg_filter.addItem(label, data)
        self.bg_filter.currentIndexChanged.connect(self._bg_changed)
        self.search_label = QLabel("Szukaj")
        self.source_label = QLabel("Źródło")
        self.bg_label = QLabel("Tło")
        top.addWidget(self.search_label)
        top.addWidget(self.search, 1)
        top.addWidget(self.source_label)
        top.addWidget(self.source)
        top.addWidget(self.bg_label)
        top.addWidget(self.bg_filter)
        lay.addLayout(top)
        self.hint = QLabel(LOSPEC_HINT)
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.model = QStandardItemModel(self)
        self.view = QListView()
        self.view.setModel(self.model)
        self.view.setItemDelegate(SwatchDelegate(self.view))
        self.view.setUniformItemSizes(True)
        self.view.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.view.selectionModel().currentChanged.connect(self._current_changed)
        self.view.doubleClicked.connect(lambda _i: self.load_current())
        self.view.installEventFilter(self)
        ll.addWidget(self.view, 1)
        self.more = QPushButton("Więcej")
        self.more.clicked.connect(self._more)
        ll.addWidget(self.more)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.preview = ThemePreview()
        rl.addWidget(self.preview, 1)
        info = QHBoxLayout()
        self.link = QLabel()
        self.link.setOpenExternalLinks(True)
        self.link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.link.setWordWrap(True)
        info.addWidget(self.link, 1)
        self.light_bg = QCheckBox("Tło jasne")
        self.light_bg.toggled.connect(lambda _on: self._update_preview())
        info.addWidget(self.light_bg)
        rl.addLayout(info)
        split.addWidget(right)
        split.setSizes([360, 640])
        lay.addWidget(split, 1)

        state = QHBoxLayout()
        self.status = QLabel()
        self.status.setWordWrap(True)
        state.addWidget(self.status, 1)
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(220)
        self.progress.setTextVisible(False)
        state.addWidget(self.progress)
        self.cancel = QPushButton("Anuluj")
        self.cancel.clicked.connect(self.cancel_loading)
        state.addWidget(self.cancel)
        lay.addLayout(state)

        bottom = QHBoxLayout()
        self.keep_settings = QCheckBox("Nie zmieniaj ustawień palety")
        self.keep_settings.setChecked(theme.read_setting(KEEP_SETTINGS_KEY, False) is True)
        self.keep_settings.toggled.connect(self._keep_toggled)
        bottom.addWidget(self.keep_settings)
        bottom.addStretch(1)
        self.refresh = QPushButton("Odśwież katalogi")
        self.refresh.clicked.connect(self.refresh_catalogs)
        bottom.addWidget(self.refresh)
        self.load = QPushButton("Wczytaj")
        self.load.clicked.connect(self.load_current)
        bottom.addWidget(self.load)
        for b in (self.more, self.cancel, self.refresh, self.load):
            b.setAutoDefault(False)
        lay.addLayout(bottom)
        self._attach_help(split, left, right)

    def _attach_help(self, *containers: QWidget) -> None:
        help.attach(self, "themes.window")
        for w in containers:
            help.attach(w, "themes.window")
        for w, key in (
            (self.search, "themes.search"),
            (self.search_label, "themes.search"),
            (self.hint, "themes.search"),
            (self.source, "themes.source"),
            (self.source_label, "themes.source"),
            (self.bg_filter, "themes.bg"),
            (self.bg_label, "themes.bg"),
            (self.view, "themes.list"),
            (self.more, "themes.more"),
            (self.preview, "themes.preview"),
            (self.light_bg, "themes.light_bg"),
            (self.link, "themes.link"),
            (self.status, "themes.status"),
            (self.progress, "themes.status"),
            (self.cancel, "themes.status"),
            (self.keep_settings, "themes.keep_settings"),
            (self.refresh, "themes.refresh"),
            (self.load, "themes.load"),
        ):
            help.attach(w, key, children=True)
        help.attach(self.view.viewport(), "themes.list")

    # --- stan wyboru -------------------------------------------------------------------------
    def selected_source(self) -> str:
        return cast(str, self.source.currentData())

    def _is_lospec(self) -> bool:
        return self.selected_source() == "lospec"

    def _file_sources(self) -> tuple[SourceId, ...]:
        s = self.selected_source()
        if s == "all":
            return FULL_CATALOG_SOURCES
        if s == "lospec":
            return ()
        return (cast(SourceId, s),)

    def _bg(self) -> BgFilter:
        return cast(BgFilter, self.bg_filter.currentData())

    def current_theme(self) -> Theme | None:
        t = self.view.currentIndex().data(THEME_ROLE)
        return t if isinstance(t, Theme) else None

    # --- zdarzenia filtrów -------------------------------------------------------------------
    def _source_changed(self, *_args: Any) -> None:
        lospec = self._is_lospec()
        self.hint.setVisible(lospec)
        self.light_bg.setVisible(lospec)
        self._timer.stop()
        if lospec:
            self._start_lospec(self.search.text(), refresh=False)
        else:
            self._ensure_loaded(retry_errors=False)
        self._rebuild()

    def _ensure_loaded(self, *, retry_errors: bool) -> None:
        """Startuje brakujące pobrania; ``retry_errors``: także przerwane/błędne."""
        if self._is_lospec():
            idle = self._lospec_page == -1 and "lospec" not in self._loading
            if idle and (retry_errors or "lospec" not in self._errors):
                self._start_lospec(self.search.text(), refresh=False)
            return
        for src in self._file_sources():
            if src in self._catalogs or src in self._loading:
                continue
            if retry_errors or src not in self._errors:
                self._start_catalog(src, refresh=False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._ensure_loaded(retry_errors=True)

    def _schedule_query(self, *_args: Any) -> None:
        self._timer.start(LOSPEC_DEBOUNCE_MS if self._is_lospec() else LOCAL_DEBOUNCE_MS)

    def _query_changed(self) -> None:
        if self._is_lospec():
            if catalog.lospec_tag(self.search.text()) != self._lospec_tag:
                self._start_lospec(self.search.text(), refresh=False)
        else:
            self._rebuild()

    def _bg_changed(self, *_args: Any) -> None:
        if self._is_lospec():
            self._update_preview()
            self.view.viewport().update()
        else:
            self._rebuild()

    def _keep_toggled(self, on: bool) -> None:
        try:
            theme.write_setting(KEEP_SETTINGS_KEY, on)
        except OSError as e:
            self.win.notify(f"Nie udało się zapamiętać ustawienia: {e.strerror or e}", error=True)

    # --- pobieranie --------------------------------------------------------------------------
    def _run(self, key: str, job: Job, done: Callable[[catalog.CatalogResult], None]) -> None:
        w = _Worker(job)
        self._jobs.add(w)
        self._loading[key] = w

        def settle() -> None:
            # przed przebudową listy (wiersze źródła w toku są wyłączone, nie do zaznaczenia)
            self._jobs.discard(w)
            if self._loading.get(key) is w:
                del self._loading[key]

        def finish() -> None:
            self._refresh_enabled()
            self._update_status()

        def ok(res: object) -> None:
            settle()
            if not w.cancel.is_set():
                done(cast(catalog.CatalogResult, res))
            finish()

        def fail(msg: str) -> None:
            settle()
            if not w.cancel.is_set():
                self._errors[key] = msg
                self._rebuild(keep_shown=True)
            finish()

        w.signals.done.connect(ok)
        w.signals.failed.connect(fail)
        w.signals.progress.connect(self._progress)
        self._errors.pop(key, None)
        self._pool.start(w)
        self._refresh_enabled()
        self._update_status()

    def _start_catalog(self, src: SourceId, *, refresh: bool) -> None:
        client = self._client

        def job(cancelled, on_progress) -> catalog.CatalogResult:
            return catalog.load_catalog(
                src, client, refresh=refresh, on_progress=on_progress, cancelled=cancelled
            )

        def done(res: catalog.CatalogResult) -> None:
            self._catalogs[src] = res
            if src in self._file_sources():
                self._rebuild(keep_shown=True)

        self._run(src, job, done)

    def _start_lospec(self, text: str, *, refresh: bool, page: int = 0) -> None:
        if page == 0:
            self._lospec_gen += 1
            self._lospec = []
            self._lospec_total = None
            self._lospec_page = -1
            self._lospec_tag = catalog.lospec_tag(text)
            self._lospec_done = False
            self._lospec_skipped = 0
            self._lospec_res = None
            self._errors.pop("lospec", None)
            old = self._loading.get("lospec")
            if old is not None:
                old.cancel.set()
        gen, tag, client = self._lospec_gen, self._lospec_tag, self._client

        def job(cancelled, _on_progress) -> catalog.CatalogResult:
            return catalog.lospec_page(tag, page, client, refresh=refresh, cancelled=cancelled)

        def done(res: catalog.CatalogResult) -> None:
            if gen != self._lospec_gen:
                return  # wynik starszego wyszukiwania
            seen = {t.id for t in self._lospec}
            new = [t for t in res.themes if t.id not in seen]
            self._lospec.extend(new)
            self._lospec_total = res.total
            self._lospec_page = page
            self._lospec_skipped += res.skipped
            self._lospec_res = res
            # koniec: strony serwera wyczerpane albo pusta strona (totalCount liczy też palety,
            # które parser pomija, więc liczba sparsowanych nigdy go nie dogoni)
            pages_done = res.total is None or (page + 1) * catalog.LOSPEC_PAGE_SIZE >= res.total
            self._lospec_done = pages_done or (not res.themes and not res.skipped)
            if self._is_lospec():
                if page == 0:
                    self._rebuild()
                else:
                    self._append(new)

        self._run("lospec", job, done)
        if page == 0:
            self._rebuild()

    def _progress(self, received: int, total: object) -> None:
        if isinstance(total, int) and total > 0 and len(self._loading) == 1:
            self.progress.setRange(0, total)
            self.progress.setValue(min(received, total))
        else:
            self.progress.setRange(0, 0)

    def cancel_loading(self) -> None:
        for key, w in list(self._loading.items()):
            w.cancel.set()
            self._errors[key] = CANCELLED
        self._loading.clear()
        self._rebuild(keep_shown=True)

    def refresh_catalogs(self) -> None:
        """Wszystkie katalogi plikowe od nowa + strony Lospec wyczyszczone (spec §9)."""
        catalog.refresh_all()
        for src in FULL_CATALOG_SOURCES:
            old = self._loading.get(src)
            if old is not None:
                old.cancel.set()
            self._start_catalog(src, refresh=True)
        if self._is_lospec():
            self._start_lospec(self.search.text(), refresh=True)

    def shutdown(self) -> None:
        """Przerywa pobierania (zamknięcie okna albo programu); nie czeka na wątki."""
        for w in list(self._jobs):
            w.cancel.set()
        self._loading.clear()

    def closeEvent(self, event) -> None:
        self.shutdown()
        self._update_status()
        super().closeEvent(event)

    # --- lista -------------------------------------------------------------------------------
    def _themes(self) -> list[Theme]:
        if self._is_lospec():
            return list(self._lospec)
        pool: list[Theme] = []
        for src in self._file_sources():
            res = self._catalogs.get(src)
            if res is not None:
                pool.extend(res.themes)
        return filter_themes(pool, self.search.text(), self._bg())

    def _rebuild(self, *, keep_shown: bool = False) -> None:
        """Lista od nowa. ``keep_shown``: nie zwijaj dołożonych porcji i zostaw zaznaczony motyw."""
        current = self.current_theme()
        self._filtered = self._themes()
        n = len(self._filtered)
        if self._is_lospec():
            shown = n
        elif keep_shown:
            shown = max(self._shown, PAGE_SIZE)
            if current is not None:
                key = (current.source, current.id)
                for i, t in enumerate(self._filtered):
                    if (t.source, t.id) == key:
                        shown = max(shown, i + 1)
                        break
        else:
            shown = PAGE_SIZE
        self._shown = min(shown, n)
        self._fill(current)
        self._update_status()

    def _item(self, t: Theme) -> QStandardItem:
        item = QStandardItem(t.name)
        item.setData(t, THEME_ROLE)
        item.setEnabled(self._source_key(t) not in self._loading)
        return item

    def _source_key(self, t: Theme) -> str:
        return "lospec" if t.source == "lospec" else t.source

    def _refresh_enabled(self) -> None:
        """Wiersze źródła, które się właśnie pobiera, są wyszarzone (spec §8)."""
        for i in range(self.model.rowCount()):
            item = self.model.item(i)
            t = item.data(THEME_ROLE)
            if isinstance(t, Theme):
                on = self._source_key(t) not in self._loading
                if item.isEnabled() != on:
                    item.setEnabled(on)

    def _append(self, themes: list[Theme]) -> None:
        """Dokłada wiersze bez przebudowy (widok się nie przewija, zaznaczenie zostaje)."""
        self._filtered = self._themes()
        had_rows = self.model.rowCount() > 0
        for t in themes:
            self.model.appendRow(self._item(t))
        self._shown = self.model.rowCount()
        if not had_rows and self.model.rowCount():
            self.view.setCurrentIndex(self.model.index(0, 0))
        self._update_more()
        self._update_status()

    def _fill(self, keep: Theme | None) -> None:
        self.model.clear()
        row_keep = -1
        for i, t in enumerate(self._filtered[: self._shown]):
            self.model.appendRow(self._item(t))
            if keep is not None and (t.source, t.id) == (keep.source, keep.id):
                row_keep = i
        if row_keep >= 0:
            self.view.setCurrentIndex(self.model.index(row_keep, 0))
        elif self.model.rowCount():
            self.view.setCurrentIndex(self.model.index(0, 0))
        else:
            self._update_preview()
        self._update_more()

    def _more(self) -> None:
        if self._is_lospec():
            if "lospec" not in self._loading:
                self._start_lospec(self._lospec_tag, refresh=False, page=self._lospec_page + 1)
            return
        start = self._shown
        end = min(start + PAGE_SIZE, len(self._filtered))
        for t in self._filtered[start:end]:
            self.model.appendRow(self._item(t))
        self._shown = end
        self._update_more()
        self._update_status()

    def _update_more(self) -> None:
        if self._is_lospec():
            visible = self._lospec_page >= 0 and not self._lospec_done
        else:
            visible = self._shown < len(self._filtered)
        self.more.setVisible(visible)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.view and event.type() == QEvent.Type.KeyPress:
            key = cast(QKeyEvent, event).key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.load_current()
                return True
        return super().eventFilter(obj, event)

    # --- podgląd i import ----------------------------------------------------------------------
    def _current_changed(self, _cur: QModelIndex, _prev: QModelIndex) -> None:
        self._update_preview()

    def _light(self) -> bool:
        return self._bg() == "light" or self.light_bg.isChecked()

    def _resolved(self):
        t = self.current_theme()
        if t is None:
            return None, None, "Brak motywów do pokazania."
        try:
            p = resolve(t, light_bg=self._light(), metric=self.win.session.globals.contrast_metric)
        except ThemeError as e:
            return t, None, str(e)
        return t, p, ""

    def _update_preview(self) -> None:
        t, p, msg = self._resolved()
        self.preview.set_palette(p, message=msg)
        self.load.setEnabled(p is not None)
        if t is None:
            self.link.setText("")
            return
        parts = [f"<b>{html.escape(t.name)}</b>", html.escape(SOURCES[t.source])]
        if t.author:
            parts.append("autor: " + html.escape(t.author))
        if t.license:
            parts.append(html.escape(t.license))
        if t.url:
            parts.append(f'<a href="{html.escape(t.url, quote=True)}">strona źródła</a>')
        self.link.setText(" · ".join(parts))

    def load_current(self) -> None:
        t, p, _msg = self._resolved()
        if t is None or p is None:
            return
        self.win.import_theme(t, p, keep_settings=self.keep_settings.isChecked())

    # --- pasek stanu okna ------------------------------------------------------------------------
    def _update_status(self) -> None:
        busy = bool(self._loading)
        self.progress.setVisible(busy)
        self.cancel.setVisible(busy)
        if busy and self.progress.maximum() != 0 and len(self._loading) > 1:
            self.progress.setRange(0, 0)
        keys: tuple[str, ...] = ("lospec",) if self._is_lospec() else self._file_sources()
        notes: list[str] = []
        errors = [
            f"{self._label(k)}: {self._errors[k].rstrip('.')}" for k in keys if k in self._errors
        ]
        for k in keys:
            res = self._lospec_res if k == "lospec" else self._catalogs.get(cast(SourceId, k))
            if res is None:
                continue
            if res.offline:
                notes.append(f"{self._label(k)}: katalog z {_date(res.fetched_at)} (offline)")
            if res.cache_error:
                notes.append(res.cache_error.rstrip(".") + ".")
            skipped = self._lospec_skipped if k == "lospec" else res.skipped
            if skipped:
                notes.append(
                    f"{self._label(k)}: pominięto {skipped} (za mało kolorów lub błędny zapis)"
                )
        loading = [self._label(k) for k in keys if k in self._loading]
        if loading:
            text = "Pobieranie katalogu: " + ", ".join(loading) + "…"
        elif errors and not self._filtered:
            text = (
                "Nie udało się pobrać katalogu "
                + "; ".join(errors)
                + ". Sprawdź połączenie i kliknij „Odśwież katalogi”."
            )
        else:
            shown = f"{min(self._shown, len(self._filtered))} z {len(self._filtered)}"
            if self._is_lospec() and self._lospec_total is not None:
                shown += f" (Lospec: {self._lospec_total} pasujących palet)"
            text = f"Motywy: {shown}."
            if errors:
                text += " Błędy: " + "; ".join(errors) + "."
        if notes:
            text += " " + " · ".join(notes)
        self.status.setText(text)
        bad = bool(errors) and not loading
        theme.mark_text(self.status, "hard" if bad else None)
        theme.mark_error(self.view, bad and not self._filtered)

    @staticmethod
    def _label(key: str) -> str:
        return SOURCES.get(cast(SourceId, key), key)
