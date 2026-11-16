# Motywy z sieci — przeglądanie i import gotowych motywów kolorów

Data: 2026-11-16. Gałąź: `feat/motywy-z-sieci` (od `feat/zasady-silnik` @ `8291a8b`, model v2 + kłódka zasad).

## 1. Cel i po co

Prośba użytkownika: „Rozwińmy algopalette'a o możliwość przeglądania i pobierania motywów z sieci, na wzór
tego, co mamy w chessboard studio […]. Jeśli chodzi o to, skąd te motywy brać, to już zostawiam tobie […].
Taki motyw byłby wtedy ładowany bezpośrednio do aplikacji do zakładki 'paleta', nie zapisywany na dysku —
to następuje dopiero po samodzielnym zapisaniu, tak jak ma to miejsce teraz.”

Wzorzec: zakładka „Pobierz z internetu” w studiu (`~/chessboard_transcriber/studio/src/ui/TextureDownload.svelte`):
wybór źródła, wyszukiwarka, lista porcjami z „Więcej”, pobranie jednym przyciskiem. Różnica: motyw to tylko
lista kolorów — nie ma plików do zapisania ani miniatur do ściągania; podgląd rysujemy lokalnie.

## 2. Cele, nie-cele, anty-cele

**Cele**
- Okno przeglądania motywów z kilku źródeł sieciowych z wyszukiwaniem, filtrami i dużym podglądem.
- Import wybranego motywu jako bieżącej sesji (zakładka „Paleta”), jeden krok cofania, bez zapisu na dysk.
- Wybór, czy import dopasowuje ustawienia palety do motywu (domyślnie tak), czy zmienia tylko kolory.
- Kłódka zasad (`Slot.rules_lock`) chroni zasady koloru w obu trybach importu.

**Nie-cele**
- Eksport/publikowanie motywów do sieci; konto, logowanie, ulubione.
- Zapis motywów do biblioteki na dysku (zapis tylko istniejącym „Zapisz / Zapisz jako…”).
- Pełne repozytorium iTerm2-Color-Schemes (setki osobnych plików, ciężkie archiwum) — pokrywają je Gogh i
  Windows Terminal.
- Import do zakładki „Źródło” (tryby Uzupełnianie/Charakter/Przeniesienie) — tylko „Paleta”.

**Anty-cele (porażka, nawet jeśli „działa”)**
- Okno zamarza podczas pobierania.
- Zestaw testów łączy się z internetem.
- Import po cichu zmienia zasady koloru z włączoną kłódką zasad.
- Import zapisuje cokolwiek do katalogu palet albo nadpisuje otwarty plik sesji.
- Pusta lista bez wyjaśnienia, gdy nie ma sieci.

## 3. Ograniczenia

- Model v2 z `feat/zasady-silnik` (`model.py`: `Slot.locked`, `Slot.rules`, `Slot.use_scheme`, `Slot.rules_lock`,
  `GlobalSettings`, `MAX_ACCENTS = 14`). Rola strukturalna: indeks 0 = tło, 1 = tekst, ≥ 2 = akcent.
- Wczytanie całej sesji = `MainWindow.replace_session(new)` (osobny krok historii; Ctrl+Z przywraca).
- `MainWindow.file_path` NIE zmienia się przy imporcie (import to zmiana treści, jak wygenerowanie propozycji;
  „Zapisz” zapisuje tam, gdzie zapisywał dotąd). — *rozstrzygnięcie agenta*
- Konwencje projektu: pomoc kontekstowa dla każdego elementu (`gui/help.py` `attach`, test pokrycia), kolory
  w arkuszach stylu wyłącznie przez `theme.mark_*`, ruff + ty bez uwag, polskie teksty UI.
- **Nazewnictwo:** w menu Widok istnieje już „Motyw” (jasny/ciemny wygląd okna). Nowa funkcja w UI nazywa się
  „Motywy z sieci”, a pomoc wyraźnie odróżnia ją od motywu okna. — *rozstrzygnięcie agenta*
