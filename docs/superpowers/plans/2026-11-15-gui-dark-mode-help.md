# GUI: tryb ciemny + pomoc kontekstowa — plan wdrożenia

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Przełączany na żywo motyw systemowy/jasny/ciemny oraz szybkie podpowiedzi na każdym elemencie GUI z F1 →
dokowany panel Pomocy na temacie elementu.

**Architecture:** `gui/theme.py` (palety Qt, kolory semantyczne, ustawienia w `config_dir()/gui.json`, sygnał
zmiany); `gui/help.py` (rejestr kluczy na widżetach/akcjach/nagłówkach/zakładkach, rozstrzyganie F1, `HelpPanel`
jako `QDockWidget`, tryb Shift+F1, proxy-styl z opóźnieniem podpowiedzi, `uncovered()` do testów pokrycia);
treść w pakiecie `gui/help_content/` — jeden moduł na obszar, scalane w `TOPICS`.

**Tech Stack:** Python 3, PySide6 (Fusion), pytest-qt (offscreen), ruff, ty, uv.

**Spec:** `docs/superpowers/specs/2026-11-15-gui-dark-mode-help-design.md` (czytaj przed każdym zadaniem).

## Global Constraints

- Treść pomocy po polsku, poprawna ortografia z diakrytykami. **Pomoc opisuje głównie działanie programu** (co robi
  element, jak wpływa na silnik / propozycje / naruszenia / zapis, jak z niego korzystać, typowe użycie);
  teoria koloru krótko i praktycznie (decyzja użytkownika niżej). Treść zgodna z FAKTYCZNYM kodem — czytaj kod,
  nie zgaduj; w razie wątpliwości `README.md` i spec `docs/superpowers/specs/2026-11-14-algopalette-design.md`.
- `Topic.short`: 1–2 zdania, ≤ 200 znaków, bez tautologii (nie powtarza samego tytułu). `Topic.body`: Markdown,
  akapity + listy, linki do innych tematów jako `[tekst](help:klucz)`.
- Klucze: małe litery, segmenty po kropce: `window.*`, `menu.*`, `concept.*`, `general.*`, `palette.*`, `cond.*`,
  `rel.*`, `globals.*`, `proposals.*`, `source.*`, `analysis.*`.
- Grupy (kolejność w drzewie): `"Ogólne"`, `"Okno i menu"`, `"Paleta"`, `"Warunki i zależności"`, `"Globalne"`,
  `"Propozycje"`, `"Źródło"`, `"Analiza"`, `"Pojęcia"`.
- Opóźnienie podpowiedzi 300 ms. Kontrast kolorów semantycznych tekstu z `Window` i `Base` ≥ 4.5 (WCAG 2.1), ramek
  ≥ 3.0, w OBU motywach.
- TUI i rdzeń bez zmian. Każdy `.py`: `ruff check --fix`, `ruff format`, `ty check` — zero uwag.
- Testy GUI: istniejący `tests/gui/conftest.py` (offscreen, XDG w tmp). Pułapki Qt z HANDOFF §0a obowiązują
  (`deleteLater` → `sendPostedEvents(None, QEvent.DeferredDelete)`, `isHidden()` zamiast `isVisible()`,
  przebudowy z sygnałów dziecka przez `QTimer.singleShot(0, …)`).
- Nigdy `git add -A`; stageuj tylko swoje pliki.

**User decisions (already made):**
- „wprowadź proszę tryb ciemny … Wyjaśnij każdą pojedynczą rzecz … szybkie tooltipy z możliwością rozwinięcia do
  bardziej rozbudowanej zakładki pomocy. Czytelność, przejrzystość i wygoda użytkownika jest wszystkim”.
- Wariant 1: podpowiedź „F1 — więcej”, F1 otwiera pomoc na temacie elementu (spis treści + wyszukiwarka).
- „na końcu wszystko scal” → po zakończeniu i przeglądzie scalić `gui` do `main`.
- „skup się w pomocy na tym, jak działa program, nie na tym, jak działa kolor. na ten temat również napisz, ale
  relatywnie mniej”.

## Review Focus

1. Zmiana motywu przy otwartym edytorze z czerwonymi ramkami błędów / plakietkami źródeł — po przełączeniu kolory
   odpowiadają NOWEMU motywowi (stylesheety ustawione ponownie). Test w Tasku 1.
