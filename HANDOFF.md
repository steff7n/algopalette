# HANDOFF — AlgoPalette

Dla agenta, który przejmie pracę bez tej rozmowy. Sekcja 0 = stan na teraz. Niżej decyzje, pułapki, mapa, dziennik.

## 0b. TRYB CIEMNY + POMOC KONTEKSTOWA (2026-11-15) — W TOKU, gałąź `gui`

- Prośba: „wprowadź proszę tryb ciemny do tego GUI, Wyjaśnij każdą pojedynczą rzecz wewnątrz aplikacji poprzez
  szybkie tooltipy z możliwością rozwinięcia do bardziej rozbudowanej zakładki pomocy. Czytelność, przejrzystość
  i wygoda użytkownika jest wszystkim”.
- **Decyzje użytkownika (wiążące, nie otwieraj ponownie):** wariant 1 — podpowiedź „F1 — więcej”, F1 nad elementem
  otwiera pomoc na temacie (spis treści + wyszukiwarka); „na końcu wszystko scal” (→ `gui` do `main` po przeglądzie);
  „skup się w pomocy na tym, jak działa program, nie na tym, jak działa kolor. na ten temat również napisz, ale
  relatywnie mniej”. Projekt zaakceptowany „tak”.
- Spec: `docs/superpowers/specs/2026-11-15-gui-dark-mode-help-design.md`. Plan: `docs/superpowers/plans/
  2026-11-15-gui-dark-mode-help.md` + `.tasks.json` (8 zadań; natywne zadania #1–#8).
- Kolejność: {T1 motyw, T2 infrastruktura pomocy} równolegle → {T3 okno, T4 Paleta+warunki+zależności,
  T5 Globalne, T6 Propozycje+Źródło, T7 Analiza} równolegle (rozłączne pliki, treść w osobnych modułach
  `gui/help_content/<obszar>.py`) → T8 integracja (pokrycie całego okna, zrzuty obu motywów, README).
  Potem JEDEN przegląd całości (Opus xhigh), pętla napraw wg CLAUDE.md, scalenie do `main`.
- **Wykonanie (decyzja użytkownika 2026-11-15): „implementuj całość samodzielnie. na koniec review z opusem xhigh,
  pojedyncze.”** → kontroler robi T1–T8 sam, sekwencyjnie, bez subagentów-implementatorów; jeden przegląd na końcu.
- Stan zadań: (aktualizowany po każdym zadaniu niżej)
- **T1 ☑ motyw**: `gui/theme.py` — `ThemeMode`, `LIGHT`/`DARK` (`Colors`; `badge` = JEDEN kolor tekstu+ramki na
  źródło, nie para tło/tekst jak w planie — plakietki są obrysowane, bez tła), `load_mode/save_mode/initial_mode`
  (`gui.json` w `config_dir()`, zapis atomowy, inne klucze zachowane), `apply(app, mode)` ustawia TYLKO paletę
  (styl Fusion raz w `run()` — `setStyle` w `apply` zgubiłby proxy-styl podpowiedzi z T2), `notifier.changed`,
  „system” śledzi `colorSchemeChanged`. Kolory w arkuszach stylu WYŁĄCZNIE przez `mark_error(w, bad, selector)` /
  `mark_text(w, kind, bold)` / `style_badge(w, src)` — dynamiczne właściwości Qt, `restyle_all()` przemalowuje je
  przy zmianie motywu. Kolory w `QTableWidgetItem` i rysunkach biorą `theme.colors()` przy budowie;
  `MainWindow._theme_changed` przebudowuje naruszenia, Paletę i bieżącą zakładkę. Menu Widok → Motyw
  (`act_theme_system/light/dark`, `set_theme`). Celowo zostały hexy: pierścienie punktów w Analizie (biało-czarne,
  czytelne na każdym tle), placeholder w Źródle, domyślny `Swatch`. Testy: `tests/gui/test_theme.py` 13;
  `tests/gui` 53 passed; ruff/ty zero uwag. Bazowo przed zmianami cały pytest: 336 passed.
- **T2 ☑ infrastruktura pomocy**: `gui/help.py` — `attach(obj, key, children=, extra=)` (właściwość `help_key` +
  podpowiedź HTML „tytuł / short / [extra] / F1 — więcej”; `extra` = dopisek kontekstowy, np. hex próbki — NIE
  nadpisuj potem `setToolTip` gołym tekstem, bo zniknie opis), `attach_header(view, keys|str, vertical=)` —
  klucze trzymane na WIDOKU (`help_columns`/`help_rows`), podpowiedź sekcji przez filtr zdarzeń na viewport
  nagłówka → przeżywa `setHorizontalHeaderLabels`; `attach_tab`, `decorative`, `key_at`, `key_for_focus`,
  `uncovered(root)`: wymaga klucza od QAbstractButton/QComboBox/QLineEdit/QAbstractSlider(bez QScrollBar)/
  QAbstractItemView (+ każda widoczna kolumna)/QTextEdit/QPlainTextEdit/QLabel z tekstem/własnych widżetów
  `algopalette.*` z fokusem; pomija wnętrza QComboBox/QAbstractSpinBox/QAbstractItemView/QTabBar/QMenu/QScrollBar/
  QToolBar, panel pomocy i obiekty `qt_*`. `HelpPanel` (QDockWidget `help-panel`, prawa strona, ukryty na starcie):
  ◀ ▶ „Spis treści”, wyszukiwarka (`normalize`: NFKD + ł→l + casefold; trafienia w tytule pierwsze), drzewo wg
  `GROUPS`, `QTextBrowser.setMarkdown`, linki `help:klucz` nawigują w panelu. `HelpController`: F1/Shift+F1 jako
  `ApplicationShortcut` (działa też w odczepionym panelu), menu Pomoc (`actions()`), `watch_menus()` — F1 w
  otwartym menu: `ShortcutOverride` przechwycony, inaczej skrót okna zjadłby F1; wyszarzone pozycje menu nie
  dostają `activeAction` → `actionAt(kursor)`. Tryb Shift+F1: filtr na całej aplikacji, połyka press+release,
  klawisze poza Esc ignorowane. Proxy-styl (`install_tooltip_style`, 300 ms) ustawiany w `run()` zamiast
  `setStyle("Fusion")`. Treść: `gui/help_content/` — `topic.py` (`Topic`, `GROUPS`), `general.py`, `concepts.py`
  gotowe; `window/palette/conditions/globals/proposals/source/analysis.py` puste (T3–T7). `HELP_TEXT` i okno
  skrótów usunięte → temat `general.shortcuts`. Ruff: `help_content/*` ma wyłączone E501 (proza).
  Testy: `tests/gui/test_help.py` 18; `tests/gui` 71 passed; ruff/format/ty zero uwag.
- **T3 ☑ okno**: `help_content/window.py` (zakładki `window.tab.*` — w grupach swoich obszarów, menu `menu.*`,
  `window.violations(.values)`, `window.toolbar`); `MainWindow._attach_help()` na końcu `_build_actions`
  (`self.menus` dict, `self.act_tabs`, `self.toolbar`). Akcje listy kolorów (`palette_tab.slot_actions()`) dostają
  klucze w T4. `uncovered(root, skip=[...])` — poddrzewa sprawdzane osobno. Testy: `test_help_window.py` 4;
  `tests/gui` 75 passed.
- **T4 ☑ Paleta + warunki + zależności**: `help_content/palette.py` (`palette.list`, `palette.col.*` — kolumny
  wartości L/C/H i H/S/L mają JEDEN temat `palette.col.values`, `palette.add/remove/lock/move/generate`,
  `palette.editor(.name)`, `palette.value(.l/.c/.h/.hsl)`), `help_content/conditions.py` (`cond.overview/enabled/
  hard/weight/reset/remove/add/badge`, `cond.<8 pól>`, `cond.chroma.mode`, `cond.contrast_bg.metric`, `rel.*`).
  Elementy wspólne dla warunków i zależności (włączony/twardy/waga) używają tych samych tematów `cond.*`.
  `help.attach_form_labels(fl)` — etykiety `QFormLayout.addRow("tekst", pole)` dostają klucz pola. `Swatch.set_hex`
  zachowuje podpowiedź pomocy (z hexem jako `extra`), gdy próbka ma klucz. `ConditionRow`: wszystkie widżety
  siatki wartości bez własnego klucza dostają `cond.<pole>` (children=True). Treść sprawdzona z kodem:
  zależność odcienia = H(ten) − H(cel) najkrótszym łukiem; para akcentów bierze OSTRZEJSZY próg i jest twarda,
  gdy którykolwiek jest; odróżnialność działa tylko dla typów CVD wybranych w Globalnych; akcent z JAKIMKOLWIEK
  warunkiem odcienia (nawet wyłączonym) nie dostaje celu z układu odcieni (`constraints.py:472`); min. 1 akcent.
  Testy: `test_help_palette.py` 9 (wszystkie role, oba widoki, 8 warunków, 6 typów zależności + zerwana,
  add/undo/redo/F7); `tests/gui` 84 passed.
- **T5 ☑ Globalne**: `help_content/globals.py` (`globals.mood(.apply/.delete/.save)`, `globals.metrics/polarity/
  contrast_metric/delta_e/fit`, `globals.hues(.kind/.rotation/.center/.spread/.tol/.jitter/.custom/.hard)`,
  `globals.spread`, `globals.cvd`, `globals.optimizer` + `globals.opt.*`, `globals.avoid`, `globals.roles`).
  W `globals_tab.py`: `group(title, key)` podpina klucz pod `QGroupBox` (F1 gdziekolwiek w sekcji), `keyed(w, key,
  children=)` zwraca widżet. Listy wyboru (nastroje, układy, ΔE, fit, CVD) opisane w body — test pilnuje, że
  każda opcja z `forms`/`moods.BUILTIN` występuje w treści. Testy: `test_help_globals.py` 4; `tests/gui` 88.
  **Uwaga:** commit 60fa271 wszedł z 1 czerwonym testem (`test_search_diacritics` zakładał, że „gamut” trafia
  pierwszy w `concept.gamut`, a „Gamut (fit)” z Globalnych też ma to w tytule) i E501 w teście — naprawione
  w kolejnym commicie; test sprawdza teraz tylko, że trafienia w tytule idą przed resztą. Łańcuchy weryfikacji
  pisz z `&&` aż do commita, nigdy `;`.
- **T6 ☑ Propozycje + Źródło**: `help_content/proposals.py` (`proposals.generate_all/generate_one/cancel/progress/
  status/list/col.*/detail/violations/take_all/take_color`), `help_content/source.py` (`source.colors/paste/parse/
  from_file/from_current/result/swatch/roles/mode(.complete/.character/.transfer)/avoid/transfer_options/apply`).
  `Strip` w komórce tabeli dostaje klucz przy każdym `_fill`. `uncovered` wymaga teraz klucza także od
  `QAbstractSpinBox` (wcześniej spinboxy tło/tekst w Źródle prześlizgiwały się, bo ich wewnętrzny QLineEdit jest
  w nieprzezroczystym rodzicu). Testy: `test_help_proposals_source.py` 2 (z prawdziwym generowaniem i przejęciem;
  odczyt poprawny i błędny); `tests/gui` 90.
- **T7 ☑ Analiza**: `help_content/analysis.py` (`analysis.view/matrix_kind/axis/overview/wheel/lc/matrix.de/
  matrix.contrast/samples`). Macierz i jej tytuł dostają klucz rodzaju macierzy przy każdym `redraw` (i startowo
  `analysis.matrix.de` w `__init__`), nagłówki poziome i pionowe przez `attach_header(..., vertical=True)`.
  Wykresy (`HueWheel`, `LCPlot`, `Samples`) mają NoFocus, więc `uncovered` ich nie wymaga — klucze sprawdza osobny
  test. Testy: `test_help_analysis.py` 2 (wszystkie 4×2×2 kombinacje przełączników); `tests/gui` 92.

## 0a. GUI (2026-11-14, prośba: „przeróbmy to TUI na GUI … potrzebuje prostego, czytelnego GUI”)

- **Domyślny interfejs to GUI w PySide6** (`pyside6-essentials`), pakiet `src/algopalette/gui/`. Stare TUI zostaje
  pod `algopalette --tui` (decyzja agenta: nie kasować działającego TUI, zanim użytkownik sprawdzi GUI ręcznie —
  do usunięcia na jego słowo, razem z zależnością `textual` i `tests/tui`).
- Rdzeń (model, silnik, io, warunki) BEZ zmian. Wspólna, niezależna od biblioteki UI logika formularzy
  (etykiety, domyślne warunki, zakresy suwaków, opcje list, `current_violations`) przeniesiona do
  `src/algopalette/forms.py`; moduły TUI re-eksportują stare nazwy (testy TUI bez zmian).
- Mapa GUI: `gui/app.py` (`MainWindow`: historia + scalanie zmian < 1.5 s, autozapis QTimer 0.5 s + zapis przy
  zamknięciu, menu/pasek, skróty, panel naruszeń w `QSplitter`, `run()` + motyw Fusion; ciemny wg systemu lub
  `ALGOPALETTE_THEME=dark|light`), `gui/widgets.py` (`NumEdit` — Enter/wyjście zatwierdza, puste = brak;
  `Bar` — pasek z 1–2 uchwytami i gradientem koloru liczonym numpy; `ValueSlider`, `RangeSlider`),
  `gui/conditions.py`, `gui/relations.py`, `gui/palette_tab.py`, `gui/globals_tab.py`, `gui/proposals_tab.py`
  (silnik w `threading.Thread`, wyniki sygnałami Qt), `gui/source_tab.py`, `gui/analysis_tab.py` (koło odcieni
  i przekrój L–C rysowane QPainterem na prawdziwych kolorach OKLCH, macierze w `QTableWidget`).
- Skróty zmienione względem TUI: generowanie `Ctrl+G` (nie `g` — litera kolidowałaby z polami tekstowymi);
  lista kolorów `Ins`/`A`, `Del`, `L`, `Alt+↑/↓` (tylko gdy lista ma fokus); `Ctrl+S` zapisuje do bieżącego
  pliku, `Ctrl+Shift+S` jako…; eksport do PB: `Ctrl+E` schowek, `Ctrl+Shift+E` plik; nowe `Ctrl+N` (cofalne).
- **Pułapki Qt (sprawdzone):** stare widżety przy przebudowie idą przez `deleteLater` — w testach
  `QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)` przed `findChild`; widżet dodany do widocznego
  rodzica jest pokazywany dopiero w kolejnym obiegu pętli → w testach `isHidden()`, nie `isVisible()`;
  nie nadpisuj `QWidget.move` (stąd `PaletteTab.move_selected`); przebudowy wywoływane z sygnału dziecka
  odkładaj `QTimer.singleShot(0, …)`. W kontenerze bez GUI potrzebne `libegl1` (apt) i `QT_QPA_PLATFORM=offscreen`.
- Weryfikacja: `tests/gui` (pytest-qt, offscreen) 40 testów; zrzuty wszystkich zakładek obejrzane (jasny i ciemny).
  **NIE sprawdzone:** prawdziwy pulpit użytkownika (Wayland/X11, skalowanie HiDPI, schowek po zamknięciu programu),
  launcher `~/.local/bin/algopalette` po dodaniu zależności — wymaga `uv tool install --editable . --force`.

## 0. STAN NA TERAZ — 2026-11-14: plan WYKONANY (11/11), przegląd całości zrobiony, znaleziska naprawione, SCALONE do `master` (fast-forward, gałąź `feat/algopalette` usunięta); czeka na ręczne testy użytkownika

- Spec `docs/superpowers/specs/2026-11-14-algopalette-design.md` — zaakceptowany słowami „a, to oks. tak, pisz plan”
  (po wyjaśnieniu, że PaletteBuildera nie ruszano; przycisk eksportu do PB ZOSTAJE).
- Plan: `docs/superpowers/plans/2026-11-14-algopalette.md` + `.tasks.json` (11 zadań, natywne zadania #1–#11 z
  zależnościami). Etap 1 = Taski 1–7 (rdzeń), Etap 2 = Taski 8–11 (TUI). Przegląd: JEDEN, całego kodu, na samym końcu, Opus
  effort HIGH; błędy naprawia kontroler sam, BEZ re-review, potem informuje użytkownika (decyzja §2).
- Kolejność: 1 → 2 → 3 → 4 → {5, 6}; 2 → 7; {4,5,6,7} → 8 → {9, 10} → 11.
- Nic nie zainstalowano w projekcie (brak `pyproject.toml` — powstaje w Tasku 1). Zależności sprawdzone tylko w
  jednorazowym `uv run --no-project --with …` (coloraide 8.15, coloraide-extras 1.13, textual 8.2.8, scipy 1.18.1).
- **Przełącznik widoku HSL/OKLCH ☑** (2026-11-14, prośba: „koniecznie dodaj toggle HSL/OKLCH”, zakres zatwierdzony
  „tak, rób”; spec §11): `Session.view_model` (`"oklch"`/`"hsl"`, io: pole opcjonalne, domyślnie oklch),
  `color.to_hsl`/`from_hsl` (HSL koloru PO fit), `palette_tab` (nagłówki kolumn wg widoku — `column_labels`,
  stałe klucze `COLUMN_KEYS`; przebudowa kolumn przy zmianie widoku; suwaki `hsl-h/s/l` w edytorze), Select
  `#view-model` nad tabelą, F7 (`priority=True`). `app.set_view_model` używa `History.replace_current` — NIE krok
  cofania; undo/redo zachowuje bieżący widok (`_keep_view`). Warunki/silnik/Analiza zostają w OKLCH.
  **Bez przeglądu — decyzja użytkownika: „nie odpalaj przypadkiem review na końcu”.**
- Wykonanie: Subagent-Driven w tej sesji, gałąź `feat/algopalette` → scalona do `master` (decyzja użytkownika „możesz
  scalać”). Dziennik kontrolera i raport przeglądu (git-ignored) usunięte po zakończeniu — treść napraw jest niżej.
- **Task 1 ☑** (8e8bf4c, Sonnet): `pyproject.toml` (ruff line 100, reguły E,F,I,UP,B,SIM,RUF; E741/RUF001-003 off;
  pytest asyncio auto), `color/{__init__,apca,fast}.py`, `model.py` (na razie tylko `OKLCH` + aliasy Literal).
  Policzone: pytest **39 passed**, ruff/format/ty zero uwag.
- **Task 2 ☑** (048d506, Sonnet): `model.py` (pełny kontrakt + `FrozenMap`, `default_role_defaults`, `snapshot_key`,
  `History`), `io.py` (`algopalette.v1`, zapis atomowy, XDG). Policzone: pytest **114 passed**, ruff/format/ty zero uwag.
- **Decyzja użytkownika 2026-11-14:** zadania tworzą łańcuch zależności → od Tasku 3 kontroler implementuje WSZYSTKO
  sam, bez subagentów-implementatorów.
- **Task 3 ☑** (kontroler): `constraints.py` — termy WSADOWE (`Ctx` z tablicą `(B, n, 3)`), `Term.vfn(ctx, margin)` +
  skalarne `Term.fn(values)`; `evaluate`, `objective`, `objective_batch(margin_frac)`. Brettel dodany do `fast.py`.
  Policzone: pytest **141 passed**, ruff/format/ty zero uwag.
- **Task 4 ☑** (kontroler): `engine.py` — zmienne wolnego slotu `(L, u, H)`, `C = u·maxC(L,H)` (kolor ZAWSZE w sRGB),
  twarde zakresy L / nasycenia względnego / odcienia = granice zmiennych; losowanie wsadowe → 4 starty → L-BFGS-B z
  gradientem różnic skończonych w JEDNYM wywołaniu wsadowym; margines twardych = 0.5 × skala; różnorodność = kara
  względem wcześniejszych propozycji (średnie ΔE ok). `apply_proposal(session, p, slot_ids)` do TUI.
  **Zmierzone:** `default_session()` → 6 propozycji, wszystkie `ok`, **2.07 s**; 14 akcentów + 2 typy CVD ≈ 2 s na
  propozycję (~12 s za 6). Domyślny `time_cap_s` podniesiony 10 → 30 s (bezpiecznik, nie budżet).
  Policzone: pytest **155 passed**, ruff/format/ty zero uwag.
- **Task 5 ☑** (kontroler): `hues.py` (`scheme_targets`, `targets_for_session`; reguła cykliczna z planu),
  `moods.py` (9 wbudowanych, nastroje użytkownika w `config_dir()/moods.json`, `apply_mood` resetuje część
  nastrojową do `default_role_defaults` i nakłada nadpisania, snapshot obejmuje WSZYSTKIE pola ról + `hue_scheme` +
  `lightness_spread`). Silnik: `hue_targets_for` → `hues.targets_for_session`; wczesne wyjście, gdy cel ≈ 0
  (`SOLVED`), `ftol` 1e-6. **Zmierzone:** default 6 propozycji ok w **1.5–1.7 s** (bez wczesnego wyjścia było 5–6 s,
  bo miękkie cele odcieni zabierały cały budżet każdego startu). Policzone: pytest **200 passed**, ruff/ty zero uwag.
- **Task 6 ☑** (kontroler): `sources.py` — `parse_colors` (≤16, `ParseError.token`), `apply_complete` (kłódki, sloty
  dokładane), `extract_profile`/`cluster_hues` (aglomeracja ważona C, łączenie < 25°), `apply_character` (custom
  odcienie POWTARZANE do 14, żeby reguła cykliczna nie rozsuwała ich po kole; zakresy z p10–p90 poszerzone),
  `apply_transfer` (każdy akcent: cel H ± 8° twardy, C względne ± 0.08, kontrast z nowym tłem = źródłowy ± tol;
  lightness wyłączone `Cond(..., enabled=False)`, bo wynika z kontrastu; liczba akcentów = źródła).
  Policzone: pytest **212 passed**, ruff/ty zero uwag.
- **Task 7 ☑** (kontroler): `pb_export.py` — `pb_json(hexes, polarity)` (`palettebuilder.v3`, `polarity`, `palette`
  `[{hex, role}]`; NIC więcej nie trzeba), `write_pb_file` (atomowo, bez nadpisania bez zgody), `default_pb_dir()` =
  `~/Dokumenty/motifs`. **Dowód akceptacji przez PB** (node, `loadPB` z `/home/qrikk/palettebuilder/tests/headless.mjs`,
  skrypt tylko w scratchpadzie): `detect` → `palette`, `parse` (icls) → null, `motif()` nie-null z tymi samymi hexami,
  `PB.state.importTheme` → paleta 1:1, `lang` domyślnie `java`; `git status` PB przed == po („PB status unchanged”).
  Ścieżka wklejenia w oknie „Wczytaj…” PB (`index.html:8733`): parse(icls) → vscode → `motif()` → hexy.
  Policzone: pytest **216 passed**, ruff/ty zero uwag. **Etap 1 (rdzeń) zakończony.**
- **Task 8 ☑** (kontroler): TUI (Textual). `__main__.py` (`algopalette [PLIK] [--fresh]`, start: plik → autozapis →
  `default_session` + nastrój „neutralny”; błędy → komunikat, nie wyjątek). `tui/app.py` (`AlgoPaletteApp`:
  `set_session(new, coalesce=, structural=)`, historia z scalaniem zmian tego samego pola < 1.5 s,
  `replace_session`, `refresh_views`, autozapis z opóźnieniem 0.5 s, `ViolationsPanel`, zapis/wczytanie przez
  `PathScreen` + `ConfirmScreen`, F1 pomoc, F2–F6 zakładki), `tui/palette_tab.py` (`SlotTable` aktualizowana W MIEJSCU,
  gdy zestaw slotów ten sam — inaczej `clear()` przestawia zaznaczenie i edytor traci fokus; `SlotEditor`: nazwa,
  kłódka, ręczne L/C/H, warunki, zależności), `tui/conditions.py` (`ConditionsEditor(mode="slot"|"role")` — wspólny
  z zakładką Globalne), `tui/relations.py`, `tui/widgets.py` (`ValueSlider`, `RangeSlider`, `_Bar`), `tui/dialogs.py`.
  `History.replace_current` dodane do modelu. Zrzuty ekranu obejrzane (150×48).
  Policzone: pytest **240 passed** (w tym 23 TUI), ruff/ty zero uwag.
- **Task 9 ☑** (kontroler): `tui/globals_tab.py` (nastroje + własne, polaryzacja/metryka → `change_polarity_or_metric`
  przelicza domyślne zakresy lub nakłada nastrój ponownie, ΔE, fit, układ odcieni, rozrzut L, CVD, optymalizator,
  unikanie, `ConditionsEditor("role", …)` w `Collapsible`), `tui/proposals_tab.py` (worker `@work(thread=True)`,
  postęp, przerwanie, przejmij całą / kolor, generowanie tylko wybranego slotu), `tui/source_tab.py` (wklejanie,
  z pliku sesji, z bieżącej palety, 3 tryby). `app.action_generate` (g), `action_export` (Ctrl+E: schowek OSC 52 +
  opcjonalny plik w `~/Dokumenty/motifs`). Zakładki odświeżają się przy aktywacji (`TabActivated`) i przy zmianach
  strukturalnych; Globalne przebudowuje się tylko, gdy sesja ≠ ostatnio pokazana (`_shown`), własne edycje ją
  aktualizują. `Switch` zastąpione kompaktowymi `Checkbox`, przyciski `compact=True`.
  Policzone: pytest **254 passed** (w tle, 104 s), ruff/ty zero uwag.
- **Task 10 ☑** (kontroler): `tui/analysis_tab.py` — czyste funkcje (sesja → Rich Text): `hue_wheel` (0° po prawej,
  90° u góry, promień = C względne, łuki zakresu/celu odcienia zaznaczonego slotu), `lc_plot` (L ↑, C wzgl./bezwzgl.),
  `de_matrix` (ΔE akcentów metodą globalną, czerwone poniżej wymaganej; widoki normalny/protan/deutan/tritan),
  `samples` („Aa” na tle). Zakładka F6, odświeżana przy aktywacji. Zrzut obejrzany (150×52).
  Policzone: pytest **264 passed** (w tle), ruff/ty zero uwag.
- **Task 11 ☑**: `README.md` (po polsku, z „czego nie robić”), `uv tool install --editable .` → jedyna kopia
  `~/.local/bin/algopalette` (edytowalna: zmiany w `src/` działają bez reinstalacji; nowa zależność → reinstalacja).
  `algopalette --help` działa. **Wszystkie 11 zadań planu ☑.**
- **Przegląd całości (Opus effort high) ☑ — 5 Critical / 8 Important / 14 Minor; WSZYSTKIE naprawione przez
  kontrolera, BEZ re-review (decyzja użytkownika).** Raport (git-ignored, zniknie):
  `.superpowers/sdd/2026-11-14-algopalette/final-review.md`. Naprawy:
  C1 relacja odcienia ≥/≤ liniowo na łuku (było podwójne zawijanie → połowa koła „spełniona”);
  C2 `widgets.parse_finite` (inf/nan/1e999 odrzucane wszędzie, `-bad`), zapis łapie też ValueError;
  C3 ziarno ≥ 0 w TUI i io, `engine.seed_entropy`/`hues` maskują ujemne (stare pliki nie wywracają);
  C4 nastrój użytkownika przywraca SWOJĄ polaryzację i metrykę; `globals_logic.change_polarity_or_metric`
  nakłada ponownie tylko nastroje wbudowane (użytkownika → zdjęty, domyślne zakresy);
  C5 `action_quit` zapisuje zaległy autozapis;
  I1 `units.py` (skale ΔE względem ok: hyab 1.3, 2000 156, itp 426, cam16 156 — zmierzone; WCAG↔APCA tabela) —
  zmiana metody ΔE / metryki przelicza progi ról, slotów i relacji; nowe warunki/relacje mają domyślne w bieżących
  jednostkach; I2 kalibracja przybliżenia ΔE dla WSZYSTKICH par slotów; I3 twardy układ odcieni = granice H,
  starty losowane przy celu układu, wygaszanie odcienia nie działa poniżej twardej dolnej granicy C
  (`constraints._chroma_floors`) → wszystkie 9 nastrojów 6/6 ok (było „monochromatyczny” 1/6); I4 kryterium
  stagnacji (`STALL_FRAC`), domyślny `max_evals` 20 000 → 8 000 (najwolniejsze nastroje ~3.8 s, 24/24 ok);
  I5 Źródło czyta tekst ponownie, gdy go zmieniono; I6 `Proposal.slot_ids` — „przejmij całą” tylko te sloty;
  I7 start nie z autozapisu → stary autozapis przeniesiony do `last.prev.json` (uszkodzony: `last.corrupt-*.json`);
  I8 ocena (panel, silnik) na kolorach po fit (`color.fitted`); M1 kłódka klawiszem odświeża edytor; M2 walidacja
  `moods.json`; M3 io: L∈[0,1], h mod 360, metryka relacji zgodna z rodzajem, t∈[0,1], ziarno ≥ 0; wykres L–C
  przycięty; M4 widok CVD bez włączonego typu niczego nie oznacza; M5 macierz kontrastu par (przełącznik);
  M6 `⚠0.042` = o ile ΔE ściągnięto do gamutu; M7 charakter przejmuje poziom kontrastu źródła (p10, fg);
  M8 mały budżet respektowany; M9 Ctrl+E `priority=True`; M10 360 w górnym uchwycie zakresu = pełne koło;
  M11 `encode` rozwija odcień przed przycięciem; M12 postęp przez `call_from_thread(self._set_progress)`;
  M13 potwierdzenie nadpisania domyślnie „Nie”; M14 testy tautologiczne zastąpione, dopisane testy do C1–C5, I1, I2,
  I5, I6, I8, M4, M10, M13.
  **NIE zrobione (spec, nie błędy):** suwaki dla wag/tolerancji/pól optymalizatora (są zwykłe pola liczbowe);
  opcjonalny fallback schowka `wl-copy`.

## 1. O co najłatwiej się potknąć

- **Nie dodawaj podglądu kodu ani niczego „IDE-owego”.** Użytkownik wprost: „podglad kodu jest calkowicie
  niepotrzebny. to ma byc program do palet, a nie drugi IDE-owy palettebuilder”.
- **Dwa niezależne programy, PB tylko jako cel eksportu, NIGDY jako źródło.** Agent proponował podpisy ról tokenów PB,
  czytanie plików `~/Dokumenty/motifs` i zachowywanie przypisań PB. Użytkownik (zirytowany, „powtarzam jeszcze raz”):
  „to maja byc dwa niezalezne programy z DODATKOWA funkcjonalnoscia przenoszenia palety z algopalette bezposrednio do
  plettebuilder. w druga strone nigdy. nie skupiaj sie tak na tym.” Nie projektuj niczego wokół PB poza akcją
  „Przenieś do PaletteBuildera” (spec §9).
- **APCA nie istnieje w coloraide 8.15 ani coloraide-extras 1.13** (`contrast(method="apca")` → ValueError). Nie ma też
  paczek PyPI `apca`, `apca-w3`, `pyapca`, `apcach`. Implementacja własna (spec §3, wektory testowe tam).
- coloraide: `ColorAll` z `coloraide.everything` ma ΔE `cam16` itd. Metoda ΔE `z` nie istnieje. Kontrast WCAG to `wcag21`.
- PaletteBuilder (`/home/qrikk/palettebuilder`) to CUDZY projekt w sensie tego repo. **Nie modyfikuj go** (nie-cel
  w specu). Czytaj tylko.
- Rachunek zawsze w OKLCH/OKLab. Losowanie/odległości w RGB/HSL to anty-cel.
- **Skale ΔE są różne**: `ok` i `hyab` (u nas liczony w OKLab!) w skali 0–1, a `2000`/`itp`/`cam16` z coloraide w
  skalach ~0–100+. Progi (`min_distance` itd.) muszą zależeć od metody.
- Wektor z planu `OKLCH(0.75, 0.25, 140)` jest tylko 0.009 poza gamutem (fit ΔE < 0.01) — zastąpiony `C=0.30`
  (plan Task 1 i Task 4 poprawione).
- `simulate_cvd` nie przycina do sRGB (OK dla ΔE, nie dla hexa).
- `ruff format` formatował bloki kodu w `docs/*.md` — od Tasku 2 `extend-exclude = ["docs"]` w `pyproject.toml`.
- `docs/superpowers/plans/*.tasks.json` trzyma statusy zadań; subagent cofnął je raz `git checkout -- docs/` — commituj je.

## 2. Decyzje użytkownika (WIĄŻĄCE — nie otwieraj ponownie)

- Osobna aplikacja TUI w Pythonie, tylko „podpowiadacz kolorów”: „mozesz zrobic osobna apke ktora bedzie skladala sie
  wylacznie z 'podpowiadacza kolorow'”.
- Wynik: własny plik sesji `.json` „do samodzielnego eksperymentowania pozniej” + osobna, jednokierunkowa akcja
  przeniesienia palety do PB (schowek/plik w formacie, który „Wczytaj…” PB przyjmuje). Zastępuje wcześniejszy pomysł
  „jeden plik dla obu programów” — decyzja „dwa niezalezne programy … w druga strone nigdy” (cytat w §1).
- Sterowanie pojedynczym kolorem: zakresy (A) jako podstawa + zależności od innych kolorów (B) jako dodatek —
  „sprobujmy twojej propozycji”.
- Nastroje jako jawne presety ustawień, trzy tryby palety wyjściowej (uzupełnianie/charakter/przeniesienie), daltonizm,
  gamut, wiele propozycji: „wszystko to, co proponujesz jest okej - po prostu zalezy mi na jak najwiekszych
  mozliwosciach konfiguracji”.
- Silnik: optymalizacja całej palety naraz (podejście B) — „idziemy w B”.
- Brak podglądu kodu (cytat w §1).
- Preferencja ogólna: „wole cos trudniejszego w obsludze niz cos dla 10latka”.
- **Komenda zawsze gotowa do uruchomienia** (2026-11-14): „binarka. zawsze. :) czy tam launcher - na jedno wychodzi.”
  Stan: `~/.local/bin/algopalette` → uv tool (instalacja EDYTOWALNA z tego repo; zmiany w `src/` działają od razu).
  Po zmianie zależności w `pyproject.toml` albo przeniesieniu repo: `uv tool install --editable . --force`.
  Po każdej zmianie sprawdź `algopalette --help` spoza repo. Jedna kopia, bez aliasów.
