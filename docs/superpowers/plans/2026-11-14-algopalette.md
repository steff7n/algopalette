# AlgoPalette Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Program TUI w Pythonie generujący palety kolorów pod motywy IDE. Liczy w OKLCH i optymalizuje całą paletę
naraz pod warunki globalne, warunki pojedynczych kolorów i zależności między kolorami.

**Architecture:** Czysty rdzeń, bez Textuala. Rdzeń ma:
- `color/`: OKLCH, kontrast WCAG/APCA, ΔE, daltonizm, gamut, wersja wektorowa numpy,
- `model.py`: sesja, sloty, warunki, dziedziczenie,
- `constraints.py`: kompilacja warunków do funkcji kary,
- `engine.py`: optymalizacja scipy z wieloma startami,
- `hues.py`, `moods.py`, `sources.py`, `io.py`, `pb_export.py`.

TUI (`tui/`) tylko wyświetla i edytuje sesję oraz uruchamia silnik w workerze.

**Tech Stack:** Python ≥ 3.13, uv, textual 8.x, coloraide 8.x, numpy, scipy, pytest (+ pytest-asyncio dla Pilota),
ruff, ty.

**Spec:** `docs/superpowers/specs/2026-11-14-algopalette-design.md`. Czytaj go razem z planem, bo plan argumentuje
ze speca.

## Global Constraints

- Cała matematyka koloru w OKLCH/OKLab (spec §2). Hex sRGB tylko na wyjściu i przy wczytywaniu. Żadnego losowania ani
  odległości w RGB/HSL.
- **Nic nie czyta plików ani formatów PaletteBuildera.** `/home/qrikk/palettebuilder` tylko do odczytu przy weryfikacji
  w Task 7. Nigdy go nie modyfikuj. Jedyny styk to `pb_export.py` (spec §9).
- Brak podglądu kodu i jakichkolwiek ról tokenów IDE (spec §2, §5.1).
- Sloty: indeks 0 = tło (`bg`), 1 = tekst (`fg`), ≥ 2 = akcent. Akcentów 1–14 (łącznie ≤ 16 slotów), domyślnie 8.
- Budżet optymalizatora liczony w ewaluacjach funkcji celu. Czas zegarowy to tylko bezpiecznik (`timed_out`).
  Te same ustawienia + ziarno → identyczne propozycje (spec §7).
- APCA = SAPC-APCA 0.0.98G-4g, implementacja własna, warunki na |Lc|, kolejność (tekst, tło) (spec §3).
- Interfejs i komunikaty błędów po polsku. Identyfikatory w kodzie po angielsku.
- Każdy `.py`: `uv run ruff check --fix`, `uv run ruff format`, `uv run ty check` bez uwag (AGENTS.md użytkownika).
- Po każdym zadaniu: testy + ruff + ty, aktualizacja `HANDOFF.md` (sekcja 0, mapa z numerami linii, policzony stan
  testów, dziennik) PRZED commitem. Commit tylko własnych plików (pathspec), nigdy `git add -A`.
- **Przegląd kodu: JEDEN, całego kodu, na samym końcu (po Tasku 11), Opus effort HIGH.** Znalezione błędy naprawia
  kontroler sam, BEZ re-review, potem informuje użytkownika. Decyzja użytkownika 2026-11-14: „przeglad calosci kodu
  robi opus high (nie xhigh) na samym koncu. bugi, ktore wylapie, naprawiasz samodzielnie ty. gdy to dobiegnie konca,
  nie wlaczasz re-review tylko dajesz mi znac”. Brak przeglądów per task i per etap.
- Nowa zależność spoza Tech Stack: dozwolona, jeśli poprawia jakość, ale trzeba ją wymienić w raporcie zadania i w
  handoffie.

**User decisions (already made):**
- „mozesz zrobic osobna apke ktora bedzie skladala sie wylacznie z 'podpowiadacza kolorow'”
- „podglad kodu jest calkowicie niepotrzebny. to ma byc program do palet, a nie drugi IDE-owy palettebuilder”
- „to maja byc dwa niezalezne programy z DODATKOWA funkcjonalnoscia przenoszenia palety z algopalette bezposrednio do
  plettebuilder. w druga strone nigdy.”
- Sterowanie kolorem: zakresy + zależności — „sprobujmy twojej propozycji”
- Nastroje, 3 tryby źródła, daltonizm, gamut, propozycje — „zalezy mi na jak najwiekszych mozliwosciach konfiguracji”
- Silnik: optymalizacja całej palety — „idziemy w B”
- „wole cos trudniejszego w obsludze niz cos dla 10latka”
- Spec zaakceptowany: „tak, pisz plan”

## Review Focus

1. **Zakres odcienia przez 0° (np. 330–20) i kolory prawie szare.** Odcień ma działać z zawinięciem. Tło/tekst o C≈0
   nie może dostawać fałszywych naruszeń odcienia (testy w Task 3).
2. **Sprzeczne warunki.** Np. kontrast WCAG ≥ 15 na tle L=0.5. Silnik zwraca propozycję z listą naruszeń, nigdy nie
   oznacza jej jako poprawnej, nie wiesza się i nie rzuca wyjątku (Task 4).
3. **Kolor z kłódką albo wklejony `oklch()` spoza sRGB.** Hex powstaje przez `fit()` metodą z ustawień, ΔE
   ściągnięcia jest znane i pokazane, bez wyjątku (Task 1, Task 4).
4. **Relacja do usuniętego slotu i cykle relacji (A→B→A).** Relacja zerwana jest oznaczona i pomijana w karze, a
   generowanie działa dalej (Task 2, Task 3).
5. **Uszkodzone wejście.** Śmieci we wklejonej liście, uszkodzony lub obcy plik sesji, brak katalogów, katalog bez
   prawa zapisu. Wynik: polski komunikat, brak wyjątku na zewnątrz, nic nie nadpisane (Task 2, Task 6, Task 9).

---

## File Structure