2. F1 nad elementem bez własnego klucza (np. viewport tabeli, etykieta wewnątrz suwaka) → klucz najbliższego
   przodka; F1 gdy kursor poza oknem → widżet z fokusem; F1 w otwartym menu → temat akcji. Testy w Tasku 2.
3. Uszkodzony / niezapisywalny `gui.json` → motyw „system”, bez wyjątku; inne klucze w pliku nie są kasowane przy
   zapisie. Test w Tasku 1.
4. Wiersze budowane dynamicznie (po cofnij/ponów, dodaniu akcentu, nowym warunku/zależności, nowych propozycjach)
   nadal mają podpowiedzi. Testy pokrycia w Taskach 4–7 robią akcję i sprawdzają ponownie.
5. Wyszukiwarka bez diakrytyków: „jasnosc” znajduje „jasność”, „zrodlo” → „Źródło”, wielkość liter bez znaczenia.
   Test w Tasku 2.

---

## Kolejność i równoległość

`{T1, T2}` równolegle → `{T3, T4, T5, T6, T7}` równolegle (rozłączne pliki, osobne worktree) → T8.

## Interfejsy dzielone (definiowane w T1/T2, używane dalej)

```python
# gui/theme.py  (T1)
ThemeMode = Literal["system", "light", "dark"]
@dataclass(frozen=True)
class Colors:            # kolory semantyczne jako "#rrggbb"
    hard: str            # tekst/znacznik naruszenia twardego
    soft: str            # tekst/znacznik naruszenia miękkiego
    ok: str              # tekst „spełnione”
    error_border: str    # ramka pola z błędem
    warn_text: str       # tekst ostrzeżenia (np. kolor poza gamutem w tabeli)
    badge: dict[str, tuple[str, str]]   # źródło wartości ("mood"/"global"/"own" — klucze wg conditions.py) → (tło, tekst)
def load_mode() -> ThemeMode                  # z gui.json; brak/uszkodzony → "system"
def save_mode(mode: ThemeMode) -> None        # scala z istniejącym JSON-em, zapis atomowy; OSError propaguje
def initial_mode() -> ThemeMode               # ALGOPALETTE_THEME (dark/light) ma pierwszeństwo nad load_mode()
def is_dark(mode: ThemeMode) -> bool          # "system" → QStyleHints.colorScheme()
def apply(app: QApplication, mode: ThemeMode) -> None   # ustawia paletę + emituje notifier.changed
def colors() -> Colors                        # zestaw dla AKTUALNIE zastosowanego motywu
def current_mode() -> ThemeMode
notifier: QObject  # z Signal changed()

# gui/help_content/__init__.py  (T2)
@dataclass(frozen=True)
class Topic:
    title: str
    short: str
    body: str            # Markdown
    group: str           # jedna z grup z Global Constraints
GROUPS: tuple[str, ...]
TOPICS: dict[str, Topic] # scalenie słowników z modułów: general, window, palette, conditions, globals,
                         # proposals, source, analysis, concepts (każdy moduł eksportuje TOPICS)

# gui/help.py  (T2)
HELP_PROP = "help_key"
HELP_ROLE: int                               # rola danych dla nagłówków tabel / zakładek
def attach(obj: QWidget | QAction, key: str, *, children: bool = False) -> None
    # KeyError gdy key not in TOPICS; ustawia property + tooltip (tooltip_html); children=True →
    # także na potomkach bez własnego klucza (np. NumEdit/Bar wewnątrz ValueSlider)
def attach_header(table: QTableWidget, keys: Sequence[str | None]) -> None   # per kolumna
def attach_tab(tabs: QTabWidget, index: int, key: str) -> None
def decorative(w: QWidget) -> None           # jawne „nie wymaga pomocy” (np. pusty odstęp); używać oszczędnie
def tooltip_html(key: str) -> str            # <b>tytuł</b><br>short<br><i>F1 — więcej</i>
def key_at(global_pos: QPoint) -> str | None # widżet pod kursorem: QTabBar→zakładka, QHeaderView→kolumna,
                                             # QToolButton→defaultAction, QMenu→activeAction, inaczej przodkowie
def key_for_focus() -> str | None
def uncovered(root: QWidget) -> list[str]    # opisy widżetów wymagających klucza, które go nie mają
class HelpPanel(QDockWidget):                # objectName "help-panel"
    def show_topic(self, key: str) -> None
    def show_index(self) -> None
    def search(self, text: str) -> list[str] # klucze; bez diakrytyków i wielkości liter, tytuł+short+body
    current_key: str | None
class HelpController:                        # install(window) tworzy panel, akcje F1/Shift+F1, filtr menu
    def help_here(self) -> None              # logika F1 ze speca (cel 6), w tym przełączenie panelu
    def enter_click_mode(self) -> None
def install(window: QMainWindow) -> HelpController
def install_tooltip_style(app: QApplication) -> None   # proxy-styl Fusion, SH_ToolTip_WakeUpDelay = 300
```

