# HANDOFF — AlgoPalette

Dla agenta, który przejmie pracę bez tej rozmowy. Sekcja 0 = stan na teraz. Niżej decyzje, pułapki, mapa, dziennik.

## 0c. JEDEN PANEL ZASAD + SILNIK W RUST (2026-11-15) — STAN: WYKONANIE W TOKU (plan 20 zadań; postęp w dzienniku §5 i w `.tasks.json`)

- **Gdzie jesteśmy:** spec `docs/superpowers/specs/2026-11-15-zasady-silnik-design.md` zaakceptowany słowami
  „wszystko sie zgadza”. Plan: `docs/superpowers/plans/2026-11-15-zasady-silnik.md` + `.tasks.json`. Gałąź
  `feat/zasady-silnik`, worktree `/home/qrikk/algopalette/.worktrees/zasady-silnik`.
- **Tryb wykonania — DECYZJA UŻYTKOWNIKA (2026-11-15, WIĄŻĄCA, nie otwieraj ponownie):** „Do implementacji silnika
  oddeleguj specjalnego Fable'a 5.2 high. Cala reszte robisz ty, a review wykonuje opus xhigh.” Czyli: silnik w
  Ruście robi JEDEN subagent (Agent `model: "fable"`, `effort: "high"`), wszystko inne kontroler sam, inline
  (skill `executing-plans`), bez Sonnetów. To nadpisuje punkt „Modele wykonawców” z Global Constraints planu.
- **Podział Tasku 4 (decyzja kontrolera):** 4a = część Rust (workspace Cargo, `crates/*`, backend maturin w
  `pyproject.toml`, `.gitignore`) — agent silnikowy, od razu, równolegle z łańcuchem 1 → 3; 4b = nakładka
  `engine.py`, `forms.violation_text`, `tests/test_engine_api.py`, pliki `tests/fixtures/v2_contract/` (z
  `migrate_v1`), usunięcie starego silnika i `scipy`, instalacja narzędzia w scratchpadzie — kontroler, po Tasku 3
  i scaleniu gałęzi agenta. Zakres agenta silnikowego: 4a, 5, 6 (faza A), potem 14, 16 (faza B, po scaleniu
  Tasków 1, 3, 4b do jego gałęzi). Tor agenta opisuje §0d.
- **Dziennik trwały wykonania (poza gitem):** `.superpowers/sdd/2026-11-15-zasady-silnik/progress.md` w tym
  worktree (rulingi, linie „Task N: complete”); briefy zadań obok. Ginie przy `git clean -fdx` — wtedy `git log`.
- **Gdzie to leży (uwaga dla sesji startującej w katalogu głównym):** spec, plan i ten wpis istnieją TYLKO na gałęzi
  `feat/zasady-silnik` (lokalnej, niewypchniętej), commity `2141daa` (spec) i `069cf2a` (plan) + ten. `HANDOFF.md`
  na `main` kończy się na §0b i o tej pracy nie wie. Natywne zadania #1–#20 żyły w sesji planującej; trwały zapis
  to `docs/superpowers/plans/2026-11-15-zasady-silnik.md.tasks.json` (wszystkie `pending`).
- **Kolejność i równoległość (z planu):** łańcuch kontraktów 1 → 3 → 4 (kontroler); od razu równolegle 2, 9, 10,
  11, 13; po 4 równolegle 5, 6, 7, 8, 12; po 5 → 14; po 7–12 → 15; po 6 i 14 → 16; po 15 → 17, 18; po 8 i 16 →
  19; na końcu 20. Interfejsy dzielone I1–I6 w planie są wiążące (schemat v2, model, `_engine`, nakładka
  `engine.py`, rdzeń Rusta, widżety/presety) — zmiana interfejsu = zmiana planu i powiadomienie pozostałych torów.
- **Przegląd:** dwa przeglądy częściowe, reviewer Opus xhigh (Agent `model: "opus"`, `effort: "xhigh"`): po
  silniku (po Tasku 16; zakres: Taski 4–6, 14, 16) i po całości (po Tasku 20); pętla napraw z `~/.claude/CLAUDE.md`
  (krytyczny → napraw cały raport → zawężony re-review; bez krytycznych → konsultacja z użytkownikiem). Słowa
  użytkownika „review wykonuje opus xhigh” przyjęte jako potwierdzenie wariantu „a” (wcześniej było to założenie).
  Reguła z §2 (jeden przegląd, Opus high, bez re-review) dotyczyła pierwszego planu.