- Zależności nowe (zgoda użytkownika „brak zastrzeżeń”): **`httpx`** (HTTP), **`PyYAML`** (base16/base24) — do
  `pyproject.toml`, potem `uv sync` i ponowna instalacja launchera (`uv tool install --editable . --force`; paczka
  ma rozszerzenie Rust budowane maturinem).

## 4. Podejścia (rozważone; wybrane A)

- **A (wybrane): rdzeń w czystym Pythonie + `httpx` w wątku roboczym Qt.** Parsery, pamięć podręczna i import
  bez Qt; pobieranie w `QThreadPool`/`QThread`, postęp sygnałem. Testy sieci przez `httpx.MockTransport`.
  Użytkownik: „brak zastrzeżeń, jeśli chodzi o stack wybierz to w czym ci wygodniej”.
- **B: QtNetwork (`QNetworkAccessManager`).** Bez `httpx`, ale pobieranie splata się z pętlą zdarzeń Qt, testy
  źródeł wymagają `pytest-qt` i podstawiania odpowiedzi w Qt.
- **Odrzucone: katalog dołączony do paczki** — nieświeży, a licencje części palet (Lospec, treść użytkowników)
  nie pozwalają pewnie go rozpowszechniać.

## 5. Źródła (zweryfikowane 2026-11-16 na żywo)

| Id | Nazwa w UI | Pobranie | Rozmiar | Role |
|----|------------|----------|---------|------|
| `base16` | base16 / base24 (tinted-theming) | `https://codeload.github.com/tinted-theming/schemes/tar.gz/HEAD` — jedno archiwum (≈ 120 KB; domyślna gałąź to `spec-0.11`, więc `HEAD`, nie `main` — `main` daje 404) | 376 base16 + 250 base24 | jawne |
| `gogh` | Gogh | `https://raw.githubusercontent.com/Gogh-Co/Gogh/master/data/themes.json` (≈ 1,1 MB) | 1257 (986 dark, 271 light) | tło/tekst + 16 ANSI |
| `wt` | Windows Terminal | `https://raw.githubusercontent.com/atomcorp/themes/master/themes.json` (≈ 150 KB) | 264 | tło/tekst + 16 ANSI |
| `lospec` | Lospec | `https://lospec.com/palette-list/load?colorNumberFilterType=max&colorNumber=16&page=<n>&tag=<tag>&sortingType=<s>` — stronicowane po 10, `{"palettes": […], "totalCount": N}` | ≈ 3170 palet ≤ 16 kolorów | brak ról |

Formaty (próbki z 2026-11-16):
- **base16/base24** (`schemes-HEAD/base16/*.yaml`, `schemes-HEAD/base24/*.yaml`; katalog `tinted8/` pomijamy):
  `system`, `name`, `author`, `variant` (`dark`/`light`), `palette: {base00: "#2E3440", …}`.
  Odczyt przez `yaml.safe_load` członków archiwum w pamięci (`tarfile`, bez rozpakowywania na dysk).
- **Gogh**: lista obiektów `name`, `author`, `variant`, `color_01`…`color_16` (01 = czerń, 08 = biel,
  09 = jasna czerń, 16 = jasna biel), `background`, `foreground`.
- **Windows Terminal**: lista obiektów `name`, `black`, `red`, …, `brightWhite`, `background`, `foreground`,
  `meta: {isDark, credits: [{name, link}]}`.
- **Lospec**: `title`, `slug`, `colors` (hexy bez `#`), `tags`, `user.name`. Strona palety:
  `https://lospec.com/palette-list/<slug>`. Wyszukiwanie po stronie serwera tylko po **tagu** (nie po nazwie).

## 6. Odwzorowanie motywu na kolory sesji

Wynik parsera: `Theme(source, id, name, author, license|None, url|None, variant: "dark"|"light"|None,
bg: OKLCH, fg: OKLCH, accents: tuple[OKLCH, ...], accent_names: tuple[str, ...])`.