```
pyproject.toml                    uv, entry point algopalette = algopalette.__main__:main
src/algopalette/__init__.py
src/algopalette/__main__.py       CLI: algopalette [PLIK_SESJI] [--fresh]
src/algopalette/color/__init__.py Color (ColorAll + APCA), API wysokiego poziomu
src/algopalette/color/apca.py     wtyczka kontrastu APCA dla coloraide
src/algopalette/color/fast.py     wektorowe numpy: OKLab↔linear sRGB, WCAG, APCA, ΔE ok/hyab, CVD vienot/machado
src/algopalette/model.py          dataclassy sesji, dziedziczenie, History (undo/redo)
src/algopalette/constraints.py    Term/Violation, compile_terms, evaluate
src/algopalette/engine.py         generate() → list[Proposal]
src/algopalette/hues.py           scheme_targets()
src/algopalette/moods.py          wbudowane nastroje, apply_mood, nastroje użytkownika
src/algopalette/sources.py        parse_colors, apply_complete / extract_profile / apply_character / apply_transfer
src/algopalette/io.py             zapis/odczyt sesji algopalette.v1, ścieżki XDG, autozapis
src/algopalette/pb_export.py      JSON dla PaletteBuildera (jednokierunkowo)
src/algopalette/tui/app.py        AlgoPaletteApp, zakładki, panel naruszeń, skróty, worker
src/algopalette/tui/widgets.py    RangeSlider, ValueSlider, Swatch, SourceBadge
src/algopalette/tui/palette_tab.py lista slotów + edytor slotu (warunki, relacje)
src/algopalette/tui/globals_tab.py ustawienia globalne + nastroje
src/algopalette/tui/proposals_tab.py
src/algopalette/tui/source_tab.py
src/algopalette/tui/analysis_tab.py koło odcieni, wykres L–C, macierze ΔE/kontrastu
src/algopalette/tui/dialogs.py    zapis/wczytanie/eksport/potwierdzenia/pomoc
tests/…                           test_<moduł>.py; tests/tui/test_*.py (Pilot)
```

## Shared Interfaces (kontrakt między zadaniami)

```python
# model.py
Role = Literal["bg", "fg", "accent"]
ContrastMetric = Literal["wcag21", "apca"]
DeltaEMethod = Literal["ok", "2000", "hyab", "itp", "cam16"]
CvdType = Literal["protan", "deutan", "tritan"]
CvdMethod = Literal["brettel", "vienot", "machado"]
FitMethod = Literal["clip", "minde-chroma", "lch-chroma", "oklch-chroma", "raytrace", "scale"]
ChromaMode = Literal["abs", "rel"]           # rel = ułamek max C w sRGB przy (L, H), 0–1

@dataclass(frozen=True) class OKLCH: l: float; c: float; h: float       # l 0–1, c ≥ 0, h stopnie [0, 360)
@dataclass(frozen=True) class Interval: lo: float | None = None; hi: float | None = None
@dataclass(frozen=True) class Cond[T]: value: T; enabled: bool = True; hard: bool = True; weight: float = 1.0
@dataclass(frozen=True) class HueRange: lo: float; hi: float              # lo > hi = zakres przez 0°
@dataclass(frozen=True) class HueTarget: target: float; tol: float
@dataclass(frozen=True) class ChromaRange: mode: ChromaMode; lo: float | None; hi: float | None
@dataclass(frozen=True) class ContrastBound: metric: ContrastMetric | None; lo: float | None; hi: float | None  # None metric = globalna

@dataclass(frozen=True) class SlotConditions:      # każde pole None = dziedzicz
    hue_range: Cond[HueRange] | None = None
    hue_target: Cond[HueTarget] | None = None
    chroma: Cond[ChromaRange] | None = None
    lightness: Cond[Interval] | None = None
    contrast_bg: Cond[ContrastBound] | None = None
    min_distance: Cond[float] | None = None        # ΔE do każdego innego akcentu
    cvd_min_distance: Cond[float] | None = None
    extreme: Cond[Literal["weakest", "strongest"]] | None = None

RelKind = Literal["hue", "lightness", "chroma", "contrast", "distance", "mix"]
RelOp = Literal["eq", "ge", "le"]
@dataclass(frozen=True) class Relation:
    kind: RelKind; target: str; op: RelOp; value: float; tol: float = 0.0
    chroma_op: Literal["add", "mul"] = "add"; chroma_mode: ChromaMode = "abs"
    metric: ContrastMetric | DeltaEMethod | None = None
    other: str | None = None; t: float = 0.5          # tylko mix: self ≈ mix(target, other, t) w OKLab
    enabled: bool = True; hard: bool = True; weight: float = 1.0

@dataclass(frozen=True) class Slot:
    id: str; name: str = ""; locked: bool = False; value: OKLCH = OKLCH(0.5, 0.0, 0.0)
    conditions: SlotConditions = SlotConditions(); relations: tuple[Relation, ...] = ()

@dataclass(frozen=True) class HueScheme:
    kind: Literal["equal", "analogous", "complementary", "split", "triad", "tetrad", "custom", "none"]
    rotation: float = 0.0; center: float = 0.0; spread: float = 90.0; custom: tuple[float, ...] = ()
    tol: float = 15.0; jitter: float = 0.0; hard: bool = False; weight: float = 1.0

@dataclass(frozen=True) class CvdSettings: types: frozenset[CvdType] = frozenset(); method: CvdMethod = "machado"; severity: float = 1.0
@dataclass(frozen=True) class OptimizerSettings:
    n_proposals: int = 6; seed: int = 0; max_evals: int = <wybór buildera>; time_cap_s: float = 10.0
    min_diversity: float = 0.05; hard_weight: float = 1000.0
@dataclass(frozen=True) class GlobalSettings:
    polarity: Literal["dark", "light"]; role_defaults: Mapping[Role, SlotConditions]  # pełne dla bg/fg/accent
    hue_scheme: HueScheme; lightness_spread: Cond[Interval] | None              # max L − min L akcentów
    contrast_metric: ContrastMetric; delta_e: DeltaEMethod; cvd: CvdSettings; fit_method: FitMethod
    avoid_colors: tuple[OKLCH, ...] = (); avoid_distance: float = 0.0           # tryb „charakter”
    optimizer: OptimizerSettings = OptimizerSettings()
@dataclass(frozen=True) class Session:
    globals: GlobalSettings; slots: tuple[Slot, ...]; mood: str | None = None
    mood_snapshot: Mapping[str, Any] | None = None    # wartości ustawione przez nastrój (do „źródła wartości”)

def role_of(index: int) -> Role
def default_session() -> Session                      # polaryzacja dark, 8 akcentów, nastrój „neutralny”
def effective_conditions(session: Session, slot_id: str) -> tuple[SlotConditions, Mapping[str, Literal["mood", "global", "slot"]]]
def broken_relations(session: Session) -> list[tuple[str, int]]   # (slot_id, indeks relacji) z targetem/other spoza sesji
def with_slot(session, slot: Slot) -> Session; add_accent(session) -> Session; remove_slot(session, slot_id) -> Session
def move_slot(session, slot_id, new_index) -> Session
class History: push(s); undo() -> Session | None; redo() -> Session | None; current; limit=200

# color/__init__.py
def to_hex(c: OKLCH, fit: FitMethod) -> str
def fit_delta(c: OKLCH, fit: FitMethod) -> float           # ΔE ok między c a wersją po fit (0 gdy w gamucie)
def from_css(text: str) -> OKLCH                           # hex / oklch(); ValueError z polskim komunikatem
def in_gamut(c: OKLCH) -> bool
def max_chroma(l: float, h: float) -> float                # max C w sRGB (bisekcja, tol 1e-5)
def contrast(text: OKLCH, bg: OKLCH, metric: ContrastMetric) -> float   # wcag ratio / |Lc|
def delta_e(a: OKLCH, b: OKLCH, method: DeltaEMethod) -> float
def simulate_cvd(c: OKLCH, kind: CvdType, method: CvdMethod, severity: float) -> OKLCH
def hue_diff(a: float, b: float) -> float                  # najkrótszy łuk, wynik w (−180, 180]

# constraints.py
@dataclass(frozen=True) class Violation:
    key: str; slot_ids: tuple[str, ...]; label: str; hard: bool; required: str; achieved: str; amount: float
@dataclass(frozen=True) class Term:
    key: str; slot_ids: tuple[str, ...]; label: str; hard: bool; weight: float; scale: float
    fn: Callable[[Mapping[str, OKLCH]], float]   # naruszenie ≥ 0 w jednostkach naturalnych; 0 = spełniony
    describe: Callable[[Mapping[str, OKLCH]], tuple[str, str]]   # (wymagane, osiągnięte) po polsku
def compile_terms(session: Session) -> list[Term]
def evaluate(terms: Sequence[Term], values: Mapping[str, OKLCH]) -> list[Violation]   # tylko naruszone
def objective(terms, values, hard_weight: float) -> float  # Σ w·(v/scale)² ×hard_weight dla twardych

# engine.py
@dataclass(frozen=True) class Proposal:
    values: Mapping[str, OKLCH]; hexes: Mapping[str, str]; fit_deltas: Mapping[str, float]
    score: float; violations: tuple[Violation, ...]; timed_out: bool; seed: int
    @property def ok(self) -> bool                  # brak twardych naruszeń i not timed_out
def generate(session: Session, *, slot_ids: Collection[str] | None = None,
             progress: Callable[[float], None] | None = None,
             cancel: Callable[[], bool] | None = None) -> list[Proposal]
```

