"""Pomoc: zakładka Źródło — kolory wyjściowe i trzy tryby startu."""

from algopalette.gui.help_content.topic import Topic

S = "Źródło"

TOPICS: dict[str, Topic] = {
    "source.colors": Topic(
        "Kolory źródła",
        "Paleta, od której startujesz: wklej kolory, weź je z pliku sesji albo z bieżącej palety, a potem "
        "wskaż, który kolor jest tłem, a który tekstem.",
        """Najwyżej 16 kolorów. Formaty: hex (`#1e1e2e`, `#fff`), `oklch(…)`, `rgb(…)` i inne zapisy CSS,
rozdzielone spacjami, przecinkami, średnikami albo liniami. „Odczytaj” sprawdza listę i pokazuje próbki
z numerami. Numery tła i tekstu wybierasz niżej.

Potem wybierz [tryb](help:source.mode) i kliknij „Zastosuj tryb do sesji”. Jeśli zmienisz tekst
w polu, „Zastosuj” sam odczyta go ponownie.""",
        S,
    ),
    "source.paste": Topic(
        "Pole kolorów",
        "Wklej kolory: hex, oklch(…), rgb(…) — rozdzielone spacjami, przecinkami, średnikami albo liniami "
        "(najwyżej 16).",
        """Zobacz [kolory źródła](help:source.colors). Błędny zapis zostanie wskazany w komunikacie pod
przyciskami.""",
        S,
    ),
    "source.parse": Topic(
        "Odczytaj",
        "Sprawdza wpisane kolory i pokazuje je jako ponumerowane próbki. Błąd — czerwony komunikat "
        "z błędnym fragmentem.",
        """Odczyt niczego nie zmienia w palecie. Zmiana następuje dopiero po „Zastosuj tryb do sesji”.""",
        S,
    ),
    "source.from_file": Topic(
        "Z pliku sesji…",
        "Wczytuje kolory z zapisanego pliku sesji AlgoPalette (tło, tekst, akcenty) jako źródło. Bieżąca "
        "paleta się nie zmienia.",
        """Kolory trafiają do pola jako hexy, tło dostaje nr 1, a tekst nr 2. Pliki PaletteBuildera nie są
obsługiwane.""",
        S,
    ),
    "source.from_current": Topic(
        "Z bieżącej palety",
        "Kopiuje kolory bieżącej palety do pola źródła — np. żeby przenieść ją na tło o odwrotnej "
        "polaryzacji.",
        """Typowe użycie: masz gotowy ciemny motyw i chcesz jego jasną wersję → „Z bieżącej palety”, tryb
[przeniesienie](help:source.mode.transfer), nowe tło: jasne.""",
        S,
    ),
    "source.result": Topic(
        "Wynik odczytu",
        "Liczba odczytanych kolorów albo komunikat o błędzie. Pod spodem próbki z numerami do wyboru tła "
        "i tekstu.",
        """Numery próbek to numery, które wpisujesz w polach „tło = nr” i „tekst = nr”.""",
        S,
    ),
    "source.swatch": Topic(
        "Próbka koloru źródła",
        "Kolor źródła po dopasowaniu do sRGB, z numerem do wyboru tła i tekstu.",
        """Zobacz [kolory źródła](help:source.colors).""",
        S,
    ),
    "source.roles": Topic(
        "Tło = nr, tekst = nr",
        "Który kolor źródła jest tłem, a który tekstem (numery próbek). Pozostałe kolory to akcenty.",
        """Tło i tekst muszą być różnymi kolorami. Przy jednym kolorze źródła jest on tłem. Akcenty biorą się
z pozostałych kolorów w kolejności.""",
        S,
    ),
    "source.mode": Topic(
        "Tryb startu",
        "Co zrobić z kolorami źródła: uzupełnianie (zablokuj je i dogeneruj resztę), charakter (odczytaj "
        "styl) albo przeniesienie (na inne tło).",
        """- [uzupełnianie](help:source.mode.complete) — masz część kolorów, resztę ma dobrać silnik;
- [charakter](help:source.mode.character) — chcesz nową paletę w tym samym stylu;
- [przeniesienie](help:source.mode.transfer) — chcesz tę samą paletę na tle o odwrotnej polaryzacji.

Każdy tryb to jeden krok cofania (Ctrl+Z). Po zastosowaniu sprawdź zasady (F2) i wygeneruj (Ctrl+G).""",
        S,
    ),
    "source.mode.complete": Topic(
        "Tryb: uzupełnianie",
        "Kolory źródła trafiają na kolejne miejsca palety (tło, tekst, akcenty) z kłódką. Pozostałe kolory "
        "dogenerujesz.",
        """Gdy kolorów źródła jest więcej niż akcentów, program dodaje akcenty. Zasady kolorów i ustawienia
całej palety zostają bez zmian, więc zadbaj o to, żeby zasady pozostałych kolorów pasowały do
zablokowanych (np. kontrast z zablokowanym tłem). Potem Ctrl+G liczy tylko kolory bez kłódki. Uwaga:
zasady dotyczące wyłącznie kolorów źródła (wszystkie mają kłódkę) nie pojawią się w panelu naruszeń —
ocenisz je w Analizie.""",
        S,
    ),
    "source.mode.character": Topic(
        "Tryb: charakter",
        "Program odczytuje profil palety (dominujące odcienie, nasycenie, jasność, zabarwienie tła) i zapisuje "
        "go jako zasady kolorów. Kolory generujesz od nowa.",
        """Co się zmienia (wszystko potem widać i można poprawić na zakładce Zasady):

- tło palety (ciemne / jasne) — wg jasności tła źródła;
- każdy akcent dostaje ten sam zestaw zasad — zakres jasności i nasycenia względnego jak w źródle
  (lekko poszerzone), kontrast z tłem na poziomie akcentów źródła — bez własnej zasady odcienia, za to
  z celem z układu odcieni;
- tekst — kontrast jak w źródle; tło — jasność, nasycenie i odcień bliskie tłu źródła;
- układ odcieni — lista dominujących odcieni źródła, w kolejności jego akcentów;
- oznaczenie presetu znika, kłódki są zdjęte; wartości kolorów i zależności zostają.

Opcja **unikaj kolorów źródła** wpisuje akcenty źródła na listę
[unikanych kolorów](help:rules.avoid): nowe akcenty muszą się od nich różnić o co najmniej podaną ΔE
(ok) — dostajesz paletę w tym samym stylu, ale z innymi kolorami.""",
        S,
    ),
    "source.mode.transfer": Topic(
        "Tryb: przeniesienie",
        "Ta sama paleta na tle o innej polaryzacji: każdy akcent zachowuje odcień, nasycenie względne "
        "i kontrast z tłem ze źródła.",
        """Program ustawia wybrane tło i dla tekstu oraz każdego akcentu własne zasady: łuk odcienia ± 8°
wokół odcienia ze źródła (tylko dla kolorów z wyraźnym odcieniem, C ≥ 0.02), nasycenie względne
± 0.08 i kontrast z nowym tłem równy kontrastowi w źródle ± tolerancja. Zasada jasności zostaje, ale
wyłączona, bo jasność wynika z kontrastu. Liczba akcentów zostaje dopasowana do źródła, akcenty nie
biorą celu z układu odcieni (lista układu odcieni jest pusta), kłódki i zależności akcentów są zdjęte,
oznaczenie presetu znika.

**Nowe tło** — jasne albo ciemne. **Tolerancja kontrastu** — puste = automatycznie (0.5 w WCAG,
5 w APCA). Po zastosowaniu wygeneruj propozycje (Ctrl+G).""",
        S,
    ),
    "source.avoid": Topic(
        "Unikaj kolorów źródła (charakter)",
        "Tylko w trybie charakter: akcenty muszą się różnić od akcentów źródła co najmniej o podaną ΔE (ok, "
        "domyślnie 0.05).",
        """Zobacz [tryb charakter](help:source.mode.character) i [unikane kolory](help:rules.avoid).""",
        S,
    ),
    "source.transfer_options": Topic(
        "Opcje przeniesienia",
        "Nowe tło (jasne / ciemne) i tolerancja kontrastu (puste = auto: 0.5 WCAG, 5 APCA). Działa tylko "
        "w trybie przeniesienie.",
        """Zobacz [tryb przeniesienie](help:source.mode.transfer).""",
        S,
    ),
    "source.apply": Topic(
        "Zastosuj tryb do sesji",
        "Wykonuje wybrany tryb na bieżącej sesji (jeden krok cofania). Nieodczytany albo zmieniony tekst "
        "zostanie najpierw odczytany.",
        """Po zastosowaniu przejrzyj zasady (zakładka Zasady, F2) i wygeneruj propozycje (Ctrl+G). Błąd (np. ten
sam numer tła i tekstu) pokazuje okno komunikatu i nic nie zmienia.""",
        S,
    ),
}
