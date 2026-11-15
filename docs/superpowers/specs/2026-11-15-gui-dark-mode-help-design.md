# GUI: przełączany tryb ciemny + pomoc kontekstowa — projekt

Data: 2026-11-15. Gałąź robocza `gui`, na koniec scalenie do `main` (decyzja użytkownika: „na końcu wszystko scal”).

## Intencja (słowa użytkownika)

„wprowadź proszę tryb ciemny do tego GUI, Wyjaśnij każdą pojedynczą rzecz wewnątrz aplikacji poprzez szybkie
tooltipy z możliwością rozwinięcia do bardziej rozbudowanej zakładki pomocy. Czytelność, przejrzystość i wygoda
użytkownika jest wszystkim.”

Mechanizm rozwinięcia wybrany przez użytkownika: **wariant 1** — podpowiedź z dopiskiem „F1 — więcej”, F1 nad
elementem otwiera pomoc na tym temacie; pomoc ma spis treści i wyszukiwarkę.

Akceptacja projektu (2026-11-15, wiążące): „tak, przy czym skup się w pomocy na tym, jak działa program, nie na
tym, jak działa kolor. na ten temat również napisz, ale relatywnie mniej” → treść pomocy opisuje przede wszystkim
działanie programu (co robi element, jak wpływa na silnik/propozycje/naruszenia, jak z niego korzystać); tematy
o teorii koloru (OKLCH, ΔE, WCAG/APCA, daltonizm, gamut) są krótkie i praktyczne.

## Stan dziś

- `gui/app.py:521` `_apply_theme`: ciemna paleta tylko gdy Qt wykryje ciemny motyw systemu albo
  `ALGOPALETTE_THEME=dark`. Brak przełącznika w programie; na Manjaro wykrywanie bywa zawodne.
- Kolory na sztywno: `HARD/SOFT/OK_COLOR` (`app.py:40`), `#d04040` w `relations.py:97`, `globals_tab.py:409`,
  `source_tab.py:142`, `widgets.py:243`, plakietki źródeł w `conditions.py:208`, `WARN_COLOR` w `palette_tab.py`.
- ~15 podpowiedzi w całym GUI; F1 = `QMessageBox` z listą skrótów (`HELP_TEXT`, `app.py:500`).

## Cele

1. Motyw: **systemowy / jasny / ciemny** w menu Widok (radio), przełączany na żywo bez restartu, zapamiętany
   między uruchomieniami. „Systemowy” śledzi zmianę motywu systemu w trakcie pracy. `ALGOPALETTE_THEME` zostaje
   jako nadpisanie na starcie.
2. Kolory semantyczne (błąd/ostrzeżenie/OK, plakietki źródeł, ramki błędów) zależne od motywu, czytelne w obu
   (kontrast tekstu z tłem ≥ 4.5:1 WCAG — sprawdzany testem własnym kodem `algopalette.color`).
3. **Każdy element** interfejsu ma szybką podpowiedź: tytuł + 1–2 zdania + „F1 — więcej”. Dotyczy: przycisków,
   pól, list, suwaków, przełączników, etykiet pól, nagłówków kolumn tabel, zakładek, akcji menu/paska, wykresów
   Analizy, panelu naruszeń, wierszy warunków i zależności (każdy typ osobno), plakietek źródła wartości.
4. Podpowiedzi „szybkie”: opóźnienie pojawienia ~300 ms (domyślne Qt ~700 ms).
5. **Panel Pomocy**: dokowany z prawej (domyślnie ukryty, można odczepić), zawiera wyszukiwarkę, drzewo tematów
   pogrupowane wg zakładek + tematy ogólne (Pierwsze kroki, Pojęcia: OKLCH, ΔE, WCAG/APCA, daltonizm, gamut,
   twarde/miękkie, źródła wartości; Skróty klawiszowe), treść z linkami między tematami, wstecz/dalej.
   Dokowanie zamiast okna modalnego: opisywany element zostaje widoczny podczas czytania.