---

## ETAP 1 — rdzeń

### Task 1: Szkielet projektu + warstwa koloru (OKLCH, gamut, kontrast WCAG/APCA, ΔE, daltonizm, wersja numpy)

**Goal:** Projekt uv z zależnościami i moduł `algopalette.color` z API z Shared Interfaces oraz zgodną z nim szybką
ścieżką numpy.

**Files:**
- Create: `pyproject.toml`, `src/algopalette/__init__.py`, `src/algopalette/color/{__init__,apca,fast}.py`, `.gitignore`
- Test: `tests/test_color.py`, `tests/test_fast.py`

**Acceptance Criteria:**
- [ ] `uv sync` instaluje textual, coloraide, numpy, scipy, pytest, pytest-asyncio. `uv run pytest` działa.
- [ ] APCA spełnia 4 wektory ze speca §3 (tol 0.1).
- [ ] `to_hex` / `max_chroma` / `fit_delta` / `from_css` / `hue_diff` spełniają testy niżej.
- [ ] `fast.py` zgadza się z coloraide do 1e-6 na 1000 losowych par (seed 0) dla OKLab→linear sRGB, WCAG, APCA,
      ΔE ok, ΔE hyab, CVD vienot i machado (severity 0.5 i 1.0).
- [ ] ruff + ty zero uwag.

**Verify:** `uv run pytest tests/test_color.py tests/test_fast.py -q` → wszystkie PASS

**Steps:**

- [ ] **Step 1: `uv init --package --name algopalette`, `uv add textual coloraide numpy scipy`, `uv add --dev pytest pytest-asyncio`.**
  Ustaw `requires-python = ">=3.13"` i skrypt `algopalette = "algopalette.__main__:main"`. Na razie stub `main()`.
- [ ] **Step 2: Testy (RED):**

```python
def test_apca_vectors():
    assert contrast_hex("#888888", "#ffffff", "apca") == approx(63.06, abs=0.1)   # |Lc|
    assert apca_signed("#ffffff", "#888888") == approx(-68.54, abs=0.1)
    assert apca_signed("#000000", "#aaaaaa") == approx(58.15, abs=0.1)
    assert apca_signed("#aaaaaa", "#000000") == approx(-56.24, abs=0.1)
def test_wcag_black_white(): assert contrast(from_css("#000"), from_css("#fff"), "wcag21") == approx(21.0)
def test_red_roundtrip(): assert to_hex(OKLCH(0.62796, 0.25768, 29.2339), "clip") == "#ff0000"
def test_max_chroma_boundary():   # dla 50 losowych (L∈[0.05,0.95], H) z seed 1
    m = max_chroma(l, h); assert in_gamut(OKLCH(l, m * 0.999, h)) and not in_gamut(OKLCH(l, m * 1.01 + 1e-4, h))
def test_fit_delta_out_of_gamut():
    c = OKLCH(0.75, 0.30, 140); assert fit_delta(c, "oklch-chroma") > 0.01; assert to_hex(c, "oklch-chroma").startswith("#")
    assert fit_delta(OKLCH(0.5, 0.05, 200), "clip") == 0.0
def test_hue_diff(): assert hue_diff(350, 10) == approx(20); assert hue_diff(10, 350) == approx(-20); assert hue_diff(0, 180) == approx(180)
def test_from_css():
    assert from_css("oklch(70% 0.1 200deg)") == from_css("oklch(0.7 0.1 200)")
    with pytest.raises(ValueError, match="#ggg"): from_css("#ggg")
```
`apca_signed`/`contrast_hex` to pomocnicze funkcje testu lub publiczne, wybór implementującego.

- [ ] **Step 3: Implementacja.** `apca.py` rejestruje metodę `"apca"` jako wtyczkę contrast coloraide (klasa `Color`
  = `ColorAll` + rejestracja). Stałe 0.0.98G-4g (zgodne z `/home/qrikk/palettebuilder/index.html:1293`, tylko do
  porównania stałych). `fast.py` operuje na tablicach `(N, 3)` OKLCH/OKLab. Brettel, ΔE 2000/itp/cam16 nie muszą
  mieć ścieżki numpy: `fast` rzuca `NotImplementedError`, a silnik używa wtedy coloraide.
