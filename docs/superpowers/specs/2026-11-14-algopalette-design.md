# AlgoPalette — projekt (spec)

Data: 2026-11-14. Status: projekt do akceptacji użytkownika.

## 1. Intencja i „dlaczego”

Użytkownik projektuje motywy IDE w PaletteBuilderze (`/home/qrikk/palettebuilder`, aplikacja webowa). Jego okno
„Generuj…” jest za ciasne i za ubogie. Słowa użytkownika: „w palettebuilderze jest zwyczajnie za malo miejsca na to
narzedzie. mozesz zrobic osobna apke ktora bedzie skladala sie wylacznie z 'podpowiadacza kolorow'. poza tym tam
konfiguracja jest minimalna - ot, kontrast, jak bardzo kolory majka odbiegac od palety lub jak jaskrawe maja byc.
nie ma kontroli nad pojedynczym kolorem etc”.

AlgoPalette to **osobny program w Pythonie z interfejsem TUI**, który robi wyłącznie jedno: generuje palety kolorów
pod motywy IDE. Rachunek prowadzi w OKLCH, a na hex przelicza dopiero na końcu. Ma mieć jak najwięcej ustawień.
Użytkownik: „wole cos trudniejszego w obsludze niz cos dla 10latka”, „zalezy mi na jak najwiekszych mozliwosciach
konfiguracji”, „uv add od-chuja-color-pakietów, im dokladniejsze i ciekawsze tym lepiej”.

**Dwa niezależne programy, przepływ w jedną stronę.** Decyzja użytkownika (WIĄŻĄCA): „to maja byc dwa niezalezne
programy z DODATKOWA funkcjonalnoscia przenoszenia palety z algopalette bezposrednio do plettebuilder. w druga strone
nigdy. nie skupiaj sie tak na tym.” AlgoPalette nie czyta plików PaletteBuildera i nie zna jego ról tokenów. Integracja
z PB to jedna dodatkowa akcja eksportu (§9). Własne pliki AlgoPalette służą „do samodzielnego eksperymentowania
pozniej”.

## 2. Cele, nie-cele, anty-cele

**Cele**
- Cała matematyka koloru w OKLCH/OKLab. Hex sRGB powstaje tylko na wyjściu.
- Sterowanie na trzech poziomach: nastrój → ustawienia całej palety → każdy kolor z osobna (zakresy + zależności).
- Trzy tryby startu z istniejącej palety: uzupełnianie, charakter, przeniesienie (§6).
- Uczciwy raport niespełnialności, czyli które warunki są złamane i o ile. Nigdy ciche łamanie warunków.
- Wiele propozycji naraz. Z propozycji można przejąć całą paletę albo pojedynczy kolor.
- Własny plik sesji AlgoPalette (pełny stan) + osobna akcja „przenieś do PaletteBuildera” (§9).

**Nie-cele**
- Eksport do IDE, mapowanie tokenów, role tokenów, motywy UI. To robi PaletteBuilder.
- **Czytanie czegokolwiek z PaletteBuildera** (plików `~/Dokumenty/motifs`, formatów `palettebuilder.*`). „w druga
  strone nigdy”.
- Zmiany w PaletteBuilderze, w tym automatyczne otwieranie go z plikiem.

**Anty-cele (porażka, nawet jeśli „działa”)**
- **Podgląd kodu.** Decyzja użytkownika (WIĄŻĄCA): „podglad kodu jest calkowicie niepotrzebny. to ma byc program do
  palet, a nie drugi IDE-owy palettebuilder”. Żadnych próbek kodu, lekserów ani podświetlania składni.
- Rachunek „na ślepo” w RGB/HSL (np. losowanie kanałów RGB, odległości w RGB).
- Uproszczony kreator „krok po kroku”, który chowa ustawienia.
- Program, który przy sprzecznych warunkach po cichu zwraca coś, co ich nie spełnia, i nic nie mówi.

## 3. Ograniczenia i środowisko

