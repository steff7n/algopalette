"""Pomoc: tematy ogólne — pierwsze kroki, skróty, korzystanie z pomocy."""

from algopalette.gui.help_content.topic import Topic

G = "Ogólne"

TOPICS: dict[str, Topic] = {
    "general.start": Topic(
        "Pierwsze kroki",
        "Typowa praca: wybierz preset, dopasuj zasady kolorów, wygeneruj propozycje, przejmij "
        "najlepszą i wyeksportuj paletę.",
        """AlgoPalette nie każe ci dobierać kolorów ręcznie. Opisujesz, **jakie zasady** ma spełniać
paleta, a silnik szuka kolorów, które spełniają je wszystkie naraz.

**Typowy przebieg pracy**

1. **Zasady (F2) → tło i preset.** Wybierz, czy tło ma być ciemne, czy jasne, i nałóż
   [preset](help:rules.preset) — gotowy zestaw zasad dla tła, tekstu i akcentów, układu odcieni
   i rozrzutu jasności. To punkt wyjścia: każdą wartość zmienisz niżej.
2. **Zasady → kolory.** [Pasek kolorów](help:rules.strip) wybiera, czyje zasady edytujesz. Każdy kolor
   ma komplet własnych zasad; zaznacz kilka kolorów naraz, żeby zmienić je jednym ruchem. Liczbę
   kolorów ustawiasz obok paska.
3. **Generuj (Ctrl+G).** Silnik liczy propozycje dla wszystkich kolorów bez kłódki. Wynik oglądasz
   na zakładce **Propozycje (F3)**: dwuklik przejmuje całą propozycję, dwuklik na pojedynczym kolorze
   przejmuje tylko ten kolor.
4. **Paleta (F4) i panel naruszeń.** Paleta pokazuje gotowe kolory: możesz je poprawić ręcznie,
   nazwać i zablokować kłódką. Panel naruszeń na dole okna stale pokazuje, które zasady bieżąca
   paleta łamie i o ile; klik w naruszenie prowadzi do zasady. **Analiza (F5)** pokazuje paletę na
   kole odcieni, w przekroju jasność–nasycenie i w macierzach odległości oraz kontrastu, także przy
   symulacji daltonizmu.
5. **Eksport.** Ctrl+E kopiuje paletę do schowka w formacie okna „Wczytaj…” PaletteBuildera,
   Ctrl+Shift+E zapisuje ją do pliku.

**Masz już paletę, od której chcesz zacząć?** Zakładka **Źródło (F6)** przyjmuje wklejone kolory
i może je uzupełnić, odczytać z nich charakter albo przenieść je na tło o odwrotnej polaryzacji.

**Nic nie przepada.** Każdą zmianę cofniesz Ctrl+Z, a sesja zapisuje się sama (autozapis) i wraca przy
następnym uruchomieniu. Zobacz też: [skróty klawiszowe](help:general.shortcuts),
[zasady twarde i miękkie](help:concept.hard_soft).""",
        G,
    ),
    "general.shortcuts": Topic(
        "Skróty klawiszowe",
        "Wszystkie skróty programu: plik, edycja, generowanie, zakładki, lista kolorów, suwaki i pola "
        "liczbowe.",
        """| Skrót | Działanie |
|---|---|
| F1 | pomoc dla elementu pod kursorem (ponownie — zamyka pomoc) |
| Shift+F1 | tryb „kliknij element, żeby zobaczyć jego pomoc” (Esc — wyjście) |
| Ctrl+G | generuj propozycje |
| Ctrl+Z / Ctrl+Y | cofnij / ponów (także Ctrl+Shift+Z) |
| Ctrl+S / Ctrl+Shift+S | zapisz / zapisz jako |
| Ctrl+O | wczytaj sesję |
| Ctrl+N | nowa paleta (cofalna przez Ctrl+Z) |
| Ctrl+E | paleta do schowka dla PaletteBuildera |
| Ctrl+Shift+E | plik dla PaletteBuildera |
| F2–F6 | zakładki Zasady, Propozycje, Paleta, Analiza, Źródło |
| F7 | widok wartości HSL / OKLCH |
| Ctrl+Q | wyjście |

**Lista kolorów na Palecie** (gdy ma fokus): Ins albo A — dodaj akcent, Del — usuń, L — kłódka,
Alt+↑ / Alt+↓ — przesuń akcent. Te same akcje są pod listą jako przyciski.

**Pasek kolorów w Zasadach:** ←/→ przenosi fokus, spacja zaznacza kolor, Ctrl+spacja dokłada go do
zaznaczenia albo odejmuje, Ctrl+A zaznacza wszystkie akcenty; myszą Ctrl+klik i Shift+klik.

**Listy z kołem odcieni** (własna lista odcieni, unikane kolory): Alt+↑ / Alt+↓ przestawia pozycję,
Delete na przycisku ✕ ją usuwa — tak samo usuwa się zakazany przedział pod suwakiem.

**Suwaki:** ←/→ krok, Shift — krok ×10, Ctrl — krok ×0.1, Home/End — skraj zakresu,
spacja przełącza uchwyt w suwaku zakresu, mysz: klik albo przeciąganie, kółko myszy — krok (gdy suwak
ma fokus).

**Pola liczbowe:** Enter albo wyjście z pola zatwierdza wpis, ↑/↓ — krok; puste pole zakresu oznacza
„bez ograniczenia” z tej strony.""",
        G,
    ),
    "general.help": Topic(
        "Jak korzystać z pomocy",
        "Najedź na element, żeby zobaczyć krótki opis. F1 otwiera pełny opis w panelu Pomocy, Shift+F1 "
        "pozwala wskazać element kliknięciem.",
        """**Podpowiedzi.** Każdy element okna ma krótką podpowiedź — wystarczy na chwilę zatrzymać nad nim
kursor. Dopisek „F1 — więcej” oznacza, że pełny opis czeka w panelu Pomocy.

**F1.** Otwiera panel Pomocy na temacie elementu pod kursorem. Gdy kursor nie wskazuje żadnego
elementu z opisem, pomoc dotyczy elementu, w którym piszesz (z fokusem), a gdy i tego brak — pokazuje
spis treści. Drugie F1 na tym samym temacie zamyka panel.

**Shift+F1** (albo Pomoc → „Kliknij element…”) zmienia kursor w znak zapytania: następne kliknięcie
niczego nie zmienia w palecie, tylko otwiera pomoc klikniętego elementu. Esc anuluje.

**Panel Pomocy** jest przypięty z prawej strony okna, żeby opisywany element był dalej widoczny.
Możesz go odczepić jako osobne okno (przycisk na pasku tytułu panelu) albo zamknąć. Na górze są
przyciski wstecz/dalej i wyszukiwarka — szuka w tytułach i treści, bez względu na polskie znaki
i wielkość liter („jasnosc” znajdzie „jasność”). Niżej spis tematów pogrupowany według zakładek.""",
        G,
    ),
}