- **Znany stan przejściowy podczas wykonania:** po Tasku 3 testy modułów nieprzeniesionych na model v2 są
  czerwone, a GUI na tej gałęzi nie startuje do końca Tasku 15. Każde zadanie uruchamia tylko testy ze swojego
  pola Verify; pełny zestaw zielony dopiero w Tasku 20. Launcher użytkownika czyta `main`, więc go to nie dotyka.
- **Jedna kopia repo (pułapka, która kosztowała pół sesji):** do 2026-11-15 `/home/qrikk/algopalette` stało na
  starym TUI (e7e5abb), a wersja z GUI żyła w `/home/qrikk/Pobrane/.gitclones/algopalette` i stamtąd czytał
  launcher — zrzuty użytkownika nie zgadzały się z kodem w katalogu sesji. Decyzja użytkownika: „ta z GUI jest
  wlasciwa, scal to w jedno”. Zrobione: `/home/qrikk/algopalette` fast-forward do 4b71aeb, launcher
  przeinstalowany `uv tool install --editable . --force` (sprawdzone: `algopalette.__file__` →
  `/home/qrikk/algopalette/src/...`). Klon w `Pobrane/.gitclones` nie ma nic unikalnego (czysty, `main` i `gui` na
  4b71aeb = `origin/main`), ale **NIE został skasowany** — użytkownik dwa razy nie odpowiedział na pytanie o
  skasowanie; nie kasuj bez jego „tak”. Jeśli zrzut nie pasuje do kodu: najpierw sprawdź, skąd czyta launcher.
- **Katalog główny ma zostać na `main`** przez całą pracę — launcher jest instalacją edytowalną z niego
  („binarka. zawsze.”). Pracuj w worktree. `.worktrees/` jest w `.git/info/exclude` (lokalnie, nie w repo).
- **Decyzje użytkownika z tej sesji (WIĄŻĄCE — nie otwieraj ponownie):**
  - Zakres panelu: „mi nie chodzi w ogole o warstwe pracy z kolorami, ktore juz mamy. ja mam ciagle na mysli
    workflow sprzed generacji jakiejkolwiek palety” → przebudowa dotyczy ustawiania zasad PRZED generowaniem;
    zakładka Paleta (wartości, kłódki, HSL/OKLCH, przejmowanie propozycji) zostaje, traci tylko edytor warunków
    i zależności. Nie tłumacz mu scenariuszy językiem „masz gotowe kolory i chcesz je zmienić” — tak sformułowane
    pytanie o edycję zbiorczą nie zostało zrozumiane („nie rozumiem pytania? opisz mi scenariusz”).
  - Edycja zbiorcza: „wybieram A” = zaznaczanie kilku zakładek kolorów naraz, zmiana trafia do zaznaczonych.
    Odrzucone: zakładka „wspólne dla akcentów” (to dziedziczenie) i samo „skopiuj do…”.
  - Kontrwarunki: „chodzi o podstawy - odcienie, jasnosc i nasycenie, np w przypadkach, gdy akceptowalny jest
    bardzo szeroki zakres barw, zalozmy 0-270, z wyjatkiem 60-85 i 140-155” → zakazane przedziały H, L, C.
  - Pomoc: „w 'kryminale' chodzilo o to w jaki sposob [nie] jest wytlumaczone pojecie C wzglednego i
    bezwzglednego”; „nazewnictwo typu dziedzicz/usun. Przeciez to jest jedno i to samo”.
  - Silnik: „wariant silnika 1” = Rust jako biblioteka w procesie GUI (PyO3 + rayon). Argument „Python pod
    spodem to C” użytkownik z góry odrzucił (doświadczenie z fontset-ui) — nie proponuj optymalizacji numpy.
  - TUI: „usuwamy” (razem z `textual`, `tests/tui`, `--tui`).
- **Decyzje agenta w specu (użytkownik ich jeszcze nie widział — może je odwrócić przy akceptacji):** nazwa
  zakładki „Zasady” i pierwsze miejsce; zakazane przedziały zawsze twarde; przełącznik `use_scheme` per akcent
  (cel układu odcieni może działać razem z własną zasadą odcienia); nowy akcent kopiuje zasady ostatniego;
  wybierak także dla listy unikanych kolorów (oznaczony „do skreślenia”); ≥ 48 presetów z listą nazw; teksty
  naruszeń składa Python, Rust zwraca liczby; budżet = oceny z gradientem na przebieg; cele wydajności W1–W4.