- Python ≥ 3.13 (system: 3.14.7), projekt `uv` w `/home/qrikk/algopalette`. Nazwa paczki i komendy: `algopalette`.
- Każdy plik `.py`: `ruff check --fix`, `ruff format`, `ty check` bez uwag (AGENTS.md użytkownika).
- Terminal użytkownika: Ghostty, `COLORTERM=truecolor`, więc próbki rysujemy w 24-bit, bez przybliżeń do 256 kolorów.
- Interfejs po polsku.
- Zależności (sprawdzone 2026-11-14 w środowisku jednorazowym):
  - `textual` 8.2.8: TUI.
  - `coloraide` 8.15: przestrzenie OKLCH/OKLab, `fit()` z metodami `clip`, `minde-chroma`, `lch-chroma`,
    `oklch-chroma`, `raytrace`, `scale`; `contrast()` z metodami `wcag21`, `lstar`; `delta_e()` z metodami `ok`,
    `2000`, `hyab`, `itp`, `cam16`; filtry daltonizmu `protan`/`deutan`/`tritan` metodami `brettel`/`vienot`/`machado`;
    `harmony()`. **APCA NIE jest w coloraide ani w `coloraide-extras`** (sprawdzone). Na PyPI nie ma też paczek
    `apca`/`apca-w3`/`pyapca`.
  - `scipy` 1.18 + `numpy`: optymalizacja.
  - Builder może dołożyć inne paczki, jeśli poprawiają jakość (decyzja użytkownika z CLAUDE.md: zależności nie są
    problemem, ale nowe trzeba zgłosić w raporcie).
- **APCA implementujemy sami** jako wtyczkę kontrastu coloraide (`Color.register`) wg SAPC-APCA 0.0.98G-4g.
  Testy wektorami z README apca-w3: tekst `#888888` na tle `#ffffff` → Lc ≈ 63.06; `#ffffff` na `#888888` → ≈ −68.54;
  `#000000` na `#aaaaaa` → ≈ 58.15; `#aaaaaa` na `#000000` → ≈ −56.24 (tolerancja 0.1). W warunkach używamy |Lc|.
  Kolejność argumentów ma znaczenie: tekst = akcent, tło = slot tła.

## 4. Podejścia (wybór dokonany)

Jak program szuka kolorów spełniających warunki:
- **A — losowanie i odsiew.** Proste i szybkie przy luźnych warunkach. Przy wielu ciasnych, powiązanych warunkach
  (np. 10 akcentów z minimalną odległością w każdej parze + zależności) często nie znajduje nic.
- **B — optymalizacja całej palety naraz** (funkcja kary za naruszenia, wszystkie wolne kolory przesuwane jednocześnie).
  Radzi sobie z ciasnymi i powiązanymi warunkami, naturalnie raportuje, co złamane i o ile, a różne starty dają różne
  propozycje. Kosztem jest większa złożoność. Czas to ułamki sekundy do kilku sekund.
- **C — solver na dyskretnej siatce** (np. CP-SAT). Potrafi dowieść niespełnialności, ale wymaga siatki, jest ciężki
  i mało elastyczny przy dodawaniu nowych rodzajów warunków.

**Wybrane: B, z losowaniem z A jako punktem startu** (użytkownik: „idziemy w B”). Uzasadnienie: największa swoboda
w dokładaniu warunków i uczciwy raport sprzeczności.

Interfejs: Textual. Kolor: coloraide. Bez realnej alternatywy, decyzja agenta zaakceptowana bez sprzeciwu.

## 5. Model palety i warunków

### 5.1 Sloty
Paleta to uporządkowana lista slotów: **slot 0 = tło, slot 1 = tekst, sloty 2… = akcenty**. Liczba akcentów 1–14,
domyślnie 8. Górna granica wynika z tego, że PB mieści najwyżej 16 kolorów i nadmiar scala. Kolejność slotów można
zmieniać.

Każdy slot ma: nazwę własną (opcjonalną, np. „komentarz”, wyłącznie dla użytkownika), kłódkę, bieżącą wartość OKLCH
(wyliczony hex), zestaw warunków (§5.2) i listę zależności (§5.3). **Żadnych podpisów ról tokenów PB** (usunięte po
decyzji użytkownika z §1).

