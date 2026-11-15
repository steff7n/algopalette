"""Pomoc: pojęcia — krótko i praktycznie, z odnośnikiem do miejsca w programie.

Tematy z ``term=True`` trzymają się wzorca terminu: „Co to jest” (jedno–dwa zdania zwykłym
językiem), „Przykład” (z liczbami) i „Kiedy użyć”. Liczby w przykładach są liczone z kodu programu
przy imporcie tego modułu, nie wpisane z pamięci — test porównuje je z ``algopalette.color``.
"""

from algopalette import color
from algopalette.gui.help_content.topic import Topic
from algopalette.model import OKLCH, CvdType, DeltaEMethod, FitMethod

G = "Pojęcia"

# --- liczby do przykładów ----------------------------------------------------------------------

_L = 0.75
_HUES = (
    (30, "pomarańczowoczerwony"),
    (110, "żółty"),
    (150, "zielony"),
    (260, "niebieski"),
    (330, "różowy"),
)


def _chroma_table() -> str:
    rows = [
        "| odcień | największe C | zakres bezwzględny 0.10–0.15 | zakres względny 50–70% |",
        "|---|---|---|---|",
    ]
    for hue, name in _HUES:
        m = color.max_chroma(_L, float(hue))
        share = f"{round(100 * 0.10 / m)}–{round(100 * 0.15 / m)}%"
        rows.append(
            f"| {hue}° ({name}) | {m:.3f} | {share} możliwości | C {0.5 * m:.3f}–{0.7 * m:.3f} |"
        )
    return "\n".join(rows)


_BLUE_MAX = color.max_chroma(_L, 260.0)

_PAIR = (OKLCH(0.70, 0.12, 30.0), OKLCH(0.70, 0.12, 60.0))
_DE_NOTES: dict[DeltaEMethod, tuple[str, str]] = {
    "ok": ("0–1", ".3f"),
    "hyab": ("0–1.3", ".3f"),
    "2000": ("0–100", ".1f"),
    "itp": ("0–400", ".1f"),
    "cam16": ("0–100", ".1f"),
}


def _delta_table() -> str:
    rows = ["| metoda | ΔE tej pary | skala (ok.) |", "|---|---|---|"]
    for method, (scale, fmt) in _DE_NOTES.items():
        value = color.delta_e(_PAIR[0], _PAIR[1], method)
        rows.append(f"| `{method}` | {value:{fmt}} | {scale} |")
    return "\n".join(rows)


_BG, _FG, _ACCENT = OKLCH(0.18, 0.02, 260.0), OKLCH(0.92, 0.01, 260.0), OKLCH(0.78, 0.12, 25.0)
_FG_WCAG = color.contrast(_FG, _BG, "wcag21")
_FG_APCA = color.contrast(_FG, _BG, "apca")
_ACC_WCAG = color.contrast(_ACCENT, _BG, "wcag21")
_ACC_APCA = color.contrast(_ACCENT, _BG, "apca")

_OUT = OKLCH(0.75, 0.25, 150.0)
_FIT_NOTES: dict[FitMethod, str] = {
    "oklch-chroma": "zmniejsza nasycenie w OKLCH, aż kolor prawie się mieści, resztę przycina",
    "lch-chroma": "to samo, ale liczone w CIE LCh",
    "minde-chroma": "metoda ze specyfikacji CSS: najmniejsza zauważalna zmiana nasycenia",
    "raytrace": "schodzi prosto w stronę szarości o tej samej jasności; L i H zostają co do joty",
    "scale": "skaluje składowe RGB; odcień zostaje, jasność lekko się zmienia",
    "clip": "obcina składowe RGB; najprostsza, najmocniej zmienia odcień",
}


def _fit_table() -> str:
    rows = ["| metoda | wynik L, C, H | co robi |", "|---|---|---|"]
    for method, note in _FIT_NOTES.items():
        f = color.fitted(_OUT, method)
        rows.append(f"| `{method}` | {f.l:.3f}, {f.c:.3f}, {f.h:.1f}° | {note} |")
    return "\n".join(rows)


_RED, _GREEN = OKLCH(0.70, 0.12, 30.0), OKLCH(0.70, 0.12, 140.0)


