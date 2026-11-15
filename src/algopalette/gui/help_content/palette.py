"""Pomoc: zakładka Paleta — lista kolorów, przyciski listy, edytor zaznaczonego koloru."""

from algopalette.gui.help_content.topic import Topic

P = "Paleta"

TOPICS: dict[str, Topic] = {
    # --- lista ---
    "palette.list": Topic(
        "Lista kolorów",
        "Wszystkie kolory palety w stałej kolejności: 0 = tło, 1 = tekst, dalej akcenty. Zaznacz wiersz, "
        "żeby edytować kolor po prawej.",
        """Każdy wiersz to jedno miejsce palety (slot). Kolejność ma znaczenie:

- **0 — tło** i **1 — tekst** mają stałe miejsca i nie da się ich usunąć ani przesunąć;
- **2 i dalej — akcenty**; możesz je dodawać (do 14), usuwać i przesuwać.

Zaznaczenie wiersza otwiera kolor w edytorze po prawej. Kiedy lista ma fokus, działają skróty:
Ins/A dodaje akcent, Del usuwa, L przełącza kłódkę, Alt+↑/↓ przesuwa. Te same akcje są pod listą jako
przyciski i w menu Paleta.

Kolumny przeliczają się po każdej zmianie — także po zmianie ustawień globalnych, np. metryki kontrastu
czy metody ΔE. Kolor spoza sRGB ma przy hexie znak ⚠ i wartość ΔE, o jaką ściągnięto go do gamutu
([gamut](help:concept.gamut)).""",
        P,
    ),
    "palette.col.swatch": Topic(
        "Próbka koloru",
        "Kolor tak, jak trafi do eksportu — po dopasowaniu do sRGB. Podpowiedź na próbce pokazuje hex.",
        """Próbka zawsze pokazuje kolor po dopasowaniu do gamutu sRGB ([gamut](help:concept.gamut)), czyli
dokładnie to, co dostanie PaletteBuilder. Zostaje w swoim kolorze także w zaznaczonym wierszu.""",
        P,
    ),
    "palette.col.index": Topic(
        "Numer miejsca (#)",
        "Pozycja koloru w palecie: 0 = tło, 1 = tekst, 2+ = akcenty. Tego numeru używają nazwy i zależności.",
        """Numer pojawia się w nazwach domyślnych („akcent 3”), w panelu naruszeń, w listach wyboru celu
zależności i w Analizie. Przesunięcie akcentu zmienia jego numer, ale zależności trzymają się koloru, nie
numeru, więc nie zrywają się przy przesuwaniu.""",
        P,
    ),
    "palette.col.name": Topic(
        "Nazwa koloru",
        "Twoja nazwa koloru albo nazwa domyślna wg roli („tło”, „tekst”, „akcent 3”). Zmienisz ją w edytorze.",
        """Nazwa służy tylko do orientacji: pojawia się w panelu naruszeń, w zależnościach i w Analizie.
Nie wpływa na silnik ani na eksport (PaletteBuilder dostaje same kolory w kolejności listy).
Zobacz [pole nazwy](help:palette.editor.name).""",
        P,
    ),
    "palette.col.hex": Topic(
        "Hex",
        "Kod sRGB koloru po dopasowaniu do gamutu. ⚠ z liczbą oznacza, że kolor był poza sRGB i został "
        "przesunięty o tyle ΔE.",
        """Hex liczony jest metodą dopasowania z Globalnych ([gamut](help:concept.gamut)). Wyróżniony hex
z ⚠ to sygnał, że wartość OKLCH (np. wpisana ręcznie) wychodzi poza sRGB. Warunki i naruszenia liczą się
na kolorze po dopasowaniu, więc to, co widzisz, jest tym, co sprawdza program. Silnik sam generuje
wyłącznie kolory mieszczące się w sRGB.""",
        P,
    ),
    "palette.col.values": Topic(
        "Wartości koloru (L C H albo H S L)",
        "Trzy liczby koloru w bieżącym widoku: OKLCH (L 0–1, C, H°) albo HSL (H°, S%, L%). Widok zmienisz "
        "polem nad listą albo F7.",
        """W widoku **OKLCH**: L — jasność (0–1), C — nasycenie, H — odcień w stopniach. To wartości zapisane
w sesji ([OKLCH](help:concept.oklch)).

W widoku **HSL**: H°, S%, L% koloru **po** dopasowaniu do sRGB — tylko do odczytu i edycji, bo sesja
zawsze przechowuje OKLCH. Odcień HSL różni się od odcienia OKLCH, więc nie porównuj liczb między
widokami ([widok wartości](help:menu.view.values)).""",
        P,
    ),
    "palette.col.lock": Topic(
        "Kłódka (🔒)",
        "Kolor z kłódką nie zmienia się przy generowaniu. Jego warunki i zależności nadal wpływają na "
        "pozostałe kolory.",
        """Zobacz [kłódka](help:palette.lock).""",
        P,
    ),
    "palette.col.contrast": Topic(
        "Kontrast z tłem",
        "Kontrast koloru z tłem (kolor 0) w metryce z Globalnych: WCAG 2.1 (1–21) albo APCA |Lc|.",
        """Wartość, jaką ma kolor teraz — szybki podgląd bez otwierania Analizy. Dla samego tła pokazuje „—”.
Wymagany zakres ustawiasz warunkiem [kontrast z tłem](help:cond.contrast_bg). Metryka:
[WCAG albo APCA](help:concept.contrast).""",
        P,
    ),
    "palette.col.de_min": Topic(
        "ΔE min",
        "Najmniejsza odległość tego akcentu od pozostałych akcentów. Mała wartość = akcent łatwo pomylić "
        "z innym.",
        """Liczone tylko dla akcentów, w skali metody ΔE z Globalnych ([ΔE](help:concept.delta_e)).
Porównaj z warunkiem [odległość od akcentów](help:cond.min_distance). Która para jest najbliżej, zobaczysz
w macierzy ΔE na zakładce Analiza.""",
        P,
    ),
    # --- akcje listy ---
    "palette.add": Topic(
        "Dodaj akcent (Ins / A)",
        "Dodaje nowy akcent na końcu listy (najwyżej 14 akcentów). Dostaje domyślne warunki roli akcentu.",
        """Nowy akcent dostaje kolejny odcień startowy i dziedziczy domyślne warunki akcentów z Globalnych.
Jego kolor wstępny zostanie zastąpiony przy najbliższym generowaniu. Liczba akcentów wpływa na układ odcieni: przy schemacie
„równo po kole” cele rozkładają się na wszystkie akcenty. Ctrl+Z cofa dodanie.""",
        P,
    ),
    "palette.remove": Topic(
        "Usuń kolor (Del)",
        "Usuwa zaznaczony akcent (tło, tekst i ostatni akcent zostają). Zależności, które go wskazywały, "
        "zostaną oznaczone jako zerwane.",
        """Zależność innego koloru, która wskazywała usunięty akcent, zostaje i dostaje czerwoną ramkę
z napisem „⚠ zerwana” — wybierz dla niej nowy cel albo ją usuń. Zerwane zależności nie są liczone.
Ctrl+Z przywraca usunięty kolor razem z powiązaniami.""",
        P,
    ),
    "palette.lock": Topic(
        "Kłódka (L)",
        "Zamraża kolor: generowanie go nie zmienia. Jego warunki i zależności nadal obowiązują pozostałe "
        "kolory.",
        """Zablokuj kolory, które już ci odpowiadają (np. tło z istniejącego motywu), i generuj resztę.
Silnik traktuje zablokowany kolor jako stały punkt: inne kolory muszą spełniać zależności i warunki
względem niego (np. kontrast z zablokowanym tłem). Ręcznie możesz dalej zmieniać zablokowany kolor
w edytorze. Tryb „uzupełnianie” na zakładce Źródło blokuje wklejone kolory automatycznie.""",
        P,
    ),
    "palette.move": Topic(
        "Przesuń akcent (Alt+↑ / Alt+↓)",
        "Zmienia kolejność akcentów. Tło i tekst zostają na miejscach 0 i 1.",
        """Kolejność określa kolejność kolorów w eksporcie do PaletteBuildera i numery w nazwach domyślnych.
Zależności trzymają się kolorów, więc przesunięcie ich nie psuje.""",
        P,
    ),
    "palette.generate": Topic(
        "Generuj propozycje",
        "Uruchamia silnik dla kolorów bez kłódki i przechodzi do zakładki Propozycje (to samo co Ctrl+G).",
        """Zobacz [generowanie](help:menu.generate).""",
        P,
    ),
    # --- edytor ---
    "palette.editor": Topic(
        "Edytor koloru",
        "Zaznaczony kolor: próbka, nazwa, kłódka, wartość, warunki i zależności. Zmiany działają od razu "
        "i są cofalne.",
        """Nagłówek pokazuje próbkę, numer i nazwę, a pod nimi hex, wartość OKLCH i rolę (tło / tekst /
akcent). Niżej:

1. **nazwa** i **kłódka**;
2. **Wartość** — ręczna zmiana koloru suwakami;
3. **Warunki** — czego silnik ma pilnować dla tego koloru; zestaw zależy od roli (tło nie ma kontrastu
   z samym sobą, warunki odległości i skrajnego kontrastu mają tylko akcenty);
4. **Zależności** — warunki względem innych kolorów.

Każda zmiana od razu przelicza panel naruszeń i jest krokiem cofania (seria ruchów jednego suwaka to
jeden krok).""",
        P,
    ),
    "palette.editor.name": Topic(
        "Nazwa",
        "Własna nazwa koloru (np. „komentarze”). Pusta = nazwa domyślna wg roli. Enter albo wyjście z pola "
        "zapisuje.",
        """Nazwa nie wpływa na wynik, tylko ułatwia orientację w panelu naruszeń, zależnościach i Analizie.
Warto nazwać akcenty wg przeznaczenia w motywie (słowa kluczowe, ciągi, liczby…).""",
        P,
    ),
    "palette.value": Topic(
        "Wartość koloru",
        "Ręczna zmiana bieżącego koloru. Suwaki pokazują gradient: jak zmieni się kolor, gdy przesuniesz "
        "dany kanał.",
        """Zmieniasz kolor bezpośrednio, bez silnika — np. żeby dopracować propozycję. Pasek każdego suwaka
jest gradientem prawdziwych kolorów: od lewej do prawej widać kolor po zmianie tylko tego jednego
kanału. Obsługa: przeciąganie, klik, ←/→ (Shift ×10, Ctrl ×0.1), Home/End, kółko myszy, albo wpis
w polu liczbowym i Enter.

Widok OKLCH edytuje [L](help:palette.value.l), [C](help:palette.value.c), [H](help:palette.value.h)
wprost. [Widok HSL](help:palette.value.hsl) edytuje H, S, L, a wynik zapisuje jako OKLCH.
Wartość wyprowadzona poza sRGB zostanie dopasowana ([gamut](help:concept.gamut)). Kolor z kłódką też
możesz zmieniać ręcznie.""",
        P,
    ),
    "palette.value.l": Topic(
        "L — jasność",
        "Jasność OKLCH od 0 (czerń) do 1 (biel). Ten sam L to ta sama jasność na oko, niezależnie od "
        "odcienia.",
        """Najważniejszy kanał dla kontrastu z tłem: to głównie różnica jasności decyduje o czytelności.
Zobacz [OKLCH](help:concept.oklch) i [wartość koloru](help:palette.value).""",
        P,
    ),
    "palette.value.c": Topic(
        "C — nasycenie",
        "Nasycenie OKLCH: 0 = szarość. Największe osiągalne C zależy od jasności i odcienia — wyżej kolor "
        "wychodzi poza sRGB.",
        """Gradient na pasku pokazuje, gdzie kończy się sRGB: dalej kolor zostanie ściągnięty do gamutu
([gamut](help:concept.gamut)). Zakres suwaka: 0–0.37.""",
        P,
    ),
    "palette.value.h": Topic(
        "H — odcień",
        "Odcień OKLCH w stopniach (0–360, zawija się). Przy C bliskim 0 odcień praktycznie nie ma znaczenia.",
        """Dla szarego koloru pasek pokazuje odcienie przy umiarkowanym nasyceniu, żeby było widać, dokąd
prowadzi zmiana. Odcień OKLCH nie jest tym samym co odcień HSL ([OKLCH](help:concept.oklch)).""",
        P,
    ),
    "palette.value.hsl": Topic(
        "H / S / L w widoku HSL",
        "Edycja koloru w HSL: H° odcień, S% nasycenie, L% jasność. Wynik zapisuje się w sesji jako OKLCH.",
        """Wartości HSL liczone są z koloru po dopasowaniu do sRGB. Każda zmiana przelicza kolor na OKLCH,
więc drobne zaokrąglenia są możliwe. Jasność L% w HSL nie jest percepcyjna — dwa kolory o tym samym L%
mogą wyglądać na różnie jasne. Do pracy z warunkami wygodniejszy jest widok OKLCH
([widok wartości](help:menu.view.values)).""",
        P,
    ),
}