---

### Task 1: Motyw systemowy/jasny/ciemny + kolory semantyczne

**Goal:** Menu Widok → Motyw (3 opcje radio), przełączanie na żywo, zapamiętanie w `gui.json`, wszystkie kolory
na sztywno zastąpione `theme.colors()`.

**Files:**
- Create: `src/algopalette/gui/theme.py`, `tests/gui/test_theme.py`
- Modify: `src/algopalette/gui/app.py` (usunąć `_apply_theme`, `HARD/SOFT/OK_COLOR` → `theme.colors()`; podmenu
  `Motyw` w Widok z `QActionGroup`; atrybuty `act_theme_system/light/dark`; `run()` → `theme.apply(app,
  theme.initial_mode())`; na `notifier.changed` → `refresh_views(editor=True)` + ponowne `show_violations`),
  `relations.py:97`, `globals_tab.py:409`, `source_tab.py:142`, `widgets.py:243`, `conditions.py:208`,
  `palette_tab.py` (`WARN_COLOR`), `analysis_tab.py` (obrazy liczone z koloru okna — przeliczyć na zmianę).

**Acceptance Criteria:**
- [ ] `grep -rn '#[0-9a-fA-F]\{6\}' src/algopalette/gui --include=*.py | grep -v theme.py` nie zwraca kolorów
      interfejsu (dopuszczalne: kolory danych palety, np. hexy sesji).
- [ ] Wybór motywu w menu zmienia `QApplication.palette().window()` od razu i zapisuje `gui.json`; nowe okno
      startuje z zapisanym motywem; `ALGOPALETTE_THEME` nadpisuje zapis.
- [ ] „systemowy” reaguje na `styleHints().colorSchemeChanged`.
- [ ] Kontrast `hard/soft/ok/warn_text` z `Window` i `Base` ≥ 4.5, `error_border` ≥ 3.0, w obu motywach;
      plakietki: tekst/tło ≥ 4.5.
- [ ] Błąd zapisu `gui.json` → komunikat w pasku stanu, bez wyjątku.

**Verify:** `uv run pytest tests/gui -q` → wszystkie zielone; `uv run ruff check src tests && uv run ruff format --check src tests && uv run ty check` → zero uwag.

**Steps:**

- [ ] **Step 1: testy (najpierw czerwone)** w `tests/gui/test_theme.py`:
  - `test_load_mode_missing_or_corrupt_is_system` — brak pliku, `"{nie json"`, `{"theme": "fiolet"}` → `"system"`.
  - `test_save_mode_keeps_other_keys` — `gui.json` = `{"x": 1}` → `save_mode("dark")` → `{"x": 1, "theme": "dark"}`.
  - `test_env_overrides_saved` — zapis `"light"`, `ALGOPALETTE_THEME=dark` → `initial_mode() == "dark"`.
  - `test_semantic_contrast[light|dark]` — `contrast_hex(c, window_hex, "wcag")` progi jak w AC
    (`from algopalette.color import contrast_hex`).
  - `test_menu_switch_live(win)` — trigger `win.act_theme_dark` → `QApplication.palette().window().color()
    .lightness() < 100`, `load_mode() == "dark"`; potem `act_theme_light` → `> 150`.
  - `test_error_border_follows_theme(win)` — wprowadź błędną wartość w polu z ramką błędu (np. pole globalne
    z `globals_tab.py:409`), przełącz na ciemny → `styleSheet()` zawiera `theme.colors().error_border` ciemnego.
  - `test_save_failure_is_reported(win, monkeypatch)` — `save_mode` rzuca `OSError` → brak wyjątku, pasek stanu
    ma komunikat.
  - Po każdym teście przywróć motyw jasny (fixture autouse w tym pliku), żeby nie psuć innych testów.
