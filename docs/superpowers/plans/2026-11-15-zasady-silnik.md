# Jeden panel zasad + natywny silnik — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zasady generowania ustawiane w jednej zakładce „Zasady” (zakładka na kolor, edycja zbiorcza, zakazane przedziały, jedna zasada odcienia, wybierak listy, ≥ 48 presetów, pomoc na przykładach) oraz silnik przepisany do Rusta (PyO3 + rayon) z dokładnymi gradientami i równoległym generowaniem.

**Architecture:** Model v2 bez dziedziczenia (`Slot.rules`, `None` = brak zasady) i plik `algopalette.v2` są jedynym kontraktem między Pythonem a Rustem: Python koduje sesję do JSON, Rust (`crates/core`) ją parsuje, kompiluje do funkcji celu z gradientem (liczby dualne), optymalizuje wielowątkowo i zwraca liczby; teksty i hexy składa Python. Stary silnik znika po zapisaniu danych wzorcowych, na których nowy jest sprawdzany. GUI dostaje nową zakładkę „Zasady” złożoną z trzech samodzielnych widżetów i czystej logiki edycji zbiorczej.

**Tech Stack:** Python ≥ 3.13, PySide6, coloraide, numpy; Rust (edycja 2024) z `pyo3` (abi3-py313), `rayon`, `serde`/`serde_json`; budowanie `maturin`; testy pytest + pytest-qt + `cargo test`.

**Spec:** `docs/superpowers/specs/2026-11-15-zasady-silnik-design.md` (wykonawca czyta spec i ten plan; plan nie powtarza uzasadnień ze speca).

## Global Constraints

- Praca wyłącznie w worktree `/home/qrikk/algopalette/.worktrees/zasady-silnik` (gałąź `feat/zasady-silnik`) albo w worktree pochodnych od tej gałęzi. **Katalog główny `/home/qrikk/algopalette` zostaje na `main` i nie jest dotykany** — czyta z niego launcher użytkownika. Żadne zadanie nie wykonuje `uv tool install` do domyślnych katalogów; sprawdzenia instalacji tylko z `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` w scratchpadzie.
- Wzorzec starego zachowania: `git show 4b71aeb:src/algopalette/<plik>` (`constraints.py`, `engine.py`, `hues.py`, `moods.py`). Po Tasku 4 tych plików nie ma w drzewie.
- Każdy plik `.py`: `ruff check --fix`, `ruff format`, `ty check` bez uwag. Każdy plik Rust: `cargo fmt`, `cargo clippy --all-targets -- -D warnings` bez uwag.
- Polecenia na pierwszym planie ≤ 20 s; kompilacje `cargo`, `uv sync`, pełne `pytest` i benchmarki w tle.
- Interfejs i komunikaty po polsku; Rust nie zawiera napisów interfejsu.
- Po każdym zadaniu: testy zadania + lint + typy, aktualizacja `HANDOFF.md` (§0c: stan, policzone wyniki, pułapki), dopiero potem commit. Stage’uj tylko własne pliki (nigdy `git add -A`). Commity kończą się liniami atrybucji sesji.
- **Bez przeglądu po zadaniu.** Przeglądy są dwa (Opus, effort xhigh): po etapie silnika (po Tasku 16) i po całości (po Tasku 20), z pętlą napraw z `~/.claude/CLAUDE.md`. To założenie z odpowiedzi „wszystko sie zgadza” na wiadomość z rekomendacją wariantu a — przed pierwszym przeglądem potwierdź u użytkownika jednym zdaniem.
- Modele wykonawców: zadania `mechanical`/`standard` → Sonnet, effort high; `frontier` → Opus, effort high (`"model": "opus"` w metadanych). Równolegli wykonawcy pracują w osobnych worktree na rozłącznych plikach (lista plików zadania jest wiążąca; plik spoza listy = stop i pytanie do kontrolera).
- Znany stan przejściowy: po Tasku 3 testy modułów jeszcze nieprzeniesionych na model v2 są czerwone, a GUI nie startuje do końca Tasku 15. Każde zadanie uruchamia wyłącznie testy ze swojego pola **Verify**; pełny zestaw jest zielony dopiero w Tasku 20.
- Nowe zależności (zgłosić użytkownikowi w raporcie końcowym): `maturin` (budowanie), `pyo3`, `rayon`, `serde`, `serde_json`. Znikają: `textual`, `pytest-asyncio`, `scipy`.
- Anty-cele ze speca §5 obowiązują każde zadanie (m.in. zasada w dwóch miejscach, słowo „dziedzicz”, różnice skończone w gorącej pętli, wynik zależny od liczby wątków, cicha migracja).

**User decisions (already made):**
- „ta z GUI jest wlasciwa, scal to w jedno” — jedna kopia repo: `/home/qrikk/algopalette`.
- „mi nie chodzi w ogole o warstwe pracy z kolorami, ktore juz mamy. ja mam ciagle na mysli workflow sprzed generacji jakiejkolwiek palety” — przebudowa dotyczy ustawiania zasad; zakładka Paleta traci tylko edytor warunków i zależności.
- „wybieram A” — edycja zbiorcza przez zaznaczenie kilku zakładek kolorów.
- „chodzi o podstawy - odcienie, jasnosc i nasycenie, np […] 0-270, z wyjatkiem 60-85 i 140-155” — kontrwarunki = zakazane przedziały H, L, C.
- „w 'kryminale' chodzilo o to w jaki sposob [nie] jest wytlumaczone pojecie C wzglednego i bezwzglednego”; „dziedzicz/usun. Przeciez to jest jedno i to samo”.
- „wariant silnika 1” — Rust jako biblioteka w procesie GUI.
- „usuwamy” — TUI.
- „wszystko sie zgadza” — akceptacja speca (z decyzjami agenta z §7–§10).

## Review Focus

1. Zakazane przedziały pokrywające cały dozwolony zakres (zasada niespełnialna): ocena pokazuje stałe twarde naruszenie, generowanie kończy się w budżecie i zwraca propozycje oznaczone jako złe; nic nie wisi (Task 14, Task 16).
2. Kolory zdegenerowane: C = 0 (odcień nieokreślony), L = 0 i L = 1, dwa identyczne kolory, kolor poza gamutem pod kłódką: wartości i gradienty skończone, brak NaN w wyniku (Task 5, Task 14).
3. Edycja zbiorcza przy mieszanym zaznaczeniu (tło + akcenty; nasycenie bezwzględne u jednego, względne u drugiego; zasada obecna tylko u części): wiersz „różne”, ustawienie dla wszystkich nadaje identyczną zasadę, zasady niedotyczące któregoś koloru nie są pokazywane (Task 12, Task 15).
4. Zmiana struktury palety między generowaniem a przejęciem (usunięty kolor, zmieniona liczba kolorów) oraz zamknięcie okna w trakcie generowania 128 palet: brak wyjątku, zadanie anulowane, proces kończy się (Task 17).
5. Stare pliki v1 z nietypową zawartością (zerwana zależność, zakres i cel odcienia naraz, nastrój użytkownika, budżet skrajny): wczytują się, a każda strata jest wymieniona w komunikacie (Task 3).

---

## Interfejsy dzielone (wiążące dla wszystkich zadań)

### I1. Plik i wejście silnika: `algopalette.v2`

```json
{
  "format": "algopalette.v2",
  "preset": "neutralny",
  "view_model": "oklch",
  "globals": {
    "polarity": "dark", "contrast_metric": "wcag21", "delta_e": "ok",
    "cvd": {"types": ["protan"], "method": "machado", "severity": 1.0},
    "fit_method": "oklch-chroma",
    "hue_scheme": {"kind": "equal", "rotation": 0.0, "center": 0.0, "spread": 90.0, "custom": [],
                   "tol": 15.0, "jitter": 0.0, "hard": false, "weight": 1.0},
    "lightness_spread": {"value": {"lo": null, "hi": 0.12}, "enabled": true, "hard": false, "weight": 1.0},
    "avoid_colors": [{"l": 0.7, "c": 0.1, "h": 30.0}], "avoid_distance": 0.05,
    "optimizer": {"n_proposals": 6, "seed": 0, "budget": 3000, "time_cap_s": 30.0,
                  "min_diversity": 0.05, "hard_weight": 1000.0, "threads": 0}
  },
  "slots": [{
    "id": "a1b2c3d4", "name": "", "locked": false,
    "value": {"l": 0.78, "c": 0.12, "h": 25.0}, "hex": "#e8a08c", "use_scheme": true,
    "rules": {
      "lightness": {"value": {"lo": 0.6, "hi": 0.85, "exclude": [[0.70, 0.74]]}, "enabled": true, "hard": true, "weight": 1.0},
      "chroma": {"value": {"mode": "abs", "lo": 0.06, "hi": 0.2, "exclude": []}, "enabled": true, "hard": true, "weight": 1.0},
      "hue": {"value": {"lo": 0.0, "hi": 270.0, "exclude": [[60.0, 85.0], [140.0, 155.0]]}, "enabled": true, "hard": true, "weight": 1.0},
      "contrast_bg": {"value": {"metric": null, "lo": 4.5, "hi": null}, "enabled": true, "hard": true, "weight": 1.0},
      "min_distance": {"value": 0.08, "enabled": true, "hard": false, "weight": 1.0},
      "cvd_min_distance": null,
      "extreme": null
    },
    "relations": []
  }]
}
```

- Wszystkie siedem kluczy `rules` zawsze obecne (`null` = brak zasady). `lightness_spread` to `null` albo zasada z wartością `{lo, hi}` (bez `exclude`). `relations[]`: pola jak w v1 (`kind, target, op, value, tol, chroma_op, chroma_mode, metric, other, t, enabled, hard, weight`).
- Walidacja po obu stronach: `l ∈ [0, 1]`, `c ≥ 0`, wagi ≥ 0, `seed ≥ 0`, `budget ≥ 1`, `threads ≥ 0`, 3–16 slotów, unikalne `id`; para `exclude` dla jasności/nasycenia wymaga `od < do`; dla odcienia `od ≠ do` (mod 360), zawijanie dozwolone; `hue.lo = 0, hi = 360` to pełne koło. Rust odrzuca nieznane pole (ścieżka w komunikacie); `hex`, `name`, `preset`, `view_model` są znane i bez znaczenia dla silnika.
- Wywołanie generowania dostaje dodatkowo listę `free` (id kolorów wolnych). Wartości pozostałych kolorów Python podaje już po dopasowaniu do gamutu.

### I2. Model Pythona (`src/algopalette/model.py`)

```python
@dataclass(frozen=True)
class Rule[T]:            # dawne Cond
    value: T; enabled: bool = True; hard: bool = True; weight: float = 1.0
Exclusions = tuple[tuple[float, float], ...]
@dataclass(frozen=True)
class Interval:  lo: float | None = None; hi: float | None = None                 # rozrzut jasności
@dataclass(frozen=True)
class Band:      lo: float | None = None; hi: float | None = None; exclude: Exclusions = ()
@dataclass(frozen=True)
class ChromaBand: mode: ChromaMode; lo: float | None; hi: float | None; exclude: Exclusions = ()
@dataclass(frozen=True)
class HueArc:    lo: float; hi: float; exclude: Exclusions = ()                   # lo > hi = przez 0°
@dataclass(frozen=True)
class SlotRules:
    lightness: Rule[Band] | None = None;  chroma: Rule[ChromaBand] | None = None
    hue: Rule[HueArc] | None = None;      contrast_bg: Rule[ContrastBound] | None = None
    min_distance: Rule[float] | None = None; cvd_min_distance: Rule[float] | None = None
    extreme: Rule[Literal["weakest", "strongest"]] | None = None
RULE_FIELDS: tuple[str, ...]              # kolejność jak wyżej
def rule_fields_for(role: Role) -> tuple[str, ...]   # tło: bez contrast_bg; min_distance/cvd/extreme tylko akcent
@dataclass(frozen=True)
class Slot: id; name = ""; locked = False; value; rules: SlotRules = SlotRules(); use_scheme: bool = True; relations = ()
@dataclass(frozen=True)
class OptimizerSettings: n_proposals = 6; seed = 0; budget = 3000; time_cap_s = 30.0; min_diversity = 0.05; hard_weight = 1000.0; threads = 0
class GlobalSettings      # jak v1 bez role_defaults
@dataclass(frozen=True)
class Session: globals; slots; preset: str | None = None; view_model: ViewModel = "oklch"
def default_rules(role: Role, polarity, contrast_metric) -> SlotRules   # liczby z dawnego default_role_defaults
def default_session() -> Session          # ciemna, 10 kolorów, zasady default_rules, preset "neutralny"
def arc_width(lo: float, hi: float) -> float                 # (hi − lo) mod 360; 0 przy lo ≠ hi → 360
def arc_from_center(center: float, half: float) -> tuple[float, float]
def arc_center_half(lo: float, hi: float) -> tuple[float, float]
def arc_intersection(a: tuple[float, float], b: tuple[float, float]) -> list[tuple[float, float]]   # 0, 1 albo 2 łuki
# bez zmian sygnatur: role_of, new_slot_id, slot_index, with_slot, broken_relations, remove_slot, move_slot, History
def add_accent(session) -> Session        # nowy akcent kopiuje rules i use_scheme ostatniego akcentu, bez relations
```
Znikają: `Cond`, `HueRange`, `HueTarget`, `ChromaRange`, `SlotConditions`, `CONDITION_FIELDS`, `effective_conditions`, `snapshot_key`, `default_role_defaults`, `Session.mood`, `Session.mood_snapshot`.

