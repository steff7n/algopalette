# Jeden panel zasad + natywny silnik — projekt

Data: 2026-11-15. Gałąź robocza `feat/zasady-silnik` (worktree `.worktrees/zasady-silnik`; katalog główny zostaje
na `main`, bo stamtąd czyta launcher). Status: do akceptacji użytkownika.

## 1. Intencja (słowa użytkownika)

„przebuduj UI w taki sposob, zeby ograniczenia i wytyczne dot. kolorow mozna bylo ukladac tylko w jednym panelu,
konkretnie w globalnym. Poza tlem, tekstem i akcentem, dodasz jeszcze 7 kolejnych zakladek ktore odpowiadac beda za
pozostale akcenty [czyli lacznie 10 kolorow, z mozliwoscia pomniejszenia palety do np 8 czy 7]. W ten sposob
pozbywamy sie zasad dla pojedynczych kolorow ukladanych w jednym miejscu, zasad dla palety w drugim, zasad dla tła
i tekstu w trzecim, ogólnego tonu w czwartym i tak dalej i tak dalej. To samo ustawienie jest w wielu miejscach
jednoczesnie lub sa to rozne ustawienia ale opisane sa w taki sposob, ze sie czlowiek w tym gubi, klasyczny objaw
tego, ze UI nie domaga.”

Siedem spraw z tej samej wiadomości:
1. Jeden panel zasad (wyżej).
2. Pomoc: „pare terminow wymaga rozwiniecia”; doprecyzowanie: „w 'kryminale' chodzilo o to w jaki sposob [nie] jest
   wytlumaczone pojecie C wzglednego i bezwzglednego”. „Podobnie nazewnictwo typu dziedzicz/usun. Przeciez to jest
   jedno i to samo.”
3. „wprowadzic "kontrwarunki", tj. to, czego dany kolor ma absolutnie NIE robic”; doprecyzowanie: „chodzi o
   podstawy - odcienie, jasnosc i nasycenie, np w przypadkach, gdy akceptowalny jest bardzo szeroki zakres barw,
   zalozmy 0-270, z wyjatkiem 60-85 i 140-155”.