- [ ] **Step 2: implementacja** wg interfejsu `theme.py`. Ciemna paleta: wyjdź od obecnej z `app.py:530-550`;
  `ToolTipBase` wyraźnie inny od `Window` (podpowiedzi mają się odcinać). Jasna: `QStyleFactory.create("Fusion")
  .standardPalette()`. Kolory semantyczne dobierz pod progi kontrastu.
- [ ] **Step 3:** `uv run pytest tests/gui -q`, ruff, ty → zero uwag.
- [ ] **Step 4: commit** `feat(gui): przełączany motyw systemowy/jasny/ciemny i kolory semantyczne`.

```json:metadata
{"files": ["src/algopalette/gui/theme.py", "src/algopalette/gui/app.py", "src/algopalette/gui/relations.py", "src/algopalette/gui/globals_tab.py", "src/algopalette/gui/source_tab.py", "src/algopalette/gui/widgets.py", "src/algopalette/gui/conditions.py", "src/algopalette/gui/palette_tab.py", "src/algopalette/gui/analysis_tab.py", "tests/gui/test_theme.py"], "verifyCommand": "uv run pytest tests/gui -q", "acceptanceCriteria": ["brak kolorów UI na sztywno poza theme.py", "menu zmienia motyw na żywo i zapisuje gui.json", "system śledzi colorSchemeChanged", "kontrast semantyczny >= 4.5/3.0 w obu motywach", "błąd zapisu -> pasek stanu"], "modelTier": "standard"}
```

### Task 2: Infrastruktura pomocy (rejestr, F1, panel, Shift+F1, opóźnienie, pokrycie)

**Goal:** `gui/help.py` + pakiet `gui/help_content/` z tematami ogólnymi; F1 = pomoc kontekstowa zamiast okna
skrótów.

**Files:**
- Create: `src/algopalette/gui/help.py`, `src/algopalette/gui/help_content/{__init__,general,concepts,window,palette,conditions,globals,proposals,source,analysis}.py`
  (moduły obszarów T3–T7 tworzone jako `TOPICS: dict[str, Topic] = {}`), `tests/gui/test_help.py`
- Modify: `src/algopalette/gui/app.py` (usunąć `HELP_TEXT` i `action_help`-QMessageBox; `self.help =
  help.install(self)`; menu Pomoc: „Pomoc (F1)”, „Pierwsze kroki”, „Skróty klawiszowe”, „Kliknij, by zobaczyć
  pomoc (Shift+F1)”; `QMenu.setToolTipsVisible(True)` dla wszystkich menu), `run()` → `install_tooltip_style`.

**Acceptance Criteria:**
- [ ] `general.py`: `general.start` („Pierwsze kroki” — typowy przebieg pracy w programie: nastrój → warunki →
      generowanie → przejęcie → eksport), `general.shortcuts` (pełna treść dawnego `HELP_TEXT` jako tabela
      Markdown), `general.help` (jak działa sama pomoc: podpowiedzi, F1, Shift+F1, wyszukiwarka).
      `concepts.py`: `concept.oklch`, `concept.delta_e`, `concept.contrast` (WCAG 2.1 i APCA), `concept.cvd`,
      `concept.gamut`, `concept.hard_soft`, `concept.sources` (źródła wartości nastrój/globalne/własne). Każdy
      temat pojęciowy krótki (body ≤ ~120 słów) i mówi, gdzie w programie to pojęcie występuje.
- [ ] F1 rozstrzyga klucz wg speca (cel 6); drugi F1 na tym samym temacie chowa panel; brak klucza → spis treści.
- [ ] Panel: wyszukiwarka (bez diakrytyków/wielkości liter), drzewo wg `GROUPS`, `QTextBrowser` z linkami
      `help:` (klik nawiguje w panelu, nie otwiera przeglądarki), wstecz/dalej, odczepialny.
- [ ] Shift+F1: kursor `WhatsThisCursor`, następny klik lewym przyciskiem NIE trafia do widżetu, tylko otwiera
      jego temat; Esc wychodzi bez akcji.
