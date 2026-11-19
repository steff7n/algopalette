# Import motywu z sieci → warianty podobne do motywu (design, krótki)

## Intencja (słowa użytkownika)
„podczas importu motywu z sieci generowane motywy [mają być] podobne do zaimportowanego motywu. […] zaimportowany
motyw ma 'ustawiać aplikację pod siebie', i generować motywy różne o np. 10 stopni w każdą stronę. Obecnie jest
z tym syf.” Swoboda: „pewnie że chcę ustawiać, ale domyślnie 10 stopni”.

## Diagnoza (odtworzona 2026-11-19, motyw typu Dracula, 4 propozycje)
Import (`themes/apply.py`, tryb domyślny) używa `sources.character_settings`:
1. układ odcieni „custom” = skupiska odcieni posortowane wg wagi, nie w kolejności akcentów → akcent k dostaje
   cudzy odcień (odchyłki 110–157° od własnego koloru motywu);
2. wspólne widełki jasności/nasycenia (p10–p90 wszystkich akcentów) → jasny żółty schodzi do L 0,81 itd.;
3. tekst bez zasady odcienia (−91°, 171°).

## Cele / nie-cele / anty-cele
- Cel: po imporcie (tryb domyślny, „Nie zmieniaj ustawień palety” odznaczone) każdy kolor — tło, tekst, każdy
  akcent — dostaje WŁASNE zasady wokół swojej wartości z motywu; generowanie daje warianty różniące się
  odcieniem o ≤ swoboda (domyślnie 10°), z jasnością i nasyceniem bliskimi oryginałowi.
- Cel: swoboda ustawiana w oknie „Motywy z sieci”, zapamiętywana jak checkbox.
- Nie-cel: zmiana trybu „Nie zmieniaj ustawień palety” (zostaje jak jest), zmiana `apply_character` /
  `apply_transfer` z „Palety wyjściowej” (tamte tryby bez zmian).
- Anty-cel: zasady, których motyw sam nie spełnia (propozycja = oryginał musi przechodzić bez twardych naruszeń);
  ruszanie kolorów z kłódką zasad (`rules_lock != "off"`) — decyzja wiążąca ze specu motywów.

## Podejścia
- **A (wybrane):** zasady per kolor wokół wartości z motywu, układ odcieni „brak”. Jawne i edytowalne
  w „Zasadach”, każdy kolor zostaje „sobą”.
- B: tylko poprawić kolejność listy odcieni (tol 10°). Odrzucone — wspólne widełki L/C zostają, żółty dalej
  może ściemnieć.

## Projekt
- `apply_theme(session, palette, *, keep_settings, spread_deg=10.0)`. Dla `keep_settings=False`, dla każdego
  slotu bez kłódki zasad, `x` = wartość z motywu, `k = spread_deg / 10`:
  - odcień: `HueArc` ±`spread_deg` wokół `x.h`, twardy; pominięty, gdy `x.c < 0.02` (szarość — odcień bez
    znaczenia; tło: próg jak `_bg_hue` 0.01 akceptowalny, decyzja buildera);
  - jasność: `Band(x.l ± 0.05·k)` przycięte do [0, 1];
  - nasycenie: akcenty `ChromaBand("rel", rel ± 0.08·k)`; tło/tekst `ChromaBand("abs", x.c ± 0.01·k)` (≥ 0);
  - kontrast z tłem (tekst, akcenty): dolna granica = kontrast oryginału z tłem motywu − tolerancja
    (`TRANSFER_TOL` · k, nie mniej niż minimum metryki), bez górnej; liczone w metryce sesji;
  - `min_distance` akcentów: miękki, nie większy niż najmniejsza ΔE między akcentami motywu (motyw nie może
    sam łamać zasady); `extreme` = brak;
  - `use_scheme=False`; globalnie `hue_scheme=HueScheme("none")`, `lightness_spread=None`, polaryzacja z tła
    (L < 0,5 → dark), `preset=None`; `avoid_*`, metryki, `fit_method`, optymalizator bez zmian;
  - `spread_deg = 0` dozwolone (zasady = punkt; propozycje ≈ motyw).
- Sloty z kłódką zasad: jak dziś (wartość z motywu, zasady nietknięte).
- GUI (`gui/themes_dialog.py`): obok checkboxa pole liczbowe/suwak „Swoboda wariantów: N°”, zakres 0–45,
  krok 1, domyślnie 10, zapamiętane w `gui.json` (`themes_spread_deg`), wyszarzone przy zaznaczonym
  „Nie zmieniaj ustawień palety”; `import_theme(…, spread_deg=…)`.
- Pomoc: nowy temat `themes.spread` + aktualizacja opisu trybu domyślnego w `help_content/themes_web.py`;
  README (sekcja „Motywy z sieci”).

## Akceptacja
- Motyw testowy (Dracula, 7 akcentów) po imporcie: oryginał sam nie ma twardych naruszeń; propozycje
  `engine.generate` — każdy kolor z odcieniem w ±swoboda od swojego koloru motywu (gdy C ≥ 0.02), |ΔL| ≤ 0,05·k.
- Swoboda 20° → łuki ±20°; checkbox zaznaczony → zachowanie bez zmian (istniejące testy).
- Kłódka zasad → zasady slotu bez zmian (istniejące testy).
- Ustawienie swobody przeżywa ponowne otwarcie okna.

## Dla buildera
Dokładne stałe tolerancji L/C/kontrastu, kształt kontrolki (QSpinBox vs suwak + etykieta), teksty pomocy.
