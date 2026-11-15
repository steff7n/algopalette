"""Zakładka „Globalne”: nastroje, polaryzacja, metryki, układ odcieni, rozrzut jasności, daltonizm,
gamut, optymalizator, unikanie kolorów, domyślne warunki ról."""

from __future__ import annotations

import contextlib
import secrets
from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QWidget,
)

from algopalette.forms import (
    CONTRAST_GLOBAL,
    CVD,
    CVD_METHODS,
    DELTA_E,
    FITS,
    POLARITIES,
    SCHEMES,
)
from algopalette.globals_logic import change_delta_e, change_polarity_or_metric
from algopalette.gui import theme
from algopalette.gui.conditions import ConditionsEditor, combo
from algopalette.gui.widgets import (
    NumEdit,
    RangeSlider,
    ValueSlider,
    channel_gradient,
    clear_layout,
    form,
    hbox,
    hint,
    parse_finite,
    source_badge,
    vbox,
)
from algopalette.model import (
    OKLCH,
    Cond,
    CvdSettings,
    CvdType,
    DeltaEMethod,
    GlobalSettings,
    Interval,
)
from algopalette.moods import (
    BUILTIN,
    Mood,
    apply_mood,
    delete_user_mood,
    list_moods,
    save_user_mood,
)

if TYPE_CHECKING:
    from algopalette.gui.app import MainWindow

HUE_GRADIENT = channel_gradient(OKLCH(0.75, 0.13, 0.0), "h")


def group(title: str) -> tuple[QGroupBox, Any]:
    box = QGroupBox(title)
    lay = vbox(box, margins=10, spacing=6)
    return box, lay


