"""Pomoc: zakładka Propozycje — generowanie, lista propozycji, szczegóły, przejmowanie."""

from algopalette.gui.help_content.topic import Topic

P = "Propozycje"

TOPICS: dict[str, Topic] = {
    "proposals.generate_all": Topic(
        "Generuj wszystkie wolne (Ctrl+G)",
        "Liczy propozycje dla wszystkich kolorów bez kłódki. Kolory z kłódką zostają, a zasady wiążące "
        "je z wolnymi kolorami się liczą.",
        """Liczenie idzie w silniku na wszystkich rdzeniach procesora, a okno w tym czasie reaguje — możesz
przeglądać inne zakładki. Postęp pokazuje pasek obok przycisków. Wynik zależy tylko od sesji w chwili
startu: zmiany wprowadzone w trakcie nie wpływają na trwające generowanie. Zobacz
[generowanie](help:menu.generate) i [ustawienia generowania](help:rules.generation).""",
        P,
    ),
    "proposals.generate_one": Topic(
        "Generuj tylko zaznaczony kolor",
        "Liczy propozycje wyłącznie dla koloru zaznaczonego na zakładce Paleta — reszta palety zostaje bez "
        "zmian.",
        """Przydaje się, gdy paleta prawie ci odpowiada, a jeden kolor nie pasuje. Pozostałe kolory są
traktowane jak zablokowane, ale ich zasady i zależności nadal obowiązują. Gdy kolor ma kłódkę, nie ma
czego liczyć — zdejmij ją najpierw.""",
        P,
    ),
    "proposals.cancel": Topic(
        "Przerwij",
        "Zatrzymuje generowanie. Propozycje policzone do tej chwili zostają na liście.",
        """Silnik reaguje w ułamku sekundy i oddaje propozycje wybrane z przebiegów, które zdążył
ukończyć. Status dostaje dopisek „(przerwano)”. Przerwane generowanie nie zmienia palety.""",
        P,
    ),
    "proposals.progress": Topic(
        "Postęp generowania",
        "Jak daleko jest silnik w liczeniu wszystkich propozycji. Widoczny tylko podczas generowania.",
        """Czas zależy od liczby propozycji, liczby wolnych kolorów, zasad (szczególnie daltonizmu
i wolniejszych metod ΔE), [budżetu](help:rules.gen.budget) i liczby [wątków](help:rules.gen.threads).
Gdy silnik musi doliczyć kolejną falę przebiegów, żeby zebrać dość różnych propozycji, pasek nie cofa
się, tylko na chwilę zwalnia.""",
        P,
    ),
    "proposals.status": Topic(
        "Stan generowania",
        "Ile propozycji policzono, ile z nich nie łamie twardych zasad i jakiego ziarna użyto.",
        """Ziarno pozwala odtworzyć wynik: te same ustawienia i to samo ziarno dają te same propozycje,
niezależnie od liczby wątków ([ziarno](help:rules.gen.seed)). Błąd silnika — także odrzucenie zasad,
których silnik nie umie przyjąć — pojawia się tu na czerwono.""",
        P,
    ),
    "proposals.list": Topic(
        "Lista propozycji",
        "Każdy wiersz to pełna paleta policzona przez silnik. Zaznacz, żeby zobaczyć szczegóły po prawej; "
        "dwuklik przejmuje całą propozycję.",
        """Kolumny:

- **#** — numer propozycji;
- **stan** — ✓ spełnia twarde zasady, ✗ łamie twarde, ⏱ niepowtarzalna (przerwana limitem czasu);
- **wynik** — łączna kara (im mniej, tym lepiej; 0 = wszystko spełnione);
- **naruszenia** — ile zasad twardych (tw.) i miękkich (mi.) propozycja łamie;
- **paleta** — pasek kolorów w kolejności listy.

Kolejność: najpierw propozycje bez twardych naruszeń, potem rosnąco według wyniku. Silnik liczy więcej
przebiegów, niż zwraca propozycji, i wybiera najlepsze różniące się od siebie
([różnorodność](help:rules.gen.min_diversity)), więc dostajesz realne alternatywy.""",
        P,
    ),
    "proposals.col.state": Topic(
        "Stan propozycji",
        "✓ — bez naruszeń twardych; ✗ łamie twarde — nie spełnia zasad; ⏱ niepowtarzalna — przerwana "
        "limitem czasu.",
        """Propozycji ✗ ani ⏱ nie traktuj jak gotowego wyniku. ✗ oznacza zwykle, że zasady się
wykluczają — lista naruszeń w szczegółach mówi, które i o ile. ⏱ powstała pod presją czasu, więc to
samo ziarno może dać inny wynik ([limit czasu](help:rules.gen.time_cap)). Limit dotyczy całego
generowania, więc po jego zadziałaniu ⏱ dostają wszystkie propozycje tej generacji.""",
        P,
    ),
    "proposals.col.score": Topic(
        "Wynik",
        "Łączna kara propozycji: naruszenia miękkie ważone wagami, twarde — wagą twardych. Mniej = lepiej, "
        "0 = wszystko spełnione.",
        """Służy do porównywania propozycji tej samej sesji, nie ma bezwzględnej skali. Twarde naruszenie
zwykle dominuje wynik ([waga twardych](help:rules.gen.hard_weight)).""",
        P,
    ),
    "proposals.col.violations": Topic(
        "Naruszenia propozycji",
        "Ile zasad twardych (tw.) i miękkich (mi.) łamie propozycja. Szczegóły — pod tabelą kolorów "
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
        "Które zasady łamie zaznaczona propozycja: ✗ twarde, ~ miękkie, z wymaganą i osiągniętą wartością.",
        """Lista pokazuje do 12 pozycji. Po przejęciu propozycji te same naruszenia zobaczysz w
[panelu naruszeń](help:window.violations). „różnorodność” (miękkie) oznacza, że propozycja jest bardzo
podobna do innej z listy — przy ciasnych zasadach tylu naprawdę różnych palet może po prostu nie być.""",
        P,
    ),
    "proposals.take_all": Topic(
        "Przejmij całą propozycję",
        "Zastępuje kolory bez kłódki kolorami z propozycji (to samo co dwuklik na wierszu). Ctrl+Z cofa.",
        """Zmieniane są tylko kolory, które propozycja liczyła — kolory z kłódką i kolory dodane po
starcie generowania zostają, a kolory usunięte w międzyczasie są pomijane (pasek stanu mówi ile).
Zasady i zależności się nie zmieniają.""",
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
