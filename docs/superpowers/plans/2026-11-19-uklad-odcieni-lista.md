# Układ odcieni jako lista — Implementation Plan

> **For agentic workers:** wykonanie INLINE przez agenta głównego (decyzja użytkownika: „bez subagentów i bez
> review”). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Układ odcieni = jedna jawna lista odcieni na kole (rodziny: akcent `i` → `hues[i mod k]`), a mono,
triada, tetrada itd. to jednorazowe generatory listy.

**Architecture:** `HueScheme` w modelu i w silniku Rust traci `kind/rotation/center/spread/custom`, dostaje
`hues`. Stare kształty (pliki v2, presety wbudowane i użytkownika) rozwija Python (`hue_layouts.legacy_targets`)
do listy dającej identyczne cele. Generatory to czyste funkcje w `hue_layouts.py`; GUI zawsze pokazuje
`ListPicker` z przyciskami generatorów, „obróć wszystkie” i licznikami ×N.

**Tech Stack:** Python 3.13 + PySide6, Rust (crates/core, PyO3/maturin), pytest/pytest-qt, cargo test.

**Spec:** `docs/superpowers/specs/2026-11-19-uklad-odcieni-lista-design.md`

## Global Constraints

- Semantyka celu: `targets[i] = hues[i % len(hues)]` (+ jitter jak dziś), pusta lista → brak celów. Bez obiegów.
- Rozwinięcie starego kształtu (`legacy_targets`): `custom` → `max(n, k)` pozycji (przy k ≥ n cała lista,
  przy k < n obiegi jak dziś do n); `equal/analogous/complementary/split/triad/tetrad` → n pozycji wg
  dzisiejszej formuły (`crates/core/src/rules/hues.rs:14-54`, bez jittera); `none` → `()`; n = 0 → `custom`
  cała, reszta `()`. Wyniki mod 360.
- Cele `engine.hue_targets` po zmianie == przed zmianą dla: każdego wbudowanego presetu × polaryzacji ×
  {7, 10 kolorów}, każdego `tests/fixtures/v2_contract/manual_*.json`, `default_session()`.
- Długość listy ≤ `MAX_ACCENTS` (14). Generatory zwracają wartości w [0, 360).
- Plik sesji: format zostaje `algopalette.v2`; nowy zapis `hue_scheme = {"hues": [...], "tol", "jitter", "hard",
  "weight"}`; dekoder rozpoznaje stary kształt po kluczu `kind`. Bez komunikatu migracji.
- Testy: `tests/` nie ma `__init__.py` — nazwy plików testów unikalne w `tests/` i `tests/gui/`.
- Po każdym zadaniu: `uv run pytest -q -m "not slow"` (w tle, ~45 s), `ruff check`, `ruff format --check`,
  `ty check` (0 błędów), przy zmianach Rust `cargo test --workspace`, `cargo clippy`, `cargo fmt --check`;
  potem handoff + commit (tylko własne pliki).
- Rozszerzenie Rust przebudowuje `uv sync`/`maturin develop` — po zmianie `crates/` przebuduj przed pytest.

**User decisions (already made):**
- „wariant A” — lista = rodziny odcieni (spec §1).
- Generatory jednorazowe, bez pamięci układu („tak, jest ok”).
- „jeśli chodzi o wdrażanie to bez subagentów i bez review.”
- Stare pliki i presety → te same cele.

## Review Focus

1. Sesja z akcentami `use_scheme=False` przemieszanymi z `True` — liczniki ×N liczą akcent po jego INDEKSIE
   (`i mod k`), także gdy `use_scheme=False` go pomija (wtedy nie liczy się do ×N) → test w Task 3.
2. Lista dłuższa niż liczba akcentów (preset 14 pozycji, 8 akcentów) — wiersze 9–14 ×0, wyszarzone; dodanie
   akcentu bierze pozycję 9 → test w Task 2 (`legacy_targets`) i Task 3 (liczniki).
3. Pusta lista + kłódka „hue” (`set_rules_lock`) — slot dostaje samą kłódkę, bez wyjątku → test w Task 2.
4. Generator na pustej liście (baza 25°) i „z bieżących kolorów” bez barwnych akcentów (komunikat, lista bez
   zmian) → testy w Task 1 i Task 3.
