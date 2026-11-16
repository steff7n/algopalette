# Motywy z sieci — plan wdrożenia

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Niemodalne okno „Motywy z sieci” (base16/base24, Gogh, Windows Terminal, Lospec) z listą, filtrami
i dużym podglądem; import wybranego motywu jako bieżącej sesji (krok cofania, bez zapisu na dysk), z trybem
„Nie zmieniaj ustawień palety” i ochroną kolorów z kłódką zasad.

**Architecture:** Nowy pakiet `algopalette/themes/` bez Qt: `model.py` (`Theme`, `Palette`, `resolve`, filtr),
`parsers.py` (cztery formaty → `Theme`), `net.py` (`httpx`, lista hostów, limity), `cache.py`
(`$XDG_CACHE_HOME/algopalette/themes/`), `catalog.py` (pobierz/z pamięci/offline, strony Lospec), `apply.py`
(`apply_theme`, oparty na wydzielonej z `sources.apply_character` części liczącej ustawienia). GUI:
`gui/theme_preview.py` (podgląd + pasek próbek), `gui/themes_dialog.py` (okno + wątek roboczy), wpięcie
w `gui/app.py`, pomoc w `gui/help_content/themes_web.py`.

**Tech Stack:** Python 3.13, PySide6 (Fusion), `httpx`, `PyYAML`, pytest + pytest-qt (offscreen), ruff, ty, uv
(paczka z rozszerzeniem Rust, backend maturin).

**Spec:** `docs/superpowers/specs/2026-11-16-motywy-z-sieci-design.md` — czytaj przed każdym zadaniem; plan
odwołuje się do sekcji jako §N.

## Global Constraints

- Gałąź `feat/motywy-z-sieci`, worktree `/home/qrikk/algopalette/.worktrees/motywy-z-sieci`. Nigdy `git add -A`
  — stageuj tylko swoje pliki (w worktree `zasady-silnik` leży cudzy zmodyfikowany `….tasks.json`; tutaj
  drzewo było czyste na starcie).
- Model v2 z `feat/zasady-silnik`: `Slot.locked`, `rules`, `use_scheme`, `relations`, `rules_lock`
  (`"off" | "rules" | "hue"`), `MAX_ACCENTS = 14`, indeks 0 = tło, 1 = tekst.
- **Żaden test nie łączy się z internetem**: `tests/conftest.py` (Task 1) blokuje prawdziwy transport `httpx`;
  testy sieci używają `httpx.MockTransport`. Testy NIE piszą do prawdziwego `~/.cache` (`XDG_CACHE_HOME` → tmp).
- Hosty dozwolone: `codeload.github.com`, `raw.githubusercontent.com`, `lospec.com` (także po przekierowaniu).
  Limit czasu 20 s, limit odpowiedzi 20 MB (20 * 1024 * 1024), `User-Agent: algopalette/<wersja paczki>`.
- URL-e (§5, sprawdzone 2026-11-16):
  - `base16`: `https://codeload.github.com/tinted-theming/schemes/tar.gz/HEAD` (NIE `main` — 404);
  - `gogh`: `https://raw.githubusercontent.com/Gogh-Co/Gogh/master/data/themes.json`;
  - `wt`: `https://raw.githubusercontent.com/atomcorp/themes/master/themes.json`;
  - `lospec`: `https://lospec.com/palette-list/load?colorNumberFilterType=max&colorNumber=16&page=<n>&tag=<tag>&sortingType=downloads`
    (10 palet na stronę, `{"palettes": [...], "totalCount": N}`).
- Świeżość pamięci: 7 dni (`base16`, `gogh`, `wt`), 1 dzień (strony Lospec). Zapis atomowy (tmp + `os.replace`).
- Ciemny/jasny = WYŁĄCZNIE L OKLCH tła < 0,5 (pole `variant` źródeł ignorowane) — filtr i polaryzacja.
- Teksty UI i pomoc po polsku z diakrytykami. Kolory w arkuszach stylu tylko przez `theme.mark_*`; podgląd motywu
  rysuje się kolorami MOTYWU niezależnie od motywu okna. Każdy element okna z `help.attach` (test pokrycia).
- Po każdym zadaniu: `uv run ruff check --fix` + `uv run ruff format` na dotkniętych plikach, `uv run ty check`,
  testy zadania; potem aktualizacja `HANDOFF.md` §0f i commit (trailer z atrybucją sesji). Polecenia na
  pierwszym planie ≤ 20 s; dłuższe przebiegi testów w tle.
- Pełny `uv run pytest -q -m "not slow"` przed końcem etapu (Task 8). Testy `slow` (jakość presetów) tylko jeśli
  zmieniono `presets*`/silnik — tu nie zmieniamy.

**User decisions (already made):**
- „Taki motyw byłby wtedy ładowany bezpośrednio do aplikacji do zakładki 'paleta', nie zapisywany na dysku — to
  następuje dopiero po samodzielnym zapisaniu, tak jak ma to miejsce teraz.”
- „jak zwykle obie opcje - gdzieś w oknie importu umieść checkboxa, który sprawi, że importowane motywy nie będą
  ustawiać ustawień globalnych 'pod siebie' - domyślnie niech ustawiają (wyjątkiem są zablokowane ustawienia
  kolorów […] te ograniczenia zostają, jeżeli są włączone, niezależnie od ustawień importu)”.
- Podgląd: wariant „C” (lista z paskiem próbek + duży podgląd terminal/kod) — „c”; szkic okna — „zgadza się”.
- Stos: „brak zastrzeżeń [httpx, PyYAML], jeśli chodzi o stack wybierz to, w czym ci wygodniej”.
- Spec z listą rozstrzygnięć agenta 1–9 — „zgadza się”.
- Źródła — wybór agenta („skąd te motywy brać, to już zostawiam tobie”).

## Review Focus

