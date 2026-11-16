"""Pomoc: zakładka Analiza — koło odcieni, przekrój L–C, macierze, próbki, przełączniki widoku."""

from algopalette.gui.help_content.topic import Topic

A = "Analiza"

TOPICS: dict[str, Topic] = {
    "analysis.view": Topic(
        "Widok (normalny / daltonizm)",
        "Pokazuje wykresy, macierze i próbki tak, jak widzi je osoba z protanopią, deuteranopią albo "
        "tritanopią. Nie zmienia palety.",
        """Symulacja używa metody i nasilenia z ustawień całej palety → [daltonizm](help:rules.cvd).
W widoku daltonizmu macierz ΔE zaznacza na czerwono pary poniżej progu zasady
[odróżnialność](help:rules.cvd_min_distance), ale tylko dla typów zaznaczonych w tych ustawieniach —
dla pozostałych typów zasada nie działa, więc nic nie jest zaznaczane.""",
        A,
    ),
    "analysis.matrix_kind": Topic(
        "Rodzaj macierzy",
        "ΔE akcentów (jak bardzo się różnią) albo kontrast par akcentów (każdy akcent jako tekst na każdym "
        "jako tle).",
        """- [macierz ΔE](help:analysis.matrix.de) — szukasz akcentów zbyt do siebie podobnych;
- [macierz kontrastu](help:analysis.matrix.contrast) — sprawdzasz, które akcenty da się położyć na
  sobie nawzajem (np. tekst na tle podświetlenia).""",
        A,
    ),
    "analysis.axis": Topic(
        "Oś C (przekrój L–C)",
        "Oś pozioma przekroju: nasycenie względne (0–1, część największego możliwego) albo bezwzględne "
        "(C 0–0.37).",
        """Przy osi **względnej** prawa krawędź to zawsze granica sRGB, więc łatwo porównać „jak mocno
nasycone względem możliwości” są kolory. Przy osi **bezwzględnej** widać prawdziwy kształt gamutu dla
odcienia zaznaczonego koloru — puste pole to kolory spoza sRGB. Zobacz [gamut](help:concept.gamut).""",
        A,
    ),
    "analysis.overview": Topic(
        "Jak czytać wykresy",
        "Koło: kąt = odcień, odległość od środka = nasycenie względne. Przekrój L–C: wysokość = jasność, "
        "w prawo = nasycenie, dla odcienia zaznaczonego koloru.",
        """Oba wykresy pokazują kolory palety jako ponumerowane punkty (numer = miejsce na liście), a
zaznaczony kolor ma większy punkt. Na kole pomijane są prawie szare tło i tekst (C < 0.02), bo ich
odcień nic nie znaczy. Tło wykresów jest przygaszone, żeby punkty się wyróżniały.
Zobacz [koło odcieni](help:analysis.wheel) i [przekrój L–C](help:analysis.lc).""",
        A,
    ),
    "analysis.wheel": Topic(
        "Koło odcieni",
        "Akcenty na kole: kąt = odcień OKLCH (0° po prawej, przeciwnie do wskazówek zegara), promień = "
        "nasycenie względne. Łuki = zasada odcienia i cel układu zaznaczonego koloru.",
        """- **Punkty blisko siebie** — akcenty o podobnym odcieniu; jeśli mają też podobną jasność, będą
  mylone (sprawdź macierz ΔE).
- **Punkty przy środku** — kolory prawie szare; ich odcień ma małe znaczenie. Tło i tekst o bardzo
  małym nasyceniu nie są rysowane.
- **Żółty łuk** — [zasada odcienia](help:rules.hue) zaznaczonego koloru (na Palecie); **czerwone
  kropki** na nim to wycięte [zakazane przedziały](help:concept.exclusion).
- **Pomarańczowy łuk** (dalej od koła) — cel z [układu odcieni](help:rules.hues) ± tolerancja;
  widać go, gdy zaznaczony akcent ma włączone [„układ odcieni: stosuj”](help:rules.scheme_use).

Okrąg wewnętrzny to połowa maksymalnego nasycenia. Kolor tła koła odpowiada jasności 0.75.""",
        A,
    ),
    "analysis.lc": Topic(
        "Przekrój jasność–nasycenie (L–C)",
        "Gamut sRGB w przekroju przez odcień zaznaczonego koloru: w górę jaśniej, w prawo bardziej "
        "nasycone. Punkty to kolory palety.",
        """Pokazuje, ile „miejsca” ma kolor przy swoim odcieniu: np. żółcie mają duże nasycenie przy
wysokiej jasności, a błękity — przy średniej. Punkty innych kolorów są rysowane na tym samym przekroju
(wg własnych L i C), więc ich pozycja względem granicy sRGB jest przybliżona — dokładna tylko dla
zaznaczonego koloru. Gdy zaznaczony kolor jest szary, przekrój pokazuje odcień 250°.
Oś C przełączasz polem [oś C](help:analysis.axis).""",
        A,
    ),
    "analysis.matrix.de": Topic(
        "Macierz ΔE akcentów",
        "Odległość każdej pary akcentów w metodzie ΔE palety. Czerwone pole = para poniżej wymaganej "
        "odległości. Ostatnia kolumna: kontrast z tłem.",
        """Wiersze i kolumny to akcenty (numer, próbka, nazwa). Czerwone pole oznacza, że para łamie zasadę
[odległość od innych akcentów](help:rules.min_distance) (w widoku daltonizmu —
[odróżnialność](help:rules.cvd_min_distance)); podpowiedź na polu podaje wymagany próg. Ostatnia
kolumna to kontrast akcentu z tłem w metryce palety. Skala liczb zależy od metody
[ΔE](help:concept.delta_e).""",
        A,
    ),
    "analysis.matrix.contrast": Topic(
        "Macierz kontrastu par akcentów",
        "Kontrast każdego akcentu (wiersz, jako tekst) na każdym innym akcencie (kolumna, jako tło). Pole "
        "jest pokolorowane tą parą.",
        """Przydaje się, gdy akcenty bywają tłem dla innych akcentów: podświetlenia, tła paneli, zaznaczenia.
Wartości w metryce palety ([WCAG albo APCA](help:concept.contrast)); APCA nie jest symetryczne,
więc wiersz i kolumna dają różne liczby. Pole ma tło w kolorze kolumny i tekst w kolorze wiersza —
od razu widać, czy para jest czytelna. Wymagania kontrastu między kolorami ustawisz
[zależnością kontrastu](help:rel.contrast).""",
        A,
    ),
    "analysis.samples": Topic(
        "Próbki na tle",
        "Napis „Aa nazwa” w każdym kolorze palety na prawdziwym tle — najszybszy test czytelności na oko.",
        """Pokazuje kolory w praktyce: tekst i akcenty na tle palety, w bieżącym widoku (także z symulacją
daltonizmu). Jeśli coś trudno przeczytać, sprawdź zasadę
[kontrast z tłem](help:rules.contrast_bg) tego koloru.""",
        A,
    ),
}