### I3. Moduł natywny `algopalette._engine` (PyO3)

```python
def build_info() -> dict            # {"version": str, "profile": "release"|"debug", "implemented": list[str]}
def validate(session_json: str) -> None                 # ValueError("<ścieżka>: <opis>")
def evaluate(session_json: str) -> dict                 # {"objective": float, "violations": [V, ...]}
def hue_targets(session_json: str) -> dict[str, float]
def start(session_json: str, free: list[str]) -> Job
class Job:
    def poll(self) -> dict          # {"state": "running"|"done"|"cancelled"|"failed", "progress": float, "candidates": int, "error": str | None}
    def cancel(self) -> None
    def result(self) -> dict        # {"proposals": [P, ...], "timed_out": bool, "cancelled": bool, "runs": int, "elapsed_s": float}
def max_chroma(l: float, h: float) -> float
def delta_e(a: list[float], b: list[float], method: str) -> float        # a, b = [l, c, h]
def contrast(text: list[float], bg: list[float], metric: str) -> float
def simulate_cvd(c: list[float], kind: str, method: str, severity: float) -> list[float]
```
- `implemented` rośnie z zadaniami: Task 4 `["schema"]`, Task 5 `+"color"`, Task 14 `+"evaluate"`, Task 16 `+"generate"`. Funkcja niezaimplementowana rzuca `NotImplementedError`; do Tasku 14 `evaluate` zwraca pusty wynik, a `hue_targets` `{}`; do Tasku 16 `start` daje zadanie od razu `done` z pustą listą. Testy zależne od funkcji mają `pytest.mark.skipif(<nazwa> not in build_info()["implemented"])`.
- `P` = `{"values": {id: [l, c, h]}, "score": float, "violations": [V, ...], "run": int, "wave": int}`; kolejność listy: bez twardych naruszeń najpierw, potem rosnąco wg `score`.
- `V` = `{"key", "slots": [id], "kind", "hard", "amount", "achieved", "req": {...}, "meta": {...}}`:

| `kind` | `key` | `req` | `meta` |
|---|---|---|---|
| `lightness`, `chroma`, `contrast_bg` | `slot:<id>:<kind>` | `{"lo", "hi"}` | chroma: `mode`; contrast: `metric` |
| `hue` | `slot:<id>:hue` | `{"lo", "hi"}` | — |
| `exclude` | `slot:<id>:<kanał>:exclude:<k>` | `{"lo", "hi"}` | `channel`, przy chroma `mode` |
| `extreme` | `slot:<id>:extreme` | `{"bound"}` | `which`, `metric` |
| `pair_distance` | `pair:<a>:<b>:min_distance` | `{"min"}` | `method` |
| `pair_cvd` | `pair:<a>:<b>:cvd:<typ>` | `{"min"}` | `method`, `cvd` |
| `rel` | `slot:<id>:rel:<rodzaj>:<n>` | `{"op", "value", "tol"}` | `rel_kind`, `chroma_op`, `chroma_mode`, `metric` |
| `spread` | `global:lightness_spread` | `{"lo", "hi"}` | — |
| `scheme` | `global:scheme:<id>` | `{"target", "tol"}` | — |
| `avoid` | `global:avoid:<id>:<k>` | `{"min"}` | — |
| `gamut` | `slot:<id>:gamut` | `{"hi"}` | — |
| `diversity` | `global:diversity` | `{"min"}` | — (tylko w propozycjach) |

### I4. Nakładka `src/algopalette/engine.py`

```python
@dataclass(frozen=True)
class Violation: key: str; slot_ids: tuple[str, ...]; kind: str; hard: bool; amount: float; achieved: float; req: Mapping[str, Any]; meta: Mapping[str, Any]
@dataclass(frozen=True)
class Proposal: values; hexes; fit_deltas; score: float; violations: tuple[Violation, ...]; timed_out: bool; seed: int; slot_ids: tuple[str, ...]
    # .ok = nie timed_out i brak twardych naruszeń
@dataclass(frozen=True)
class Progress: state: str; fraction: float; candidates: int; error: str | None
class Generation:
    def poll(self) -> Progress; def cancel(self) -> None; def result(self) -> list[Proposal]
def to_engine_json(session: Session, free: Collection[str]) -> str     # kolory spoza `free` po col.fitted
def start(session: Session, slot_ids: Collection[str] | None = None) -> Generation   # wolne = bez kłódki ∩ slot_ids
def generate(session, *, slot_ids=None, progress=None, cancel=None) -> list[Proposal]   # blokujące: testy, narzędzia
def current_violations(session: Session) -> list[Violation]            # free = [], wszystkie kolory po fit
def objective(session: Session) -> float
def hue_targets(session: Session) -> dict[str, float]
def apply_proposal(session, proposal, slot_ids=None) -> Session        # pomija kłódki i id nieobecne w sesji
def slot_label(session: Session, index: int) -> str                    # przeniesione z constraints
```
`forms.violation_text(v: Violation, session: Session) -> tuple[str, str, str]` (etykieta, wymagane, osiągnięte) odtwarza polskie napisy z `constraints.py@4b71aeb`; nowe: etykieta „odcień (<kolor>)” dla `hue`, „zakazany przedział: <kanał> (<kolor>)” dla `exclude` z wymaganiem „poza <od>–<do>”.

### I5. Rdzeń Rusta (`crates/core/src`, biblioteka `algopalette_core`)

```rust
// schema.rs (Task 4): struktury serde 1:1 z I1, #[serde(deny_unknown_fields)]
pub fn parse(json: &str) -> Result<Session, SchemaError>;        // SchemaError { path: String, msg: String }
// rng.rs (Task 4): algorytm zamrożony — SplitMix64(seed, stream) → xoshiro256++
impl Rng { pub fn new(seed: u64, stream: u64) -> Self; pub fn next_u64(&mut self) -> u64;
           pub fn uniform(&mut self) -> f64; pub fn range(&mut self, lo: f64, hi: f64) -> f64; }
// objective.rs (Task 4)
pub struct Score { pub feasible: bool, pub total: f64 }           // feasible = żaden twardy term > 1e-9; total bez marginesu
pub trait Objective: Sync {
    fn dim(&self) -> usize;
    fn bounds(&self) -> (&[f64], &[f64]);                         // zmienna okresowa (odcień bez granic): −inf, +inf
    fn sample(&self, rng: &mut Rng, out: &mut [f64]);             // losowy start w granicach
    fn current(&self, out: &mut [f64]);                           // start z bieżących wartości palety
    fn value_grad(&self, x: &[f64], grad: &mut [f64]) -> f64;     // z marginesem twardych
    fn score(&self, x: &[f64]) -> Score;
    fn distance(&self, a: &[f64], b: &[f64]) -> f64;              // średnie ΔE ok odpowiadających sobie kolorów wolnych
    fn repulsion(&self, x: &[f64], others: &[Vec<f64>], min_div: f64, grad: &mut [f64]) -> f64;   // dodaje do grad
}
// violation.rs (Task 4): struct Violation (Serialize) wg tabeli I3
// scalar.rs + color/ (Task 5)
pub trait Scalar: Copy + PartialOrd + Add<Output = Self> + Sub<Output = Self> + Mul<Output = Self> + Div<Output = Self> + Neg<Output = Self> {
    fn c(v: f64) -> Self; fn val(self) -> f64;
    fn sqrt(self) -> Self; fn cbrt(self) -> Self; fn powf(self, p: f64) -> Self; fn exp(self) -> Self; fn ln(self) -> Self;
    fn sin(self) -> Self; fn cos(self) -> Self; fn atan2(self, x: Self) -> Self; fn abs(self) -> Self; fn hypot(self, o: Self) -> Self;
}
pub struct Dual<const N: usize> { pub v: f64, pub d: [f64; N] }  // impl Scalar; f64 też impl Scalar
pub fn oklch_to_oklab<T: Scalar>(lch: [T; 3]) -> [T; 3];
pub fn oklab_to_linear_srgb<T: Scalar>(lab: [T; 3]) -> [T; 3];
pub fn max_chroma<T: Scalar>(l: T, h: T) -> T;                   // wartość bisekcją, pochodne z funkcji niejawnej
pub fn in_gamut(lch: [f64; 3]) -> bool;                          // kanały liniowe w [−1e-6, 1 + 1e-6]
pub fn contrast<T: Scalar>(text_lab: [T; 3], bg_lab: [T; 3], metric: ContrastMetric) -> T;   // APCA: |Lc|
pub fn delta_e<T: Scalar>(a_lab: [T; 3], b_lab: [T; 3], method: DeltaE) -> T;
pub fn simulate_cvd<T: Scalar>(lab: [T; 3], kind: CvdKind, method: CvdMethod, severity: f64) -> [T; 3];
// rules/ (Task 14)
pub struct Problem; impl Objective for Problem {}
impl Problem { pub fn compile(session: &Session, free: &[String]) -> Problem;
               pub fn decode(&self, x: &[f64]) -> Vec<[f64; 3]>;                    // OKLCH wszystkich kolorów, wolne w gamucie
               pub fn free_ids(&self) -> &[String]; }
pub struct Evaluation { pub objective: f64, pub violations: Vec<Violation> }
pub fn evaluate(session: &Session) -> Evaluation;                 // wartości z sesji, bez marginesu
pub fn hue_targets(session: &Session) -> Vec<(String, f64)>;
// optim/ (Task 6)
pub struct DriverOpts { pub n: usize, pub seed: u64, pub budget: usize, pub time_cap: Duration, pub min_diversity: f64, pub threads: usize }
pub struct Control { /* atomowe: cancel, evals_done, evals_planned, candidates */ }
pub struct Candidate { pub x: Vec<f64>, pub score: Score, pub run: u32, pub wave: u32, pub diverse: bool }
pub struct Outcome { pub chosen: Vec<Candidate>, pub timed_out: bool, pub cancelled: bool, pub runs: u32 }
pub fn generate<O: Objective>(obj: &O, opts: &DriverOpts, ctl: &Control) -> Outcome;
pub struct Job; impl Job { pub fn spawn<O: Objective + Send + 'static>(obj: O, opts: DriverOpts) -> Job;   // + poll/cancel/result
```

### I6. Widżety i logika GUI

```python
# gui/band.py (Task 9)
class BandSlider(QWidget):
    changed = Signal(object, object, object)        # lo, hi, exclude
    def __init__(self, lo, hi, exclude=(), *, minimum, maximum, step, fmt=".3f", wrap=False, allow_none=False,
                 gradient=None, center_fields=False, parent=None)
    def values(self) -> tuple[float | None, float | None, Exclusions]
    def set_values(self, lo, hi, exclude) -> None
# gui/picker.py (Task 10)
class ListPicker(QWidget):
    changed = Signal(object)                        # tuple[float, ...] (mode="hue") albo tuple[OKLCH, ...] (mode="color")
    def __init__(self, items, *, mode: Literal["hue", "color"], max_items: int | None = None, parent=None)
    def items(self) -> tuple; def set_items(self, items) -> None
# gui/colorstrip.py (Task 11)
@dataclass(frozen=True)
class StripEntry: id: str; label: str; hex: str; accent: bool
@dataclass(frozen=True)
class Selection: palette: bool; ids: tuple[str, ...]          # palette=True ⇒ ids == ()
class ColorStrip(QWidget):
    selection_changed = Signal(object)              # Selection
    def set_entries(self, entries: Sequence[StripEntry]) -> None      # zachowuje zaznaczenie istniejących id
    def selection(self) -> Selection
    def select(self, ids: Sequence[str]) -> None; def select_palette(self) -> None; def select_all_accents(self) -> None
# rules_edit.py (Task 12, bez Qt)
@dataclass(frozen=True)
class Merged: state: Literal["same", "mixed", "absent"]; rule: Rule[Any] | None; per_slot: tuple[tuple[str, Rule[Any] | None], ...]
def applicable_fields(session, ids: Sequence[str]) -> tuple[str, ...]          # część wspólna rule_fields_for
def merged_rule(session, ids, field: str) -> Merged
def set_rule(session, ids, field: str, rule: Rule[Any] | None) -> Session       # None = usuń u wszystkich
def update_rule(session, ids, field: str, **changes: Any) -> Session            # tylko tam, gdzie zasada istnieje
def merged_use_scheme(session, ids) -> bool | None                              # None = różne
def set_use_scheme(session, ids, on: bool) -> Session
# presets.py (Task 8)
@dataclass(frozen=True)
class Preset: name: str; category: str; description: str; builtin: bool; polarities: tuple[str, ...]
CATEGORIES: tuple[str, ...]
def list_presets() -> list[Preset]; def search(query: str, category: str | None = None) -> list[Preset]
def apply_preset(session, name: str, *, polarity: str | None = None) -> Session
def is_modified(session) -> bool
def change_polarity(session, polarity: str, *, reapply: bool) -> Session
def save_user_preset(name: str, session, description: str = "") -> None; def delete_user_preset(name: str) -> None
def migrate_user_moods() -> int
# gui/app.py (Task 15)
MainWindow.show_rules(self, ids: Sequence[str]) -> None       # otwiera „Zasady” z zaznaczonymi kolorami
MainWindow.generate(self) -> None                             # start generowania + przejście do Propozycji
```
Klucze pomocy nowych elementów mają przedrostek `rules.` (zakładka) i `concept.` (pojęcia); `Topic` dostaje pole `term: bool = False` (Task 13).

