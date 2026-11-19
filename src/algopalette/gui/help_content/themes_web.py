"""Pomoc: okno „Motywy z sieci” — przeglądanie i import gotowych motywów kolorów."""

from algopalette.gui.help_content.topic import Topic

G = "Motywy z sieci"

TOPICS: dict[str, Topic] = {
    "themes.window": Topic(
        "Motywy z sieci",
        "Przeglądarka gotowych motywów kolorów z internetu. Wybrany motyw staje się bieżącą paletą; "
        "na dysk trafia dopiero po „Zapisz”.",
        """Okno pobiera katalogi czterech źródeł i pokazuje je jako listę z próbkami oraz dużym
podglądem. „Wczytaj” zamienia bieżącą paletę na wybrany motyw — to jeden krok cofania, więc
**Ctrl+Z** przywraca poprzednią paletę razem z jej ustawieniami i kłódkami.

Import niczego nie zapisuje: otwarty plik sesji zostaje ten sam, a motyw trafia na dysk dopiero
po [Zapisz](help:menu.file.save) albo [Zapisz jako…](help:menu.file.save_as). Okno jest
niemodalne — możesz wczytywać kolejne motywy i od razu oglądać je w zakładkach Paleta i Analiza.

Źródła:
- **base16 / base24** ([tinted-theming](https://github.com/tinted-theming/schemes)) — schematy
  z jawnymi rolami: `base00` tło, `base05` tekst, `base08`–`base0F` (i w base24 `base12`–`base17`)
  akcenty;
- **Gogh** i **Windows Terminal** — motywy terminali: tło, tekst i kolory ANSI (czerwony, zielony,
  żółty, niebieski, magenta, cyjan i ich jasne odmiany; czerń i biel ANSI są pomijane, bo dublują
  tło i tekst);
- **[Lospec](https://lospec.com/palette-list)** — palety pixel-artu do 16 kolorów, bez ról: tłem
  zostaje kolor najciemniejszy (albo najjaśniejszy — [Tło jasne](help:themes.light_bg)), tekstem
  kolor najbardziej z nim kontrastujący.

Powtórzone kolory są usuwane, więc motyw może mieć mniej akcentów, niż podaje źródło.

To co innego niż [Widok → Motyw](help:menu.view.theme), który zmienia tylko wygląd okna programu.""",
        G,
    ),
    "themes.search": Topic(
        "Szukaj",
        "Zawęża listę do motywów, których nazwa albo autor zawiera wpisany tekst (bez znaczenia "
        "wielkości liter i polskich znaków).",
        """Dla źródeł base16, Gogh i Windows Terminal szukanie działa na pobranym katalogu, od razu.
Dla **Lospec** tekst trafia do serwisu jako **tag** — liczy się pierwsze słowo, małymi literami
(np. `warm`, `gameboy`, `pastel`). Puste pole pokazuje palety Lospec najczęściej pobierane.""",
        G,
    ),
    "themes.source": Topic(
        "Źródło",
        "Skąd brać motywy. „Wszystkie” łączy base16, Gogh i Windows Terminal; Lospec wybierasz "
        "osobno, bo jego lista przychodzi stronami z serwera.",
        """Katalog źródła pobiera się przy pierwszym wyborze i trafia do pamięci podręcznej
(`~/.cache/algopalette/themes/`), więc później lista otwiera się od razu, także bez internetu.
Opis źródeł: [Motywy z sieci](help:themes.window).""",
        G,
    ),
    "themes.bg": Topic(
        "Tło",
        "Pokazuje wszystkie motywy albo tylko ciemne lub tylko jasne — według jasności tła.",
        """Motyw jest ciemny, gdy jasność tła (L w OKLCH) jest mniejsza niż 0,5. Etykieta „dark/light”
podawana przez źródło jest pomijana, bo bywa niezgodna z faktycznym tłem. Palety Lospec nie mają
tła z góry — filtr „jasne” sprawia, że tłem zostaje ich najjaśniejszy kolor, i niczego nie ukrywa.""",
        G,
    ),
    "themes.list": Topic(
        "Lista motywów",
        "Motywy wybranego źródła: nazwa, źródło i próbki kolorów (tło, tekst, akcenty). "
        "Dwuklik albo Enter wczytuje motyw.",
        """Zaznaczony motyw pokazuje się w [podglądzie](help:themes.preview). Lista wyświetla motywy
porcjami; kolejne dokłada przycisk [Więcej](help:themes.more).""",
        G,
    ),
    "themes.more": Topic(
        "Więcej",
        "Dokłada do listy kolejną porcję motywów (dla Lospec — kolejną stronę z serwera).",
        """Przycisk znika, gdy pokazano już wszystko, co pasuje do wyszukiwania i filtrów.""",
        G,
    ),
    "themes.preview": Topic(
        "Podgląd",
        "Kawałek terminala i kodu w kolorach zaznaczonego motywu, a pod nim wszystkie jego kolory "
        "z rolami.",
        """Podgląd rysuje się kolorami motywu niezależnie od [motywu okna](help:menu.view.theme).
Akcenty schematów base16/base24 grają swoje kanoniczne role (np. `base0E` słowa kluczowe,
`base0B` napisy); w pozostałych motywach role dostają kolejne akcenty. Jeśli motywu nie da się
użyć (np. paleta Lospec ma za mało różnych kolorów), podgląd mówi dlaczego, a „Wczytaj” jest
wyłączone.""",
        G,
    ),
    "themes.light_bg": Topic(
        "Tło jasne",
        "Tylko Lospec: tłem zostaje najjaśniejszy kolor palety zamiast najciemniejszego.",
        """Palety Lospec nie mówią, który kolor jest tłem. Domyślnie tłem jest najciemniejszy,
a tekstem kolor najbardziej z nim kontrastujący (w metryce kontrastu bieżącej palety). Zaznacz,
żeby zbudować jasny motyw z tej samej palety.""",
        G,
    ),
    "themes.keep_settings": Topic(
        "Nie zmieniaj ustawień palety",
        "Zaznaczone: import wymienia tylko kolory. Odznaczone (domyślnie): ustawienia i zasady "
        "dopasowują się do motywu.",
        """**Odznaczone** — motyw ustawia paletę „pod siebie”: każdy kolor (tło, tekst, każdy akcent)
dostaje własne zasady wokół swojej wartości z motywu — odcień w granicach
[swobody wariantów](help:themes.spread), jasność i nasycenie blisko oryginału, kontrast z tłem nie
niższy niż w motywie. Polaryzacja wynika z jasności tła, [układ odcieni](help:rules.hues) zostaje
wyłączony (każdy kolor ma własny łuk odcienia). Generowanie daje więc warianty tego motywu, a sam
motyw spełnia wszystkie zasady. Metryka kontrastu, ΔE, dopasowanie do gamutu, kolory do unikania
i optymalizator zostają.

**Zaznaczone** — zmieniają się tylko kolory i ich liczba; ustawienia palety i zasady wszystkich
kolorów zostają. Jeśli motyw ma inną polaryzację niż paleta, [panel naruszeń](help:window.violations)
to pokaże.

**W obu trybach** kolory z [kłódką zasad](help:rules.lock) zachowują swoje zasady, przełącznik
„układ odcieni: stosuj” i zależności — dostają tylko nową wartość. Przy kłódce „zasady” cel
odcienia dalej wynika z układu odcieni palety — po imporcie w trybie domyślnym lista układu jest pusta;
kłódka „odcień” ma własny łuk i układ jej nie dotyczy.

Zawsze: liczba akcentów dopasowuje się do motywu (akcenty z kłódką zasad nie są usuwane),
kłódki wartości znikają, a nazwy kolorów biorą się z motywu. Ustawienie jest zapamiętywane.""",
        G,
    ),
    "themes.spread": Topic(
        "Swoboda wariantów",
        "O ile stopni odcienia generowane warianty mogą odejść od każdego koloru motywu "
        "(domyślnie 10°).",
        """Działa przy odznaczonym [Nie zmieniaj ustawień palety](help:themes.keep_settings). Każdy
kolor motywu dostaje twardy łuk odcienia „swój odcień ± swoboda”; prawie szare kolory (np. tekst)
łuku nie dostają, bo ich odcień jest niewidoczny. Razem ze swobodą rosną widełki jasności (±0,05
na każde 10°) i nasycenia (±0,025 dla akcentów, ±0,01 dla tła i tekstu na każde 10°) oraz
dopuszczalny spadek kontrastu z tłem. 0° = propozycje praktycznie równe motywowi. Zakres 0–45°;
ustawienie jest zapamiętywane. Zasady można potem dowolnie zmieniać w zakładce Zasady.""",
        G,
    ),
    "themes.refresh": Topic(
        "Odśwież katalogi",
        "Pobiera katalogi źródeł od nowa, z pominięciem pamięci podręcznej.",
        """Katalogi są ważne 7 dni (strony Lospec 1 dzień); potem program sam próbuje je odświeżyć.
Bez internetu używa ostatniego pobranego katalogu i pisze to w pasku stanu okna.""",
        G,
    ),
    "themes.load": Topic(
        "Wczytaj",
        "Zamienia bieżącą paletę na zaznaczony motyw i przechodzi do zakładki Paleta. Ctrl+Z cofa.",
        """Sposób importu ustala [Nie zmieniaj ustawień palety](help:themes.keep_settings). Nic nie jest
zapisywane na dysk — użyj [Zapisz](help:menu.file.save), gdy motyw ci odpowiada.""",
        G,
    ),
    "themes.status": Topic(
        "Stan pobierania",
        "Postęp pobierania katalogu, liczba motywów i komunikaty: brak sieci, katalog z pamięci "
        "(offline), błąd zapisu pamięci.",
        """„Anuluj” przerywa pobieranie. Gdy nie ma ani sieci, ani pobranego wcześniej katalogu, lista
zostaje pusta z wyjaśnieniem — sprawdź połączenie i kliknij [Odśwież katalogi](help:themes.refresh).""",
        G,
    ),
    "themes.link": Topic(
        "Autor i strona źródła",
        "Autor motywu (jeśli źródło go podaje) i link do strony motywu lub źródła, otwierany "
        "w przeglądarce.",
        """Motywy należą do ich autorów; AlgoPalette tylko je pokazuje i pozwala wczytać jako punkt
wyjścia do własnej palety.""",
        G,
    ),
}