5. Stary plik v2 z `kind="none"` i niepustym `custom` → pusta lista → test w Task 2.

---

### Task 1: `hue_layouts.py` — generatory, `LegacyScheme`, `legacy_targets`, snapshot celów

**Goal:** Czyste funkcje układów i port starej formuły + zapisany snapshot dzisiejszych celów (przed zmianą modelu).

**Files:**
- Create: `src/algopalette/hue_layouts.py`
- Create: `tools/snapshot_hue_targets.py`, `tests/fixtures/hue_targets_snapshot.json`
- Test: `tests/test_hue_layouts.py`

**Acceptance Criteria:**
- [ ] Generatory od bazy 30° dają wartości ze spec §5; `rotate` działa mod 360.
- [ ] `legacy_targets` odtwarza wszystkie przypadki z `hues.rs` testu `targets_match_the_old_engine` + reguły
      długości z Global Constraints.
- [ ] `ordered_clusters` (Dracula) zwraca kolejność pierwszego wystąpienia.
- [ ] Snapshot JSON zawiera cele dla presetów × polaryzacji × {7, 10}, `manual_*.json`, `default_session()`.

**Verify:** `uv run pytest -q tests/test_hue_layouts.py` → all passed

**Steps:**

- [ ] **Step 1: Testy** (`tests/test_hue_layouts.py`):
  - `test_generators_from_30`: `mono(30)==(30,)`, `complementary(30)==(30,210)`, `split(30)==(30,180,240)`,
    `triad(30)==(30,150,270)`, `square(30)==(30,120,210,300)`, `rectangle(30)==(30,90,210,270)`,
    `analogous(30, n=3, spread=60)==(0,30,60)`, `analogous(30, n=1, spread=60)==(30,)`,
    `equal(30, n=4)==(30,120,210,300)`; wszystko `pytest.approx`, wartości w [0, 360).
  - `test_rotate`: `rotate((350, 10), 20) == (10, 30)`.
  - `test_legacy_matches_old_engine`: przypadki z `crates/core/src/rules/hues.rs` (`equal 10` n=8, `equal 350`
    n=3, analogous center 200 spread 90 n=5, analogous n=1, complementary 20 n=5, split 0 n=7, triad 45 n=8,
    tetrad 300 n=14, custom [15,140,280] n=8 → `[15,140,280,55,180,320,95,220]`, custom [] → `()`, none → `()`,
    triad n=0 → `()`).
  - `test_legacy_custom_longer_than_n_kept_whole`: custom 14 pozycji, n=8 → 14 pozycji, identyczne.
  - `test_ordered_clusters_first_occurrence`: akcenty Dracula (hexy `#ff5555 #50fa7b #f1fa8c #bd93f9 #ff79c6
    #8be9fd #ffb86c`) → pierwsze trzy ≈ `(24.4, 148.0, 112.8)` (±1°); szare akcenty (C < 0.03) pominięte;
    same szare → `()`.
- [ ] **Step 2: Implementacja** `hue_layouts.py`:
  - `LegacyScheme` (frozen dataclass: `kind: Literal[equal, analogous, complementary, split, triad, tetrad,
    custom, none]`, `rotation=0.0`, `center=0.0`, `spread=90.0`, `custom: tuple[float, ...]=()`, `tol=15.0`,
    `jitter=0.0`, `hard=False`, `weight=1.0`).
  - `legacy_targets(s: LegacyScheme, n: int) -> tuple[float, ...]` (reguły z Global Constraints).
  - `mono, complementary, split, triad, square, rectangle (base: float)`, `analogous(base, n, spread)`,
    `equal(base, n)`, `rotate(hues, delta)` → `tuple[float, ...]`.
  - `ordered_clusters(colors: Sequence[OKLCH], merge_deg=25.0, chroma_min=0.03) -> tuple[float, ...]` —
    aglomeracja jak `sources.cluster_hues`, wynik posortowany wg najmniejszego indeksu członka skupiska.
  - `GENERATORS`: lista `(etykieta GUI, klucz)` w kolejności spec §4.3; `BASE_EMPTY = 25.0`.