## Kolejność i równoległość

```
bez zależności:  1 → 3 → 4          (łańcuch kontraktów — kontroler)
                 2, 9, 10, 11, 13   (od razu, równolegle z łańcuchem)
po 4:            5, 6, 7, 8, 12     (równolegle)
po 5:            14        po 7, 8, 9, 10, 11, 12:  15
po 6 i 14:       16  → PRZEGLĄD 1 (silnik: Taski 4–6, 14, 16)
po 15:           17 (też po 7), 18 (też po 13)
po 8 i 16:       19        po 16–19:  20  → PRZEGLĄD 2 (całość)
```

---

### Task 1: Dane wzorcowe ze starego silnika

**Goal:** Zapisać w repo dane, na których nowy kod udowodni zgodność oceny zasad i brak regresji jakości, zanim stary silnik zniknie.

**Files:**
- Create: `tools/make_v1_reference.py`
- Create: `tests/fixtures/v1_reference/eval.json`, `tests/fixtures/v1_reference/quality.json`, `tests/fixtures/v1_reference/README.md`

**Acceptance Criteria:**
- [ ] `eval.json`: 300 przypadków `{"session": <dict v1>, "objective": float, "violations": [{"key", "hard", "amount"}]}`, generator `random.Random(20261115)`, dwa uruchomienia dają identyczny plik.
- [ ] Wśród naruszeń każdy rodzaj klucza występuje ≥ 10 razy: `lightness`, `chroma`, `hue_range`, `hue_target`, `contrast_bg`, `extreme`, `min_distance`, `cvd:`, `rel:hue`, `rel:lightness`, `rel:chroma`, `rel:contrast`, `rel:distance`, `rel:mix`, `lightness_spread`, `scheme`, `avoid`.
- [ ] Żaden przypadek nie ma naraz włączonego `hue_range` i `hue_target` w warunkach obowiązujących kolor; `hue_scheme.jitter == 0` wszędzie.
- [ ] `quality.json`: 36 przypadków (9 nastrojów × 2 polaryzacje × 2 metryki) `{"mood", "polarity", "metric", "session": <dict v1>, "ok_count", "best_score", "scores"}` przy 6 propozycjach, `max_evals = 30000`, `seed = 1`.
- [ ] `README.md` mówi, z którego commita pochodzą dane i że nie wolno ich odtwarzać nowym kodem.

**Verify:** `uv run python tools/make_v1_reference.py --check` → `eval: 300 przypadków, quality: 36 przypadków, pokrycie kluczy OK`

**Reguły generatora (eval):**
- Start `default_session()`; liczba akcentów 1–14; polaryzacja i metryka losowo przez `globals_logic.change_polarity_or_metric`; `delta_e`: ok 40%, pozostałe po 15%; CVD: 50% bez typów, inaczej losowy niepusty podzbiór, metoda losowa, nasilenie z {1.0, 0.6}.
- Układ odcieni: rodzaj losowy (także `custom` z 1–6 odcieniami i `none`), twardy w 20%; rozrzut jasności w 30%; unikane kolory w 20% (1–3 kolory, odległość 0.03–0.08).
- Warunki ról: każde pole z prawdopodobieństwem 50% zastąpione losową poprawną wartością; `enabled` 90%, `hard` 60%, waga z {0.5, 1, 2}. Warunki własne koloru: każde pole 25%. Zależności: 0–2 na kolor, wszystkie rodzaje, 5% z nieistniejącym celem. Kłódka 15%.
- Wartości kolorów: L ∈ [0.05, 0.97], H ∈ [0, 360), C = u · `color.max_chroma(L, H)`, u ∈ [0, 1]; 10% kolorów z C × 1.3 (poza gamutem).
- Naruszenia: `forms.current_violations(session)`; funkcja celu: `constraints.objective` na kolorach po `color.fitted`, z `hard_weight` sesji.
- `quality`: `apply_mood` po ustawieniu polaryzacji i metryki; `best_score` = najmniejszy `score` wśród propozycji `ok` (gdy brak: wśród wszystkich).

**Steps:**
- [ ] Napisz generator z trybami domyślnym (zapis) i `--check` (liczby + pokrycie kluczy, bez zapisu).
- [ ] Uruchom zapis w tle (część `quality` trwa kilka minut), potem `--check`.
- [ ] ruff/ty; handoff; commit `test: dane wzorcowe v1 (ocena zasad, jakość silnika)`.

```json:metadata
{"files": ["tools/make_v1_reference.py", "tests/fixtures/v1_reference/eval.json", "tests/fixtures/v1_reference/quality.json", "tests/fixtures/v1_reference/README.md"], "verifyCommand": "uv run python tools/make_v1_reference.py --check", "acceptanceCriteria": ["eval.json: 300 deterministycznych przypadków", "każdy rodzaj klucza naruszenia ≥ 10 razy", "nigdy naraz włączony hue_range i hue_target; jitter 0", "quality.json: 36 przypadków z ok_count i best_score", "README z commitem źródłowym"], "modelTier": "standard"}
```

### Task 2: Usunięcie TUI

**Goal:** Usunąć stary interfejs tekstowy i jego zależności.

**Files:**
- Delete: `src/algopalette/tui/` (cały katalog), `tests/tui/` (cały katalog)
- Modify: `src/algopalette/__main__.py` (flaga `--tui`), `pyproject.toml` (`textual`, `pytest-asyncio`, `asyncio_*`, wpis `per-file-ignores` dla `tui`, opis projektu), `README.md` (wzmianki o TUI), `uv.lock`

**Acceptance Criteria:**
- [ ] `grep -rIil "textual\|--tui\|algopalette.tui" src tests pyproject.toml README.md` nic nie zwraca.
- [ ] `uv run algopalette --help` nie wymienia `--tui` i kończy się kodem 0.
- [ ] `uv run pytest -q tests/gui/test_gui_app.py` przechodzi (zadanie nie zależy od modelu v2; jeśli gałąź ma już Task 3, pomiń ten punkt i odnotuj w handoffie).

**Verify:** `grep -rIil "textual\|--tui\|algopalette.tui" src tests pyproject.toml README.md; uv run algopalette --help | grep -c tui` → brak plików, `0`

**Steps:**
- [ ] Usuń katalogi i wpisy; `uv lock` w tle.
- [ ] Sprawdzenia z **Verify**; ruff/ty; handoff; commit `chore: usunięcie TUI i zależności textual`.

```json:metadata
{"files": ["src/algopalette/tui/", "tests/tui/", "src/algopalette/__main__.py", "pyproject.toml", "README.md", "uv.lock"], "verifyCommand": "grep -rIil 'textual\\|--tui\\|algopalette.tui' src tests pyproject.toml README.md; uv run algopalette --help | grep -c tui", "acceptanceCriteria": ["brak wzmianek o textual/--tui/algopalette.tui", "algopalette --help bez --tui, kod 0", "testy GUI aplikacji nadal przechodzą (przed Taskiem 3)"], "modelTier": "mechanical"}
```

### Task 3: Model v2, plik v2, migracja v1

**Goal:** Wprowadzić model zasad bez dziedziczenia, zapis `algopalette.v2` i wierną, głośną migrację plików v1.

**Files:**
- Modify: `src/algopalette/model.py`, `src/algopalette/io.py`
- Create: `src/algopalette/migrate.py`
- Modify: `tests/test_model.py`, `tests/test_io.py`
- Create: `tests/test_migrate.py`

**Acceptance Criteria:**
- [ ] `model.py` zgodny z I2; `default_session()` ma 10 kolorów, `preset == "neutralny"`, zasady równe `default_rules` roli (liczby jak `default_role_defaults@4b71aeb`).
- [ ] `io.session_to_dict` daje dokument zgodny z I1; `session_from_dict(session_to_dict(s)) == s` dla sesji z każdą zasadą, zakazami, zależnościami każdego rodzaju.
- [ ] `io.load_session_ex(path) -> tuple[Session, tuple[str, ...]]` wczytuje v1 i v2; `load_session(path)` zwraca samą sesję; zapis zawsze v2; `FORMAT == "algopalette.v2"`.
- [ ] `migrate.migrate_v1(data: dict) -> tuple[dict, list[str]]` spełnia tabelę przypadków niżej; wszystkie 300 sesji z `eval.json` i 36 z `quality.json` migrują się bez komunikatów i przechodzą `session_from_dict`.
- [ ] Błędy formatu nadal jako `SessionFormatError` ze ścieżką; plik v2 z parą zakazu `od ≥ do` (jasność/nasycenie) jest odrzucany.

**Verify:** `uv run pytest -q tests/test_model.py tests/test_io.py tests/test_migrate.py` → wszystkie przechodzą

**Przypadki migracji (wejście v1 → wynik v2):**

| Wejście | Wynik |
|---|---|
| pole koloru `null`, rola ma warunek | zasada = warunek roli (kopia) |
| pole koloru ustawione | zasada = warunek koloru |
| tylko `hue_range(330, 20)` | `hue` = łuk 330–20 z flagami zakresu |
| tylko `hue_target(30, 15)` twardy | `hue` = łuk 15–45, twardy |
| oba, włączony tylko cel | `hue` z celu; komunikat wymienia kolor |
| oba wyłączone | `hue` z zakresu (wyłączona); komunikat |
| oba włączone, zakres 0–90 miękki waga 1, cel 60 ± 20 twardy waga 2 | `hue` = 40–80, twarda, waga 2; komunikat |
| oba włączone, zakres 0–60, cel 200 ± 10 | `hue` = 0–60 z flagami zakresu; komunikat |
| oba włączone, część wspólna to dwa łuki (zakres 300–60 przez 0, cel 180 ± 150) | `hue` z zakresu; komunikat |
| kolor miał jakikolwiek warunek odcienia (także wyłączony, także z roli) | `use_scheme = False`; inaczej `True` |
| `mood` z listy dziewięciu dawnych nazw | `preset` = ta nazwa; inna nazwa → `None` |
| `max_evals` 30000 / 100 / 5000000 | `budget` 3000 / 300 / 100000 (÷ 10, w granicach 300–100 000) |
| zerwana zależność, ujemne `h`, `view_model` brak | zachowane / `h mod 360` / `"oklch"` |

Komunikat ma postać jednego zdania po polsku z nazwą koloru (`slot_label`), np. „akcent 3: zakres i cel odcienia scalono do 40–80°, zasada jest teraz twarda”.

**Steps:**
- [ ] Testy modelu i `arc_*` (m.in. `arc_intersection((300, 60), (30, 330))` → dwa łuki; `arc_center_half(330, 10) == (350, 20)`).
- [ ] Testy migracji wg tabeli + masowy test na `eval.json`/`quality.json`.
- [ ] Implementacja; migracja działa na słownikach (nie odtwarza starych klas).
- [ ] ruff/ty; handoff (lista modułów, które po tym zadaniu są czerwone); commit `feat: model zasad v2, plik algopalette.v2, migracja v1`.

```json:metadata
{"files": ["src/algopalette/model.py", "src/algopalette/io.py", "src/algopalette/migrate.py", "tests/test_model.py", "tests/test_io.py", "tests/test_migrate.py"], "verifyCommand": "uv run pytest -q tests/test_model.py tests/test_io.py tests/test_migrate.py", "acceptanceCriteria": ["model zgodny z I2, default_session: 10 kolorów, preset neutralny", "zapis/odczyt v2 zgodny z I1, round-trip", "load_session_ex zwraca komunikaty migracji", "migrate_v1 spełnia tabelę przypadków; 336 sesji wzorcowych migruje bez komunikatów", "walidacja: SessionFormatError ze ścieżką"], "modelTier": "frontier", "model": "opus"}
```