- Przegląd (2026-11-14, nadpisuje CLAUDE.md dla tego projektu): „przeglad calosci kodu robi opus high (nie xhigh) na
  samym koncu. bugi, ktore wylapie, naprawiasz samodzielnie ty. gdy to dobiegnie konca, nie wlaczasz re-review tylko
  dajesz mi znac”.

## 3. Mapa

- `src/algopalette/model.py` — `OKLCH` (frozen), aliasy `Role/ContrastMetric/DeltaEMethod/CvdType/CvdMethod/FitMethod/ChromaMode`
  (Task 2 ROZSZERZA, nie redefiniuje).
- `src/algopalette/model.py:239` `default_role_defaults(polarity, metric)` — dark: bg L .10–.25 C≤.04; fg L .85–.98,
  kontrast ≥7 (WCAG)/75 (APCA); akcent L .60–.85, C abs .06–.20, kontrast ≥4.5/60, min ΔE .08 (miękki), CVD .04 (miękki).
  `:313` `effective_conditions` (źródła slot/mood/global; klucz snapshotu `role_defaults.<rola>.<pole>`),
  `:348` `broken_relations`, `:374` `add_accent` (≤14), `:387` `remove_slot` (≥1 akcent), `:397` `move_slot` (tylko
  akcenty), `:409` `History` (limit = liczba stanów). Wartości `mood_snapshot` muszą być hashowalne.
