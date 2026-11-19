"""Pomoc: zakładka „Zasady” — preset, pasek kolorów, zasady kolorów, zależności, cała paleta.

Tematy z ``term=True`` trzymają się wzorca terminu („Co to jest” / „Przykład” z liczbami / „Kiedy
użyć”). Lista presetów w temacie ``rules.preset`` i wartości domyślne w tematach generowania są
brane z kodu przy imporcie, żeby pomoc nie rozjechała się z programem.
"""

from algopalette.gui.help_content.topic import Topic
from algopalette.migrate import BUDGET_DIVISOR
from algopalette.model import MAX_ACCENTS, OptimizerSettings
from algopalette.presets_builtin import BUILTIN, CATEGORIES

Z = "Zasady"
K = "Zasady koloru"

_OPT = OptimizerSettings()


def _preset_list() -> str:
    lines = []
    for category in CATEGORIES:
        items = [p for p in BUILTIN if p.category == category]
        if items:
            lines.append(f"**{category}**")
            lines += [f"- **{p.name}** — {p.description}" for p in items]
            lines.append("")
    return "\n".join(lines).rstrip()


TOPICS: dict[str, Topic] = {
    # --- zakładka, preset, pasek kolorów -------------------------------------------------------
    "rules.tab": Topic(
        "Zakładka Zasady (F2)",
        "Jedyne miejsce, w którym ustawiasz to, co wpływa na generowanie: zasady każdego koloru "
        "i ustawienia całej palety.",
        """Zakładka opisuje paletę, która dopiero ma powstać. Od góry:

1. [preset](help:rules.preset) i [tło](help:rules.polarity) — gotowy zestaw zasad na początek;
2. [liczba kolorów](help:rules.count);
3. [pasek kolorów](help:rules.strip) — wybierasz, czyje zasady edytujesz;
4. edytor zaznaczenia: [zasady kolorów](help:rules.editing) albo [cała paleta](help:rules.palette);
5. [Generuj propozycje](help:rules.generate) — zawsze widoczne na dole.

**Każdy kolor ma komplet własnych zasad.** To, co widzisz po zaznaczeniu koloru, to wszystko, co go
obowiązuje — nie ma wartości wspólnych, z których kolor coś by brał. Tę samą zmianę w wielu kolorach
robisz, zaznaczając je razem. Zasadę zdejmuje się jednym przyciskiem: **✕ usuń**.

Zmiany działają od razu, panel naruszeń na dole przelicza się na bieżąco, a Ctrl+Z cofa każdy krok.""",
        Z,
    ),
    "rules.preset": Topic(
        "Preset",
        "Gotowy zestaw zasad całej palety. Nałożenie zastępuje zasady wszystkich kolorów, układ "
        "odcieni i rozrzut jasności.",
        f"""Preset to nazwany zestaw zasad: tła, tekstu i akcentów (czasem z wyjątkami dla konkretnych
akcentów), układu odcieni i rozrzutu jasności; niektóre ustawiają też metrykę kontrastu.
[Zastosuj](help:rules.preset.apply) zastępuje nimi bieżące zasady. Preset **nie rusza** wartości
kolorów, kłódek, nazw, zależności, listy unikanych kolorów ani ustawień generowania.

Wszystko, co preset ustawił, widać niżej i można zmienić — wtedy przy nazwie pojawia się
[„(zmieniony)”](help:rules.preset.current). Własny zestaw zapiszesz przyciskiem
[Zapisz zasady jako preset](help:rules.preset.save).

**Presety wbudowane**

{_preset_list()}""",
        Z,
    ),
    "rules.preset.search": Topic(
        "Szukaj presetu",
        "Zawęża listę presetów do tych, których nazwa albo opis zawiera wpisany tekst (bez względu "
        "na wielkość liter i polskie znaki).",
        """Wpisz fragment nazwy albo opisu, np. „mgl” albo „zielen” — „chlodny” znajdzie „chłodny”. Lista
obok pokazuje tylko pasujące presety z wybranej [kategorii](help:rules.preset.category). Puste pole
pokazuje wszystkie.""",
        Z,
    ),
    "rules.preset.category": Topic(
        "Kategoria presetów",
        "Zawęża listę do jednej kategorii, np. Chłodne albo Pory dnia. „Własne” to presety "
        "zapisane przez ciebie.",
        """Presety wbudowane są podzielone na kategorie (ich spis jest w temacie
[Preset](help:rules.preset)). Kategoria i [wyszukiwarka](help:rules.preset.search) działają razem.""",
        Z,
    ),
    "rules.preset.list": Topic(
        "Lista presetów",
        "Presety pasujące do wyszukiwarki i kategorii. Podpowiedź pozycji mówi, co preset ustawia.",
        """Wybierz preset i naciśnij [Zastosuj](help:rules.preset.apply) — sam wybór z listy niczego nie
zmienia. Presety z dopiskiem „(własny)” zapisałeś sam; pozostałe są wbudowane. Po otwarciu zakładki
lista wskazuje bieżący preset.""",
        Z,
    ),
    "rules.preset.apply": Topic(
        "Zastosuj preset",
        "Zastępuje zasady wszystkich kolorów, układ odcieni i rozrzut jasności wybranym presetem. "
        "Ctrl+Z cofa.",
        """Preset wbudowany jest nakładany dla bieżącego [tła](help:rules.polarity) i bieżącej metryki
kontrastu (jego liczby zależą od obu). Jeśli preset nie ma wersji dla bieżącego tła, bierze swoją
i zmienia tło. Preset własny przywraca tło i metrykę, przy których go zapisano; zmiana metryki
przelicza wtedy progi w zależnościach.

Zasady, które miały kolory wcześniej, są zastępowane w całości — także te ustawione ręcznie.
Wyjątek: kolory z [kłódką zasad](help:rules.lock) zachowują swoje zasady i przełącznik „układ
odcieni: stosuj”. Wartości kolorów, kłódki, nazwy i zależności zostają. Nałożenie to jeden krok
cofania.""",
        Z,
    ),
    "rules.preset.current": Topic(
        "Bieżący preset i „(zmieniony)”",
        "Nazwa ostatnio nałożonego presetu. „(zmieniony)” znaczy, że zasady różnią się już od tego, "
        "co preset ustawia.",
        """Program porównuje bieżące zasady kolorów, przełączniki „układ odcieni: stosuj”, układ odcieni
i rozrzut jasności ze świeżo nałożonym presetem (dla bieżącego tła i metryki). Zmiana wartości
kolorów, kłódek, zależności czy ustawień generowania nie daje „(zmieniony)”, bo preset ich nie
ustawia. Kolory z [kłódką zasad](help:rules.lock) nie są porównywane — ich odstępstwo jest
zamierzone. „— (własne zasady)” oznacza, że żadnego presetu nie nałożono albo zdjął go tryb
z zakładki Źródło. Od tego oznaczenia zależy, co stanie się przy [zmianie tła](help:rules.polarity).""",
        Z,
    ),
    "rules.preset.save": Topic(
        "Zapisz zasady jako preset",
        "Zapisuje bieżące zasady wszystkich kolorów, układ odcieni, rozrzut jasności, tło i metrykę "
        "pod podaną nazwą.",
        """Wpisz nazwę w pole obok i naciśnij przycisk. Własny preset pamięta zasady **według pozycji
koloru** (tło, tekst, akcent 1, akcent 2…). Nałożony na paletę z większą liczbą akcentów powiela
zasady ostatniego zapisanego akcentu; na paletę mniejszą — bierze tylko początek. Zapisany preset
od razu staje się bieżącym. Nazwy presetów wbudowanych są zajęte; zapis pod istniejącą własną nazwą
ją nadpisuje. Presety leżą w `~/.config/algopalette/presets.json`.""",
        Z,
    ),
    "rules.preset.delete": Topic(
        "Usuń własny preset",
        "Usuwa z listy preset zapisany przez ciebie. Presetów wbudowanych nie da się usunąć.",
        """Usunięcie nie zmienia bieżących zasad — znika tylko pozycja z listy. Jeśli usunięty preset był
bieżącym, przy jego nazwie pojawi się „(zmieniony)”, bo nie ma już z czym porównywać.""",
        Z,
    ),
    "rules.polarity": Topic(
        "Tło: ciemne albo jasne",
        "Polaryzacja palety. Zakresy jasności w presetach zależą od niej, więc zmiana tła nakłada "
        "preset ponownie albo pyta, co zrobić.",
        """- **Zasady są świeżo nałożonym presetem** → program nakłada ten sam preset w wersji dla nowego
  tła i tyle.
- **Zasady są zmienione albo presetu nie ma** → program pyta: *zastąp zasady presetem* (bieżącym,
  a gdy go nie ma albo nie ma wersji dla tego tła — presetem „neutralny”), *zmień tylko oznaczenie
  tła* (zasady zostają, co do liczby) albo *anuluj*.

Samo oznaczenie tła trafia do eksportu dla PaletteBuildera i decyduje, którą wersję presetu nałoży
„Zastosuj”. Zasad kolorów nie przelicza — ciemny zakres jasności tła zostanie ciemny, dopóki go nie
zmienisz albo nie nałożysz presetu.""",
        Z,
    ),
    "rules.count": Topic(
        "Liczba kolorów",
        f"Paleta ma tło, tekst i od 1 do {MAX_ACCENTS} akcentów. „+” dodaje akcent z zasadami "
        "ostatniego, „−” usuwa ostatni.",
        f"""Nowa paleta ma 10 kolorów (8 akcentów); najmniej 3, najwięcej {MAX_ACCENTS + 2}. Pasek kolorów
podąża za liczbą.

- **+** dodaje akcent na końcu. Dostaje kopię zasad i przełącznika układu odcieni ostatniego akcentu,
  bez jego zależności — nie trzeba ustawiać go od zera.
- **−** usuwa ostatni akcent. Zależności innych kolorów, które go wskazywały, zostają i są oznaczone
  jako [zerwane](help:rel.broken).

Obie czynności to jeden krok cofania, bez pytania. Dowolny akcent (nie tylko ostatni) usuniesz albo
przestawisz na zakładce Paleta. Lista [układu odcieni](help:rules.hues) się nie zmienia: nowy akcent
bierze kolejny odcień z listy (gdy się skończyła — od początku), co widać w licznikach ×N.""",
        Z,
    ),
    "rules.strip": Topic(
        "Pasek kolorów",
        "Wybierasz, czyje zasady edytujesz: jeden kolor, kilka naraz albo całą paletę. Ctrl+klik "
        "dokłada kolor, Shift+klik zaznacza zakres.",
        """Każdy przycisk to jeden kolor z próbką bieżącej wartości i nazwą.

- **Klik** — zaznacza jeden kolor.
- **Ctrl+klik** — dokłada kolor do zaznaczenia albo go odejmuje (ostatniego zaznaczonego nie da się
  odjąć).
- **Shift+klik** — zaznacza zakres od ostatnio klikniętego koloru.
- **wszystkie akcenty** — zaznacza wszystkie akcenty naraz, z pominięciem tych z
  [kłódką zasad](help:rules.lock) (🔒 przy nazwie); gdy kłódkę mają wszystkie — zaznacza wszystkie.
- **cała paleta** — zamiast kolorów pokazuje [ustawienia wspólne](help:rules.palette).

Zmiana zasady trafia do **wszystkich** zaznaczonych kolorów jednym krokiem cofania — tak ustawia się
to samo w ośmiu akcentach bez ośmiu przejść ([edycja zbiorcza](help:rules.editing)).

**Klawiatura:** pasek jest jednym przystankiem Tab; ←/→ przenosi fokus po przyciskach, spacja
zaznacza kolor, Ctrl+spacja dokłada albo odejmuje, Ctrl+A zaznacza wszystkie akcenty.""",
        Z,
    ),
    "rules.editing": Topic(
        "Zasady zaznaczonych kolorów",
        "Wiersz na każdą zasadę, która dotyczy wszystkich zaznaczonych kolorów. Zmiana trafia do "
        "każdego z nich.",
        """Przy jednym zaznaczonym kolorze widzisz komplet jego zasad. Przy kilku — zasady, które dotyczą
**każdego** z nich: tło nie ma kontrastu z tłem, a odległość od innych akcentów i skrajny kontrast
mają tylko akcenty. Zaznaczysz tło i akcent — zobaczysz jasność, nasycenie
i odcień.

Stany wiersza:

- **zwykły** — wszystkie zaznaczone kolory mają tę zasadę identyczną; zmiana trafia do wszystkich;
- **[różne](help:rules.rule.mixed)** — kolory mają ją ustawioną inaczej (albo tylko część ją ma);
- **brak zasady** — żaden jej nie ma; [+ dodaj](help:rules.rule.add) nadaje ją wszystkim.

Pod zasadami akcentów jest przełącznik [układ odcieni: stosuj](help:rules.scheme_use), a na końcu
[zależności od innych kolorów](help:rel.overview) — te edytuje się przy jednym zaznaczonym kolorze.""",
        K,
    ),
    "rules.generate": Topic(
        "Generuj propozycje",
        "Uruchamia silnik dla wszystkich kolorów bez kłódki i przechodzi do zakładki Propozycje.",
        """To samo co Ctrl+G i przycisk na pasku narzędzi. Silnik szuka palet spełniających wszystkie
zasady naraz; wyniki oglądasz i przejmujesz na zakładce Propozycje. Ile propozycji i ile pracy —
ustawiasz w [generowaniu](help:rules.generation). Więcej: [generowanie](help:menu.generate).""",
        Z,
    ),
    "rules.palette_link": Topic(
        "Zasady tego koloru",
        "Przechodzi do zakładki Zasady z zaznaczonym tym kolorem.",
        """Zasady kolorów ustawia się tylko na zakładce [Zasady](help:rules.tab); ten odnośnik otwiera ją
na kolorze zaznaczonym na liście Palety.""",
        K,
    ),
    # --- wiersz zasady -------------------------------------------------------------------------
    "rules.rule.enabled": Topic(
        "Włączona",
        "Odznaczona zasada albo zależność zostaje zapamiętana, ale nie liczy się ani w silniku, ani "
        "w naruszeniach.",
        """Wyłączenie przydaje się do prób: sprawdzasz, co wyjdzie bez zasady, nie tracąc jej wartości.
Wyłączona zasada jasności, nasycenia albo odcienia wyłącza też swoje
[zakazane przedziały](help:concept.exclusion). Żeby pozbyć się zasady na dobre, użyj
[✕ usuń](help:rules.rule.remove).""",
        K,
    ),
    "rules.rule.hard": Topic(
        "Twarda",
        "Twarda zasada musi być spełniona; miękka jest celem z wagą.",
        """Propozycja łamiąca twardą zasadę dostaje oznaczenie ✗. Miękka zasada to życzenie: silnik
zbliża się do niej, ile się da, a naruszenie widać ze znakiem ~. Przykład z liczbami:
[twarde i miękkie](help:concept.hard_soft).""",
        K,
    ),
    "rules.rule.weight": Topic(
        "Waga",
        "Jak ważna jest miękka zasada wobec innych miękkich. Większa waga = silnik mniej chętnie "
        "z niej ustępuje.",
        """Waga działa dla zasad miękkich; dla twardych mnoży się jeszcze przez
[wagę twardych](help:rules.gen.hard_weight), więc w praktyce nie ma znaczenia. Przykład:
[twarde i miękkie](help:concept.hard_soft).""",
        K,
    ),
    "rules.rule.remove": Topic(
        "Usuń zasadę",
        "Zdejmuje zasadę z zaznaczonych kolorów. Kolor bez zasady nie jest w tym zakresie niczym "
        "ograniczony.",
        """Jedno słowo i jedna czynność: zasady nie ma, więc nic nie ogranicza koloru w tym zakresie —
nie wraca żadna „wartość domyślna”. Przy kilku zaznaczonych kolorach („✕ usuń u wszystkich”)
zdejmuje zasadę z każdego. Ctrl+Z przywraca.""",
        K,
    ),
    "rules.rule.add": Topic(
        "Dodaj zasadę",
        "Żaden z zaznaczonych kolorów nie ma tej zasady. „+ dodaj” nadaje ją wszystkim z wartością "
        "startową.",
        """Wartość startowa jest w jednostkach bieżącej metryki kontrastu i metody ΔE (np. kontrast 4.5
albo 60, odległość 0.08 albo jej odpowiednik); potem ustawiasz ją jak każdą inną. Nowa zasada jest
włączona i twarda.""",
        K,
    ),
    "rules.rule.mixed": Topic(
        "Różne wartości",
        "Zaznaczone kolory mają tę zasadę ustawioną inaczej (wartość, włączenie, twardość, waga "
        "albo sama obecność).",
        """Wiersz wypisuje, co ma każdy kolor, np. „akcent 1: 0.060–0.200 · akcent 2: 50–70% · miękka”;
„brak” znaczy, że kolor tej zasady nie ma. Dopóki wartości się różnią, nie ma jednego suwaka do
przesunięcia — najpierw wybierz:

- [ustaw dla zaznaczonych](help:rules.rule.unify) — wszystkie kolory dostają jedną zasadę;
- **usuń u wszystkich** — zasada znika z każdego.

Jeśli chcesz zostawić różnice, zaznacz kolory pojedynczo.""",
        K,
    ),
    "rules.rule.unify": Topic(
        "Ustaw dla zaznaczonych",
        "Nadaje wszystkim zaznaczonym kolorom tę samą zasadę — taką, jaką ma pierwszy zaznaczony "
        "kolor, który ją posiada.",
        """Kolejność to kolejność kolorów na pasku. Po ujednoliceniu wiersz zamienia się w zwykły edytor
i dalsze zmiany trafiają do wszystkich zaznaczonych kolorów. Całość to jeden krok cofania.""",
        K,
    ),
    "rules.lightness": Topic(
        "Jasność L",
        "Dozwolony zakres jasności koloru (0 = czerń, 1 = biel) i zakazane przedziały wewnątrz "
        "niego.",
        """Uchwyty na pasku ustawiają dolną i górną granicę; puste pole oznacza brak ograniczenia
z tej strony. Pasek jest gradientem pierwszego zaznaczonego koloru przy zmienianej jasności.

**„+ zakaz”** dodaje pod suwakiem [zakazany przedział](help:concept.exclusion) — wąski wycinek,
w którym kolor nie może się znaleźć (domyślnie 10% osi w środku największej wolnej luki). Zakaz
ma dwa pola „od–do” i przycisk ✕; na pasku jest zakreskowany.

Twardy zakres jasności jest dla silnika granicą poszukiwań, więc propozycje z niego nie wychodzą.
Jasność decyduje o kontraście — zbyt wąski zakres w połączeniu z wysokim
[kontrastem z tłem](help:rules.contrast_bg) bywa nie do spełnienia.""",
        K,
    ),
    "rules.chroma": Topic(
        "Nasycenie C",
        "Dozwolony zakres nasycenia — w jednostkach C albo jako procent największego nasycenia "
        "możliwego przy tej jasności i odcieniu.",
        """Tryb wybierasz z listy obok suwaka: [bezwzględne albo względne](help:rules.chroma.mode).
W trybie względnym 0.60 znaczy 60%.

Zakres może mieć [zakazane przedziały](help:concept.exclusion) („+ zakaz”), w jednostkach bieżącego
trybu. Twardy zakres nasycenia względnego jest dla silnika granicą poszukiwań; bezwzględny — wysoką
karą. Szare tło i tekst mają zwykle zakres bezwzględny 0–0.04. Przykład z liczbami i rysunkiem:
[nasycenie bezwzględne i względne](help:concept.chroma_modes).""",
        K,
    ),
    "rules.chroma.mode": Topic(
        "Tryb nasycenia",
        "Bezwzględne: zakres w jednostkach C. Względne: zakres jako część największego nasycenia, "
        "jakie ekran pokaże przy tej jasności i odcieniu.",
        """Zmiana trybu ustawia zakres startowy w nowej skali (0.05–0.15 bezwzględnie, 20–60% względnie)
i usuwa zakazane przedziały, bo były w starej skali. Przy zaznaczeniu kilku kolorów tryb zmienia się
u wszystkich. Przykład z liczbami: [nasycenie bezwzględne i względne](help:concept.chroma_modes).""",
        K,
    ),
    "rules.hue": Topic(
        "Odcień",
        "Dozwolony łuk na kole odcieni, zapisany jako „od–do” albo „środek ± połowa szerokości”, "
        "z zakazanymi przedziałami.",
        """Kolor ma **jedną** zasadę odcienia: łuk. Dwie pary pól pokazują tę samą wartość —
„od” i „do” przy pasku oraz „środek” i „±” obok; zmiana jednej pary przelicza drugą. „Od” większe
niż „do” to łuk przez 0°, a „od 0 do 360” to pełne koło.

**„+ zakaz”** wycina z łuku [zakazany przedział](help:concept.exclusion): „dowolny odcień od 0 do
270, ale nie 60–85 i nie 140–155”. Zakaz też może przechodzić przez 0°.

Twardy łuk jest dla silnika granicą poszukiwań. Akcent może mieć własny łuk i jednocześnie cel
z [układu odcieni](help:rules.scheme_use). Przy bardzo małym nasyceniu odcień przestaje być widoczny
i zasada słabnie. Więcej: [zasada odcienia](help:concept.hue_arc).""",
        K,
    ),
    "rules.contrast_bg": Topic(
        "Kontrast z tłem",
        "Najmniejszy (i opcjonalnie największy) kontrast tego koloru z tłem, w jednostkach wybranej "
        "metryki.",
        """Dolna granica pilnuje czytelności; górna (zwykle pusta) przydaje się dla kolorów, które mają
być stonowane, np. komentarzy. Zwykłe progi: 4.5 (WCAG) albo 60 (APCA) dla akcentów, 7 albo 75 dla
tekstu. Tło tej zasady nie ma.

Obok jest [metryka tej zasady](help:rules.contrast_bg.metric). Gdy tło ma kłódkę, silnik dopasowuje
do niego pozostałe kolory. Więcej i przykład: [kontrast](help:concept.contrast).""",
        K,
    ),
    "rules.contrast_bg.metric": Topic(
        "Metryka tej zasady",
        "Zasada może liczyć kontrast metryką palety albo własną: WCAG 2.1 lub APCA.",
        """Przy „metryka palety” próg przelicza się razem ze zmianą
[metryki kontrastu](help:rules.contrast_metric) w ustawieniach całej palety. Wybranie tu własnej
metryki ustawia próg startowy w jej jednostkach (4.5 dla WCAG, 60 dla APCA) i od tej pory zmiana
metryki palety tej zasady nie rusza.""",
        K,
    ),
    "rules.min_distance": Topic(
        "Odległość od innych akcentów",
        "Najmniejsza ΔE między tym akcentem a każdym innym. Para akcentów bierze ostrzejszy z ich "
        "dwóch progów.",
        """Zasada dotyczy par: dla każdej pary akcentów obowiązuje **większy** z ich dwóch progów, a para
jest twarda, gdy twarda jest zasada któregokolwiek z nich (waga — większa z dwóch). Wystarczy więc
ustawić zasadę w jednym akcencie, żeby odsunąć od niego wszystkie pozostałe. Tło i tekst w tym nie
uczestniczą.

Skala progu zależy od metody [ΔE](help:concept.delta_e): 0.08 w `ok` to wyraźna różnica. Zmiana
metody przelicza próg. Odległości par zobaczysz w macierzy ΔE na zakładce Analiza.""",
        K,
    ),
    "rules.extreme": Topic(
        "Skrajny kontrast",
        "Ten akcent ma mieć najsłabszy albo najmocniejszy kontrast z tłem spośród wszystkich "
        "akcentów.",
        """**Co to jest.** Zasada porównuje kontrast tego akcentu z tłem z kontrastem każdego innego akcentu.
„Najsłabszy” wymaga, żeby był mniejszy od wszystkich pozostałych, „najmocniejszy” — żeby był większy.

**Przykład.** Trzy akcenty mają z tłem kontrast 5.2, 6.0 i 7.1 (WCAG). Akcent z kontrastem 6.0
i zasadą „najsłabszy” łamie ją o 0.8: musiałby zejść poniżej 5.2. Ten sam akcent z zasadą
„najmocniejszy” łamie ją o 1.1, bo musiałby przekroczyć 7.1.

**Kiedy użyć.** „Najsłabszy” dla koloru, który ma schodzić na drugi plan (komentarze, numery linii);
„najmocniejszy” dla tego, który ma przyciągać wzrok (błędy, słowa kluczowe). Zasadę nadaj jednemu
akcentowi — dwa „najsłabsze” wykluczają się nawzajem.""",
        K,
        term=True,
    ),
    "rules.lock": Topic(
        "Kłódka zasad",
        "Chroni zasady zaznaczonych kolorów przed presetem: po nałożeniu innego presetu zostają "
        "takie, jak są.",
        """Kłódka zasad to coś innego niż kłódka na zakładce Paleta: tamta chroni **wartość** koloru przed
generowaniem, ta — jego **zasady** przed [presetem](help:rules.preset.apply). Kolor z kłódką ma 🔒
przy nazwie na pasku kolorów.

- **wyłączona** — preset zastępuje zasady koloru jak zwykle.
- **zasady (odcień dalej z układu palety)** — preset nie zmienia zasad koloru ani przełącznika
  „układ odcieni: stosuj”. Cel odcienia liczy jednak [układ odcieni](help:rules.hues) całej palety,
  a ten preset zmienia — więc cel akcentu może się przesunąć.
- **zasady + zamrożony cel odcienia** (tylko akcenty) — jak wyżej, a dodatkowo bieżący cel z układu
  („cel 70° ± 4°”) w chwili wyboru staje się własną [zasadą odcienia](help:rules.hue) akcentu
  (łuk 66–74°, twardość i waga z układu; gdy akcent miał już własny łuk — część wspólna obu),
  a „układ odcieni: stosuj” się wyłącza. Odcień nie zależy już od presetu; pozostałe akcenty dzielą
  układ między siebie.

Kłódka nie blokuje ręcznej edycji — zasady koloru z kłódką zmienisz jak każde inne. Zdjęcie kłódki
niczego nie przywraca (zamrożony łuk odcienia zostaje). „Wszystkie akcenty” pomija kolory z kłódką.
Tryb z zakładki Źródło zastępuje zasady wszystkich kolorów i zdejmuje kłódki. Przy zmianie
[tła](help:rules.polarity) z ponownym nałożeniem presetu kolory z kłódką też zachowują zasady —
także progi jasności dobrane do poprzedniego tła.""",
        K,
    ),
    "rules.scheme_use": Topic(
        "Układ odcieni: stosuj",
        "Czy ten akcent dostaje cel odcienia z układu odcieni całej palety. Cel może działać razem "
        "z własną zasadą odcienia.",
        """Układ odcieni wylicza cel dla **każdego** akcentu według jego pozycji; przełącznik decyduje
tylko, czy ten cel obowiązuje dany akcent. Obok widać wyliczony cel i tolerancję („cel 45° ± 15°”;
przy kilku zaznaczonych akcentach — cele po kolei).

- **Zaznaczony** — akcent ma trzymać się celu; jeśli ma też własną [zasadę odcienia](help:rules.hue),
  musi spełnić jedno i drugie (np. łuk 0–270 z zakazami i cel z układu).
- **Odznaczony** — odcień akcentu wynika tylko z jego własnej zasady (albo jest dowolny).
- **Kwadrat (częściowo)** — zaznaczone akcenty mają to ustawione różnie; klik włącza u wszystkich.

Twardość, wagę i tolerancję celu ustawia się raz, w [układzie odcieni](help:rules.hues) — odnośnik
obok prowadzi tam wprost.""",
        K,
    ),
    # --- zależności ----------------------------------------------------------------------------
    "rel.overview": Topic(
        "Zależności od innych kolorów",
        "Zasady względem innego koloru: różnica odcienia, jasności, nasycenia, kontrast, odległość ΔE "
        "albo mieszanka dwóch kolorów.",
        """Zależność wiąże zaznaczony kolor z innym kolorem palety (celem). Edytuje się ją przy **jednym**
zaznaczonym kolorze. Przykłady:

- „odcień przeciwny do akcentu 1” — odcień, `=`, 180, tol 15;
- „ciemniejszy od tekstu o co najmniej 0.1” — jasność, `≤`, −0.1;
- „nasycenie co najmniej jak akcent 2” — nasycenie, `× mnożnik`, `≥`, 1.0;
- „podobny do akcentu 3, ale nie identyczny” — dwie zależności odległości: `≥ 0.03` i `≤ 0.08`;
- „w połowie między akcentem 1 a 4” — mieszanka, t = 0.5, tol ΔE 0.02.

**Elementy wiersza:** [typ](help:rel.kind), [względem](help:rel.target), [operator](help:rel.op),
wartość (znaczenie zależy od typu), [tolerancja](help:rel.tol), [metryka](help:rel.metric) (kontrast
i odległość), [✕ usuń](help:rel.delete); pod spodem włączona / twarda / waga.

Zależność trzyma się koloru-celu, nie jego numeru. Po usunięciu celu zostaje oznaczona jako
[zerwana](help:rel.broken). Twarda/miękka i waga działają jak w zasadach
([twarde i miękkie](help:concept.hard_soft)). Presety zależności nie ruszają.""",
        K,
    ),
    "rel.add": Topic(
        "+ dodaj zależność",
        "Dodaje zależność względem pierwszego innego koloru (domyślnie: odcień = 180° ± 15). Potem "
        "wybierz typ i cel.",
        """Zobacz [zależności](help:rel.overview).""",
        K,
    ),
    "rel.delete": Topic(
        "✕ usuń zależność",
        "Usuwa tę zależność (Ctrl+Z cofa).",
        """Zobacz [zależności](help:rel.overview).""",
        K,
    ),
    "rel.broken": Topic(
        "⚠ zerwana",
        "Kolor, którego dotyczyła ta zależność, został usunięty. Zależność się nie liczy — wybierz "
        "nowy cel albo ją usuń.",
        """Zerwana zależność ma czerwoną ramkę. Wybranie nowego celu z listy naprawia ją od razu.
Ctrl+Z przywraca usunięty kolor, a wtedy zależność znów działa. Plik ze starszej wersji programu
z zerwaną zależnością wczytuje się razem z nią.""",
        K,
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

Zmiana typu ustawia wartość startową w jednostkach nowego typu i zdejmuje własną metrykę.""",
        K,
    ),
    "rel.target": Topic(
        "Względem (kolor-cel)",
        "Kolor, z którym porównujesz ten kolor. Lista obejmuje wszystkie inne kolory palety.",
        """Zależność trzyma się wybranego koloru, także po zmianie jego numeru. Cel może mieć kłódkę —
wtedy silnik dopasowuje tylko ten kolor.""",
        K,
    ),
    "rel.op": Topic(
        "Operator",
        "= (± tol): różnica równa wartości z tolerancją; ≥ co najmniej; ≤ co najwyżej.",
        """Przy `=` zależność jest spełniona, gdy różnica mieści się w wartość ± tol. Przy `≥` i `≤`
tolerancja nie jest używana. Znaczenie „różnicy” zależy od [typu](help:rel.kind).""",
        K,
    ),
    "rel.tol": Topic(
        "Tolerancja (tol)",
        "Dopuszczalne odchylenie od wartości przy operatorze „=”. W jednostkach typu zależności "
        "(stopnie, L, C, kontrast, ΔE).",
        """Przy `≥` i `≤` tolerancja nie ma znaczenia. Zbyt mała tolerancja przy zależności twardej potrafi
zablokować silnik — dla odcieni typowe jest 10–20°.""",
        K,
    ),
    "rel.metric": Topic(
        "Metryka zależności",
        "Dla kontrastu: WCAG albo APCA, dla odległości: metoda ΔE. „Metryka palety” = ustawienie "
        "całej palety.",
        """Wartość i tolerancja są w skali wybranej metryki ([kontrast](help:concept.contrast),
[ΔE](help:concept.delta_e)). Przy „metryka palety” / „metoda palety” zmiana ustawienia całej palety
przelicza wartość i tolerancję; przy własnej — nie.""",
        K,
    ),
    "rel.hue": Topic(
        "Zależność: odcień",
        "Różnica odcieni: odcień tego koloru minus odcień celu, najkrótszym łukiem (−180°…180°). "
        "180 = przeciwny, ±30 = sąsiedni.",
        """**Co to jest.** Zależność porównuje różnicę „odcień tego koloru − odcień celu”, liczoną
najkrótszym łukiem, z podaną wartością.

**Przykład.** Cel ma odcień 40°. `=` 180, tol 15 wymaga odcienia między 205° a 235° (dopełniający);
kolor o odcieniu 250° łamie zależność o 15°. `=` 30, tol 10 to „sąsiad” w stronę rosnących kątów
(60–80°), a `=` −30 — w drugą stronę (0–20°): znak ma znaczenie.

**Kiedy użyć.** Dla par, które mają trzymać się razem na kole niezależnie od tego, gdzie wylądują:
kolor ostrzeżenia naprzeciw koloru sukcesu, odcień nagłówków tuż obok słów kluczowych. Dla szarych
kolorów (C poniżej 0.02) zależność słabnie, bo ich odcienia nie widać.""",
        K,
        term=True,
    ),
    "rel.lightness": Topic(
        "Zależność: jasność",
        "Różnica jasności L: ten kolor minus cel. Ujemna = ciemniejszy od celu (np. ≤ −0.1 = "
        "ciemniejszy co najmniej o 0.1).",
        """**Co to jest.** Zależność porównuje „L tego koloru − L celu” z podaną wartością. Dodatnia różnica
znaczy „jaśniejszy od celu”, ujemna — „ciemniejszy”.

**Przykład.** Tekst ma L 0.92. Zależność `≤` −0.1 względem tekstu wymaga L najwyżej 0.82; kolor
o L 0.85 łamie ją o 0.03. Zależność `=` 0.03, tol 0.01 względem tła o L 0.18 wymaga L między
0.20 a 0.22.

**Kiedy użyć.** Gdy liczy się kolejność jasności, a nie konkretna liczba: tło paneli bocznych
odrobinę jaśniejsze od tła głównego, komentarze zawsze ciemniejsze od tekstu — także wtedy, gdy
silnik przesunie oba kolory.""",
        K,
        term=True,
    ),
    "rel.chroma": Topic(
        "Zależność: nasycenie",
        "„+ różnica”: C tego koloru minus C celu; „× mnożnik”: C tego koloru względem wartość × C "
        "celu. Bezwzględne albo względne C.",
        """**Co to jest.** Zależność porównuje nasycenie tego koloru z nasyceniem celu na dwa sposoby:
jako różnicę („+ różnica”) albo jako stosunek („× mnożnik”). Drugie pole wybiera, czy porównywane
jest C bezwzględne, czy [względne](help:concept.chroma_modes).

**Przykład.** Cel ma C 0.10. „+ różnica”, `≥` 0.02 wymaga C co najmniej 0.12. „× mnożnik”, `≥` 1.0
wymaga C co najmniej 0.10 (tyle co cel), a `≤` 0.5 — najwyżej 0.05 (połowa nasycenia celu); kolor
o C 0.08 łamie tę ostatnią o 0.03.

**Kiedy użyć.** „× mnożnik”, gdy chodzi o proporcję („tło podświetlenia o połowę mniej nasycone
niż akcent”); „+ różnica”, gdy o stały odstęp. Tryb względny wybierz, gdy kolory mają różne
odcienie i ich możliwości nasycenia mocno się różnią.""",
        K,
        term=True,
    ),
    "rel.contrast": Topic(
        "Zależność: kontrast",
        "Kontrast tego koloru na kolorze-celu jako tle — np. tekst na tle zaznaczenia, ikona na tle "
        "paska.",
        """**Co to jest.** Zależność mierzy kontrast tego koloru położonego na celu jako tle, w jednostkach
wybranej [metryki](help:rel.metric).

**Przykład.** Kolor podświetlenia wyszukiwania jest tłem, tekst leży na nim. Zależność tekstu:
kontrast, `≥` 4.5 (WCAG) względem podświetlenia. Jeśli wychodzi 3.8, naruszenie wynosi 0.7.
W APCA ten sam wymóg to `≥` 60.

**Kiedy użyć.** Gdy kolor ma być czytelny nie tylko na głównym tle: napis na pasku stanu, tekst
na zaznaczeniu, ikona na przycisku. Główne tło obsługuje zwykła zasada
[kontrast z tłem](help:rules.contrast_bg); tu podajesz każde inne tło. Wymagania par akcentów
sprawdzisz w macierzy kontrastu na zakładce Analiza.""",
        K,
        term=True,
    ),
    "rel.distance": Topic(
        "Zależność: odległość ΔE",
        "Jak bardzo ten kolor ma się różnić od celu. Dwie zależności (≥ i ≤) dają „podobny, ale nie "
        "identyczny”.",
        """**Co to jest.** Zależność porównuje odległość [ΔE](help:concept.delta_e) między tym kolorem
a celem z podaną wartością, metodą palety albo własną.

**Przykład.** W metodzie `ok`: `≥` 0.03 razem z `≤` 0.08 względem akcentu 3 daje kolor „podobny,
ale nie identyczny”. Kolor odległy o 0.10 łamie drugą zależność o 0.02, a odległy o 0.01 — pierwszą
o 0.02.

**Kiedy użyć.** Gdy zwykła zasada [odległość od innych akcentów](help:rules.min_distance) to za
mało: działa ona tylko między akcentami i tylko jako „co najmniej”. Zależność obejmuje dowolne
kolory (np. tło paneli wyraźnie inne od tła głównego) i pozwala też wymagać bliskości (`≤`).""",
        K,
        term=True,
    ),
    "rel.mix": Topic(
        "Zależność: mieszanka dwóch",
        "Kolor ma leżeć między celem a drugim kolorem: t = 0 — przy celu, 1 — przy drugim, 0.5 — "
        "w połowie (w OKLab). Tol ΔE = dopuszczalne odchylenie.",
        """**Co to jest.** Zależność wymaga, żeby kolor był mieszanką dwóch innych: celu i koloru z pola
„i”, w proporcji t. Mieszanka liczona jest w OKLab, czyli równo dla oka.

**Przykład.** Kolor zaznaczenia w połowie między tłem a akcentem: cel — tło, „i” — akcent,
t = 0.5, tol ΔE 0.02. Kolor odległy od punktu mieszanki o ΔE 0.05 łamie zależność o 0.03.
t = 0.3 daje kolor bliżej tła, t = 0.8 — bliżej akcentu.

**Kiedy użyć.** Dla kolorów pochodnych, które mają podążać za dwoma innymi: tło zaznaczenia,
ramka między tłem a tekstem, przygaszona wersja akcentu. Gdy któryś z dwóch kolorów zostanie
usunięty, zależność jest [zerwana](help:rel.broken).""",
        K,
        term=True,
    ),
    # --- cała paleta ---------------------------------------------------------------------------
    "rules.palette": Topic(
        "Cała paleta",
        "Ustawienia wspólne dla wszystkich kolorów: metryki, układ odcieni, rozrzut jasności, "
        "unikane kolory i generowanie.",
        """Tu są rzeczy, które nie należą do żadnego pojedynczego koloru:

- [metryki](help:rules.metrics) — czym mierzyć kontrast i odległość, jak dopasować do ekranu;
- [układ odcieni](help:rules.hues) — cele odcieni dla akcentów;
- [rozrzut jasności akcentów](help:rules.spread);
- [unikane kolory](help:rules.avoid);
- [generowanie](help:rules.generation) — liczba propozycji, ziarno, budżet, wątki.

Zasady pojedynczych kolorów ustawiasz po zaznaczeniu koloru na [pasku](help:rules.strip). Tło palety
(ciemne / jasne) jest w wierszu presetu.""",
        Z,
    ),
    "rules.metrics": Topic(
        "Metryki",
        "Czym program mierzy kontrast i odległość kolorów oraz jak ściąga do ekranu kolory spoza "
        "niego.",
        """Zmiana [metryki kontrastu](help:rules.contrast_metric) albo [metody ΔE](help:rules.delta_e)
przelicza progi w zasadach kolorów i zależnościach, które nie mają własnej metryki — zasady znaczą
potem mniej więcej to samo, w nowych jednostkach. [Dopasowanie do gamutu](help:rules.fit) niczego
nie przelicza.""",
        Z,
    ),
    "rules.contrast_metric": Topic(
        "Metryka kontrastu",
        "WCAG 2.1 (stosunek 1–21) albo APCA (|Lc| do ok. 106). Progi kontrastu są w jej jednostkach.",
        """Zmiana przelicza progi zasad „kontrast z tłem” i zależności kontrastu według par 4.5 ↔ 60,
7 ↔ 75 (wartości pośrednie proporcjonalnie). Zasady z własną metryką zostają. Po zmianie przy
presecie pojawi się „(zmieniony)”, jeśli jego liczby dla nowej metryki są inne niż przeliczone.
Więcej i przykład: [kontrast](help:concept.contrast).""",
        Z,
    ),
    "rules.delta_e": Topic(
        "Metoda ΔE",
        "Sposób liczenia odległości kolorów: ok, hyab, 2000, itp albo cam16. Każda ma własną skalę.",
        """Metody: `ok` (domyślna, OKLab, skala ok. 0–1), `hyab` (OKLab, osobno jasność i barwa),
`2000` (CIEDE2000, ok. 0–100), `itp` (ICtCp), `cam16` (CAM16-UCS). Zmiana przelicza progi odległości
w zasadach kolorów i zależnościach bez własnej metody; odległość
[unikanych kolorów](help:rules.avoid) zostaje, bo zawsze jest w `ok`. Silnik liczy każdą metodę
dokładnie; `2000` i `cam16` wydłużają generowanie. Więcej i przykład: [ΔE](help:concept.delta_e).""",
        Z,
    ),
    "rules.fit": Topic(
        "Dopasowanie do gamutu",
        "Metoda, którą kolor spoza ekranu sRGB jest ściągany do najbliższego możliwego.",
        """Metody: `oklch-chroma` (domyślna), `raytrace`, `minde-chroma`, `lch-chroma`, `scale`, `clip`.
Dotyczy kolorów wpisanych ręcznie albo wklejonych — silnik generuje wyłącznie kolory mieszczące się
w sRGB. Hex, naruszenia, Analiza i eksport używają koloru po dopasowaniu. Co robi każda metoda
i przykład: [gamut](help:concept.gamut).""",
        Z,
    ),
    "rules.hues": Topic(
        "Układ odcieni",
        "Lista odcieni na kole — cele dla akcentów. Mono, triada, kwadrat i inne harmonie "
        "wstawiają punkty na tę listę.",
        """Układ to **lista odcieni** widoczna na kole. Akcenty biorą je po kolei i wracają do początku,
gdy akcentów jest więcej niż odcieni: przy 3 odcieniach i 8 akcentach odcienie dostają 3, 3 i 2
akcenty (licznik **×N** przy każdym wierszu). Akcenty jednego odcienia różnią się jasnością
i nasyceniem. Pusta lista = brak celów.

Cel obowiązuje akcent, gdy ten ma włączone [„układ odcieni: stosuj”](help:rules.scheme_use) —
niezależnie od tego, czy ma własną zasadę odcienia. Tła i tekstu układ nie dotyczy.

Harmonie wstawiasz przyciskami [„wstaw”](help:rules.hues.generate), całość przesuwa
[„obróć wszystkie”](help:rules.hues.rotate), a pojedyncze punkty zmieniasz w
[wybieraku](help:rules.hues.custom). Do tego [tolerancja](help:rules.hues.tol),
[rozrzut losowy](help:rules.hues.jitter) oraz [twardy / waga](help:rules.hues.hard).

Wyliczone cele widać przy każdym akcencie w jego zasadach i na kole w Analizie (pomarańczowy łuk).""",
        Z,
    ),
    "rules.hues.generate": Topic(
        "Wstaw harmonię",
        "Zastępuje listę układem zbudowanym od odcienia bazowego: zaznaczonego punktu, a bez "
        "zaznaczenia — pierwszego (pusta lista: 25°).",
        """**Co to jest.** Jednorazowe wstawienie: przycisk liczy odcienie i zastępuje nimi listę. Lista
nie pamięta, czym była — dalej możesz przeciągać pojedyncze punkty. Ctrl+Z cofa wstawienie.

**Przykład.** Baza 30°:

- **mono** → 30° (wszystkie akcenty w jednym odcieniu);
- **analogiczny** (pyta o liczbę punktów i rozpiętość; 3 punkty, 60°) → 0°, 30°, 60°;
- **dopełniający** → 30°, 210°;
- **rozszczepiony** (dopełniający) → 30°, 180°, 240°;
- **triada** → 30°, 150°, 270°;
- **kwadrat** → 30°, 120°, 210°, 300°;
- **prostokąt** → 30°, 90°, 210°, 270° (dwie pary dopełniające);
- **równo po kole** (pyta o liczbę punktów; domyślnie tyle, ile akcentów) → 4 punkty: 30°, 120°,
  210°, 300°;
- **z bieżących kolorów** → odcienie obecnych akcentów; bliskie (do 25°) łączą się w jeden punkt,
  kolejność jak akcentów, szare są pomijane.

**Kiedy użyć.** Mono i analogiczny dla spójnych, stonowanych palet; dopełniający, triada, kwadrat
i prostokąt dla wyraźnych kontrastów barw; równo po kole, gdy każdy akcent ma być inny; z bieżących
kolorów, gdy paleta już ci się podoba i chcesz ją utrwalić jako układ.""",
        Z,
        term=True,
    ),
    "rules.hues.rotate": Topic(
        "Obróć wszystkie",
        "Przesuwa całą listę odcieni o tę samą liczbę stopni, np. całą triadę.",
        """Przesunięcie liczy się od listy sprzed obrotu: przy liście 30°, 150°, 270° ustawienie +20 daje
50°, 170°, 290°, a −40 — 350°, 110°, 230°. Każda inna zmiana listy (wstawienie, klik w koło)
zeruje suwak. Jeden gest suwaka = jeden krok cofania.""",
        Z,
    ),
    "rules.hues.tol": Topic(
        "Tolerancja",
        "O ile stopni akcent może odejść od swojego celu, zanim powstanie naruszenie.",
        """**Co to jest.** Tolerancja to połowa szerokości pasa wokół celu, w którym odcień akcentu jest
w porządku.

**Przykład.** Cel 90° i tolerancja 15°: odcienie od 75° do 105° nie dają naruszenia; odcień 110°
łamie układ o 5°. Przy tolerancji 5° ten sam odcień łamałby go o 15°.

**Kiedy użyć.** 10–20° dla zwykłych palet: daje silnikowi miejsce na pogodzenie odcieni
z kontrastem i odległościami. Mała (5°), gdy odcienie mają być dokładne, np. z własnej listy.
Duża (30° i więcej), gdy układ ma tylko z grubsza porządkować koło.""",
        Z,
        term=True,
    ),
    "rules.hues.jitter": Topic(
        "Rozrzut losowy",
        "Losowe przesunięcie każdego celu o najwyżej tyle stopni, zależne od ziarna.",
        """**Co to jest.** Każdy cel układu zostaje przesunięty o losową liczbę stopni z przedziału
od −rozrzut do +rozrzut. Losowanie zależy od [ziarna](help:rules.gen.seed).

**Przykład.** Cel 90° przy rozrzucie 10° staje się jakimś odcieniem między 80° a 100° — przy ziarnie
0 zawsze tym samym, przy ziarnie 1 innym. Rozrzut 0° daje dokładnie 90° przy każdym ziarnie.

**Kiedy użyć.** Zostaw 0, gdy chcesz, żeby zmiana ziarna zmieniała tylko dobór kolorów wokół
stałych celów. Ustaw 5–15°, gdy kolejne ziarna mają dawać palety o wyraźnie innym rozkładzie
odcieni, bez ręcznego obracania listy.""",
        Z,
        term=True,
    ),
    "rules.hues.custom": Topic(
        "Lista odcieni",
        "Odcienie, które układ przydziela akcentom po kolei. Klik w koło dodaje odcień, wiersze "
        "można przestawiać i usuwać; ×N mówi, ile akcentów bierze odcień.",
        f"""Pierwszy akcent dostaje pierwszy odcień z listy, drugi — drugi i tak dalej. Gdy akcentów jest
więcej niż pozycji, lista zaczyna się od początku (bez przesunięć): 3 odcienie i 8 akcentów →
×3, ×3, ×2. Pozycja ×0 (lista dłuższa niż liczba akcentów albo akcenty bez „stosuj”) jest
wyszarzona — zacznie działać po dodaniu akcentu. Lista mieści najwyżej {MAX_ACCENTS} pozycji.

**Obsługa wybieraka**

- **klik w koło** — dodaje odcień (zaokrąglony do 1°) na koniec listy;
- **przeciąganie znacznika** na kole — zmienia odcień tej pozycji;
- **pole liczbowe** w wierszu — dokładna wartość; Enter zatwierdza;
- **przeciąganie próbki** w wierszu albo **Alt+↑ / Alt+↓** — zmienia kolejność;
- **✕** albo **Delete** na tym przycisku — usuwa pozycję;
- **+ dodaj** — wstawia odcień w środku największej przerwy na kole.

Zaznaczona pozycja jest podświetlona w liście i ma większy znacznik na kole. Kolejność ma znaczenie:
decyduje, który akcent dostanie który odcień.""",
        Z,
    ),
    "rules.hues.hard": Topic(
        "Układ twardy i waga",
        "Czy cele układu są zasadą twardą, czy miękką z podaną wagą.",
        """Domyślnie układ jest miękki: silnik trzyma się celów, ile się da, ale ustąpi kontrastowi
i odległościom. Twardy układ wymusza cele (z tolerancją) i potrafi uczynić paletę niespełnialną,
gdy koliduje z twardymi zasadami kolorów. Waga działa jak w zasadach:
[twarde i miękkie](help:concept.hard_soft).""",
        Z,
    ),
    "rules.spread": Topic(
        "Rozrzut jasności akcentów",
        "Różnica między najjaśniejszym a najciemniejszym akcentem: najmniejsza i największa "
        "dozwolona.",
        """**Co to jest.** Rozrzut to „największa jasność L wśród akcentów minus najmniejsza”. Zasada
ogranicza go z góry, z dołu albo z obu stron.

**Przykład.** Akcenty mają L od 0.62 do 0.84, więc rozrzut wynosi 0.22. Zasada „najwyżej 0.12”
jest naruszona o 0.10 — akcenty muszą zbliżyć się jasnością. Zasada „co najmniej 0.25” jest
naruszona o 0.03 — muszą się rozsunąć.

**Kiedy użyć.** Górna granica (np. 0.12) dla spokojnych palet, w których żaden akcent nie
wybija się jasnością. Dolna (np. 0.25) dla palet o jednym odcieniu, gdzie akcenty mają się różnić
właśnie jasnością. Zasada może być twarda albo miękka z wagą; przy jednym akcencie nic nie robi.""",
        Z,
        term=True,
    ),
    "rules.avoid": Topic(
        "Unikane kolory",
        "Lista kolorów, od których każdy akcent ma być odległy o co najmniej podaną ΔE ok. Zasada "
        "jest zawsze twarda.",
        """Przydaje się, gdy pewne kolory są zajęte (barwy innego motywu, kolory firmowe konkurencji) albo
gdy chcesz paletę „w tym samym stylu, ale inną” — tryb „charakter” na zakładce Źródło potrafi
wpisać tu akcenty palety źródłowej.

**Obsługa wybieraka**

- **klik w koło** — dodaje kolor o klikniętym odcieniu;
- **suwaki jasności i nasycenia** — ustawiają zaznaczoną pozycję;
- **pole „kolor”** — przyjmuje hex albo `oklch(...)`; Enter podmienia zaznaczoną pozycję, a gdy nic
  nie jest zaznaczone — dodaje nową;
- przestawianie i usuwanie jak we [własnej liście odcieni](help:rules.hues.custom).

**Najmniejsza odległość** jest zawsze w ΔE `ok`, niezależnie od metody palety; 0.05 to mało,
0.10 — wyraźnie inny kolor. Dodanie pierwszego koloru przy odległości 0 ustawia ją na 0.05, bo
inaczej lista nic by nie robiła. Zasada dotyczy tylko akcentów.""",
        Z,
    ),
    "rules.generation": Topic(
        "Generowanie",
        "Ile propozycji policzyć, z jakiego ziarna, ile pracy włożyć w każdą i na ilu wątkach.",
        """- [liczba propozycji](help:rules.gen.n_proposals) — ile palet zobaczysz;
- [ziarno](help:rules.gen.seed) — który zestaw losowych startów;
- [budżet](help:rules.gen.budget) — ile pracy na jednego kandydata;
- [limit czasu](help:rules.gen.time_cap) — bezpiecznik;
- [różnorodność](help:rules.gen.min_diversity) — jak bardzo propozycje mają się różnić;
- [waga twardych](help:rules.gen.hard_weight);
- [wątki](help:rules.gen.threads).

Te same zasady, ustawienia i ziarno dają te same propozycje — niezależnie od liczby wątków
i szybkości komputera (o ile nie zadziała limit czasu). Presety tych ustawień nie ruszają.""",
        Z,
    ),
    "rules.gen.n_proposals": Topic(
        "Liczba propozycji",
        "Ile palet silnik ma zwrócić w jednym generowaniu.",
        f"""Domyślnie {_OPT.n_proposals}. Silnik liczy więcej niezależnych przebiegów, niż zwraca
propozycji (dla 6 propozycji — 10), i wybiera z nich najlepsze, które różnią się od siebie co
najmniej o [różnorodność](help:rules.gen.min_diversity). Przebiegi idą równolegle na wszystkich
rdzeniach, więc nawet ponad sto propozycji liczy się w sekundy.""",
        Z,
    ),
    "rules.gen.seed": Topic(
        "Ziarno",
        "Liczba wyznaczająca losowe starty. To samo ziarno i te same zasady dają te same propozycje.",
        """**Co to jest.** Silnik zaczyna każdy przebieg od losowych kolorów. Ziarno to numer zestawu tych
losowań: ten sam numer daje zawsze te same starty, a więc te same propozycje.

**Przykład.** Ziarno 0 i 6 propozycji: dziś, jutro i na innym komputerze dostaniesz tę samą szóstkę.
Ziarno 1 daje inną szóstkę, równie dobrą — innych kolorów spełniających te same zasady.
„🎲 losuj” wstawia przypadkowe ziarno.

**Kiedy użyć.** Zmień ziarno, gdy propozycje ci się nie podobają, a zasady są takie, jak chcesz —
to najtańszy sposób na „pokaż coś innego”. Zostaw je, gdy poprawiasz zasady i chcesz zobaczyć
skutek samej poprawki. Ziarno steruje też [rozrzutem losowym](help:rules.hues.jitter) układu odcieni.""",
        Z,
        term=True,
    ),
    "rules.gen.budget": Topic(
        "Budżet",
        "Największa liczba ocen palety na jeden przebieg (jednego kandydata). Przebieg kończy się "
        "wcześniej, gdy już nic nie poprawia.",
        f"""**Co to jest.** Jeden przebieg silnika wielokrotnie ocenia paletę i poprawia ją w stronę
spełnienia zasad. Budżet to górna granica liczby takich ocen na jednego kandydata. Gdy paleta
przestaje się poprawiać, przebieg kończy się wcześniej.

**Przykład.** Domyślny budżet to {_OPT.budget}. Przy łatwych zasadach (preset „neutralny”) przebieg
kończy po kilkudziesięciu–kilkuset ocenach i większy budżet niczego nie zmienia. Przy ciasnych
(wąskie zakresy, wiele zależności) budżet 300 może uciąć szukanie, zanim silnik znajdzie
paletę bez twardych naruszeń, a 10 000 da mu czas.

**Kiedy użyć.** Zwiększ, gdy propozycje mają twarde naruszenia, a zasady wyglądają na spełnialne.
Zmniejsz, gdy generujesz setki propozycji i liczy się czas. W starszych wersjach programu budżet
liczył inne, tańsze oceny, więc pliki z nich mają tę wartość przeliczoną (÷ {BUDGET_DIVISOR}).""",
        Z,
        term=True,
    ),
    "rules.gen.time_cap": Topic(
        "Limit czasu",
        "Bezpiecznik w sekundach (0 = bez limitu). Po jego zadziałaniu propozycje są oznaczone jako "
        "niepowtarzalne.",
        f"""Domyślnie {_OPT.time_cap_s:g} s na całe generowanie; **0 wyłącza limit**. Pracę ogranicza
[budżet](help:rules.gen.budget); limit czasu chroni tylko przed bardzo długim liczeniem przy
skrajnych ustawieniach. Gdy zadziała, silnik oddaje propozycje z przebiegów, które zdążył
**ukończyć** (przebieg przerwany w połowie nie daje propozycji), a **wszystkie** propozycje tej
generacji dostają stan ⏱ — wynik zależał od szybkości komputera, więc to samo ziarno może dać
następnym razem coś innego. Zbyt krótki limit może nie dać żadnej propozycji — status to powie.""",
        Z,
    ),
    "rules.gen.min_diversity": Topic(
        "Różnorodność",
        "Najmniejsza średnia ΔE ok między odpowiadającymi sobie kolorami dwóch propozycji.",
        f"""**Co to jest.** Dwie propozycje porównuje się kolor po kolorze (akcent 1 z akcentem 1 i tak dalej,
tylko kolory bez kłódki); różnorodność to średnia z tych odległości ΔE `ok`. Silnik wybiera
propozycje tak, żeby każde dwie różniły się co najmniej o podaną wartość.

**Przykład.** Przy różnorodności {_OPT.min_diversity:g} dwie palety, których kolory różnią się średnio
o 0.03, są „za podobne”: druga dostaje miękkie naruszenie „różnorodność” o 0.02. Gdy takich
propozycji brakuje, silnik liczy jeszcze dwie fale przebiegów odpychanych od już wybranych, a potem
dopełnia listę najlepszymi z pozostałych.

**Kiedy użyć.** Zwiększ (0.08–0.12), gdy propozycje wyglądają jak warianty tej samej palety.
Zmniejsz albo ustaw 0, gdy zasady są tak ciasne, że różnych palet po prostu nie ma — naruszenie
„różnorodność” jest wtedy tylko informacją.""",
        Z,
        term=True,
    ),
    "rules.gen.hard_weight": Topic(
        "Waga twardych",
        "Mnożnik kary za naruszenie zasady twardej względem miękkiej.",
        f"""**Co to jest.** Silnik ocenia paletę jedną liczbą: sumą kar za naruszenia. Kara za naruszenie
twardej zasady jest mnożona przez wagę twardych.

**Przykład.** Przy wadze {_OPT.hard_weight:g} złamanie twardej zasady jasności o 0.01 kosztuje tyle,
co złamanie tysiąca miękkich zasad o tę samą wielkość — silnik najpierw usuwa twarde naruszenia,
a dopiero potem dopracowuje miękkie cele. Przy wadze 10 chętniej zostawi drobne twarde naruszenie,
żeby lepiej spełnić cele miękkie.

**Kiedy użyć.** Prawie nigdy nie trzeba jej zmieniać. Zmniejsz (do 100), gdy twarde zasady są
spełnione, ale miękkie wychodzą wyraźnie gorzej, niż mogłyby. Zwiększ, gdy propozycje mają maleńkie
twarde naruszenia przy dużej liczbie miękkich zasad o wysokich wagach.""",
        Z,
        term=True,
    ),
    "rules.gen.threads": Topic(
        "Wątki",
        "Na ilu wątkach procesora liczyć. 0 = wszystkie dostępne. Wynik nie zależy od tej liczby.",
        """Wartość 0 oznacza wszystkie rdzenie procesora. Przebiegi silnika są niezależne, więc liczą się
równolegle — na ośmiu rdzeniach mniej więcej
osiem razy szybciej niż na jednym. Mniejsza liczba zostawia moc innym programom kosztem czasu
generowania. Propozycje są identyczne przy każdej liczbie wątków: każdy przebieg ma własny,
z góry wyznaczony ciąg losowań, a o kolejności wyniku decydują numery przebiegów, nie to, który
skończył pierwszy.""",
        Z,
    ),
}