1. **Paleta, z której po deduplikacji nie zostaje ani jeden akcent** (Lospec: 2–3 kolory, powtórzenia) —
   `resolve` zgłasza `ThemeError`; okno pokazuje „Za mało różnych kolorów” i wyłącza „Wczytaj”, bez wyjątku
   w pętli zdarzeń. Test: Task 1 (`resolve`), Task 7 (okno).
2. **Spóźniony wynik pobierania** (szybkie przełączanie źródeł / zamknięcie okna w trakcie) — wynik starego
   żądania nie nadpisuje listy bieżącego źródła; zamknięcie okna nie wywraca programu. Test: Task 7.
3. **Import usuwający kolory zaznaczone w „Zasadach”** (zaznaczony akcent 10, motyw z 8 akcentami) — okno
   odświeża się bez wyjątku, zaznaczenie spada na istniejące kolory. Test: Task 7.
4. **Uszkodzony albo niezapisywalny katalog pamięci** — uszkodzony plik = brak pamięci; błąd zapisu nie
   przerywa wyświetlenia pobranego katalogu. Test: Task 3 i Task 5.
5. **Wyszukiwanie z diakrytykami/wielkością liter** („Żółty”, „NORD”) i Cofnij po imporcie przywracające
   kłódki zasad i ustawienia. Test: Task 1 (fold) i Task 7 (cofnij).

---

## Mapa plików

| Plik | Odpowiedzialność | Zadanie |
|------|------------------|---------|
| `pyproject.toml` | + `httpx`, `PyYAML` (+ `types-PyYAML` w dev, jeśli `ty` tego wymaga) | 1 |
| `tests/conftest.py` (nowy) | blokada sieci, `XDG_CACHE_HOME` → tmp (autouse, cały zestaw) | 1 |
| `src/algopalette/themes/__init__.py` | eksport publicznych nazw | 1 |
| `src/algopalette/themes/model.py` | `Theme`, `Palette`, `ThemeError`, `SOURCES`, `resolve`, `is_dark`, `filter_themes`, `fold` | 1 |
| `src/algopalette/themes/parsers.py` | `parse_tinted`, `parse_gogh`, `parse_wt`, `parse_lospec` | 2 |
| `src/algopalette/themes/net.py` | `make_client`, `fetch`, `FetchError` | 3 |
| `src/algopalette/themes/cache.py` | `cache_dir`, `load`, `save`, `clear`, `Cached` | 3 |
| `src/algopalette/sources.py` | wydzielenie `character_settings` z `apply_character` (zachowanie bez zmian) | 4 |
| `src/algopalette/themes/apply.py` | `apply_theme` | 4 |
| `src/algopalette/themes/catalog.py` | `load_catalog`, `lospec_page`, `lospec_url`, `CATALOG_URLS`, `refresh_all` | 5 |
| `src/algopalette/gui/theme_preview.py` | `ThemePreview` (podgląd), `SwatchDelegate` (wiersz listy) | 6 |
| `src/algopalette/gui/themes_dialog.py` | `ThemesDialog`, wątek roboczy | 7 |
| `src/algopalette/gui/app.py` | akcja „Motywy z sieci…”, `open_themes`, `import_theme` | 7 |
| `src/algopalette/gui/theme.py` | `read_setting`/`write_setting` (uogólnienie `save_mode`) | 7 |
| `src/algopalette/gui/help_content/themes_web.py` + `__init__.py` | tematy `themes.*`, `menu.file.themes` | 8 |
| `tests/fixtures/themes/*` | wycinki odpowiedzi źródeł | 2 |
| `README.md`, `HANDOFF.md` | opis funkcji, stan | 8 (HANDOFF po każdym) |

Kolejność: **1 → {2, 3, 4, 6} równolegle (rozłączne pliki) → 5 (po 2, 3) → 7 (po 4, 5, 6) → 8**.

---

### Task 1: Zależności, model motywu, blokada sieci w testach

**Goal:** Dodane `httpx`/`PyYAML`, pakiet `algopalette.themes` z typami dzielonymi przez wszystkie zadania
oraz globalna blokada sieci i katalogu pamięci w testach.

**Files:**
- Modify: `pyproject.toml` (`dependencies`)
- Create: `src/algopalette/themes/__init__.py`, `src/algopalette/themes/model.py`, `tests/conftest.py`
- Test: `tests/themes/test_model.py` (+ `tests/themes/__init__.py` jeśli wymaga tego układ testów)

**Interfaces (dzielone — inne zadania używają DOKŁADNIE tych nazw):**

```python
SourceId = Literal["base16", "gogh", "wt", "lospec"]
SOURCES: dict[SourceId, str]  # etykiety UI: "base16 / base24", "Gogh", "Windows Terminal", "Lospec"
FULL_CATALOG_SOURCES: tuple[SourceId, ...] = ("base16", "gogh", "wt")  # „wszystkie” w oknie

class ThemeError(ValueError): ...  # komunikat PL dla użytkownika

@dataclass(frozen=True)
class Theme:
    source: SourceId
    id: str                      # unikalny w źródle: base16 "base16/nord", gogh/wt nazwa, lospec slug
    name: str
    author: str                  # "" gdy brak
    url: str | None              # strona motywu/źródła
    colors: tuple[str, ...]      # "#rrggbb" małymi literami; has_roles → (bg, fg, *akcenty)
    accent_names: tuple[str, ...]  # has_roles → len == len(colors) - 2; inaczej ()
    has_roles: bool              # False tylko Lospec
    license: str | None = None

@dataclass(frozen=True)
class Palette:
    bg: OKLCH
    fg: OKLCH
    accents: tuple[OKLCH, ...]   # 1 … MAX_ACCENTS
    accent_names: tuple[str, ...]  # len == len(accents)

def theme_to_dict(t: Theme) -> dict[str, Any]: ...
def theme_from_dict(d: Mapping[str, Any]) -> Theme: ...   # ValueError przy złym kształcie
def resolve(t: Theme, *, light_bg: bool = False, metric: ContrastMetric = "wcag21") -> Palette: ...
def is_dark(t: Theme) -> bool | None: ...                 # None dla has_roles=False
def fold(text: str) -> str: ...                           # casefold + bez diakrytyków (ł → l)
def filter_themes(themes: Sequence[Theme], query: str, bg: Literal["any", "dark", "light"]) -> list[Theme]: ...
```