- `src/algopalette/io.py` — `SessionFormatError(ValueError)`, `save_session(s, path, overwrite=False)` (atomowo),
  `load_session` (brak pliku → `FileNotFoundError`; OSError przy zapisie leci do TUI), `default_palettes_dir()`,
  `autosave_path()`, `config_dir()` (nie tworzą katalogów). JSON slotu ma informacyjny `hex`.
  `OptimizerSettings.max_evals = 20_000` (do strojenia w Tasku 4).
- `src/algopalette/color/__init__.py` — API: `to_hex`, `fit_delta`, `from_css`, `in_gamut`, `max_chroma`, `contrast`,
  `delta_e`, `simulate_cvd`, `hue_diff` + `Color` (ColorAll+APCA), `to_color`, `apca_signed`, `contrast_hex`, `fast`.
  `to_hex` = fit(metoda) + clip; `fit_delta` = ΔE ok(c, po fit+clip). Gamut: kanały linear sRGB w [−1e-6, 1+1e-6].
  `from_css` zaokrągla do 12 miejsc; błąd `ValueError("Nie można odczytać koloru „…”.")`.
- `src/algopalette/color/apca.py` — wtyczka contrast `apca` (stałe = PB `index.html:1282-1310`).
- `src/algopalette/constraints.py` — `Ctx` (leniwe: `lab`, `maxc`, `rel_c`, `contrast(i,j,metric)`, `de(i,j,method,lch)`,
  `cvd_lch(kind)`, `hue_weight` = (C/0.02)² obcięte do 1); `compile_terms(session, hue_targets)`; klucze termów:
  `slot:<id>:<pole>`, `slot:<id>:rel:<kind>:<n>`, `slot:<id>:gamut`, `pair:<a>:<b>:min_distance`,
  `pair:<a>:<b>:cvd:<typ>`, `global:lightness_spread`, `global:scheme:<id>`, `global:avoid:<id>:<k>`. Pary
  min_distance/CVD tylko między AKCENTAMI; próg pary = max z obu slotów, twardy jeśli którykolwiek. Termy, których
  wszystkie sloty mają kłódkę, są pomijane. ΔE 2000/itp/cam16: w optymalizacji ΔE ok × `Ctx.calib[(i,j,metoda)]`,
  w `evaluate` (exact) przez coloraide. Skale: L .01, C .01/.02(rel), H 1°, WCAG .1, APCA 1, ΔE ok/hyab .01, inne 1.
