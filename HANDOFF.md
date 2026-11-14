# HANDOFF — AlgoPalette

Dla agenta, który przejmie pracę bez tej rozmowy. Sekcja 0 = stan na teraz. Niżej decyzje, pułapki, mapa, dziennik.

## 0. STAN NA TERAZ — 2026-11-14: spec ZAAKCEPTOWANY, plan napisany, implementacja NIE rozpoczęta

- Spec `docs/superpowers/specs/2026-11-14-algopalette-design.md` — zaakceptowany słowami „a, to oks. tak, pisz plan”
  (po wyjaśnieniu, że PaletteBuildera nie ruszano; przycisk eksportu do PB ZOSTAJE).
- Plan: `docs/superpowers/plans/2026-11-14-algopalette.md` + `.tasks.json` (11 zadań, natywne zadania #1–#11 z
  zależnościami). Etap 1 = Taski 1–7 (rdzeń), Etap 2 = Taski 8–11 (TUI). Przegląd: JEDEN, całego kodu, na samym końcu, Opus
  effort HIGH; błędy naprawia kontroler sam, BEZ re-review, potem informuje użytkownika (decyzja §2).
- Kolejność: 1 → 2 → 3 → 4 → {5, 6}; 2 → 7; {4,5,6,7} → 8 → {9, 10} → 11.
- Nic nie zainstalowano w projekcie (brak `pyproject.toml` — powstaje w Tasku 1). Zależności sprawdzone tylko w
  jednorazowym `uv run --no-project --with …` (coloraide 8.15, coloraide-extras 1.13, textual 8.2.8, scipy 1.18.1).
- Wykonanie: Subagent-Driven w tej sesji, gałąź `feat/algopalette`. Dziennik kontrolera (git-ignored):
  `.superpowers/sdd/2026-11-14-algopalette/progress.md`.
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
- Następny: Task 6 (sources) i Task 7 (pb_export).

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
- `src/algopalette/color/fast.py` — numpy `(...,3)`: `oklch_to_oklab`, `oklab_to_linear_srgb`, `in_gamut`, `max_chroma`
  (bisekcja), `wcag21`, `apca(_signed)`, `contrast`, `delta_e(ok|hyab)`, `simulate_cvd(vienot|machado)`.
  + Brettel (Task 3). ΔE 2000/itp/cam16 → `NotImplementedError`.

Jedyne odniesienie do PB: `/home/qrikk/palettebuilder/index.html:6236` `motif()` — wczytywanie JSON (akceptuje
`palettebuilder.v2/v3`, `palette` = `{hex, role}` lub napisy); okno „Wczytaj…” przyjmuje wklejenie; PB mieści ≤ 16
kolorów (nadmiar scala). APCA w PB (`index.html:1293`) = te same stałe 0.0.98G-4g.

## 4. Stan weryfikacji

Po Tasku 5: `uv run pytest -q` → 200 passed; `ruff check`, `ruff format --check`, `ty check` → zero uwag.

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