### Task 4: Rusztowanie Rusta, kontrakty, nakładka silnika

**Goal:** Postawić przestrzeń Cargo i moduł `_engine` z pełnym interfejsem I3 (na razie z zaślepkami), zamrozić kontrakty I5 w kodzie, przepiąć Pythona na nakładkę I4 i usunąć stary silnik.

**Files:**
- Create: `Cargo.toml` (workspace), `crates/core/Cargo.toml`, `crates/core/src/{lib,schema,rng,objective,violation}.rs`, `crates/core/tests/schema_contract.rs`, `crates/py/Cargo.toml`, `crates/py/src/lib.rs`, `crates/cli/Cargo.toml`, `crates/cli/src/main.rs` (na razie `--version`)
- Create: `tests/fixtures/v2_contract/*.json`, `tests/test_engine_api.py`
- Modify: `pyproject.toml` (backend `maturin`, `[tool.maturin]`, `[tool.uv] cache-keys` na pliki Rusta, usunięcie `scipy`), `.gitignore` (`target/`, `src/algopalette/_engine*.so`), `src/algopalette/engine.py` (nakładka I4), `src/algopalette/forms.py` (`violation_text`, usunięcie `current_violations`), `uv.lock`
- Delete: `src/algopalette/constraints.py`, `src/algopalette/hues.py`, `tests/test_constraints.py`, `tests/test_engine.py`, `tests/test_hues.py`

**Acceptance Criteria:**
- [ ] `uv sync` buduje rozszerzenie; `_engine.build_info()` zwraca `profile == "release"` i `implemented == ["schema"]`.
- [ ] `_engine.validate` przyjmuje każdy plik z `tests/fixtures/v2_contract/` (40 zmigrowanych sesji z `eval.json` + ręczne z zakazami, pełnym kołem, 16 kolorami); dla dokumentu z nieznanym polem `slots[2].rules.hue.value.foo` rzuca `ValueError` zawierający tę ścieżkę.
- [ ] `cargo test -p algopalette-core` przechodzi: parsowanie tych samych plików kontraktu; `Rng::new(1, 0)` daje zapisane w teście pierwsze 4 wartości `next_u64` (zamrożenie).
- [ ] Nakładka: `to_engine_json` podaje kolory spoza `free` po `color.fitted`; `start(...).poll().state == "done"` na zaślepce; `current_violations` zwraca `[]` na zaślepce; `apply_proposal` pomija kłódki i nieznane id.
- [ ] `forms.violation_text` odtwarza napisy v1 dla każdego `kind` z I3 (test na ręcznie zbudowanych `Violation`).
- [ ] Instalacja narzędzia w scratchpadzie (`UV_TOOL_DIR`, `UV_TOOL_BIN_DIR`): `uv tool install --editable .` → `algopalette --help` działa, `_engine` importuje się, profil release. Jeśli tryb edytowalny nie działa z maturin: instalacja zwykła + polecenie przebudowy opisane w handoffie i zgłoszone użytkownikowi (spec §12).

**Verify:** `cargo test -p algopalette-core && uv run pytest -q tests/test_engine_api.py` → wszystkie przechodzą

**Reguły:**
- `crates/py`: `crate-type = ["cdylib"]`, moduł `algopalette._engine`, `pyo3` z `abi3-py313`; `[tool.maturin]`: `manifest-path = "crates/py/Cargo.toml"`, `python-source = "src"`, `module-name = "algopalette._engine"`, `profile = "release"`.
- Profil release w workspace: `opt-level = 3`, `lto = "thin"`, `codegen-units = 1`, `panic = "abort"` wyłączone (panika ma zostać wyjątkiem Pythona).
- Pliki kontraktu generuje test Pythona z `eval.json` przez `migrate_v1` (zapis przy braku plików; potem tylko porównanie), więc Python i Rust czytają te same bajty.
- Wersje zależności: najnowsze stabilne; zapisz je w handoffie.

**Steps:**
- [ ] Workspace + `schema.rs` + test kontraktu (czerwony → zielony).
- [ ] `rng.rs`, `objective.rs`, `violation.rs` wg I5.
- [ ] `crates/py` z funkcjami I3 (zaślepki wg I3) + `tests/test_engine_api.py`.
- [ ] Nakładka `engine.py`, `forms.violation_text`; usunięcie starego silnika i jego testów.
- [ ] Sprawdzenie instalacji narzędzia w scratchpadzie.
- [ ] fmt/clippy/ruff/ty; handoff; commit `feat: przestrzeń Cargo, moduł _engine (kontrakty), nakładka silnika; usunięty silnik Pythona`.

```json:metadata
{"files": ["Cargo.toml", "crates/core/", "crates/py/", "crates/cli/", "tests/fixtures/v2_contract/", "tests/test_engine_api.py", "pyproject.toml", ".gitignore", "src/algopalette/engine.py", "src/algopalette/forms.py", "uv.lock", "src/algopalette/constraints.py", "src/algopalette/hues.py", "tests/test_constraints.py", "tests/test_engine.py", "tests/test_hues.py"], "verifyCommand": "cargo test -p algopalette-core && uv run pytest -q tests/test_engine_api.py", "acceptanceCriteria": ["uv sync buduje _engine w profilu release, implemented == [schema]", "validate przyjmuje pliki kontraktu i odrzuca nieznane pole ze ścieżką", "cargo test: kontrakt schematu + zamrożony Rng", "nakładka engine.py wg I4 działa na zaślepkach", "forms.violation_text dla każdego kind", "instalacja narzędzia w scratchpadzie działa (albo opisany tryb zastępczy)"], "modelTier": "frontier", "model": "opus"}
```

### Task 5: Matematyka koloru w Ruście

**Goal:** Dokładne przekształcenia, kontrast, ΔE i symulacja CVD jako funkcje generyczne po typie skalarnym, z pochodnymi przez liczby dualne.

**Files:**
- Create: `crates/core/src/scalar.rs`, `crates/core/src/color/{mod,convert,gamut,contrast,delta_e,cvd}.rs`
- Modify: `crates/core/src/lib.rs` (moduły), `crates/py/src/lib.rs` (`max_chroma`, `delta_e`, `contrast`, `simulate_cvd`; `implemented += "color"`)
- Create: `tests/test_engine_color.py`

**Acceptance Criteria:**
- [ ] Sygnatury z I5; `f64` i `Dual<N>` implementują `Scalar`.
- [ ] Zgodność z wyrocznią (`algopalette.color` i `algopalette.color.fast`) na 2000 losowych kolorach w gamucie (ziarno stałe) i na brzegach (C = 0; L = 0; L = 1; para identycznych kolorów): przekształcenia, `max_chroma`, kontrast WCAG/APCA ≤ 1e-9; ΔE `ok`, `hyab`, CVD (3 typy × 3 metody × nasilenie 1.0 i 0.6) ≤ 1e-6; ΔE `2000`, `itp`, `cam16` ≤ 1e-4.
- [ ] Pochodne `Dual` każdej funkcji publicznej zgodne z różnicą centralną (błąd względny ≤ 1e-5) w 200 losowych punktach z dala od załamań; `max_chroma` także.
- [ ] Brak NaN/inf w wartościach i pochodnych dla: C = 0, L = 0, L = 1, ΔE dwóch identycznych kolorów (pochodna 0), kontrastu koloru z samym sobą.

**Verify:** `cargo test -p algopalette-core color && uv run pytest -q tests/test_engine_color.py` → wszystkie przechodzą

**Reguły:**
- Stałe i wzory: `color/fast.py` (macierze OKLab, WCAG, APCA 0.0.98G-4g z `color/apca.py`, Brettel/Viénot/Machado), `hyab` liczony w OKLab jak `fast.delta_e`. `2000`, `itp`, `cam16`: wynik ma się zgadzać z `algopalette.color.delta_e` (coloraide) — warunki obserwacji i punkt bieli odczytaj z kodu coloraide w `.venv`, test jest rozstrzygający.
- Funkcje koloru przyjmują OKLab (konwersja z OKLCH raz na kolor). `simulate_cvd` zwraca OKLab bez przycinania do gamutu (jak `fast.simulate_cvd`).
- `max_chroma`: wartość bisekcją na `f64` (tolerancja ≤ 1e-7), pochodne po L i H z twierdzenia o funkcji niejawnej na kanale ograniczającym.

**Steps:**
- [ ] `scalar.rs` z testami arytmetyki `Dual`.
- [ ] Moduły koloru: najpierw test z wyrocznią (przez `_engine`), potem implementacja; kolejność: convert, gamut, contrast, ΔE ok/hyab, CVD, ΔE 2000, itp, cam16.
- [ ] Testy pochodnych i przypadków zdegenerowanych (Review Focus 2).
- [ ] fmt/clippy/ruff/ty; handoff; commit `feat(engine): matematyka koloru w Ruście z pochodnymi`.

```json:metadata
{"files": ["crates/core/src/scalar.rs", "crates/core/src/color/", "crates/core/src/lib.rs", "crates/py/src/lib.rs", "tests/test_engine_color.py"], "verifyCommand": "cargo test -p algopalette-core color && uv run pytest -q tests/test_engine_color.py", "acceptanceCriteria": ["sygnatury I5, Scalar dla f64 i Dual<N>", "zgodność z wyrocznią w tolerancjach 1e-9 / 1e-6 / 1e-4", "pochodne Dual zgodne z różnicą centralną ≤ 1e-5", "brak NaN/inf w przypadkach zdegenerowanych"], "modelTier": "frontier", "model": "opus"}
```

### Task 6: Optymalizator, sterownik równoległy, zadanie

**Goal:** Deterministyczne, wielowątkowe generowanie N różnorodnych rozwiązań dowolnego `Objective`, z budżetem, limitem czasu, postępem i przerwaniem.

**Files:**
- Create: `crates/core/src/optim/{mod,lbfgsb,select,driver,job}.rs`
- Modify: `crates/core/src/lib.rs` (moduł `optim`), `crates/core/Cargo.toml` (`rayon`)

**Acceptance Criteria:**
- [ ] `lbfgsb`: kwadratowa funkcja z granicami → optimum na granicy z dokładnością 1e-6; Rosenbrock 10-D → f ≤ 1e-8 w ≤ 2000 ocen; zmienna okresowa (granice ±inf) nie psuje zbieżności.
- [ ] Liczba wywołań `value_grad` w jednym przebiegu ≤ `budget` (wliczając ocenę puli startów).
- [ ] `generate` dla funkcji z ≥ N rozdzielonymi minimami zwraca N kandydatów parami odległych o ≥ `min_diversity`, wszyscy `diverse == true`; dla funkcji z jednym minimum zwraca N kandydatów, z których N − 1 ma `diverse == false`, po najwyżej 3 falach.
- [ ] Determinizm: `threads = 1` i `threads = 8` dają bitowo identyczny `Outcome` (x, score, run, wave) na funkcji wielomodalnej; dwa kolejne wywołania też.
- [ ] Kolejność `chosen`: `feasible` najpierw, potem rosnąco `total`, remisy wg `run`.
- [ ] `Control.cancel` ustawione w trakcie → powrót w ≤ 100 ms z `cancelled == true` i kandydatami z ukończonych przebiegów; przekroczony `time_cap` → `timed_out == true`.
- [ ] `Job`: `poll` nie blokuje, postęp monotoniczny w [0, 1], `result` przed końcem zwraca błąd, panika w funkcji celu daje stan `failed` z opisem.

**Verify:** `cargo test -p algopalette-core optim` → wszystkie przechodzą

**Reguły:**
- Fala 1: `R = max(N + 4, ceil(1.5 · N))` niezależnych przebiegów; przebieg `r` używa `Rng::new(seed, r)`; pula startów `S = clamp(budget / 8, 8, 128)` losowań z `sample`, przebieg 0 dokłada `current`; najlepszy punkt puli → lokalna minimalizacja z pozostałym budżetem; wcześniejsze zakończenie przy zbieżności.
- Wybór: sortowanie (feasible, total, run); zachłannie bierz kandydata, którego `distance` do każdego wybranego ≥ `min_diversity`.
- Fale 2–3 (gdy wybranych < N): `ceil(1.5 · brakujących)` przebiegów z `repulsion` względem wybranych na początku fali; numeracja przebiegów ciągła między falami. Po fali 3: dopełnienie najlepszymi pozostałymi z `diverse = false`.
- Wynik nie może zależeć od kolejności zakończenia wątków: przebiegi fali zbierane wg numeru; brak współdzielonego stanu między przebiegami fali.
- Postęp = `evals_done / evals_planned`; `evals_planned` rośnie przy dodaniu fali (postęp nie cofa się: licz względem maksimum).
- Testy używają syntetycznych `Objective` zdefiniowanych w module testowym (nie zależą od Tasku 14).