4. „wprowadzic wybierak kolorow z mozliwoscia ich interaktywnego dodawania na liste [mowie tutaj o 'wlasna
   lista'], robienie tego tekstowo jest odrobine niepowazne”.
5. „'zakres odcienia' vs 'cel odcienia'.... co?”
6. „WIECEJ PRESETOW. mialo byc ich duzo, jest chyba 6?”
7. „Przy np 128 paletach i budzecie rzedu 30000 apka mieli to bardzo, bardzo dlugo. […] Silnik, algorytmike,
   asynch, wielowatkowosc - te cala warstwe chce miec przepisana do dowolnego niskopoziomowego jezyka.”

Ramy pracy, też słowami użytkownika: „To bardzo powazny rewrite, takze mysl i planuj ile wlezie; im wiecej
subagentow, tym lepiej [wyjatkiem jest review, ale o to mnie zapytaj po napisaniu specyfikacji]”.

Zakres panelu zasad (doprecyzowanie, WIĄŻĄCE): „mi nie chodzi w ogole o warstwe pracy z kolorami, ktore juz mamy.
ja mam ciagle na mysli workflow sprzed generacji jakiejkolwiek palety”. Panel zasad opisuje paletę, która dopiero
ma powstać. Praca na gotowych kolorach (zakładka Paleta: wartości, kłódki, widok HSL/OKLCH, przejmowanie
propozycji) nie jest przedmiotem przebudowy.

## 2. Stan dziś (commit 4b71aeb)

- Zasady żyją w czterech warstwach: nastrój (`moods.py`, `Session.mood` + `mood_snapshot`), domyślne warunki ról
  (`GlobalSettings.role_defaults`, edytowane w Globalnych w zakładkach tło/tekst/akcenty,
  `gui/globals_tab.py:366`), własne warunki koloru (`Slot.conditions`, edytowane w zakładce Paleta,
  `gui/conditions.py`), ustawienia całej palety (reszta `GlobalSettings`). Pole `None` w slocie = dziedzicz
  (`model.effective_conditions`, `model.py:315`). Stąd plakietki źródeł i dwa przyciski na tę samą czynność:
  „↺ dziedzicz” w slocie, „✕ usuń” w roli.
- Odcień ma dwa osobne warunki: `hue_range` (od–do) i `hue_target` (cel ± tolerancja). Matematycznie cel ±
  tolerancja jest łukiem `[cel − tol, cel + tol]` (`constraints.py:370-398`), więc to dwa zapisy jednej rzeczy.
- „Własna lista” układu odcieni to pole tekstowe z liczbami po przecinku (`gui/globals_tab.py`, pole `custom`).
- 9 wbudowanych nastrojów (`moods.py:176-196`).
- Silnik: Python + numpy + scipy L-BFGS-B, gradient różnicami skończonymi (D+1 = 31 ocen palety na krok przy 10
  kolorach), propozycje liczone kolejno, każda karana za podobieństwo do wszystkich poprzednich, jeden wątek.
  **Pomiar 2026-11-15** (10 kolorów, budżet 30 000, 4 propozycje): „neutralny” 0,14 s/propozycję, „neon”
  0,11 s/propozycję (wczesne wyjście), „chłodny mglisty” **1,84 s/propozycję** → 128 propozycji ≥ 4 min. Profil:
  35% czasu w `fast.max_chroma` (bisekcja granicy gamutu), reszta to narzut numpy na małych tablicach.
- Dwa interfejsy: GUI PySide6 (domyślny) i stare TUI pod `--tui` (`src/algopalette/tui/`, `tests/tui/`).

## 3. Cele

1. **Jedno miejsce na zasady.** Zakładka „Zasady” (dawne „Globalne”) jest jedynym miejscem, w którym ustawia się
   cokolwiek, co wpływa na generowanie. Każda zasada jest edytowalna w dokładnie jednym miejscu.
2. **Zakładka na kolor.** Tło, tekst, akcent 1…N. Domyślnie 10 kolorów (8 akcentów); liczbę można zmieniać,
   zakładki za nią podążają. To, co widać w zakładce koloru, to komplet zasad tego koloru. Brak dziedziczenia.
3. **Kontrwarunki**: zakazane przedziały odcienia, jasności i nasycenia, dowolnie wiele na kolor.
4. **Jedna zasada odcienia** zamiast „zakresu” i „celu”.
5. **Wybierak** do „własnej listy” odcieni: klik na kole dodaje pozycję, lista próbek z usuwaniem i przestawianiem.
6. **Pomoc**: terminy wyjaśnione na przykładach z liczbami; jedno słowo na usunięcie zasady.
7. **Presety**: co najmniej 48 wbudowanych, w kategoriach, z wyszukiwarką.
8. **Silnik natywny** (Rust): zasady, funkcja celu, optymalizacja, wielowątkowość, przerwanie i postęp. Cel
   wydajności w §9.6.

## 4. Nie-cele

- Warstwa pracy na gotowych kolorach (zakładka Paleta) poza zmianami wymuszonymi przeniesieniem zasad (§7.5).
- Zakładka Analiza poza dostosowaniem do nowego modelu (łuk odcienia z zakazami, cele układu z silnika).
- Eksport do PaletteBuildera, pliki PB (bez zmian; PB nadal tylko jako cel eksportu).
- Nowe rodzaje zasad poza zakazanymi przedziałami. Rodzaje zależności między kolorami bez zmian.
- Tłumaczenia (interfejs tylko po polsku).

## 5. Anty-cele (porażka, nawet gdy „działa”)

- Zasada edytowalna w dwóch miejscach albo druga warstwa „wspólnych” wartości, z której kolory coś dziedziczą.
- Dwa słowa na tę samą czynność („dziedzicz”/„usuń”).
- Pythonowy silnik zapasowy albo druga implementacja semantyki zasad obok natywnej.
- Różnice skończone w gorącej pętli optymalizatora.
- Wynik zależny od liczby wątków albo od kolejności ich zakończenia.
- Migracja starego pliku, która po cichu gubi albo zmienia zasadę.
- Podpowiedź-definicja bez przykładu przy terminie liczbowym („ułamek największego C osiągalnego w sRGB”).
- Wszystko z wcześniejszych speców nadal obowiązuje: brak podglądu kodu, rachunek w OKLCH, uczciwy raport
  niespełnialności, nic z PaletteBuildera jako źródło.

## 6. Podejścia (wybrane przez użytkownika)

**Edycja zbiorcza akcentów** (bez dziedziczenia zmiana jednej zasady w 8 akcentach to 8 zakładek):
- A. Zaznaczanie kilku zakładek naraz; zmiana trafia do wszystkich zaznaczonych. **Wybrane** („wybieram A”).
- B. Zakładka „wspólne dla akcentów” z nadpisywaniem per kolor. Odrzucone: to dzisiejsze dziedziczenie.
- C. Tylko przycisk „skopiuj zasady do…”. Odrzucone: więcej klikania, brak podglądu różnic.

**Język i osadzenie silnika:**
- 1. Rust jako biblioteka w procesie GUI (PyO3, wątki rayon). **Wybrane** („wariant silnika 1”). Kompilator
  pilnuje bezpieczeństwa wątków; ocena naruszeń na żywo bez serializacji między procesami; jedna paczka. Koszt:
  zależność budowania `maturin`; po zmianie kodu Rust trzeba przebudować rozszerzenie.
- 2. C + cffi + pthreads (wzorzec z fontset-ui). Odrzucone: pamięć i współbieżność pilnowane ręcznie.
- 3. Osobny program silnika, GUI rozmawia przez potok. Odrzucone: dwie binarki do pilnowania („binarka. zawsze.”
  robi się podwójne), więcej kodu na komunikację.

Pozostałe decyzje użytkownika: właściwa jest kopia z GUI, jedno repo („ta z GUI jest wlasciwa, scal to w jedno”;
zrobione: `/home/qrikk/algopalette` na 4b71aeb, launcher przepięty); TUI do usunięcia („usuwamy”).

## 7. Model zasad v2 i interfejs

### 7.1 Model (Python, `model.py`)

- `Rule[T]` = dzisiejsze `Cond[T]`: `value`, `enabled`, `hard`, `weight`. Zmiana nazwy klasy to decyzja buildera;
  w tym dokumencie „zasada”.
- `Band`: `lo: float | None`, `hi: float | None`, `exclude: tuple[tuple[float, float], ...]`.
- `ChromaBand`: `mode: "abs" | "rel"`, `lo`, `hi`, `exclude` (zakazy w jednostkach trybu).
- `HueArc`: `lo: float`, `hi: float` (stopnie; `lo > hi` = łuk przez 0°; pełne koło = `0, 360`), `exclude`
  (pary `(od, do)`, też z zawijaniem).
- `ContrastBound`: bez zmian (`metric | None`, `lo`, `hi`), bez zakazów.
- `SlotRules`: `lightness: Rule[Band] | None`, `chroma: Rule[ChromaBand] | None`, `hue: Rule[HueArc] | None`,
  `contrast_bg: Rule[ContrastBound] | None`, `min_distance: Rule[float] | None`,
  `cvd_min_distance: Rule[float] | None`, `extreme: Rule["weakest" | "strongest"] | None`.
  **`None` znaczy „tej zasady nie ma”** (nie „dziedzicz”). Zastosowalność jak dziś: tło nie ma `contrast_bg`;
  `min_distance`, `cvd_min_distance`, `extreme` tylko akcenty.
- `Slot`: `id`, `name`, `locked`, `value`, `rules: SlotRules`, `use_scheme: bool` (tylko akcenty, domyślnie
  `True`), `relations` (bez zmian).
- `GlobalSettings`: bez `role_defaults`; reszta pól zostaje (`polarity`, `hue_scheme`, `lightness_spread`,
  `contrast_metric`, `delta_e`, `cvd`, `fit_method`, `avoid_colors`, `avoid_distance`, `optimizer`).
- `OptimizerSettings`: `max_evals` → `budget` (znaczenie w §9.4), nowe `threads: int = 0` (0 = wszystkie rdzenie).
- `Session`: `mood` → `preset: str | None`; `mood_snapshot` znika. Znikają `effective_conditions`,
  `snapshot_key`, `default_role_defaults` (domyślne zasady ról przechodzą do presetu „neutralny”, §8).
- Limity bez zmian: 1–14 akcentów (3–16 kolorów). Sesja startowa: 10 kolorów, preset „neutralny”.
- Nowy akcent dostaje kopię zasad ostatniego akcentu (bez zależności), `use_scheme` jak on.

### 7.2 Semantyka nowych elementów

- **Zakazany przedział** `(a, b)` w zasadzie kanału X: naruszenie, gdy `a < X < b`; wielkość naruszenia =
  odległość do bliższego brzegu (`min(X − a, b − X)`), skala jak dla kanału. **Zawsze twardy**, bez wagi i bez
  osobnego wyłącznika (słowo użytkownika: „absolutnie”); działa, gdy zasada jest włączona. Zakres dozwolony
  zasady zachowuje własne twardy/miękki/waga. Klucz termu: `slot:<id>:<lightness|chroma|hue>:exclude:<k>`.
  Dla odcienia naruszenie mnożone przez to samo wygaszanie przy C → 0 co zakres odcienia. Zakazy pokrywające
  cały zakres dają stałe naruszenie, widoczne w panelu naruszeń (uczciwy raport, nie błąd walidacji).
- **Zasada odcienia**: jeden łuk. W interfejsie dwa zsynchronizowane zapisy tej samej wartości: „od–do” i „środek
  ± szerokość”. Klucz termu: `slot:<id>:hue`.
- **Układ odcieni a zasada koloru** (`use_scheme`): akcent z `use_scheme = True` dostaje cel z układu odcieni
  jako osobny term `global:scheme:<id>` (twardość, waga i tolerancja z układu, jak dziś), niezależnie od tego,
  czy ma własną zasadę odcienia. Obie rzeczy mogą działać razem (np. łuk 0–270 z zakazami + cel z układu).
  `use_scheme = False` wyłącza cel dla tego koloru. Cele liczone dla wszystkich akcentów wg pozycji (reguła
  cykliczna z `hues.py` bez zmian); przełącznik decyduje tylko, czy term powstaje.
- Wszystko inne (skale, margines twardych, wygaszanie odcienia, progi par = max z obu kolorów, pomijanie termów
  samych kłódek, zerwane zależności, gamut, unikanie kolorów, rozrzut jasności) zachowuje semantykę
  `constraints.py` z commita 4b71aeb. Ten plik jest wzorcem zachowania dla portu (§9.2).

### 7.3 Zakładka „Zasady”

Zakładka zmienia nazwę z „Globalne” na „Zasady” i staje się pierwszą (kolejność: Zasady, Propozycje, Paleta,
Analiza, Źródło; skróty F2–F6 w nowej kolejności). Kolejność i nazwa to moja decyzja wynikająca z „workflow
sprzed generacji”.

```
┌ Preset ──────────────────────────────────────────────────────────────────────────────┐
│ [szukaj…        ] [kategoria ▾] [preset ▾            ]  tło: (•) ciemne ( ) jasne  [Zastosuj] │
│ bieżący: „chłodny mglisty” (zmieniony)      [Zapisz zasady jako preset…] [Usuń własny]         │
└──────────────────────────────────────────────────────────────────────────────────────┘
Kolory: 10 [−] [+]
[cała paleta] | [■ tło] [■ tekst] [■ akcent 1 ✓] [■ akcent 2 ✓] [■ akcent 3] … [■ akcent 8]   [wszystkie akcenty]
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Edytujesz: akcent 1, akcent 2                                                         │
│ jasność L      ☑ włączona ☑ twarda  waga [1]                                  [✕ usuń] │
│   [0.600] ━━━●══════▒▒══●━━━ [0.850]     zakazane: 0.70–0.74 ✕   [+ zakaz]            │
│ nasycenie C    różne — akcent 1: 0.06–0.20 · akcent 2: 0.10–0.25     [ustaw dla obu]  │
│ odcień         brak zasady                                                  [+ dodaj] │
│   układ odcieni: ☑ stosuj → cel 45° ± 15° / 90° ± 15°                                 │
│ kontrast z tłem …                                                                      │
│ Zależności od innych kolorów (edycja przy jednym zaznaczonym kolorze)                  │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                                        [Generuj propozycje  Ctrl+G]
```

- **Pasek kolorów** to własny widżet (QTabBar nie ma wielokrotnego zaznaczenia): przyciski z próbką bieżącej
  wartości koloru i nazwą. Klik = jeden kolor; Ctrl+klik = dołóż/odejmij; Shift+klik = zakres; „wszystkie
  akcenty” = wszystkie akcenty naraz. „cała paleta” wyklucza się z zaznaczeniem kolorów. Obsługa z klawiatury
  (strzałki, spacja/Ctrl+spacja) obowiązkowa.
- **Edycja zbiorcza**: wiersz zasady pojawia się, gdy zasada dotyczy wszystkich zaznaczonych kolorów (przy tło +
  akcent nie ma „kontrastu z tłem” ani zasad tylko-akcentowych). Gdy wartości są zgodne, wiersz wygląda jak przy
  jednym kolorze. Gdy się różnią (wartość, włączenie, twardość, waga albo sama obecność), wiersz pokazuje „różne”
  z wartością każdego koloru i dwa działania: ustaw dla wszystkich zaznaczonych (otwiera edycję z wartością
  pierwszego zaznaczonego), usuń u wszystkich. Każda zmiana zbiorcza to jeden krok cofania. Zależności edytuje
  się tylko przy jednym zaznaczonym kolorze.
- **Wiersz zasady**: nazwa, włączona, twarda, waga, edytor wartości, „✕ usuń”; gdy zasady nie ma: „+ dodaj”.
  Jedno słowo: **usuń**. Znikają plakietki źródeł i legenda „nastrój/globalne/własne”.
- **Zakazy** (jasność, nasycenie, odcień): pod suwakiem lista pozycji „od–do ✕” z polami liczbowymi i „+ zakaz”;
  na pasku suwaka zakazane odcinki są widoczne (kreskowanie albo przygaszenie). Dodanie, zmiana i usunięcie
  zakazu działają z klawiatury.
- **Odcień**: suwak zakresu na kole/pasku odcieni + pola „od”, „do” oraz „środek”, „± szerokość”; edycja jednej
  pary przelicza drugą. Wiersz „układ odcieni: ☑ stosuj → cel …” tylko dla akcentów, pokazuje wyliczony cel i
  prowadzi do sekcji układu w „całej palecie”.
- **„cała paleta”**: metryki (kontrast, ΔE, gamut), układ odcieni z wybierakiem własnej listy (§7.4), rozrzut
  jasności, daltonizm, unikane kolory, generowanie (dawny „Optymalizator”: liczba propozycji, ziarno, budżet,
  limit czasu, różnorodność, waga twardych, wątki). Polaryzacja siedzi w wierszu presetu.
- **Liczba kolorów**: „−” usuwa ostatni akcent, „+” dodaje (§7.1). Cofalne, bez pytania.
- **Preset** (§8): wyszukiwarka + kategoria + lista; „Zastosuj” zastępuje zasady wszystkich kolorów, układ
  odcieni i rozrzut jasności. Oznaczenie „(zmieniony)”, gdy bieżące zasady różnią się od świeżo nałożonego
  presetu. Zmiana polaryzacji: preset niezmieniony → nakładany ponownie dla nowej polaryzacji; zmieniony albo
  brak presetu → pytanie z trzema wyjściami: zastąp zasady presetem dla nowej polaryzacji / zmień tylko
  oznaczenie polaryzacji / anuluj. Zmiana metryki kontrastu i metody ΔE przelicza progi jak dziś (`units.py`).
- „Generuj propozycje” na dole panelu uruchamia generowanie i przechodzi do Propozycji.

### 7.4 Wybierak listy

Jeden widżet w dwóch trybach:
- **odcienie** (własna lista układu odcieni): koło odcieni OKLCH (rysowanie jak w Analizie); klik albo
  przeciągnięcie dodaje/ustawia odcień; lista pozycji z próbką i stopniami; usuwanie, zmiana kolejności
  (przeciąganie i klawisze), dokładne wpisanie liczby. Zastępuje pole tekstowe.
- **kolory** (lista unikanych kolorów w „całej palecie”): pełny kolor (koło odcieni + jasność + nasycenie albo
  wpisany hex/`oklch(...)`), ta sama lista. Dziś tę listę wypełnia tylko tryb „charakter” w Źródle i można ją
  jedynie wyczyścić. *To mój dodatek; do skreślenia, jeśli zbędny.*

### 7.5 Co zmienia się poza zakładką „Zasady”

- **Paleta**: z edytora koloru znikają warunki i zależności; zostaje nazwa, kłódka, wartość. Dochodzi odnośnik
  „Zasady tego koloru →” (otwiera Zasady z zaznaczonym tym kolorem). Dodawanie/usuwanie/przestawianie kolorów
  zostaje.
- **Panel naruszeń**: kliknięcie naruszenia prowadzi do zasady w zakładce „Zasady”.
- **Źródło**: trzy tryby zapisują zasady w nowym modelu. „Charakter”: zasady tła, tekstu i ten sam zestaw dla
  każdego akcentu (`use_scheme = True`, bez własnego odcienia) + układ „własna lista”. „Przeniesienie”: zasady
  per akcent (`use_scheme = False`). „Uzupełnianie”: bez zmian (kłódki i wartości).
- **Analiza**: łuk odcienia zaznaczonego koloru z zakazami; cele układu pobierane z silnika.
- **TUI**: usunięte (`src/algopalette/tui/`, `tests/tui/`, flaga `--tui`, zależności `textual`,
  `pytest-asyncio`; `scipy` znika razem ze starym silnikiem).

### 7.6 Pomoc

- Tematy zakładki przepisane pod nowy model; znikają tematy o dziedziczeniu i źródłach wartości
  (`concept.sources`, `cond.reset`, `cond.badge`); dochodzą: pasek kolorów i edycja zbiorcza, zakazane przedziały,
  zasada odcienia, przełącznik układu, wybierak, presety, liczba kolorów, wątki, nowe znaczenie budżetu.
- **Wzorzec terminu**: (1) co to jest jednym zdaniem zwykłym językiem, (2) przykład z liczbami, (3) kiedy wybrać
  którą opcję. Obowiązuje co najmniej dla: nasycenie bezwzględne i względne; twarda/miękka/waga; każda metoda
  ΔE; WCAG i APCA; gamut i metody dopasowania; rodzaje układu odcieni, tolerancja, jitter; rozrzut jasności;
  metody i nasilenie symulacji daltonizmu; budżet, ziarno, różnorodność, waga twardych; zakazany przedział;
  każdy rodzaj zależności; skrajny kontrast. Tematy objęte wzorcem mają znacznik w `Topic`; test sprawdza, że
  każdy zawiera część „Przykład”.
- **Nasycenie względne i bezwzględne** (wzorzec jakości dla reszty): temat pokazuje dla jednej jasności, ile
  wynosi największe C kilku odcieni, co wtedy znaczy ten sam zakres bezwzględny dla każdego z nich i co znaczy
  ten sam procent; do tego rysunek: dwa rzędy próbek w kilkunastu odcieniach, górny przy stałym C bezwzględnym,
  dolny przy stałym C względnym, z podpisanymi liczbami. Liczby i rysunek liczone z silnika przy budowie treści,
  nie wpisywane z pamięci. Krótka podpowiedź przy liście trybów mówi to samo w dwóch zdaniach bez żargonu.
- Zasada z poprzedniego speca zostaje: pomoc opisuje głównie działanie programu, teorię koloru krótko. Test
  pokrycia całego okna (`uncovered(win) == []`) i osiągalności tematów zostaje zielony.

## 8. Presety

- „Nastrój” → „Preset” w interfejsie i kodzie (`moods.py` → `presets.py`).
- Preset wbudowany jest deklaratywny: nazwa, kategoria, opis, obsługiwane polaryzacje, szablony zasad dla tła,
  tekstu i akcentu, opcjonalne nadpisania dla konkretnych akcentów (np. „akcent 1: odcień 25–45, `use_scheme`
  wyłączone”), układ odcieni, rozrzut jasności, opcjonalnie `cvd` i `contrast_metric`. Funkcja
  `(preset, polaryzacja, metryka, liczba akcentów) → zasady`. Nałożenie zastępuje zasady wszystkich kolorów,
  `use_scheme`, układ odcieni i rozrzut; nie rusza wartości, kłódek, nazw, zależności, ustawień generowania,
  listy unikanych kolorów. Preset zmieniający metrykę przelicza progi zależności jak ręczna zmiana metryki.
- Presety użytkownika: zapis bieżących zasad wszystkich kolorów (wg pozycji) + układ + rozrzut + polaryzacja +
  metryka do `config_dir()/presets.json`. Nałożenie na paletę z większą liczbą akcentów powiela zasady
  ostatniego zapisanego akcentu.
- **Co najmniej 48 wbudowanych.** Lista wyjściowa (builder może zamienić pozycje, liczba i kategorie zostają):
  - Podstawowe: neutralny, stonowany, żywy, wysoki kontrast, niski kontrast, maksymalna rozróżnialność.
  - Chłodne: chłodny mglisty, arktyczny, głębia oceanu, stalowy, zimowy poranek, zorza.
  - Ciepłe: ziemisty, jesienny, pustynny, bursztynowy, ognisko, terakota.
  - Natura: leśny, mech i kamień, wiosenna łąka, lawendowe pole, tropikalny, morski brzeg.
  - Pastelowe: pastel, pudrowy, akwarela, cukierkowy, sorbet.
  - Świecące: neon, synthwave, cyberpunk, arcade, kwaśny.
  - Retro i druk: retro terminal, bursztynowy terminal, CRT, sepia, papier i atrament, gazeta.
  - Ograniczone: monochromatyczny z jednym akcentem, szarości z akcentem, duotone, jeden odcień wiele jasności,
    dwa bieguny.
  - Harmonie: dopełniający, rozszczepiony dopełniający, triada, tetrada, analogiczny.
  - Pory dnia: nocny wysoki kontrast, północ, świt, zmierzch, burza.
  - Dostępność: bezpieczny przy protanopii i deuteranopii, bezpieczny przy tritanopii, APCA do długiego czytania.
- Akceptacja presetu (test, znacznik `slow`): dla każdej obsługiwanej polaryzacji i obu metryk, przy 10 i przy 7
  kolorach, ustawienia domyślne dają co najmniej 5 z 6 propozycji bez twardych naruszeń; żadne dwa presety nie
  dają identycznego zestawu zasad; opis zgadza się z zasadami (ocenia przegląd).

## 9. Silnik natywny

### 9.1 Układ

- Przestrzeń robocza Cargo w repo: `crates/core` (czysty Rust, bez Pythona: kolor, zasady, funkcja celu,
  optymalizator, sterownik równoległy), `crates/py` (PyO3, moduł `algopalette._engine`, abi3), `crates/cli`
  (program `algopalette-bench` do benchmarków i uruchamiania silnika na pliku sesji bez GUI).
- Budowanie paczki: backend `maturin` zamiast `uv_build`. Nowe zależności (do zgłoszenia użytkownikowi w
  raporcie): budowanie `maturin`; Rust `pyo3`, `rayon`, `serde`, `serde_json` (+ ewentualne drobne, decyzja
  buildera). Generator liczb losowych własny, mały i zamrożony (wynik dla ziarna nie może się zmienić po
  aktualizacji zależności).
- Python zostawia: `model.py`, `io.py`, `color/` (hex, dopasowanie do gamutu, HSL, parsowanie; `fast.py` dla
  gradientów suwaków), `forms.py`, `presets.py`, `sources.py`, `units.py`, `globals_logic.py`, `pb_export.py`,
  `gui/`. `engine.py` staje się cienką nakładką na `_engine` (zachowuje `generate`/`Proposal`/`apply_proposal`
  w kształcie wygodnym dla GUI). Znikają `constraints.py`, `hues.py` i algorytm z `engine.py`.

### 9.2 Kontrakt danych

- Silnik przyjmuje sesję jako JSON w formacie pliku `algopalette.v2` (§10), jeden schemat dla pliku i silnika.
  Nakładka Pythona przed wywołaniem podmienia wartości kolorów stałych (kłódka albo spoza generowanego zbioru)
  na wartości po dopasowaniu do gamutu; silnik bierze je, jak są. Kolory wolne silnik zwraca w gamucie sRGB.
- Funkcje modułu `_engine` (nazwy do ustalenia w planie, zakres wiążący):
  - ocena: sesja → lista naruszeń (klucz, id kolorów, rodzaj, twardy, wielkość, wartość osiągnięta, wymaganie w
    postaci liczb, metadane typu metryka/typ CVD/tryb) + wartość funkcji celu. Teksty po polsku składa Python
    (`forms.py`); Rust nie zawiera napisów interfejsu.
  - generowanie: sesja + zbiór kolorów wolnych → uchwyt zadania: `poll()` (postęp 0–1, liczba gotowych
    kandydatów, stan), `cancel()`, `result()`. Zadanie działa na wątkach Rusta bez GIL; GUI odpytuje je
    zegarem Qt. Żadnych wątków Pythona.
  - cele układu odcieni: sesja → `{id: stopnie}`.
  - funkcje pomocnicze do testów i pomocy: ΔE, kontrast, symulacja CVD, największe C, informacja o kompilacji
    (profil release/debug).
  - błąd schematu → wyjątek Pythona ze ścieżką w JSON.
- Naruszenie „różnorodność” i znacznik przerwania limitem czasu zostają w wyniku jak dziś.

### 9.3 Matematyka koloru (dokładna, bez przybliżeń kalibrowanych)

OKLCH/OKLab/linear sRGB, największe C w sRGB dla (L, H), kontrast WCAG 2.1 i APCA 0.0.98G-4g (stałe z
`color/apca.py`), ΔE `ok`, `hyab` (w OKLab, jak `fast.py`), `2000`, `itp`, `cam16`, symulacja CVD
Brettel/Viénot/Machado z nasileniem. Wyrocznią jest dzisiejszy kod: `color/__init__.py` (coloraide) i
`color/fast.py`. Zgodność: ≤ 1e-9 dla przekształceń i kontrastu, ≤ 1e-6 dla ΔE `ok`/`hyab` i CVD, ≤ 1e-4 dla
ΔE `2000`/`itp`/`cam16` (skala ~0–100), na losowych kolorach w gamucie i na brzegach (C = 0, L = 0/1).

### 9.4 Optymalizacja

- Funkcja celu bez zmian: Σ waga · (naruszenie / skala)², twarde × `hard_weight`, margines twardych 0,5 × skala
  w trakcie optymalizacji; ocena końcowa bez marginesu.
- Zmienne koloru wolnego i twarde zakresy jako granice zmiennych: jak dziś (L, nasycenie względne, odcień;
  decyzja o parametryzacji należy do buildera, warunek: wynik zawsze w gamucie).
- **Gradient dokładny** (ręczny albo różniczkowanie automatyczne), sprawdzony testem względem różnic skończonych
  dla każdego rodzaju termu. Optymalizator z ograniczeniami pudełkowymi (quasi-Newton) własny albo z biblioteki.
- Starty: losowanie w granicach, poza zakazanymi przedziałami, odcień w pobliżu celu układu (jak dziś).
- **Budżet** = największa liczba ocen funkcji z gradientem na jeden przebieg (jeden kandydat). Przebieg kończy
  się wcześniej przy zbieżności. Domyślnie wartość dobrana pomiarem (punkt wyjścia: 3 000).
- **Sterownik równoległy**: fala niezależnych przebiegów (więcej niż N), każdy z własnym strumieniem losowym
  wyznaczonym przez (ziarno, numer przebiegu) → wybór N propozycji: najpierw bez twardych naruszeń, potem wg
  wyniku, zachłannie z warunkiem minimalnej różnorodności (średnie ΔE ok między odpowiadającymi sobie kolorami
  wolnymi ≥ `min_diversity`, definicja jak dziś). Gdy brakuje różnorodnych: kolejne fale z karą odpychającą od
  już wybranych (najwyżej kilka fal), potem dopełnienie najlepszymi pozostałymi z miękkim naruszeniem
  „różnorodność”. Kolejność wyniku: bez twardych naruszeń najpierw, potem rosnąco wg wyniku.
- **Determinizm**: ta sama sesja i ziarno → identyczny wynik niezależnie od liczby wątków i kolejności
  zakończenia przebiegów (remisy rozstrzyga numer przebiegu). Limit czasu pozostaje bezpiecznikiem: po jego
  zadziałaniu wszystkie propozycje tej generacji są oznaczone jako niepowtarzalne.
- Przerwanie: zadanie reaguje w ≤ 100 ms i zwraca to, co wybrano z ukończonych przebiegów.
- Skutek dla użytkownika: to samo ziarno daje inne palety niż stary silnik (uprzedzony).

### 9.5 Wzorzec zachowania i jakości (zanim stary silnik zniknie)

Pierwszy krok implementacji zapisuje do repo dane wzorcowe ze starego kodu:
- **Zgodność oceny**: kilkaset losowych sesji v1 (wszystkie rodzaje warunków i zależności, układy, metryki, CVD,
  kłódki) z paletami → lista naruszeń (klucz, twardy, wielkość) i wartość funkcji celu wg `constraints.evaluate`.
  Test nowego kodu: wczytaj sesję v1 → migracja do v2 (§10) → ocena natywna → te same naruszenia (klucze
  `hue_range`/`hue_target` odwzorowane na `hue`), wielkości z tolerancjami z §9.3. Generator nie włącza naraz
  zakresu i celu odcienia (jedyny przypadek, w którym v2 celowo różni się liczbą termów).
- **Jakość**: 9 dawnych nastrojów × 2 polaryzacje × 2 metryki, 6 propozycji, budżet 30 000: liczba propozycji
  bez twardych naruszeń i najlepszy wynik. Dane wzorcowe zawierają **pełne sesje v1 z już nałożonym nastrojem**,
  więc test nie zależy od definicji nowych presetów: wczytuje sesję v1, migruje ją i generuje. Nowy silnik przy
  domyślnym budżecie: liczba ≥ wzorcowej, najlepszy wynik ≤ wzorcowy × 1,05 (ta sama funkcja celu, liczona
  oceną natywną bez marginesu).
- **Dziewięć dawnych nastrojów zostaje presetami o niezmienionych zasadach** (te same nazwy): test sprawdza, że
  nałożenie takiego presetu na sesję startową daje te same zasady co migracja sesji v1 z tym nastrojem (ta
  sama polaryzacja, metryka, 10 kolorów). Strojenie liczb w S1 dotyczy tylko nowych presetów.

### 9.6 Cele wydajności (ta maszyna, 16 wątków, kompilacja release; mierzone `algopalette-bench`)

- W1: sesja startowa, 6 propozycji: ≤ 0,15 s.
- W2: preset „chłodny mglisty”, 10 kolorów, 128 propozycji: **≤ 2 s**, co najmniej 120 bez twardych naruszeń
  (dziś ≥ 4 min). Liczą się tylko naruszenia twarde: miękkie naruszenie „różnorodność” jest dozwolone, bo przy
  wąskich zasadach 128 wzajemnie różnych palet może nie istnieć. Sterownik ma stałą, małą liczbę fal (nie szuka
  różnorodności „do skutku”); pomiar podaje też, ile propozycji ma naruszenie „różnorodność”.
- W3: 16 kolorów, dwa typy CVD, ΔE 2000, 128 propozycji: ≤ 6 s.
- W4: ocena naruszeń na żywo (16 kolorów, komplet zasad): ≤ 1 ms z Pythona.
- Test w pytest (znacznik `slow`) z luźniejszym progiem (W2 ≤ 6 s), żeby nie migotał; dokładne liczby trafiają
  do handoffu. **Niedotrzymany cel zgłaszam z liczbami i profilem; nie obniżam progu po cichu.**
- Launcher zawsze uruchamia kompilację release (sprawdzane przez informację o kompilacji).

## 10. Plik sesji v2 i migracja

- `format: "algopalette.v2"`. Układ jak v1 z różnicami: `preset` zamiast `mood`, brak `mood_snapshot`; `globals`
  bez `role_defaults`, `optimizer.budget` i `optimizer.threads`; slot ma `rules` (pola z §7.1, `null` = brak
  zasady; `exclude` jako lista par) i `use_scheme`; `hex` w slocie nadal informacyjny. Dokładny schemat (wspólny
  dla Pythona i Rusta) ustala plan jako pierwszy interfejs dzielony; test kontraktu: Python koduje sesje
  pokrywające każdy wariant, Rust je przyjmuje, nieznane pole w zasadach jest błędem.
- **Wczytanie v1** (plik, autozapis): każdy kolor dostaje zasady obowiązujące go w v1 (własne albo roli);
  `use_scheme = False` dokładnie wtedy, gdy kolor miał w v1 jakikolwiek warunek odcienia (zachowuje dawne
  zachowanie); `mood` → `preset` o tej samej nazwie, jeśli istnieje; `max_evals` → `budget` wg przelicznika
  ustalonego pomiarem (punkt wyjścia: ÷ 10, w granicach 300–100 000). Zapis zawsze v2. Zmigrowany autozapis
  zostawia kopię `last.v1.json`.
- **Scalanie odcienia z v1** (v1 pozwalał mieć naraz `hue_range` i `hue_target`, każdy z własnym
  włączeniem/twardością/wagą; v2 ma jeden łuk). Moja decyzja:
  - jest tylko jeden z nich → staje się zasadą odcienia ze swoimi flagami (`hue_target` jako łuk `cel ± tol`);
  - są oba, włączony dokładnie jeden → zostaje włączony, wyłączony przepada;
  - są oba wyłączone → zostaje zakres (wyłączony);
  - są oba włączone i część wspólna jest jednym łukiem → zasada = część wspólna, twarda, jeśli którykolwiek był
    twardy, waga = większa z dwóch („wygrywa ostrzejszy”);
  - są oba włączone, a część wspólna jest pusta albo składa się z dwóch łuków → zostaje zakres ze swoimi
    flagami, cel przepada.
  W każdym przypadku, w którym coś przepada albo zmienia twardość, użytkownik dostaje po wczytaniu komunikat z
  listą kolorów, których to dotyczy (migracja nigdy nie jest cicha).
- `moods.json` użytkownika → `presets.json` przy pierwszym uruchomieniu (stary plik zostaje). Nastrój v1 trzyma
  warunki ról; preset użytkownika v2 trzyma zasady wg pozycji, więc konwersja zapisuje: tło, tekst i **jeden**
  akcent (z warunków roli „akcent”; przy nakładaniu jest powielany na wszystkie akcenty, §8), `use_scheme` wg
  reguły wyżej, układ odcieni, rozrzut, polaryzację i metrykę nastroju.

## 11. Podział pracy (pod plan i subagentów)

Krok 0 jest sekwencyjny i ustala kontrakty; potem tory są rozłączne plikami.
- **K0** (kontroler): dane wzorcowe ze starego silnika (§9.5); schemat v2; model v2 w Pythonie; rusztowanie
  Cargo + maturin z jedną funkcją próbną i sprawdzeniem ścieżki instalacji launchera; usunięcie TUI.
- **R1** matematyka koloru w Rust + testy z wyrocznią. **R2** kompilator zasad, funkcja celu, gradienty, ocena.
  **R3** optymalizator, sterownik równoległy, zadanie z postępem i przerwaniem, PyO3, `algopalette-bench`.
  R2 i R3 zależą od sygnatur R1 ustalonych w planie, nie od jego ukończenia.
- **P1** `io.py` v2 + migracja v1. **P2** `sources.py`, `units.py`, `globals_logic.py` pod nowy model.
- **G1** widżety: suwak z zakazami, wybierak listy, pasek kolorów z wielokrotnym zaznaczeniem. **G2** zakładka
  „Zasady” (wiersze zasad, edycja zbiorcza, zależności, preset, liczba kolorów) + zmiany w Palecie, panelu
  naruszeń, Analizie.
- **H1** treść pomocy. **S1** presety (deklaracje; strojenie liczb po R3).
- **Integracja** (kontroler): nakładka `engine.py`, Propozycje na odpytywaniu zadania, usunięcie starego
  silnika, benchmarki, README, handoff, launcher.

## 12. Ryzyka i reguły decyzji

- **Instalacja edytowalna z maturin**: launcher to `uv tool install --editable .`. Jeśli edytowalna instalacja z
  rozszerzeniem natywnym nie zadziała pod `uv tool`, K0 przechodzi na instalację zwykłą + jedno polecenie
  przebudowy i zgłasza to użytkownikowi. Katalog główny zostaje na `main` do scalenia, więc launcher działa
  przez cały czas pracy; po scaleniu jednorazowa reinstalacja.
- **Zgodność ΔE `itp`/`cam16` z coloraide** zależy od warunków obserwacji przyjętych przez coloraide; test z
  wyrocznią rozstrzyga, nie dokumentacja.
- **Gradient przy granicy gamutu** (największe C nie jest gładkie w punkcie zmiany kanału ograniczającego):
  builder wybiera sposób (pochodna niejawna, tablica, lokalna różnica tylko dla tej jednej funkcji); kryterium
  to test jakości z §9.5, nie elegancja.
- Polecenia na pierwszym planie ≤ 20 s (kompilacje i pełne testy w tle).

## 13. Co zostaje dla buildera

Nazwy klas i funkcji, układ modułów GUI, wygląd zakazów na suwaku, interakcje wybieraka, dokładne liczby presetów,
parametryzacja zmiennych i algorytm wewnątrz optymalizatora, liczba fal i nadmiar przebiegów, przelicznik budżetu,
domyślny budżet, sposób rysowania rysunku w pomocy, wersje zależności.

## 14. Otwarte (do decyzji użytkownika po akceptacji speca)

- Zasady przeglądu kodu dla tej pracy (użytkownik: „o to mnie zapytaj po napisaniu specyfikacji”).