- **Pomiar bazowy starego silnika (2026-11-15, 10 kolorów, budżet 30 000, 4 propozycje, launcherowy Python
  3.13):** „neutralny” 0,55 s; „neon” 0,45 s (wczesne wyjście); „chłodny mglisty” **7,35 s = 1,84 s/propozycję**
  → 128 propozycji ≥ 4 min. Profil (2 propozycje, 3,73 s): `fast.max_chroma` 1,31 s, `objective_batch` 2,0 s
  łącznie z kontekstem, reszta narzut numpy. Skrypt był w scratchpadzie sesji (nie w repo); odtworzenie:
  `apply_mood(default_session(), nazwa)` + `replace(optimizer, n_proposals=4, max_evals=30000)` → `generate`.
- **Narzędzia na maszynie:** cargo/rustc 1.99, gcc 16.2, clang 23.1, cmake 4.4; brak `maturin` (dociągnie uv),
  16 wątków. Launcherowy Python to 3.13.
- **NIE zrobione / NIE zweryfikowane:** spec nieprzeczytany przez użytkownika; plan; czy `uv tool install
  --editable` działa z backendem maturin (ryzyko §12 speca — sprawdzić w K0, zanim cokolwiek na tym stanie);
  testów w tej sesji nie uruchamiano (stan z 0b: fala napraw GUI też nigdy nie była uruchomiona testami).

## 0d. TOR SILNIKA (Rust) — pisze WYŁĄCZNIE agent silnikowy; kontroler tej sekcji nie edytuje

**Stan na 2026-11-16.** Gałąź `feat/silnik-rust`, worktree `/home/qrikk/algopalette/.worktrees/silnik-rust`
(odgałęziona od `feat/zasady-silnik` @ `bc85502`). Faza A = Task 4a → 5 → 6, osobny commit na każde.
Zrobione: **4a** (`50e56d4` `feat: przestrzeń Cargo, moduł _engine (kontrakty)`), **5** (commit
`feat(engine): matematyka koloru w Ruście z pochodnymi`). W toku: 6.
Faza B (Task 14, 16) dopiero po scaleniu przez kontrolera modelu v2/migracji/nakładki do tej gałęzi.
Nic z tej gałęzi nie jest jeszcze scalone do `feat/zasady-silnik`. Raport fazy A dla kontrolera:
`.worktrees/zasady-silnik/.superpowers/sdd/2026-11-15-zasady-silnik/engine-phaseA-report.md`.

**Podział Tasku 4 (wiążący).** 4a (ten tor): `Cargo.toml`, `crates/`, backend maturin w `pyproject.toml`,
`.gitignore`, ręczne pliki kontraktu. 4b (kontroler, NIE ruszać stąd): `src/algopalette/engine.py`, `forms.py`,
`tests/test_engine_api.py`, usunięcie starego silnika i `scipy`/`textual`, 40 plików kontraktu z `eval.json`,
instalacja narzędzia w scratchpadzie. W `pyproject.toml` ten tor zmienił TYLKO `[build-system]`, `[tool.maturin]`,
`[tool.uv]`.

**Mapa (4a).**
- `Cargo.toml` — workspace (`crates/core`, `crates/py`, `crates/cli`), edycja 2024, `[workspace.dependencies]`,
  profil release: `opt-level = 3`, `lto = "thin"`, `codegen-units = 1`, `panic` domyślne (unwind — panika ma być
  wyjątkiem Pythona / stanem `failed`, nie przerwaniem procesu). `rustfmt.toml`: `max_width = 100`,
  `use_small_heuristics = "Max"`.
- `crates/core/src/schema.rs` — I1. Wyliczenia `schema.rs:48–200` (`DeltaE::Ciede2000` ↔ `"2000"`; `RelMetric` =
  metryki kontrastu + metody ΔE, `as_contrast`/`as_delta_e` `:182`/`:191`). `enum_from_name` `:204` (nazwa z dokumentu → wyliczenie, np. `"2000"`). `required` `:214`
  (pole wymagane, ale może być `null` — bez tego serde uznaje brak `Option` za `None`). `pairs` `:224` (pary
  zakazów; patrz pułapka 2). Struktury `:244–436`. `parse` `:444` (serde_path_to_error → ścieżka; błąd składni
  → ścieżka `$`), `validate` `:566`.
- `crates/core/src/rng.rs` — ZAMROŻONY: `splitmix64` `:22`, `Rng::new` `:36` (ziarno → 1 krok SplitMix64 → xor
  `stream · 0xD6E8FEB86659FD93` → 4 kroki SplitMix64 = stan xoshiro256++), `next_u64` `:51`, `uniform` `:65`
  (górne 53 bity), `range` `:70` (półotwarty). Testy `frozen_*` mają wartości policzone niezależną implementacją
  w Pythonie + wektor wzorcowy xoshiro256++ dla stanu [1,2,3,4].