**Steps:**
- [ ] `lbfgsb` z testami; `select`; `driver` (fale, determinizm); `job` (wątek + stan atomowy).
- [ ] Testy przerwania i limitu czasu na funkcji celu ze sztucznym opóźnieniem.
- [ ] fmt/clippy; handoff; commit `feat(engine): optymalizator, sterownik równoległy, zadanie z postępem`.

```json:metadata
{"files": ["crates/core/src/optim/", "crates/core/src/lib.rs", "crates/core/Cargo.toml"], "verifyCommand": "cargo test -p algopalette-core optim", "acceptanceCriteria": ["minimalizacja z granicami i zmienną okresową zbieżna", "budżet respektowany", "N różnorodnych albo dopełnienie z diverse=false po ≤ 3 falach", "wynik bitowo identyczny dla 1 i 8 wątków", "kolejność: feasible, total, run", "cancel ≤ 100 ms, time_cap → timed_out", "Job: poll nieblokujący, failed przy panice"], "modelTier": "frontier", "model": "opus"}
```

### Task 7: Źródło, jednostki i logika ustawień na modelu v2

**Goal:** Przenieść `sources.py`, `units.py` i `globals_logic.py` na zasady per kolor.

**Files:**
- Modify: `src/algopalette/sources.py`, `src/algopalette/units.py`, `src/algopalette/globals_logic.py`
- Modify: `tests/test_sources.py`
- Create: `tests/test_units.py`

**Acceptance Criteria:**
- [ ] `apply_character`: tło, tekst i każdy akcent dostają zasady z profilu (liczby jak w `sources.py@4b71aeb`: jasność ± 0.03, nasycenie względne ± 0.05, kontrast p10 akcentów, kontrast tekstu ze źródła, tło L ± 0.03 i C ± 0.01, odcień tła jako łuk h ± 20 miękki, gdy C tła ≥ 0.01); akcenty `use_scheme = True` bez zasady odcienia; układ `custom` z odcieniami profilu powtórzonymi do 14; `preset = None`; kłódki zdjęte.
- [ ] `apply_transfer`: każdy akcent dostaje łuk `h ± 8` twardy (gdy C ≥ 0.02), nasycenie względne ± 0.08, kontrast z nowym tłem = źródłowy ± tolerancja, jasność wyłączoną, `use_scheme = False`; liczba akcentów = liczba akcentów źródła.
- [ ] `apply_complete`, `parse_colors`, `extract_profile`, `cluster_hues`: zachowanie bez zmian.
- [ ] `units.rescale_delta_e` i `rescale_contrast_metric` przeliczają progi w zasadach każdego koloru i w zależnościach; zakazane przedziały i zasady L/C/H bez zmian.
- [ ] `globals_logic`: `change_metric(session, metric) -> Session` i `change_delta_e(session, method) -> Session` (ustawienie + przeliczenie progów); nic nie odwołuje się do nastrojów ani ról.

**Verify:** `uv run pytest -q tests/test_sources.py tests/test_units.py` → wszystkie przechodzą

**Steps:**
- [ ] Przenieś testy `test_sources.py` na nowy model (asercje na `slot.rules`), dopisz `test_units.py` (WCAG 4.5 ↔ APCA 60 wg tabeli w `units.py`; ΔE ok 0.08 → 2000 ≈ 12.5 wg `DE_SCALE`).
- [ ] Implementacja; ruff/ty; handoff; commit `refactor: źródło, jednostki i logika ustawień na modelu v2`.

```json:metadata
{"files": ["src/algopalette/sources.py", "src/algopalette/units.py", "src/algopalette/globals_logic.py", "tests/test_sources.py", "tests/test_units.py"], "verifyCommand": "uv run pytest -q tests/test_sources.py tests/test_units.py", "acceptanceCriteria": ["apply_character zapisuje zasady per kolor z liczbami jak w v1", "apply_transfer: łuk h±8, use_scheme False", "apply_complete i parsowanie bez zmian", "przeliczenia jednostek obejmują zasady kolorów i zależności", "change_metric / change_delta_e bez odwołań do nastrojów"], "modelTier": "standard"}
```

### Task 8: Presety — rdzeń i dziewięć dawnych

**Goal:** Zastąpić nastroje presetami zgodnymi z I6, z dziewięcioma dawnymi nastrojami o niezmienionych zasadach.

**Files:**
- Create: `src/algopalette/presets.py`, `src/algopalette/presets_builtin.py`, `tests/test_presets.py`
- Delete: `src/algopalette/moods.py`, `tests/test_moods.py`
- Modify: `src/algopalette/__main__.py` (start: `default_session()` ma już preset „neutralny”; wywołanie `migrate_user_moods()` przed pierwszym użyciem presetów)

**Acceptance Criteria:**
- [ ] Interfejs z I6. `presets_builtin.py` zawiera deklaracje (`PresetDef`: nazwa, kategoria, opis, polaryzacje, funkcja `(polaryzacja, metryka) -> PresetRules` z polami: zasady tła, tekstu, akcentu, nadpisania per numer akcentu, układ odcieni, rozrzut, opcjonalnie `cvd` i `contrast_metric`).
- [ ] Dla każdej z 36 sesji z `quality.json`: `apply_preset(sesja startowa o tej polaryzacji i metryce, nazwa)` daje zasady kolorów, `use_scheme`, układ odcieni i rozrzut równe wynikowi `migrate_v1` tej sesji.
- [ ] `apply_preset` nie zmienia wartości, kłódek, nazw, zależności, ustawień generowania, listy unikanych kolorów; ustawia `session.preset`.
- [ ] `is_modified` jest `False` zaraz po nałożeniu i `True` po zmianie dowolnej zasady, `use_scheme`, układu albo rozrzutu.
- [ ] `change_polarity(reapply=True)` nakłada bieżący preset dla nowej polaryzacji; `reapply=False` zmienia tylko `globals.polarity`.
- [ ] Preset użytkownika: zapis zasad wg pozycji + układ + rozrzut + polaryzacja + metryka do `config_dir()/presets.json` (zapis atomowy); nałożenie na paletę z większą liczbą akcentów powiela ostatni zapisany akcent; nazwa wbudowana odrzucana.
- [ ] `migrate_user_moods()` zamienia wpisy `moods.json` na presety (tło, tekst, jeden akcent z warunków roli; `use_scheme` wg reguły migracji), nie rusza starego pliku, drugi raz nic nie dopisuje.

**Verify:** `uv run pytest -q tests/test_presets.py` → wszystkie przechodzą

**Steps:**
- [ ] Testy (równość z migracją dla 36 sesji jest głównym testem); implementacja; ruff/ty; handoff; commit `feat: presety zamiast nastrojów (rdzeń + dziewięć dawnych)`.

```json:metadata
{"files": ["src/algopalette/presets.py", "src/algopalette/presets_builtin.py", "tests/test_presets.py", "src/algopalette/moods.py", "tests/test_moods.py", "src/algopalette/__main__.py"], "verifyCommand": "uv run pytest -q tests/test_presets.py", "acceptanceCriteria": ["interfejs I6, deklaratywne PresetDef", "9 dawnych presetów = migracja sesji wzorcowych (36 przypadków)", "apply_preset nie rusza wartości/kłódek/zależności/generowania", "is_modified", "change_polarity z reapply", "presety użytkownika w presets.json", "migrate_user_moods idempotentne"], "modelTier": "standard"}
```

### Task 9: Widżet `BandSlider`

**Goal:** Suwak zakresu z zakazanymi przedziałami, używany dla jasności, nasycenia i odcienia.

**Files:**
- Create: `src/algopalette/gui/band.py`, `tests/gui/test_band.py`
- Modify: `src/algopalette/gui/widgets.py` (tylko `Bar`: rysowanie zakazanych odcinków przez nową metodę `set_excluded(Exclusions)`)

**Acceptance Criteria:**
- [ ] Interfejs z I6. Pod paskiem lista pozycji „od–do” z polami liczbowymi i przyciskiem usunięcia oraz przycisk „+ zakaz”; każda zmiana emituje `changed(lo, hi, exclude)`.
- [ ] „+ zakaz” dodaje przedział o szerokości 10% zakresu osi w środku największej wolnej luki dozwolonego zakresu.
- [ ] Zakazy są widoczne na pasku (kreskowanie albo przygaszenie) także przy osi okrężnej z zawijaniem (zakaz 350–10).
- [ ] `center_fields=True` (oś okrężna): dodatkowe pola „środek” i „±”; wpisanie środka 30 i ± 20 daje `lo = 10, hi = 50`; środek 350 ± 20 daje `lo = 330, hi = 10`; zmiana `lo`/`hi` odświeża środek i szerokość.
- [ ] Pary z `od ≥ do` na osi liniowej są odrzucane (pole oznaczone jako błędne, sygnał nie wychodzi); zakazy zwracane posortowane wg `od`.
- [ ] Wszystko osiągalne z klawiatury (Tab do pól, Enter zatwierdza, Delete na pozycji usuwa zakaz).

**Verify:** `QT_QPA_PLATFORM=offscreen uv run pytest -q tests/gui/test_band.py` → wszystkie przechodzą

**Steps:**
- [ ] Testy pytest-qt (bez `MainWindow`); implementacja z użyciem istniejących `NumEdit`, `Bar`, `RangeSlider`; kolory przez `theme.colors()`/`theme.mark_*` (żadnego `palette(...)` w arkuszach).
- [ ] ruff/ty; handoff; commit `feat(gui): suwak zakresu z zakazanymi przedziałami`.

```json:metadata
{"files": ["src/algopalette/gui/band.py", "tests/gui/test_band.py", "src/algopalette/gui/widgets.py"], "verifyCommand": "QT_QPA_PLATFORM=offscreen uv run pytest -q tests/gui/test_band.py", "acceptanceCriteria": ["interfejs I6, sygnał changed(lo, hi, exclude)", "+ zakaz w największej wolnej luce", "zakazy widoczne na pasku, także przez 0°", "pola środek/± zsynchronizowane z od/do", "walidacja par, sortowanie", "obsługa z klawiatury"], "modelTier": "standard"}
```

### Task 10: Widżet `ListPicker`

**Goal:** Interaktywna lista odcieni albo kolorów z kołem do wybierania.

**Files:**
- Create: `src/algopalette/gui/picker.py`, `tests/gui/test_picker.py`

**Acceptance Criteria:**
- [ ] Interfejs z I6. Tryb `hue`: koło odcieni OKLCH (kolory liczone jak w `gui/analysis_tab.py`, stałe L = 0.75, C = 0.13); klik w koło dodaje odcień (zaokrąglony do 1°) na koniec listy i emituje `changed`.
- [ ] Lista pozycji: próbka + pole stopni; zmiana liczby, usunięcie (przycisk i Delete), przestawianie (przeciąganie oraz Alt+↑/↓); zaznaczona pozycja jest oznaczona na kole, przeciąganie znacznika zmienia jej wartość.
- [ ] Tryb `color`: jak wyżej plus suwaki jasności i nasycenia dla zaznaczonej pozycji oraz pole tekstowe przyjmujące hex i `oklch(...)` (`color.from_css`); elementy to `OKLCH`.
- [ ] `max_items` blokuje dodawanie ponad limit (przycisk i klik w koło nieaktywne, podpowiedź z powodem).
- [ ] `set_items` nie emituje `changed`; pusty wybierak pokazuje wskazówkę „kliknij koło, żeby dodać”.

**Verify:** `QT_QPA_PLATFORM=offscreen uv run pytest -q tests/gui/test_picker.py` → wszystkie przechodzą

**Steps:**
- [ ] Testy pytest-qt (klik w punkt koła o znanym kącie → oczekiwany odcień ± 1°); implementacja; ruff/ty; handoff; commit `feat(gui): wybierak listy odcieni i kolorów`.

```json:metadata
{"files": ["src/algopalette/gui/picker.py", "tests/gui/test_picker.py"], "verifyCommand": "QT_QPA_PLATFORM=offscreen uv run pytest -q tests/gui/test_picker.py", "acceptanceCriteria": ["tryb hue: klik w koło dodaje odcień", "lista: edycja, usuwanie, przestawianie, znacznik na kole", "tryb color: L/C + hex/oklch()", "max_items", "set_items bez sygnału, wskazówka przy pustej liście"], "modelTier": "standard"}
```

### Task 11: Widżet `ColorStrip`

**Goal:** Pasek kolorów z wielokrotnym zaznaczeniem, zastępujący zakładki ról.

**Files:**
- Create: `src/algopalette/gui/colorstrip.py`, `tests/gui/test_colorstrip.py`