- [ ] **Step 3: Snapshot** `tools/snapshot_hue_targets.py` (uruchamiany NA OBECNYM kodzie): dla każdego
  wbudowanego presetu, polaryzacji z `polarities`, n_colors ∈ {7, 10}: sesja z `default_session()` przycięta/
  dociągnięta do n kolorów, `apply_preset`, zapis listy `engine.hue_targets` w kolejności akcentów; plus każdy
  `manual_*.json` (`io.load_session`) i `default_session()`. Klucze czytelne (`"preset:<nazwa>:<pol>:<n>"`,
  `"file:<nazwa>"`, `"default"`). Uruchom, zapisz JSON.
- [ ] **Step 4:** pytest, ruff, ty; handoff; commit.

```json:metadata
{"files": ["src/algopalette/hue_layouts.py", "tools/snapshot_hue_targets.py", "tests/fixtures/hue_targets_snapshot.json", "tests/test_hue_layouts.py"], "verifyCommand": "uv run pytest -q tests/test_hue_layouts.py", "acceptanceCriteria": ["generatory wg spec §5", "legacy_targets = stary silnik", "ordered_clusters kolejność wystąpienia", "snapshot zapisany"], "modelTier": "standard"}
```

### Task 2: Model + silnik + zgodność wsteczna (lista zamiast rodzaju)

**Goal:** `HueScheme(hues, tol, jitter, hard, weight)` w Pythonie i Rust, semantyka rodzin, stare kształty
rozwijane do identycznych celów; cała reszta kodu (poza nowym UI generatorów) działa na liście.

**Files:**
- Modify: `crates/core/src/schema.rs:384-396` (+ usunąć `HueSchemeKind`), `crates/core/src/rules/hues.rs`,
  `crates/core/src/rules/mod.rs` (testy z `kind`), `crates/core/tests/schema_contract.rs`
- Modify: `src/algopalette/model.py` (`HueScheme`, `default_session`), `io.py` (`_enc/_dec_hue_scheme`,
  `_HUE_KINDS`, dekoder sesji przekazuje n akcentów), `presets.py` (`_Resolved.hue_scheme` jako lista,
  `_decode_entry`, `_resolve` rozwija `LegacyScheme`), `presets_builtin.py` (`HueScheme(...)` → `LegacyScheme(...)`,
  `PresetRules.hue_scheme: LegacyScheme`), `sources.py` (`character_settings` → `ordered_clusters`;
  `apply_transfer` → `HueScheme()`), `rules_edit.py:160`, `themes/apply.py` (`HueScheme()`),
  `gui/rule_rows.py:385`, `gui/rules_tab.py` (minimalnie: zawsze `ListPicker`, bez combo i suwaków rodzaju —
  pełne UI w Task 3), `gui/analysis_tab.py` (jeśli używa usuniętych pól)
- Regenerate: `tests/fixtures/v2_contract/eval_*.json` (test je odtwarza), `tests/fixtures/bench/w*.json`,
  `v2_contract/manual_*.json` (zapis nowym koderem, format pliku zachowany); `v1_reference/*` NIETKNIĘTE.
- Test: `tests/test_hue_list_compat.py` + aktualizacja istniejących testów z `kind=`/`.custom`
  (`test_model, test_io, test_presets, test_rules_lock, test_sources, tests/gui/test_rules_tab, test_gui_app,
  test_help_rules, test_gui_regressions_2026_11_18, test_themes_dialog, test_themes_apply`).

**Acceptance Criteria:**
- [ ] Rust: `scheme_targets([15,140,280], 8)` → `[15,140,280,15,140,280,15,140]`; pusta → `[]`; jitter jak dziś.
- [ ] `engine.hue_targets` == snapshot z Task 1 dla wszystkich kluczy.
- [ ] Stary plik v2: `kind="none"` + niepuste `custom` → `hues == ()`; zapis nie zawiera `kind`.
- [ ] Preset użytkownika ze starym kształtem w `presets.json` nakłada się z celami jak dawniej; nowy zapis = lista.
- [ ] `set_rules_lock(…, "hue")` przy pustej liście → sama kłódka.
- [ ] Cały `pytest -m "not slow"`, `cargo test --workspace` zielone.

