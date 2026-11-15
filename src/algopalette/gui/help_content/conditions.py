"""Pomoc: warunki koloru (8 typów + elementy wiersza) i zależności od innych kolorów."""

from algopalette.gui.help_content.topic import Topic

C = "Warunki i zależności"

TOPICS: dict[str, Topic] = {
    # --- warunki: ogólnie i elementy wiersza ---
    "cond.overview": Topic(
        "Warunki koloru",
        "Czego silnik ma pilnować dla tego koloru: jasność, nasycenie, odcień, kontrast, odległość od "
        "innych akcentów. Każdy warunek jest twardy albo miękki.",
        """Każdy wiersz to jeden typ warunku. W edytorze koloru widzisz warunki **obowiązujące** ten kolor:
własne albo dziedziczone z domyślnych warunków roli w Globalnych — plakietka mówi, skąd pochodzi
wartość ([źródła wartości](help:concept.sources)).

- Zmiana wartości dziedziczonej tworzy **własną kopię** warunku w tym kolorze; „↺ dziedzicz” ją usuwa.
- „+ dodaj” przy „brak warunku” włącza warunek, którego rola domyślnie nie ma.
- **włączony** / **twardy** / **waga** sterują tym, czy i jak mocno warunek się liczy
  ([twarde i miękkie](help:concept.hard_soft)).

Zestaw zależy od roli: tło nie ma kontrastu z tłem, a odległość od akcentów, odróżnialność
i skrajny kontrast mają tylko akcenty. Na zakładce Globalne ten sam edytor ustawia domyślne warunki
całej roli.""",
        C,
    ),
    "cond.enabled": Topic(
        "Włączony / włączona",
        "Odznaczony warunek albo zależność zostaje zapamiętany, ale nie liczy się ani w silniku, ani "
        "w naruszeniach.",
        """Wygodne do sprawdzenia, czy to właśnie ten warunek blokuje dobre propozycje — wyłącz go, wygeneruj,
porównaj. Wartość zostaje, więc włączenie przywraca go bez przepisywania liczb.""",
        C,
    ),
    "cond.hard": Topic(
        "Twardy / twarda",
        "Zaznaczone: musi być spełniony (✗ przy złamaniu). Odznaczone: miękki cel z wagą — silnik ustąpi, "
        "gdy koliduje z twardymi.",
        """Zobacz [warunki twarde i miękkie](help:concept.hard_soft). Zasada praktyczna: twarde zostaw na to,
bez czego motyw jest nieużywalny (kontrast tekstu, rozróżnialność akcentów), a estetykę (odcienie,
nasycenie) rób miękką. Za dużo twardych warunków łatwo się wyklucza.""",
        C,
    ),
    "cond.weight": Topic(
        "Waga",
        "Jak ważny jest warunek miękki względem innych miękkich (domyślnie 1). 0 = nie liczy się. Przy "
        "warunku twardym ma niewielkie znaczenie.",
        """Silnik minimalizuje sumę naruszeń miękkich warunków pomnożonych przez wagi. Waga 2 oznacza, że
naruszenie tego warunku „boli” dwa razy bardziej niż warunku z wagą 1. Puste pole przy wpisie jest
ignorowane, wartości ujemne są zamieniane na 0.""",
        C,
    ),
    "cond.reset": Topic(
        "↺ dziedzicz",
        "Usuwa własną wartość tego koloru — warunek wraca do domyślnej wartości roli z Globalnych.",
        """Widoczny tylko przy warunkach z plakietką „własne”. Gdy rola nie ma takiego warunku domyślnie,
„↺ dziedzicz” po prostu usuwa warunek z tego koloru. Zobacz [źródła wartości](help:concept.sources).""",
        C,
    ),
    "cond.remove": Topic(
        "✕ usuń (domyślny warunek roli)",
        "Usuwa ten domyślny warunek z całej roli — przestaje obowiązywać kolory, które go dziedziczą.",
        """Kolory z własną wartością tego warunku zachowują ją. Ponowne dodanie: „+ dodaj” w tym samym
wierszu. Ctrl+Z cofa usunięcie.""",
        C,
    ),
    "cond.add": Topic(
        "Brak warunku / + dodaj",
        "Ten typ warunku nie obowiązuje tego koloru (ani roli). „+ dodaj” włącza go z wartością domyślną.",
        """Wartość startowa zależy od ustawień: kontrast — 4.5 w WCAG albo 60 w APCA, odległości — w skali
bieżącej metody ΔE. Potem dostosuj ją suwakiem.""",
        C,
    ),
    "cond.badge": Topic(
        "Plakietka źródła wartości",
        "Skąd pochodzi wartość warunku: nastrój, globalne (domyślny warunek roli zmieniony ręcznie) albo "
        "własne (ustawione w tym kolorze).",
        """Zobacz [źródła wartości](help:concept.sources).""",
        C,
    ),
    # --- warunki: 8 typów ---
    "cond.lightness": Topic(
        "Warunek: jasność L",
        "Dozwolony zakres jasności OKLCH (0 = czerń, 1 = biel). Pusta granica = bez ograniczenia z tej "
        "strony.",
        """Suwak zakresu ma dwa uchwyty (spacja przełącza aktywny). Jako warunek **twardy** zakres staje się
granicą poszukiwań — silnik w ogóle nie bada jasności spoza niego. Jako **miękki** jest celem
z [wagą](help:cond.weight).

Typowe użycie: ciemne tło w 0.15–0.25, tekst 0.85–0.95, akcenty w wąskim paśmie (np. 0.65–0.80),
żeby miały podobną wagę wizualną. Rozrzut jasności akcentów możesz też wymusić w Globalnych.""",
        C,
    ),
    "cond.chroma": Topic(
        "Warunek: nasycenie C",
        "Zakres nasycenia — bezwzględny (C OKLCH) albo względny (ułamek największego C możliwego w sRGB "
        "przy danym L i H).",
        """**Bezwzględne** (0–0.37): ta sama liczba to to samo nasycenie, niezależnie od odcienia; ale np.
C 0.15 jest niemożliwe dla niektórych odcieni przy danej jasności.

**Względne** (0–1): 1 = najmocniejszy kolor, jaki sRGB pozwala przy tej jasności i odcieniu. Lepsze do
spójnych palet — każdy akcent jest „równie nasycony względem swoich możliwości”. Twardy zakres względny
staje się granicą poszukiwań.

Zmiana trybu ustawia rozsądny zakres startowy (bezwzględne 0.05–0.15, względne 0.2–0.6).""",
        C,
    ),
    "cond.chroma.mode": Topic(
        "Tryb nasycenia",
        "Bezwzględne = C OKLCH; względne = ułamek największego C osiągalnego w sRGB przy tej jasności "
        "i odcieniu.",
        """Zobacz [warunek nasycenia](help:cond.chroma) i [gamut](help:concept.gamut).""",
        C,
    ),
    "cond.hue_range": Topic(
        "Warunek: zakres odcienia",
        "Dozwolony łuk odcienia w stopniach. Gdy lewa granica jest większa od prawej (np. 330–20), łuk "
        "przechodzi przez 0°.",
        """Używaj, gdy kolor ma pozostać „w rodzinie” — np. błędy w czerwieniach (330–20), komentarze
w szarościach niebieskawych. Twardy zakres staje się granicą poszukiwań. Akcent z zakresem odcienia nie
dostaje celu z układu odcieni w Globalnych. Na kole odcieni w Analizie zakres zaznaczonego koloru widać
jako żółty łuk.""",
        C,
    ),
    "cond.hue_target": Topic(
        "Warunek: cel odcienia",
        "Odcień docelowy ± tolerancja (pole po „±”, w stopniach). W tolerancji warunek jest spełniony, "
        "dalej rośnie kara.",
        """Precyzyjniejsza wersja zakresu: „mniej więcej 210° ± 15°”. Domyślnie cele odcieni akcentów wynikają
z układu odcieni w Globalnych. Akcent, który ma jakikolwiek warunek odcienia (cel albo zakres, nawet
wyłączony), nie dostaje celu z układu. Na kole odcieni w Analizie widać cel jako pomarańczowy łuk.""",
        C,
    ),
    "cond.contrast_bg": Topic(
        "Warunek: kontrast z tłem",
        "Zakres kontrastu tego koloru z tłem (kolor 0). Metryka: globalna z ustawień albo własna — WCAG 2.1 "
        "lub APCA.",
        """Najważniejszy warunek czytelności: tekst zwykle ≥ 4.5 (WCAG) albo ≥ 75 (APCA), akcenty składni
≥ 3–4.5. Górna granica przydaje się do kolorów, które mają być stonowane (komentarze, nieaktywny kod).

Lista metryki: „globalna” idzie za ustawieniem z Globalnych; konkretna metryka zostaje przy tym
warunku niezależnie od globalnej. Zmiana metryki ustawia próg startowy w jej skali (4.5 albo 60).
Zobacz [WCAG i APCA](help:concept.contrast).""",
        C,
    ),
    "cond.contrast_bg.metric": Topic(
        "Metryka kontrastu warunku",
        "„Globalna” = metryka z Globalnych; WCAG 2.1 albo APCA = ta metryka tylko dla tego warunku.",
        """Zobacz [kontrast z tłem](help:cond.contrast_bg) i [WCAG i APCA](help:concept.contrast).""",
        C,
    ),
    "cond.min_distance": Topic(
        "Warunek: odległość od akcentów",
        "Minimalna ΔE między tym akcentem a każdym innym akcentem — żeby akcenty nie były do siebie zbyt "
        "podobne.",
        """Dla każdej pary akcentów obowiązuje **ostrzejszy** z ich dwóch progów, a para jest twarda, gdy
którykolwiek z nich jest twardy. Skala zależy od metody ΔE w Globalnych (0.08 w `ok` to wyraźna
różnica) — patrz [ΔE](help:concept.delta_e). Bieżącą najmniejszą odległość widać w kolumnie
„ΔE min” listy i w macierzy ΔE w Analizie.""",
        C,
    ),
    "cond.cvd_min_distance": Topic(
        "Warunek: odróżnialność (daltonizm)",
        "Minimalna ΔE między akcentami po symulacji daltonizmu — dla typów wybranych w Globalnych. Bez "
        "wybranych typów nic nie robi.",
        """Działa jak [odległość od akcentów](help:cond.min_distance), tylko liczona na kolorach widzianych
z zaburzeniem widzenia barw (osobno dla każdego wybranego typu). Zwykle próg jest niższy niż zwykłej
odległości. Typy, metodę i nasilenie ustawiasz w Globalnych → daltonizm ([CVD](help:concept.cvd)).""",
        C,
    ),
    "cond.extreme": Topic(
        "Warunek: skrajny kontrast",
        "Ten akcent ma mieć najsłabszy (albo najmocniejszy) kontrast z tłem spośród wszystkich akcentów.",
        """Typowe użycie: komentarze — najsłabszy kontrast, żeby nie przyciągały wzroku; albo najważniejszy
akcent — najmocniejszy. Warunek porównuje kontrast tego akcentu z kontrastem pozostałych akcentów
w metryce z Globalnych, bez sztywnego progu.""",
        C,
    ),
    # --- zależności ---
    "rel.overview": Topic(
        "Zależności od innych kolorów",
        "Warunki względem innego koloru: różnica odcienia, jasności, nasycenia, kontrast, odległość ΔE "
        "albo mieszanka dwóch kolorów.",
        """Zależność wiąże ten kolor z innym kolorem palety (celem). Przykłady:

- „odcień przeciwny do akcentu 1” — odcień, `=`, 180, tol 15;
- „ciemniejszy od tekstu o co najmniej 0.1” — jasność, `≤`, −0.1;
- „nasycenie co najmniej jak akcent 2” — nasycenie, `× mnożnik`, `≥`, 1.0;
- „podobny do akcentu 3, ale nie identyczny” — dwie zależności odległości: `≥ 0.03` i `≤ 0.08`;
- „w połowie między akcentem 1 a 4” — mieszanka, t = 0.5, tol ΔE 0.02.

Zależność trzyma się koloru-celu, nie jego numeru. Po usunięciu celu zostaje oznaczona jako
[zerwana](help:rel.broken). Twarda/miękka i waga działają jak w warunkach
([twarde i miękkie](help:concept.hard_soft)).""",
        C,
    ),
    "rel.add": Topic(
        "+ dodaj zależność",
        "Dodaje zależność względem pierwszego innego koloru (domyślnie: odcień = 180° ± 15). Potem wybierz "
        "typ i cel.",
        """Zobacz [zależności](help:rel.overview).""",
        C,
    ),
    "rel.delete": Topic(
        "✕ usuń zależność",
        "Usuwa tę zależność (Ctrl+Z cofa).",
        """Zobacz [zależności](help:rel.overview).""",
        C,
    ),
    "rel.broken": Topic(
        "⚠ zerwana",
        "Kolor, którego dotyczyła ta zależność, został usunięty. Zależność się nie liczy — wybierz nowy cel "
        "albo ją usuń.",
        """Zerwana zależność ma czerwoną ramkę. Wybranie nowego celu z listy naprawia ją od razu.
Ctrl+Z przywraca usunięty kolor, a wtedy zależność znów działa.""",
        C,
    ),
    "rel.kind": Topic(
        "Typ zależności",
        "Co porównujesz z kolorem-celem: odcień, jasność, nasycenie, kontrast, odległość ΔE albo "
        "mieszankę dwóch kolorów.",
        """- [odcień](help:rel.hue) — różnica odcieni w stopniach;
- [jasność](help:rel.lightness) — różnica L;
- [nasycenie](help:rel.chroma) — różnica albo stosunek C;
- [kontrast](help:rel.contrast) — ten kolor na celu jako tle;
- [odległość ΔE](help:rel.distance) — jak bardzo kolory się różnią;
- [mieszanka](help:rel.mix) — kolor leży między dwoma innymi.

Zmiana typu ustawia wartość startową w jednostkach nowego typu.""",
        C,
    ),
    "rel.target": Topic(
        "Względem (kolor-cel)",
        "Kolor, z którym porównujesz ten kolor. Lista obejmuje wszystkie inne kolory palety.",
        """Zależność trzyma się wybranego koloru, także po zmianie jego numeru. Cel może mieć kłódkę —
wtedy silnik dopasowuje tylko ten kolor.""",
        C,
    ),
    "rel.op": Topic(
        "Operator",
        "= (± tol): różnica równa wartości z tolerancją; ≥ co najmniej; ≤ co najwyżej.",
        """Przy `=` warunek jest spełniony, gdy różnica mieści się w wartość ± tol. Przy `≥` i `≤`
tolerancja nie jest używana. Znaczenie „różnicy” zależy od [typu](help:rel.kind).""",
        C,
    ),
    "rel.tol": Topic(
        "Tolerancja (tol)",
        "Dopuszczalne odchylenie od wartości przy operatorze „=”. W jednostkach typu zależności (stopnie, L, "
        "C, kontrast, ΔE).",
        """Przy `≥` i `≤` tolerancja nie ma znaczenia. Zbyt mała tolerancja przy warunku twardym potrafi
zablokować silnik — dla odcieni typowe jest 10–20°.""",
        C,
    ),
    "rel.metric": Topic(
        "Metryka zależności",
        "Dla kontrastu: WCAG albo APCA, dla odległości: metoda ΔE. „Globalna” = ustawienie z Globalnych.",
        """Wartość i tolerancja są w skali wybranej metryki ([kontrast](help:concept.contrast),
[ΔE](help:concept.delta_e)).""",
        C,
    ),
    "rel.hue": Topic(
        "Zależność: odcień",
        "Różnica odcieni: odcień tego koloru minus odcień celu, najkrótszym łukiem (−180°…180°). 180 = "
        "przeciwny, ±30 = sąsiedni.",
        """Przykład: `=` 180, tol 15 — dopełniający; `=` 30, tol 10 — analogiczny „obok”. Znak ma
znaczenie: +30 i −30 to różne kierunki na kole. Dla szarych kolorów (bardzo małe C) różnica odcieni
waży mniej, bo odcień jest wtedy ledwo widoczny.""",
        C,
    ),
    "rel.lightness": Topic(
        "Zależność: jasność",
        "Różnica jasności L: ten kolor minus cel. Ujemna = ciemniejszy od celu (np. ≤ −0.1 = ciemniejszy "
        "co najmniej o 0.1).",
        """Typowe: tło paneli bocznych odrobinę jaśniejsze od tła (`=` 0.03, tol 0.01), akcent ciemniejszy od
tekstu (`≤` −0.1).""",
        C,
    ),
    "rel.chroma": Topic(
        "Zależność: nasycenie",
        "„+ różnica”: C tego koloru minus C celu; „× mnożnik”: C tego koloru względem wartość × C celu. "
        "Bezwzględne albo względne C.",
        """- **+ różnica**, `≥` 0 — co najmniej tak nasycony jak cel;
- **× mnożnik**, `≥` 1.0 — to samo, wyrażone stosunkiem; `≤` 0.5 — najwyżej połowa nasycenia celu.

„bezwzgl.” porównuje C OKLCH, „względne” — ułamki największego C osiągalnego w sRGB
([warunek nasycenia](help:cond.chroma)).""",
        C,
    ),
    "rel.contrast": Topic(
        "Zależność: kontrast",
        "Kontrast tego koloru na kolorze-celu jako tle — np. tekst na tle zaznaczenia, ikona na tle paska.",
        """Przydaje się, gdy kolor ma być czytelny nie tylko na głównym tle: napis na tle paska stanu,
podświetlenie wyszukiwania pod tekstem. Wartość w skali [metryki](help:rel.metric).""",
        C,
    ),
    "rel.distance": Topic(
        "Zależność: odległość ΔE",
        "Jak bardzo ten kolor ma się różnić od celu. Dwie zależności (≥ i ≤) dają „podobny, ale nie "
        "identyczny”.",
        """Wartość w skali [metody ΔE](help:concept.delta_e) (z Globalnych albo własnej z listy metryki).
Działa dla dowolnych kolorów, nie tylko akcentów — np. tło paneli wyraźnie inne od tła głównego.""",
        C,
    ),
    "rel.mix": Topic(
        "Zależność: mieszanka dwóch",
        "Kolor ma leżeć między celem a drugim kolorem: t = 0 — przy celu, 1 — przy drugim, 0.5 — w połowie "
        "(w OKLab). Tol ΔE = dopuszczalne odchylenie.",
        """Mieszanka liczona jest w OKLab (percepcyjnie równo). Przykład: kolor zaznaczenia w połowie między
tłem a akcentem — cel: tło, „i”: akcent, t = 0.3, tol ΔE 0.02. Gdy któryś z dwóch kolorów zostanie
usunięty, zależność jest [zerwana](help:rel.broken).""",
        C,
    ),
}