- `crates/core/src/objective.rs` — `FEASIBLE_EPS` `:10`, `Score` `:14`, `trait Objective` `:25` (dokładnie I5).
- `crates/core/src/violation.rs` — `ViolationKind` `:12` (14 rodzajów z tabeli I3), `Violation` `:53`
  (`req`/`meta` = `serde_json::Map`), funkcje kluczy `key_*` `:72–110` (formaty kluczy z tabeli I3 zamrożone
  testem `keys_match_i3_table`).
- `crates/core/tests/schema_contract.rs` — czyta WSZYSTKIE `tests/fixtures/v2_contract/*.json` (pliki kontrolera
  dojdą bez zmiany testu; próg „≥ 12 plików”) + 16 testów negatywnych psujących `manual_exclusions.json`.
- `crates/py/src/lib.rs` — moduł `algopalette._engine` (`#[pymodule(name = "_engine")]` na końcu pliku),
  `IMPLEMENTED` `:15` (`["schema", "color"]`). Zaślepki: `evaluate` `:44`, `hue_targets` `:54`, `Job` (od razu
  `done`), `start` `:93`. Kolor: `named` `:104` (nazwa → wyliczenie, `ValueError("<argument>: unknown value …")`),
  `max_chroma` `:111`, `delta_e` `:117`, `contrast` `:124`, `simulate_cvd` `:131` (wejście/wyjście OKLCH), dodatki
  ponad I3: `oklch_to_linear_srgb` `:142`, `linear_srgb_to_oklch` `:148`, `in_gamut` `:154`.
  `src/algopalette/_engine.pyi` — typy I3 + dodatków dla `ty` (bez tego `from algopalette import _engine` to
  błąd `unresolved-import`).
- `crates/cli/src/main.rs` — `algopalette-bench --version` (reszta w Tasku 16).
- `tests/fixtures/v2_contract/manual_*.json` — 12 ręcznych sesji v2 (generator jednorazowy, nie w repo): przykład
  I1, zakazy w 3 kanałach (odcień przez 0°, zakaz pokrywający cały zakres), pełne koło 0–360 zapisane liczbami
  całkowitymi, 16 kolorów z ziarnem > 2³², wszystkie zasady `null` + `lightness_spread: null`, 16 zależności
  (każdy rodzaj/metryka/`op`, zerwana), `avoid_colors` + układ `custom` + 3 typy CVD, po jednym pliku na każdy
  pozostały `hue_scheme.kind` / `fit_method` / `delta_e`.

**Mapa (5: kolor).**
- `crates/core/src/scalar.rs` — `trait Scalar` `:16` (I5 + dodatki z domyślną implementacją: `scale`, `offset`,
  `maxf`, `minf`, `spow`, `square`, `cube` — działania ze stałą `f64` bez budowania `Dual` ze stałej), `impl
  Scalar for f64` `:79`, `Dual<N>` `:140` (`constant`, `var(v, i)`, `chain`), arytmetyka `:182–226`, `impl Scalar
  for Dual<N>` `:228`. Porównania `Dual` patrzą tylko na wartość.
- `crates/core/src/color/mod.rs` — re-eksporty (wyliczenia `ContrastMetric`, `DeltaE`, `CvdKind`, `CvdMethod`
  pochodzą ze `schema`); `testutil` `:27` (tylko testy): `random_lch` `:33`, `grad_error` `:59`,
  `check_gradients` `:77`.
- `color/convert.rs` — macierze `:9–40` (z coloraide; `LMS_TO_LRGB`/`LRGB_TO_LMS` to iloczyny policzone przez
  numpy w `fast.py`), `mat3` `:43`, `dot3` `:49`, `oklch_to_oklab` `:55` (h w STOPNIACH), `oklab_to_oklch` `:62`,
  `oklab_to_lms` `:76`, `oklab_to_linear_srgb` `:82`, `linear_srgb_to_oklab` `:88`, `oklab_to_xyz` `:94`.
- `color/gamut.rs` — `GAMUT_EPS` `:14`, `in_gamut` `:27`, `Ray` `:37` (półprosta LMS′ = base + C·step),
  `boundary` `:96`, `finish_bisection` `:143`, `max_chroma` `:162`.