**Rules:**
- `resolve` z rolami: tło `colors[0]`, tekst `colors[1]`, akcenty reszta (już zdeduplikowane przez parser).
  Bez ról (§6): deduplikacja hexów; tło = min L (albo max L przy `light_bg`), tekst = max `color.contrast(c, bg,
  metric)` wśród pozostałych, akcenty = reszta w kolejności z palety; nazwy puste. Mniej niż 1 akcent albo więcej
  niż `MAX_ACCENTS` → `ThemeError` („Za mało różnych kolorów…” / „Za dużo kolorów…”).
- `is_dark`: `has_roles` → L OKLCH `colors[0]` < 0,5; inaczej `None`.
- `filter_themes`: `query` dopasowuje podciąg `fold(name)` lub `fold(author)`; `bg="dark"/"light"` zostawia
  motywy o zgodnym `is_dark`, a `None` (Lospec) ZAWSZE przepuszcza. Kolejność: `(SOURCES-order, fold(name))`.
- `tests/conftest.py`: autouse fixture ustawia `XDG_CACHE_HOME` na `tmp_path / "cache"` i podmienia
  `httpx.HTTPTransport.handle_request` na funkcję rzucającą `RuntimeError("sieć zablokowana w testach")`.
  `tests/gui/conftest.py` zostaje bez zmian.

**Acceptance Criteria:**
- [ ] `uv sync` instaluje `httpx` i `PyYAML`; `import httpx, yaml` działa w `uv run python`.
- [ ] `resolve` dla motywu z rolami zwraca `Palette` z `len(accents) == len(colors) - 2`.
- [ ] `resolve` Lospec `("#000000","#ffffff","#ff0000","#00ff00")` → tło czarne, tekst biały, 2 akcenty; z
      `light_bg=True` → tło białe, tekst czarny.
- [ ] `resolve` Lospec `("#112233","#112233","#ffffff")` → `ThemeError`.
- [ ] `filter_themes(..., "zolty", "any")` znajduje „Żółty”, `"NORD"` znajduje „Nord”; `bg="light"` zostawia
      motywy Lospec.
- [ ] `theme_from_dict(theme_to_dict(t)) == t`.
- [ ] Test, który próbuje `httpx.get("https://example.com")`, dostaje `RuntimeError` (blokada działa).

**Verify:** `uv run pytest -q tests/themes/test_model.py` → wszystkie zielone; `uv run ty check` → bez uwag.

**Steps:**
- [ ] Dodaj zależności (`uv add httpx pyyaml`; jeśli `ty` zgłasza brak typów `yaml` → `uv add --dev types-PyYAML`), `uv sync`.
- [ ] Napisz testy z kryteriów → czerwone.
- [ ] Zaimplementuj `model.py`, `__init__.py`, `tests/conftest.py` → zielone; ruff/ty.
- [ ] HANDOFF §0f + commit `feat(themes): model motywu, zależności httpx/PyYAML, blokada sieci w testach`.

```json:metadata
{"files": ["pyproject.toml", "src/algopalette/themes/__init__.py", "src/algopalette/themes/model.py", "tests/conftest.py", "tests/themes/test_model.py"], "verifyCommand": "uv run pytest -q tests/themes/test_model.py", "acceptanceCriteria": ["httpx i PyYAML zainstalowane", "resolve z rolami", "resolve Lospec ciemne/jasne tło", "ThemeError przy braku akcentów", "fold i filtr", "round-trip dict", "blokada sieci w testach"], "modelTier": "standard"}
```

---

### Task 2: Parsery czterech źródeł

**Goal:** `bytes` odpowiedzi każdego źródła → lista `Theme` + liczba pominiętych, zgodnie z §5–§6.

**Files:**
- Create: `src/algopalette/themes/parsers.py`
- Create: `tests/fixtures/themes/gogh.json`, `wt.json`, `lospec_page.json`, `tinted/base16/*.yaml`,
  `tinted/base24/*.yaml`, `tinted/tinted8/*.yaml` (wycinki prawdziwych danych + przypadki brzegowe)
- Test: `tests/themes/test_parsers.py` (archiwum `.tar.gz` budowane w teście z `tests/fixtures/themes/tinted/`
  przez `tarfile` w pamięci, z prefiksem `schemes-HEAD/`)

**Interfaces:**

```python
@dataclass(frozen=True)
class Parsed:
    themes: tuple[Theme, ...]
    skipped: int

def parse_tinted(data: bytes) -> Parsed: ...          # .tar.gz; tylko <root>/base16/*.yaml i <root>/base24/*.yaml
def parse_gogh(data: bytes) -> Parsed: ...
def parse_wt(data: bytes) -> Parsed: ...
def parse_lospec(data: bytes) -> tuple[Parsed, int]: ...  # (palety, totalCount)
```

**Rules (§5–§6):**
- Nieczytelny dokument jako całość (zły JSON, nie-gzip, zły kształt korzenia) → `ThemeError` z nazwą źródła.
  Pojedynczy zły wpis → pomijany i liczony w `skipped`.
- Hexy: akceptuj `#rgb`/`#rrggbb` (z `#` lub bez — Lospec bez), normalizuj do `#rrggbb` małymi literami;
  inny zapis = wpis zły.
- base16: tło `base00`, tekst `base05`, akcenty `base08`–`base0F`; base24: + `base12`–`base17`. `id`
  `"<system>/<plik bez .yaml>"`, `url` `https://github.com/tinted-theming/schemes/blob/HEAD/<system>/<plik>`,
  nazwa akcentu = klucz (`"base08"`). YAML wyłącznie `yaml.safe_load`; archiwum czytane w pamięci
  (`tarfile.open(fileobj=BytesIO, mode="r:gz")` + `extractfile`), żadnego zapisu na dysk; członkowie inni niż
  zwykłe pliki pomijani. Katalogi inne niż `base16`/`base24` (np. `tinted8`, `.github`) ignorowane BEZ liczenia
  w `skipped`.