- [ ] **Step 4: Test `tests/test_fast.py::test_matches_coloraide` (parametryzowany po funkcjach z kryteriów) → GREEN.**
- [ ] **Step 5: ruff/ty, HANDOFF.md, commit `feat: warstwa koloru (OKLCH, APCA, ΔE, CVD, gamut, numpy)`.**

```json:metadata
{"files": ["pyproject.toml", "src/algopalette/color/__init__.py", "src/algopalette/color/apca.py", "src/algopalette/color/fast.py", "tests/test_color.py", "tests/test_fast.py"], "verifyCommand": "uv run pytest tests/test_color.py tests/test_fast.py -q", "acceptanceCriteria": ["APCA 4 wektory tol 0.1", "to_hex red == #ff0000", "max_chroma granica gamutu", "fast == coloraide do 1e-6", "ruff+ty zero uwag"], "modelTier": "standard"}
```

### Task 2: Model sesji, dziedziczenie, historia, zapis/odczyt `algopalette.v1`

**Goal:** Dataclassy z Shared Interfaces, rozstrzyganie dziedziczenia ze źródłem wartości, undo/redo i trwały zapis
sesji z autozapisem.

**Files:**
- Create: `src/algopalette/model.py`, `src/algopalette/io.py`
- Test: `tests/test_model.py`, `tests/test_io.py`

**Acceptance Criteria:**
- [ ] `default_session()`: 10 slotów (bg, fg, 8 akcentów), polaryzacja dark, pełne `role_defaults` dla 3 ról.
- [ ] `effective_conditions` scala pole po polu (slot > globalne). Źródło = `"slot"`, `"mood"` (wartość globalna
      równa `mood_snapshot`) albo `"global"`.
- [ ] `add_accent` powyżej 14 akcentów → `ValueError("Najwyżej 14 akcentów")`. `remove_slot` na bg/fg → `ValueError`.
      Usunięcie slotu zostawia relacje, które `broken_relations` wtedy zgłasza.
- [ ] Zapis i odczyt sesji to tożsamość (`load(save(s)) == s`), łącznie z relacjami, `Cond`, `frozenset`.
- [ ] Obcy/uszkodzony JSON → `SessionFormatError` z polskim komunikatem. Istniejący plik bez `overwrite=True` →
      `FileExistsError`, plik nietknięty.
- [ ] Ścieżki respektują `XDG_DATA_HOME`/`XDG_STATE_HOME`/`XDG_CONFIG_HOME`.

**Verify:** `uv run pytest tests/test_model.py tests/test_io.py -q` → PASS

**Steps:**

- [ ] **Step 1: Testy (RED):** `test_default_session_shape`, `test_effective_inherits_and_sources`,
  `test_accent_limit`, `test_cannot_remove_bg_fg`, `test_broken_relation_after_remove`
  (A ma relację do B, `remove_slot(B)` → `broken_relations == [(A.id, 0)]`), `test_history_undo_redo_limit`
  (201 push → najstarszy znika), `test_roundtrip(tmp_path)` (sesja z każdym typem warunku i relacji),
  `test_bad_format` (`{"format":"palettebuilder.v3"}` → `SessionFormatError`), `test_truncated_json`,
  `test_no_overwrite(tmp_path)`, `test_xdg_paths(monkeypatch)`.
- [ ] **Step 2: Implementacja `model.py`** wg Shared Interfaces. Slot id: `uuid4().hex[:8]`. Domyślne `role_defaults`
  i domyślne wartości numeryczne to wybór implementującego, ale ciemne tło musi mieć L ≤ 0.25.
- [ ] **Step 3: Implementacja `io.py`:** `session_to_dict`, `session_from_dict`, `save_session(s, path, overwrite=False)`
  (zapis atomowy: plik tymczasowy + `os.replace`), `load_session(path)`, `default_palettes_dir()`
  (`$XDG_DATA_HOME/algopalette/palettes`), `autosave_path()` (`$XDG_STATE_HOME/algopalette/last.json`),
  `config_dir()`. JSON: `{"format": "algopalette.v1", ...}`.
- [ ] **Step 4: GREEN, ruff/ty, HANDOFF.md, commit `feat: model sesji, historia, zapis algopalette.v1`.**

```json:metadata
{"files": ["src/algopalette/model.py", "src/algopalette/io.py", "tests/test_model.py", "tests/test_io.py"], "verifyCommand": "uv run pytest tests/test_model.py tests/test_io.py -q", "acceptanceCriteria": ["default_session 10 slotów", "dziedziczenie ze źródłem", "limit 14 akcentów", "broken_relations", "roundtrip", "SessionFormatError", "brak nadpisania", "XDG"], "modelTier": "standard"}
```

### Task 3: Kompilacja warunków do funkcji kary

**Goal:** `compile_terms(session)` zamienia warunki slotów, relacje i ustawienia globalne na listę `Term`.
`evaluate`/`objective` liczą naruszenia z polskimi opisami.

**Files:**
- Create: `src/algopalette/constraints.py`
- Test: `tests/test_constraints.py`

**Acceptance Criteria:**
- [ ] Term dla każdego włączonego warunku §5.2, relacji §5.3 i globalnych: rozrzut L, układ odcieni (cele z
      `hues.scheme_targets` dopiero w Task 5; tutaj interfejs `hue_targets: Mapping[str, float] | None` w
      `compile_terms(session, hue_targets=None)`), daltonizm (każdy włączony typ × każda para akcentów), gamut
      (`fit_delta` na kolorach wolnych), unikanie kolorów źródła.
- [ ] Wyłączone warunki (`enabled=False`), relacje zerwane i sloty z kłódką nie dają termów zależnych wyłącznie od
      zablokowanych slotów.
- [ ] Odcień: zawijanie zakresu. Waga termów odcienia skalowana do 0 płynnie, gdy C < 0.02 (szarość nie ma odcienia).
- [ ] Skale normalizacji: L 0.01, C 0.01 (abs) / 0.02 (rel), H 1°, WCAG 0.1, APCA 1 Lc, ΔE ok 0.01 (inne ΔE: 1.0).
- [ ] `Violation.label` i `required`/`achieved` po polsku, np. `"kontrast z tłem"`, `"≥ 4.50"`, `"3.12"`.

**Verify:** `uv run pytest tests/test_constraints.py -q` → PASS

**Steps:**

- [ ] **Step 1: Testy (RED):**