def _cvd(kind: CvdType, severity: float = 1.0) -> float:
    a = color.simulate_cvd(_RED, kind, "machado", severity)
    b = color.simulate_cvd(_GREEN, kind, "machado", severity)
    return color.delta_e(a, b, "ok")


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
    "concept.chroma_modes": Topic(
        "Nasycenie bezwzględne i względne",
        "Bezwzględne: podajesz samo C, tę samą liczbę dla każdego odcienia. Względne: podajesz "
        "procent największego nasycenia, jakie ekran pokaże przy tej jasności i tym odcieniu.",
        f"""**Co to jest.** Nasycenie C ograniczasz na jeden z dwóch sposobów. **Bezwzględne** to sama liczba C,
taka sama dla każdego odcienia. **Względne** to procent największego nasycenia, jakie ekran (sRGB)
pokaże przy danej jasności i danym odcieniu. To największe nasycenie jest dla każdego odcienia inne,
więc ten sam procent daje różne liczby C.

**Przykład.** Przy jasności L = {_L}:

{_chroma_table()}

Zakres 0.10–0.15 dla niebieskiego sięga ponad 100%: górna część leży poza ekranem, więc niebieski
dostanie najwyżej C {_BLUE_MAX:.3f}. Ten sam zakres dla różowego to niecałe dwie trzecie jego możliwości —
róż wyjdzie stonowany, a niebieski prawie najmocniejszy, jaki się da. Zakres 50–70% znaczy dla
każdego odcienia to samo: „mniej więcej w połowie drogi do granicy”.

![Dwa rzędy próbek w odcieniach co 30°](figure:chroma_modes)

Górny rząd ma wszędzie C = 0.10, dolny wszędzie 60% największego C (liczba pod próbką to C).

**Kiedy użyć.** Bezwzględne — gdy chcesz równej „ilości koloru” w liczbach, np. spokojnej palety
z C do 0.08. Względne — gdy każdy kolor ma być równie blisko granicy swoich możliwości, np. świecąca
paleta (85–100%) albo pastelowa (22–42%); wtedy żaden zakres nie wyjdzie poza ekran. Zobacz też:
[gamut](help:concept.gamut).""",
        G,
        term=True,
    ),
    "concept.delta_e": Topic(
        "ΔE — odległość kolorów",
        "Liczba mówiąca, jak bardzo dwa kolory różnią się na oko. Zasady odległości porównują ją "
        "z progiem; skala zależy od wybranej metody.",
        f"""**Co to jest.** ΔE to odległość między dwoma kolorami: 0 oznacza identyczne, im więcej, tym łatwiej je
odróżnić. Zasady „odległość od innych akcentów” i „odróżnialność (daltonizm)” wymagają, żeby ΔE nie
spadło poniżej progu. Program liczy ΔE jedną z pięciu metod, a każda ma własną skalę.

**Przykład.** Dwa kolory o tej samej jasności i nasyceniu (L 0.70, C 0.12), odcienie 30° i 60°:

{_delta_table()}

Próg 0.08 w `ok` znaczy mniej więcej to samo co 12.5 w `2000`. Przy zmianie metody program przelicza
progi przybliżonym przelicznikiem (`hyab` ×1.3, `2000` i `cam16` ×156, `itp` ×426) — sprawdź je
potem, jeśli zależy ci na dokładnych wartościach.

**Kiedy użyć.** `ok` — domyślna: szybka i zgodna z przestrzenią, w której program liczy. `hyab` — gdy
porównujesz kolory bardzo różne (osobno liczy jasność, osobno barwę). `2000` — gdy potrzebujesz liczb
porównywalnych z innymi narzędziami (CIEDE2000). `itp` — dla treści wideo i HDR (ICtCp). `cam16` —
model wyglądu koloru CAM16-UCS: najbliżej tego, co widzi oko, kosztem czasu. Macierz ΔE w Analizie
pokazuje odległości wszystkich par akcentów.""",
        G,
        term=True,
    ),
    "concept.contrast": Topic(
        "Kontrast: WCAG 2.1 i APCA",
        "Miara czytelności koloru na tle. WCAG 2.1 daje stosunek 1–21, APCA — wartość |Lc| do ok. "
        "106; metrykę wybierasz w zasadach całej palety.",
        f"""**Co to jest.** Kontrast mówi, jak czytelny jest kolor na tle. Program zna dwie metryki: **WCAG 2.1**
podaje stosunek jasności od 1 do 21, **APCA** — wartość |Lc| od 0 do ok. 106. Progi w zasadach
„kontrast z tłem” i w zależnościach kontrastu są w jednostkach wybranej metryki.

**Przykład.** Startowy tekst (L 0.92) na startowym tle (L 0.18) ma kontrast {_FG_WCAG:.2f} według WCAG
i {_FG_APCA:.1f} według APCA. Pierwszy akcent (L 0.78, C 0.12) na tym samym tle: {_ACC_WCAG:.2f} i {_ACC_APCA:.1f}.
Zwykłe progi to 4.5 (WCAG) albo 60 (APCA) dla akcentów oraz 7 albo 75 dla tekstu głównego; przy
zmianie metryki program przelicza progi według tych par (4.5 ↔ 60, 7 ↔ 75).

**Kiedy użyć.** WCAG — gdy musisz wykazać zgodność z normą dostępności. APCA — gdy liczy się
faktyczna czytelność, zwłaszcza w ciemnych motywach, które WCAG ocenia zbyt łagodnie (ciemny tekst
na ciemnym tle potrafi „zaliczyć” 4.5 i być ledwo widoczny). Pojedyncza zasada albo zależność może
mieć własną metrykę, niezależną od metryki palety.""",
        G,
        term=True,
    ),
    "concept.cvd": Topic(
        "Daltonizm (CVD)",
        "Symulacja zaburzeń widzenia barw: program sprawdza, czy akcenty dalej się różnią dla osób "
        "z protanopią, deuteranopią albo tritanopią.",
        f"""**Co to jest.** Przy zaburzeniach widzenia barw (CVD) część par kolorów zlewa się w jeden. W zasadach
całej palety wybierasz typy (protanopia — czerwień, deuteranopia — zieleń, tritanopia — błękit),
metodę symulacji i nasilenie. Zasada „odróżnialność (daltonizm)” wymaga wtedy minimalnej ΔE między
akcentami także po symulacji każdego wybranego typu.

**Przykład.** Akcent czerwonawy (H 30°) i zielonkawy (H 140°), oba L 0.70 i C 0.12, dzieli ΔE
{color.delta_e(_RED, _GREEN, "ok"):.3f} — różnią się wyraźnie. Po symulacji deuteranopii (Machado, nasilenie 1.0)
zostaje {_cvd("deutan"):.3f}: nie do odróżnienia. Przy nasileniu 0.6 zostaje {_cvd("deutan", 0.6):.3f}, przy protanopii
{_cvd("protan"):.3f}, a tritanopia tej parze nie szkodzi ({_cvd("tritan"):.3f}).

**Kiedy użyć.** Protanopię i deuteranopię włącz, gdy kolory niosą znaczenie (dotyczą ok. 8%
mężczyzn); tritanopia jest rzadka. Metody: Machado — dobra na co dzień i najlepsza przy częściowych
zaburzeniach; Viénot — szybka, dla protanopii i deuteranopii; Brettel — najdokładniejsza przy pełnym
zaburzeniu, zwłaszcza tritanopii. Nasilenie 1.0 to pełne zaburzenie, mniejsze — częściowe, czyli
łagodniejszy wymóg. W Analizie obejrzysz paletę i macierze tak, jak widzi je osoba z danym typem.""",
        G,
        term=True,
    ),
    "concept.gamut": Topic(
        "Gamut sRGB i dopasowanie",
        "Nie każdy kolor OKLCH da się wyświetlić w sRGB. Kolor spoza zakresu zostaje ściągnięty do "
        "najbliższego możliwego wybraną metodą dopasowania.",
        f"""**Co to jest.** Ekran sRGB pokazuje tylko część kolorów OKLCH; granica (gamut) zależy od jasności
i odcienia. Silnik generuje kolory zawsze mieszczące się w sRGB, ale wartość wpisaną ręcznie albo
wklejoną da się wyprowadzić poza zakres. Taki kolor program dopasowuje wybraną metodą, a hex,
naruszenia, Analiza i eksport używają koloru **po** dopasowaniu.

**Przykład.** Kolor L 0.75, C 0.25, H 150° nie istnieje na ekranie: przy tej jasności i tym odcieniu
największe C to {color.max_chroma(0.75, 150.0):.3f}. Co zrobi z nim każda metoda:

{_fit_table()}

**Kiedy użyć.** Zostaw `oklch-chroma`, jeśli nie masz powodu jej zmieniać. `raytrace` — gdy jasność
i odcień mają zostać nietknięte. `clip` — tylko dla zgodności z narzędziami, które tak przycinają.
Na liście kolorów hex dopasowanego koloru jest wyróżniony, a podpowiedź mówi, o ile ΔE go
przesunięto. Od granicy gamutu liczy się też [nasycenie względne](help:concept.chroma_modes).""",
        G,
        term=True,
    ),
    "concept.hard_soft": Topic(
        "Zasady twarde i miękkie, waga",
        "Twarda zasada musi być spełniona — wynik, który ją łamie, jest oznaczony ✗. Miękka to cel "
        "z wagą: silnik zbliża się do niego, ile się da.",
        """**Co to jest.** Każdą zasadę i każdą zależność oznaczasz jako twardą albo miękką. **Twarda** musi być
spełniona. **Miękka** jest celem, od którego silnik odstąpi, gdy koliduje z twardymi. **Waga** mówi,
jak ważny jest miękki cel wobec innych miękkich.

**Przykład.** Jasność akcentu 0.60–0.85 jako zasada twarda: kolor o L 0.58 łamie ją o 0.02, a
propozycja dostaje oznaczenie „✗ łamie twarde”. Ta sama zasada jako miękka: propozycja jest
w porządku, a naruszenie widać w panelu ze znakiem ~. Kara za naruszenie rośnie z jego kwadratem
i jest mnożona przez wagę, a dla zasad twardych dodatkowo przez „wagę twardych” (domyślnie 1000).
Dwa miękkie cele nie do pogodzenia — odległość między akcentami z wagą 1 i rozrzut jasności z wagą
2 — silnik rozstrzygnie na korzyść rozrzutu, bo to samo naruszenie kosztuje tam dwa razy więcej.

**Kiedy użyć.** Twarde — dla rzeczy, bez których paleta jest bezużyteczna: kontrast tekstu, zakres
jasności. Miękkie — dla życzeń: równe odstępy, układ odcieni. [Zakazane
przedziały](help:concept.exclusion) są zawsze twarde. Gdy zasady się wykluczają, program pokazuje,
które są złamane i o ile, zamiast udawać sukces. Wyłączona zasada (odznaczona) nie liczy się wcale.""",
        G,
        term=True,
    ),
    "concept.exclusion": Topic(
        "Zakazany przedział",
        "Kawałek zakresu jasności, nasycenia albo odcienia, w którym kolor nie może się znaleźć. "
        "Zakaz jest zawsze twardy.",
        """**Co to jest.** Zasady jasności, nasycenia i odcienia mają zakres dozwolony oraz dowolnie wiele
zakazanych przedziałów. Kolor musi leżeć w zakresie i poza każdym zakazem. Zakaz jest zawsze twardy:
nie ma wagi ani własnego wyłącznika i działa, dopóki zasada jest włączona.

**Przykład.** Odcień dozwolony 0–270° z zakazami 60–85° i 140–155°. Odcień 70° łamie pierwszy zakaz
o 10° (bliżej mu do brzegu 60° niż do 85°), a panel naruszeń pokaże „zakazany przedział: odcień …
poza 60–85”. Odcień 86° jest w porządku. Zakaz może przechodzić przez 0°: 350–10° wyklucza
czerwienie po obu stronach zera.

**Kiedy użyć.** Gdy dopuszczasz szeroki zakres z wyjątkami: „dowolny odcień, byle nie żółty” albo
„jasność 0.55–0.90, ale nie 0.70–0.74, bo zlewa się z komentarzami”. Zakaz dodajesz przyciskiem
„+ zakaz” pod suwakiem; zakazane odcinki są zakreskowane na pasku. Zakazy pokrywające cały zakres
dają stałe naruszenie — program je pokaże, zamiast udawać, że da się je spełnić.""",
        G,
        term=True,
    ),
    "concept.hue_arc": Topic(
        "Zasada odcienia — łuk",
        "Dozwolony łuk na kole odcieni. Ten sam łuk zapisujesz jako „od–do” albo jako „środek ± "
        "połowa szerokości”.",
        """**Co to jest.** Odcień koloru ograniczasz jednym łukiem na kole (0–360°). Łuk ma dwa równoważne
zapisy, które program przelicza na bieżąco: „od–do” oraz „środek ± połowa szerokości”. „Od” większe
niż „do” oznacza łuk przechodzący przez 0°.

**Przykład.** „Od 330 do 20” to to samo co „środek 355 ± 25”: dozwolone są czerwienie po obu
stronach zera, razem 50°. Odcień 40° łamie tę zasadę o 20°. „Od 0 do 360” to pełne koło — taka
zasada niczego nie ogranicza, ale pozwala dopisać [zakazane przedziały](help:concept.exclusion).

**Kiedy użyć.** „Od–do”, gdy myślisz granicami („ciepłe: 20–90”); „środek ±”, gdy masz konkretny
odcień i tolerancję („firmowy niebieski: 255 ± 8”). Akcent może mieć własny łuk i jednocześnie cel
z układu odcieni — wtedy musi spełnić jedno i drugie. Przy bardzo małym nasyceniu (C poniżej 0.02)
odcień przestaje być widoczny, więc zasada stopniowo słabnie do zera.""",
        G,
        term=True,
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
