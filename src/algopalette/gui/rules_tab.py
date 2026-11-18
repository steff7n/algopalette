"""Zakładka „Zasady”: jedyne miejsce, w którym ustawia się to, co wpływa na generowanie.

Od góry: preset (wyszukiwarka, kategoria, lista, polaryzacja tła), liczba kolorów, pasek kolorów
z wielokrotnym zaznaczeniem, a pod nim edytor zaznaczenia — albo zasady zaznaczonych kolorów
(wiersz na zasadę, edycja zbiorcza, zależności przy jednym kolorze), albo „cała paleta” (metryki,
układ odcieni, rozrzut jasności, unikane kolory, generowanie).

Zapis idzie przez ``rules_edit`` i ``MainWindow.set_session``. Zmiana wartości aktualizuje widżety
w miejscu; przebudowa edytora następuje tylko przy zmianie zaznaczenia albo struktury (dodanie
lub usunięcie zasady, zmiana trybu) i jest odkładana do pętli zdarzeń, bo często wywołuje ją
sygnał widżetu, który przy przebudowie znika.
"""

from __future__ import annotations

import secrets
from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QWidget,
)

from algopalette import color as col
from algopalette import engine, presets, rules_edit
from algopalette.forms import (
    CONTRAST_GLOBAL,
    DELTA_E,
    FITS,
    SCHEMES,
)
from algopalette.globals_logic import change_delta_e, change_metric
from algopalette.gui import help
from algopalette.gui.colorstrip import ColorStrip, Selection, StripEntry
from algopalette.gui.picker import ListPicker
from algopalette.gui.relations import RelationsEditor
from algopalette.gui.rule_rows import RuleRow, SchemeRow, row_signature
from algopalette.gui.widgets import (
    NumEdit,
    RangeSlider,
    ValueSlider,
    channel_gradient,
    clear_layout,
    combo,
    form,
    hbox,
    hint,
    section,
    vbox,
)
from algopalette.model import (
    MAX_ACCENTS,
    MAX_BUDGET,
    MAX_PROPOSALS,
    MAX_SEED,
    MAX_THREADS,
    MIN_ACCENTS,
    OKLCH,
    ContrastMetric,
    DeltaEMethod,
    GlobalSettings,
    Interval,
    Rule,
    Session,
    add_accent,
    broken_relations,
    remove_slot,
    role_of,
    slot_index,
)

if TYPE_CHECKING:
    from algopalette.gui.app import MainWindow

HUE_GRADIENT = channel_gradient(OKLCH(0.75, 0.13, 0.0), "h")
ALL_CATEGORIES = "wszystkie kategorie"
# Które pola układu odcieni mają sens dla danego rodzaju (reszty nie pokazujemy).
SCHEME_FIELDS: dict[str, tuple[str, ...]] = {
    "equal": ("rotation",),
    "analogous": ("center", "spread"),
    "complementary": ("rotation",),
    "split": ("rotation",),
    "triad": ("rotation",),
    "tetrad": ("rotation",),
    "custom": (),
    "none": (),
}


def group(title: str, key: str) -> tuple[QGroupBox, Any]:
    box = QGroupBox(title)
    help.attach(box, key)
    return box, vbox(box, margins=10, spacing=6)


def keyed(w: QWidget, key: str, *, children: bool = False) -> QWidget:
    help.attach(w, key, children=children)
    return w