```python
def test_hue_range_wraps():      # warunek 330–20
    assert violation_of(hue=5) == 0; assert violation_of(hue=25) == approx(5); assert violation_of(hue=300) == approx(30)
def test_gray_has_no_hue_violation():   # bg OKLCH(0.2, 0.0, 0) z HueRange(100,120) → evaluate == []
def test_contrast_bg_wcag_and_apca():   # fg #777 na bg #1e1e1e: WCAG ≥ 7 naruszony, required "≥ 7.00"
def test_min_distance_pairs():   # 3 akcenty, dwa identyczne → dokładnie 1 naruszenie z obydwoma slot_ids
def test_cvd_pairs():            # czerwony vs zielony o tym samym L przy deutan → naruszenie; bez cvd.types → brak
def test_relation_hue_opposite():# B = A + 180 ± 10: A.h=30, B.h=200 → 0; B.h=240 → approx(50)
def test_relation_mix():         # self dokładnie w połowie OKLab A i B → 0
def test_extreme_weakest():      # akcent z flagą weakest nie ma najniższego kontrastu → naruszenie
def test_disabled_and_broken_skipped()
def test_locked_only_terms_dropped()   # term między dwoma slotami z kłódką nie wchodzi do compile_terms
def test_objective_hard_weight(): # objective rośnie ×hard_weight dla twardych względem miękkich
def test_cycle_relations_ok()     # A→B i B→A: compile_terms kończy się, evaluate działa
```
- [ ] **Step 2: Implementacja** wg Shared Interfaces. Funkcje termów mogą wołać `color` (coloraide). Wektoryzację robi
  Task 4.
- [ ] **Step 3: GREEN, ruff/ty, HANDOFF.md, commit `feat: kompilacja warunków do funkcji kary`.**

```json:metadata
{"files": ["src/algopalette/constraints.py", "tests/test_constraints.py"], "verifyCommand": "uv run pytest tests/test_constraints.py -q", "acceptanceCriteria": ["wszystkie warunki §5.2/§5.3/§5.4 mają termy", "zawijanie odcienia", "szarość bez naruszeń odcienia", "pominięte wyłączone/zerwane/zablokowane", "polskie opisy"], "modelTier": "frontier"}
```

### Task 4: Silnik optymalizacji (podejście B)

**Goal:** `engine.generate()` zwraca N deterministycznych, zróżnicowanych propozycji minimalizujących `objective`
z uczciwą listą naruszeń.

**Files:**
- Create: `src/algopalette/engine.py`
- Modify: `src/algopalette/constraints.py` (opcjonalnie wektorowe ewaluatory przez `color.fast`)
- Test: `tests/test_engine.py`

**Acceptance Criteria:**
- [ ] Tło `#1e1e2e` z kłódką, 4 akcenty, WCAG ≥ 4.5, ΔE ok ≥ 0.08 → każda z 6 propozycji `ok`. Kontrast i ΔE
      sprawdzone niezależnie przez coloraide na hexach.
- [ ] Te same ustawienia + seed → identyczne `hexes`. Inny seed → różne.
- [ ] Sprzeczność (tło `oklch(0.5 0 0)` z kłódką, akcent WCAG ≥ 15) → propozycje zwrócone, `ok == False`, naruszenie
      `contrast_bg` twarde z `amount > 0`, bez wyjątku.
- [ ] Sloty z kłódką mają dokładnie wartość wejściową. `slot_ids={X}` zmienia tylko X.
- [ ] Propozycje różnią się średnio o ≥ `min_diversity` (ΔE ok, średnia po wolnych slotach).
      Gdy to niemożliwe, propozycja ma naruszenie miękkie `"różnorodność"`.
- [ ] `cancel()` → zwrot w ≤ 1 s z listą ≤ N. `time_cap_s=0.001` → `timed_out == True`.
- [ ] Wydajność: `default_session()`, 6 propozycji → < 6 s na maszynie testowej (cel speca ~3 s). Zmierzony czas
      wpisany do handoffu.
- [ ] `hexes` = `to_hex(value, fit_method)`, `fit_deltas` = `fit_delta`. Slot z kłódką na `OKLCH(0.75, 0.30, 140)`
      (spoza sRGB) → poprawny hex, `fit_deltas[id] > 0.01`, bez wyjątku (`test_locked_out_of_gamut`).

**Verify:** `uv run pytest tests/test_engine.py -q` → PASS (z czasem testu wydajności w wyjściu `-s` lub w handoffie)

**Steps:**

- [ ] **Step 1: Testy (RED)** dla każdego kryterium: `test_feasible_basic`, `test_deterministic`, `test_seed_changes`,
  `test_infeasible_reports`, `test_locked_untouched`, `test_subset_generation`, `test_diversity`, `test_cancel`,
  `test_time_cap`, `test_perf_default` (`@pytest.mark.slow`, wliczany do domyślnego biegu).
- [ ] **Step 2: Implementacja.** Wymagany kształt:
  1. Losowe starty w zakresach (LHS lub uniform) z `numpy.random.default_rng(seed + k)`.
  2. Wybór najlepszych startów.
  3. Lokalna/globalna optymalizacja scipy z twardym limitem ewaluacji `max_evals`.
  4. Kolejne propozycje dostają term różnorodności względem poprzednich.

  Reprezentacja zmiennych (np. L, a, b z ograniczeniami) i wybór metody scipy należą do implementującego. Na tym
  zadaniu wolno wektoryzować przez `color.fast`, a koszt i zysk opisać w handoffie.
- [ ] **Step 3: GREEN, ruff/ty, HANDOFF.md (czas perf), commit `feat: silnik optymalizacji palety`.**

```json:metadata
{"files": ["src/algopalette/engine.py", "src/algopalette/constraints.py", "tests/test_engine.py"], "verifyCommand": "uv run pytest tests/test_engine.py -q", "acceptanceCriteria": ["feasible → ok", "determinizm", "sprzeczność raportowana", "kłódki nietknięte", "różnorodność", "cancel/time cap", "perf < 6 s"], "modelTier": "frontier"}
```

### Task 5: Układy odcieni i nastroje

**Goal:** `hues.scheme_targets` wytwarza cele odcieni dla akcentów, a `moods` daje wbudowane i własne nastroje
nakładane jawnie na ustawienia globalne.

**Files:**
- Create: `src/algopalette/hues.py`, `src/algopalette/moods.py`
- Modify: `src/algopalette/engine.py` (przekazanie `hue_targets` do `compile_terms` dla akcentów bez własnego H)
- Test: `tests/test_hues.py`, `tests/test_moods.py`

**Acceptance Criteria:**
- [ ] `scheme_targets(scheme, n, seed) -> list[float]`:
  - `equal` n=4, rotation=10 → `[10, 100, 190, 280]`;
  - `triad` rotation=0, n=3 → `[0, 120, 240]`;
  - `complementary` rotation=30, n=2 → `[30, 210]`;
  - `analogous` center=200, spread=60, n=3 → `[170, 200, 230]`;
  - `custom (30, 200)` n=2 → `[30, 200]`;
  - `none` → `[]`.
