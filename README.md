# AlgoPalette

Generator palet kolorów pod motywy IDE, z interfejsem w terminalu (TUI). Cały rachunek odbywa się w **OKLCH /
OKLab**; na hex sRGB program przelicza dopiero na końcu. Paletę opisujesz warunkami — dla całej palety, dla
każdego koloru z osobna i jako zależności między kolorami — a silnik optymalizacji szuka kolorów, które spełniają
je wszystkie naraz. Gdy warunki się wykluczają, program pokazuje, które są złamane i o ile.

AlgoPalette to osobny program. Z PaletteBuilderem łączy go tylko jedna akcja: **przeniesienie gotowej palety do
PaletteBuildera** (w jedną stronę).

## Uruchamianie

```sh
algopalette                  # przywraca ostatnią sesję (autozapis) albo zaczyna od nowej palety
algopalette moja.json        # otwiera zapisany plik sesji
algopalette --fresh          # ignoruje autozapis
```

Z kodu źródłowego: `uv run algopalette`. Instalacja komendy: `uv tool install --editable .`.

Terminal powinien obsługiwać 24-bitowy kolor (np. Ghostty, `COLORTERM=truecolor`) — próbki pokazują wtedy
dokładnie te hexy, które trafią do pliku.

## Zakładki

| Klawisz | Zakładka | Co tam jest |
|---|---|---|
| F2 | **Paleta** | lista kolorów (tło, tekst, akcenty) i edytor zaznaczonego koloru: wartość L/C/H, warunki, zależności |
| F3 | **Globalne** | nastrój, polaryzacja, metryki, układ odcieni, rozrzut jasności, daltonizm, gamut, optymalizator, domyślne warunki ról |
| F4 | **Propozycje** | generowanie, przegląd propozycji, przejmowanie całej palety albo pojedynczego koloru |
| F5 | **Źródło** | paleta wyjściowa (wklejona lub z pliku) i trzy tryby startu |
| F6 | **Analiza** | koło odcieni, wykres jasność–nasycenie, macierz odległości ΔE i kontrastu (także przy daltonizmie), próbki „Aa” |

Na dole zawsze widać **panel naruszeń bieżącej palety** (✗ twarde, ~ miękkie). F1 pokazuje wszystkie skróty.

Najważniejsze skróty: `g` generuj, `Ctrl+Z` / `Ctrl+Y` cofnij / ponów, `Ctrl+S` zapisz, `Ctrl+O` wczytaj,
`Ctrl+E` przenieś do PaletteBuildera, `Ctrl+Q` wyjście. Na liście kolorów: `a` dodaj akcent, `x` usuń,
`l` kłódka, `Shift+↑/↓` przesuń. Suwaki: `←/→` krok, `Shift` ×10, `Ctrl` ×0.1, `Home/End`, spacja przełącza
uchwyt zakresu, mysz działa; w polach liczbowych Enter zatwierdza, puste pole = bez ograniczenia.

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

`g` (albo przycisk na zakładce Propozycje) liczy kilka propozycji dla wszystkich kolorów bez kłódki; można też
generować tylko zaznaczony kolor. Te same ustawienia i to samo ziarno dają zawsze te same propozycje — budżet
liczony jest w krokach, nie w sekundach (limit czasu to tylko bezpiecznik; propozycja przerwana limitem jest
oznaczona jako niepowtarzalna). Propozycja „✗ łamie twarde” nie spełnia warunków — lista pod nią mówi, które
i o ile. `Enter`/`t` przejmuje całą propozycję, `Enter`/`c` na kolorze — tylko ten kolor. `Ctrl+Z` cofa.

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
| autozapis ostatniej sesji | `~/.local/state/algopalette/last.json` |
| własne nastroje | `~/.config/algopalette/moods.json` |
| plik dla PaletteBuildera (opcjonalny) | domyślnie `~/Dokumenty/motifs/` |

**Przeniesienie do PaletteBuildera** (`Ctrl+E`): paleta trafia do schowka w formacie, który PaletteBuilder
przyjmuje w oknie „Wczytaj…” (wklej tam). Program pyta też, czy zapisać plik — Esc = tylko schowek.

## Czego nie robić

- Nie zapisuj palety z PaletteBuildera z powrotem do pliku sesji AlgoPalette — przepływ jest jednokierunkowy;
  AlgoPalette nie czyta plików PaletteBuildera.
- Nie porównuj progów odległości między metodami ΔE: 0.08 w `ok` to coś zupełnie innego niż 0.08 w `2000`.
  Po zmianie metody ustaw progi na nowo.
- Nie traktuj propozycji oznaczonej „✗ łamie twarde” ani „⏱ niepowtarzalna” jak gotowego wyniku.
- Zmiana polaryzacji albo metryki kontrastu przelicza domyślne zakresy (albo nakłada nastrój ponownie) —
  ręczne zmiany domyślnych warunków ról z tej chwili przepadają (`Ctrl+Z` je przywraca).

## Rozwój

```sh
uv run pytest -q          # testy (pełny zestaw ok. 100 s)
uv run ruff check && uv run ruff format --check && uv run ty check
```

Projekt i decyzje: `docs/superpowers/specs/2026-11-14-algopalette-design.md`, plan:
`docs/superpowers/plans/2026-11-14-algopalette.md`, stan prac: `HANDOFF.md`.