- `src/algopalette/engine.py` — `generate(session, slot_ids, progress, cancel)`, `Proposal.ok` (brak twardych i nie
  timed_out), `_Space.decode_with_maxc` (maxC liczone raz, podawane do `Ctx(maxc=)`), `_optimize`, `_finish`,
  `hue_targets_for` (HOOK dla Tasku 5). Budżet `max_evals` (20 000) na propozycję = wiersze ocenione przez
  `f_batch`. `cancel` → przerywa i zwraca gotowe propozycje; limit czasu → bieżąca z `timed_out` i koniec.
- Wydajność `constraints.objective_batch`: termy par (`Term.pair`) liczone hurtem z macierzy ΔE `Ctx._de_matrix`.
- `src/algopalette/hues.py` — `base_hues`, `scheme_targets(scheme, n, seed)`, `targets_for_session(session)`.
- `src/algopalette/moods.py` — `BUILTIN` (nazwa → (opis, builder(polarity, metric))), `list_moods`, `apply_mood`,
  `mood_overrides`, `save_user_mood`/`delete_user_mood` (używa `io._enc_globals/_dec_globals`). Nastroje
  zależą od polaryzacji/metryki → po zmianie polaryzacji lub metryki w TUI trzeba nałożyć nastrój ponownie.
  „monochromatyczny z jednym akcentem” = custom (35°, 220°×13), bo reguła cykliczna rozsuwa krótsze listy.
