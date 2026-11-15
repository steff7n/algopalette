"""Pomoc: zakładka „Zasady” — preset, pasek kolorów, zasady kolorów, ustawienia całej palety."""

from algopalette.gui.help_content.topic import Topic

Z = "Zasady"
K = "Zasady koloru"

TOPICS: dict[str, Topic] = {
    # --- zakładka, preset, pasek kolorów -------------------------------------------------------
    "rules.tab": Topic(
        "Zakładka Zasady",
        "Jedyne miejsce, w którym ustawiasz to, co wpływa na generowanie: zasady każdego koloru "
        "i ustawienia całej palety.",
        """Zakładka opisuje paletę, która dopiero ma powstać. Od góry: [preset](help:rules.preset),
[liczba kolorów](help:rules.count), [pasek kolorów](help:rules.strip) i edytor tego, co zaznaczysz
na pasku — [zasady kolorów](help:rules.editing) albo [cała paleta](help:rules.palette). Każdy kolor ma
komplet własnych zasad; to, co widzisz przy kolorze, to wszystko, co go obowiązuje. Na dole
[Generuj propozycje](help:rules.generate).""",
        Z,
    ),
    "rules.preset": Topic(
        "Preset",
        "Gotowy zestaw zasad całej palety. Nałożenie zastępuje zasady wszystkich kolorów, układ "
        "odcieni i rozrzut jasności.",
        """Preset to nazwany zestaw zasad: tła, tekstu i akcentów, układu odcieni i rozrzutu jasności.
[Zastosuj](help:rules.preset.apply) zastępuje nimi bieżące zasady; nie rusza wartości kolorów, kłódek,
nazw, zależności, listy unikanych kolorów ani ustawień generowania. Wszystko, co preset ustawił,
widać niżej i można zmienić — wtedy przy nazwie pojawia się
[„(zmieniony)”](help:rules.preset.current).""",
        Z,
    ),
    "rules.preset.search": Topic(
        "Szukaj presetu",
        "Zawęża listę presetów do tych, których nazwa albo opis zawiera wpisany tekst (bez względu "
        "na wielkość liter i polskie znaki).",
        """Wpisz fragment nazwy albo opisu, np. „mgl” albo „zielen”. Lista obok pokazuje tylko pasujące
presety z wybranej [kategorii](help:rules.preset.category).""",
        Z,
    ),
    "rules.preset.category": Topic(
        "Kategoria presetów",
        "Zawęża listę do jednej kategorii, np. Chłodne albo Dostępność. „Własne” to presety "
        "zapisane przez ciebie.",
        """Presety wbudowane są podzielone na kategorie. Kategoria i [wyszukiwarka](help:rules.preset.search)
działają razem.""",
        Z,
    ),
    "rules.preset.list": Topic(
        "Lista presetów",
        "Presety pasujące do wyszukiwarki i kategorii. Podpowiedź pozycji mówi, co preset ustawia.",
        """Wybierz preset i naciśnij [Zastosuj](help:rules.preset.apply). Presety z dopiskiem „(własny)”
zapisałeś sam; pozostałe są wbudowane.""",
        Z,
    ),
    "rules.preset.apply": Topic(
        "Zastosuj preset",
        "Zastępuje zasady wszystkich kolorów, układ odcieni i rozrzut jasności wybranym presetem. "
        "Ctrl+Z cofa.",
        """Preset wbudowany jest nakładany dla bieżącego [tła](help:rules.polarity) i metryki kontrastu.
Preset własny przywraca też tło i metrykę, przy których go zapisano. Wartości kolorów, kłódki
i zależności zostają.""",
        Z,
    ),
    "rules.preset.current": Topic(
        "Bieżący preset i „(zmieniony)”",
        "Nazwa ostatnio nałożonego presetu. „(zmieniony)” znaczy, że zasady różnią się już od tego, "
        "co preset ustawia.",
        """Program porównuje zasady kolorów, układ odcieni i rozrzut jasności ze świeżo nałożonym
presetem. Zmiana wartości kolorów, kłódek czy ustawień generowania nie daje „(zmieniony)”.""",
        Z,
    ),
    "rules.preset.save": Topic(
        "Zapisz zasady jako preset",
        "Zapisuje bieżące zasady wszystkich kolorów, układ odcieni, rozrzut jasności, tło i metrykę "
        "pod podaną nazwą.",
        """Własny preset pamięta zasady według pozycji koloru. Nałożony na paletę z większą liczbą akcentów
powiela zasady ostatniego zapisanego akcentu. Nazwy presetów wbudowanych są zajęte.""",
        Z,
    ),
    "rules.preset.delete": Topic(
        "Usuń własny preset",
        "Usuwa z listy preset zapisany przez ciebie. Presetów wbudowanych nie da się usunąć.",
        """Usunięcie nie zmienia bieżących zasad — znika tylko pozycja z listy.""",
        Z,
    ),
    "rules.polarity": Topic(
        "Tło: ciemne albo jasne",
        "Polaryzacja palety. Zakresy jasności w presetach zależą od niej, więc zmiana tła nakłada "
        "preset ponownie albo pyta, co zrobić.",
        """Gdy zasady są świeżo nałożonym presetem, zmiana tła nakłada ten sam preset w wersji dla nowego
tła. Gdy zasady są zmienione albo presetu nie ma, program pyta: zastąpić zasady presetem dla nowego
tła, zmienić tylko oznaczenie tła, czy anulować.""",
        Z,
    ),
    "rules.count": Topic(
        "Liczba kolorów",
        "Paleta ma tło, tekst i od 1 do 14 akcentów. „+” dodaje akcent z zasadami ostatniego, „−” "
        "usuwa ostatni.",
        """Nowy akcent dostaje kopię zasad ostatniego akcentu (bez zależności). Obie czynności cofa
Ctrl+Z. Dowolny akcent usuniesz albo przestawisz na zakładce Paleta.""",
        Z,
    ),
    "rules.strip": Topic(
        "Pasek kolorów",
        "Wybierasz, czyje zasady edytujesz: jeden kolor, kilka naraz albo całą paletę. Ctrl+klik "
        "dokłada kolor, Shift+klik zaznacza zakres.",
        """Klik zaznacza jeden kolor. **Ctrl+klik** dokłada albo odejmuje kolor, **Shift+klik** zaznacza
zakres od ostatnio klikniętego, „wszystkie akcenty” — wszystkie akcenty naraz. Zmiana zasady trafia
do wszystkich zaznaczonych kolorów jednym krokiem cofania. „cała paleta” pokazuje ustawienia wspólne.
Z klawiatury: ←/→ przenosi fokus, spacja zaznacza, Ctrl+spacja dokłada, Ctrl+A to wszystkie akcenty.""",
        Z,
    ),
    "rules.editing": Topic(
        "Zasady zaznaczonych kolorów",
        "Wiersz na każdą zasadę, która dotyczy wszystkich zaznaczonych kolorów. Zmiana trafia do "
        "każdego z nich.",
        """Przy jednym kolorze widzisz komplet jego zasad. Przy kilku — tylko zasady wspólne dla ich ról
(tło nie ma kontrastu z tłem; odległość, odróżnialność i skrajny kontrast mają tylko akcenty). Gdy
kolory mają różne wartości, wiersz pokazuje [„różne”](help:rules.rule.mixed).""",
        K,
    ),
    "rules.generate": Topic(
        "Generuj propozycje",
        "Uruchamia silnik dla wszystkich kolorów bez kłódki i przechodzi do zakładki Propozycje.",
        """To samo co Ctrl+G. Silnik szuka palet spełniających wszystkie zasady naraz; wyniki oglądasz
i przejmujesz na zakładce Propozycje.""",
        Z,
    ),
    "rules.palette_link": Topic(
        "Zasady tego koloru",
        "Przechodzi do zakładki Zasady z zaznaczonym tym kolorem.",
        """Zasady kolorów ustawia się tylko na zakładce Zasady; ten odnośnik otwiera ją na kolorze
zaznaczonym na liście.""",
        K,
    ),
    # --- wiersz zasady -------------------------------------------------------------------------
    "rules.rule.enabled": Topic(
        "Włączona",
        "Odznaczona zasada albo zależność zostaje zapamiętana, ale nie liczy się ani w silniku, ani "
        "w naruszeniach.",
        """Wyłączenie przydaje się do prób: sprawdzasz, co wyjdzie bez zasady, nie tracąc jej wartości.""",
        K,
    ),
    "rules.rule.hard": Topic(
        "Twarda",
        "Twarda zasada musi być spełniona; miękka jest celem z wagą.",
        """Propozycja łamiąca twardą zasadę dostaje oznaczenie ✗. Więcej:
[twarde i miękkie](help:concept.hard_soft).""",
        K,
    ),
    "rules.rule.weight": Topic(
        "Waga",
        "Jak ważna jest miękka zasada wobec innych miękkich. Większa waga = silnik mniej chętnie "
        "z niej ustępuje.",
        """Waga działa tylko dla zasad miękkich. Przykład i szczegóły:
[twarde i miękkie](help:concept.hard_soft).""",
        K,
    ),
    "rules.rule.remove": Topic(
        "Usuń zasadę",
        "Zdejmuje zasadę z zaznaczonych kolorów. Kolor bez zasady nie jest w tym zakresie niczym "
        "ograniczony.",
        """Przy kilku zaznaczonych kolorach usuwa zasadę u wszystkich. Ctrl+Z przywraca.""",
        K,
    ),
    "rules.rule.add": Topic(
        "Dodaj zasadę",
        "Żaden z zaznaczonych kolorów nie ma tej zasady. „+ dodaj” nadaje ją wszystkim z wartością "
        "startową.",
        """Wartość startowa jest w jednostkach bieżącej metryki kontrastu i metody ΔE; potem ustawiasz
ją jak każdą inną.""",
        K,
    ),
    "rules.rule.mixed": Topic(
        "Różne wartości",
        "Zaznaczone kolory mają tę zasadę ustawioną inaczej (wartość, włączenie, twardość, waga "
        "albo sama obecność).",
        """Wiersz pokazuje, co ma każdy kolor. [Ustaw dla zaznaczonych](help:rules.rule.unify) nadaje
wszystkim jedną zasadę, a „usuń u wszystkich” zdejmuje ją z każdego.""",
        K,
    ),
    "rules.rule.unify": Topic(
        "Ustaw dla zaznaczonych",
        "Nadaje wszystkim zaznaczonym kolorom tę samą zasadę — taką, jaką ma pierwszy zaznaczony "
        "kolor, który ją posiada.",
        """Po ujednoliceniu wiersz zamienia się w zwykły edytor i dalsze zmiany trafiają do wszystkich
zaznaczonych kolorów.""",
        K,
    ),
    "rules.lightness": Topic(
        "Jasność L",
        "Dozwolony zakres jasności koloru (0 = czerń, 1 = biel) i zakazane przedziały wewnątrz "
        "niego.",
        """Uchwyty na pasku ustawiają zakres; puste pole oznacza brak ograniczenia z tej strony.
„+ zakaz” dodaje [zakazany przedział](help:concept.exclusion).""",
        K,
    ),
    "rules.chroma": Topic(
        "Nasycenie C",
        "Dozwolony zakres nasycenia — w jednostkach C albo jako procent największego nasycenia "
        "możliwego przy tej jasności i odcieniu.",
        """Tryb wybierasz z listy obok suwaka: [bezwzględne albo względne](help:concept.chroma_modes).
Zakres może mieć [zakazane przedziały](help:concept.exclusion).""",
        K,
    ),
    "rules.chroma.mode": Topic(
        "Tryb nasycenia",
        "Bezwzględne: zakres w jednostkach C. Względne: zakres jako część największego nasycenia, "
        "jakie ekran pokaże przy tej jasności i odcieniu.",
        """Zmiana trybu ustawia zakres startowy w nowej skali i usuwa zakazane przedziały (były w starej
skali). Przykład z liczbami: [nasycenie bezwzględne i względne](help:concept.chroma_modes).""",
        K,
    ),
    "rules.hue": Topic(
        "Odcień",
        "Dozwolony łuk na kole odcieni, zapisany jako „od–do” albo „środek ± połowa szerokości”, "
        "z zakazanymi przedziałami.",
        """Oba zapisy to ta sama wartość — zmiana jednego przelicza drugi. Więcej:
[zasada odcienia](help:concept.hue_arc), [zakazane przedziały](help:concept.exclusion).""",
        K,
    ),
    "rules.contrast_bg": Topic(
        "Kontrast z tłem",
        "Najmniejszy (i opcjonalnie największy) kontrast tego koloru z tłem, w jednostkach wybranej "
        "metryki.",
        """Zwykłe progi: 4.5 (WCAG) albo 60 (APCA). Więcej: [kontrast](help:concept.contrast).""",
        K,
    ),
    "rules.contrast_bg.metric": Topic(
        "Metryka tej zasady",
        "Zasada może liczyć kontrast metryką palety albo własną: WCAG 2.1 lub APCA.",
        """Przy „metryka palety” próg przelicza się razem ze zmianą metryki w ustawieniach całej palety.
Zmiana metryki tutaj ustawia próg startowy w nowych jednostkach.""",
        K,
    ),
    "rules.min_distance": Topic(
        "Odległość od innych akcentów",
        "Najmniejsza ΔE między tym akcentem a każdym innym. Para akcentów bierze ostrzejszy z ich "
        "dwóch progów.",
        """Para jest twarda, gdy twarda jest zasada któregokolwiek z dwóch akcentów. Skala progu zależy
od metody [ΔE](help:concept.delta_e).""",
        K,
    ),
    "rules.cvd_min_distance": Topic(
        "Odróżnialność (daltonizm)",
        "Najmniejsza ΔE między akcentami po symulacji typów daltonizmu wybranych w ustawieniach "
        "całej palety.",
        """Zasada działa tylko dla typów zaznaczonych w sekcji Daltonizm. Więcej:
[daltonizm](help:concept.cvd).""",
        K,
    ),
    "rules.extreme": Topic(
        "Skrajny kontrast",
        "Ten akcent ma mieć najsłabszy albo najmocniejszy kontrast z tłem spośród wszystkich "
        "akcentów.",
        """Przydatne dla koloru, który ma być najmniej albo najbardziej widoczny, np. komentarzy.""",
        K,
    ),
    "rules.scheme_use": Topic(
        "Układ odcieni: stosuj",
        "Czy ten akcent dostaje cel odcienia z układu odcieni całej palety. Cel może działać razem "
        "z własną zasadą odcienia.",
        """Obok widać wyliczony cel i tolerancję. Odznacz, gdy odcień tego akcentu ma wynikać tylko z jego
własnej zasady. Odnośnik prowadzi do [układu odcieni](help:rules.hues) w ustawieniach całej palety.""",
        K,
    ),
    # --- cała paleta ---------------------------------------------------------------------------
    "rules.palette": Topic(
        "Cała paleta",
        "Ustawienia wspólne dla wszystkich kolorów: metryki, układ odcieni, rozrzut jasności, "
        "daltonizm, unikane kolory i generowanie.",
        """Tu nie ma zasad pojedynczych kolorów — te ustawiasz po zaznaczeniu koloru na
[pasku](help:rules.strip).""",
        Z,
    ),
    "rules.metrics": Topic(
        "Metryki",
        "Czym program mierzy kontrast i odległość kolorów oraz jak ściąga do ekranu kolory spoza "
        "niego.",
        """Zmiana metryki kontrastu albo metody ΔE przelicza progi w zasadach kolorów i zależnościach,
które nie mają własnej metryki.""",
        Z,
    ),
    "rules.contrast_metric": Topic(
        "Metryka kontrastu",
        "WCAG 2.1 (stosunek 1–21) albo APCA (|Lc| do ok. 106). Progi kontrastu są w jej jednostkach.",
        """Więcej i przykład: [kontrast](help:concept.contrast).""",
        Z,
    ),
    "rules.delta_e": Topic(
        "Metoda ΔE",
        "Sposób liczenia odległości kolorów: ok, hyab, 2000, itp albo cam16. Każda ma własną skalę.",
        """Więcej i przykład: [ΔE](help:concept.delta_e).""",
        Z,
    ),
    "rules.fit": Topic(
        "Dopasowanie do gamutu",
        "Metoda, którą kolor spoza ekranu sRGB jest ściągany do najbliższego możliwego.",
        """Więcej i przykład dla każdej metody: [gamut](help:concept.gamut).""",
        Z,
    ),
    "rules.hues": Topic(
        "Układ odcieni",
        "Rozkłada cele odcieni dla akcentów: równo po kole, w wachlarzu, parami dopełniającymi "
        "albo według własnej listy.",
        """Akcent dostaje cel z układu, gdy ma włączone [„układ odcieni: stosuj”](help:rules.scheme_use).
Pola zależą od rodzaju układu; tolerancja mówi, o ile stopni akcent może odejść od celu.""",
        Z,
    ),
    "rules.hues.kind": Topic(
        "Rodzaj układu",
        "Jak rozłożyć odcienie akcentów: równo po kole, analogicznie, dopełniająco, w triadzie, "
        "tetradzie, z własnej listy albo wcale.",
        """„równo po kole” dzieli koło na tyle części, ile jest akcentów; „analogiczny” rozkłada je
w wachlarzu wokół środka; „własna lista” bierze odcienie z listy po kolei; „brak” wyłącza cele.""",
        Z,
    ),
    "rules.hues.rotation": Topic(
        "Obrót",
        "Odcień, od którego układ zaczyna rozkładać cele.",
        """Obrót przesuwa wszystkie cele o tę samą liczbę stopni.""",
        Z,
    ),
    "rules.hues.center": Topic(
        "Środek",
        "Środkowy odcień wachlarza w układzie analogicznym.",
        """Cele rozkładają się równo po obu stronach środka, w granicach rozpiętości.""",
        Z,
    ),
    "rules.hues.spread": Topic(
        "Rozpiętość",
        "Szerokość wachlarza odcieni w układzie analogicznym, w stopniach.",
        """Rozpiętość 90° wokół środka 220° daje cele od 175° do 265°.""",
        Z,
    ),
    "rules.hues.tol": Topic(
        "Tolerancja",
        "O ile stopni akcent może odejść od swojego celu, zanim powstanie naruszenie.",
        """Mała tolerancja trzyma odcienie blisko celów; duża daje silnikowi swobodę.""",
        Z,
    ),
    "rules.hues.jitter": Topic(
        "Rozrzut losowy",
        "Losowe przesunięcie każdego celu o najwyżej tyle stopni, zależne od ziarna.",
        """Zero daje zawsze te same cele. Większa wartość urozmaica palety między ziarnami.""",
        Z,
    ),
    "rules.hues.custom": Topic(
        "Własna lista odcieni",
        "Odcienie, które układ przydziela akcentom po kolei. Klik w koło dodaje odcień, wiersze "
        "można przestawiać i usuwać.",
        """Pierwszy akcent dostaje pierwszy odcień z listy, drugi — drugi i tak dalej; gdy akcentów jest
więcej niż pozycji, lista zaczyna się od początku z przesunięciem. Przeciąganie znacznika na kole
zmienia odcień, Alt+↑/↓ przestawia pozycję, Delete na ✕ ją usuwa.""",
        Z,
    ),
    "rules.hues.hard": Topic(
        "Układ twardy i waga",
        "Czy cele układu są zasadą twardą, czy miękką z podaną wagą.",
        """Domyślnie układ jest miękki: silnik trzyma się celów, ile się da.
Więcej: [twarde i miękkie](help:concept.hard_soft).""",
        Z,
    ),
    "rules.spread": Topic(
        "Rozrzut jasności akcentów",
        "Różnica między najjaśniejszym a najciemniejszym akcentem: najmniejsza i największa "
        "dozwolona.",
        """Górna granica wyrównuje jasność akcentów; dolna wymusza zróżnicowanie.""",
        Z,
    ),
    "rules.cvd": Topic(
        "Daltonizm",
        "Typy zaburzeń widzenia barw, metoda symulacji i nasilenie używane przez zasadę "
        "odróżnialności.",
        """Zasada „odróżnialność (daltonizm)” działa tylko dla zaznaczonych tu typów.
Więcej i przykład: [daltonizm](help:concept.cvd).""",
        Z,
    ),
    "rules.avoid": Topic(
        "Unikane kolory",
        "Lista kolorów, od których każdy akcent ma być odległy o co najmniej podaną ΔE ok. Zasada "
        "jest zawsze twarda.",
        """Kolor dodajesz kliknięciem w koło albo wpisując hex lub `oklch(...)`; jasność i nasycenie
zaznaczonej pozycji ustawiają suwaki. Tryb „charakter” na zakładce Źródło może wypełnić tę listę
kolorami palety źródłowej.""",
        Z,
    ),
    "rules.generation": Topic(
        "Generowanie",
        "Ile propozycji policzyć, z jakiego ziarna, ile pracy włożyć w każdą i na ilu wątkach.",
        """Te same ustawienia i ziarno dają te same propozycje, niezależnie od liczby wątków.""",
        Z,
    ),
    "rules.gen.n_proposals": Topic(
        "Liczba propozycji",
        "Ile palet silnik ma zwrócić w jednym generowaniu.",
        """Silnik liczy więcej przebiegów, niż zwraca propozycji, i wybiera najlepsze różniące się od
siebie.""",
        Z,
    ),
    "rules.gen.seed": Topic(
        "Ziarno",
        "Liczba wyznaczająca losowe starty. To samo ziarno i te same zasady dają te same propozycje.",
        """„🎲 losuj” wstawia nowe ziarno, czyli inny zestaw propozycji.""",
        Z,
    ),
    "rules.gen.budget": Topic(
        "Budżet",
        "Największa liczba ocen palety na jeden przebieg (jednego kandydata). Przebieg kończy się "
        "wcześniej, gdy już nic nie poprawia.",
        """Większy budżet pomaga przy trudnych, ciasnych zasadach; przy łatwych niczego nie zmienia.""",
        Z,
    ),
    "rules.gen.time_cap": Topic(
        "Limit czasu",
        "Bezpiecznik w sekundach. Po jego zadziałaniu propozycje są oznaczone jako niepowtarzalne.",
        """Pracę ogranicza budżet; limit czasu chroni tylko przed bardzo długim liczeniem.""",
        Z,
    ),
    "rules.gen.min_diversity": Topic(
        "Różnorodność",
        "Najmniejsza średnia ΔE ok między odpowiadającymi sobie kolorami dwóch propozycji.",
        """Propozycja zbyt podobna do już wybranych dostaje miękkie naruszenie „różnorodność”.""",
        Z,
    ),
    "rules.gen.hard_weight": Topic(
        "Waga twardych",
        "Mnożnik kary za naruszenie zasady twardej względem miękkiej.",
        """Domyślne 1000 sprawia, że silnik najpierw spełnia zasady twarde, a potem dopracowuje miękkie.
Więcej: [twarde i miękkie](help:concept.hard_soft).""",
        Z,
    ),
    "rules.gen.threads": Topic(
        "Wątki",
        "Na ilu wątkach procesora liczyć. 0 = wszystkie dostępne. Wynik nie zależy od tej liczby.",
        """Mniej wątków zostawia moc dla innych programów kosztem czasu generowania.""",
        Z,
    ),
}
