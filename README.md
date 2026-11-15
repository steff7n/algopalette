# AlgoPalette

Generator palet kolorów pod motywy IDE, z interfejsem graficznym (Qt / PySide6). Cały rachunek odbywa się w
**OKLCH / OKLab**; na hex sRGB program przelicza dopiero na końcu. Paletę opisujesz warunkami — dla całej palety, dla
każdego koloru z osobna i jako zależności między kolorami — a silnik optymalizacji szuka kolorów, które spełniają
je wszystkie naraz. Gdy warunki się wykluczają, program pokazuje, które są złamane i o ile.

AlgoPalette to osobny program. Z PaletteBuilderem łączy go tylko jedna akcja: **przeniesienie gotowej palety do
PaletteBuildera** (w jedną stronę).

## Uruchamianie

```sh
algopalette                  # przywraca ostatnią sesję (autozapis) albo zaczyna od nowej palety
algopalette moja.json        # otwiera zapisany plik sesji
algopalette --fresh          # ignoruje autozapis
algopalette --tui            # stary interfejs w terminalu (Textual)
```

Z kodu źródłowego: `uv run algopalette`. Instalacja komendy: `uv tool install --editable .` (po zmianie
zależności: `uv tool install --editable . --force`).

**Motyw okna:** Widok → Motyw → systemowy / jasny / ciemny. Zmienia się od razu i zostaje zapamiętany
(`~/.config/algopalette/gui.json`). „Systemowy” idzie za motywem pulpitu, także po zmianie w trakcie pracy.
`ALGOPALETTE_THEME=dark|light` wymusza motyw na starcie, gdy wykrywanie motywu pulpitu zawodzi.

## Pomoc w programie

Każdy element okna ma podpowiedź — wystarczy zatrzymać nad nim kursor (ok. 0,3 s). **F1** otwiera panel Pomocy
(przypięty z prawej, można go odczepić) na pełnym opisie elementu pod kursorem; ponowne F1 zamyka panel. Gdy
kursor nie wskazuje elementu z opisem, pomoc dotyczy pola z fokusem, a w ostateczności pokazuje spis treści.
F1 działa też w otwartym menu. **Shift+F1** zmienia kursor w znak zapytania: następne kliknięcie niczego nie
zmienia, tylko otwiera pomoc klikniętego elementu (Esc anuluje). Panel ma spis tematów według zakładek,
wyszukiwarkę (bez względu na polskie znaki: „jasnosc” znajdzie „jasność”), linki między tematami i wstecz/dalej.
Menu Pomoc: Pierwsze kroki, Skróty klawiszowe, Spis treści.

## Zakładki

| Klawisz | Zakładka | Co tam jest |
|---|---|---|
| F2 | **Paleta** | lista kolorów (tło, tekst, akcenty) i edytor zaznaczonego koloru: wartość L/C/H (suwaki z gradientem koloru), warunki, zależności |
| F3 | **Globalne** | nastrój, polaryzacja, metryki, układ odcieni, rozrzut jasności, daltonizm, gamut, optymalizator, domyślne warunki ról |
| F4 | **Propozycje** | generowanie, przegląd propozycji, przejmowanie całej palety albo pojedynczego koloru |
| F5 | **Źródło** | paleta wyjściowa (wklejona lub z pliku) i trzy tryby startu |
| F6 | **Analiza** | koło odcieni, przekrój gamutu jasność–nasycenie, macierz odległości ΔE i kontrastu (także przy daltonizmie), próbki „Aa” |

Na dole zawsze widać **panel naruszeń bieżącej palety** (✗ twarde, ~ miękkie; granicę z zakładkami można
przeciągać). F1 — pomoc dla elementu pod kursorem, wszystkie skróty: Pomoc → Skróty klawiszowe.