- **TUI — pułapki Textuala (sprawdzone):** `App._ready` to metoda Textuala (nie nadpisuj; flaga to `_ui_ready`);
  `App.is_mounted` to metoda, nie właściwość; `[F2]` w tytule zakładki znika (markup) — używaj `(F2)`; `Select`
  bez `compact=True` ma 3 linie; poziomy suwak bez `width: 1fr` rozjeżdża się poza widok; edytory składają dzieci
  LENIWIE — `compose` musi sprawdzić, czy slot jeszcze istnieje (`alive()`); w testach przyciski poza widokiem
  przewijanym naciskaj `Button.press()`, nie `pilot.click`. Zrzuty: `app.save_screenshot` + `rsvg-convert`.
  Dalsze kolizje nazw z Textualem: `Widget.colors` (stąd `SourceTab.source_colors`). Klasy `-valid/-invalid`
  na `Input` ustawia SAM Textual (walidacja) — własne oznaczenie błędu to `-bad`. `Switch` nie ma trybu
  kompaktowego. W testach po programowej zmianie `Select.value` daj `await pilot.pause()` przed akcją.
  Przełączanie zakładek w testach/zrzutach: klawisze F2–F6 (`action_tab` + jedna pauza nie zawsze wystarcza).
- **Polecenia na pierwszym planie ≤ 20 s (decyzja użytkownika „timeouty max 20s”)** — pełne pytest (~100 s) TYLKO w tle.
- `src/algopalette/units.py` — `DE_SCALE`, `convert_de`, `convert_contrast`, `rescale_delta_e`,
  `rescale_contrast_metric`, `default_distance`; `src/algopalette/globals_logic.py` — `change_polarity_or_metric`,
  `change_delta_e` (używane przez zakładkę Globalne).