**Verify:** `uv run pytest -q tests/test_hue_list_compat.py` → passed; `cargo test --workspace` → ok

**Steps:**

- [ ] **Step 1: Testy** `tests/test_hue_list_compat.py`:
  - `test_targets_match_snapshot` (param po kluczach snapshotu; odtwarza sesję jak skrypt z Task 1).
  - `test_old_v2_file_none_kind_gives_empty_list` (dict sesji z `"kind": "none", "custom": [10, 20]` →
    `load` → `hues == ()`), `test_old_v2_triad_8_accents` → `hues == (45,165,285,85,205,325,125,245)`,
    `test_save_has_no_kind`.
  - `test_user_preset_old_shape` (w `presets.json` w tmp config — jak istniejące testy presetów — wpis
    z `"kind": "equal", "rotation": 10` → nałożony na 8 akcentów → `hues == (10,55,…,325)`; `is_modified`
    False); `test_user_preset_saved_as_list`.
  - `test_hue_lock_with_empty_list` (pusta lista, `set_rules_lock(s, [akcent], "hue", {})` → `rules_lock ==
    "hue"`, zasady bez zmian).
  - `test_character_hues_in_accent_order` (Dracula przez `extract_profile` + `character_settings` →
    `hues[:3] ≈ (24.4, 148.0, 112.8)`).
- [ ] **Step 2: Rust** — `HueScheme { hues: Vec<f64>, tol, jitter, hard, weight }`; `scheme_targets` = rodziny;
  testy Rust: przepisać `targets_match_the_old_engine` na `families` (`[15,140,280]` n=8 jw., `[]`, n=0),
  jitter bez zmian; `mod.rs`/`schema_contract.rs` dokumenty testowe z `"hues"`.
- [ ] **Step 3: Python** — zmiany z listy plików. `io._dec_hue_scheme(v, path, n_accents: int) -> HueScheme`:
  dict z `kind` → `LegacyScheme` → `HueScheme(legacy_targets(...), tol, jitter, hard, weight)`; walidacja jak
  dziś (liczby, nieujemne), lista ≤ `MAX_ACCENTS` dla nowego kształtu. Presety: `_decode_entry` rozwija stary
  kształt przy `n_slots - 2`; wbudowane: `LegacyScheme` → `legacy_targets(…, n_slots - 2)`.
  `default_session()`: `HueScheme(hues=equal(0.0, 8))`.
- [ ] **Step 4: Fixture'y** — przebuduj rozszerzenie, pozwól `test_contract_files_are_what_python_encodes`
  odtworzyć `eval_*`; `manual_*`/`bench` przepisz skryptem (load → save, wcięcie jak w pliku).
- [ ] **Step 5:** pełny pytest (bez slow), cargo test/clippy/fmt, ruff, ty; handoff; commit.

```json:metadata
{"files": ["crates/core/src/schema.rs", "crates/core/src/rules/hues.rs", "src/algopalette/model.py", "src/algopalette/io.py", "src/algopalette/presets.py", "src/algopalette/presets_builtin.py", "src/algopalette/sources.py", "src/algopalette/rules_edit.py", "tests/test_hue_list_compat.py"], "verifyCommand": "uv run pytest -q tests/test_hue_list_compat.py && cargo test --workspace", "acceptanceCriteria": ["rodziny w Rust", "cele == snapshot", "stare pliki/presety zgodne", "pełny zestaw zielony"], "modelTier": "frontier"}
```

### Task 3: GUI — generatory, „obróć wszystkie”, liczniki ×N

**Goal:** Ramka „Układ odcieni” z kołem + listą zawsze, rząd przycisków generatorów, obrót całej listy,
licznik akcentów przy każdym punkcie.

**Files:**
- Modify: `src/algopalette/gui/rules_tab.py` (`_hues_box`, `SCHEME_FIELDS` usunąć), `src/algopalette/gui/picker.py`
  (`ListPicker`: `set_counts(counts: Sequence[int] | None)` — tekst `×N` w wierszu, ×0 wyszarzony; zaznaczenie
  zachowane po `set_items`), `src/algopalette/forms.py` (`SCHEMES` → usunąć/zastąpić `GENERATORS`)
- Test: `tests/gui/test_hue_list_ui.py`

