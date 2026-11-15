"""Pomoc: pojęcia — krótko i praktycznie, z odnośnikiem do miejsca w programie."""

from algopalette.gui.help_content.topic import Topic

G = "Pojęcia"

TOPICS: dict[str, Topic] = {
    "concept.oklch": Topic(
        "OKLCH — jasność, nasycenie, odcień",
        "Przestrzeń, w której program liczy wszystko: L = jasność 0–1, C = nasycenie, H = odcień w "
        "stopniach. Ta sama zmiana liczby daje podobną zmianę na oko.",
        """Każdy kolor w AlgoPalette to trzy liczby OKLCH:

- **L** — jasność, 0 = czerń, 1 = biel;
- **C** — nasycenie, 0 = szarość; praktycznie do ok. 0.37, a największe możliwe C zależy od L i H;
- **H** — odcień w stopniach na kole (0–360°).

Program używa OKLCH, bo jest percepcyjnie równa: dwa kolory o tym samym L wyglądają na równie jasne,
czego nie gwarantuje HSL. Dlatego warunki, silnik i Analiza zawsze liczą w OKLCH. Widok HSL (F7) zmienia
tylko sposób wyświetlania i edycji wartości koloru. Hex sRGB powstaje dopiero na końcu, przy zapisie
i eksporcie. Zobacz też: [gamut](help:concept.gamut).""",
        G,
    ),
    "concept.delta_e": Topic(
        "ΔE — odległość kolorów",
        "Liczba mówiąca, jak bardzo dwa kolory różnią się na oko. Warunki odległości i odróżnialności "
        "porównują ją z progiem.",
        """ΔE to odległość między dwoma kolorami: 0 oznacza identyczne kolory, im więcej, tym łatwiej je
odróżnić. Warunki „odległość od akcentów” i „odróżnialność (daltonizm)” wymagają, żeby ΔE nie spadło
poniżej progu. Macierz ΔE w Analizie pokazuje odległości wszystkich par akcentów.

**Skala zależy od metody** (Globalne → metoda ΔE): `ok` i `hyab` mają skalę ok. 0–1 (0.08 to wyraźna
różnica), `2000`, `itp` i `cam16` — ok. 0–100. Przy zmianie metody program przelicza progi
przybliżonym przelicznikiem, więc sprawdź je potem, jeśli zależy ci na dokładnych wartościach.""",
        G,
    ),
    "concept.contrast": Topic(
        "Kontrast: WCAG 2.1 i APCA",
        "Miara czytelności tekstu na tle. WCAG 2.1 daje współczynnik 1–21, APCA — wartość |Lc| do ok. "
        "106; metodę wybierasz w Globalnych.",
        """Kontrast mówi, jak czytelny jest kolor na tle. Program zna dwie metryki (Globalne → metryka
kontrastu):

- **WCAG 2.1** — współczynnik od 1 do 21; 4.5 to próg dla zwykłego tekstu, 3 — dla dużego tekstu
  i grafiki;
- **APCA** — wartość |Lc| (do ok. 106); 60 to przyzwoity tekst, 75+ — tekst główny. Lepiej niż WCAG
  ocenia ciemne motywy, a te są typowe dla IDE.

Progi w warunkach „kontrast z tłem” i w zależnościach kontrastu są w jednostkach wybranej metryki.
Zmiana metryki przelicza domyślne zakresy ról.""",
        G,
    ),
    "concept.cvd": Topic(
        "Daltonizm (CVD)",
        "Symulacja zaburzeń widzenia barw: program sprawdza, czy akcenty dalej się różnią dla osób "
        "z protanopią, deuteranopią albo tritanopią.",
        """Przy zaburzeniach widzenia barw (CVD) część par kolorów zlewa się w jeden. W Globalnych wybierasz,
które typy uwzględnić (protanopia — czerwień, deuteranopia — zieleń, tritanopia — błękit), metodę
symulacji (Machado, Viénot, Brettel) i nasilenie. Wtedy warunek „odróżnialność (daltonizm)” wymaga
minimalnej ΔE między akcentami także po symulacji. W Analizie możesz obejrzeć paletę i macierze tak,
jak widzi je osoba z danym typem CVD.""",
        G,
    ),
    "concept.gamut": Topic(
        "Gamut sRGB i dopasowanie",
        "Nie każdy kolor OKLCH da się wyświetlić w sRGB. Kolor spoza zakresu zostaje ściągnięty do "
        "najbliższego możliwego wybraną metodą (fit).",
        """Monitor w sRGB pokazuje tylko część kolorów OKLCH — szczególnie mocno nasyconych przy bardzo jasnych
albo bardzo ciemnych L. Silnik generuje kolory zawsze mieszczące się w sRGB, ale wartość wpisaną ręcznie
albo wklejoną da się wyprowadzić poza zakres.

Taki kolor zostaje „dopasowany” metodą z Globalnych (domyślnie `oklch-chroma` — obniża nasycenie,
zachowując jasność i odcień). Hex, naruszenia, Analiza i eksport używają koloru **po** dopasowaniu.
Na liście kolorów hex takiego koloru jest wyróżniony, a podpowiedź mówi, o ile ΔE go przesunięto.
Nasycenie **względne** w warunkach to ułamek największego C możliwego w sRGB przy danych L i H.""",
        G,
    ),
    "concept.hard_soft": Topic(
        "Warunki twarde i miękkie",
        "Twardy warunek musi być spełniony — wynik, który go łamie, jest oznaczony ✗. Miękki to cel "
        "z wagą: silnik zbliża się do niego, ile się da.",
        """Każdy warunek i każdą zależność oznaczasz jako twardą albo miękką.

- **Twardy (✗ w panelu naruszeń)** — musi być spełniony. Zakresy jasności, odcienia i nasycenia
  względnego stają się granicami poszukiwań, pozostałe twarde warunki — wysoką karą. Propozycja, która mimo to
  łamie twardy warunek, dostaje oznaczenie „✗ łamie twarde”.
- **Miękki (~)** — cel z wagą. Silnik próbuje go spełnić, ale ustąpi, gdy koliduje z twardymi.
  Większa waga = ważniejszy cel względem innych miękkich.

Gdy warunki się wykluczają, program pokazuje, które są złamane i o ile, zamiast udawać sukces.
Wyłączony warunek (odznaczony) nie liczy się wcale.""",
        G,
    ),
    "concept.sources": Topic(
        "Źródło wartości: nastrój, globalne, własne",
        "Plakietka przy warunku mówi, skąd wzięła się wartość: z nastroju, z ustawień globalnych albo "
        "z tego koloru. ↺ wraca do wartości dziedziczonej.",
        """Warunki koloru dziedziczą się w trzech warstwach:

- **nastrój** — wartość ustawił wybrany nastrój;
- **globalne** — domyślny warunek roli (tło / tekst / akcent), którego nie ustawił bieżący nastrój:
  zmieniony ręcznie w Globalnych albo ustawiony bez nastroju (np. trybem charakter / przeniesienie,
  zmianą metryki); dotyczy wszystkich kolorów tej roli;
- **własne** — wartość zmieniona w tym jednym kolorze; nadpisuje globalne.

Przycisk **↺ dziedzicz** (w edytorze koloru) usuwa własną wartość, więc kolor znów bierze ją
z Globalnych. Wybór nastroju ustawia na nowo wszystkie domyślne warunki ról — także te zmienione ręcznie
w Globalnych (Ctrl+Z je przywraca) — ale nie rusza wartości własnych kolorów.""",
        G,
    ),
}