### 5.2 Warunki slotu (zakresy)
Każdy warunek jest osobno włączany. Ma tryb **twardy** (musi być spełniony, raportowany jako błąd) albo **miękki**
(cel z wagą). Niezdefiniowane pole slotu **dziedziczy** wartość z ustawień globalnych (§5.4). UI pokazuje źródło każdej
wartości (nastrój / globalne / własne slotu) i pozwala wrócić do dziedziczenia.

- **Odcień H**: zakres `[od, do]` z zawijaniem przez 0° (np. 330–20), albo cel ± tolerancja.
- **Nasycenie C**: zakres bezwzględny (0–0.37) **albo względny**, jako % maksymalnego C osiągalnego w sRGB przy
  danych L i H. Względny jest ważny, bo „średnio nasycony” żółty i niebieski to bardzo różne liczby bezwzględne.
- **Jasność L**: zakres (UI w %, 0–100).
- **Kontrast z tłem**: minimum i opcjonalnie maksimum. Metryka globalna (WCAG 2.1 ratio albo APCA |Lc|), slot może ją
  nadpisać.
- **Odległość od innych akcentów**: minimum ΔE (metoda globalna), liczone do każdego innego akcentu.
- **Odróżnialność przy daltonizmie**: minimum ΔE po symulacji dla każdego włączonego typu (§5.4).
- **Kłódka**: wartość stała. Slot dalej bierze udział w warunkach innych slotów.
- **Najsłabszy/najmocniejszy**: opcjonalnie „ten akcent ma najniższy (najwyższy) kontrast z tłem spośród akcentów”
  (np. pod kolor komentarzy).

Tło i tekst to sloty jak inne. Dla tła sensowne są zakresy L i C („zabarwienie”) oraz odcień zabarwienia. Dla tekstu
liczy się kontrast z tłem.

### 5.3 Zależności slotu (relacje do innych slotów)
Lista relacji. Każda relacja: slot docelowy X, właściwość, operator (`=`/`≈` z tolerancją, `≥`, `≤`), wartość,
twarda/miękka + waga.
- **H**: `H_self − H_X` (najkrótszy łuk, −180…180) op Δ, np. „przeciwny do X” = 180 ± 15°.
- **L**: `L_self − L_X` op Δ, np. „ciemniejszy od X o ≥ 0.10”.
- **C**: `C_self` op `k·C_X` albo `C_X + Δ` (także w trybie względnym).
- **Kontrast**: `contrast(self, X)` op v (metryka globalna lub własna relacji).
- **Odległość**: `ΔE(self, X)` op v (np. „podobny do X, ale nie identyczny”: 0.03 ≤ ΔE ≤ 0.08).
- **Mieszanka**: `self ≈ mix(X, Y, t)` w OKLab, tolerancja ΔE.

Zależności mogą tworzyć cykle. Silnik B je obsługuje, bo wszystko jest jedną funkcją kary. Relacja do slotu usuniętego
zostaje oznaczona jako zerwana (widoczna w UI), a nie po cichu usunięta.

### 5.4 Ustawienia całej palety (globalne)
- **Polaryzacja**: ciemne/jasne. Zakłada domyślne zakresy dla tła i tekstu.
- **Tło**: skróty do warunków slotu 0 (L, zabarwienie C, odcień zabarwienia).
- **Domyślne zakresy akcentów**: L, C (bezwzględny/względny), rozrzut L między akcentami.
- **Układ odcieni** (wytwarza miękkie cele H dla akcentów bez własnego H): równo po kole (z obrotem), analogiczny
  (środek + rozpiętość), dopełniający, rozszczepiony dopełniający, triada, tetrada, własna lista odcieni docelowych.
  Do tego tolerancja i „jitter”. Dla akcentów > liczby odcieni układu kolejne biorą odcienie cyklicznie z przesunięciem.
- **Metryka kontrastu**: WCAG 2.1 / APCA. Domyślne minimum kontrastu akcent–tło i tekst–tło.
- **Metryka odległości ΔE**: `ok` (domyślna), `2000`, `hyab`, `itp`, `cam16`. Domyślne minimum odległości akcentów.
- **Daltonizm**: włączane protanopia/deuteranopia/tritanopia, metoda (`brettel`/`vienot`/`machado`), nasilenie 0–1,
  minimum ΔE po symulacji.