- [ ] `uncovered(root)` zgłasza interaktywne widżety (`QAbstractButton`, `QComboBox`, `QLineEdit`,
      `QAbstractSlider` poza `QScrollBar`, `QAbstractItemView`, `QTextEdit/QPlainTextEdit`, `widgets.Bar`) i
      `QLabel` z niepustym tekstem bez własnego klucza (ani `children=True` od przodka, ani `decorative`);
      pomija wnętrza `QComboBox`/`QAbstractSpinBox`/`QAbstractItemView`/`QTabBar`/`QToolBar`-rozszerzeń oraz
      sam panel pomocy; dla `QAbstractItemView` z nagłówkiem wymaga klucza dla każdej widocznej kolumny.
- [ ] Wszystkie linki `help:` w `TOPICS` wskazują istniejące klucze; każdy temat ma niepuste `short`
      (≤ 200 znaków) i `body`; `group in GROUPS`.

**Verify:** `uv run pytest tests/gui -q` → zielone; ruff/format/ty → zero uwag.

**Steps:**

- [ ] **Step 1: testy** w `tests/gui/test_help.py`:
  - `test_topics_wellformed` — dla każdego tematu: `short` 1..200 znaków, `body` niepuste, `group in GROUPS`,
    każdy `help:klucz` z body istnieje w `TOPICS`.
  - `test_attach_unknown_key_raises` — `attach(QPushButton(), "nie.ma")` → `KeyError`.
  - `test_tooltip_html` — zawiera tytuł, `short` i „F1 — więcej”.
  - `test_key_at_walks_ancestors(qtbot)` — kontener z kluczem `general.start`, w nim `QLabel` bez klucza →
    `key_at(środek etykiety) == "general.start"`.
  - `test_key_at_tab_and_header(win)` — środek zakładki „Globalne” na `QTabBar` → klucz z `attach_tab`; środek
    sekcji nagłówka tabeli z `attach_header` → klucz kolumny (w teście sam podepnij klucze z `general.*`).
  - `test_f1_opens_and_toggles(win)` — `help_here()` z fokusem na widżecie z kluczem → panel `not isHidden()`,
    `current_key` ten klucz; drugie `help_here()` → panel ukryty; bez klucza → spis treści.
  - `test_search_diacritics` — `search("jasnosc")` znajduje temat zawierający „jasność”, `search("ZRODLO")` →
    temat z „źródło”; w tym teście użyj tematów ogólnych (`concept.*`, `general.*`) lub dodaj tymczasowe przez
    `monkeypatch.setitem(TOPICS, …)`.
  - `test_link_navigates_in_panel(win)` — `anchorClicked(QUrl("help:concept.gamut"))` → `current_key ==
    "concept.gamut"`; wstecz → poprzedni.
  - `test_click_mode_swallows_click(win, qtbot)` — tryb Shift+F1, klik w `QPushButton` z kluczem i podpiętym
    licznikiem `clicked` → licznik 0, panel na temacie przycisku; Esc w trybie → wyjście, panel bez zmian.
  - `test_uncovered_reports_and_respects_decorative(qtbot)` — widżet z `QPushButton` bez klucza i `QLabel("x")`
    oznaczonym `decorative` → raport wymienia tylko przycisk; `attach(slider, k, children=True)` pokrywa
    `NumEdit` wewnątrz `ValueSlider`.
  - `test_tooltip_delay` — `QApplication.style().styleHint(SH_ToolTip_WakeUpDelay) == 300` po
    `install_tooltip_style`.
- [ ] **Step 2: implementacja** wg interfejsów. Normalizacja wyszukiwania: `unicodedata.normalize("NFKD")` bez
  znaków łączących + `ł→l`, `casefold()`. Panel domyślnie ukryty, `Qt.RightDockWidgetArea`, szerokość startowa
  ~360 px. Podpowiedzi tematów pojęciowych/ogólnych pisz wg Global Constraints.
- [ ] **Step 3:** testy, ruff, ty → zero uwag.
- [ ] **Step 4: commit** `feat(gui): infrastruktura pomocy — podpowiedzi, F1, panel Pomocy, Shift+F1`.

```json:metadata
{"files": ["src/algopalette/gui/help.py", "src/algopalette/gui/help_content/__init__.py", "src/algopalette/gui/help_content/general.py", "src/algopalette/gui/help_content/concepts.py", "src/algopalette/gui/app.py", "tests/gui/test_help.py"], "verifyCommand": "uv run pytest tests/gui -q", "acceptanceCriteria": ["tematy ogólne i pojęciowe", "F1 wg speca, toggle, spis treści", "panel: szukanie bez diakrytyków, drzewo, linki help:, wstecz/dalej", "Shift+F1 połyka klik", "uncovered() zgodnie z regułą", "linki help: poprawne"], "modelTier": "frontier"}
```