class GlobalsTab(QScrollArea):
    def __init__(self, win: MainWindow) -> None:
        super().__init__()
        self.win = win
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        self._lay = vbox(body, margins=10, spacing=10)
        self.setWidget(body)
        self._shown = None
        self._role_tab = 2

    @property
    def g(self) -> GlobalSettings:
        return self.win.session.globals

    def refresh_from_session(self) -> None:
        """Przebudowa tylko, gdy sesja zmieniła się od ostatniego rysowania."""
        if self.win.session is not self._shown:
            self.rebuild()

    def _rebuild_later(self) -> None:
        QTimer.singleShot(0, self.rebuild)

    def rebuild(self) -> None:
        if hasattr(self, "role_tabs"):
            with contextlib.suppress(RuntimeError):  # zakładki ról już usunięte
                self._role_tab = self.role_tabs.currentIndex()
        scroll = self.verticalScrollBar().value()
        clear_layout(self._lay)
        s = self.win.session
        self._shown = s
        g = s.globals
        top = QWidget()
        cols = vbox(top, spacing=10)
        cols.addWidget(self._moods_box(s))
        row = hbox(self._metrics_box(g), self._optimizer_box(g), stretch=False, spacing=10)
        cols.addWidget(row)
        cols.addWidget(self._hues_box(g))
        row = hbox(self._spread_box(g), self._cvd_box(g), stretch=False, spacing=10)
        cols.addWidget(row)
        cols.addWidget(self._avoid_box(g))
        cols.addWidget(self._roles_box())
        self._lay.addWidget(top)
        self._lay.addStretch(1)
        QTimer.singleShot(0, lambda: self.verticalScrollBar().setValue(scroll))

    # --- sekcje -------------------------------------------------------------------------------
    def _moods_box(self, s) -> QGroupBox:
        box, lay = group("Nastrój")
        try:
            moods = list_moods()
        except ValueError as e:
            self.win.notify(str(e))
            moods = [Mood(n, d, True) for n, (d, _) in BUILTIN.items()]
        lay.addWidget(QLabel(f"bieżący: <b>{s.mood or '— (własne ustawienia)'}</b>"))
        self.mood = combo([(("★ " if m.builtin else "") + m.name, m.name) for m in moods], s.mood)
        for i, m in enumerate(moods):
            self.mood.setItemData(i, m.description or m.name, 3)  # 3 = ToolTipRole
        apply_btn = QPushButton("Zastosuj nastrój")
        apply_btn.clicked.connect(self._mood_apply)
        del_btn = QPushButton("Usuń własny")
        del_btn.clicked.connect(self._mood_delete)
        lay.addWidget(hbox(self.mood, apply_btn, del_btn))
        self.mood_name = QLineEdit()
        self.mood_name.setPlaceholderText("nazwa nowego nastroju")
        self.mood_name.setMinimumWidth(220)
        save_btn = QPushButton("Zapisz bieżące ustawienia jako nastrój")
        save_btn.clicked.connect(self._mood_save)
        lay.addWidget(hbox(self.mood_name, save_btn))
        lay.addWidget(
            hint(
                "Nastrój wypełnia ustawienia globalne gotowymi wartościami (★ = wbudowany). "
                "Wszystko, co ustawił, widać niżej i można zmienić."
            )
        )
        return box

    def _metrics_box(self, g: GlobalSettings) -> QGroupBox:
        box, lay = group("Polaryzacja i metryki")
        w, fl = form()
        pol = combo(POLARITIES, g.polarity)
        pol.currentIndexChanged.connect(
            lambda _: self._polarity_metric("polarity", pol.currentData())
        )
        fl.addRow("polaryzacja", pol)
        met = combo(CONTRAST_GLOBAL, g.contrast_metric)
        met.currentIndexChanged.connect(
            lambda _: self._polarity_metric("contrast_metric", met.currentData())
        )
        fl.addRow("kontrast", met)
        de = combo(DELTA_E, g.delta_e)
        de.currentIndexChanged.connect(lambda _: self._delta_e(de.currentData()))
        fl.addRow("ΔE", de)
        fit = combo(FITS, g.fit_method)
        fit.currentIndexChanged.connect(
            lambda _: (
                self._set(fit_method=fit.currentData())
                if fit.currentData() != self.g.fit_method
                else None
            )
        )
        fit.setToolTip("Sposób sprowadzania koloru spoza sRGB do gamutu")
        fl.addRow("gamut (fit)", fit)
        lay.addWidget(w)
        lay.addWidget(
            hint(
                "Zmiana polaryzacji/metryki przelicza domyślne zakresy ról; zmiana ΔE przelicza "
                "progi odległości."
            )
        )
        return box

    def _hues_box(self, g: GlobalSettings) -> QGroupBox:
        h = g.hue_scheme
        box, lay = group("Układ odcieni — cele dla akcentów bez własnego warunku odcienia")
        w, fl = form()
        kind = combo(SCHEMES, h.kind)
        kind.currentIndexChanged.connect(lambda _: self._scheme(kind=kind.currentData()))
        fl.addRow("rodzaj", kind)
        for key, label, lo, hi, wrap, grad in (
            ("rotation", "obrót °", 0, 360, True, HUE_GRADIENT),
            ("center", "środek °", 0, 360, True, HUE_GRADIENT),
            ("spread", "rozpiętość °", 0, 360, False, None),
            ("tol", "tolerancja ±°", 0, 90, False, None),
            ("jitter", "jitter ±°", 0, 45, False, None),
        ):
            sl = ValueSlider(
                getattr(h, key),
                minimum=lo,
                maximum=hi,
                step=1,
                fmt=".0f",
                wrap=wrap,
                gradient=grad,
            )
            sl.changed.connect(lambda v, key=key: self._scheme_value(key, v))
            fl.addRow(label, sl)
        custom = QLineEdit(", ".join(f"{x:g}" for x in h.custom))
        custom.setPlaceholderText("np. 30, 200, 120")
        custom.editingFinished.connect(lambda: self._custom(custom))
        fl.addRow("własne °", custom)
        hard = QCheckBox("twardy")
        hard.setChecked(h.hard)
        hard.toggled.connect(lambda on: self._scheme(hard=on))
        weight = NumEdit(h.weight, minimum=0.0, step=0.1, width=56)
        weight.committed.connect(lambda v: v is not None and self._scheme(weight=v))
        fl.addRow("", hbox(hard, QLabel("waga"), weight))
        lay.addWidget(w)
        return box

    def _spread_box(self, g: GlobalSettings) -> QGroupBox:
        sp = g.lightness_spread
        box, lay = group("Rozrzut jasności akcentów (max L − min L)")
        if sp is None:
            add = QPushButton("+ dodaj warunek rozrzutu")
            add.clicked.connect(
                lambda: self._set(
                    lightness_spread=Cond(Interval(0.15, None), hard=False), structural=True
                )
            )
            lay.addWidget(hbox(add))
            lay.addStretch(1)
            return box
        en = QCheckBox("włączony")
        en.setChecked(sp.enabled)
        en.toggled.connect(lambda on: self._spread_flag("enabled", on))
        hard = QCheckBox("twardy")
        hard.setChecked(sp.hard)
        hard.toggled.connect(lambda on: self._spread_flag("hard", on))
        rm = QPushButton("✕ usuń")
        rm.clicked.connect(lambda: self._set(lightness_spread=None, structural=True))
        lay.addWidget(hbox(en, hard, rm))
        rs = RangeSlider(
            sp.value.lo, sp.value.hi, minimum=0, maximum=1, step=0.01, fmt=".2f", allow_none=True
        )
        rs.changed.connect(self._spread)
        lay.addWidget(rs)
        lay.addStretch(1)
        return box

    def _cvd_box(self, g: GlobalSettings) -> QGroupBox:
        c = g.cvd
        box, lay = group("Daltonizm — symulacja dla warunku odróżnialności")
        checks = []
        for label, kind in CVD:
            cb = QCheckBox(label)
            cb.setChecked(kind in c.types)
            cb.toggled.connect(lambda on, kind=kind: self._cvd_type(kind, on))
            checks.append(cb)
        lay.addWidget(hbox(*checks))
        w, fl = form()
        method = combo(CVD_METHODS, c.method)
        method.currentIndexChanged.connect(
            lambda _: self._set(cvd=replace(self.g.cvd, method=method.currentData()))
        )
        fl.addRow("metoda", method)
        sev = ValueSlider(c.severity, minimum=0, maximum=1, step=0.05, fmt=".2f")
        sev.changed.connect(
            lambda v: (
                v is not None
                and self._set(cvd=replace(self.g.cvd, severity=float(v)), coalesce="g:cvd-severity")
            )
        )
        fl.addRow("nasilenie", sev)
        lay.addWidget(w)
        return box

    def _optimizer_box(self, g: GlobalSettings) -> QGroupBox:
        o = g.optimizer
        box, lay = group("Optymalizator")
        w, fl = form()

        def field(name: str, label: str, integer: bool, minimum: float, tip: str = "") -> NumEdit:
            e = NumEdit(
                getattr(o, name),
                integer=integer,
                minimum=minimum,
                width=96,
                step=1.0 if integer else 0.0,
            )
            e.setToolTip(tip)
            e.committed.connect(lambda v, name=name, integer=integer: self._opt(name, v, integer))
            fl.addRow(label, e)
            return e

        field("n_proposals", "propozycje", True, 1)
        seed = NumEdit(o.seed, integer=True, minimum=0, width=96)
        seed.committed.connect(lambda v: self._opt("seed", v, True))
        rnd = QPushButton("🎲 losuj")
        rnd.clicked.connect(
            lambda: self._set(
                optimizer=replace(self.g.optimizer, seed=secrets.randbelow(2**31)), structural=True
            )
        )
        fl.addRow("ziarno", hbox(seed, rnd))
        field(
            "max_evals",
            "budżet (ewaluacje)",
            True,
            100,
            "Budżet na propozycję w ewaluacjach — te same ustawienia dają te same wyniki",
        )
        field("time_cap_s", "limit czasu (s)", False, 0, "Tylko bezpiecznik")
        field("min_diversity", "różnorodność ΔE", False, 0, "Minimalna różnica między propozycjami")
        field("hard_weight", "waga twardych", False, 0)
        lay.addWidget(w)
        return box

    def _avoid_box(self, g: GlobalSettings) -> QGroupBox:
        box, lay = group("Unikanie kolorów źródła (tryb „charakter”)")
        dist = NumEdit(g.avoid_distance, minimum=0.0, step=0.005, width=72)
        dist.committed.connect(
            lambda v: v is not None and v != self.g.avoid_distance and self._set(avoid_distance=v)
        )
        clear = QPushButton("wyczyść")
        clear.clicked.connect(
            lambda: self._set(avoid_colors=(), avoid_distance=0.0, structural=True)
        )
        lay.addWidget(hbox(QLabel(f"{len(g.avoid_colors)} kolorów, min ΔE ok"), dist, clear))
        return box

    def _roles_box(self) -> QGroupBox:
        box, lay = group("Domyślne warunki ról (dziedziczone przez kolory)")
        legend = hbox(
            source_badge("mood"),
            QLabel("= wartość z nastroju"),
            source_badge("global"),
            QLabel("= zmieniona ręcznie"),
        )
        lay.addWidget(legend)
        self.role_tabs = QTabWidget()
        for role, title in (("bg", "tło"), ("fg", "tekst"), ("accent", "akcenty")):
            self.role_tabs.addTab(ConditionsEditor(self.win, "role", role), title)
        self.role_tabs.setCurrentIndex(self._role_tab)
        lay.addWidget(self.role_tabs)
        return box

    # --- zapis --------------------------------------------------------------------------------
    def _set(
        self, *, structural: bool = False, coalesce: str | None = None, **changes: Any
    ) -> None:
        s = self.win.session
        self.win.set_session(
            replace(s, globals=replace(s.globals, **changes)),
            coalesce=coalesce,
            structural=structural,
        )
        if not structural:
            self._shown = self.win.session  # własna edycja — widok już ją pokazuje
        # strukturalna zmiana: refresh_views przebuduje zakładkę (sesja ≠ _shown)

    def _polarity_metric(self, field: str, value: str) -> None:
        if getattr(self.g, field) == value:
            return
        self.win.set_session(
            change_polarity_or_metric(self.win.session, **{field: value}), structural=True
        )
        note = (
            "nastrój nałożony ponownie"
            if self.win.session.mood
            else "domyślne zakresy ról (nastrój użytkownika zdjęty)"
        )
        self.win.notify(f"Przeliczono: {note}; własne progi kontrastu przeliczone.")

    def _delta_e(self, value: str) -> None:
        if self.g.delta_e == value:
            return
        self.win.set_session(
            change_delta_e(self.win.session, cast(DeltaEMethod, value)), structural=True
        )
        self.win.notify("Progi odległości przeliczone na skalę nowej metody ΔE.")

    def _scheme(self, **changes: Any) -> None:
        new = replace(self.g.hue_scheme, **changes)
        if new != self.g.hue_scheme:
            self._set(hue_scheme=new)

    def _scheme_value(self, key: str, v: float | None) -> None:
        if v is not None:
            self._set(
                hue_scheme=replace(self.g.hue_scheme, **{key: float(v)}), coalesce=f"g:hs-{key}"
            )

    def _custom(self, edit: QLineEdit) -> None:
        vals = []
        for x in edit.text().replace(";", ",").split(","):
            if not x.strip():
                continue
            try:
                vals.append(parse_finite(x) % 360)
            except ValueError:
                theme.mark_error(edit, True)
                return
        theme.mark_error(edit, False)
        self._scheme(custom=tuple(vals))

    def _spread(self, lo: float | None, hi: float | None) -> None:
        sp = self.g.lightness_spread
        if sp is not None:
            self._set(lightness_spread=replace(sp, value=Interval(lo, hi)), coalesce="g:spread")

    def _spread_flag(self, field: str, on: bool) -> None:
        sp = self.g.lightness_spread
        if sp is not None and getattr(sp, field) != on:
            self._set(lightness_spread=replace(sp, **{field: on}))

    def _cvd_type(self, kind: str, on: bool) -> None:
        c = self.g.cvd
        types = set(c.types)
        (types.add if on else types.discard)(cast(CvdType, kind))
        if frozenset(types) != c.types:
            self._set(cvd=CvdSettings(frozenset(types), c.method, c.severity))

    def _opt(self, name: str, v: float | None, integer: bool) -> None:
        if v is None:
            return
        value: float | int = int(v) if integer else float(v)
        o = self.g.optimizer
        if getattr(o, name) != value:
            self._set(optimizer=replace(o, **{name: value}))

    def _mood_apply(self) -> None:
        name = self.mood.currentData()
        if name is None:
            self.win.notify("Wybierz nastrój z listy.")
            return
        try:
            self.win.set_session(apply_mood(self.win.session, str(name)), structural=True)
        except ValueError as e:
            self.win.notify(str(e), error=True)
            return
        self.win.notify(f"Nastrój „{name}” nałożony na ustawienia globalne.")

    def _mood_save(self) -> None:
        name = self.mood_name.text().strip()
        try:
            save_user_mood(name, self.win.session)
        except (ValueError, OSError) as e:
            self.win.notify(str(e), error=True)
            return
        self.win.notify(f"Zapisano nastrój „{name}”.")
        self._rebuild_later()

    def _mood_delete(self) -> None:
        name = self.mood.currentData()
        try:
            delete_user_mood(str(name))
        except (ValueError, OSError) as e:
            self.win.notify(str(e), error=True)
            return
        self.win.notify(f"Usunięto nastrój „{name}”.")
        self._rebuild_later()
