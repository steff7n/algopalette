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
- Następny krok: wybór sposobu wykonania przez użytkownika, potem Task 1.

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

(brak kodu — uzupełnić po pierwszym zadaniu planu)

Jedyne odniesienie do PB: `/home/qrikk/palettebuilder/index.html:6236` `motif()` — wczytywanie JSON (akceptuje
`palettebuilder.v2/v3`, `palette` = `{hex, role}` lub napisy); okno „Wczytaj…” przyjmuje wklejenie; PB mieści ≤ 16
kolorów (nadmiar scala). APCA w PB (`index.html:1293`) = te same stałe 0.0.98G-4g.

## 4. Stan weryfikacji

Nic do weryfikacji (brak kodu).

## 5. Dziennik sesji (append-only)

- 2026-11-14 — brainstorming: ustalenia jak w §2, spec napisany, `git init`, handoff założony.
- 2026-11-14 — builder-check (3 pytania): determinizm = budżet w ewaluacjach (decyzja agenta); nastroje tylko wg ról
  strukturalnych (decyzja agenta); pytanie o zachowanie danych PB → użytkownik odrzucił cały kierunek PB→AlgoPalette;
  spec oczyszczony z ról PB, czytania motifs; dodana akcja „Przenieś do PaletteBuildera”, max 14 akcentów (PB ≤ 16).
- 2026-11-14 — spec zaakceptowany; plan 11 zadań + .tasks.json; natywne zadania #1–#11 z zależnościami.
- 2026-11-14 — wykonanie: gałąź `feat/algopalette`; Task 1 wysłany (Sonnet). Zmiana zasad przeglądu (jeden, Opus high, na końcu).