- **base16**: tło `base00`, tekst `base05`, akcenty `base08`–`base0F` (8). Nazwy akcentów: klucze (`base08`…).
- **base24**: jak base16 + `base12`–`base17` (razem 14 = `MAX_ACCENTS`).
- **Gogh / Windows Terminal**: tło `background`, tekst `foreground`, akcenty: ANSI czerwony, zielony, żółty,
  niebieski, magenta, cyjan, potem ich jasne odpowiedniki (12). Czerń i biel ANSI (normalne i jasne) pomijamy —
  dublują tło/tekst. Nazwy akcentów po polsku („czerwony”, „jasny czerwony”, …).
- **Lospec**: brak ról. `Theme` z pamięci podręcznej trzyma surową listę kolorów (`roles=None`); role
  przydziela dopiero funkcja `resolve_roles(theme, light_bg: bool, metric)` w chwili podglądu i importu (bo
  zależą od metryki sesji, a katalog w pamięci podręcznej od sesji nie zależy). Tło = najciemniejszy kolor
  (L OKLCH), a przy `light_bg` (filtr tła = „jasne” albo przełącznik „Tło jasne” w podglądzie) najjaśniejszy.
  Tekst = kolor o największym kontraście z tłem w metryce sesji. Akcenty = reszta w kolejności z palety. Nazwy
  akcentów puste. — *rozstrzygnięcie agenta*
- **Wspólne**: duplikaty akcentów (ten sam hex po normalizacji) usuwane, także akcent równy tłu lub tekstowi.
  Motyw z mniej niż 1 akcentem po deduplikacji, z nieczytelnym kolorem albo bez tła/tekstu (dla źródeł z rolami)
  jest pomijany przy budowie katalogu (licznik pominiętych w logu/stopce, bez błędu).
- **Ciemny/jasny** = WYŁĄCZNIE z jasności tła (L OKLCH < 0,5 → ciemny) — i dla filtra „Tło”, i dla polaryzacji
  przy imporcie. Pole `variant` ze źródła jest ignorowane (bywa niezgodne z tłem); jedno źródło prawdy.
  — *rozstrzygnięcie agenta*

## 7. Import do sesji — `apply_theme(session, theme, *, keep_settings: bool) -> Session`

Funkcja czysta (bez Qt), w nowym pakiecie `algopalette/themes/`.

**Liczba kolorów.** Docelowo `2 + len(theme.accents)` pozycji. Brakujące akcenty — `add_accent` (kopiuje zasady
ostatniego). Nadmiarowe — usuwane od końca, z pominięciem kolorów z kłódką zasad (`rules_lock != "off"`).
Jeśli po tym zostaje więcej pozycji niż kolorów motywu (bo kłódki nie pozwoliły usunąć), kolory motywu idą
kolejno na pozycje, a nadmiarowe zablokowane akcenty zachowują poprzednią wartość. Nowe akcenty z `add_accent`
kopiują zasady i `use_scheme` ostatniego koloru, ale NIE jego kłódkę zasad (`rules_lock="off"`, jak dziś) —
w trybie domyślnym i tak dostają zasady z profilu. — *rozstrzygnięcie agenta*

**Wartości.** Każda pozycja dostaje kolor motywu (tło, tekst, akcenty po kolei). Kłódka wartości (`locked`)
zdejmowana ze wszystkich pozycji — także tych, które miały ją przed importem (to nowa paleta). Kłódka zasad
NIE chroni wartości, tylko zasady. Nazwy: tło „tło”, tekst „tekst”, akcenty z `accent_names` (puste, jeśli
brak). — *rozstrzygnięcie agenta*