**F7 (albo pole „widok wartości” nad listą kolorów) przełącza widok OKLCH ↔ HSL.** W HSL tabela pokazuje H°, S%,
L%, a suwaki „Wartość” w edytorze edytują kolor w HSL (zapis i tak trafia do sesji jako OKLCH). Warunki,
zależności, nastroje, silnik i koło odcieni w Analizie zostają w OKLCH — odcień HSL i odcień OKLCH tego samego
koloru potrafią różnić się o kilkadziesiąt stopni. Przełączenie widoku nie jest krokiem cofania; zapamiętuje się
w sesji.

Najważniejsze skróty: `F1` pomoc, `Shift+F1` wskaż element, `Ctrl+G` generuj, `Ctrl+Z` / `Ctrl+Y` cofnij / ponów, `Ctrl+S` zapisz
(`Ctrl+Shift+S` jako…), `Ctrl+O` wczytaj, `Ctrl+N` nowa paleta, `Ctrl+E` paleta do schowka dla PaletteBuildera
(`Ctrl+Shift+E` — do pliku), `Ctrl+Q` wyjście. Na liście kolorów (gdy ma fokus): `Ins`/`A` dodaj akcent,
`Del` usuń, `L` kłódka, `Alt+↑/↓` przesuń — te same akcje są pod listą jako przyciski. Suwaki: przeciąganie
myszą, `←/→` krok, `Shift` ×10, `Ctrl` ×0.1, `Home/End`, spacja przełącza uchwyt zakresu, kółko myszy (gdy suwak
ma fokus); w polach liczbowych Enter zatwierdza, `↑/↓` krok, puste pole = bez ograniczenia.

## Jak opisujesz paletę

Każda wartość ma **źródło**: `[nastrój]` (ustawił ją nastrój), `[globalne]` (zmieniona w ustawieniach globalnych)
albo `[własne]` (ustawiona w tym kolorze; „↺ dziedzicz” wraca do wartości globalnej). Każdy warunek można włączyć
lub wyłączyć, oznaczyć jako **twardy** (musi być spełniony) albo **miękki** (cel z wagą).

**Warunki koloru:** jasność L, nasycenie C (bezwzględne albo względne — jako ułamek największego nasycenia
możliwego w sRGB przy danej jasności i odcieniu), zakres odcienia (także przez 0°, np. 330–20), cel odcienia
± tolerancja, kontrast z tłem (WCAG 2.1 albo APCA), minimalna odległość od innych akcentów, odróżnialność przy
daltonizmie, „najsłabszy / najmocniejszy kontrast spośród akcentów” (np. pod komentarze), kłódka.

**Zależności od innych kolorów**, przykłady:

- „odcień przeciwny do akcentu 1”: odcień, `=`, 180, tol 15;
- „ciemniejszy od napisów o co najmniej 0.1”: jasność, `≤`, −0.1;
- „nasycenie co najmniej jak akcent 2”: nasycenie, `× mnożnik`, `≥`, 1.0;
- „podobny do akcentu 3, ale nie identyczny”: dwie zależności odległości, `≥ 0.03` i `≤ 0.08`;
- „w połowie między akcentem 1 a 4”: mieszanka, t = 0.5, tol ΔE 0.02.

**Ustawienia całej palety:** polaryzacja, metryka kontrastu (WCAG / APCA — APCA trafniej ocenia ciemne motywy),
metoda ΔE (`ok` i `hyab` w skali 0–1, `2000`/`itp`/`cam16` w skalach ~0–100 — progi trzeba ustawić pod metodę),
układ odcieni (równo po kole, analogiczny, dopełniający, rozszczepiony, triada, tetrada, własna lista; tolerancja,
jitter), rozrzut jasności akcentów, daltonizm (protanopia / deuteranopia / tritanopia; Machado, Viénot, Brettel;
nasilenie), sposób sprowadzania koloru spoza sRGB (`fit`), optymalizator (liczba propozycji, ziarno, budżet,
limit czasu, minimalna różnorodność propozycji).

**Nastroje** wypełniają ustawienia globalne gotowymi wartościami: neutralny, chłodny mglisty, neon, ziemisty,
pastel, nocny wysoki kontrast, monochromatyczny z jednym akcentem, retro terminal, jesienny. Wszystko, co
ustawiły, widać i można zmienić. Bieżące ustawienia zapiszesz jako własny nastrój.

