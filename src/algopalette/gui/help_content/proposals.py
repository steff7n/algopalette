"""Pomoc: zakładka Propozycje — generowanie, lista propozycji, szczegóły, przejmowanie."""

from algopalette.gui.help_content.topic import Topic

P = "Propozycje"

TOPICS: dict[str, Topic] = {
    "proposals.generate_all": Topic(
        "Generuj wszystkie wolne (Ctrl+G)",
        "Liczy propozycje dla wszystkich kolorów bez kłódki. Kolory z kłódką zostają, a warunki wiążące "
        "je z wolnymi kolorami się liczą.",
        """Liczenie działa w tle — możesz w tym czasie przeglądać inne zakładki. Postęp pokazuje pasek obok
przycisków. Wynik zależy tylko od sesji w chwili startu: zmiany wprowadzone w trakcie nie wpływają na
trwające generowanie. Zobacz [generowanie](help:menu.generate) i
[optymalizator](help:globals.optimizer).""",
        P,
    ),
    "proposals.generate_one": Topic(
        "Generuj tylko zaznaczony kolor",
        "Liczy propozycje wyłącznie dla koloru zaznaczonego na zakładce Paleta — reszta palety zostaje bez "
        "zmian.",
        """Przydaje się, gdy paleta prawie ci odpowiada, a jeden kolor nie pasuje. Pozostałe kolory są
traktowane jak zablokowane, ale ich warunki i zależności nadal obowiązują. Gdy kolor ma kłódkę, nie ma
czego liczyć — zdejmij ją najpierw.""",
        P,
    ),
    "proposals.cancel": Topic(
        "Przerwij",
        "Zatrzymuje generowanie. Propozycje policzone do tej chwili zostają na liście.",
        """Status dostaje dopisek „(przerwano)”. Przerwane generowanie nie zmienia palety.""",
        P,
    ),
    "proposals.progress": Topic(
        "Postęp generowania",
        "Jak daleko jest silnik w liczeniu wszystkich propozycji. Widoczny tylko podczas generowania.",
        """Czas zależy od liczby wolnych kolorów, warunków (szczególnie daltonizmu) i budżetu w Globalnych →
[optymalizator](help:globals.optimizer).""",
        P,
    ),
    "proposals.status": Topic(
        "Stan generowania",
        "Ile propozycji policzono, ile z nich nie łamie twardych warunków i jakiego ziarna użyto.",
        """Ziarno pozwala odtworzyć wynik: te same ustawienia i to samo ziarno dają te same propozycje
([ziarno](help:globals.opt.seed)). Błąd silnika pojawia się tu na czerwono.""",
        P,
    ),
    "proposals.list": Topic(
        "Lista propozycji",
        "Każdy wiersz to pełna paleta policzona przez silnik. Zaznacz, żeby zobaczyć szczegóły po prawej; "
        "dwuklik przejmuje całą propozycję.",
        """Kolumny:

- **#** — numer propozycji;
- **stan** — ✓ spełnia twarde warunki, ✗ łamie twarde, ⏱ niepowtarzalna (przerwana limitem czasu);
- **wynik** — łączna kara (im mniej, tym lepiej; 0 = wszystko spełnione);
- **naruszenia** — ile warunków twardych (tw.) i miękkich (mi.) propozycja łamie;
- **paleta** — pasek kolorów w kolejności listy.

Silnik odpycha każdą kolejną propozycję od poprzednich ([różnorodność](help:globals.opt.min_diversity)),
więc dostajesz realne alternatywy.""",
        P,
    ),
    "proposals.col.state": Topic(
        "Stan propozycji",
        "✓ — bez naruszeń twardych; ✗ łamie twarde — nie spełnia warunków; ⏱ niepowtarzalna — przerwana "
        "limitem czasu.",
        """Propozycji ✗ ani ⏱ nie traktuj jak gotowego wyniku. ✗ oznacza zwykle, że warunki się
wykluczają — lista naruszeń w szczegółach mówi, które i o ile. ⏱ powstała pod presją czasu, więc to
samo ziarno może dać inny wynik ([limit czasu](help:globals.opt.time_cap)). Limit dotyczy całego
generowania, więc po propozycji ⏱ kolejnych już nie ma.""",
        P,
    ),
    "proposals.col.score": Topic(
        "Wynik",
        "Łączna kara propozycji: naruszenia miękkie ważone wagami, twarde — wagą twardych. Mniej = lepiej, "
        "0 = wszystko spełnione.",
        """Służy do porównywania propozycji tej samej sesji, nie ma bezwzględnej skali. Twarde naruszenie
zwykle dominuje wynik ([waga twardych](help:globals.opt.hard_weight)).""",
        P,
    ),
    "proposals.col.violations": Topic(
        "Naruszenia propozycji",
        "Ile warunków twardych (tw.) i miękkich (mi.) łamie propozycja. Szczegóły — pod tabelą kolorów "
        "po prawej.",
        """Liczone na kolorach po dopasowaniu do sRGB, tak samo jak [panel naruszeń](help:window.violations).""",
        P,
    ),
    "proposals.col.strip": Topic(
        "Pasek palety",
        "Kolory propozycji w kolejności listy: tło, tekst, akcenty.",
        """Szybki podgląd całości. Kolory w szczegółach po prawej możesz porównać z bieżącymi.""",
        P,
    ),
    "proposals.detail": Topic(
        "Kolory propozycji",
        "Każdy kolor zaznaczonej propozycji obok bieżącego. Dwuklik albo „Przejmij zaznaczony kolor” bierze "
        "tylko ten jeden.",
        """Kolumny:

- **kolor** — numer i nazwa;
- **teraz** — bieżący kolor w palecie;
- **propozycja** — kolor z propozycji;
- **hex** — hex propozycji;
- **Δ fit** — o ile ΔE kolor został ściągnięty do sRGB (zwykle pusto, bo silnik generuje kolory
  mieszczące się w sRGB).

Kolory z kłódką mają w propozycji swoją bieżącą wartość.""",
        P,
    ),
    "proposals.violations": Topic(
        "Naruszenia zaznaczonej propozycji",
        "Które warunki łamie zaznaczona propozycja: ✗ twarde, ~ miękkie, z wymaganą i osiągniętą wartością.",
        """Lista pokazuje do 12 pozycji. Po przejęciu propozycji te same naruszenia zobaczysz w
[panelu naruszeń](help:window.violations). „różnorodność” oznacza, że propozycja jest bardzo podobna
do wcześniejszej.""",
        P,
    ),
    "proposals.take_all": Topic(
        "Przejmij całą propozycję",
        "Zastępuje kolory bez kłódki kolorami z propozycji (to samo co dwuklik na wierszu). Ctrl+Z cofa.",
        """Zmieniane są tylko kolory, które propozycja liczyła — kolory z kłódką i kolory dodane po
starcie generowania zostają. Warunki i zależności się nie zmieniają.""",
        P,
    ),
    "proposals.take_color": Topic(
        "Przejmij zaznaczony kolor",
        "Bierze z propozycji tylko kolor zaznaczony w tabeli szczegółów (to samo co dwuklik). Ctrl+Z cofa.",
        """Kolor z kłódką nie zostanie podmieniony (program poprosi o zdjęcie kłódki). Możesz składać paletę
z kilku propozycji: kolor z jednej, kolor z drugiej — pamiętaj tylko, że zależności między nimi mogą
wtedy przestać być spełnione (sprawdź panel naruszeń).""",
        P,
    ),
}