**Tryb domyślny — dopasuj ustawienia do motywu (`keep_settings=False`).** Ta sama logika co tryb „Charakter”
w Źródle (`sources.extract_profile` + reguły `sources.apply_character`), bez drugiego algorytmu:
- polaryzacja z jasności tła; układ odcieni `custom` z odcieni motywu; zasady tła/tekstu/akcentów z profilu;
  `use_scheme = True` dla akcentów; `Session.preset = None`;
- pozostałe ustawienia globalne (metryka kontrastu, ΔE, daltonizm, dopasowanie do gamutu, kolory do unikania,
  optymalizator) zostają. W szczególności lista „unikaj kolorów” NIE jest czyszczona (różnica wobec
  `apply_character(avoid_source=False)`, które ją zeruje). — *rozstrzygnięcie agenta*
- **kolory z kłódką zasad zachowują `rules`, `use_scheme`, `relations` i `rules_lock`** (słowa użytkownika:
  „wyjątkiem są zablokowane ustawienia kolorów […] te ograniczenia zostają, jeżeli są włączone, niezależnie od
  ustawień importu”). Wymaga to wydzielenia z `apply_character` części liczącej zasady, tak by import mógł je
  nałożyć selektywnie; `apply_character` w Źródle zachowuje dotychczasowe zachowanie (zdejmuje kłódki).
- zmiana polaryzacji i układu odcieni pod kolorem z kłódką zasad jest DOZWOLONA i nie łamie kłódki — tak samo
  jak przy presetach, gdzie użytkownik zdecydował (HANDOFF §0e): kłódka „rules” zachowuje zasady, „ale cel
  odcienia dalej liczy układ odcieni palety (preset go zmienia → cel się przesuwa)”; kłódka „hue” ma własny,
  zamrożony łuk odcienia i `use_scheme=False`, więc układ jej nie dotyczy. Pomoc tematu importu mówi to wprost.
- zależności (`relations`) niezablokowanych kolorów zostają (jak w `apply_character`); zależność wskazująca na
  usunięty kolor staje się zerwana tak jak przy ręcznym usunięciu (istniejący mechanizm `broken_relations`).

**Tryb „Nie zmieniaj ustawień palety” (`keep_settings=True`).** Zmieniają się tylko wartości, liczba kolorów
i kłódki wartości. `GlobalSettings`, `rules`, `use_scheme`, `relations`, `rules_lock`, `Session.preset` bez zmian.
Polaryzacja nie jest dostosowywana nawet przy niezgodności z tłem motywu — naruszenia pokaże panel naruszeń
(świadomie: to wybór użytkownika).

**Okno.** `MainWindow.replace_session(apply_theme(...))`, przejście na zakładkę „Paleta”, komunikat na pasku
stanu: „Wczytano motyw „<nazwa>” (<źródło>). Cofnij: Ctrl+Z.”

## 8. Okno „Motywy z sieci” (wariant C — decyzja użytkownika)

Szkic zaakceptowany słowami „zgadza się”:

```
┌ Motywy z sieci ───────────────────────────────────────────────────────┐
│ Szukaj [ nord            ]  Źródło [wszystkie ▾]  Tło [dowolne ▾]     │
│ ┌──────────────────────────────┐ ┌──────────────────────────────────┐ │
│ │ Nord            base16       │ │  $ git status                    │ │
│ │ ■■■■■■■■■■■■■■               │ │  On branch main                  │ │
│ │ Nord Light      Gogh         │ │  modified:  src/app.py           │ │
│ │ ■■■■■■■■■■■■                 │ │  def build(x: int) -> str:       │ │
│ │ Nordic          iTerm2       │ │      return f"#{x}"  # komentarz │ │
│ │ ■■■■■■■■■■■■■■               │ │  ■■■■■■■■■■■■■■ (tło, tekst, …)  │ │
│ │ …          [Więcej]          │ │  14 akcentów · ciemny · MIT      │ │
│ └──────────────────────────────┘ └──────────────────────────────────┘ │
│ ☐ Nie zmieniaj ustawień palety          [Odśwież katalogi] [Wczytaj]  │
└───────────────────────────────────────────────────────────────────────┘
```