- [ ] Reguła cykliczna dla n > liczby bazowych odcieni k: akcent i dostaje `base[i % k] + c·360/(k·⌈n/k⌉)`, gdzie
      `c = i // k`. `jitter` daje deterministyczne przesunięcia ±jitter z seeda.
- [ ] 9 wbudowanych nastrojów: neutralny, chłodny mglisty, neon, ziemisty, pastel, nocny wysoki kontrast,
      monochromatyczny z jednym akcentem, retro terminal, jesienny. Każdy to częściowe nadpisanie `GlobalSettings`.
      Wygenerowana z nastroju paleta „neon” ma medianę C względnego akcentów > „pastel”, a „pastel” ma medianę L
      akcentów > „nocny wysoki kontrast” (test przez engine, 1 propozycja).
- [ ] `apply_mood(session, name)` ustawia `mood`, `mood_snapshot` i nie zmienia slotów. Nastroje użytkownika:
      `save_user_mood(name, session)`, `delete_user_mood`, `list_moods()` w `config_dir()/moods.json`. Nazwa
      wbudowana → `ValueError`.

**Verify:** `uv run pytest tests/test_hues.py tests/test_moods.py -q` → PASS

**Steps:**

- [ ] **Step 1: Testy (RED)** z wartościami z kryteriów (tol 1e-9 dla układów bez jittera).
- [ ] **Step 2: Implementacja.** Liczby nastrojów wybiera implementujący, ale muszą odpowiadać nazwie (spec §5.5).
- [ ] **Step 3: GREEN, ruff/ty, HANDOFF.md, commit `feat: układy odcieni i nastroje`.**

```json:metadata
{"files": ["src/algopalette/hues.py", "src/algopalette/moods.py", "src/algopalette/engine.py", "tests/test_hues.py", "tests/test_moods.py"], "verifyCommand": "uv run pytest tests/test_hues.py tests/test_moods.py -q", "acceptanceCriteria": ["scheme_targets wartości", "reguła cykliczna", "9 nastrojów zgodnych z nazwą", "apply_mood jawny", "nastroje użytkownika w moods.json"], "modelTier": "standard"}
```

### Task 6: Paleta wyjściowa — parsowanie i trzy tryby

**Goal:** `sources.py` parsuje wklejone kolory i zamienia je na warunki sesji w trybach uzupełnianie, charakter i
przeniesienie (spec §6).

**Files:**
- Create: `src/algopalette/sources.py`
- Test: `tests/test_sources.py`

**Acceptance Criteria:**
- [ ] `parse_colors("#fff, #000000;oklch(0.7 0.1 200)\n oklch(70% 0.1 200deg)")` → 4 kolory.
      `"#fff zielony"` → `ParseError` wskazujące `"zielony"`. Ponad 16 kolorów → `ParseError("Najwyżej 16 kolorów")`.
- [ ] `apply_complete(session, colors, bg_index=0, fg_index=1)` daje pierwsze sloty z kłódką w kolejności
      bg, fg, akcenty. Brakujące akcenty są dokładane do 14, a nadmiar wolnych slotów zostaje.
- [ ] `extract_profile(colors, bg_index, fg_index) -> Profile` (odcienie dominujące, klastrowanie H ważone C;
      `rel_chroma: Interval`, `lightness: Interval` jako p10–p90; `bg: OKLCH`; `contrasts: tuple[float, ...]`).
      Paleta z akcentami wokół 30° i 200° → `profile.hues` zawiera wartości w ±10° od obu.
- [ ] `apply_character(session, profile, avoid_source: bool, avoid_distance: float)` ustawia `hue_scheme` custom,
      zakresy globalne i `avoid_colors`. Po `generate` żaden akcent nie jest bliżej niż `avoid_distance` od koloru
      źródła (gdy `ok`).
- [ ] `apply_transfer(session, colors, bg_index, fg_index, polarity)`: ciemna paleta → jasna. Po `generate`
      (propozycja `ok`):
  - L tła ≥ 0.9;
  - odcień każdego akcentu w ±10° od źródła;
  - |kontrast − kontrast źródła| ≤ tolerancja ustawiona przez tryb (domyślnie WCAG 0.5 / APCA 5).
- [ ] Wczytanie sesji AlgoPalette jako źródła: kolory slotów w kolejności (bg = 0, fg = 1).

**Verify:** `uv run pytest tests/test_sources.py -q` → PASS

**Steps:**

- [ ] **Step 1: Testy (RED)** wg kryteriów (fixture: ciemna paleta 2 + 6 kolorów z odcieniami 30/35/200/210/120/300).
- [ ] **Step 2: Implementacja.** Metoda klastrowania odcieni (np. ważone k-means na okręgu) do wyboru implementującego.
- [ ] **Step 3: GREEN, ruff/ty, HANDOFF.md, commit `feat: paleta wyjściowa — uzupełnianie, charakter, przeniesienie`.**

```json:metadata
{"files": ["src/algopalette/sources.py", "tests/test_sources.py"], "verifyCommand": "uv run pytest tests/test_sources.py -q", "acceptanceCriteria": ["parse_colors + ParseError", "uzupełnianie z kłódkami", "profil odcieni ±10°", "charakter unika źródła", "przeniesienie dark→light"], "modelTier": "frontier"}
```

### Task 7: Eksport do PaletteBuildera (jednokierunkowy)

**Goal:** `pb_export.py` wytwarza JSON, który okno „Wczytaj…” PaletteBuildera przyjmuje, sprawdzone na prawdziwej
logice PB.

**Files:**
- Create: `src/algopalette/pb_export.py`, `tests/fixtures/pb_export_expected.json`
- Test: `tests/test_pb_export.py`

**Acceptance Criteria:**
- [ ] `pb_json(session_or_proposal_hexes, polarity) -> str` daje
      `{"format": "palettebuilder.v3", "polarity": …, "palette": [{"hex": "#rrggbb", "role": "bg"|"fg"|null}, …]}`
      w kolejności slotów, plus minimalne pola, jeśli PB ich wymaga.
- [ ] `write_pb_file(text, path, overwrite=False)`: bez nadpisywania bez zgody (jak `save_session`).
- [ ] **Dowód akceptacji przez PB:** jednorazowy skrypt node w scratchpadzie wywołuje funkcję `motif()`
      z `/home/qrikk/palettebuilder/index.html` (sposób ładowania podejrzany w testach PB `tests/*.mjs`) na wyniku
      `pb_json` i dostaje nie-null z tymi samymi hexami. Wynik (wyjście konsoli) trafia do handoffu. Skrypt NIE trafia
      do repo PB, a PB pozostaje niezmieniony (`git -C /home/qrikk/palettebuilder status` przed i po identyczny).