- Gogh: tło `background`, tekst `foreground`, akcenty `color_02`–`color_07`, potem `color_10`–`color_15`
  (pomijamy 01, 08, 09, 16). WT: `red, green, yellow, blue, purple, cyan, brightRed, …, brightCyan`
  (pomijamy black/white/brightBlack/brightWhite); `author` z `meta.credits[0].name`, jeśli jest. Nazwy
  akcentów ANSI: „czerwony, zielony, żółty, niebieski, magenta, cyjan” i „jasny czerwony, jasny zielony, jasny
  żółty, jasny niebieski, jasna magenta, jasny cyjan”. `url`: Gogh `https://gogh-co.github.io/Gogh/`, WT
  `https://windowsterminalthemes.dev/`.
- Deduplikacja akcentów (z rolami): usuń akcent równy tłu, tekstowi albo wcześniejszemu akcentowi (po
  normalizacji hexu), razem z jego nazwą. 0 akcentów po deduplikacji → wpis pominięty (`skipped`).
- Lospec: `has_roles=False`, `colors` = wszystkie hexy w kolejności (bez deduplikacji — robi ją `resolve`),
  `id` = `slug`, `name` = `title`, `author` = `user.name` (brak `user` → ""), `url`
  `https://lospec.com/palette-list/<slug>`; palety > 16 kolorów albo < 3 → pominięte.

**Acceptance Criteria:**
- [ ] `parse_tinted` na archiwum z fixture: liczba motywów = liczba poprawnych plików base16+base24; plik w
      `tinted8/` nie trafia ani do motywów, ani do `skipped`; Nord ma 8 akcentów, motyw base24 14.
- [ ] Wpis Gogh, w którym jasne kolory = normalne, ma 6 akcentów (duplikaty usunięte).
- [ ] Wpis WT z nieczytelnym hexem → `skipped == 1`, reszta poprawna.
- [ ] `parse_lospec` zwraca `totalCount` i palety z `has_roles=False`; hex bez `#` znormalizowany.
- [ ] Śmieci (`b"not json"`, `b"\x00"` jako tar) → `ThemeError`.

**Verify:** `uv run pytest -q tests/themes/test_parsers.py` → zielone; ruff/ty bez uwag.

**Steps:**
- [ ] Przygotuj fixture (wycinki z prawdziwych plików — próbki z 2026-11-16 leżały w scratchpadzie sesji
      planującej; jeśli ich nie ma, utwórz ręcznie zgodnie z formatami w §5) → testy czerwone.
- [ ] Zaimplementuj → zielone; ruff/ty; HANDOFF §0f; commit `feat(themes): parsery base16/base24, Gogh, Windows Terminal, Lospec`.

```json:metadata
{"files": ["src/algopalette/themes/parsers.py", "tests/themes/test_parsers.py", "tests/fixtures/themes/"], "verifyCommand": "uv run pytest -q tests/themes/test_parsers.py", "acceptanceCriteria": ["tinted: base16+base24, tinted8 ignorowany", "Gogh deduplikacja", "WT zły hex pominięty", "Lospec totalCount i normalizacja", "śmieci → ThemeError"], "modelTier": "standard"}
```

---

### Task 3: Sieć i pamięć podręczna

**Goal:** Bezpieczne pobieranie (`httpx`) z listą hostów, limitami, postępem i anulowaniem oraz pamięć
podręczna znormalizowanych katalogów.

**Files:**
- Create: `src/algopalette/themes/net.py`, `src/algopalette/themes/cache.py`
- Test: `tests/themes/test_net.py`, `tests/themes/test_cache.py`

**Interfaces:**

```python
# net.py
ALLOWED_HOSTS: frozenset[str]; TIMEOUT_S = 20.0; MAX_BYTES = 20 * 1024 * 1024
class FetchError(Exception): ...          # str(e) = komunikat PL; atrybut .kind: "offline"|"http"|"host"|"size"|"cancelled"
def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client: ...
def fetch(client: httpx.Client, url: str, *, on_progress: Callable[[int, int | None], None] | None = None,
          cancelled: Callable[[], bool] | None = None) -> bytes: ...

# cache.py
@dataclass(frozen=True)
class Cached:
    themes: tuple[Theme, ...]
    fetched_at: float          # epoch s
    total: int | None = None   # Lospec totalCount
def cache_dir() -> Path: ...   # io._xdg("XDG_CACHE_HOME", ".cache") / "algopalette" / "themes"
def load(key: str) -> Cached | None: ...       # brak/uszkodzony → None (nigdy wyjątek)
def save(key: str, themes: Sequence[Theme], *, total: int | None = None, now: float | None = None) -> None: ...  # OSError idzie wyżej
def is_fresh(c: Cached, ttl_s: float, now: float) -> bool: ...
def clear(prefix: str = "") -> None: ...        # usuwa pliki kluczy zaczynających się od prefix
```

**Rules:**
- `make_client`: `timeout=TIMEOUT_S`, `follow_redirects=True`, nagłówek `User-Agent: algopalette/<wersja>`
  (`importlib.metadata.version("algopalette")`, fallback `"dev"`), `event_hooks["request"]` sprawdza host
  każdego żądania (także przekierowanego) → `FetchError(kind="host")`.
- `fetch`: strumieniowo (`client.stream("GET", …)`), status ≥ 400 → `FetchError(kind="http")` z kodem;
  `httpx.TimeoutException`/`ConnectError` → `kind="offline"`; przekroczenie `MAX_BYTES` (z nagłówka albo w
  trakcie) → `kind="size"`; `cancelled()` sprawdzane między porcjami → `kind="cancelled"`; postęp
  `(odebrane, content-length|None)`.
- Klucz pamięci = nazwa pliku `<key>.json` (klucz zawiera tylko `[a-z0-9-]`; inne znaki zamieniane na `-`).
  Format pliku: `{"version": 1, "fetched_at": …, "total": …, "themes": [theme_to_dict…]}`; zła wersja/kształt
  → `None`.