## Generowanie

`Ctrl+G` (albo przycisk na zakładce Paleta / Propozycje) liczy kilka propozycji dla wszystkich kolorów bez kłódki; można też
generować tylko zaznaczony kolor. Te same ustawienia i to samo ziarno dają zawsze te same propozycje — budżet
liczony jest w krokach, nie w sekundach (limit czasu to tylko bezpiecznik; propozycja przerwana limitem jest
oznaczona jako niepowtarzalna). Propozycja „✗ łamie twarde” nie spełnia warunków — lista pod nią mówi, które
i o ile. Dwuklik (albo przycisk) na propozycji przejmuje całą, dwuklik na kolorze — tylko ten kolor. `Ctrl+Z`
cofa.

## Paleta wyjściowa (zakładka Źródło)

Wklej kolory (hex, `oklch(…)`, `rgb(…)`; dowolne separatory) albo weź je z pliku sesji lub z bieżącej palety,
wskaż numer tła i tekstu, wybierz tryb:

- **uzupełnianie** — podane kolory trafiają do kolejnych miejsc z kłódką, resztę generujesz;
- **charakter** — program odczytuje profil palety (dominujące odcienie, nasycenie, jasność, zabarwienie tła)
  i ustawia nim ustawienia globalne; opcjonalnie unika samych kolorów źródła;
- **przeniesienie** — ta sama paleta na tle o innej polaryzacji: każdy akcent zachowuje odcień, nasycenie
  względne i kontrast z tłem.

## Pliki

| Co | Gdzie |
|---|---|
| sesje AlgoPalette (`algopalette.v1`, pełny stan) | domyślnie `~/.local/share/algopalette/palettes/` |
| autozapis ostatniej sesji | `~/.local/state/algopalette/last.json` (start z innego pliku albo `--fresh` przenosi go do `last.prev.json`, uszkodzony — do `last.corrupt-<czas>.json`) |
| własne nastroje | `~/.config/algopalette/moods.json` |
| plik dla PaletteBuildera (opcjonalny) | domyślnie `~/Dokumenty/motifs/` |

**Przeniesienie do PaletteBuildera** (`Ctrl+E`): paleta trafia do schowka w formacie, który PaletteBuilder
przyjmuje w oknie „Wczytaj…” (wklej tam). `Ctrl+Shift+E` zapisuje to samo do pliku (domyślnie
`~/Dokumenty/motifs/`).

## Czego nie robić

- Nie zapisuj palety z PaletteBuildera z powrotem do pliku sesji AlgoPalette — przepływ jest jednokierunkowy;
  AlgoPalette nie czyta plików PaletteBuildera.
- Progi odległości zależą od metody ΔE (0.08 w `ok` ≈ 12.5 w `2000`). Zmiana metody w zakładce Globalne
  przelicza progi przybliżonym przelicznikiem — sprawdź je potem, jeśli zależy Ci na dokładnych wartościach.
- Nie traktuj propozycji oznaczonej „✗ łamie twarde” ani „⏱ niepowtarzalna” jak gotowego wyniku.
- Zmiana polaryzacji albo metryki kontrastu przelicza domyślne zakresy (nastrój wbudowany nakłada ponownie,
  własny nastrój zdejmuje — jego liczby dotyczą polaryzacji, w której go zapisano) — ręczne zmiany domyślnych
  warunków ról przepadają (`Ctrl+Z` je przywraca).

## Rozwój

```sh
uv run pytest -q          # testy (pełny zestaw ok. 2 min; GUI w trybie offscreen)
uv run ruff check && uv run ruff format --check && uv run ty check
```

Projekt i decyzje: `docs/superpowers/specs/2026-11-14-algopalette-design.md`, plan:
`docs/superpowers/plans/2026-11-14-algopalette.md`, stan prac: `HANDOFF.md`.