- **Gamut**: cel sRGB (hex). Optymalizator karze wyjście poza gamut, więc wynik zwykle już w nim jest. Metoda `fit()`
  (lista z §3, domyślnie `oklch-chroma` lub `raytrace`, do wyboru buildera) dotyczy przypadków, gdy wartość spoza gamutu
  jest wymuszona (kłódka na OKLCH spoza sRGB, import). UI pokazuje, że kolor został „ściągnięty”, i o ile ΔE.
- **Optymalizator**: liczba propozycji (domyślnie 6), ziarno losowe (pokazywane, edytowalne, zapisywane), budżet czasu,
  minimalna różnorodność między propozycjami (ΔE między odpowiadającymi sobie slotami), wagi twarde/miękkie.

### 5.5 Nastroje
Nastrój to **nazwany zestaw wartości ustawień globalnych** (opcjonalnie też domyślnych warunków slotów według roli
**strukturalnej**: tło / tekst / akcent; decyzja agenta po builder-check).
Wybranie nastroju wypełnia ustawienia, a użytkownik dalej je zmienia. Nic nie działa w ukryciu. Wbudowane (dokładne
liczby to decyzja buildera, muszą odpowiadać nazwie): chłodny mglisty, neon, ziemisty, pastel, nocny wysoki kontrast,
monochromatyczny z jednym akcentem, retro terminal, jesienny, plus „neutralny” jako domyślny. Własne nastroje
zapisywane/usuwane z poziomu TUI w `~/.config/algopalette/moods.json` (lub `.toml`, wybór buildera).

## 6. Paleta wyjściowa — trzy tryby

Źródło: plik sesji AlgoPalette albo wklejona lista kolorów (hex, a także zapis `oklch(...)`; dowolne separatory).
Przy liście użytkownik wskazuje, który kolor jest tłem i który tekstem (domyślnie pierwszy i drugi). **Nie czytamy
plików PaletteBuildera** (§1).

Wszystkie trzy tryby **tylko wypełniają warunki** z §5. Silnik jest jeden, a wynik trybu jest widoczny i edytowalny
jak każde inne ustawienie.
1. **Uzupełnianie**: podane kolory trafiają do kolejnych slotów z kłódką. Pozostałe sloty są generowane.
2. **Charakter**: z palety źródłowej powstaje profil: dominujące odcienie (klastrowanie H ważone C), rozkład C
   (względnego) i L akcentów, zabarwienie tła, poziomy kontrastu. Profil ustawia globalne ustawienia (własna lista
   odcieni, zakresy). Opcja „unikaj kolorów źródła” to minimum ΔE od każdego koloru źródła.
3. **Przeniesienie**: nowe tło (inna polaryzacja/zakres L tła). Każdy akcent dostaje relacje: H ≈ H źródła, kontrast
   z nowym tłem ≈ kontrast źródła ze starym tłem (ta sama metryka), C względne ≈ C względne źródła. Tekst analogicznie.

## 7. Silnik (B)

- Zmienne: wartości wolnych slotów. Reprezentacja to decyzja buildera (np. OKLab a/b + L, żeby uniknąć osobliwości
  odcienia przy C≈0). Warunki H muszą poprawnie obsługiwać zawijanie i pomijać H, gdy C jest bliskie 0.
- Funkcja celu: Σ wag × naruszeń² (twarde z dużą wagą, miękkie z wagą użytkownika) + kara za wyjście poza gamut.
- Algorytm: wiele startów z losowania w zakresach (A), potem lokalna/globalna optymalizacja (scipy, np.
  `differential_evolution`, `minimize`, wybór buildera). N propozycji o zadanej minimalnej różnorodności.
- Determinizm (decyzja agenta po builder-check): budżet optymalizatora liczony w **ewaluacjach/iteracjach**, nie w
  czasie, więc te same ustawienia + ziarno → te same propozycje niezależnie od maszyny i wątku/procesu. Czas zegarowy
  to tylko bezpiecznik. Gdy zadziała, propozycja jest oznaczona „przerwane limitem czasu, niepowtarzalne”.