### Task 3: Treść — okno, menu, pasek narzędzi, panel naruszeń, zakładki

**Goal:** Klucze `window.*`/`menu.*` dla wszystkich akcji (menu i pasek), zakładek, panelu naruszeń (tabela +
każda kolumna + tytuł), podmenu Motyw, menu Pomoc.

**Files:**
- Modify: `src/algopalette/gui/app.py`, `src/algopalette/gui/help_content/window.py`
- Test: `tests/gui/test_help_window.py`

**Acceptance Criteria:**
- [ ] Każda `QAction` w `menuBar()` i na pasku narzędzi ma klucz (sprawdzane iteracją po menu, w tym podmenu).
- [ ] Każda zakładka ma klucz (temat zakładki = co tam robisz i kiedy tam iść).
- [ ] `uncovered(win)` z pominięciem wnętrza `win.tabs` (zakładki to T4–T7) == `[]`.
- [ ] Temat panelu naruszeń wyjaśnia ✗/~, kolumny, że liczone na kolorach po dopasowaniu do gamutu, i jak
      z nich przejść do poprawki (link do `cond.*`/`concept.hard_soft`).

**Verify:** `uv run pytest tests/gui/test_help_window.py -q` → zielone; ruff/ty → zero uwag.

**Steps:**
- [ ] **Step 1: test** `test_window_actions_and_tabs_covered(win)`, `test_window_uncovered_outside_tabs(win)`.
- [ ] **Step 2:** treść + `attach`/`attach_tab`/`attach_header` w `app.py`.
- [ ] **Step 3:** testy, ruff, ty. **Step 4: commit** `feat(gui): pomoc — okno, menu, naruszenia`.

```json:metadata
{"files": ["src/algopalette/gui/app.py", "src/algopalette/gui/help_content/window.py", "tests/gui/test_help_window.py"], "verifyCommand": "uv run pytest tests/gui/test_help_window.py -q", "acceptanceCriteria": ["każda akcja menu/paska ma klucz", "każda zakładka ma klucz", "uncovered poza zakładkami pusty", "temat naruszeń kompletny"], "modelTier": "standard"}
```

### Task 4: Treść — zakładka Paleta + warunki + zależności

**Goal:** Klucze `palette.*` (tabela kolorów + każda kolumna w OBU widokach OKLCH/HSL, przyciski pod listą,
przełącznik widoku, edytor: nazwa/rola/kłódka/suwaki wartości L/C/H i H/S/L, sekcje), `cond.<field>` dla
każdego z 8 pól warunku (+ wspólne elementy wiersza: włącz, twardy/miękki, waga, ↺ dziedzicz, plakietka źródła),
`rel.*` dla każdego typu zależności i elementów wiersza.

**Files:**
- Modify: `src/algopalette/gui/palette_tab.py`, `src/algopalette/gui/conditions.py`,
  `src/algopalette/gui/relations.py`, `src/algopalette/gui/widgets.py` (tylko jeśli potrzebne pomocniki),
  `src/algopalette/gui/help_content/palette.py`, `src/algopalette/gui/help_content/conditions.py`
- Test: `tests/gui/test_help_palette.py`

**Acceptance Criteria:**
- [ ] `uncovered(win.palette_tab) == []` dla zaznaczonego koloru każdej roli (tło, tekst, akcent), z warunkiem
      każdego z 8 typów dodanym/włączonym i z zależnością każdego typu, w widoku OKLCH i HSL.
- [ ] Po dodaniu akcentu, Ctrl+Z, Ctrl+Y i przełączeniu F7 — nadal `[]` (Review Focus 4).
- [ ] Teksty `cond.*` rozwijają `forms.DESCRIPTIONS` o: wpływ na silnik (twarde = granice/kara, miękkie = cel
      z wagą), dziedziczenie, przykłady wartości; `DESCRIPTIONS` może pozostać (TUI) — nie usuwać.

**Verify:** `uv run pytest tests/gui/test_help_palette.py -q` → zielone; ruff/ty → zero uwag.

**Steps:**
- [ ] **Step 1: testy** `test_palette_covered_each_role_and_view`, `test_conditions_each_field_covered`,
  `test_relations_each_kind_covered`, `test_palette_covered_after_undo_redo_add` — wszystkie przez
  `uncovered(...) == []` (komunikat asercji = lista).