6. F1: temat elementu pod kursorem (zakładka na pasku zakładek → temat zakładki; sekcja nagłówka tabeli → temat
   kolumny; inaczej najbliższy przodek z kluczem pomocy), gdy brak — element z fokusem, gdy brak — spis treści.
   F1 przy otwartym panelu na tym samym temacie zamyka panel. Shift+F1: tryb „kliknij element, by zobaczyć
   pomoc” (dla obsługi samą myszą); Esc wychodzi. Menu Pomoc: Pomoc (F1), Pierwsze kroki, Skróty klawiszowe,
   Tryb „kliknij, by zobaczyć pomoc” (Shift+F1).

## Nie-cele

- TUI bez zmian. Brak tłumaczeń (tylko polski). Rdzeń (model/silnik/io) bez zmian poza ewentualnym miejscem na
  ustawienia GUI w `config_dir()`.

## Anty-cele (porażka, nawet gdy „działa”)

- Podpowiedzi-tautologie („Nasycenie — nasycenie”). Każda mówi, CO robi element i jak wpływa na wynik/silnik.
- Treść pomocy niezgodna z zachowaniem programu (pomoc musi opisywać faktyczny kod, nie spec z pamięci).
- Ciemny motyw z nieczytelnymi elementami (kolory na sztywno, białe tła z jasnego motywu, wykresy z jasną ramką).
- Pomoc zasłaniająca pracę (modalne okna) albo podpowiedzi z opóźnieniem tak małym, że migają przy każdym ruchu.

## Podejścia (rozważone)

1. **Podpowiedź + F1 do dokowanego panelu pomocy** — WYBRANE przez użytkownika.
2. Stały panel boczny pokazujący opis elementu pod kursorem — odrzucony (zabiera szerokość).
3. Ikonki ⓘ przy sekcjach — odrzucony (szum w gęstym UI).

## Architektura (decyzje agenta)

- `gui/theme.py`: `ThemeMode = "system"|"light"|"dark"`, budowa palety Qt dla obu motywów, kolory semantyczne
  (`theme.colors()` → aktualny zestaw), `apply(app, mode)`, sygnał zmiany motywu; ustawienia w
  `config_dir()/gui.json` (`{"theme": ...}`, odczyt odporny na brak/uszkodzenie pliku). Widżety z kolorami na
  sztywno pobierają je z `theme.colors()` i odświeżają się na zmianę motywu (`refresh_views` + `update()`
  rysowanych widżetów).
- `gui/help_content.py`: same dane — `TOPICS: dict[str, Topic]`, `Topic(title, short, body_md, group)`;
  treść w Markdown (`QTextBrowser.setMarkdown`), linki `help:<klucz>`.
- `gui/help.py`: `attach(widget, key)` (tooltip HTML z tytułem/krótkim opisem/„F1 — więcej”, właściwość
  `help_key`), pomocniki dla nagłówków tabel, zakładek i akcji; `resolve_key(app)` (logika F1); `HelpPanel`
  (QDockWidget); tryb Shift+F1 (filtr zdarzeń); proxy-styl z opóźnieniem podpowiedzi.
- `HELP_TEXT` i `QMessageBox` F1 znikają — skróty stają się tematem pomocy.

## Weryfikacja

- Test pokrycia: po zbudowaniu okna (każda zakładka, edytor zaznaczonego koloru każdej roli, warunki każdego
  typu, zależność każdego typu, propozycje z wynikiem) każdy widżet interaktywny i każda etykieta pola ma klucz
  pomocy, który istnieje w `TOPICS`; każdy temat ma niepusty krótki opis i treść; linki `help:` prowadzą do
  istniejących tematów.
- Testy: przełączanie motywu (paleta aplikacji, zapis/odczyt ustawień, kolory semantyczne), kontrast kolorów
  semantycznych w obu motywach, F1 (rozstrzyganie klucza, zakładka, nagłówek, fokus, spis treści), wyszukiwarka.
- Zrzuty ekranu wszystkich zakładek w obu motywach + panel pomocy, obejrzane.
- Pełny `pytest`, `ruff check`, `ruff format --check`, `ty check` — zero uwag.
- Przegląd całości (Opus xhigh) na koniec, w tym zgodność treści pomocy z kodem.

## Zostawione wykonawcy

Dokładne sformułowania treści (zgodne z kodem), dokładne odcienie kolorów motywu ciemnego (w granicach
kontrastu), układ panelu pomocy.