**Acceptance Criteria:**
- [ ] Ramka zawsze ma `ListPicker`; brak combo „rodzaj”.
- [ ] Zaznaczony punkt 40° + „triada” → `hues == (40,160,280)`, jeden krok cofania (Ctrl+Z przywraca).
- [ ] Pusta lista + „mono” → `(25,)`.
- [ ] „Analogiczny”/„równo po kole” pytają o N (i S); domyślnie N=3,S=60 / N=liczba akcentów.
- [ ] „Z bieżących kolorów” bez barwnych akcentów → komunikat (`win.notify`), lista bez zmian.
- [ ] „Obróć wszystkie” o +30° → każdy odcień +30 mod 360, jeden krok cofania na gest.
- [ ] 8 akcentów (wszystkie `use_scheme`), 3 punkty → liczniki `(3,3,2)`; akcent 2 z `use_scheme=False` →
      `(3,2,2)`; lista 14, 8 akcentów → wiersze 9–14 ×0.
- [ ] `rule_rows` przy pustej liście: „→ układ odcieni jest pusty — brak celów”.

**Verify:** `uv run pytest -q tests/gui/test_hue_list_ui.py` → passed

**Steps:**

- [ ] **Step 1: Testy** wg Acceptance Criteria (fixture `win` jak w `tests/gui/test_rules_tab.py`).
- [ ] **Step 2: Implementacja.** Liczniki: `family_counts(n_hues, slots) -> tuple[int, ...]` w `hue_layouts.py`
  (akcent `i` liczy się do `i % k`, jeśli `use_scheme`). Pytanie o N/S: `QDialog` z `QSpinBox`-ami
  (N 1–14, S 0–360) albo `QInputDialog` — wybór implementującego; w testach podmienialne (atrybut na zakładce).
  „Obróć wszystkie”: `ValueSlider` względny (offset od stanu z początku gestu, `coalesce="g:hs-rotate"`, po
  zwolnieniu 0) albo pole + przycisk — wybór implementującego.
- [ ] **Step 3:** pełny pytest (bez slow), ruff, ty; zrzut ramki (offscreen) obejrzany; handoff; commit.

```json:metadata
{"files": ["src/algopalette/gui/rules_tab.py", "src/algopalette/gui/picker.py", "src/algopalette/forms.py", "src/algopalette/hue_layouts.py", "tests/gui/test_hue_list_ui.py"], "verifyCommand": "uv run pytest -q tests/gui/test_hue_list_ui.py", "acceptanceCriteria": ["koło zawsze", "generatory jednorazowe z cofaniem", "obrót listy", "liczniki ×N"], "modelTier": "standard"}
```

### Task 4: Pomoc, README, pełna weryfikacja

**Goal:** Teksty pomocy i README zgodne z nowym modelem; zielone wszystkie zestawy (także `slow`).

**Files:**
- Modify: `src/algopalette/gui/help_content/rules.py` (`rules.hues*`: usunąć `kind/rotation/center/spread`,
  dodać tematy przycisków generatorów, obrotu, liczników; `rules.py:167` nowa semantyka),
  `help_content/analysis.py:46` (jeśli treść o rodzaju), `help_content/themes_web.py` (wzmianka „układ
  wyłączony” → „pusta lista”), `README.md`, `HANDOFF.md`

**Acceptance Criteria:**
- [ ] `test_help_coverage` i testy pomocy zielone; żaden tekst pomocy nie wspomina „rodzaju” układu.
- [ ] `pytest -m slow` zielony (jakość presetów bez zmian), `cargo test --workspace` zielony, lintery czyste.

**Verify:** `uv run pytest -q -m slow` → passed; `grep -rn "rules.hues.kind" src` → brak

**Steps:**

- [ ] **Step 1:** teksty; **Step 2:** pełna weryfikacja (`slow` w tle); **Step 3:** handoff (stan, liczby testów,
  czego nie sprawdzono) i commit.

```json:metadata
{"files": ["src/algopalette/gui/help_content/rules.py", "README.md", "HANDOFF.md"], "verifyCommand": "uv run pytest -q -m slow", "acceptanceCriteria": ["pomoc zgodna", "slow zielony", "cargo zielony"], "modelTier": "mechanical"}
```