- [ ] Test złotego pliku w tym repo pilnuje kształtu.

**Verify:** `uv run pytest tests/test_pb_export.py -q` → PASS + wyjście skryptu node w handoffie

**Steps:**

- [ ] **Step 1: Test złotego pliku (RED).**
- [ ] **Step 2: Sprawdzenie w PB** (wyżej). Jeśli PB wymaga dodatkowych pól (`lang`, `defaults`…), dodaj je minimalnie
  i zaktualizuj złoty plik.
- [ ] **Step 3: GREEN, ruff/ty, HANDOFF.md, commit `feat: eksport palety do PaletteBuildera`.**

```json:metadata
{"files": ["src/algopalette/pb_export.py", "tests/test_pb_export.py", "tests/fixtures/pb_export_expected.json"], "verifyCommand": "uv run pytest tests/test_pb_export.py -q", "acceptanceCriteria": ["kształt palettebuilder.v3", "brak nadpisania", "motif() PB zwraca nie-null z tymi samymi hexami", "PB niezmieniony"], "modelTier": "mechanical"}
```

**Koniec Etapu 1 — bez przeglądu (przegląd tylko na samym końcu).**

---

## ETAP 2 — TUI

### Task 8: Szkielet aplikacji, suwaki, zakładka Paleta, panel naruszeń, undo/redo, autozapis

**Goal:** Działające `algopalette` z zakładką Paleta (lista slotów + edytor warunków i relacji), stałym panelem naruszeń,
historią i autozapisem.

**Files:**
- Create: `src/algopalette/__main__.py` (pełny), `src/algopalette/tui/{__init__,app,widgets,palette_tab,dialogs}.py`
- Test: `tests/tui/test_app.py`, `tests/tui/test_widgets.py`

**Acceptance Criteria:**
- [ ] `algopalette [PLIK] [--fresh]`. Bez pliku program przywraca autozapis (jeśli jest), inaczej startuje
      z `default_session()`. Uszkodzony autozapis → start od domyślnej sesji + komunikat, bez wyjątku.
- [ ] Lista slotów: próbka truecolor (tło próbki = hex), nazwa, hex, `L C H`, kłódka, kontrast z tłem (metryka
      globalna), ΔE do najbliższego sąsiada. Dodawanie, usuwanie i przesuwanie slotów działa (limity z Task 2 jako
      komunikat).
- [ ] Edytor slotu: wszystkie pola `SlotConditions` (włącz/wyłącz, twardy/miękki, waga) ze źródłem wartości
      (`mood`/`global`/`slot`) i akcją „wróć do dziedziczenia”. Lista relacji z dodawaniem, edycją, usuwaniem
      i oznaczeniem zerwanych.
- [ ] `RangeSlider`/`ValueSlider`: ←/→ krok, z modyfikatorem krok drobny/gruby, przeciąganie myszą, wpisanie
      dokładnej liczby. Zakres przez 0° dla odcienia.
- [ ] Panel naruszeń widoczny na każdej zakładce, przeliczany po każdej zmianie (`evaluate` na bieżących wartościach).
- [ ] Undo/redo całej sesji. Autozapis po każdej zmianie (z debounce) do `autosave_path()`.
- [ ] Ekran pomocy z pełną listą skrótów.

**Verify:** `uv run pytest tests/tui -q` → PASS

**Steps:**

- [ ] **Step 1: Testy Pilot (RED):** `test_starts_with_default` (wiersze == 10), `test_open_file_arg`,
  `test_corrupt_autosave_falls_back`, `test_slider_keyboard_changes_lightness` (zmiana + undo przywraca),
  `test_hue_slider_wraps`, `test_add_remove_accent_limits`, `test_violation_panel_updates`
  (fixture sprzeczna → panel zawiera „kontrast z tłem”), `test_reset_to_inherited`, `test_broken_relation_marked`,
  `test_help_screen`, `test_autosave_written(tmp_path, monkeypatch XDG_STATE_HOME)`. Rozmiary terminala 120×40
  i 80×24 bez wyjątku.
- [ ] **Step 2: Implementacja.** Układ jak w szkicu w rozmowie (lista slotów po lewej, edytor po prawej, panel naruszeń
  na dole), bez podglądu kodu. Skróty wybiera implementujący.
- [ ] **Step 3: GREEN, ruff/ty, HANDOFF.md, commit `feat: TUI — paleta, edytor slotu, naruszenia, historia`.**

```json:metadata
{"files": ["src/algopalette/__main__.py", "src/algopalette/tui/app.py", "src/algopalette/tui/widgets.py", "src/algopalette/tui/palette_tab.py", "src/algopalette/tui/dialogs.py", "tests/tui/test_app.py", "tests/tui/test_widgets.py"], "verifyCommand": "uv run pytest tests/tui -q", "acceptanceCriteria": ["CLI + autozapis", "lista slotów z danymi", "edytor warunków i relacji ze źródłem", "suwaki klawiatura/mysz/wpis", "panel naruszeń", "undo/redo", "pomoc"], "modelTier": "frontier"}
```

### Task 9: Zakładki Globalne, Propozycje, Źródło + zapis/wczytanie/eksport

**Goal:** Pełne sterowanie globalne i nastrojami, generowanie w workerze z przeglądaniem propozycji, tryby źródła,
zapis i wczytanie sesji oraz „Przenieś do PaletteBuildera”.

**Files:**
- Create: `src/algopalette/tui/{globals_tab,proposals_tab,source_tab}.py`
- Modify: `src/algopalette/tui/app.py`, `src/algopalette/tui/dialogs.py`
- Test: `tests/tui/test_flows.py`

**Acceptance Criteria:**
- [ ] Globalne: każde pole `GlobalSettings` (w tym metryki, daltonizm, fit, optymalizator i ziarno), wybór nastroju,
      zapis i usuwanie własnego nastroju.
- [ ] Generowanie w workerze: UI responsywne, pasek postępu, przerwanie, generowanie całości lub zaznaczonych slotów.
- [ ] Propozycje: N wierszy próbek, wynik, liczba naruszeń, znacznik `timed_out`/„niepowtarzalne”. Akcje „przejmij
      całą” i „przejmij kolor do slotu” (z undo). Propozycja z twardymi naruszeniami wyraźnie oznaczona.
- [ ] Źródło: pole wklejania (błąd `ParseError` pokazany przy polu), wczytanie pliku sesji jako źródła, wybór
      bg/fg, tryb (uzupełnianie/charakter/przeniesienie) z parametrami.