**Acceptance Criteria:**
- [ ] Interfejs z I6. Pasek: przycisk „cała paleta”, przycisk na każdy wpis (próbka + etykieta), przycisk „wszystkie akcenty”.
- [ ] Klik = zaznacz jeden; Ctrl+klik = dołóż/odejmij (ostatniego zaznaczonego nie da się odjąć); Shift+klik = zakres od ostatnio klikniętego; „cała paleta” czyści zaznaczenie kolorów i odwrotnie.
- [ ] Klawiatura: ←/→ przenosi fokus, spacja zaznacza jeden, Ctrl+spacja dokłada/odejmuje, Ctrl+A zaznacza wszystkie akcenty.
- [ ] `set_entries` zachowuje zaznaczenie id, które nadal istnieją; gdy żadne nie zostało, zaznacza „całą paletę”; aktualizuje próbki bez przebudowy przy tym samym zestawie id.
- [ ] `selection_changed` wychodzi tylko przy faktycznej zmianie zaznaczenia; `Selection.ids` w kolejności wpisów.
- [ ] Przy 16 wpisach pasek mieści się przez przewijanie poziome albo zawijanie, bez obcinania etykiet.

**Verify:** `QT_QPA_PLATFORM=offscreen uv run pytest -q tests/gui/test_colorstrip.py` → wszystkie przechodzą

**Steps:**
- [ ] Testy pytest-qt; implementacja; ruff/ty; handoff; commit `feat(gui): pasek kolorów z wielokrotnym zaznaczeniem`.

```json:metadata
{"files": ["src/algopalette/gui/colorstrip.py", "tests/gui/test_colorstrip.py"], "verifyCommand": "QT_QPA_PLATFORM=offscreen uv run pytest -q tests/gui/test_colorstrip.py", "acceptanceCriteria": ["przyciski: cała paleta, kolory, wszystkie akcenty", "klik / Ctrl+klik / Shift+klik", "obsługa z klawiatury", "set_entries zachowuje zaznaczenie", "sygnał tylko przy zmianie, ids w kolejności", "16 wpisów bez obcinania"], "modelTier": "standard"}
```

### Task 12: Logika edycji zbiorczej i opisy formularzy

**Goal:** Czysta logika odczytu i zapisu zasad dla wielu kolorów naraz oraz etykiety, domyślne wartości i zakresy suwaków nowych zasad.

**Files:**
- Create: `src/algopalette/rules_edit.py`, `tests/test_rules_edit.py`
- Modify: `src/algopalette/forms.py` (`LABELS`, `DESCRIPTIONS`, `DEFAULTS`, `DISPLAY_ORDER`, `default_for`, `fields_for`, `range_spec` dla pól I2; usunięcie `hue_range`/`hue_target`)

**Acceptance Criteria:**
- [ ] Interfejs z I6.
- [ ] `applicable_fields`: tło + akcent → `("lightness", "chroma", "hue")`; tekst + akcent → te trzy + `contrast_bg`; same akcenty → wszystkie siedem.
- [ ] `merged_rule`: identyczne zasady → `same`; różna wartość, włączenie, twardość, waga albo obecność tylko u części → `mixed` z `per_slot` w kolejności `ids`; brak u wszystkich → `absent`.
- [ ] `set_rule` nadaje wszystkim tę samą zasadę (w tym ten sam `ChromaBand.mode`); `None` usuwa; `update_rule(..., hard=False)` zmienia tylko istniejące i nie tworzy zasady tam, gdzie jej nie było.
- [ ] Każda funkcja zapisująca zwraca nową `Session` jednym przebiegiem (jeden krok cofania po stronie GUI) i rzuca `ValueError` dla pola, które nie dotyczy któregoś z `ids`.
- [ ] `forms`: etykiety „jasność L”, „nasycenie C”, „odcień”, „kontrast z tłem”, „odległość od innych akcentów”, „odróżnialność (daltonizm)”, „skrajny kontrast”; `default_for("hue", …) == HueArc(0.0, 60.0)`; domyślne progi w jednostkach bieżącej metryki i metody ΔE (jak `default_for@4b71aeb`).

**Verify:** `uv run pytest -q tests/test_rules_edit.py` → wszystkie przechodzą

**Steps:**
- [ ] Testy (w tym Review Focus 3: nasycenie `abs` u jednego i `rel` u drugiego → `mixed`; po `set_rule` oba mają tę samą zasadę); implementacja; ruff/ty; handoff; commit `feat: logika edycji zbiorczej zasad, opisy formularzy v2`.

```json:metadata
{"files": ["src/algopalette/rules_edit.py", "tests/test_rules_edit.py", "src/algopalette/forms.py"], "verifyCommand": "uv run pytest -q tests/test_rules_edit.py", "acceptanceCriteria": ["interfejs I6", "applicable_fields = część wspólna ról", "merged_rule: same / mixed / absent", "set_rule i update_rule", "ValueError dla pola niedotyczącego koloru", "etykiety i domyślne wartości nowych zasad"], "modelTier": "standard"}
```

### Task 13: Pomoc — wzorzec terminu, pojęcia, rysunek

**Goal:** Wprowadzić wzorzec „co to jest / przykład z liczbami / kiedy użyć” i napisać według niego tematy pojęć, zaczynając od nasycenia względnego i bezwzględnego.

**Files:**
- Modify: `src/algopalette/gui/help_content/topic.py` (`Topic.term: bool = False`; nowe grupy „Zasady” i „Zasady koloru” dopisane obok starych — stare grupy i stare tematy usuwa dopiero Task 18)
- Modify: `src/algopalette/gui/help_content/concepts.py`
- Create: `src/algopalette/gui/help_figures.py`
- Modify: `src/algopalette/gui/help.py` (rejestracja rysunków w panelu pomocy)
- Create: `tests/gui/test_help_terms.py`

**Acceptance Criteria:**
- [ ] Tematy z `term=True`: `concept.chroma_modes`, `concept.hard_soft` (z wagą), `concept.delta_e` (każda z pięciu metod), `concept.contrast` (WCAG i APCA), `concept.gamut` (z metodami dopasowania), `concept.cvd` (metody i nasilenie), `concept.exclusion`, `concept.hue_arc`. `concept.sources` zostaje nietknięty (usuwa go Task 18 razem z odnośnikami).
- [ ] Każdy temat `term=True` ma w treści trzy części z nagłówkami pogrubionymi „Co to jest”, „Przykład”, „Kiedy użyć”; „Przykład” zawiera co najmniej jedną liczbę; test sprawdza to dla wszystkich tematów `term=True` w całym `TOPICS`.
- [ ] `concept.chroma_modes`: liczby w przykładzie (największe C przy L = 0.75 dla odcieni 30°, 110°, 150°, 260°, 330°; co znaczy zakres 0.10–0.15 bezwzględnie i 50–70% względnie dla każdego z nich) są liczone z `algopalette.color.max_chroma` przy imporcie; test przelicza je niezależnie i znajduje w treści.
- [ ] Rysunek `chroma_modes` (dwa rzędy po 12 próbek w odcieniach co 30°: stałe C bezwzględne 0.10 oraz stałe C względne 60%, z podpisaną wartością C pod każdą próbką) renderuje się w panelu pomocy w obu motywach; test: obraz niepusty, dwa rzędy różnią się pikselami.
- [ ] `short` tematu `concept.chroma_modes` (podpowiedź) tłumaczy różnicę w dwóch zdaniach bez słów „ułamek” i „osiągalne”.

**Verify:** `QT_QPA_PLATFORM=offscreen uv run pytest -q tests/gui/test_help_terms.py` → wszystkie przechodzą

**Reguły:** proza po polsku, pełne zdania; teoria koloru krótko, nacisk na to, co program z daną wartością robi (decyzja użytkownika ze speca pomocy 2026-11-15). Żadnych definicji przez synonim. Test nie importuje `MainWindow` (okno nie startuje między Taskiem 3 a 15); zadanie najlepiej wykonać od razu, równolegle z łańcuchem 1 → 3 → 4, i wtedy dodatkowo uruchomić `tests/gui/test_help.py`.

**Steps:**
- [ ] Test wzorca i test liczb; `Topic.term`; treść; rysunek (`QImage` rysowany `QPainter`, kolory tekstu z `theme.colors()`); ruff/ty; handoff; commit `feat(help): wzorzec terminu, pojęcia z przykładami, rysunek nasycenia`.

```json:metadata
{"files": ["src/algopalette/gui/help_content/topic.py", "src/algopalette/gui/help_content/concepts.py", "src/algopalette/gui/help_figures.py", "src/algopalette/gui/help.py", "tests/gui/test_help_terms.py"], "verifyCommand": "QT_QPA_PLATFORM=offscreen uv run pytest -q tests/gui/test_help_terms.py", "acceptanceCriteria": ["osiem tematów pojęć z term=True; concept.sources nietknięty do Tasku 18", "trzy części w każdym temacie term=True, liczba w Przykładzie", "liczby nasycenia liczone z max_chroma i sprawdzone testem", "rysunek chroma_modes w obu motywach", "podpowiedź bez żargonu"], "modelTier": "standard"}
```

### Task 14: Zasady, funkcja celu, gradienty, ocena

**Goal:** Skompilować sesję v2 do `Problem` (funkcja celu z dokładnym gradientem) i dać ocenę naruszeń zgodną ze starym silnikiem.

**Files:**
- Create: `crates/core/src/rules/{mod,compile,terms,problem,eval,hues}.rs`
- Modify: `crates/core/src/lib.rs`, `crates/py/src/lib.rs` (`evaluate`, `hue_targets`; `implemented += "evaluate"`)
- Create: `tests/test_engine_parity.py`

**Acceptance Criteria:**
- [ ] Zgodność: dla każdego z 300 przypadków `eval.json` (v1 → `migrate_v1` → `engine.current_violations`/`engine.objective`): ten sam zbiór kluczy (po odwzorowaniu `:hue_range` i `:hue_target` na `:hue`), te same flagi `hard`, wielkości i funkcja celu w tolerancji względnej 1e-6 (1e-4 bezwzględnie dla termów z ΔE `2000`/`itp`/`cam16`).
- [ ] Zakaz: jasność 0.72 przy zakazie 0.70–0.74 → naruszenie `exclude`, wielkość 0.02, twarde, klucz `slot:<id>:lightness:exclude:0`; odcień 5° przy zakazie 350–10 → 5°; wartość poza zakazem → brak; zasada wyłączona → brak.
- [ ] `use_scheme`: akcent z własnym łukiem 0–270 i `use_scheme = True` ma oba termy (`hue`, `scheme`); `use_scheme = False` → brak termu `scheme`; cele układu równe `hues.scheme_targets@4b71aeb` przy `jitter = 0`.
- [ ] `Problem`: gradient `value_grad` zgodny z różnicą centralną (błąd względny ≤ 1e-4) w 50 losowych punktach dla sesji zawierającej każdy rodzaj termu, w tym zakazy, `extreme`, `spread`, `mix`, CVD, każdą metodę ΔE i `repulsion`.
- [ ] `decode` zwraca kolory wolne w gamucie (`in_gamut`) dla dowolnego `x` w granicach; twarde zakresy jasności, nasycenia względnego i odcienia są granicami zmiennych (jak `_space@4b71aeb`); `sample` nie trafia w zakazane przedziały.
- [ ] Sesja z zakazami pokrywającymi cały dozwolony zakres jasności: `evaluate` zwraca twarde naruszenie, `value_grad` skończony, `score().feasible == false` (Review Focus 1).
- [ ] Brak NaN w wartości i gradiencie dla kolorów z C = 0, L = 0, L = 1 i dwóch identycznych kolorów (Review Focus 2).

**Verify:** `cargo test -p algopalette-core rules && uv run pytest -q tests/test_engine_parity.py` → wszystkie przechodzą

**Reguły (port `constraints.py@4b71aeb` + spec §7.2):**
- Termy, skale (`L 0.01`, `C 0.01`/`0.02` względne, `H 1°`, WCAG `0.1`, APCA `1`, ΔE ok/hyab `0.01`, inne `1`), margines twardych `0.5 × skala` tylko w `value_grad`, wygaszanie odcienia `(C / 0.02)²` obcięte do 1 z podłogami twardego minimum nasycenia, progi par = max z obu kolorów (twarde, gdy którykolwiek; waga = max), pary tylko między akcentami, pomijanie termów samych kłódek i zerwanych zależności, `extreme`, `spread`, `avoid` (zawsze twardy, ΔE ok), `gamut` dla kolorów bez kłódki.
- Funkcja celu: Σ waga · (naruszenie / skala)², twarde × `hard_weight`.
- Zmienne koloru wolnego: (L, u, H), C = u · `max_chroma(L, H)`. Pochodne: liczby dualne z lokalnymi zmiennymi termu (3 na kolor: `Dual<3>` dla termów jednego koloru, `Dual<6>` dla par, `Dual<9>` dla mieszanki); `extreme` i `spread` przez wybór aktywnego elementu (podgradient).
- Start losowy: jak `_space@4b71aeb` (odcień w pobliżu celu układu ± tolerancja, gdy `use_scheme` i brak własnej zasady odcienia), z odrzucaniem zakazanych przedziałów.
- Jitter układu: `Rng::new(seed, 7919)`, kolejno `range(−jitter, jitter)` na akcent.
- `evaluate`: `achieved`, `req`, `meta` wg tabeli I3.