**Acceptance Criteria:**
- [ ] MockTransport 200 → bajty; 404 → `FetchError.kind == "http"`; `httpx.ConnectError` → `"offline"`.
- [ ] Żądanie na `https://evil.example/x` → `"host"`; 302 z dozwolonego hosta na niedozwolony → `"host"`.
- [ ] Odpowiedź większa niż `MAX_BYTES` (podmień stałą w teście przez monkeypatch na małą) → `"size"`.
- [ ] `cancelled=lambda: True` → `"cancelled"`; `on_progress` wywołany co najmniej raz przy sukcesie.
- [ ] `save` → `load` zwraca te same motywy i `total`; plik z `b"{"` → `load` → `None`; `is_fresh` dla
      `now - fetched_at` = 6 dni / 8 dni przy TTL 7 dni → True / False; `clear("lospec")` usuwa tylko klucze
      Lospec.

**Verify:** `uv run pytest -q tests/themes/test_net.py tests/themes/test_cache.py` → zielone; ruff/ty.

**Steps:**
- [ ] Testy → czerwone; implementacja → zielone; ruff/ty; HANDOFF §0f; commit `feat(themes): pobieranie z listą hostów i limitami, pamięć podręczna katalogów`.

```json:metadata
{"files": ["src/algopalette/themes/net.py", "src/algopalette/themes/cache.py", "tests/themes/test_net.py", "tests/themes/test_cache.py"], "verifyCommand": "uv run pytest -q tests/themes/test_net.py tests/themes/test_cache.py", "acceptanceCriteria": ["200/404/offline", "host spoza listy i po przekierowaniu", "limit rozmiaru", "anulowanie i postęp", "pamięć: round-trip, uszkodzony plik, świeżość, clear"], "modelTier": "standard"}
```

---

### Task 4: Import motywu do sesji (`apply_theme`)

**Goal:** Czysta funkcja importu zgodna z §7, oparta na wydzielonej części `apply_character`; kłódka zasad
chroni zasady w obu trybach.

**Files:**
- Modify: `src/algopalette/sources.py:200-257` (wydzielenie; `apply_character` zachowuje zachowanie co do bitu)
- Create: `src/algopalette/themes/apply.py`
- Test: `tests/themes/test_apply.py`; regresja: `tests/test_sources.py`, `tests/test_rules_lock.py`

**Interfaces:**

```python
# sources.py
@dataclass(frozen=True)
class CharacterSettings:
    globals: GlobalSettings   # polaryzacja + układ odcieni "custom"; avoid_* BEZ zmian względem wejścia
    bg: SlotRules
    fg: SlotRules
    accent: SlotRules
def character_settings(session: Session, profile: Profile) -> CharacterSettings: ...
# apply_character(...) = character_settings + dotychczasowe avoid_* + zdjęcie kłódek (bez zmian zachowania)

# themes/apply.py
def apply_theme(session: Session, palette: Palette, *, keep_settings: bool) -> Session: ...
```

**Rules (§7 — czytaj w całości):**
- Liczba kolorów → `2 + len(palette.accents)`; dokładanie `model.add_accent`; usuwanie od końca z pominięciem
  `rules_lock != "off"` (`model.remove_slot`); nadmiarowe zablokowane akcenty zachowują poprzednią wartość.
- Wartości: tło, tekst, akcenty po kolei; `locked=False` WSZĘDZIE; nazwy: `"tło"`, `"tekst"`, akcenty z
  `palette.accent_names` (pozycje bez nazwy motywu → `""`).
- `keep_settings=False`: `extract_profile([bg, fg, *accents], metric=session.globals.contrast_metric)` →
  `character_settings`; `globals` z wyniku (avoid_* z wejścia), `preset=None`; każdy kolor BEZ kłódki zasad
  dostaje zasady roli z wyniku i `use_scheme=True`; kolor Z kłódką zasad zachowuje `rules`, `use_scheme`,
  `relations`, `rules_lock` bez zmian.
- `keep_settings=True`: `globals`, `preset`, `rules`, `use_scheme`, `relations`, `rules_lock` wszystkich
  istniejących kolorów identyczne; nowe akcenty jak z `add_accent`.

**Acceptance Criteria:**
- [ ] `tests/test_sources.py` i `tests/test_rules_lock.py` zielone bez zmian w testach (zachowanie
      `apply_character` nienaruszone).
- [ ] Domyślny tryb, jasne tło motywu na ciemnej sesji → `globals.polarity == "light"`,
      `hue_scheme.kind == "custom"`, `preset is None`, `avoid_colors` i `contrast_metric` jak przed importem.
- [ ] Akcent z `rules_lock="rules"` (i osobno `"hue"`): po imporcie w obu trybach `rules`, `use_scheme`,
      `relations`, `rules_lock` identyczne jak przed, `value` = kolor motywu z tej pozycji.
- [ ] `keep_settings=True`: `new.globals == old.globals`, `new.preset == old.preset`, zasady wszystkich
      dotychczasowych kolorów identyczne; zmienione tylko wartości/liczba/`locked`.
- [ ] Sesja 8 akcentów + motyw 12 → 14 kolorów; 8 akcentów + motyw 3 → 5 kolorów; 8 akcentów z kłódką zasad na
      ostatnim + motyw 3 → ostatni akcent zostaje (6 kolorów, ostatni ma starą wartość).
- [ ] Wszystkie `locked == False` po imporcie (także gdy wcześniej były `True`).

**Verify:** `uv run pytest -q tests/themes/test_apply.py tests/test_sources.py tests/test_rules_lock.py` → zielone; ruff/ty.

**Steps:**
- [ ] Testy → czerwone; wydzielenie w `sources.py` (najpierw, z regresją zieloną); `apply.py` → zielone;
      ruff/ty; HANDOFF §0f; commit `feat(themes): import motywu do sesji z ochroną kłódek zasad`.

