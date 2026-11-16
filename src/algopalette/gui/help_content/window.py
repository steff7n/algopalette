"""Pomoc: okno główne — menu, pasek narzędzi, zakładki, panel naruszeń."""

from algopalette.gui.help_content.topic import Topic

W = "Okno i menu"

TOPICS: dict[str, Topic] = {
    # --- zakładki (w grupach swoich obszarów) ---
    "window.tab.proposals": Topic(
        "Zakładka Propozycje (F3)",
        "Generowanie propozycji palety, ich przegląd i przejmowanie całej palety albo pojedynczego "
        "koloru.",
        """Ctrl+G (z dowolnej zakładki) przenosi tutaj i uruchamia silnik. Każda propozycja to pełna paleta
spełniająca zasady tak dobrze, jak się dało, z oznaczeniem, czy łamie zasady twarde. Przejęcie
propozycji to zwykła zmiana sesji — Ctrl+Z ją cofa.""",
        "Propozycje",
    ),
    "window.tab.palette": Topic(
        "Zakładka Paleta (F4)",
        "Lista gotowych kolorów palety i edytor zaznaczonego koloru: nazwa, kłódka i wartość.",
        """Tu pracujesz na konkretnych kolorach, które już masz. Po lewej lista: tło, tekst i akcenty
z bieżącymi wartościami i hexem. Po prawej edytor zaznaczonego koloru:

- **Nazwa i kłódka** — kłódka zamraża kolor, generowanie go nie zmieni;
- **Wartość** — suwaki L/C/H (albo H/S/L w widoku HSL) zmieniają kolor ręcznie;
- **Zasady tego koloru →** — otwiera zakładkę [Zasady](help:rules.tab) z zaznaczonym tym kolorem.

Zasad kolorów nie ustawia się tutaj — mają jedno miejsce, zakładkę Zasady. Przeczytaj też
[pierwsze kroki](help:general.start).""",
        "Paleta",
    ),
    "window.tab.analysis": Topic(
        "Zakładka Analiza (F5)",
        "Podgląd bieżącej palety: koło odcieni, przekrój jasność–nasycenie, macierze ΔE i kontrastu, "
        "próbki tekstu — także przy daltonizmie.",
        """Analiza niczego nie zmienia — pokazuje, jak wypada bieżąca paleta. Pomaga zrozumieć, dlaczego
zasada jest złamana (np. dwa akcenty zbyt blisko na kole odcieni) i jak zmienić zasady, żeby
silnik znalazł lepsze kolory.""",
        "Analiza",
    ),
    "window.tab.source": Topic(
        "Zakładka Źródło (F6)",
        "Start od istniejącej palety: wklej kolory albo weź je z pliku czy z bieżącej palety, potem "
        "wybierz tryb — uzupełnianie, charakter albo przeniesienie.",
        """Gdy masz już paletę, od której chcesz zacząć — z innego motywu, z obrazka, z PaletteBuildera — wklej
jej kolory tutaj. Program może je uzupełnić o brakujące, odczytać z nich charakter (dominujące odcienie,
nasycenie, jasność) albo przenieść paletę na tło o odwrotnej polaryzacji. Tryby „charakter”
i „przeniesienie” zapisują zasady kolorów — zobaczysz je potem na zakładce Zasady.""",
        "Źródło",
    ),
    # --- panel naruszeń ---
    "window.violations": Topic(
        "Panel naruszeń",
        "Zasady, które łamie bieżąca paleta: ✗ twarde, ~ miękkie, z wymaganą i osiągniętą wartością. "
        "Klik w wiersz otwiera tę zasadę na zakładce Zasady.",
        """Panel na dole okna przelicza się po każdej zmianie palety i pokazuje, czego bieżąca paleta nie
spełnia. Granicę między nim a zakładkami możesz przeciągać.

- **✗** — zasada twarda (musi być spełniona), **~** — miękka (cel z wagą);
- **zasada** — której zasady albo zależności i którego koloru dotyczy;
- **wymagane** i **jest** — próg i wartość osiągnięta.

**Klik w wiersz** przenosi do zakładki Zasady z zaznaczonym kolorem, którego zasada jest złamana
(przy odległości pary akcentów — z oboma; przy rozrzucie jasności — z „całą paletą”).

Liczone na kolorach **po** dopasowaniu do sRGB, czyli takich, jakie trafią do hexa i eksportu
([gamut](help:concept.gamut)). Zielony nagłówek oznacza, że paleta spełnia wszystko.

**Kłódki:** zasada albo zależność, która dotyczy WYŁĄCZNIE kolorów z kłódką (np. kontrast tekstu
z tłem, gdy oba są zablokowane), nie jest ani liczona, ani pokazywana — silnik i tak nie może ich
zmienić. Żeby ją sprawdzić, zdejmij kłódkę z jednego z tych kolorów albo zajrzyj do kolumn listy
kolorów i do Analizy.

**Co dalej z naruszeniem?** Zmień kolor ręcznie na Palecie, wygeneruj propozycje (Ctrl+G) albo
poluzuj zasadę. Gdy dwie twarde zasady się wykluczają, silnik ich nie pogodzi — trzeba zmienić którąś
z nich albo zrobić ją [miękką](help:concept.hard_soft).""",
        W,
    ),
    "window.violations.values": Topic(
        "Wymagane i osiągnięte",
        "Kolumna „wymagane” to próg zasady, kolumna „jest” — wartość, którą ma bieżąca paleta.",
        """Jednostki zależą od zasady: jasność i nasycenie w skali OKLCH, odcień w stopniach, kontrast
w jednostkach wybranej metryki ([WCAG albo APCA](help:concept.contrast)), odległości w skali metody
[ΔE](help:concept.delta_e). Przy [zakazanym przedziale](help:concept.exclusion) „wymagane” brzmi
„poza od–do”. Różnica między kolumnami mówi, o ile trzeba się przesunąć, żeby zasada była spełniona.
Wiersz należy do [panelu naruszeń](help:window.violations).""",
        W,
    ),
    # --- menu ---
    "menu.file": Topic(
        "Menu Plik",
        "Nowa paleta, wczytywanie i zapisywanie sesji, przeniesienie palety do PaletteBuildera, wyjście.",
        """Sesja AlgoPalette (plik `.json`, format `algopalette.v2`) zapisuje pełny stan: kolory, ich zasady
i zależności, ustawienia całej palety i widok. Niezależnie od zapisu działa autozapis ostatniej
sesji — po zamknięciu i ponownym uruchomieniu wracasz tam, gdzie skończyłeś.""",
        W,
    ),
    "menu.file.new": Topic(
        "Nowa paleta (Ctrl+N)",
        "Zaczyna od domyślnej palety z presetem „neutralny”. Bieżącą przywrócisz przez Cofnij (Ctrl+Z).",
        """Program pyta o potwierdzenie, potem zastępuje sesję domyślną paletą z presetem „neutralny”
i odpina plik — następny Ctrl+S zapyta, gdzie zapisać. Zmiana jest zwykłym krokiem historii,
więc Ctrl+Z przywraca poprzednią paletę.""",
        W,
    ),
    "menu.file.open": Topic(
        "Wczytaj sesję (Ctrl+O)",
        "Otwiera zapisany plik sesji AlgoPalette i zastępuje nim bieżącą paletę (Ctrl+Z cofa).",
        """Domyślnie otwiera katalog `~/.local/share/algopalette/palettes/`. Plik uszkodzony albo w obcym
formacie zostanie odrzucony z komunikatem, a bieżąca sesja zostanie bez zmian. Plik ze starszej
wersji programu (`algopalette.v1`) jest przenoszony na nowy model zasad: każdy kolor dostaje
zasady, które go wtedy obowiązywały, a wszystko, czego nie dało się przenieść wiernie (np. dwa
osobne ustawienia odcienia scalone w jeden łuk), program wypisuje po wczytaniu. AlgoPalette nie
czyta plików PaletteBuildera — przepływ jest jednokierunkowy.""",
        W,
    ),
    "menu.file.themes": Topic(
        "Motywy z sieci… (Ctrl+Shift+O)",
        "Otwiera przeglądarkę gotowych motywów kolorów z internetu (base16, Gogh, Windows Terminal, "
        "Lospec); wybrany motyw staje się bieżącą paletą.",
        """Szczegóły w temacie [Motywy z sieci](help:themes.window). Import nie zapisuje niczego na
dysk i można go cofnąć (Ctrl+Z).""",
        W,
    ),
    "menu.file.save": Topic(
        "Zapisz (Ctrl+S)",
        "Zapisuje sesję do bieżącego pliku (nazwa w tytule okna). Gdy pliku jeszcze nie ma, pyta, gdzie "
        "zapisać.",
        """Zapis jest atomowy: najpierw plik tymczasowy, potem podmiana, więc przerwany zapis nie zostawi
uszkodzonego pliku. Autozapis działa niezależnie i nie zastępuje zapisu do własnego pliku.""",
        W,
    ),
    "menu.file.save_as": Topic(
        "Zapisz jako (Ctrl+Shift+S)",
        "Zapisuje sesję do nowego pliku i od tej chwili to on jest plikiem bieżącym.",
        """Brak rozszerzenia zostanie uzupełniony o `.json`. Domyślny katalog:
`~/.local/share/algopalette/palettes/`.""",
        W,
    ),
    "menu.file.export": Topic(
        "Paleta do schowka dla PaletteBuildera (Ctrl+E)",
        "Kopiuje hexy palety (po dopasowaniu do sRGB) i polaryzację w formacie okna „Wczytaj…” "
        "PaletteBuildera — wklej je tam.",
        """Jedyne połączenie z PaletteBuilderem i działa tylko w jedną stronę. Do schowka trafia JSON
(`palettebuilder.v3`) z kolorami w kolejności listy (tło, tekst, akcenty) i polaryzacją. Zasady
i ustawienia zostają w AlgoPalette — zapisz sesję, jeśli chcesz do nich wrócić.""",
        W,
    ),
    "menu.file.export_file": Topic(
        "Plik dla PaletteBuildera (Ctrl+Shift+E)",
        "To samo co eksport do schowka, ale zapisane do pliku JSON (domyślnie w ~/Dokumenty/motifs/).",
        """Treść pliku jest taka sama jak przy [eksporcie do schowka](help:menu.file.export). Okno wyboru
pliku pyta o nadpisanie istniejącego pliku.""",
        W,
    ),
    "menu.file.quit": Topic(
        "Wyjście (Ctrl+Q)",
        "Zamyka program. Zaległe zmiany trafiają do autozapisu, a działające generowanie zostaje "
        "przerwane.",
        """Autozapis ma krótkie opóźnienie, więc przy zamykaniu program zapisuje zaległą zmianę od razu.
Następne uruchomienie przywraca tę sesję (chyba że uruchomisz z plikiem albo z `--fresh`).""",
        W,
    ),
    "menu.edit": Topic(
        "Menu Edycja",
        "Cofanie i ponawianie zmian palety.",
        """Historia obejmuje każdą zmianę sesji: kolory, zasady, zależności, ustawienia całej palety, przejęte
propozycje, wczytane pliki. Zmiana zasady w kilku zaznaczonych kolorach naraz to jeden krok. Seria szybkich zmian tego samego pola (np. przeciąganie suwaka) to jeden
krok. Przełączenie widoku HSL/OKLCH i motywu nie jest krokiem cofania.""",
        W,
    ),
    "menu.edit.undo": Topic(
        "Cofnij (Ctrl+Z)",
        "Wraca do stanu sprzed ostatniej zmiany palety. Szybka seria zmian jednego pola cofa się "
        "naraz.",
        """Cofa także przejęcie propozycji, wczytanie pliku i nową paletę. Wyszarzone, gdy nie ma czego
cofać. Zobacz [menu Edycja](help:menu.edit).""",
        W,
    ),
    "menu.edit.redo": Topic(
        "Ponów (Ctrl+Y)",
        "Przywraca zmianę cofniętą przez Cofnij. Nowa zmiana po cofnięciu kasuje możliwość ponowienia.",
        """Działa też pod Ctrl+Shift+Z. Zobacz [menu Edycja](help:menu.edit).""",
        W,
    ),
    "menu.palette": Topic(
        "Menu Paleta",
        "Generowanie propozycji i działania na liście kolorów: dodawanie, usuwanie, kłódka, kolejność.",
        """Działania na liście kolorów są też pod listą na zakładce Paleta jako przyciski i działają na
zaznaczonym kolorze.""",
        W,
    ),
    "menu.generate": Topic(
        "Generuj propozycje (Ctrl+G)",
        "Uruchamia silnik dla wszystkich kolorów bez kłódki i przechodzi do zakładki Propozycje.",
        """Silnik szuka kolorów spełniających jednocześnie zasady twarde i jak najlepiej miękkie. Liczy kilka
propozycji różniących się od siebie (liczbę, ziarno, budżet i wątki ustawisz w Zasadach → cała paleta
→ [generowanie](help:rules.generation)). Te same ustawienia i to samo ziarno dają zawsze te same
propozycje. Kolory z kłódką zostają bez zmian, ale ich zasady i zależności dalej obowiązują pozostałe
kolory. Liczenie idzie na wszystkich rdzeniach procesora — okno reaguje, a generowanie można przerwać
na zakładce Propozycje.""",
        W,
    ),
    "menu.view": Topic(
        "Menu Widok",
        "Widok wartości (HSL/OKLCH), motyw okna i przechodzenie między zakładkami (F2–F6).",
        """Ustawienia widoku nie zmieniają palety i nie są krokami cofania.""",
        W,
    ),
    "menu.view.values": Topic(
        "Widok wartości HSL / OKLCH (F7)",
        "Przełącza sposób wyświetlania i edycji wartości kolorów. Zasady, silnik i Analiza zawsze "
        "liczą w OKLCH.",
        """W widoku HSL lista kolorów pokazuje H°, S%, L%, a suwaki „Wartość” w edytorze edytują kolor w HSL
(do sesji i tak trafia OKLCH). Zasady, zależności, presety, silnik i koło odcieni w Analizie zostają
w OKLCH. Odcień HSL i odcień OKLCH tego samego koloru potrafią różnić się o kilkadziesiąt stopni, więc
nie przenoś liczb między widokami. Widok zapisuje się w sesji, ale nie jest krokiem cofania.
Zobacz [OKLCH](help:concept.oklch).""",
        W,
    ),
    "menu.view.theme": Topic(
        "Motyw okna",
        "Systemowy (jak motyw pulpitu), jasny albo ciemny. Zmienia się od razu i zostaje zapamiętany.",
        """- **Systemowy** — okno idzie za ustawieniem jasny/ciemny pulpitu, także gdy zmienisz je w trakcie
  pracy;
- **Jasny** / **Ciemny** — na stałe, niezależnie od pulpitu.

Wybór zapisuje się w `~/.config/algopalette/gui.json`. Zmienna środowiskowa
`ALGOPALETTE_THEME=dark` (albo `light`) wymusza motyw na starcie, gdy wykrywanie motywu pulpitu
zawodzi. Motyw dotyczy tylko okna programu — nie zmienia palety ani podglądów kolorów.""",
        W,
    ),
    "menu.help": Topic(
        "Menu Pomoc",
        "Pomoc kontekstowa (F1), tryb wskazywania elementu (Shift+F1), pierwsze kroki, skróty i spis "
        "treści.",
        """Zobacz [jak korzystać z pomocy](help:general.help).""",
        W,
    ),
    "window.toolbar": Topic(
        "Pasek narzędzi",
        "Najczęstsze akcje pod ręką: cofnij, ponów, generuj, zapisz, eksport do PaletteBuildera, widok "
        "wartości.",
        """Każdy przycisk paska odpowiada pozycji z menu — najedź na niego, żeby zobaczyć jej opis.""",
        W,
    ),
}