- `color/contrast.rs` — stałe APCA `:12–23`, `wcag21` `:32`, `apca_y` `:40`, `apca_signed` `:56`, `contrast` `:71`.
- `color/delta_e.rs` — `delta_e` `:22`, `delta_e_ok` `:40`, `delta_e_hyab` `:47`, `lab_d65` `:61`, `ciede2000`
  `:91`, `ictcp` `:172`, `delta_e_itp` `:181`, stałe CAM16 `:191–210`, `cam16_ucs` `:213`, `delta_e_cam16` `:250`.
- `color/cvd.rs` — `simulate_cvd` `:13`, `lerp` `:49`, wybór macierzy `:56–81`, stałe (Brettel/Viénot/Machado
  11 × 3) od `:87`.
- `tests/test_engine_color.py` — 69 testów wobec wyroczni (`algopalette.color`, `algopalette.color.fast`), 2000
  losowych kolorów w gamucie (ziarno 20261115) + 11 kolorów brzegowych; `skipif("color" not in implemented)`.

**Decyzje (5).**
- `max_chroma` (`gamut.rs:162`): wartość = ta sama bisekcja co wyrocznia (przedział [0, 0.5], środek, kanały
  liniowe w [−1e-6, 1 + 1e-6]) przez 20 kroków (przedział 4.8e-7), potem Newton na kanale przekroczonym w górnym
  końcu; pierwiastek przyjęty tylko, gdy tuż pod nim kolor jest w gamucie, inaczej bisekcja do wyczerpania
  precyzji. Zgodność z `fast.max_chroma(l, h, tol=1e-13)` ≤ 1e-9 (wyrocznia z domyślnym `tol=1e-5` zwraca dolny
  koniec przedziału, czyli wartość do 1e-5 mniejszą — to sprawdza osobna asercja). Pochodna: funkcja niejawna
  `lin_k(L, C*, H) = próg` ⇒ `dC*/dθ = −(∂lin_k/∂θ)/(∂lin_k/∂C)`; `∂lin_k/∂θ` z liczb dualnych przy stałym C*,
  `∂lin_k/∂C` analitycznie (`Ray::channel`). W punkcie zmiany kanału ograniczającego pochodna jednostronna. L
  poza [0, 1] → wartość 0 i pochodna 0. Dla L = 0 wynik NIE jest zerem (≈ 0.0116 przy h = 30°): tolerancja
  gamutu 1e-6 dopuszcza małe C przy czerni — tak samo liczy wyrocznia.
- Punkty nieróżniczkowalne (`scalar.rs`): `sqrt(0)`, `cbrt(0)`, `powf(0, p < 1)`, `abs(0)`, `hypot(0, 0)`,
  `atan2(0, 0)` mają pochodną 0 ⇒ ΔE identycznych kolorów ma gradient dokładnie zerowy we wszystkich pięciu
  metodach (test `identical_colors_have_zero_derivative`).
- ΔE `2000` w CIELAB D65 (biel xy 0.3127/0.3290), `itp` w ICtCp z bielą 203 cd/m², `cam16` w CAM16-UCS przy
  środowisku `CAM16JMh.ENV` coloraide (L_A = 64/π·0,2, tło 20, „average”, D = 0.8317); stałe środowiska
  przepisane liczbowo z coloraide 8.15 (`delta_e.rs:197–207`). `hyab` w OKLab.
- Funkcje koloru w Ruście biorą OKLab; funkcje `_engine` biorą i zwracają OKLCH `[l, c, h°]`.
- Testy pochodnych: gradient z `Dual` wobec różnicy centralnej 4. rzędu; punkt uznany za „z dala od załamania”,
  gdy różnice z krokami 2e-4 i 1e-4 zgadzają się do 1e-7 (ocena niezależna od sprawdzanej pochodnej); 200
  punktów gładkich na funkcję, najwyżej 20 % losowań odrzuconych (zmierzone: ≤ 243 losowania na 200).

**Decyzje (4a).**
- Walidacja Rusta = lista z I1 + to, co sprawdzał `io.py` v1: `l ∈ [0,1]`, `c ≥ 0` (kolory i `avoid_colors`);
  wagi ≥ 0 (każda zasada, zależność, układ, rozrzut); `tol`, `jitter`, `severity`, `avoid_distance`, `time_cap_s`,
  `min_diversity`, `hard_weight` ≥ 0; `n_proposals ≥ 1`, `budget ≥ 1`, `seed`/`threads` nieujemne całkowite;
  3–16 slotów; unikalne `id` (ścieżka `slots[i].id` drugiego wystąpienia); zakaz L/C `od < do`; zakaz H końce
  różne mod 360; metryka zależności pasuje do rodzaju (`contrast` ↔ wcag21/apca, `distance` ↔ ΔE, inne rodzaje:
  tylko `null`); `t ∈ [0,1]`. NIE sprawdza: `lo ≤ hi` zakresów, zakresu wartości odcienia, istnienia celu
  zależności (zerwana zależność to nie błąd schematu).