```json:metadata
{"files": ["src/algopalette/sources.py", "src/algopalette/themes/apply.py", "tests/themes/test_apply.py"], "verifyCommand": "uv run pytest -q tests/themes/test_apply.py tests/test_sources.py tests/test_rules_lock.py", "acceptanceCriteria": ["apply_character bez zmian zachowania", "tryb domyślny: polaryzacja, custom, preset None, avoid bez zmian", "kłódka zasad chroni zasady w obu trybach", "keep_settings: globals/preset/zasady identyczne", "liczba kolorów z kłódką na końcu", "locked=False wszędzie"], "modelTier": "frontier"}
```

---

### Task 5: Katalog — pobierz / z pamięci / offline, strony Lospec

**Goal:** Jedna funkcja na źródło plikowe i jedna na stronę Lospec, łącząca sieć, parsery i pamięć wg §9.

**Files:**
- Create: `src/algopalette/themes/catalog.py`
- Test: `tests/themes/test_catalog.py` (MockTransport + fixture z Tasku 2)

**Interfaces:**

```python
CATALOG_URLS: dict[SourceId, str]   # bez "lospec"
CATALOG_TTL_S = 7 * 86400; LOSPEC_TTL_S = 86400
@dataclass(frozen=True)
class CatalogResult:
    themes: tuple[Theme, ...]
    fetched_at: float
    offline: bool              # True = użyto przeterminowanej pamięci, bo sieć zawiodła
    skipped: int = 0
    total: int | None = None   # Lospec
    cache_error: str | None = None  # komunikat, gdy zapis do pamięci się nie udał
def lospec_url(tag: str, page: int) -> str: ...      # tag: pierwsze słowo, małe litery, URL-encode
def load_catalog(source: SourceId, client: httpx.Client, *, refresh: bool = False, now: float | None = None,
                 on_progress=None, cancelled=None) -> CatalogResult: ...   # source != "lospec"
def lospec_page(tag: str, page: int, client: httpx.Client, *, refresh: bool = False, now=None,
                cancelled=None) -> CatalogResult: ...
def refresh_all() -> None: ...   # cache.clear("lospec"); katalogi plikowe pobierze następne load_catalog(refresh=True)
```

**Rules:** świeża pamięć i `refresh=False` → bez sieci; inaczej pobierz → parsuj → zapisz (błąd zapisu →
`cache_error`, wynik i tak zwrócony); `FetchError` (poza `"cancelled"`) przy istniejącej (choć starej) pamięci →
wynik z pamięci, `offline=True`; bez pamięci → `FetchError` wyżej. `ThemeError` parsera → wyżej (pamięć
nienaruszona). Klucz pamięci: `source` albo `f"lospec-{tag or '_'}-{page}"`.

**Acceptance Criteria:**
- [ ] Pierwsze `load_catalog("gogh")` robi 1 żądanie; drugie (świeże) 0 żądań; `refresh=True` 1 żądanie.
- [ ] Przeterminowana pamięć + transport rzucający `ConnectError` → `offline=True`, motywy z pamięci.
- [ ] Brak pamięci + `ConnectError` → `FetchError(kind="offline")`.
- [ ] `cache_dir` niezapisywalny (monkeypatch `cache.save` rzuca `OSError`) → wynik zwrócony, `cache_error` ustawione.
- [ ] `lospec_url("Warm pastel", 2)` → `…&page=2&tag=warm&sortingType=downloads`; `lospec_page` zwraca `total`.

**Verify:** `uv run pytest -q tests/themes/test_catalog.py` → zielone; ruff/ty.

**Steps:** testy → czerwone; implementacja → zielone; ruff/ty; HANDOFF §0f; commit `feat(themes): katalogi źródeł z pamięcią i trybem offline`.

```json:metadata
{"files": ["src/algopalette/themes/catalog.py", "tests/themes/test_catalog.py"], "verifyCommand": "uv run pytest -q tests/themes/test_catalog.py", "acceptanceCriteria": ["liczba żądań: pierwsze/świeże/refresh", "offline z przeterminowanej pamięci", "brak pamięci + brak sieci → FetchError", "błąd zapisu pamięci nie przerywa", "lospec_url i total"], "modelTier": "standard"}
```

---

### Task 6: Podgląd motywu i wiersz listy

**Goal:** Widżet dużego podglądu (terminal + kod + pasek ról) i delegat wiersza listy (nazwa, plakietka
źródła, pasek próbek), rysowane kolorami motywu.

**Files:**
- Create: `src/algopalette/gui/theme_preview.py`
- Test: `tests/gui/test_theme_preview.py`

**Interfaces:**

```python
THEME_ROLE = int(Qt.ItemDataRole.UserRole) + 1   # Theme w modelu listy
PALETTE_ROLE = int(Qt.ItemDataRole.UserRole) + 2 # Palette | None (po resolve; None = błąd)
class ThemePreview(QWidget):
    def set_palette(self, palette: Palette | None, *, message: str = "") -> None: ...  # None → komunikat
    def snippet_colors(self) -> dict[str, QColor]: ...   # rola podglądu → kolor (do testów)
class SwatchDelegate(QStyledItemDelegate): ...           # sizeHint ≈ 2 linie; rysuje nazwę, źródło, próbki
```

**Rules:** role podglądu: `keyword, string, number, comment, function, type, added, removed`. Przy nazwach
akcentów base16/base24 (`palette.accent_names` zawiera `"base08"` itd.): `removed`←08, `number`←09, `type`←0A,
`string`/`added`←0B, `function`←0D, `keyword`←0E; `comment` = tekst zmieszany 50 % z tłem w OKLab. Inaczej
kolejne akcenty w kolejności `keyword, string, number, function, type, added, removed` (zawijanie modulo),
`comment` jak wyżej. Kolory przez `color.to_hex(c, "oklch-chroma")`. Pasek ról pod podglądem: tło, tekst,
akcenty, podpis „tło · tekst · N akcentów · ciemny/jasny”. Rysowanie `QPainter`, niezależnie od palety Qt okna.