- [ ] **Step 2:** treść + `attach` przy konstrukcji wierszy/kontrolek.
- [ ] **Step 3:** testy, ruff, ty. **Step 4: commit** `feat(gui): pomoc — Paleta, warunki, zależności`.

```json:metadata
{"files": ["src/algopalette/gui/palette_tab.py", "src/algopalette/gui/conditions.py", "src/algopalette/gui/relations.py", "src/algopalette/gui/widgets.py", "src/algopalette/gui/help_content/palette.py", "src/algopalette/gui/help_content/conditions.py", "tests/gui/test_help_palette.py"], "verifyCommand": "uv run pytest tests/gui/test_help_palette.py -q", "acceptanceCriteria": ["uncovered(palette_tab) pusty dla każdej roli i widoku", "pokrycie po add/undo/redo/F7", "cond.* rozwinięte o wpływ na silnik"], "modelTier": "frontier"}
```

### Task 5: Treść — zakładka Globalne

**Goal:** Klucze `globals.*` dla każdej kontrolki zakładki Globalne (nastrój, polaryzacja, metryki, układ odcieni,
rozrzut jasności, daltonizm, gamut/fit, optymalizator, domyślne warunki ról — nagłówki sekcji ról).

**Files:**
- Modify: `src/algopalette/gui/globals_tab.py`, `src/algopalette/gui/help_content/globals.py`
- Test: `tests/gui/test_help_globals.py`

**Acceptance Criteria:**
- [ ] `uncovered(win.globals_tab)` z pominięciem poddrzew `ConditionsEditor` (to T4; całość sprawdza T8) == `[]`.
- [ ] Każda opcja list wyboru (nastroje, układy odcieni, metody fit, typy daltonizmu, metryki) opisana w body
      tematu tej listy — co zmienia w wynikach.

**Verify:** `uv run pytest tests/gui/test_help_globals.py -q` → zielone; ruff/ty → zero uwag.

**Steps:**
- [ ] **Step 1: test** `test_globals_covered` (pomijanie `ConditionsEditor` przez filtr wyniku po przodkach).
- [ ] **Step 2:** treść + `attach`. **Step 3:** testy, ruff, ty.
- [ ] **Step 4: commit** `feat(gui): pomoc — Globalne`.

```json:metadata
{"files": ["src/algopalette/gui/globals_tab.py", "src/algopalette/gui/help_content/globals.py", "tests/gui/test_help_globals.py"], "verifyCommand": "uv run pytest tests/gui/test_help_globals.py -q", "acceptanceCriteria": ["uncovered(globals_tab) poza ConditionsEditor pusty", "opcje list opisane w body"], "modelTier": "standard"}
```

### Task 6: Treść — zakładki Propozycje i Źródło

**Goal:** Klucze `proposals.*` (generowanie, stop, lista/paski propozycji, przejęcie całej palety / pojedynczego
koloru, stan silnika, liczniki naruszeń propozycji) i `source.*` (pole wklejania, wczytanie z pliku, wynik
parsowania, trzy tryby startu: uzupełnij / charakter / przenieś — co każdy robi z sesją).

**Files:**
- Modify: `src/algopalette/gui/proposals_tab.py`, `src/algopalette/gui/source_tab.py`,
  `src/algopalette/gui/help_content/proposals.py`, `src/algopalette/gui/help_content/source.py`
- Test: `tests/gui/test_help_proposals_source.py`

**Acceptance Criteria:**
- [ ] `uncovered(win.proposals_tab) == []` przed generowaniem i PO otrzymaniu wyników (silnik na
      `default_session`, czekanie `qtbot.waitUntil`, timeout ≤ 30 s).
- [ ] `uncovered(win.source_tab) == []` przed i po wklejeniu poprawnej i błędnej palety.

**Verify:** `uv run pytest tests/gui/test_help_proposals_source.py -q` → zielone; ruff/ty → zero uwag.

**Steps:**
- [ ] **Step 1: testy** `test_proposals_covered_before_and_after`, `test_source_covered_ok_and_error`.
- [ ] **Step 2:** treść + `attach` (także przy budowie wierszy wyników). **Step 3:** testy, ruff, ty.
- [ ] **Step 4: commit** `feat(gui): pomoc — Propozycje i Źródło`.

