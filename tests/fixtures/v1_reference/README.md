# Dane wzorcowe ze starego silnika (v1)

Wygenerowane `tools/make_v1_reference.py` na kodzie z commita **4b71aeb** (silnik w Pythonie:
`constraints.py`, `engine.py`, `hues.py`, `moods.py`; numpy + scipy L-BFGS-B). Tego kodu już nie ma w
drzewie — **tych plików nie wolno odtwarzać nowym kodem**. Są jedynym zapisem zachowania starego
silnika; nowy silnik (Rust) jest na nich sprawdzany. `--check` generatora działa bez starego kodu
(liczy przypadki i pokrycie kluczy), tryb zapisu wymaga `git checkout 4b71aeb`.

## `eval.json` — zgodność oceny zasad (300 przypadków)

Jeden przypadek na wiersz: `{"session": <sesja algopalette.v1>, "objective": float, "violations":
[{"key", "hard", "amount"}]}`. Generator `random.Random(20261115)`, deterministyczny (dwa
uruchomienia = ten sam plik).

- `violations` = `forms.current_violations(session)`; `objective` = `constraints.objective` z
  `hard_weight` sesji. Oba liczone na kolorach **po** `color.fitted(wartość, fit_method)` (w pliku
  sesji są wartości sprzed dopasowania, 10% poza gamutem), bez marginesu twardych.
- Żaden kolor nie ma w warunkach obowiązujących (własne albo roli) naraz `hue_range` i
  `hue_target` (także wyłączonych) — migracja v1 → v2 tych sesji nie może zgłosić żadnego
  komunikatu. `hue_scheme.jitter == 0` wszędzie.
- 5% zależności ma nieistniejący cel (zerwane — stary silnik je pomija).
- **Termy `gamut` to szum bisekcji**: wszystkie 37 naruszeń `slot:<id>:gamut` ma wielkość
  < 1e-5 (stare `max_chroma` ma tolerancję 1e-5, a kolor po dopasowaniu leży na granicy gamutu).
  Nie porównuj ich względnie ani jako zbioru kluczy — dokładniejsze `max_chroma` da inne wartości.

## `quality.json` — jakość generowania (36 przypadków)

9 nastrojów × 2 polaryzacje × 2 metryki kontrastu: `{"mood", "polarity", "metric", "session":
<sesja v1 z nałożonym nastrojem>, "ok_count", "best_score", "scores"}`. 10 kolorów, 6 propozycji,
`max_evals = 30000`, `seed = 1`. `ok_count` = propozycje bez twardych naruszeń; `best_score` =
najmniejszy wynik wśród nich (gdy żadnej: wśród wszystkich); `scores` w kolejności propozycji.
Wynik (`score`) = `constraints.objective` na kolorach po dopasowaniu do gamutu, bez marginesu i
bez kary za różnorodność.
Pola `polarity`/`metric` to ustawienia sprzed nałożenia nastroju; obowiązuje to, co w `session`.
Generowanie szło z wyłączonym w praktyce limitem czasu (3600 s), w sesji zostaje domyślne 30 s.