**Acceptance Criteria:**
- [ ] Dla palety base16 `snippet_colors()["keyword"]` = kolor `base0E`, `["string"]` = `base0B`.
- [ ] Dla palety bez nazw base16 `keyword` = pierwszy akcent; 1 akcent → wszystkie role kodu = ten akcent.
- [ ] `set_palette(None, message="Za mało różnych kolorów")` → `grab()` nie rzuca, komunikat w `accessibleDescription` lub atrybucie testowalnym.
- [ ] `grab()` podglądu w motywie okna jasnym i ciemnym daje IDENTYCZNY piksel tła podglądu (kolor tła motywu).

**Verify:** `uv run pytest -q tests/gui/test_theme_preview.py` → zielone; ruff/ty.

**Steps:** testy → czerwone; implementacja → zielone; zrzut ekranu podglądu do scratchpadu i obejrzenie; ruff/ty; HANDOFF §0f; commit `feat(gui): podgląd motywu i wiersz listy z próbkami`.

```json:metadata
{"files": ["src/algopalette/gui/theme_preview.py", "tests/gui/test_theme_preview.py"], "verifyCommand": "uv run pytest -q tests/gui/test_theme_preview.py", "acceptanceCriteria": ["role base16 w podglądzie", "role kolejnych akcentów", "komunikat przy None", "tło podglądu niezależne od motywu okna"], "modelTier": "standard"}
```

---

### Task 7: Okno „Motywy z sieci” i wpięcie w aplikację

**Goal:** Niemodalne okno z §8 z pobieraniem w wątku roboczym, import przez `MainWindow.import_theme`,
akcja w menu Plik i na pasku narzędzi, zapamiętany checkbox.

**Files:**
- Create: `src/algopalette/gui/themes_dialog.py`
- Modify: `src/algopalette/gui/app.py` (`_build_actions`, menu Plik po `act_open`, pasek narzędzi, `_attach_help`
  — klucz `menu.file.themes`), `src/algopalette/gui/theme.py` (`read_setting(key, default)`,
  `write_setting(key, value)`; `save_mode` przez `write_setting`)
- Test: `tests/gui/test_themes_dialog.py`

**Interfaces:**

```python
# themes_dialog.py
KEEP_SETTINGS_KEY = "themes_keep_settings"
PAGE_SIZE = 50
class ThemesDialog(QDialog):
    def __init__(self, win: MainWindow, *, client_factory: Callable[[], httpx.Client] = net.make_client) -> None: ...
    # atrybuty dla testów i pomocy:
    search: QLineEdit; source: QComboBox  # data: "all" | SourceId
    bg_filter: QComboBox                  # data: "any" | "dark" | "light"
    view: QListView; more: QPushButton; preview: ThemePreview; light_bg: QCheckBox  # widoczny tylko dla Lospec
    keep_settings: QCheckBox; refresh: QPushButton; load: QPushButton
    status: QLabel; progress: QProgressBar; cancel: QPushButton; link: QLabel
    def current_theme(self) -> Theme | None: ...
# app.py
self.act_themes_web  # „Motywy z sieci…”, skrót "Ctrl+Shift+O"
def open_themes(self) -> None: ...     # jedna instancja: tworzy albo show()+raise_()+activateWindow()
def import_theme(self, theme: Theme, palette: Palette, *, keep_settings: bool) -> None: ...
```

**Rules (§8):**
- Pobieranie w `QThreadPool` (QRunnable + QObject z sygnałami `progress(int, object)`, `done(object)`,
  `failed(str)`); każde żądanie z numerem generacji — wynik o starszym numerze ignorowany; `closeEvent`
  ustawia flagę anulowania i odłącza sygnały.
- „Źródło = wszystkie” ładuje `FULL_CATALOG_SOURCES` (każde osobno, lista uzupełnia się w miarę przychodzenia);
  Lospec tylko po wybraniu: pusty `search` → strony najczęściej pobieranych, tekst → tag (debounce 400 ms);
  „Więcej” = kolejna strona Lospec albo kolejne `PAGE_SIZE` z lokalnie przefiltrowanej listy. Pod polem
  szukania dla Lospec podpowiedź „Lospec szuka po tagach (np. warm, gameboy, pastel)”.
- Zaznaczenie → `resolve(theme, light_bg=…, metric=win.session.globals.contrast_metric)`; `ThemeError` →
  `preview.set_palette(None, message=str(e))`, `load` wyłączony.
- „Wczytaj”/dwuklik/Enter → `win.import_theme(...)`: `replace_session(apply_theme(...))`, `file_path` bez zmian,
  `tabs.setCurrentWidget(palette_tab)`, `notify(f"Wczytano motyw „{name}” ({SOURCES[src]}). Cofnij: Ctrl+Z.")`.
- `keep_settings` startuje z `read_setting(KEEP_SETTINGS_KEY, False)`; zmiana → `write_setting` (błąd zapisu →
  `win.notify(..., error=True)`, bez wyjątku).
- Stany: postęp + „Anuluj”; `FetchError` bez pamięci → komunikat w `status` (tekst §8) i pusta lista z
  `mark_error`; `offline=True` → `status` „katalog z <data> (offline)”; `cache_error` → `status` dopisek.
- „Odśwież katalogi” → `catalog.refresh_all()` + ponowne `load_catalog(refresh=True)` bieżących źródeł.

**Acceptance Criteria:** (pytest-qt, `client_factory` z MockTransport serwującym fixture Tasku 2)
- [ ] `win.open_themes()` dwa razy → ten sam obiekt okna, `isModal() is False`.
- [ ] Po załadowaniu „wszystkie” lista zawiera motywy base16, Gogh i WT, ale nie Lospec; wpisanie „nord” zawęża;
      `bg_filter="light"` zostawia tylko jasne.
- [ ] Wybór „Lospec” → żądanie z `sortingType=downloads` i pustym tagiem; `light_bg` widoczny.
- [ ] Zaznaczenie + „Wczytaj” → `win.session` ma kolory motywu, `len(win.history)` +1, `win.file_path`
      bez zmian, bieżąca zakładka = Paleta; `win.action_undo()` → sesja sprzed importu (z kłódkami zasad).