- Praca w tle (worker Textual: wątek lub proces). UI się nie zamraża, generowanie można przerwać, postęp jest widoczny.
- Wynik propozycji: kolory OKLCH + hex, wynik funkcji celu, **lista naruszeń** (warunek, slot, wymagane vs osiągnięte).
  Propozycja z naruszeniami twardych warunków jest wyraźnie oznaczona. Wydajność: domyślne ustawienia (11 slotów,
  6 propozycji) poniżej ~3 s na typowym sprzęcie.
- Generowanie może dotyczyć całej palety albo tylko wybranych slotów (reszta traktowana jak zablokowana).

## 8. TUI

Gęsty, klawiaturowy interfejs z obsługą myszy. Każde pole liczbowe ma suwak i dokładne wpisywanie. Textual nie ma
natywnego suwaka zakresu, więc trzeba zrobić własny widget (`←/→`, z modyfikatorem drobny/gruby krok, przeciąganie
myszą). Ekrany/zakładki:

- **Paleta**: lista slotów (próbka truecolor, nazwa, hex, OKLCH, kłódka, kontrast z tłem, ΔE do najbliższego
  sąsiada) + edytor zaznaczonego slotu (warunki §5.2 ze źródłem wartości, zależności §5.3).
- **Globalne**: §5.4 + wybór/zapis nastroju §5.5.
- **Propozycje**: N wierszy próbek. Dla każdej wynik i liczba naruszeń. Akcje: przejmij całą, przejmij pojedynczy
  kolor do slotu.
- **Źródło**: wczytanie palety wyjściowej i wybór trybu §6.
- **Analiza** (zamiast podglądu kodu): koło odcieni z kolorami i zakresami H, wykres L–C (np. braille/półbloki),
  macierz par ΔE i kontrastu (normalnie i przy symulacji daltonizmu) z zaznaczeniem naruszeń, próbki „Aa”/bloki
  akcentów na tle.
- **Stały panel kontroli**: lista bieżących naruszeń, widoczna z każdej zakładki.
- Cofanie/ponawianie całego stanu (ustawienia + paleta), ekran pomocy z listą skrótów. Dokładne skróty to decyzja
  buildera.

## 9. Pliki

- **Plik sesji AlgoPalette**: własny format JSON (`format: "algopalette.v1"`): ustawienia globalne, nastrój, sloty
  z warunkami i zależnościami, wartości OKLCH + hex, ziarno, propozycje opcjonalnie. Domyślny katalog
  `~/.local/share/algopalette/palettes/` (decyzja agenta), nazwa od użytkownika. Wczytanie odtwarza całą sesję.
  Nadpisanie wymaga potwierdzenia.
- **„Przenieś do PaletteBuildera”**, jedyna akcja dotykająca PB, w jedną stronę. Wytwarza tekst JSON, który okno PB
  „Wczytaj…” przyjmuje wklejony (PB akceptuje wklejenie, plik i upuszczenie). Format: `format: "palettebuilder.v3"`,
  `polarity: "dark"|"light"`, `palette: [{hex, role: "bg"|"fg"|null}]` w kolejności slotów. Akcja (a) kopiuje go do
  schowka (OSC 52 przez `App.copy_to_clipboard` Textuala, Ghostty to obsługuje; opcjonalnie fallback `wl-copy`) i
  (b) opcjonalnie zapisuje plik do wskazanego katalogu (domyślnie `~/Dokumenty/motifs`). Builder **musi sprawdzić**,
  że PB faktycznie przyjmuje ten minimalny JSON (`motif()` w `/home/qrikk/palettebuilder/index.html:6236`; np. czy
  wymaga `lang`/`defaults`), uruchamiając logikę PB, a nie zgadując. PB pozostaje nietknięty.
- Autozapis ostatniej sesji (`~/.local/state/algopalette/`) i jej przywrócenie przy starcie.

## 10. Co zostaje dla buildera

Struktura modułów, reprezentacja zmiennych i algorytm wewnątrz B, dokładne liczby nastrojów, skróty klawiszowe, sposób
rysowania wykresów, format pliku nastrojów, domyślna metoda `fit()`. Testy: pytest dla koloru/APCA/warunków/silnika/IO
(w tym zgodność z PB), testy Textual `Pilot` dla podstawowych przepływów TUI. Instalacja komendy `algopalette`:
`uv tool install --editable .`.