- `src/algopalette/color/fast.py` — numpy `(...,3)`: `oklch_to_oklab`, `oklab_to_linear_srgb`, `in_gamut`, `max_chroma`
  (bisekcja), `wcag21`, `apca(_signed)`, `contrast`, `delta_e(ok|hyab)`, `simulate_cvd(vienot|machado)`.
  + Brettel (Task 3). ΔE 2000/itp/cam16 → `NotImplementedError`.

Jedyne odniesienie do PB: `/home/qrikk/palettebuilder/index.html:6236` `motif()` — wczytywanie JSON (akceptuje
`palettebuilder.v2/v3`, `palette` = `{hex, role}` lub napisy); okno „Wczytaj…” przyjmuje wklejenie; PB mieści ≤ 16
kolorów (nadmiar scala). APCA w PB (`index.html:1293`) = te same stałe 0.0.98G-4g.

## 4. Stan weryfikacji

**Czego NIE zweryfikowano:** uruchomienia w prawdziwym terminalu Ghostty przez człowieka (tylko Pilot + zrzuty
SVG); schowka OSC 52 w prawdziwym terminalu (w testach `copy_to_clipboard` podmienione); wklejenia schowka do
działającego PaletteBuildera w przeglądarce (sprawdzone tylko `motif()` + `importTheme` w node); wydajności na
innej maszynie; metod ΔE 2000/itp/cam16 w optymalizacji poza testem jednostkowym (przybliżenie kalibrowane).