- `hex`, `name`, `preset`, `view_model` opcjonalne (`#[serde(default)]`), `view_model` dowolny tekst — silnik ich
  nie używa. Wszystkie inne pola wymagane, także o wartości `null`.
- Opisy błędów po angielsku (jak komunikaty serde, których nie da się spolszczyć); to kanał techniczny, napisy dla
  użytkownika składa Python.
- `start` odrzuca nieznane id w `free` (`ValueError("free[k]: unknown slot id")`).

**Zależności (wersje).** Rust: `serde 1.0.229` (derive), `serde_json 1.0.154`, `serde_path_to_error 0.1.20`
(ścieżka błędu), `pyo3 0.30.1` (`abi3-py313`; cecha `extension-module` już niepotrzebna — maturin ustawia
`PYO3_BUILD_EXTENSION_MODULE`). Python (budowanie): `maturin 1.16.0` (`requires = ["maturin>=1.16,<2.0"]`).
rustc/cargo 1.99.0, uv 0.13.6.

**Wyniki policzone (5).** `cargo test -p algopalette-core color`: 24 zielone; całość `cargo test -p
algopalette-core`: 63 (40 jednostkowych + 23 `schema_contract`). `uv run pytest -q tests/test_engine_color.py`: 69
zielonych w 0,7 s. `cargo fmt --check` czysto, `cargo clippy --all-targets -- -D warnings` bez uwag, `ruff` i
`ty` na `tests/test_engine_color.py` i `_engine.pyi` czysto. Sprawdzone mutacją (test pada po zepsuciu): znak
pochodnej `max_chroma`, pochodna `cbrt`, pochodna `atan2`. `build_info()["implemented"] == ["schema", "color"]`.

**Wyniki policzone (4a).** `cargo test -p algopalette-core`: 32 zielone (9 jednostkowych: 6 rng + 3 violation;
23 w `schema_contract`). `cargo fmt --check` czysto, `cargo clippy --all-targets -- -D warnings` bez uwag.
`uv sync` buduje `src/algopalette/_engine.abi3.so` (pierwszy raz ~21 s, potem ~5 s); `build_info()` →
`{'version': '0.1.0', 'profile': 'release', 'implemented': ['schema']}`; `validate` przyjmuje 12/12 plików
kontraktu; nieznane pole → `ValueError: slots[2].rules.hue.value.foo: unknown field ...`. `ruff`/`ty` na
`_engine.pyi` czysto. `pytest tests/test_color.py tests/test_fast.py`: 46 zielonych (paczka importuje się z
backendem maturin).

**Pułapki, które kosztowały czas.**
1. pyo3 0.30 ma inne API niż starsze poradniki: moduł deklaratywny `#[pymodule] mod … { #[pymodule_export] use … }`,
   `Python::detach` zamiast `allow_threads`, `PyDict::new(py)` zwraca `Bound`. Poradnik do TEJ wersji:
   `~/.cargo/registry/src/*/pyo3-0.30.1/guide/src/`.
2. `[f64; 2]` z serde przyjmuje za długą tablicę po cichu, a błąd wychodzi dopiero z serde_json jako składniowy
   („trailing characters”), bez ścieżki. Stąd własny `pairs` w `schema.rs:218` (test
   `exclusion_pair_must_have_two_numbers`).
3. `[tool.uv] cache-keys` obejmuje `crates/**/*.rs`: każde `uv run` po zmianie Rusta przebudowuje release
   (5–25 s). Wzorzec pracy: `uv sync` w tle, potem `uv run --no-sync …` na pierwszym planie.
4. `ty` nie widzi modułu z pliku `.so` — potrzebny `_engine.pyi`; nowe funkcje `_engine` dopisuj też tam.
5. `cargo clippy` nie buduje binarki; `./target/debug/algopalette-bench` powstaje dopiero po `cargo build`.

