# Układ odcieni = jedna lista na kole; triada, tetrada, mono… jako generatory listy (design)

Status: projekt do akceptacji użytkownika. Data: 2026-11-19. Repo: `/home/qrikk/algopalette` (`main` @ `b78de22`).

## 1. Intencja (słowa użytkownika — wiążące)

„Tryby kolorów — dopełniający, triada, tetrada, własna lista etc… jest ich za mało. Brakuje choćby mono.
Niemniej największą wadą jest to, że po włączeniu czegokolwiek innego niż 'własna lista' koło kolorów znika
i użytkownik zostaje z niczym. No tak, triada, tetrada, ale bazowana na czym? Niech wszystkie te tryby
skutkują pojawieniem się oczekiwanych kolorów na kole koloru z trybu 'własna lista'. Innymi słowy, 'własna
lista' zostaje domyślnym, w zasadzie jedynym trybem, a ustawienia typu tetrada, dopełniający, triada,
manipulują kolorami już na tej liście (albo generują kolory które pojawiają się na liście).”

Rozstrzygnięcia w rozmowie (WIĄŻĄCE, nie otwierać ponownie):
- **Wariant A**: lista = **rodziny odcieni**. Akcent `i` (od 0, kolejność kolorów) dostaje cel `lista[i mod k]`
  (k = długość listy) — **bez** dzisiejszego „przesuwania obiegów”. Triada przy 8 akcentach = 3 punkty na kole,
  akcenty 3/3/2; mono = 1 punkt, wszystkie akcenty w nim.
- Generatory to **jednorazowe przyciski**: zastępują listę układem zbudowanym od odcienia bazowego; lista nie
  pamięta, czym była („tak, jest ok” na pytanie o brak pamięci układu).
- Baza generatora: zaznaczony punkt listy; bez zaznaczenia — pierwszy; pusta lista — 25°.
- „Obróć wszystkie” przesuwa całą listę (zastępuje suwak „obrót”).
- Nowe: mono, prostokąt (60°/120°), „z bieżących kolorów”. Analogiczny i „równo po kole” pytają o liczbę punktów
  (i analogiczny o rozpiętość).
- Pusta lista = brak celów (zastępuje rodzaj „brak”).
- Przy każdym punkcie widać, ile akcentów do niego trafia (×N).
- Stare pliki i presety → lista dająca **dokładnie te same cele co dotąd** (wygenerowane palety bez zmian).

## 2. Cele / nie-cele / anty-cele

Cele: (1) koło z listą zawsze widoczne w ramce „Układ odcieni” (zakładka Zasady, „cała paleta”); (2) każda
harmonia widoczna jako punkty na kole i edytowalna punkt po punkcie; (3) więcej układów (lista w §4.3);
(4) zgodność wsteczna plików sesji v2, presetów użytkownika i presetów wbudowanych (te same cele).

Nie-cele: zmiana tolerancji/rozrzutu/twardości/wagi układu (zostają jak są); zmiana kłódki zasad poza
dostosowaniem do braku `kind`; zmiana importu motywu z sieci (`themes/apply.py` — już ustawia pustą listę).

Anty-cele: ukryte tryby/formuły, których nie widać na kole; jakakolwiek ścieżka, w której zmiana liczby akcentów
po cichu przelicza listę (lista jest jawna — dodanie akcentu tylko zmienia liczniki ×N); zmiana wyników
wbudowanych presetów (test jakości `slow` 452/452 ma przejść bez strojenia).

## 3. Podejścia

- **A (wybrane): sama lista w modelu i w silniku.** `HueScheme` traci `kind/rotation/center/spread`, zostaje
  `hues` + `tol/jitter/hard/weight`. Generatory = czyste funkcje Pythona. Rust: cel = `hues[i mod k]` (+ jitter).
  Jeden model, nic ukrytego.
- B: zostawić `kind` i w GUI zawsze ustawiać „custom”. Odrzucone — martwe gałęzie w formacie pliku, w Rust
  i w presetach; łatwo o regres, w którym stary tryb znów działa niewidocznie.

## 4. Projekt

### 4.1 Model (`model.py`)
`HueScheme(hues: tuple[float, ...] = (), tol=15.0, jitter=0.0, hard=False, weight=1.0)`. Pola `kind`,
`rotation`, `center`, `spread`, `custom` znikają. Długość listy ≤ `MAX_ACCENTS`. Pusta = brak celów.
`default_session()` — lista „równo po kole” dla 8 akcentów od 0° (= dzisiejsze `equal`, rotation 0).

