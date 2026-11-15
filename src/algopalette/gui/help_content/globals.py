"""Pomoc: zakładka Globalne — nastroje, metryki, układ odcieni, rozrzut, daltonizm, optymalizator,
unikanie kolorów, domyślne warunki ról."""

from algopalette.gui.help_content.topic import Topic

G = "Globalne"

TOPICS: dict[str, Topic] = {
    # --- nastrój ---
    "globals.mood": Topic(
        "Nastrój",
        "Gotowy zestaw ustawień: układ odcieni, rozrzut jasności i domyślne warunki ról, dopasowane do "
        "bieżącej polaryzacji. Wybierz z listy i kliknij „Zastosuj nastrój”.",
        """Nastrój to najszybszy start: jednym kliknięciem wypełnia ustawienia globalne, a wszystko, co
ustawił, widać niżej i można zmienić (plakietka „nastrój” przy warunkach ról). ★ oznacza nastrój
wbudowany. „bieżący” pokazuje, który nastrój jest nałożony.

**Wbudowane nastroje:**

- **neutralny** — równo po kole, średnie nasycenie; punkt wyjścia;
- **chłodny mglisty** — błękity i zielenie, niskie nasycenie, mały rozrzut jasności;
- **neon** — maksymalne nasycenie w gamucie, odcienie szeroko, skrajne tło (bardzo ciemne albo, przy
  jasnej polaryzacji, prawie białe);
- **ziemisty** — ciepłe, przygaszone brązy, oliwki i ochry;
- **pastel** — jasne, mało nasycone akcenty;
- **nocny wysoki kontrast** — skrajne tło (prawie czarne albo białe), bardzo wysoki kontrast tekstu
  i akcentów;
- **monochromatyczny z jednym akcentem** — jeden odcień w wielu jasnościach + pierwszy akcent ciepły;
- **retro terminal** — fosforowe zielenie i bursztyny, tło z nutą zieleni;
- **jesienny** — pomarańcze, rudości i złoto.

**Polaryzacji nastrój wbudowany nie zmienia** — jego liczby są liczone dla bieżącej polaryzacji
i metryki kontrastu, więc jasny motyw ustawiasz polem [polaryzacja](help:globals.polarity) (przed albo
po wyborze nastroju). Nastrój własny przywraca polaryzację i metrykę, w których go zapisano.

**Co zmienia zastosowanie nastroju:** ustawia na nowo układ odcieni, rozrzut jasności i WSZYSTKIE
domyślne warunki ról — także zmienione ręcznie.
Wartości własne poszczególnych kolorów zostają. Ctrl+Z cofa całą zmianę. Kolorów nie przelicza —
żeby zobaczyć efekt, wygeneruj propozycje (Ctrl+G).""",
        G,
    ),
    "globals.mood.apply": Topic(
        "Zastosuj nastrój",
        "Nakłada wybrany nastrój na ustawienia globalne (Ctrl+Z cofa). Kolory zmienią się dopiero po "
        "wygenerowaniu propozycji.",
        """Zobacz [nastrój](help:globals.mood).""",
        G,
    ),
    "globals.mood.delete": Topic(
        "Usuń własny nastrój",
        "Usuwa z pliku nastrojów wybrany nastrój użytkownika. Nastrojów wbudowanych (★) usunąć się nie da.",
        """Własne nastroje są zapisane w `~/.config/algopalette/moods.json`. Usunięcie nie zmienia bieżących
ustawień palety i nie da się go cofnąć przez Ctrl+Z (dotyczy pliku, nie sesji).""",
        G,
    ),
    "globals.mood.save": Topic(
        "Zapisz jako nastrój",
        "Zapisuje bieżące ustawienia globalne pod podaną nazwą jako własny nastrój — do użycia w innych "
        "paletach.",
        """Wpisz nazwę w polu obok i kliknij przycisk. Zapisywane są: polaryzacja, metryka kontrastu, układ
odcieni, rozrzut jasności i domyślne warunki ról. Kolory palety nie trafiają do nastroju.

Uwaga: liczby nastroju dotyczą polaryzacji i metryki, w których go zapisano. Zmiana polaryzacji albo
metryki zdejmuje własny nastrój i wraca do domyślnych warunków ról (nastrój wbudowany jest wtedy
nakładany ponownie).""",
        G,
    ),
    # --- polaryzacja i metryki ---
    "globals.polarity": Topic(
        "Polaryzacja",
        "Ciemne tło (jasny tekst) albo jasne tło (ciemny tekst). Zmiana przelicza domyślne zakresy jasności "
        "i kontrastu ról.",
        """Polaryzacja decyduje o domyślnych warunkach tła, tekstu i akcentów. Nowa paleta startuje z ciemnym
tłem, a nastroje wbudowane polaryzacji nie zmieniają — jasny motyw ustawiasz tutaj. Przy zmianie
nastrój wbudowany zostaje nałożony ponownie (w nowej polaryzacji), a własny nastrój zdjęty. Ręczne
zmiany domyślnych warunków ról — a przy nastroju wbudowanym także układu odcieni i rozrzutu jasności —
przepadają (Ctrl+Z je przywraca). Żeby przenieść gotową paletę na tło o odwrotnej
polaryzacji z zachowaniem jej charakteru, użyj zakładki Źródło → przeniesienie.""",
        G,
    ),
    "globals.contrast_metric": Topic(
        "Metryka kontrastu",
        "WCAG 2.1 (współczynnik 1–21) albo APCA (|Lc| 0–108). Dotyczy wszystkich warunków i kolumn "
        "kontrastu bez własnej metryki.",
        """Zmiana metryki ustawia od nowa domyślne warunki ról (nastrój wbudowany zostaje nałożony ponownie,
własny — zdjęty), więc ręczne zmiany domyślnych warunków ról, a przy nastroju wbudowanym także układu
odcieni i rozrzutu jasności, przepadają (Ctrl+Z je przywraca). Własne progi kontrastu kolorów
i zależności używające metryki globalnej są przeliczane na nową skalę. Warunki z własną metryką
zostają bez zmian.
Zobacz [WCAG i APCA](help:concept.contrast).""",
        G,
    ),
    "globals.delta_e": Topic(
        "Metoda ΔE",
        "Jak liczona jest odległość kolorów: ok i hyab (skala 0–1) albo 2000, itp, cam16 (skala ~0–100). "
        "Zmiana przelicza progi odległości.",
        """- **ok** — odległość w OKLab; szybka, zgodna z resztą programu (domyślna);
- **hyab** — w OKLab, ale osobno jasność i barwa; mocniej „widzi” różnice jasności;
- **2000** — klasyczna CIEDE2000;
- **itp** — ΔE ITP (ICtCp);
- **cam16** — w przestrzeni CAM16-UCS.

Progi w warunkach odległości i zależnościach są przeliczane przybliżonym przelicznikiem — sprawdź je
potem, jeśli zależy ci na dokładnych wartościach. Zobacz [ΔE](help:concept.delta_e).""",
        G,
    ),
    "globals.fit": Topic(
        "Gamut (fit)",
        "Jak sprowadzić do sRGB kolor spoza zakresu. Domyślnie oklch-chroma: obniża nasycenie, zachowując "
        "jasność i odcień.",
        """Dotyczy kolorów spoza sRGB — wpisanych ręcznie albo wklejonych. Wynik dopasowania widać w hexie,
w naruszeniach, w Analizie i w eksporcie.

- **oklch-chroma** — obniża C w OKLCH aż do granicy sRGB; zachowuje L i H (zalecane);
- **raytrace** — szybkie dopasowanie metodą śledzenia promienia, bardzo bliskie oklch-chroma;
- **minde-chroma** — algorytm z CSS Color 4: obniża nasycenie, dopuszczając drobne przycięcie;
- **lch-chroma** — obniża nasycenie w CIE LCh (odcień w innej przestrzeni);
- **scale** — skaluje kolor w stronę szarości o tej samej jasności;
- **clip** — przycina kanały RGB; najprostsze, ale potrafi przesunąć odcień.

Zobacz [gamut](help:concept.gamut).""",
        G,
    ),
    "globals.metrics": Topic(
        "Polaryzacja i metryki",
        "Ustawienia, od których zależą liczby we wszystkich warunkach: polaryzacja, metryka kontrastu, "
        "metoda ΔE, dopasowanie do gamutu.",
        """- [polaryzacja](help:globals.polarity);
- [metryka kontrastu](help:globals.contrast_metric);
- [metoda ΔE](help:globals.delta_e);
- [gamut (fit)](help:globals.fit).

Zmiana polaryzacji lub metryki ustawia od nowa domyślne warunki ról (ręczne zmiany przepadają,
Ctrl+Z je przywraca), a zmiana ΔE przelicza progi odległości.""",
        G,
    ),
    # --- układ odcieni ---
    "globals.hues": Topic(
        "Układ odcieni",
        "Cele odcieni dla akcentów, które nie mają własnego warunku odcienia: równo po kole, analogiczny, "
        "dopełniający, triada…",
        """Układ rozdziela odcienie docelowe między akcenty w kolejności listy. Akcent z własnym warunkiem
odcienia (cel albo zakres) nie dostaje celu z układu, ale zajmuje swoje miejsce w kolejności —
pozostałe akcenty się nie przesuwają. Cel to „H ± tolerancja” — domyślnie miękki, więc silnik
może od niego odejść, gdy koliduje z innymi warunkami.

**Rodzaje:**

- **równo po kole** — n akcentów co 360°/n, zaczynając od „obrót”;
- **analogiczny** — akcenty rozłożone równo na łuku „rozpiętość” wokół „środek”;
- **dopełniający** — dwa odcienie: obrót i obrót + 180°;
- **rozszczepiony dopełniający** — obrót, +150°, +210°;
- **triada** — co 120°; **tetrada** — co 90°;
- **własna lista** — odcienie z pola „własne °”;
- **brak** — bez celów odcienia.

Gdy akcentów jest więcej niż odcieni bazowych układu, kolejne „obiegi” wstawiają się równo między
bazowe. **jitter** dodaje losowe (ale powtarzalne dla danego ziarna) przesunięcia ± tyle stopni, żeby
paleta była mniej „geometryczna”.""",
        G,
    ),
    "globals.hues.kind": Topic(
        "Rodzaj układu",
        "Jak rozłożyć odcienie akcentów: równo, analogicznie, dopełniająco, triada, tetrada, własna lista "
        "albo brak celów.",
        """Zobacz [układ odcieni](help:globals.hues) — tam opis każdego rodzaju.""",
        G,
    ),
    "globals.hues.rotation": Topic(
        "Obrót °",
        "Pierwszy odcień układu. Obraca cały układ po kole (dla „równo”, „dopełniający”, „rozszczepiony”, "
        "„triada”, „tetrada”).",
        """Nie dotyczy układu analogicznego (tam liczy się „środek”) ani własnej listy.
Zobacz [układ odcieni](help:globals.hues).""",
        G,
    ),
    "globals.hues.center": Topic(
        "Środek °",
        "Środek łuku w układzie analogicznym — wokół niego rozkładają się odcienie akcentów.",
        """Używany tylko przez układ analogiczny. Zobacz [układ odcieni](help:globals.hues).""",
        G,
    ),
    "globals.hues.spread": Topic(
        "Rozpiętość °",
        "Szerokość łuku w układzie analogicznym: akcenty rozkładają się równo od środek − ½ do środek + ½ "
        "rozpiętości.",
        """Używana tylko przez układ analogiczny. Mała rozpiętość (30–60°) daje paletę „jednej rodziny”,
duża (120°+) — różnorodną, ale spójną.""",
        G,
    ),
    "globals.hues.tol": Topic(
        "Tolerancja ±°",
        "Jak daleko od celu odcień może leżeć bez kary. Większa tolerancja = więcej swobody dla silnika.",
        """W tolerancji cel jest spełniony, dalej rośnie kara (albo naruszenie, gdy układ jest twardy).
Zobacz [układ odcieni](help:globals.hues).""",
        G,
    ),
    "globals.hues.jitter": Topic(
        "Jitter ±°",
        "Losowe przesunięcie każdego celu o najwyżej tyle stopni. Powtarzalne: to samo ziarno = te same "
        "przesunięcia.",
        """Przydaje się, gdy układ wychodzi zbyt „geometryczny”. Przesunięcia zależą od ziarna
optymalizatora ([ziarno](help:globals.opt.seed)).""",
        G,
    ),
    "globals.hues.custom": Topic(
        "Własne odcienie °",
        "Lista odcieni dla układu „własna lista”, oddzielona przecinkami (np. 30, 200, 120). Błędny wpis "
        "dostaje czerwoną ramkę.",
        """Akcenty dostają odcienie z listy po kolei. Gdy akcentów jest więcej, kolejne obiegi wstawiają się
między podane odcienie. Wartości spoza 0–360 są zawijane. Enter albo wyjście z pola zatwierdza.
Tryb „charakter” na zakładce Źródło wypełnia tę listę dominującymi odcieniami palety źródłowej.""",
        G,
    ),
    "globals.hues.hard": Topic(
        "Układ twardy / waga",
        "Twardy: każdy akcent musi trafić w swój cel ± tolerancja. Miękki (domyślnie): cel z wagą, od którego "
        "silnik może odejść.",
        """Twardy układ razem z innymi twardymi warunkami łatwo się wyklucza — zwykle lepiej zostawić go
miękkim i ewentualnie zwiększyć wagę. Zobacz [twarde i miękkie](help:concept.hard_soft).""",
        G,
    ),
    # --- rozrzut, daltonizm ---
    "globals.spread": Topic(
        "Rozrzut jasności akcentów",
        "Zakres różnicy między najjaśniejszym a najciemniejszym akcentem (max L − min L). Mały = akcenty "
        "równie jasne.",
        """Warunek dotyczy wszystkich akcentów naraz. Typowo miękki: np. ≥ 0.15, żeby akcenty nie były
jednakowo jasne (łatwiej je wtedy odróżnić także w skali szarości), albo ≤ 0.10 dla spokojnej,
wyrównanej palety. „+ dodaj warunek rozrzutu” tworzy miękki warunek ≥ 0.15. Włączony / twardy działają
jak w [warunkach](help:cond.overview), „✕ usuń” usuwa warunek.""",
        G,
    ),
    "globals.cvd": Topic(
        "Daltonizm",
        "Wybierz typy zaburzeń widzenia barw, dla których akcenty mają być odróżnialne, oraz metodę "
        "i nasilenie symulacji.",
        """Zaznaczone typy włączają warunek [odróżnialność (daltonizm)](help:cond.cvd_min_distance) dla każdej
pary akcentów — osobno dla każdego typu. Bez zaznaczonych typów warunek nic nie robi.

- **protanopia** — brak czułości na czerwień; **deuteranopia** — na zieleń (najczęstsze);
  **tritanopia** — na błękit (rzadka);
- **metoda** — model symulacji: Machado (domyślna), Viénot albo Brettel; wyniki są zbliżone;
- **nasilenie** — 0 = widzenie normalne, 1 = pełna dychromazja.

Analiza pozwala obejrzeć paletę tak, jak widzi ją osoba z danym typem. Zobacz [CVD](help:concept.cvd).""",
        G,
    ),
    # --- optymalizator ---
    "globals.optimizer": Topic(
        "Optymalizator",
        "Ustawienia silnika: liczba propozycji, ziarno, budżet obliczeń, limit czasu, różnorodność "
        "propozycji, waga warunków twardych.",
        """Silnik dla każdej propozycji losuje wiele punktów startowych w obrębie twardych zakresów, wybiera
najlepsze i dopracowuje je lokalnie. Wynik jest **deterministyczny**: te same ustawienia i to samo
ziarno dają zawsze te same propozycje, bo budżet liczony jest w obliczeniach, nie w sekundach.

- [propozycje](help:globals.opt.n_proposals), [ziarno](help:globals.opt.seed),
  [budżet](help:globals.opt.max_evals), [limit czasu](help:globals.opt.time_cap),
  [różnorodność](help:globals.opt.min_diversity), [waga twardych](help:globals.opt.hard_weight).""",
        G,
    ),
    "globals.opt.n_proposals": Topic(
        "Liczba propozycji",
        "Ile różnych palet silnik ma policzyć przy jednym generowaniu (domyślnie 6). Więcej = dłużej.",
        """Wszystkie propozycje dzielą jeden [limit czasu](help:globals.opt.time_cap) — przy wielu
propozycjach i ciężkich warunkach ostatnie mogą się nie zmieścić. Każda kolejna propozycja jest
odpychana od poprzednich ([różnorodność](help:globals.opt.min_diversity)),
więc dostajesz realne alternatywy, a nie kopie.""",
        G,
    ),
    "globals.opt.seed": Topic(
        "Ziarno",
        "Liczba startowa losowania. To samo ziarno = te same propozycje. 🎲 losuje nowe ziarno.",
        """Zmień ziarno, gdy chcesz zobaczyć inne propozycje przy tych samych warunkach. Ziarno wpływa też na
[jitter](help:globals.hues.jitter) układu odcieni. Zapisane w sesji, więc wynik da się odtworzyć.""",
        G,
    ),
    "globals.opt.max_evals": Topic(
        "Budżet (ewaluacje)",
        "Ile razy silnik może ocenić paletę na jedną propozycję. Większy budżet = lepsze wyniki przy trudnych "
        "warunkach, ale dłużej.",
        """Budżet liczony w obliczeniach, nie w czasie, dlatego wyniki są powtarzalne niezależnie od szybkości
komputera. Zwiększ, gdy propozycje często łamią twarde warunki, które da się pogodzić.""",
        G,
    ),
    "globals.opt.time_cap": Topic(
        "Limit czasu (s)",
        "Bezpiecznik na CAŁE generowanie: po jego przekroczeniu bieżąca propozycja dostaje ⏱ "
        "niepowtarzalna, a dalszych już nie ma.",
        """To nie jest budżet — w normalnych warunkach limit nie powinien zadziałać. Liczy się od startu
generowania dla wszystkich propozycji razem, więc po jego przekroczeniu dostajesz mniej propozycji, niż
ustawiono. Propozycja przerwana limitem zależy od szybkości komputera, więc nie da się jej odtworzyć tym
samym ziarnem. Zamiast podnosić limit, zwykle lepiej zmniejszyć liczbę propozycji, budżet albo liczbę
akcentów.""",
        G,
    ),
    "globals.opt.min_diversity": Topic(
        "Różnorodność ΔE",
        "Minimalna średnia odległość (ΔE ok) kolorów propozycji od każdej wcześniejszej. Poniżej — wpis "
        "„różnorodność” wśród naruszeń propozycji.",
        """Silnik karze propozycje zbyt podobne do już policzonych. Gdy warunki są tak ciasne, że możliwa
jest praktycznie jedna paleta, kolejne propozycje i tak wyjdą podobne — wtedy widać miękkie naruszenie
„różnorodność”. 0 wyłącza odpychanie.""",
        G,
    ),
    "globals.opt.hard_weight": Topic(
        "Waga twardych",
        "Mnożnik kary za łamanie warunków twardych względem miękkich (domyślnie 1000). Zwykle nie trzeba "
        "zmieniać.",
        """Twarde zakresy jasności, odcienia i nasycenia względnego są granicami poszukiwań, a pozostałe
twarde warunki działają jako bardzo duża kara — to jest jej mnożnik. Za mała waga pozwala silnikowi
„kupić” spełnienie miękkich celów kosztem twardych.""",
        G,
    ),
    # --- unikanie, role ---
    "globals.avoid": Topic(
        "Unikanie kolorów źródła",
        "Akcenty muszą się różnić od kolorów palety źródłowej o co najmniej tyle ΔE (ok). Ustawia to tryb "
        "„charakter” na zakładce Źródło.",
        """Gdy w trybie „charakter” zaznaczysz unikanie kolorów źródła, program zapisuje tu akcenty źródła
i minimalną odległość — dzięki temu dostajesz paletę o tym samym charakterze, ale z innymi kolorami.
Warunek jest twardy. Pole liczbowe zmienia odległość, „wyczyść” usuwa listę i wyłącza unikanie.""",
        G,
    ),
    "globals.roles": Topic(
        "Domyślne warunki ról",
        "Warunki, które dziedziczy każdy kolor danej roli (tło, tekst, akcenty), dopóki nie ustawi własnych.",
        """Zakładki tło / tekst / akcenty zawierają ten sam edytor co edytor koloru, ale zmiana działa na
wszystkie kolory roli naraz. Plakietka „nastrój” oznacza wartość ustawioną przez nastrój, „globalne” —
zmienioną ręcznie. „✕ usuń” usuwa domyślny warunek z roli. Kolory z własną wartością (plakietka
„własne” w edytorze koloru) nie zmieniają się. Zobacz [warunki](help:cond.overview) i
[źródła wartości](help:concept.sources).""",
        G,
    ),
}
