# AlgoPalette

Generator palet kolorów pod motywy IDE, z interfejsem graficznym (Qt / PySide6) i natywnym silnikiem
optymalizacji w Ruście. Cały rachunek odbywa się w **OKLCH / OKLab**; na hex sRGB program przelicza dopiero na
końcu. Paletę opisujesz **zasadami** — każdy kolor ma komplet własnych, do tego zależności między kolorami
i kilka ustawień całej palety — a silnik szuka kolorów, które spełniają je wszystkie naraz. Gdy zasady się
wykluczają, program pokazuje, które są złamane i o ile.

AlgoPalette to osobny program. Z PaletteBuilderem łączy go tylko jedna akcja: **przeniesienie gotowej palety do
PaletteBuildera** (w jedną stronę).

## Uruchamianie

```sh
algopalette                  # przywraca ostatnią sesję (autozapis) albo zaczyna od nowej palety
algopalette moja.json        # otwiera zapisany plik sesji
algopalette --fresh          # ignoruje autozapis
```

Z kodu źródłowego: `uv run algopalette`. Instalacja komendy: `uv tool install --editable .` — buduje przy
okazji silnik (potrzebny Rust, patrz [Rozwój](#rozwój)). Po zmianie zależności albo kodu Rust:
`uv tool install --editable . --force`.

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
| F2 | **Zasady** | wszystko, co wpływa na generowanie: preset i tło, liczba kolorów, pasek kolorów (wybór, czyje zasady edytujesz), zasady zaznaczonych kolorów i zależności, ustawienia całej palety, „Generuj propozycje” |
| F3 | **Propozycje** | postęp generowania, przegląd propozycji, przejmowanie całej palety albo pojedynczego koloru |
| F4 | **Paleta** | lista kolorów (tło, tekst, akcenty) i edytor zaznaczonego koloru: nazwa, kłódka, wartość L/C/H (suwaki z gradientem koloru) |
| F5 | **Analiza** | koło odcieni z zasadą odcienia i celem układu, przekrój gamutu jasność–nasycenie, macierz odległości ΔE i kontrastu (także przy daltonizmie), próbki „Aa” |
| F6 | **Źródło** | paleta wyjściowa (wklejona lub z pliku) i trzy tryby startu |

Na dole zawsze widać **panel naruszeń bieżącej palety** (✗ twarde, ~ miękkie; granicę z zakładkami można
przeciągać). Klik w naruszenie otwiera „Zasady” na kolorze, którego zasada jest złamana. F1 — pomoc dla
elementu pod kursorem, wszystkie skróty: Pomoc → Skróty klawiszowe.

**F7 (albo pole „widok wartości” nad listą kolorów) przełącza widok OKLCH ↔ HSL.** W HSL tabela pokazuje H°, S%,
L%, a suwaki „Wartość” w edytorze edytują kolor w HSL (zapis i tak trafia do sesji jako OKLCH). Zasady,
zależności, presety, silnik i koło odcieni w Analizie zostają w OKLCH — odcień HSL i odcień OKLCH tego samego
koloru potrafią różnić się o kilkadziesiąt stopni. Przełączenie widoku nie jest krokiem cofania; zapamiętuje się
w sesji.

Najważniejsze skróty: `F1` pomoc, `Shift+F1` wskaż element, `Ctrl+G` generuj, `Ctrl+Z` / `Ctrl+Y` cofnij / ponów, `Ctrl+S` zapisz
(`Ctrl+Shift+S` jako…), `Ctrl+O` wczytaj, `Ctrl+N` nowa paleta, `Ctrl+E` paleta do schowka dla PaletteBuildera
(`Ctrl+Shift+E` — do pliku), `Ctrl+Q` wyjście. Na liście kolorów (gdy ma fokus): `Ins`/`A` dodaj akcent,
`Del` usuń, `L` kłódka, `Alt+↑/↓` przesuń — te same akcje są pod listą jako przyciski. Pasek kolorów w „Zasadach”:
`←/→` fokus, spacja zaznacza, `Ctrl+spacja` dokłada albo odejmuje kolor, `Ctrl+A` wszystkie akcenty. Suwaki:
przeciąganie myszą, `←/→` krok, `Shift` ×10, `Ctrl` ×0.1, `Home/End`, spacja przełącza uchwyt zakresu, kółko
myszy (gdy suwak ma fokus); w polach liczbowych Enter zatwierdza, `↑/↓` krok, puste pole = bez ograniczenia.

## Jak opisujesz paletę (zakładka Zasady)

**Każdy kolor ma komplet własnych zasad.** To, co widzisz po zaznaczeniu koloru na pasku, to wszystko, co go
obowiązuje — nie ma wartości wspólnych, z których kolor coś by brał, więc nie ma też „dziedziczenia”. Zasadę
zdejmuje się jednym przyciskiem (**✕ usuń**) i wtedy nic nie ogranicza koloru w tym zakresie.

**Edycja zbiorcza.** Na pasku kolorów zaznaczasz kilka kolorów naraz (`Ctrl+klik` dokłada, `Shift+klik` zakres,
przycisk „wszystkie akcenty”). Edytor pokazuje zasady, które dotyczą każdego z nich; zmiana trafia do wszystkich
zaznaczonych jednym krokiem cofania. Gdy kolory mają zasadę ustawioną inaczej, wiersz mówi „różne”, wypisuje
wartość każdego koloru i daje wybór: „ustaw dla zaznaczonych” albo „usuń u wszystkich”.

**Zasady koloru** (każdą można włączyć lub wyłączyć, oznaczyć jako **twardą** — musi być spełniona — albo
**miękką** — cel z wagą):

- **jasność L** — zakres, z opcjonalnymi zakazanymi przedziałami;
- **nasycenie C** — zakres bezwzględny albo względny (część największego nasycenia możliwego w sRGB przy danej
  jasności i odcieniu), z zakazanymi przedziałami;
- **odcień** — jeden łuk na kole, zapisywany jako „od–do” albo „środek ± połowa szerokości” (także przez 0°,
  np. 330–20), z zakazanymi przedziałami: „dowolny odcień od 0 do 270, ale nie 60–85 i nie 140–155”;
- **kontrast z tłem** (WCAG 2.1 albo APCA; dolna i opcjonalnie górna granica);
- tylko akcenty: **odległość od innych akcentów**, **odróżnialność przy daltonizmie**, **skrajny kontrast**
  (najsłabszy albo najmocniejszy spośród akcentów, np. pod komentarze) oraz przełącznik **„układ odcieni:
  stosuj”** — czy akcent dostaje cel odcienia z układu całej palety (cel może działać razem z własnym łukiem).

Zakazane przedziały są zawsze twarde.

**Zależności od innych kolorów** (przy jednym zaznaczonym kolorze), przykłady:

- „odcień przeciwny do akcentu 1”: odcień, `=`, 180, tol 15;
- „ciemniejszy od napisów o co najmniej 0.1”: jasność, `≤`, −0.1;
- „nasycenie co najmniej jak akcent 2”: nasycenie, `× mnożnik`, `≥`, 1.0;
- „podobny do akcentu 3, ale nie identyczny”: dwie zależności odległości, `≥ 0.03` i `≤ 0.08`;
- „w połowie między akcentem 1 a 4”: mieszanka, t = 0.5, tol ΔE 0.02.

**Ustawienia całej palety** (przycisk „cała paleta” na pasku): metryka kontrastu (WCAG / APCA — APCA trafniej
ocenia ciemne motywy), metoda ΔE (`ok` i `hyab` w skali 0–1, `2000`/`itp`/`cam16` w skalach ~0–100; zmiana
przelicza progi), sposób sprowadzania koloru spoza sRGB, układ odcieni (równo po kole, analogiczny,
dopełniający, rozszczepiony, triada, tetrada, własna lista wybierana na kole; tolerancja, rozrzut losowy),
rozrzut jasności akcentów, daltonizm (protanopia / deuteranopia / tritanopia; Machado, Viénot, Brettel;
nasilenie), unikane kolory (lista z wybierakiem), generowanie (liczba propozycji, ziarno, budżet, limit czasu,
różnorodność, waga twardych, wątki).

**Presety** to gotowe zestawy zasad — 58 wbudowanych w 11 kategoriach (Podstawowe, Chłodne, Ciepłe, Natura,
Pastelowe, Świecące, Retro i druk, Ograniczone, Harmonie, Pory dnia, Dostępność), z wyszukiwarką. „Zastosuj”
zastępuje zasady wszystkich kolorów, układ odcieni i rozrzut jasności; nie rusza wartości kolorów, kłódek, nazw,
zależności, unikanych kolorów ani ustawień generowania. Wszystko, co preset ustawił, widać i można zmienić —
przy nazwie pojawia się wtedy „(zmieniony)”. Bieżące zasady zapiszesz jako własny preset. Zmiana tła (ciemne /
jasne) nakłada bieżący preset w wersji dla nowego tła, a gdy zasady są już zmienione — pyta, co zrobić.

## Generowanie

`Ctrl+G` (albo „Generuj propozycje” na dole „Zasad”) liczy propozycje dla wszystkich kolorów bez kłódki; na
zakładce Propozycje można też generować tylko zaznaczony kolor. Liczy silnik natywny, równolegle na wszystkich
rdzeniach (albo na tylu wątkach, ile ustawisz), a okno w tym czasie pozostaje responsywne i pokazuje postęp;
„Przerwij” zatrzymuje liczenie. Te same zasady i to samo ziarno dają zawsze te same propozycje, niezależnie od
liczby wątków i szybkości komputera — budżet liczony jest w ocenach palety na przebieg, nie w sekundach (limit
czasu to tylko bezpiecznik; po jego zadziałaniu propozycje są oznaczone ⏱ jako niepowtarzalne). Propozycja
„✗ łamie twarde” nie spełnia zasad — lista pod nią mówi, których i o ile. Dwuklik (albo przycisk) na propozycji
przejmuje całą, dwuklik na kolorze — tylko ten kolor. `Ctrl+Z` cofa.

## Paleta wyjściowa (zakładka Źródło)

Wklej kolory (hex, `oklch(…)`, `rgb(…)`; dowolne separatory) albo weź je z pliku sesji lub z bieżącej palety,
wskaż numer tła i tekstu, wybierz tryb:

- **uzupełnianie** — podane kolory trafiają do kolejnych miejsc z kłódką, resztę generujesz;
- **charakter** — program odczytuje profil palety (dominujące odcienie, nasycenie, jasność, zabarwienie tła)
  i wpisuje go w zasady kolorów i układ odcieni; opcjonalnie dopisuje kolory źródła do unikanych;
- **przeniesienie** — ta sama paleta na tle o innej polaryzacji: każdy akcent zachowuje odcień, nasycenie
  względne i kontrast z tłem.

## Pliki

| Co | Gdzie |
|---|---|
| sesje AlgoPalette (`algopalette.v2`, pełny stan) | domyślnie `~/.local/share/algopalette/palettes/` |
| autozapis ostatniej sesji | `~/.local/state/algopalette/last.json` (start z innego pliku albo `--fresh` przenosi go do `last.prev.json`, uszkodzony — do `last.corrupt-<czas>.json`) |
| własne presety | `~/.config/algopalette/presets.json` |
| plik dla PaletteBuildera (opcjonalny) | domyślnie `~/Dokumenty/motifs/` |

**Pliki ze starszej wersji** (`algopalette.v1`) wczytują się normalnie: wartości dziedziczone są wpisywane
w każdy kolor, zakres i cel odcienia stają się jedną zasadą odcienia, budżet jest przeliczany. Program mówi
wprost, co przy tym przepadło albo się zmieniło (np. „akcent 3: zakres i cel odcienia scalono do 40–80°, zasada
jest teraz twarda”); zapis daje już `algopalette.v2`. Autozapis w starym formacie jest migrowany przy
pierwszym starcie, a stary plik zostaje obok jako `last.v1.json`. Własne nastroje z `moods.json` stają się
jednorazowo własnymi presetami.

**Przeniesienie do PaletteBuildera** (`Ctrl+E`): paleta trafia do schowka w formacie, który PaletteBuilder
przyjmuje w oknie „Wczytaj…” (wklej tam). `Ctrl+Shift+E` zapisuje to samo do pliku (domyślnie
`~/Dokumenty/motifs/`).

## Czego nie robić

- Nie zapisuj palety z PaletteBuildera z powrotem do pliku sesji AlgoPalette — przepływ jest jednokierunkowy;
  AlgoPalette nie czyta plików PaletteBuildera.
- Progi odległości zależą od metody ΔE (0.08 w `ok` ≈ 12.5 w `2000`). Zmiana metody w ustawieniach całej palety
  przelicza progi przybliżonym przelicznikiem — sprawdź je potem, jeśli zależy Ci na dokładnych wartościach.
- Nie traktuj propozycji oznaczonej „✗ łamie twarde” ani „⏱ niepowtarzalna” jak gotowego wyniku.
- „Zastosuj” preset zastępuje zasady wszystkich kolorów, także te ustawione ręcznie (`Ctrl+Z` je przywraca).
  Jeśli chcesz zachować własne zasady, zapisz je najpierw jako własny preset.

## Rozwój

Do zbudowania potrzebny jest **Rust** (cargo i rustc, wydanie stabilne) oraz kompilator C; resztę (`maturin`,
PySide6) dociąga `uv`. Silnik leży w `crates/`: `core` (kolor, zasady, funkcja celu, optymalizator, sterownik
równoległy — czysty Rust), `py` (moduł `algopalette._engine`, PyO3) i `cli` (program `algopalette-bench`).

```sh
uv sync                    # buduje też silnik; powtórz po każdej zmianie kodu Rust
uv run pytest -q           # testy Pythona (GUI w trybie offscreen)
uv run pytest -q tests/test_presets_quality.py -m slow    # jakość presetów na silniku (wolne, w tle)
cargo test --workspace     # testy silnika
uv run ruff check && uv run ruff format --check && uv run ty check
cargo fmt --check && cargo clippy --all-targets -- -D warnings
```

Po zmianie kodu Rust zainstalowana komenda `algopalette` wymaga przebudowy:
`uv tool install --editable . --force`.

Projekt i decyzje: `docs/superpowers/specs/2026-11-15-zasady-silnik-design.md` (zasady i silnik) oraz
`docs/superpowers/specs/2026-11-14-algopalette-design.md` (pierwsza wersja); plany w `docs/superpowers/plans/`;
stan prac: `HANDOFF.md`.