### 4.2 Silnik (Rust, `crates/core`)
`schema::HueScheme { hues: Vec<f64>, tol, jitter, hard, weight }` (`deny_unknown_fields` zostaje),
`HueSchemeKind` usunięty. `rules/hues.rs::scheme_targets`: `hues[i % k]` (+ jitter jak dziś), pusta lista →
brak celów. Testy Rust przepisać na nową semantykę; port starej formuły zostaje tylko w Pythonie (§4.5).
Fixture'y kontraktu `tests/fixtures/v2_contract/*` i `bench/*` — przeliczyć skryptem (jak w §0g handoffu).

### 4.3 Generatory (`hue_layouts.py`, nowy, czyste funkcje)
Każdy: `(baza°, parametry) → tuple[float, ...]` w [0, 360), kolejność od bazy:
| nazwa w GUI | wynik |
|---|---|
| mono | `(b,)` |
| analogiczny (N punktów, rozpiętość S) | N punktów równo w `b − S/2 … b + S/2` (N = 1 → `(b,)`); domyślnie N = 3, S = 60° |
| dopełniający | `(b, b+180)` |
| rozszczepiony dopełniający | `(b, b+150, b+210)` |
| triada | `(b, b+120, b+240)` |
| kwadrat (dzisiejsza „tetrada”) | `(b, b+90, b+180, b+270)` |
| prostokąt | `(b, b+60, b+180, b+240)` |
| równo po kole (N) | `b + 360·i/N`; domyślnie N = liczba akcentów |
| z bieżących kolorów | odcienie WSZYSTKICH akcentów sesji (`slots[2:]`, `slot.value`, bez względu na kłódki i `use_scheme`; decyzja agenta): skupiska jak `sources.cluster_hues` (25°, C ≥ 0.03), ale w **kolejności pierwszego wystąpienia akcentu**, nie wg wagi; brak barwnych akcentów → komunikat, lista bez zmian |
Operacja `rotate(hues, d)` dla „obróć wszystkie”.

### 4.4 GUI (`gui/rules_tab.py` `_hues_box`, `gui/picker.py`)
- Ramka „Układ odcieni”: zawsze `ListPicker(mode="hue")` z listą; combo „rodzaj” i suwaki
  obrót/środek/rozpiętość znikają.
- Rząd przycisków „Wstaw:” (tabela §4.3). Analogiczny i „równo po kole”: małe okno/wyskakujące pole z N
  (i S); reszta działa od razu. Każde wstawienie = jeden krok cofania.
- „Obróć wszystkie”: suwak względny (przeciąganie przesuwa listę o różnicę; po puszczeniu wraca do 0) albo
  pole „obróć o … °” + przycisk — wybór buildera; jeden krok cofania na gest (`coalesce`).
- Przy każdym wierszu listy licznik `×N` akcentów (N = liczba `i` z `i mod k == wiersz` wśród akcentów
  z `use_scheme`); wiersz z ×0 wyszarzony. Na kole punkty jak dziś.
- Pod listą: tolerancja, rozrzut losowy, twardy, waga — bez zmian.
- `rule_rows.py:385` „układ wyłączony” ⇔ pusta lista („→ układ odcieni jest pusty — brak celów”).
- `rules_tab.py:269` (klucz przebudowy) — bez `kind`; przebudowa przy zmianie „pusta/niepusta” jeśli potrzebna.

### 4.5 Zgodność wsteczna (`io.py`, `presets.py`, `presets_builtin.py`, `migrate.py`)
- Python: `legacy_targets(kind, rotation, center, spread, custom, n) → tuple[float, ...]` — wierny port dzisiejszego
  `base_hues` + obiegów **bez** jittera (jitter zostaje polem układu i działa w silniku tak jak dziś).
- **Długość rozwinięcia (decyzja agenta po builder-checku):** `custom` rozwija się do `max(n, k)` — przy
  k ≥ n lista zostaje CAŁA (14 pozycji presetu nie przepada; dodanie akcentu dalej bierze `custom[n]` jak dziś),
  przy k < n — do n z obiegami jak dziś. Rodzaje o stałym k (triada itd.) i `equal`/`analogous` → długość n.
  Zero akcentów → `custom` cała, pozostałe rodzaje → pusta lista.