6. ΔE `itp` koloru prawie czarnego z minimalnie ujemnym kanałem liniowym (w tolerancji gamutu 1e-6, np. OKLCH
   `[0.00025, 0.0167, 154]`, kanały ≈ −4e-7) wybucha w SAMYM coloraide do ~3e62 (mianownik krzywej PQ przechodzi
   przez zero dla ujemnego LMS). Rust odtwarza to co do ~12 cyfr; test porównuje więc ΔE błędem bezwzględnym w
   skali 0–100 i względnym powyżej (`_max_scaled`). **Skutek dla Tasku 14:** przy `delta_e = "itp"` kolor wolny
   przy czerni na brzegu gamutu może dać funkcję celu ~1e120 i nieskończony gradient — `Problem` musi to
   zabezpieczyć (np. liczyć ΔE po obcięciu kanałów do ≥ 0 albo trzymać kolory wolne w gamucie ścisłym) i
   zgłosić wybór kontrolerowi.
7. Wzorcowe liczby do testów Rusta bierz z wyroczni (`uv run --no-sync python -c …`), nie z pamięci: wartości
   OKLCH czerwieni sRGB wpisane „z głowy” różniły się na 15. cyfrze.

**Czego NIE zweryfikowano (5).** Gałęzi coloraide „ujemna barwność M → ponowne przeliczenie” w CAM16 (kolory
daleko poza gamutem; w Ruście jej nie ma — udokumentowane w nagłówku `delta_e.rs`). Zgodności ΔE dla kolorów
wyraźnie poza gamutem (testy biorą kolory w gamucie + brzegi + dwa kolory tuż za gamutem). Wydajności (pomiary
dopiero w Tasku 16; `max_chroma` to ~25 wyliczeń kanałów na wywołanie — kandydat do profilowania).

**Czego NIE zweryfikowano (4a).** Instalacji `uv tool install --editable .` (to 4b, kontroler). Zgodności
`schema.rs` z `io.session_to_dict` v2 (Task 3 powstaje równolegle; wykryje to test kontraktu po dołożeniu 40
plików z `eval.json`). Pełnego `pytest` (zgodnie z planem każde zadanie uruchamia tylko swoje Verify).
Budowania na innym systemie niż ta maszyna.

## 0b. TRYB CIEMNY + POMOC KONTEKSTOWA (2026-11-15) — T1–T8 ☑, przegląd + fala napraw, SCALONE do `main` i wypchnięte (bez re-review i bez uruchomienia testów — decyzja użytkownika)

- **STAN NA TERAZ (2026-11-15, koniec dnia):** `gui` scalona do `main` i wypchnięta na `origin`. Ostatni commit
  zawiera falę napraw po przeglądzie całości, która w poprzedniej sesji została NIEZACOMMITOWANA (sesja przerwana
  przed commitem i bez wpisu w handoffie). Użytkownik: „nie testuj juz. handoff + commit + merge + push. jezeli cos
  sie nie bedzie zgadzalo w dzialaniu aplikacji, to wrocimy do tematu” → **fala napraw NIE była uruchomiona
  testami ani lintem, re-review NIE było**. Jeśli użytkownik zgłosi błąd: najpierw `uv run pytest -q tests/gui`
  (w tym nowe `tests/gui/test_review_fixes.py`, 14 testów), `ruff check`, `ty check`.
- **Pułapka, która kosztowała zgłoszenie użytkownika („dlaczego nie ma ciemnego trybu i pomocy?”):** launcher
  `~/.local/bin/algopalette` był z `uv tool install .` BEZ `--editable` — zamrożona kopia z 2026-11-15 00:51,
  sprzed `gui/theme.py`/`gui/help.py`. Przeinstalowane `uv tool install --editable . --force` → launcher czyta
  wprost z `src/` w repo (sprawdzone: `algopalette.gui.theme.__file__` wskazuje repo). Nie instaluj już bez
  `--editable`; po zmianie zależności w `pyproject.toml` powtórz to polecenie.
- **Fala napraw (co zmienia, wg diffu):** `theme.apply` ustawia też `QToolTip.setPalette` (paleta podpowiedzi
  była statyczna); `_restyle` czyści arkusz, gdy żaden znacznik nie jest aktywny (`mark_text(w, None)`); ciemny
  `Highlight` #3a6bc0 (kontrast); `ProposalsTab._state()`/`restyle()` — kolory stanów, błąd silnika i szczegóły
  przemalowywane w `MainWindow._theme_changed`; `HelpPanel._rerender` na `theme.notifier.changed` (QTextBrowser
  wpieka kolory linków), `_showing_results` (wyczyszczenie wyszukiwarki wraca do tematu, ponowne otwarcie tego
  samego tematu po wyszukiwaniu działa), `itemClicked`→`_pick` / `itemActivated`→`_pick_topic` (grupa nie
  przełącza się dwa razy w KDE); `uncovered` wymaga klucza od `QGroupBox` z tytułem i od każdej zakładki
  `QTabWidget`, `QToolBar` nie jest już nieprzezroczysty; `act_info` w menu Pomoc z kluczem; `Swatch` obwódka
  #808080 zamiast `palette(mid)`; pusty uchwyt `Bar` w kolorze `windowText`; opisy nastrojów „neon” i „nocny
  wysoki kontrast” zgodne z silnikiem (skrajne tło, ciemne LUB jasne); poprawki treści w `help_content/*`.
  Test pokrycia całego okna już bez parametryzacji motywem (`uncovered` od motywu nie zależy).