class RulesTab(QWidget):
    def __init__(self, win: MainWindow) -> None:
        super().__init__()
        self.win = win
        help.attach(self, "rules.tab")
        outer = vbox(self, spacing=0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(self.scroll_area, 1)
        body = QWidget()
        lay = vbox(body, margins=10, spacing=8)
        self.scroll_area.setWidget(body)

        self._sig: tuple[Any, ...] | None = None
        self._pending = False
        self._busy = False
        self._targets: tuple[Session | None, dict[str, float]] = (None, {})
        self.rows: dict[str, RuleRow] = {}
        self.scheme_row: SchemeRow | None = None
        self.relations: RelationsEditor | None = None
        self.editing_label: QLabel | None = None
        self.lock_combo: QComboBox | None = None
        self.hue_box: QGroupBox | None = None
        self.custom_picker: ListPicker | None = None
        self.avoid_picker: ListPicker | None = None
        self.palette_widgets: dict[str, QWidget] = {}

        lay.addWidget(self._preset_box())
        self.count_label = QLabel()
        self.minus_btn = QPushButton("−")
        self.plus_btn = QPushButton("+")
        for b in (self.minus_btn, self.plus_btn):
            b.setFixedWidth(34)
        self.minus_btn.setAccessibleName("usuń ostatni akcent")
        self.plus_btn.setAccessibleName("dodaj akcent")
        self.minus_btn.clicked.connect(self._fewer)
        self.plus_btn.clicked.connect(self._more)
        count = hbox(self.count_label, self.minus_btn, self.plus_btn)
        help.attach(count, "rules.count", children=True)
        lay.addWidget(count)
        self.strip = ColorStrip()
        help.attach(self.strip, "rules.strip", children=True)
        self.strip.selection_changed.connect(self._selection_changed)
        lay.addWidget(self.strip)

        self._editor = QWidget()
        self._editor_lay = vbox(self._editor, spacing=6)
        lay.addWidget(self._editor)
        lay.addStretch(1)
        self.generate_btn = QPushButton("Generuj propozycje  (Ctrl+G)")
        self.generate_btn.setDefault(True)
        self.generate_btn.clicked.connect(self.win.generate)
        help.attach(self.generate_btn, "rules.generate")
        bar = QWidget()  # poza przewijaniem: przycisk widać zawsze
        bar_lay = QHBoxLayout(bar)
        bar_lay.setContentsMargins(10, 6, 10, 6)
        bar_lay.addStretch(1)
        bar_lay.addWidget(self.generate_btn)
        outer.addWidget(bar)
        self._refresh_presets()

    # --- stan ----------------------------------------------------------------------------------

    @property
    def g(self) -> GlobalSettings:
        return self.win.session.globals

    @property
    def ids(self) -> tuple[str, ...]:
        """Zaznaczone kolory (pusta krotka = „cała paleta”)."""
        return self.strip.selection().ids

    def label(self, index: int) -> str:
        return engine.slot_label(self.win.session, index)

    def base_color(self) -> OKLCH | None:
        """Kolor, na którym rysowane są gradienty suwaków: pierwszy zaznaczony."""
        s = self.win.session
        ids = self.ids
        return s.slots[slot_index(s, ids[0])].value if ids else None

    def hue_targets(self) -> dict[str, float]:
        s = self.win.session
        if self._targets[0] is not s:
            try:
                self._targets = (s, engine.hue_targets(s))
            except ValueError:
                self._targets = (s, {})
        return self._targets[1]

    def write(self, new: Session, *, coalesce: str | None = None, structural: bool = False) -> None:
        """Jedyna droga zapisu z tej zakładki (jeden krok cofania; ``coalesce`` skleja serię).
        ``structural``: zmiana z nagłówka (preset, tło) — edytor buduje się od nowa, bo jego
        widżety (suwaki całej palety, zależności) pokazywałyby wartości sprzed zmiany
        (przegląd 2026-11-18 I2/I3)."""
        self.win.set_session(new, coalesce=coalesce, structural=structural)

    # --- odświeżanie ---------------------------------------------------------------------------

    def _entries(self) -> list[StripEntry]:
        s = self.win.session
        fit = s.globals.fit_method
        return [
            StripEntry(
                sl.id,
                self.label(i) + ("  🔒" if sl.rules_lock != "off" else ""),
                col.to_hex(sl.value, fit),
                role_of(i) == "accent",
                sl.rules_lock != "off",
            )
            for i, sl in enumerate(s.slots)
        ]

    def refresh_from_session(self, force: bool = False) -> None:
        """Dopasowuje zakładkę do sesji. ``force`` (cofnij, wczytanie, inna zakładka zmieniła
        sesję) przebudowuje edytor od razu; inaczej przebudowa tylko przy zmianie struktury."""
        self._busy = True
        try:
            self.strip.set_entries(self._entries())
            help.attach(self.strip, "rules.strip", children=True)
        finally:
            self._busy = False
        self._refresh_header()
        sig = self._signature()
        if force or self._sig is None:
            self._rebuild_editor()
        elif sig != self._sig:
            self._schedule_rebuild()
        else:
            self._sync()

    def _refresh_header(self) -> None:
        s = self.win.session
        n = len(s.slots)
        self.count_label.setText(f"Kolory: {n}")
        self.minus_btn.setEnabled(n - 2 > MIN_ACCENTS)
        self.plus_btn.setEnabled(n - 2 < MAX_ACCENTS)
        for radio, pol in ((self.pol_dark, "dark"), (self.pol_light, "light")):
            radio.blockSignals(True)
            radio.setChecked(s.globals.polarity == pol)
            radio.blockSignals(False)
        if s.preset is None:
            text = "bieżący: — (własne zasady)"
        else:
            try:
                modified = presets.is_modified(s)
            except ValueError:
                modified = True
            text = f"bieżący: <b>„{s.preset}”</b>" + (" (zmieniony)" if modified else "")
        self.current_label.setText(text)

    def _signature(self) -> tuple[Any, ...]:
        s = self.win.session
        sel = self.strip.selection()
        if sel.palette:
            g = s.globals
            return ("palette", g.hue_scheme.kind, g.lightness_spread is None, g.delta_e)
        ids = sel.ids
        fields = rules_edit.applicable_fields(s, ids)
        rows = tuple((f, row_signature(s, ids, f)) for f in fields)
        accents = all(role_of(slot_index(s, i)) == "accent" for i in ids)
        rel: Any = None
        if len(ids) == 1:
            slot = s.slots[slot_index(s, ids[0])]
            broken = {i for sid, i in broken_relations(s) if sid == slot.id}
            names = tuple(self.label(i) for i in range(len(s.slots)))
            rel = (tuple((r.kind, i in broken) for i, r in enumerate(slot.relations)), names)
        locks = rules_edit.merged_rules_lock(s, ids)
        return ("colors", ids, self.base_color(), rows, accents, rel, locks)

    def _schedule_rebuild(self) -> None:
        if not self._pending:
            self._pending = True
            QTimer.singleShot(0, self, self.flush)  # z kontekstem: nie odpali po zniszczeniu

    def flush(self) -> None:
        """Wykonuje odłożoną przebudowę (zegar pętli zdarzeń; testy wołają wprost)."""
        if self._pending:
            self._rebuild_editor()

    def _selection_changed(self, _sel: Selection) -> None:
        if not self._busy:
            self._schedule_rebuild()

    def _sync(self) -> None:
        for row in self.rows.values():
            row.sync()
        if self.scheme_row is not None:
            self.scheme_row.sync()

    def _rebuild_editor(self) -> None:
        self._pending = False
        self._sig = self._signature()
        bar = self.scroll_area.verticalScrollBar()
        scroll = bar.value()
        clear_layout(self._editor_lay)
        self.rows, self.scheme_row, self.relations = {}, None, None
        self.lock_combo = None
        self.hue_box, self.custom_picker, self.avoid_picker = None, None, None
        self.palette_widgets = {}
        if self.strip.selection().palette:
            self._build_palette()
        else:
            self._build_colors()
        QTimer.singleShot(0, bar, lambda: bar.setValue(scroll))

    # --- zasady zaznaczonych kolorów -----------------------------------------------------------

    def _build_colors(self) -> None:
        s, ids = self.win.session, self.ids
        index = {sl.id: i for i, sl in enumerate(s.slots)}
        names = ", ".join(self.label(index[i]) for i in ids)
        self.editing_label = QLabel(f"Edytujesz: <b>{names}</b>")
        self.editing_label.setWordWrap(True)
        help.attach(self.editing_label, "rules.editing")
        self._editor_lay.addWidget(self.editing_label)
        self._editor_lay.addWidget(self._lock_row(all(role_of(index[i]) == "accent" for i in ids)))
        for f in rules_edit.applicable_fields(s, ids):
            row = RuleRow(self, f)
            self.rows[f] = row
            self._editor_lay.addWidget(row)
            if f == "hue" and all(role_of(index[i]) == "accent" for i in ids):
                self.scheme_row = SchemeRow(self)
                self._editor_lay.addWidget(self.scheme_row)
        head = section("Zależności od innych kolorów")
        help.attach(head, "rel.overview")
        self._editor_lay.addWidget(head)
        if len(ids) == 1:
            self.relations = RelationsEditor(self.win, ids[0])
            self._editor_lay.addWidget(self.relations)
        else:
            note = hint("Zależności edytuje się przy jednym zaznaczonym kolorze.")
            help.attach(note, "rel.overview")
            self._editor_lay.addWidget(note)

    def _lock_row(self, accents: bool) -> QWidget:
        """„kłódka zasad: [wyłączona ▾]” — ochrona zasad zaznaczonych kolorów przed presetem."""
        options: list[tuple[str, Any]] = [
            ("wyłączona", "off"),
            ("zasady (odcień dalej z układu palety)" if accents else "zasady", "rules"),
        ]
        if accents:
            options.append(("zasady + zamrożony cel odcienia", "hue"))
        current = rules_edit.merged_rules_lock(self.win.session, self.ids)
        if current is None:
            options.insert(0, ("— różnie —", None))
        elif current == "hue" and not accents:
            current = "rules"
        self.lock_combo = combo(options, current)
        self.lock_combo.setCurrentIndex(self.lock_combo.findData(current))
        self.lock_combo.activated.connect(self._lock_changed)
        label = QLabel("🔒 kłódka zasad:")
        row = hbox(label, self.lock_combo, None)
        help.attach(row, "rules.lock", children=True)
        return row

    def _lock_changed(self, _index: int) -> None:
        combo_box = self.lock_combo
        mode = combo_box.currentData() if combo_box is not None else None
        if mode is None:
            return
        s = self.win.session
        try:
            new = rules_edit.set_rules_lock(s, self.ids, mode, self.hue_targets())
        except ValueError as e:
            self.win.notify(str(e), error=True)
            return
        if new is not s:
            self.write(new)

    def show_scheme_settings(self) -> None:
        """Odnośnik z wiersza „układ odcieni”: „cała paleta”, przewinięte do układu odcieni."""
        self.strip.select_palette()
        self.flush()
        box = self.hue_box
        if box is not None:
            QTimer.singleShot(0, box, lambda: self.scroll_area.ensureWidgetVisible(box))

    # --- liczba kolorów ------------------------------------------------------------------------

    def _fewer(self) -> None:
        s = self.win.session
        if len(s.slots) - 2 > MIN_ACCENTS:
            self.write(remove_slot(s, s.slots[-1].id))

    def _more(self) -> None:
        s = self.win.session
        if len(s.slots) - 2 < MAX_ACCENTS:
            self.write(add_accent(s))

    # --- preset --------------------------------------------------------------------------------

    def _preset_box(self) -> QGroupBox:
        box, lay = group("Preset", "rules.preset")
        self.search = QLineEdit()
        self.search.setPlaceholderText("szukaj presetu…")
        self.search.setMinimumWidth(170)
        self.search.textChanged.connect(lambda _t: self._refresh_presets())
        help.attach(self.search, "rules.preset.search")
        options = [(ALL_CATEGORIES, None), *((c, c) for c in presets.CATEGORIES)]
        options.append((presets.USER_CATEGORY, presets.USER_CATEGORY))
        self.category = combo(options, None)
        self.category.setCurrentIndex(0)
        self.category.currentIndexChanged.connect(lambda _i: self._refresh_presets())
        help.attach(self.category, "rules.preset.category")
        self.preset_combo = combo([], None)
        self.preset_combo.setMinimumWidth(260)
        help.attach(self.preset_combo, "rules.preset.list")
        self.pol_dark = QRadioButton("ciemne")
        self.pol_light = QRadioButton("jasne")
        self.pol_dark.clicked.connect(lambda: self._polarity("dark"))
        self.pol_light.clicked.connect(lambda: self._polarity("light"))
        pol_label = QLabel("tło:")
        for w in (pol_label, self.pol_dark, self.pol_light):
            help.attach(w, "rules.polarity")
        self.apply_btn = QPushButton("Zastosuj")
        self.apply_btn.clicked.connect(self._preset_apply)
        help.attach(self.apply_btn, "rules.preset.apply")
        lay.addWidget(
            hbox(
                self.search,
                self.category,
                self.preset_combo,
                self.apply_btn,
                pol_label,
                self.pol_dark,
                self.pol_light,
            )
        )
        self.current_label = QLabel()
        help.attach(self.current_label, "rules.preset.current")
        self.preset_name = QLineEdit()
        self.preset_name.setPlaceholderText("nazwa własnego presetu")
        self.preset_name.setMinimumWidth(200)
        help.attach(self.preset_name, "rules.preset.save")
        self.save_btn = QPushButton("Zapisz zasady jako preset")
        self.save_btn.clicked.connect(self._preset_save)
        help.attach(self.save_btn, "rules.preset.save")
        self.delete_btn = QPushButton("Usuń własny")
        self.delete_btn.clicked.connect(self._preset_delete)
        help.attach(self.delete_btn, "rules.preset.delete")
        lay.addWidget(
            hbox(self.current_label, None, self.preset_name, self.save_btn, self.delete_btn)
        )
        return box

    def _refresh_presets(self) -> None:
        """Lista presetów pasujących do wyszukiwarki i kategorii (bieżący wybór zostaje)."""
        wanted = self.preset_combo.currentData()
        try:
            found = presets.search(self.search.text(), self.category.currentData())
        except ValueError as e:
            self.win.notify(str(e))
            found = []
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        for i, p in enumerate(found):
            self.preset_combo.addItem(p.name if p.builtin else f"{p.name}  (własny)", p.name)
            self.preset_combo.setItemData(i, f"{p.category}: {p.description}", 3)  # ToolTipRole
        names = [p.name for p in found]
        current = self.win.session.preset
        pick = wanted if wanted in names else current if current in names else None
        self.preset_combo.setCurrentIndex(
            names.index(pick) if pick in names else (0 if names else -1)
        )
        self.preset_combo.blockSignals(False)

    def _preset_apply(self) -> None:
        name = self.preset_combo.currentData()
        if name is None:
            self.win.notify("Wybierz preset z listy.")
            return
        try:
            new = presets.apply_preset(self.win.session, str(name))
        except ValueError as e:
            self.win.notify(str(e), error=True)
            return
        self.write(new, structural=True)
        kept = [self.label(i) for i, sl in enumerate(new.slots) if sl.rules_lock != "off"]
        what = f"kolorów bez kłódki (zostały: {', '.join(kept)})" if kept else "wszystkich kolorów"
        self.win.notify(f"Preset „{name}” zastąpił zasady {what} (Ctrl+Z cofa).")

    def _preset_save(self) -> None:
        name = self.preset_name.text().strip()
        try:
            presets.save_user_preset(name, self.win.session)
        except (ValueError, OSError) as e:
            self.win.notify(str(e), error=True)
            return
        self.preset_name.clear()
        self.write(replace(self.win.session, preset=name))
        self._refresh_presets()
        self._refresh_header()
        self.win.notify(f"Zapisano preset „{name}”.")

    def _preset_delete(self) -> None:
        name = self.preset_combo.currentData()
        try:
            presets.delete_user_preset(str(name))
        except (ValueError, OSError) as e:
            self.win.notify(str(e), error=True)
            return
        self._refresh_presets()
        self._refresh_header()
        self.win.notify(f"Usunięto preset „{name}”.")

    def ask_polarity(self, polarity: str) -> str:
        """Pytanie przy zmianie polaryzacji, gdy zasady nie są świeżym presetem.
        Zwraca ``"replace"``, ``"mark"`` albo ``"cancel"``."""
        name = "jasne" if polarity == "light" else "ciemne"
        box = QMessageBox(self)
        box.setWindowTitle("Zmiana tła")
        box.setText(
            f"Zasady nie są świeżo nałożonym presetem. Co zrobić przy zmianie tła na {name}?"
        )
        replace_btn = box.addButton("Zastąp zasady presetem", QMessageBox.ButtonRole.AcceptRole)
        mark_btn = box.addButton("Zmień tylko oznaczenie tła", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Anuluj", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        return "replace" if clicked is replace_btn else "mark" if clicked is mark_btn else "cancel"

    def _polarity(self, polarity: str) -> None:
        s = self.win.session
        if s.globals.polarity == polarity:
            return
        try:
            fresh = (
                s.preset is not None
                and presets.supports(s.preset, polarity)
                and not presets.is_modified(s)
            )
            choice = "replace" if fresh else self.ask_polarity(polarity)
            if choice == "cancel":
                self._refresh_header()  # przycisk wraca do polaryzacji sesji
                return
            new = presets.change_polarity(s, polarity, reapply=choice == "replace")
        except ValueError as e:  # np. uszkodzony presets.json (przegląd 2026-11-18 M12)
            self._refresh_header()
            self.win.notify(str(e), error=True)
            return
        self.write(new, structural=True)
        if choice == "replace":
            self.win.notify(f"Preset „{new.preset}” nałożony ponownie dla nowego tła.")
        else:
            self.win.notify("Zmieniono tylko oznaczenie tła — zasady zostały bez zmian.")

    # --- cała paleta ---------------------------------------------------------------------------

    def _set(self, *, coalesce: str | None = None, **changes: Any) -> None:
        s = self.win.session
        self.write(replace(s, globals=replace(s.globals, **changes)), coalesce=coalesce)

    def _build_palette(self) -> None:
        g = self.g
        self.editing_label = QLabel(
            "Edytujesz: <b>całą paletę</b> — ustawienia wspólne dla wszystkich kolorów"
        )
        help.attach(self.editing_label, "rules.palette")
        self._editor_lay.addWidget(self.editing_label)
        row = hbox(self._metrics_box(g), self._generation_box(g), stretch=False, spacing=10)
        self._editor_lay.addWidget(row)
        self.hue_box = self._hues_box(g)
        self._editor_lay.addWidget(self.hue_box)
        self._editor_lay.addWidget(self._spread_box(g))
        self._editor_lay.addWidget(self._avoid_box(g))

    def _metrics_box(self, g: GlobalSettings) -> QGroupBox:
        box, lay = group("Metryki", "rules.metrics")
        w, fl = form()
        met = combo(CONTRAST_GLOBAL, g.contrast_metric)
        met.activated.connect(lambda _i: self._metric(met.currentData()))
        fl.addRow("kontrast", keyed(met, "rules.contrast_metric"))
        de = combo(DELTA_E, g.delta_e)
        de.activated.connect(lambda _i: self._delta_e(de.currentData()))
        fl.addRow("ΔE", keyed(de, "rules.delta_e"))
        fit = combo(FITS, g.fit_method)
        fit.activated.connect(lambda _i: self._set(fit_method=fit.currentData()))
        fl.addRow("dopasowanie do gamutu", keyed(fit, "rules.fit"))
        help.attach_form_labels(fl)
        lay.addWidget(w)
        note = hint("Zmiana metryki kontrastu albo metody ΔE przelicza progi w zasadach kolorów.")
        lay.addWidget(keyed(note, "rules.metrics"))
        lay.addStretch(1)
        self.palette_widgets.update(contrast_metric=met, delta_e=de, fit_method=fit)
        return box

    def _hues_box(self, g: GlobalSettings) -> QGroupBox:
        h = g.hue_scheme
        box, lay = group("Układ odcieni — cele dla akcentów, które go stosują", "rules.hues")
        w, fl = form()
        kind = combo(SCHEMES, h.kind)
        kind.activated.connect(lambda _i: self._scheme(kind=kind.currentData()))
        fl.addRow("rodzaj", keyed(kind, "rules.hues.kind"))
        self.palette_widgets["hues.kind"] = kind
        sliders = {
            "rotation": ("obrót °", 0, 360, True, HUE_GRADIENT),
            "center": ("środek °", 0, 360, True, HUE_GRADIENT),
            "spread": ("rozpiętość °", 0, 360, False, None),
            "tol": ("tolerancja ±°", 0, 90, False, None),
            "jitter": ("rozrzut losowy ±°", 0, 45, False, None),
        }
        shown = (*SCHEME_FIELDS[h.kind], *(() if h.kind == "none" else ("tol", "jitter")))
        for key in shown:
            label, lo, hi, wrap, grad = sliders[key]
            sl = ValueSlider(
                getattr(h, key), minimum=lo, maximum=hi, step=1, fmt=".0f", wrap=wrap, gradient=grad
            )
            sl.changed.connect(lambda v, key=key: self._scheme_value(key, v))
            fl.addRow(label, keyed(sl, f"rules.hues.{key}", children=True))
            self.palette_widgets[f"hues.{key}"] = sl
        if h.kind == "custom":
            self.custom_picker = ListPicker(h.custom, mode="hue", max_items=MAX_ACCENTS)
            self.custom_picker.changed.connect(self._custom)
            fl.addRow("własna lista", keyed(self.custom_picker, "rules.hues.custom", children=True))
        if h.kind != "none":
            hard = QCheckBox("twardy")
            hard.setChecked(h.hard)
            hard.clicked.connect(lambda on: self._scheme(hard=on))
            weight = NumEdit(h.weight, minimum=0.0, step=0.1, width=56)
            weight.committed.connect(lambda v: v is not None and self._scheme(weight=v))
            row = hbox(hard, QLabel("waga"), weight)
            fl.addRow("", keyed(row, "rules.hues.hard", children=True))
            self.palette_widgets.update({"hues.hard": hard, "hues.weight": weight})
        help.attach_form_labels(fl)
        lay.addWidget(w)
        return box

    def _spread_box(self, g: GlobalSettings) -> QGroupBox:
        sp = g.lightness_spread
        box, lay = group("Rozrzut jasności akcentów (największa L − najmniejsza L)", "rules.spread")
        if sp is None:
            add = QPushButton("+ dodaj zasadę rozrzutu")
            add.clicked.connect(
                lambda: self._set(lightness_spread=Rule(Interval(0.15, None), hard=False))
            )
            lay.addWidget(hbox(keyed(add, "rules.spread")))
            lay.addStretch(1)
            self.palette_widgets["spread.add"] = add
            return box
        en = QCheckBox("włączona")
        en.setChecked(sp.enabled)
        en.clicked.connect(lambda on: self._spread_flag("enabled", on))
        hard = QCheckBox("twarda")
        hard.setChecked(sp.hard)
        hard.clicked.connect(lambda on: self._spread_flag("hard", on))
        weight = NumEdit(sp.weight, minimum=0.0, step=0.1, width=56)
        weight.committed.connect(lambda v: v is not None and self._spread_flag("weight", v))
        rm = QPushButton("✕ usuń")
        rm.clicked.connect(lambda: self._set(lightness_spread=None))
        lay.addWidget(
            keyed(hbox(en, hard, QLabel("waga"), weight, rm), "rules.spread", children=True)
        )
        rs = RangeSlider(
            sp.value.lo, sp.value.hi, minimum=0, maximum=1, step=0.01, fmt=".2f", allow_none=True
        )
        rs.changed.connect(self._spread)
        lay.addWidget(keyed(rs, "rules.spread", children=True))
        lay.addStretch(1)
        self.palette_widgets.update({"spread.range": rs, "spread.remove": rm, "spread.hard": hard})
        return box

    def _avoid_box(self, g: GlobalSettings) -> QGroupBox:
        box, lay = group(
            "Unikane kolory — akcenty mają trzymać się od nich z daleka", "rules.avoid"
        )
        self.avoid_picker = ListPicker(g.avoid_colors, mode="color", max_items=16)
        self.avoid_picker.changed.connect(self._avoid)
        lay.addWidget(keyed(self.avoid_picker, "rules.avoid", children=True))
        dist = NumEdit(g.avoid_distance, minimum=0.0, step=0.005, width=72)
        dist.committed.connect(lambda v: v is not None and self._set(avoid_distance=float(v)))
        row = hbox(QLabel("najmniejsza odległość ΔE ok"), dist)
        lay.addWidget(keyed(row, "rules.avoid", children=True))
        self.palette_widgets["avoid.distance"] = dist
        return box

    def _generation_box(self, g: GlobalSettings) -> QGroupBox:
        o = g.optimizer
        box, lay = group("Generowanie", "rules.generation")
        w, fl = form()

        def field(
            name: str,
            label: str,
            integer: bool,
            minimum: float,
            key: str,
            maximum: float | None = None,
        ) -> NumEdit:
            e = NumEdit(
                getattr(o, name),
                integer=integer,
                minimum=minimum,
                maximum=maximum,
                width=96,
                step=1.0 if integer else 0.0,
            )
            help.attach(e, key)
            e.committed.connect(lambda v, name=name, integer=integer: self._opt(name, v, integer))
            fl.addRow(label, e)
            self.palette_widgets[f"gen.{name}"] = e
            return e

        field("n_proposals", "liczba propozycji", True, 1, "rules.gen.n_proposals", MAX_PROPOSALS)
        seed = NumEdit(o.seed, integer=True, minimum=0, maximum=MAX_SEED, width=96)
        seed.committed.connect(lambda v: self._opt("seed", v, True))
        rnd = QPushButton("🎲 losuj")
        rnd.clicked.connect(
            lambda: self._set(optimizer=replace(self.g.optimizer, seed=secrets.randbelow(2**31)))
        )
        fl.addRow("ziarno", keyed(hbox(seed, rnd), "rules.gen.seed", children=True))
        self.palette_widgets.update({"gen.seed": seed, "gen.random": rnd})
        field("budget", "budżet (oceny na przebieg)", True, 1, "rules.gen.budget", MAX_BUDGET)
        field("time_cap_s", "limit czasu (s, 0 = bez)", False, 0, "rules.gen.time_cap")
        field("min_diversity", "różnorodność ΔE", False, 0, "rules.gen.min_diversity")
        field("hard_weight", "waga twardych", False, 0, "rules.gen.hard_weight")
        field("threads", "wątki (0 = wszystkie)", True, 0, "rules.gen.threads", MAX_THREADS)
        help.attach_form_labels(fl)
        lay.addWidget(w)
        return box

    # --- zapis ustawień całej palety -------------------------------------------------------------

    def _metric(self, value: str) -> None:
        if self.g.contrast_metric != value:
            self.write(change_metric(self.win.session, cast(ContrastMetric, value)))
            self.win.notify("Progi kontrastu przeliczone na nową metrykę.")

    def _delta_e(self, value: str) -> None:
        if self.g.delta_e != value:
            self.write(change_delta_e(self.win.session, cast(DeltaEMethod, value)))
            self.win.notify("Progi odległości przeliczone na skalę nowej metody ΔE.")

    def _scheme(self, **changes: Any) -> None:
        new = replace(self.g.hue_scheme, **changes)
        if new != self.g.hue_scheme:
            self._set(hue_scheme=new)

    def _scheme_value(self, key: str, v: float | None) -> None:
        if v is not None:
            new = replace(self.g.hue_scheme, **{key: float(v)})
            self._set(hue_scheme=new, coalesce=f"g:hs-{key}")

    def _custom(self, hues: tuple[float, ...]) -> None:
        self._set(hue_scheme=replace(self.g.hue_scheme, custom=tuple(hues)), coalesce="g:hs-custom")
        if self.custom_picker is not None:
            help.attach(self.custom_picker, "rules.hues.custom", children=True)

    def _avoid(self, colors: tuple[OKLCH, ...]) -> None:
        changes: dict[str, Any] = {"avoid_colors": tuple(colors)}
        if colors and self.g.avoid_distance <= 0:
            changes["avoid_distance"] = 0.05  # lista bez odległości nic by nie robiła
        self._set(coalesce="g:avoid", **changes)
        if self.avoid_picker is not None:
            help.attach(self.avoid_picker, "rules.avoid", children=True)
        dist = self.palette_widgets.get("avoid.distance")
        if isinstance(dist, NumEdit):
            dist.set_value(self.g.avoid_distance)

    def _spread(self, lo: float | None, hi: float | None) -> None:
        sp = self.g.lightness_spread
        if sp is not None:
            self._set(lightness_spread=replace(sp, value=Interval(lo, hi)), coalesce="g:spread")

    def _spread_flag(self, name: str, value: Any) -> None:
        sp = self.g.lightness_spread
        if sp is not None and getattr(sp, name) != value:
            self._set(lightness_spread=replace(sp, **{name: value}))

    def _opt(self, name: str, v: float | None, integer: bool) -> None:
        if v is None:
            return
        value: float | int = int(v) if integer else float(v)
        o = self.g.optimizer
        if getattr(o, name) != value:
            self._set(optimizer=replace(o, **{name: value}))