**Steps:**
- [ ] Test zgodności (czerwony), `compile` + termy grupami: zakresy, pary, zależności, globalne; po każdej grupie odsetek zgodnych przypadków rośnie.
- [ ] Zakazy, `use_scheme`, `hues`; `Problem` + testy gradientu i przypadków z Review Focus.
- [ ] fmt/clippy/ruff/ty; handoff; commit `feat(engine): kompilacja zasad, funkcja celu z gradientem, ocena naruszeń`.

```json:metadata
{"files": ["crates/core/src/rules/", "crates/core/src/lib.rs", "crates/py/src/lib.rs", "tests/test_engine_parity.py"], "verifyCommand": "cargo test -p algopalette-core rules && uv run pytest -q tests/test_engine_parity.py", "acceptanceCriteria": ["zgodność oceny z 300 przypadkami wzorcowymi", "semantyka zakazanych przedziałów", "use_scheme i cele układu", "gradient Problem zgodny z różnicą centralną ≤ 1e-4", "decode w gamucie, granice z twardych zakresów, sample poza zakazami", "zasada niespełnialna: twarde naruszenie, brak zawieszenia", "brak NaN w przypadkach zdegenerowanych"], "modelTier": "frontier", "model": "opus"}
```

### Task 15: Zakładka „Zasady”

**Goal:** Zbudować zakładkę „Zasady” (preset, liczba kolorów, pasek kolorów, wiersze zasad z edycją zbiorczą, zależności, „cała paleta”) i przepiąć na nią okno.

**Files:**
- Create: `src/algopalette/gui/rules_tab.py`, `src/algopalette/gui/rule_rows.py`, `src/algopalette/gui/help_content/rules.py`, `tests/gui/test_rules_tab.py`
- Delete: `src/algopalette/gui/globals_tab.py`, `src/algopalette/gui/conditions.py` (funkcja `combo` przechodzi do `gui/widgets.py`)
- Modify: `src/algopalette/gui/relations.py`, `src/algopalette/gui/app.py`, `src/algopalette/gui/widgets.py` (`combo`, usunięcie `source_badge`), `src/algopalette/gui/help_content/__init__.py`

**Acceptance Criteria:**
- [ ] Kolejność zakładek: Zasady, Propozycje, Paleta, Analiza, Źródło (F2–F6 w tej kolejności); nigdzie w GUI nie ma tekstów „Globalne”, „dziedzicz”, „nastrój” ani plakietek źródeł.
- [ ] Sesja startowa: pasek ma „cała paleta” + 10 kolorów; „−” przy 3 kolorach i „+” przy 16 są nieaktywne; „−”/„+” to jeden krok cofania.
- [ ] Zaznaczenie akcentu 1 i 2, zmiana dolnej granicy jasności → oba kolory mają nową zasadę; jedno Ctrl+Z cofa oba.
- [ ] Zasady różne w zaznaczonych kolorach → wiersz „różne” z wartością każdego koloru, „ustaw dla zaznaczonych” (ujednolica wg pierwszego zaznaczonego) i „usuń u wszystkich”.
- [ ] Tło + akcent zaznaczone → brak wierszy „kontrast z tłem”, „odległość…”, „odróżnialność…”, „skrajny kontrast”; edytor zależności widoczny tylko przy jednym kolorze.
- [ ] Wiersz zasady: włączona, twarda, waga, wartość, „✕ usuń”; brak zasady → „+ dodaj” (wartość `forms.default_for`). Jasność, nasycenie i odcień używają `BandSlider` (odcień z `center_fields=True`); dodanie zakazu trafia do sesji.
- [ ] Akcenty: wiersz „układ odcieni: ☑ stosuj → cel X° ± Y°” (`engine.hue_targets`; „—”, gdy silnik nie zwraca celów) z odnośnikiem do sekcji układu w „całej palecie”.
- [ ] „cała paleta”: metryki, układ odcieni (własna lista przez `ListPicker(mode="hue")`), rozrzut jasności, daltonizm, unikane kolory (`ListPicker(mode="color")` + odległość), generowanie (liczba propozycji, ziarno z losowaniem, budżet, limit czasu, różnorodność, waga twardych, wątki).
- [ ] Preset: wyszukiwarka + kategoria + lista, „Zastosuj”, „(zmieniony)” wg `presets.is_modified`, zapis i usunięcie własnego; zmiana polaryzacji przy presecie niezmienionym nakłada go ponownie, przy zmienionym albo braku presetu pyta (zastąp / tylko oznaczenie / anuluj).
- [ ] `MainWindow.show_rules(ids)` i `MainWindow.generate()` wg I6; przycisk „Generuj propozycje” woła `generate()`; kliknięcie naruszenia w panelu woła `show_rules(v.slot_ids)`; komunikaty z `io.load_session_ex` trafiają do `notify`.
- [ ] Każdy nowy element ma klucz pomocy `rules.*` z tytułem i krótką podpowiedzią w `help_content/rules.py`; `help.uncovered(zakładka) == []`.
- [ ] Zrzuty zakładki (jeden kolor, dwa kolory z „różne”, „cała paleta”) w obu motywach zapisane w scratchpadzie i obejrzane przez kontrolera.

**Verify:** `QT_QPA_PLATFORM=offscreen uv run pytest -q tests/gui/test_rules_tab.py` → wszystkie przechodzą

**Reguły:**
- Zapisy wyłącznie przez `rules_edit` i `win.set_session(..., coalesce=...)`; klucz scalania zawiera pole i posortowane id (seria ruchów suwaka = jeden krok cofania).
- Przebudowa wierszy tylko przy zmianie zaznaczenia albo struktury (dodanie/usunięcie zasady, zmiana trybu); zmiana wartości aktualizuje widżety w miejscu (fokus nie ucieka).
- Pułapki Qt z `HANDOFF.md` §0a/§0b obowiązują (odkładanie przebudowy `QTimer.singleShot(0, …)`, `deleteLater`, kolory przez `theme`).

**Steps:**
- [ ] Testy pytest-qt wg kryteriów; `rule_rows.py` (wiersz zasady: stany `same`/`mixed`/`absent`); `rules_tab.py`; przepięcie `app.py`; klucze pomocy.
- [ ] Zrzuty; ruff/ty; handoff; commit `feat(gui): zakładka „Zasady” z zakładką na kolor i edycją zbiorczą`.

```json:metadata
{"files": ["src/algopalette/gui/rules_tab.py", "src/algopalette/gui/rule_rows.py", "src/algopalette/gui/help_content/rules.py", "tests/gui/test_rules_tab.py", "src/algopalette/gui/globals_tab.py", "src/algopalette/gui/conditions.py", "src/algopalette/gui/relations.py", "src/algopalette/gui/app.py", "src/algopalette/gui/widgets.py", "src/algopalette/gui/help_content/__init__.py"], "verifyCommand": "QT_QPA_PLATFORM=offscreen uv run pytest -q tests/gui/test_rules_tab.py", "acceptanceCriteria": ["kolejność zakładek, brak tekstów Globalne/dziedzicz/nastrój i plakietek", "pasek kolorów, liczba kolorów 3–16", "edycja zbiorcza = jeden krok cofania", "wiersz różne z ujednoliceniem i usunięciem", "zastosowalność wierszy, zależności przy jednym kolorze", "wiersze zasad z BandSlider i zakazami", "przełącznik układu odcieni z celem", "cała paleta z ListPicker", "preset: szukanie, zmieniony, polaryzacja", "show_rules, generate, naruszenia, komunikaty migracji", "klucze pomocy rules.*, uncovered == []", "zrzuty obejrzane"], "modelTier": "frontier", "model": "opus"}
```

### Task 16: Spięcie silnika — generowanie, benchmark, progi

**Goal:** Połączyć `Problem` ze sterownikiem w `_engine.start`, dać program `algopalette-bench` i udowodnić cele jakości oraz wydajności.

**Files:**
- Modify: `crates/py/src/lib.rs` (`start`, `Job`; `implemented += "generate"`), `crates/cli/src/main.rs`, `src/algopalette/engine.py` (składanie `Proposal`), `src/algopalette/model.py` i `src/algopalette/migrate.py` (tylko stałe: domyślny budżet, przelicznik)
- Create: `tests/test_engine_generate.py`, `tests/fixtures/bench/{w1,w2,w3}.json`

**Acceptance Criteria:**
- [ ] `engine.generate(default_session())` zwraca 6 propozycji `ok`; kolory wolne w gamucie; kolory pod kłódką i spoza `slot_ids` bez zmian; `Proposal.slot_ids` = kolory wolne.
- [ ] Determinizm: `threads = 1` i `threads = 0` dają identyczne `values` i `score`; dwa uruchomienia też.
- [ ] Jakość (36 sesji `quality.json` po migracji, budżet domyślny): liczba `ok` ≥ `ok_count`, najlepszy wynik ≤ `best_score × 1.05 + 1e-9`.
- [ ] Propozycja zbyt podobna do wybranych ma miękkie naruszenie `diversity`; po limicie czasu wszystkie mają `timed_out`; `cancel()` kończy zadanie w ≤ 100 ms.
- [ ] Sesja z zasadą niespełnialną (zakazy pokrywające cały dozwolony zakres jasności akcentu): generowanie kończy się w budżecie, zwraca 6 propozycji, żadna nie jest `ok`, każda ma twarde naruszenie `exclude` (Review Focus 1).
- [ ] `algopalette-bench <sesja.json> [--threads N] [--repeat K]` wypisuje czas, liczbę propozycji bez twardych naruszeń i z naruszeniem „różnorodność”.
- [ ] Zmierzone na tej maszynie i zapisane w handoffie: W1 ≤ 0,15 s; W2 ≤ 2 s i ≥ 120/128 bez twardych; W3 ≤ 6 s; W4 `engine.current_violations` (16 kolorów, komplet zasad) ≤ 1 ms. **Cel niedotrzymany → liczby i profil do handoffu i do użytkownika; próg zostaje.**
- [ ] Test `slow`: W2 ≤ 6 s.

**Verify:** `uv run pytest -q tests/test_engine_generate.py -m "not slow"` oraz w tle `uv run pytest -q tests/test_engine_generate.py -m slow && cargo run --release -p algopalette-bench -- tests/fixtures/bench/w2.json` → testy przechodzą, czas W2 ≤ 2 s

**Reguły:**
- `w1.json` = sesja startowa; `w2.json` = sesja startowa + preset „chłodny mglisty”, 128 propozycji; `w3.json` = 16 kolorów, protan + deutan, ΔE 2000, 128 propozycji. Budżet domyślny.
- Domyślny budżet i przelicznik `max_evals → budget` dobierz pomiarem tak, żeby test jakości przechodził z zapasem; zmienione stałe wpisz do handoffu (Task 3 przyjął 3000 i ÷ 10).
- `timed_out` propozycji = `timed_out` generacji; `seed` = ziarno sesji.

**Steps:**
- [ ] `start`/`Job` w PyO3 (wątki Rusta, GIL zwolniony; `poll` bez blokowania); składanie `Proposal` w nakładce.
- [ ] Testy determinizmu i jakości; strojenie budżetu; `algopalette-bench`; pomiary W1–W4 w tle.
- [ ] fmt/clippy/ruff/ty; handoff z liczbami; commit `feat(engine): generowanie natywne, benchmark, progi jakości i wydajności`.
- [ ] Koniec etapu silnika → PRZEGLĄD 1 (po potwierdzeniu zasad przeglądu u użytkownika).

```json:metadata
{"files": ["crates/py/src/lib.rs", "crates/cli/src/main.rs", "src/algopalette/engine.py", "src/algopalette/model.py", "src/algopalette/migrate.py", "tests/test_engine_generate.py", "tests/fixtures/bench/"], "verifyCommand": "uv run pytest -q tests/test_engine_generate.py -m 'not slow'", "acceptanceCriteria": ["6 propozycji ok dla sesji startowej, gamut, kłódki nietknięte", "determinizm niezależny od liczby wątków", "jakość ≥ wzorca dla 36 sesji", "diversity, timed_out, cancel ≤ 100 ms", "algopalette-bench", "W1–W4 zmierzone i zapisane; niedotrzymany cel zgłoszony, próg bez zmian", "test slow: W2 ≤ 6 s"], "modelTier": "frontier", "model": "opus"}
```

### Task 17: Pozostałe zakładki na nowym modelu

**Goal:** Dostosować Paletę, Propozycje, Analizę i Źródło do modelu v2 i zadania silnika.