- [ ] `keep_settings` zaznaczony → `win.session.globals` bez zmian; stan checkboxa po ponownym utworzeniu okna
      odtworzony z `gui.json`.
- [ ] Transport rzucający `ConnectError`, pusta pamięć → `status` zawiera „Nie udało się pobrać katalogu”,
      bez wyjątku.
- [ ] Wynik spóźnionego żądania (przełączenie źródła przed `done`) nie zmienia listy; zamknięcie okna
      w trakcie pobierania nie powoduje wyjątku (sprawdzone `qtbot` + `capture_exceptions`).
- [ ] Zaznaczony w „Zasadach” akcent 10 + import motywu z 8 akcentami → brak wyjątku, `rules_tab` pokazuje
      istniejące kolory.
- [ ] Paleta Lospec z 2 różnymi kolorami → `load.isEnabled() is False`, podgląd z komunikatem.

**Verify:** `uv run pytest -q tests/gui/test_themes_dialog.py tests/gui/test_theme.py tests/gui/test_gui_app.py` → zielone; ruff/ty.

**Steps:** testy → czerwone; `theme.py` helpery; okno; wpięcie w `app.py`; zrzut ekranu okna (oba motywy okna)
do scratchpadu i obejrzenie; ruff/ty; HANDOFF §0f; commit `feat(gui): okno „Motywy z sieci” i import do Palety`.

```json:metadata
{"files": ["src/algopalette/gui/themes_dialog.py", "src/algopalette/gui/app.py", "src/algopalette/gui/theme.py", "tests/gui/test_themes_dialog.py"], "verifyCommand": "uv run pytest -q tests/gui/test_themes_dialog.py tests/gui/test_theme.py tests/gui/test_gui_app.py", "acceptanceCriteria": ["jedna niemodalna instancja", "wszystkie bez Lospec, filtry", "Lospec downloads + light_bg", "import: sesja, historia, file_path, zakładka, cofnij", "keep_settings i zapamiętanie", "błąd sieci → komunikat", "spóźniony wynik i zamknięcie w trakcie", "import usuwający zaznaczone kolory", "Lospec za mało kolorów → Wczytaj wyłączony"], "modelTier": "frontier"}
```

---

### Task 8: Pomoc, pokrycie, README, domknięcie etapu

**Goal:** Tematy pomocy dla okna i akcji, test pokrycia okna, README, pełna weryfikacja i handoff gotowy do
przeglądu całości.

**Files:**
- Create: `src/algopalette/gui/help_content/themes_web.py`
- Modify: `src/algopalette/gui/help_content/__init__.py` (moduł w `_merge`), `src/algopalette/gui/help_content/window.py`
  (`menu.file.themes`), `src/algopalette/gui/help_content/topic.py` (grupa „Motywy z sieci”, jeśli `GROUPS` jest
  zamkniętą listą), `tests/gui/test_help_coverage.py` (okno motywów: `gh.uncovered(dialog) == []`), `README.md`,
  `HANDOFF.md`
- Test: `tests/gui/test_help_coverage.py`, `tests/gui/test_help.py` (wszystkie klucze osiągalne)

**Rules:** klucze `themes.window, themes.search, themes.source, themes.bg, themes.list, themes.more,
themes.preview, themes.light_bg, themes.keep_settings, themes.refresh, themes.load, themes.status, themes.link,
menu.file.themes`. Treść o działaniu programu: skąd są motywy (cztery źródła, linki), jak działa import w obu
trybach, kłódka zasad (cytat reguły z §7, w tym przesuwanie celu odcienia przy kłódce „rules”), Cofnij, brak
zapisu na dysk, pamięć podręczna/offline, Lospec po tagach, różnica wobec Widok → Motyw. `short` ≤ 200 znaków.

**Acceptance Criteria:**
- [ ] `gh.uncovered(ThemesDialog)` → `[]` (w stanie z listą, z Lospec i z błędem sieci).
- [ ] Każdy klucz `themes.*` ma temat; test osiągalności tematów zielony.
- [ ] `uv run pytest -q -m "not slow"` → zielone (liczba policzona i wpisana w HANDOFF); `ruff check .`,
      `ruff format --check .`, `ty check` → bez uwag.
- [ ] `uv tool install --editable . --force` z `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` w scratchpadzie → `algopalette --help` działa.
- [ ] README: sekcja „Motywy z sieci” (źródła, import, offline). HANDOFF §0f: stan, liczby, czego NIE
      zweryfikowano (prawdziwa sieć — tylko jeden ręczny przebieg agenta, jeśli wykonany; ręczne użycie okna).

**Verify:** `uv run pytest -q -m "not slow"` (w tle) → 0 failed; `uv run ruff check . && uv run ruff format --check . && uv run ty check` → kod 0.

**Steps:** treść pomocy; test pokrycia; README; pełna weryfikacja; jedno ręczne uruchomienie okna z prawdziwą
siecią w scratchpadzie (`XDG_CACHE_HOME` w scratchpadzie) — pobranie każdego z 4 źródeł, wynik do HANDOFF;
HANDOFF §0f; commit `feat(gui): pomoc „Motywy z sieci”; docs: README, handoff`. Następnie JEDEN przegląd całości
(Opus xhigh) wg `~/.claude/CLAUDE.md`.

```json:metadata
{"files": ["src/algopalette/gui/help_content/themes_web.py", "src/algopalette/gui/help_content/__init__.py", "src/algopalette/gui/help_content/window.py", "tests/gui/test_help_coverage.py", "README.md", "HANDOFF.md"], "verifyCommand": "uv run pytest -q -m 'not slow'", "acceptanceCriteria": ["pokrycie pomocą okna motywów", "tematy themes.* osiągalne", "pełny zestaw zielony, ruff/ty czyste", "launcher w scratchpadzie startuje", "README i HANDOFF"], "modelTier": "mechanical"}
```