```json:metadata
{"files": ["src/algopalette/gui/proposals_tab.py", "src/algopalette/gui/source_tab.py", "src/algopalette/gui/help_content/proposals.py", "src/algopalette/gui/help_content/source.py", "tests/gui/test_help_proposals_source.py"], "verifyCommand": "uv run pytest tests/gui/test_help_proposals_source.py -q", "acceptanceCriteria": ["proposals pokryte przed i po wynikach", "source pokryte przy ok i błędzie"], "modelTier": "standard"}
```

### Task 7: Treść — zakładka Analiza

**Goal:** Klucze `analysis.*`: koło odcieni, przekrój L–C, każda macierz (ΔE, kontrast, wersje CVD) z nagłówkami,
próbki „Aa”, przełączniki/listy zakładki; jak czytać każdy wykres i co z tego wynika dla warunków.

**Files:**
- Modify: `src/algopalette/gui/analysis_tab.py`, `src/algopalette/gui/help_content/analysis.py`
- Test: `tests/gui/test_help_analysis.py`

**Acceptance Criteria:**
- [ ] `uncovered(win.analysis_tab) == []` po `refresh_from_session()`, przy każdej wartości przełączników zakładki
      (np. typ CVD).
- [ ] Nagłówki macierzy (dynamiczne — nazwy kolorów) mają klucz macierzy.

**Verify:** `uv run pytest tests/gui/test_help_analysis.py -q` → zielone; ruff/ty → zero uwag.

**Steps:**
- [ ] **Step 1: test** `test_analysis_covered_each_mode`. **Step 2:** treść + `attach`.
- [ ] **Step 3:** testy, ruff, ty. **Step 4: commit** `feat(gui): pomoc — Analiza`.

```json:metadata
{"files": ["src/algopalette/gui/analysis_tab.py", "src/algopalette/gui/help_content/analysis.py", "tests/gui/test_help_analysis.py"], "verifyCommand": "uv run pytest tests/gui/test_help_analysis.py -q", "acceptanceCriteria": ["uncovered(analysis_tab) pusty w każdym trybie", "nagłówki macierzy z kluczem"], "modelTier": "standard"}
```

### Task 8: Integracja — pokrycie całości, zrzuty obu motywów, dokumentacja

**Goal:** Test pokrycia całego okna bez wyłączeń, przegląd wzrokowy, README + HANDOFF.

**Files:**
- Create: `tests/gui/test_help_coverage.py`
- Modify: `README.md` (motyw, pomoc: F1/Shift+F1, panel), `HANDOFF.md`

**Acceptance Criteria:**
- [ ] `test_whole_window_covered` — dla każdej zakładki (aktywnej), każdej roli zaznaczonej na Palecie, obu widoków
      i obu motywów: `uncovered(win) == []`.
- [ ] `test_every_topic_reachable` — każdy klucz z `TOPICS` jest podpięty do jakiegoś elementu ALBO linkowany
      z innego tematu ALBO dostępny z menu Pomoc.
- [ ] Zrzuty (`win.grab().save`) wszystkich zakładek + panel pomocy, jasny i ciemny, obejrzane (Read na PNG);
      nieczytelności naprawione.
- [ ] Pełny `uv run pytest -q`, `ruff check`, `ruff format --check`, `ty check` — zero uwag; liczby wpisane do
      HANDOFF.

**Verify:** `uv run pytest -q` → wszystkie zielone (liczba w HANDOFF).

**Steps:**
- [ ] **Step 1:** testy całości. **Step 2:** zrzuty → poprawki. **Step 3:** README/HANDOFF.
- [ ] **Step 4: commit** `test(gui): pokrycie pomocą całego okna; docs: README, HANDOFF`.

```json:metadata
{"files": ["tests/gui/test_help_coverage.py", "README.md", "HANDOFF.md"], "verifyCommand": "uv run pytest -q", "acceptanceCriteria": ["uncovered(win) pusty we wszystkich stanach", "każdy temat osiągalny", "zrzuty obu motywów obejrzane", "pełna weryfikacja zero uwag"], "modelTier": "standard"}
```

## Po planie

Przegląd całości (Opus, effort xhigh) wg CLAUDE.md użytkownika — w tym zgodność treści pomocy z kodem; pętla
napraw wg reguł; potem scalenie `gui` → `main` (decyzja użytkownika).