**Files:**
- Modify: `src/algopalette/gui/palette_tab.py`, `src/algopalette/gui/proposals_tab.py`, `src/algopalette/gui/analysis_tab.py`, `src/algopalette/gui/source_tab.py`
- Modify: `tests/gui/test_gui_app.py`, `tests/gui/test_review_fixes.py`, `tests/gui/test_gui_widgets.py`

**Acceptance Criteria:**
- [ ] Paleta: edytor koloru ma nazwę, kłódkę, wartość i odnośnik „Zasady tego koloru →” (`win.show_rules([id])`); brak edytora warunków i zależności; lista, dodawanie, usuwanie, przestawianie, F7 jak dotąd.
- [ ] Propozycje: generowanie przez `engine.start` i `QTimer` (~30 Hz) odpytujący `poll()`; żadnego `threading`; pasek postępu, przerwanie, błąd silnika pokazany w zakładce; „generuj tylko zaznaczony kolor” działa.
- [ ] Przejęcie propozycji po usunięciu koloru albo zmianie liczby kolorów nie rzuca wyjątku: przejmowane są tylko kolory nadal istniejące (Review Focus 4).
- [ ] Zamknięcie okna w trakcie generowania anuluje zadanie; `closeEvent` wraca w ≤ 1 s; autozapis wykonany (Review Focus 4).
- [ ] Analiza: łuk zasady odcienia zaznaczonego koloru z wyciętymi zakazami; cele układu z `engine.hue_targets`; macierze i wykresy bez zmian.
- [ ] Źródło: trzy tryby wołają `sources.apply_*` na nowym modelu; po „charakterze” i „przeniesieniu” zasady są widoczne w zakładce „Zasady”.
- [ ] Przeniesione testy tych zakładek przechodzą; testy starych edytorów warunków w Palecie usunięte.

**Verify:** `QT_QPA_PLATFORM=offscreen uv run pytest -q tests/gui/test_gui_app.py tests/gui/test_review_fixes.py tests/gui/test_gui_widgets.py` → wszystkie przechodzą

**Steps:**
- [ ] Testy (testy wymagające prawdziwego generowania z `skipif` wg I3); implementacja; ruff/ty; handoff; commit `feat(gui): Paleta, Propozycje, Analiza i Źródło na modelu v2`.

```json:metadata
{"files": ["src/algopalette/gui/palette_tab.py", "src/algopalette/gui/proposals_tab.py", "src/algopalette/gui/analysis_tab.py", "src/algopalette/gui/source_tab.py", "tests/gui/test_gui_app.py", "tests/gui/test_review_fixes.py", "tests/gui/test_gui_widgets.py"], "verifyCommand": "QT_QPA_PLATFORM=offscreen uv run pytest -q tests/gui/test_gui_app.py tests/gui/test_review_fixes.py tests/gui/test_gui_widgets.py", "acceptanceCriteria": ["Paleta bez edytora zasad, z odnośnikiem do Zasad", "Propozycje na zadaniu silnika i QTimer, bez threading", "przejęcie po zmianie struktury palety bez wyjątku", "zamknięcie okna anuluje generowanie ≤ 1 s", "Analiza: łuk z zakazami, cele z silnika", "Źródło na nowym modelu", "przeniesione testy zielone"], "modelTier": "standard"}
```

### Task 18: Treść pomocy zakładki „Zasady”

**Goal:** Napisać pełną pomoc nowej zakładki i usunąć tematy starego modelu.

**Files:**
- Modify: `src/algopalette/gui/help_content/rules.py`, `src/algopalette/gui/help_content/{window,palette,analysis,source,proposals,general}.py` (odnośniki i opisy dotknięte zmianą)
- Delete: `src/algopalette/gui/help_content/globals.py`, `src/algopalette/gui/help_content/conditions.py`
- Modify: `tests/gui/test_help_coverage.py`, `tests/gui/test_help_globals.py` → `tests/gui/test_help_rules.py`, `tests/gui/test_help_palette.py`, `tests/gui/test_help_window.py`, `tests/gui/test_help_analysis.py`, `tests/gui/test_help_proposals_source.py`

**Acceptance Criteria:**
- [ ] Każdy klucz `rules.*` ma pełną treść zgodną z kodem (edycja zbiorcza i „różne”, zakazy, odcień w dwóch zapisach, przełącznik układu, wybierak, presety i „(zmieniony)”, zmiana polaryzacji, liczba kolorów, każda pozycja generowania łącznie z wątkami i nowym znaczeniem budżetu).
- [ ] `term=True` z trzema częściami mają: rodzaje układu odcieni, tolerancja, jitter, rozrzut jasności, budżet, ziarno, różnorodność, waga twardych, każdy rodzaj zależności, skrajny kontrast.
- [ ] Brak tematów i odnośników `concept.sources`, `cond.reset`, `cond.badge`, `globals.*`, `cond.hue_range`, `cond.hue_target`; żaden odnośnik `help:` nie prowadzi do nieistniejącego klucza.
- [ ] Test pokrycia całego okna: `uncovered(win) == []` dla każdej zakładki, zaznaczeń (cała paleta, tło, tekst, akcent, dwa akcenty), obu widoków wartości; każdy temat osiągalny.
- [ ] Opisy presetów wbudowanych i opcji list (układy, ΔE, dopasowanie, CVD) występują w treści (test jak dotychczasowy `test_help_globals`).

**Verify:** `QT_QPA_PLATFORM=offscreen uv run pytest -q tests/gui/test_help_rules.py tests/gui/test_help_coverage.py tests/gui/test_help_terms.py tests/gui/test_help_palette.py tests/gui/test_help_window.py tests/gui/test_help_analysis.py tests/gui/test_help_proposals_source.py` → wszystkie przechodzą

**Reguły:** treść pisana z kodem przed oczami (Task 15, 17), nie ze speca; wzorzec terminu z Tasku 13; pomoc opisuje działanie programu, teorię krótko.

**Steps:**
- [ ] Treść; przeniesienie testów pomocy; ruff/ty; handoff; commit `feat(help): pomoc zakładki „Zasady”, usunięte tematy starego modelu`.

```json:metadata
{"files": ["src/algopalette/gui/help_content/", "tests/gui/test_help_coverage.py", "tests/gui/test_help_globals.py", "tests/gui/test_help_rules.py", "tests/gui/test_help_palette.py", "tests/gui/test_help_window.py", "tests/gui/test_help_analysis.py", "tests/gui/test_help_proposals_source.py"], "verifyCommand": "QT_QPA_PLATFORM=offscreen uv run pytest -q tests/gui/test_help_rules.py tests/gui/test_help_coverage.py tests/gui/test_help_terms.py", "acceptanceCriteria": ["pełna treść każdego klucza rules.*", "terminy panelu wg wzorca", "brak tematów i odnośników starego modelu, brak martwych odnośników", "pokrycie całego okna i osiągalność tematów", "opisy presetów i opcji list w treści"], "modelTier": "standard"}
```

### Task 19: Presety do co najmniej 48

**Goal:** Dopisać presety z listy ze speca §8 i nastroić je na prawdziwym silniku.

**Files:**
- Modify: `src/algopalette/presets_builtin.py`, `tests/test_presets.py`
- Create: `tests/test_presets_quality.py`

**Acceptance Criteria:**
- [ ] ≥ 48 presetów wbudowanych w 11 kategoriach ze speca §8; każda kategoria ma ≥ 3 presety; dziewięć dawnych bez zmian (test z Tasku 8 nadal zielony).
- [ ] Żadne dwa presety nie dają identycznego zestawu (zasady + układ + rozrzut) dla tej samej polaryzacji i metryki.
- [ ] Test `slow`: każdy preset × każda obsługiwana polaryzacja × obie metryki, przy 10 i przy 7 kolorach, ustawienia domyślne → ≥ 5 z 6 propozycji `ok`.
- [ ] Presety z kategorii „Ograniczone” używają nadpisań per akcent albo własnej listy tak, żeby opis był prawdziwy (np. „szarości z akcentem”: nasycenie akcentów 2…N ≤ 0.02, akcent 1 nasycony); presety z kategorii „Dostępność” włączają odpowiednie typy CVD i progi odróżnialności, a „APCA do długiego czytania” ustawia metrykę APCA.
- [ ] Opis każdego presetu (jedno zdanie) mówi, co preset ustawia, nie tylko jak się nazywa.
- [ ] Paski próbek (pierwsza propozycja każdego presetu, ciemne i jasne tło) wyrenderowane do jednego obrazu w scratchpadzie i obejrzane przez kontrolera: nazwa pasuje do wyglądu.

**Verify:** `uv run pytest -q tests/test_presets.py` oraz w tle `uv run pytest -q tests/test_presets_quality.py -m slow` → wszystkie przechodzą

**Steps:**
- [ ] Deklaracje; test jakości w tle; strojenie liczb tych presetów, które nie dają 5/6; obraz z próbkami.
- [ ] ruff/ty; handoff; commit `feat: presety wbudowane (≥ 48) w kategoriach`.

```json:metadata
{"files": ["src/algopalette/presets_builtin.py", "tests/test_presets.py", "tests/test_presets_quality.py"], "verifyCommand": "uv run pytest -q tests/test_presets.py", "acceptanceCriteria": ["≥ 48 presetów w 11 kategoriach, ≥ 3 na kategorię, dziewięć dawnych bez zmian", "presety parami różne", "≥ 5/6 ok dla każdego presetu, polaryzacji, metryki, 10 i 7 kolorów", "Ograniczone i Dostępność zgodne z opisem", "opisy mówią, co preset ustawia", "próbki obejrzane"], "modelTier": "frontier", "model": "opus"}
```

### Task 20: Integracja i zamknięcie

**Goal:** Doprowadzić całość do zielonego stanu, uaktualnić dokumentację i sprawdzić instalację narzędzia.

**Files:**
- Modify: `README.md`, `HANDOFF.md`, `pyproject.toml` (opis, znaczniki pytest), dowolny plik z listy zadań 1–19 wymagający poprawki integracyjnej
- Create: `tests/gui/test_workflow.py`

**Acceptance Criteria:**
- [ ] Pełne `uv run pytest -q` (w tle) i `cargo test --workspace` zielone; `ruff check`, `ruff format --check`, `ty check`, `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings` bez uwag; liczby testów wpisane do handoffu.
- [ ] Test przepływu: start → Zasady: akcentom 1–3 zakaz odcienia 60–85 → „Generuj propozycje” → Propozycje: 6 wierszy, żaden akcent 1–3 nie ma odcienia w 60–85 → „przejmij całą” → Paleta pokazuje nowe kolory, panel naruszeń pusty.
- [ ] Wczytanie pliku v1 z `tests/fixtures` w GUI pokazuje zasady w „Zasadach” i ewentualne komunikaty migracji; zapis daje v2.
- [ ] Start z autozapisu w formacie v1 (`src/algopalette/__main__.py`, `gui/app.py`): sesja zmigrowana, obok zostaje kopia `last.v1.json`, komunikaty migracji pokazane po otwarciu okna; drugi start nie tworzy kopii ponownie.
- [ ] Brak pozostałości: `grep -rn "effective_conditions\|role_defaults\|mood_snapshot\|hue_range\|hue_target\|import threading\|scipy" src` nic nie zwraca.
- [ ] Instalacja narzędzia w scratchpadzie z czystego klonu gałęzi: `algopalette --help` działa, profil release.
- [ ] README: zakładka „Zasady”, presety, wymagania budowania (Rust), polecenie przebudowy po zmianie kodu Rust, benchmark. HANDOFF: stan, liczby W1–W4, pułapki, czego nie zweryfikowano, instrukcja reinstalacji launchera po scaleniu.

**Verify:** w tle `uv run pytest -q && cargo test --workspace` → 0 niepowodzeń; `grep -rn "effective_conditions\|role_defaults\|mood_snapshot\|hue_range\|hue_target\|import threading\|scipy" src` → brak wyników

**Steps:**
- [ ] Pełne testy w tle, naprawy integracyjne, test przepływu, dokumentacja.
- [ ] Handoff; commit `feat: integracja zakładki „Zasady” i silnika natywnego; README, handoff`.
- [ ] PRZEGLĄD 2 (całość), pętla napraw, potem `finishing-a-development-branch` (scalenie i reinstalacja launchera to decyzja użytkownika).

```json:metadata
{"files": ["README.md", "HANDOFF.md", "pyproject.toml", "tests/gui/test_workflow.py"], "verifyCommand": "uv run pytest -q && cargo test --workspace", "acceptanceCriteria": ["pełne testy i linty zielone, liczby w handoffie", "test przepływu Zasady → Propozycje → Paleta z zakazem odcienia", "plik v1 wczytany w GUI, zapis v2", "brak pozostałości starego modelu, threading i scipy", "instalacja narzędzia z czystego klonu w scratchpadzie", "README i HANDOFF aktualne"], "modelTier": "frontier", "model": "opus"}
```