- Raport z przeglądu nie został zapisany w repo — kategorie znalezisk (C/I/M) nieznane tej sesji.

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
- **T8 ☑ integracja**: `tests/gui/test_help_coverage.py` — `uncovered(win) == []` dla każdej zakładki, ról
  tło/tekst/akcent na Palecie, obu widoków i obu motywów; każdy temat osiągalny (klucz na elemencie/nagłówku/
  zakładce/akcji albo link `help:` z innego tematu). Zrzuty obu motywów obejrzane → naprawione 2 usterki ciemnego
  motywu: (1) `widgets.hint()` miał `color: palette(placeholder-text)` w arkuszu — Qt rozwiązuje `palette(...)`
  RAZ, przy polerowaniu, więc po zmianie motywu wskazówki zostawały w kolorze jasnego motywu (prawie niewidoczne)
  → teraz `theme.mark_text(lbl, "hint")` + `Colors.hint`; (2) tło koła odcieni w Analizie było cache’owane bez
  koloru okna (szare rogi z jasnego motywu) → klucz cache zawiera kolor okna, a obrazy biorą
  `QApplication.palette()` (`_window_color()`), bo `widget.palette()` dostaje nową paletę z opóźnieniem.
  **Pułapka na przyszłość:** nie używaj `palette(...)` w arkuszach stylu dla kolorów, które mają śledzić motyw —
  tylko `theme.mark_*` / `theme.colors()` przy budowie + przebudowa w `_theme_changed`. README: motyw + sekcja
  „Pomoc w programie”.
- **Weryfikacja policzona (2026-11-15, po T8):** cały `uv run pytest -q` **393 passed** (bazowo 336), `tests/gui`
  97; `ruff check`, `ruff format --check`, `ty check` — zero uwag.
- **NIE zweryfikowane:** prawdziwy pulpit (Wayland/X11, KDE/GNOME): czy „systemowy” wykrywa ciemny motyw Manjaro
  (`QStyleHints.colorScheme()` bywa Unknown → jasny; wtedy wybór ręczny w menu), opóźnienie podpowiedzi 300 ms
  na żywo, wygląd natywnej podpowiedzi Qt (zrzut robiony na QLabel z paletą ToolTip), F1 w menu na prawdziwym
  pulpicie (offscreen test przechodzi), HiDPI. Treść pomocy porównana z kodem przez kontrolera, ale nie przez
  drugą osobę — to robi przegląd.

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
- 2026-11-15 — tryb ciemny + pomoc kontekstowa (T1–T8), przegląd, fala napraw zacommitowana bez testów (decyzja
  użytkownika); launcher przeinstalowany `--editable`; `gui` scalona do `main`, push.
- 2026-11-15 — scalenie kopii repo (katalog sesji dociągnięty do 4b71aeb, launcher przepięty); brainstorming
  przebudowy „jeden panel zasad + silnik w Rust”; pomiar bazowy silnika; spec napisany na gałęzi
  `feat/zasady-silnik` (worktree `.worktrees/zasady-silnik`), czeka na akceptację. Szczegóły: §0c.
- 2026-11-15 — spec zaakceptowany („wszystko sie zgadza”); plan 20 zadań + `.tasks.json`, natywne zadania #1–#20
  z zależnościami; przegląd przyjęty w wariancie „a” jako założenie do potwierdzenia. Kodu nie ruszono.
- 2026-11-15 — start wykonania: tryb = agent silnikowy Fable high (Rust) + kontroler inline (reszta), przeglądy
  Opus xhigh po Tasku 16 i 20; Task 4 podzielony na 4a (agent) i 4b (kontroler); natywne zadania #1–#20
  odtworzone; ledger w `.superpowers/sdd/`; gałąź `feat/silnik-rust` założona.