- Wejście: Plik → „Motywy z sieci…” oraz przycisk na pasku narzędzi. Okno **niemodalne**, jedna instancja
  (ponowne wywołanie podnosi istniejące); można wczytywać kolejne motywy bez zamykania.
- **Lista (lewa)**: wiersz = nazwa, plakietka źródła, pasek próbek (tło, tekst, akcenty). Porcjami po ~50,
  przycisk „Więcej”. Sortowanie: źródło, potem nazwa (bez znaczenia wielkości liter i polskich znaków).
- **Filtry**: „Szukaj” (podciąg nazwy i autora, fold wielkości liter i diakrytyków); „Źródło” (wszystkie /
  każde z §5); „Tło” (dowolne / ciemne / jasne — wg jasności tła, §6; dla Lospec filtr wybiera, który skrajny
  kolor jest tłem, i niczego nie odrzuca). **„Wszystkie” = trzy źródła z pełnym katalogiem (base16, Gogh,
  Windows Terminal); Lospec tylko po wybraniu go w „Źródło”** — jego lista jest stronicowana na serwerze, więc nie
  da się jej uczciwie wymieszać i posortować z resztą. Po wybraniu Lospec: puste pole = najczęściej pobierane
  (`sortingType=downloads`), wpisany tekst = **tag** (małe litery, pierwsze słowo) z podpowiedzią pod polem
  „Lospec szuka po tagach (np. warm, gameboy, pastel)”; „Więcej” pobiera kolejną stronę serwera (lub kilka, by
  uzbierać porcję). — *rozstrzygnięcie agenta*
- **Podgląd (prawa)** dla zaznaczonej pozycji: kilka linijek „terminala” i kodu na tle motywu, w kolorze tekstu,
  z akcentami (słowa kluczowe, napisy, liczby, komentarze, funkcje, typy, git: zmiany/usunięcia — dobór akcentów
  do ról podglądu = kolejne akcenty; dla base16/base24 kanoniczne role: 08 zmienne/usunięcia, 0B napisy/dodania,
  0D funkcje, 0E słowa kluczowe, 09 liczby, 0A typy, 03 komentarze — tu `base03` jest poza sesją, więc komentarz
  = tekst z obniżonym kontrastem lub pierwszy pasujący akcent; szczegół wizualny dla wykonawcy); pod spodem pełny
  pasek kolorów z podpisem ról; linia: liczba akcentów · ciemny/jasny · autor/licencja (gdy źródło podaje);
  link „Strona źródła” (otwiera przeglądarkę systemową). Dla Lospec przełącznik „Tło jasne”.
- **Dół**: checkbox „Nie zmieniaj ustawień palety” (domyślnie odznaczony; stan zapamiętany w `gui.json`
  obok motywu okna — *rozstrzygnięcie agenta*), „Odśwież katalogi”, „Wczytaj” (też dwuklik / Enter na liście).
- **Stany**: pobieranie katalogu → pasek postępu w oknie, lista wyszarzona tylko dla tego źródła, „Anuluj”;
  brak sieci i brak pamięci podręcznej → komunikat w miejscu listy („Nie udało się pobrać katalogu <źródło>:
  <powód>. Sprawdź połączenie i kliknij „Odśwież katalogi”.”); brak sieci, ale jest stary katalog → używany,
  z dopiskiem „katalog z <data> (offline)”.
- **Pomoc**: każdy element z `help.attach` i tematem w nowym `gui/help_content/themes_web.py`; test pokrycia
  okna obejmuje też to okno. Temat główny odróżnia „Motywy z sieci” od Widok → Motyw.

## 9. Sieć i pamięć podręczna

- Jeden klient `httpx.Client`: limit czasu 20 s, `follow_redirects=True`, **lista dozwolonych hostów**
  (`codeload.github.com`, `raw.githubusercontent.com`, `lospec.com`) sprawdzana też po przekierowaniu, limit
  rozmiaru odpowiedzi 20 MB (strumieniowo), nagłówek `User-Agent: algopalette/<wersja>` (bez danych
  użytkownika).