- [ ] Zapis i wczytanie sesji (domyślny katalog `default_palettes_dir()`, potwierdzenie nadpisania). Brak prawa
      zapisu → polski komunikat.
- [ ] Eksport do PB: `App.copy_to_clipboard(pb_json(...))` + opcjonalny zapis pliku (domyślnie `~/Dokumenty/motifs`,
      potwierdzenie nadpisania), komunikat o sukcesie.

**Verify:** `uv run pytest tests/tui -q` → PASS

**Steps:**

- [ ] **Step 1: Testy Pilot (RED):** `test_generate_fills_proposals` (czekanie na worker, wierszy == n_proposals),
  `test_cancel_generation`, `test_take_whole_and_single_color` (+ undo), `test_mood_apply_and_user_mood(tmp_path)`,
  `test_source_paste_error_shown`, `test_source_complete_locks`, `test_save_load_roundtrip(tmp_path)`,
  `test_save_overwrite_confirm`, `test_save_unwritable_dir_message`, `test_export_clipboard(monkeypatch copy_to_clipboard)`
  (tekst = `pb_json`).
- [ ] **Step 2: Implementacja.**
- [ ] **Step 3: GREEN, ruff/ty, HANDOFF.md, commit `feat: TUI — globalne, nastroje, propozycje, źródło, zapis, eksport`.**

```json:metadata
{"files": ["src/algopalette/tui/globals_tab.py", "src/algopalette/tui/proposals_tab.py", "src/algopalette/tui/source_tab.py", "src/algopalette/tui/app.py", "src/algopalette/tui/dialogs.py", "tests/tui/test_flows.py"], "verifyCommand": "uv run pytest tests/tui -q", "acceptanceCriteria": ["globalne + nastroje", "worker z postępem i przerwaniem", "propozycje i przejmowanie", "źródło 3 tryby", "zapis/wczytanie", "eksport do schowka/pliku"], "modelTier": "standard"}
```

### Task 10: Zakładka Analiza

**Goal:** Wizualna analiza palety w terminalu: koło odcieni z zakresami, wykres L–C, macierze ΔE i kontrastu (także po
symulacji daltonizmu) z zaznaczeniem naruszeń, próbki „Aa” na tle.

**Files:**
- Create: `src/algopalette/tui/analysis_tab.py`
- Modify: `src/algopalette/tui/app.py`
- Test: `tests/tui/test_analysis.py`

**Acceptance Criteria:**
- [ ] Koło odcieni (braille lub półbloki) z punktem na kolor (kolor truecolor) i łukami zakresów H zaznaczonego slotu.
- [ ] Wykres L (oś pionowa) × C względne/bezwzględne (przełącznik).
- [ ] Macierz par akcentów: ΔE (metoda globalna) i kontrast. Przełącznik normalnie/protan/deutan/tritan. Komórki
      łamiące `min_distance`/`cvd_min_distance` wyróżnione.
- [ ] Próbki „Aa” i bloki każdego koloru na tle.
- [ ] Renderuje się bez wyjątku przy 80×24 i 200×60 oraz przy 1 i 14 akcentach.

**Verify:** `uv run pytest tests/tui/test_analysis.py -q` → PASS

**Steps:**

- [ ] **Step 1: Testy (RED):** `test_renders_sizes` (parametryzacja rozmiarów i liczby akcentów),
  `test_matrix_highlights_violation` (dwa identyczne akcenty → wyróżniona komórka),
  `test_cvd_toggle_changes_matrix`, `test_hue_point_position` (kolor H=90 rysowany w górnej/prawej ćwiartce zgodnie
  z przyjętą orientacją, opisaną w docstringu).
- [ ] **Step 2: Implementacja.**
- [ ] **Step 3: GREEN, ruff/ty, HANDOFF.md, commit `feat: TUI — zakładka analizy`.**

```json:metadata
{"files": ["src/algopalette/tui/analysis_tab.py", "src/algopalette/tui/app.py", "tests/tui/test_analysis.py"], "verifyCommand": "uv run pytest tests/tui/test_analysis.py -q", "acceptanceCriteria": ["koło odcieni z zakresami", "wykres L–C", "macierze ΔE/kontrastu z CVD", "próbki Aa", "render 80x24 i 200x60, 1 i 14 akcentów"], "modelTier": "standard"}
```

### Task 11: Instalacja, README, końcowa weryfikacja

**Goal:** Komenda `algopalette` zainstalowana dla użytkownika, README po polsku i policzony stan weryfikacji
w handoffie.

**Files:**
- Create: `README.md`
- Modify: `HANDOFF.md`

**Acceptance Criteria:**
- [ ] `uv tool install --editable .` → `which algopalette` wskazuje `~/.local/bin/algopalette`. Uruchomienie
      w trybie headless (`--help` albo test Pilot na zainstalowanym module) działa.
- [ ] README: uruchamianie, zakładki, warunki i relacje z przykładami, nastroje, tryby źródła, eksport do PB (tylko
      w jedną stronę), pliki i katalogi, sekcja „czego nie robić”.
- [ ] Pełny `uv run pytest -q`, `ruff check`, `ruff format --check`, `ty check`. Liczby wpisane do handoffu.
      „Czego NIE zweryfikowano” oddzielone.

**Verify:** `uv run pytest -q && uv run ruff check && uv run ruff format --check && uv run ty check && which algopalette`

**Steps:**

- [ ] **Step 1: Instalacja i sprawdzenie.**
- [ ] **Step 2: README.**
- [ ] **Step 3: Pełna weryfikacja, HANDOFF.md, commit `docs: README, instalacja, stan weryfikacji`.**

```json:metadata
{"files": ["README.md", "HANDOFF.md"], "verifyCommand": "uv run pytest -q && uv run ruff check && uv run ruff format --check && uv run ty check && which algopalette", "acceptanceCriteria": ["algopalette w ~/.local/bin", "README z sekcją czego nie robić", "pełna weryfikacja policzona w handoffie"], "modelTier": "mechanical"}
```

**Koniec → jeden przegląd całego kodu Opus high; naprawy robi kontroler bez re-review; raport do użytkownika.**

## Zależności zadań

1 → 2 → 3 → 4 → {5, 6}; 2 → 7; {4, 5, 6, 7} → 8 → {9, 10} → 11.
Niezależne równolegle: po Tasku 4 można równolegle prowadzić 5, 6 i 7 (rozłączne pliki, ale 5 modyfikuje `engine.py`).
Po Tasku 8 można równolegle prowadzić 9 i 10 (oba modyfikują `app.py`, więc rejestracja zakładek musi być scalana
ostrożnie).