- **Plik sesji v2** ze starym `hue_scheme` (ma `kind`): lista = `legacy_targets(…, n = liczba akcentów pliku)`
  — cele `hues[i mod len]` dla i < n równe starym. `kind="none"` → pusta lista; `custom` pusta → pusta.
  Nowy zapis bez `kind`. Format zostaje `algopalette.v2` (dekoder rozpoznaje stary kształt po kluczu `kind`) —
  albo podbicie do v3; wybór buildera, byle stare pliki wczytywały się po cichu z tymi samymi celami
  (bez komunikatu migracji — to nie utrata funkcji). Pliki v1 → przez `migrate` do nowego kształtu.
- **Presety (wbudowane i użytkownika)**: wynik zależy od liczby akcentów w chwili nałożenia, więc preset
  przechowuje **przepis** (dzisiejszy kształt: kind/rotation/center/spread/custom + tol/jitter/hard/weight)
  rozwijany przy nakładaniu przez `legacy_targets(…, n = liczba akcentów sesji)`. Wbudowane listy custom mają
  14 pozycji (= `MAX_ACCENTS`), więc wynik się nie zmienia. `presets.json` użytkownika: odczyt starego kształtu
  bez zmian; nowy preset zapisany z sesji zapisuje gotową listę (przepis „lista”). `is_modified` porównuje
  listę rozwiniętą dla bieżącej liczby akcentów (dodanie akcentu po presecie może oznaczyć „(zmieniony)” —
  akceptowalne: lista się wtedy nie zmienia, a preset dałby inną).
- `sources.character_settings`: lista = skupiska (bez powielania do 14 — przy nowej semantyce to to samo),
  ale w kolejności pierwszego wystąpienia akcentu (ta sama funkcja co generator „z bieżących kolorów”);
  `apply_transfer` → pusta lista.
- `rules_edit.set_rules_lock` (`rules_edit.py:160`): `scheme.kind == "none"` → `not scheme.hues`.
- Analiza (`analysis_tab.py:211`) — tylko `tol`, bez zmian logiki.

### 4.6 Pomoc i README
Przepisać `rules.hues*` w `help_content/rules.py` (zniknie `rules.hues.kind/rotation/center/spread`, dojdą
tematy przycisków generatorów, „obróć wszystkie”, licznik ×N); `rules.py:167` (liczba akcentów a układ) —
nowa semantyka rodzin. `test_help_coverage` musi przejść. README — sekcja o układzie odcieni.

## 5. Akceptacja (wejście → wynik)
- `scheme_targets([15,140,280], n=8)` → `[15,140,280,15,140,280,15,140]`; `[]` → brak celów; jitter jak dziś.
- Generatory od bazy 30°: mono `(30)`, dopełniający `(30,210)`, triada `(30,150,270)`, kwadrat
  `(30,120,210,300)`, prostokąt `(30,90,210,270)`, rozszczepiony `(30,180,240)`, analogiczny N=3 S=60
  `(0,30,60)`, równo N=4 `(30,120,210,300)`; wyniki mod 360.
- „Z bieżących kolorów” na akcentach h = 24, 148, 113, 302, 347, 213, 67 (Dracula) → kolejność 24, 148, 113, …
  (pierwsze wystąpienie), a nie wg wagi.
- Stary plik v2 `equal rotation=10`, 8 akcentów → `hues = (10,55,…,325)`; `triad 45`, 8 akcentów → dokładnie
  dzisiejsze `[45,165,285,85,205,325,125,245]`; `engine.hue_targets` przed i po migracji identyczne dla
  wszystkich `tests/fixtures/v2_contract/manual_*.json` i dla każdego wbudowanego presetu przy 7 i 10 kolorach.
- Test jakości presetów (`slow`) — bez zmian wyników.
- GUI: ramka zawsze ma koło; klik „triada” przy zaznaczonym punkcie 40° → lista `(40,160,280)`, jeden krok
  cofania; liczniki ×N przy 8 akcentach i 3 punktach = 3/3/2; pusta lista → wiersz zasady „brak celów”.

## 6. Dla buildera (decyzje pozostawione)
Kształt kontrolki „obróć wszystkie”; jak pytać o N/S (okienko vs pola obok przycisku); dokładne teksty pomocy;
v2 z rozpoznawaniem kształtu vs v3; nazwy funkcji.