- Pamięć podręczna w `$XDG_CACHE_HOME/algopalette/themes/` (domyślnie `~/.cache/…`): katalog źródła jako
  **znormalizowany JSON listy `Theme`** (nie surowa odpowiedź), z datą pobrania; zapis atomowy. Świeżość:
  7 dni dla base16/Gogh/WT; strony Lospec po kluczu (tag, sortowanie, strona) — 1 dzień. Uszkodzony plik
  pamięci = brak pamięci (bez wyjątku na zewnątrz).
- „Odśwież katalogi” pobiera ponownie wszystkie katalogi plikowe i czyści strony Lospec.
- Pobieranie w wątku roboczym; wynik i błędy sygnałami do okna. Zamknięcie okna/„Anuluj” przerywa pobieranie
  (wynik spóźnionego wątku ignorowany). Błędy sieci/parsowania zamieniane na czytelne komunikaty PL.
- Treści z sieci to dane niezaufane: tylko `yaml.safe_load` / `json`, archiwum czytane w pamięci (bez
  rozpakowywania, bez ścieżek z archiwum na dysk), hexy walidowane przed konwersją.

## 10. Testy akceptacyjne (wymagane)

- **Parsery**: dla każdego źródła mała próbka w `tests/fixtures/themes/` (wycinek prawdziwej odpowiedzi, w tym
  przypadki brzegowe: duplikaty ANSI, motyw bez akcentów, nieczytelny hex, `tinted8/` w archiwum) → oczekiwane
  `Theme` (role, liczba akcentów, nazwy, `variant`).
- **Sieć**: `httpx.MockTransport` — sukces, timeout, 404, host spoza listy (także po przekierowaniu), zbyt duża
  odpowiedź; **żaden test nie łączy się z internetem** (np. fixture autouse blokujący prawdziwy transport).
- **Pamięć podręczna**: świeża → bez sieci; przeterminowana + brak sieci → stara z oznaczeniem offline; uszkodzona
  → pobranie od nowa.
- **Import (`apply_theme`)**:
  - `keep_settings=False`: polaryzacja z tła, układ `custom`, zasady z profilu, `preset=None`, unikane kolory
    i metryka bez zmian; kolor z kłódką zasad ma identyczne `rules`/`use_scheme`/`relations`/`rules_lock`
    jak przed importem, ale nową wartość;
  - `keep_settings=True`: `globals`, wszystkie `rules`/`use_scheme`/`relations`/`rules_lock`, `preset` identyczne;
    zmienione tylko wartości/liczba/`locked`;
  - liczba kolorów: dokładanie, usuwanie, usuwanie z zablokowanym akcentem na końcu;
  - wszystkie `locked == False` po imporcie.
- **GUI (pytest-qt, offscreen)**: filtry zawężają listę; zaznaczenie pokazuje podgląd; „Wczytaj” zastępuje sesję,
  jeden krok cofania, `file_path` bez zmian, przejście na „Paletę”; checkbox przełącza tryb; stan błędu sieci
  pokazuje komunikat; okno niemodalne, druga akcja podnosi to samo okno; pokrycie pomocą.
- Ruff, ty, pełny `pytest` zielone; `uv tool install --editable . --force` w scratchpadzie startuje.

## 11. Co zostawione wykonawcy

Podział modułów w `algopalette/themes/` (np. `model.py`, `sources/*.py`, `net.py`, `cache.py`, `apply.py`);
mechanizm wątku (QThreadPool vs QThread); rysowanie podglądu (QPainter vs QTextBrowser z HTML) przy zachowaniu
kolorów motywu niezależnie od motywu okna; dokładne teksty podglądu; liczba pozycji na porcję; wygląd plakietek
źródeł (spójnie z `theme.style_badge`).