Po przełączniku HSL: `uv run pytest -q` → **296 passed** (w tle, ~130 s); perf default 0.39 s; `ruff check`, `ruff format --check`, `ty check` → zero uwag.

## 5. Dziennik sesji (append-only)

- 2026-11-14 — brainstorming: ustalenia jak w §2, spec napisany, `git init`, handoff założony.
- 2026-11-14 — builder-check (3 pytania): determinizm = budżet w ewaluacjach (decyzja agenta); nastroje tylko wg ról
  strukturalnych (decyzja agenta); pytanie o zachowanie danych PB → użytkownik odrzucił cały kierunek PB→AlgoPalette;
  spec oczyszczony z ról PB, czytania motifs; dodana akcja „Przenieś do PaletteBuildera”, max 14 akcentów (PB ≤ 16).
- 2026-11-14 — spec zaakceptowany; plan 11 zadań + .tasks.json; natywne zadania #1–#11 z zależnościami.
- 2026-11-14 — wykonanie: gałąź `feat/algopalette`; Task 1 wysłany (Sonnet). Zmiana zasad przeglądu (jeden, Opus high, na końcu).
- 2026-11-14 — Task 1 ☑ (8e8bf4c): warstwa koloru; 39 testów; wektor gamutu w planie poprawiony na C=0.30.
- 2026-11-14 — Task 2 ☑ (048d506): model + io; 114 testów; ruff wyłączony dla docs/; od Tasku 3 kontroler pracuje sam.
- 2026-11-14 — Task 3 ☑: constraints wsadowe, Brettel w numpy; 141 testów.
- 2026-11-14 — Task 4 ☑: silnik B (L,u,H; L-BFGS-B wsadowo); default 2.07 s / 6 ok; time_cap 30 s; 155 testów.
- 2026-11-14 — Task 5 ☑: hues + moods (9 + własne); wczesne wyjście silnika; default 1.5–1.7 s; 200 testów.
- 2026-11-14 — Task 6 ☑: sources (parsowanie, uzupełnianie, charakter, przeniesienie); 212 testów.
- 2026-11-14 — Task 7 ☑: eksport do PB, akceptacja sprawdzona na logice PB (motif + importTheme); 216 testów. Etap 1 koniec.
- 2026-11-14 — Task 8 ☑: TUI szkielet + Paleta + naruszenia + historia + autozapis; 240 testów.
- 2026-11-14 — Task 9 ☑: Globalne, Propozycje, Źródło, eksport; 254 testy. Użytkownik: timeouty ≤ 20 s.
- 2026-11-14 — Task 10 ☑: zakładka Analiza; 264 testy.
- 2026-11-14 — Task 11 ☑: README, instalacja komendy; plan wykonany w całości.
- 2026-11-14 — przegląd całości Opus high: 5C/8I/14M, wszystko naprawione bez re-review; testy dopisane.
- 2026-11-14 — scalono do master (fast-forward 316e210); launcher `algopalette` sprawdzony spoza repo.
- 2026-11-14 — przełącznik widoku HSL/OKLCH (F7); bez przeglądu na życzenie użytkownika.
- 2026-11-14 — GUI w PySide6 (domyślne), TUI pod `--tui`; `forms.py` wspólne; testy GUI (pytest-qt).
