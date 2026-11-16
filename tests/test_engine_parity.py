"""Zgodność oceny zasad silnika natywnego ze starym silnikiem (Task 14, spec §9.5).

Dane wzorcowe: ``tests/fixtures/v1_reference/eval.json`` — 300 sesji v1 z listą naruszeń i wartością
funkcji celu policzonymi kodem z commita 4b71aeb. Ścieżka testu: sesja v1 → ``migrate_v1`` →
``engine.current_violations`` / ``engine.objective``.

Termy porównuje się w tolerancji względnej 1e-6 (1e-4 bezwzględnie dla ΔE ``2000``/``itp``/
``cam16``). Cztery rodzaje różnic nie są błędem portu i mają własne, wyprowadzone traktowanie:

1. **Gamut.** Wszystkie naruszenia ``slot:<id>:gamut`` we wzorcu to szum bisekcji starego
   ``max_chroma`` (wielkości < 1e-5; opis w ``v1_reference/README.md``). Nie są porównywane jako
   klucze: obie strony muszą mieć wielkość < 2e-5, a wkład tych termów jest odejmowany od funkcji
   celu po obu stronach.
2. **Nasycenie względne.** Stare ``max_chroma`` (``fast.max_chroma`` z domyślną tolerancją 1e-5 —
   ta funkcja nadal jest w drzewie) zaniża największe C nawet o 7,6e-6, więc C względne starego
   silnika jest zawyżone. Dla zakresów nasycenia względnego i zależności nasycenia względnego test
   odtwarza starą wartość dokładnie (``_old_amount``) i porównuje ją ze wzorcem w zwykłej
   tolerancji 1e-6. Dla termów odcienia, w których C względne wchodzi przez podłogę wygaszania,
   stosuje granicę błędu wyprowadzoną z kroku bisekcji (``_floor_slack``).
3. **Próg wykrywania.** Term o wielkości przy progu 1e-9 bywa naruszeniem tylko po jednej stronie;
   brak klucza jest błędem dopiero, gdy wielkość przekracza tolerancję termu.
4. **Nieciągłość CIEDE2000.** Wzór ma skok, gdy odcienie CIELAB pary różnią się o 180°. Kolory po
   symulacji dichromazji leżą na płaszczyźnie przez oś szarości, więc dla ciemnych par (liniowa
   gałąź CIELAB) różnica wynosi 180° co do zaokrągleń i o gałęzi decyduje szum 1e-13. Taki term
   (``_on_ciede_discontinuity``) nie jest porównywany, a jego wkład jest odejmowany od funkcji celu.
"""

import json
import math
from pathlib import Path
from typing import Any

import pytest

from algopalette import _engine, engine
from algopalette import color as slow
from algopalette import io as aio
from algopalette.color import fast
from algopalette.migrate import migrate_v1
from algopalette.model import OKLCH, Relation, Session

pytestmark = pytest.mark.skipif(
    "evaluate" not in _engine.build_info()["implemented"],
    reason="ocena zasad silnika jeszcze niezaimplementowana",
)

REFERENCE = Path(__file__).parent / "fixtures" / "v1_reference" / "eval.json"
CASES: list[dict[str, Any]] = json.loads(REFERENCE.read_text(encoding="utf-8"))

REL_TOL = 1e-6
ABS_FLOOR = 1e-9  # próg wykrywania naruszenia w obu silnikach
SLOW_DE_TOL = 1e-4  # ΔE 2000 / itp / cam16: bezwzględnie, skala ~0–100
GAMUT_NOISE = 2e-5
OLD_MAXC_STEP = 0.5 / 2**16  # dokładność bisekcji starego max_chroma (16 kroków na [0, 0.5])
SLOW_DE = ("2000", "itp", "cam16")
MAX_WEIGHT = 2.0  # największa waga zasady w danych wzorcowych (sprawdzana w teście)


class Case:
    """Jeden przypadek wzorcowy po migracji, z kolorami takimi, jakie dostaje silnik."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw
        self.session: Session = aio.session_from_dict(migrate_v1(raw["session"])[0])
        doc = json.loads(engine.to_engine_json(self.session, ()))
        self.ids = [s.id for s in self.session.slots]
        self.values = {s["id"]: s["value"] for s in doc["slots"]}
        ls = [v["l"] for v in self.values.values()]
        hs = [v["h"] for v in self.values.values()]
        cs = [v["c"] for v in self.values.values()]
        old = fast.max_chroma(ls, hs)  # tak liczył stary silnik (tolerancja 1e-5)
        new = fast.max_chroma(ls, hs, tol=1e-13)
        self.old_relc = {
            sid: (c / max(float(m), 1e-9) if m > 1e-9 else 0.0)
            for sid, c, m in zip(self.ids, cs, old, strict=True)
        }
        self.maxc = dict(zip(self.ids, (float(m) for m in new), strict=True))
        self.hard_weight = self.session.globals.optimizer.hard_weight
        self.want = {_new_key(v["key"]): v for v in raw["violations"]}
        self.got = {v.key: v for v in engine.current_violations(self.session)}

    def slot(self, sid: str) -> Any:
        return self.session.slots[self.ids.index(sid)]

    def has_relative_floor(self, sid: str) -> bool:
        """Twarde, włączone minimum nasycenia względnego > 0 (podłoga wygaszania odcienia)."""
        if sid not in self.ids:
            return False
        rule = self.slot(sid).rules.chroma
        return bool(
            rule is not None
            and rule.enabled
            and rule.hard
            and rule.value.mode == "rel"
            and (rule.value.lo or 0.0) > 0.0
        )

    def relation(self, key: str) -> Relation:
        parts = key.split(":")
        return self.slot(parts[1]).relations[int(parts[4])]


def _new_key(key: str) -> str:
    """Klucze v1 ``hue_range`` / ``hue_target`` to w v2 jedna zasada ``hue``."""
    for old in (":hue_range", ":hue_target"):
        if key.endswith(old):
            return key[: -len(old)] + ":hue"
    return key


def _is_gamut(key: str) -> bool:
    return key.endswith(":gamut")


def _interval(x: float, lo: float | None, hi: float | None) -> float:
    return (max(lo - x, 0.0) if lo is not None else 0.0) + (
        max(x - hi, 0.0) if hi is not None else 0.0
    )


def _op(d: float, op: str, value: float, tol: float) -> float:
    if op == "eq":
        return max(abs(d - value) - tol, 0.0)
    return max(value - d, 0.0) if op == "ge" else max(d - value, 0.0)


def _old_amount(case: Case, key: str) -> float | None:
    """Wielkość naruszenia termu liczonego wprost z C względnego — tak, jak liczył ją stary silnik
    (ze starym ``max_chroma``). ``None`` dla pozostałych termów."""
    parts = key.split(":")
    if parts[0] != "slot":
        return None
    if parts[2] == "chroma":
        rule = case.slot(parts[1]).rules.chroma
        if rule.value.mode != "rel":
            return None
        return _interval(case.old_relc[parts[1]], rule.value.lo, rule.value.hi)
    if parts[2] == "rel" and parts[3] == "chroma":
        rel = case.relation(key)
        if rel.chroma_mode != "rel":
            return None
        own, target = case.old_relc[parts[1]], case.old_relc[rel.target]
        if rel.chroma_op == "add":
            return _op(own - target, rel.op, rel.value, rel.tol)
        return _op(own - rel.value * target, rel.op, 0.0, rel.tol)
    return None


def _floor_slack(case: Case, key: str, amount: float) -> float:
    """Granica błędu termu odcienia, którego wygaszanie stoi na podłodze nasycenia względnego:
    waga = ``clip(max(C, lo · maxC) / 0.02, 0, 1)²``, a stare ``maxC`` było zaniżone o ≤ 7,6e-6."""
    parts = key.split(":")
    sids: list[str] = []
    if parts[0] == "slot" and parts[2] == "hue":
        sids = [parts[1]]
    elif parts[:2] == ["global", "scheme"]:
        sids = [parts[2]]
    elif parts[0] == "slot" and parts[2] == "rel" and parts[3] == "hue":
        sids = [parts[1], case.relation(key).target]
    slack = 0.0
    for sid in sids:
        if case.has_relative_floor(sid):
            # na podłodze waga ∝ maxC², więc d(wielkość) ≤ 2 · wielkość · d(maxC) / maxC
            # (+1 % zapasu na wyrazy wyższego rzędu)
            slack += 2.02 * amount * OLD_MAXC_STEP / max(case.maxc[sid], 1e-9)
    return slack


def _slow_de(case: Case, key: str) -> str | None:
    """Metoda ΔE termu, jeśli to ``2000`` / ``itp`` / ``cam16``."""
    g = case.session.globals
    parts = key.split(":")
    method: str | None = None
    if parts[0] == "pair":
        method = g.delta_e
    elif parts[0] == "slot" and parts[2] == "rel" and parts[3] == "distance":
        method = case.relation(key).metric or g.delta_e
    return method if method in SLOW_DE else None


def _on_ciede_discontinuity(case: Case, key: str) -> bool:
    """Para, której odcienie CIELAB różnią się o 180° co do zaokrągleń (skok wzoru CIEDE2000)."""
    if _slow_de(case, key) != "2000":
        return False
    parts = key.split(":")
    g = case.session.globals
    if parts[0] == "pair":
        a, b = parts[1], parts[2]
        cvd = parts[4] if parts[3] == "cvd" else None
    else:
        a, b, cvd = parts[1], case.relation(key).target, None
    labs = []
    for sid in (a, b):
        v = case.values[sid]
        color = OKLCH(v["l"], v["c"], v["h"])
        if cvd is not None:
            color = slow.simulate_cvd(color, cvd, g.cvd.method, g.cvd.severity)  # ty: ignore[invalid-argument-type]
        labs.append(slow.to_color(color).convert("lab-d65").coords(nans=False))
    hues = [math.degrees(math.atan2(lab[2], lab[1])) for lab in labs]
    diff = abs((hues[0] - hues[1] + 180.0) % 360.0 - 180.0)
    return abs(diff - 180.0) < 1e-6


def _scale(v: engine.Violation) -> float:
    """Skala termu (jak w silniku) — potrzebna do przeniesienia luzu wielkości na funkcję celu."""
    if v.kind in ("pair_distance", "pair_cvd"):
        return 0.01 if v.meta["method"] in ("ok", "hyab") else 1.0
    if v.kind == "chroma":
        return 0.02 if v.meta.get("mode") == "rel" else 0.01
    if v.kind == "rel":
        if v.meta["rel_kind"] == "distance":
            return 0.01 if v.meta["metric"] in ("ok", "hyab") else 1.0
        if v.meta["rel_kind"] == "chroma":
            return 0.02 if v.meta["chroma_mode"] == "rel" else 0.01
    return 1.0  # odcień, układ, zależność odcienia


def _compare(raw: dict[str, Any]) -> list[str]:
    """Lista rozbieżności jednego przypadku (pusta = zgodny)."""
    case = Case(raw)
    got, want = case.got, case.want
    problems: list[str] = []
    if len(want) != len(raw["violations"]):
        problems.append("powtórzone klucze naruszeń we wzorcu po odwzorowaniu")

    def coefficient(v: engine.Violation) -> float:
        return (case.hard_weight if v.hard else 1.0) * MAX_WEIGHT / _scale(v) ** 2

    objective_slack = 0.0
    for key in sorted(set(got) | set(want)):
        g_amount = got[key].amount if key in got else 0.0
        w_amount = want[key]["amount"] if key in want else 0.0
        if _is_gamut(key):
            if max(g_amount, w_amount) >= GAMUT_NOISE:
                problems.append(f"{key}: gamut {g_amount:.3e} / wzorzec {w_amount:.3e}")
            continue
        if _on_ciede_discontinuity(case, key):
            continue
        if key in got and key in want and got[key].hard != want[key]["hard"]:
            problems.append(f"{key}: twardość {got[key].hard} zamiast {want[key]['hard']}")

        tol = REL_TOL * abs(w_amount) + ABS_FLOOR
        if _slow_de(case, key):
            tol = max(tol, SLOW_DE_TOL)
        emulated = _old_amount(case, key)
        if emulated is not None:
            # wzorzec ma się zgadzać ze starą wartością odtworzoną z bieżących kolorów …
            if abs(emulated - w_amount) > tol:
                problems.append(
                    f"{key}: wzorzec {w_amount!r}, odtworzona stara wartość {emulated!r}"
                )
            # … a silnik różnić się od niej najwyżej o błąd starego max_chroma
            sids = [key.split(":")[1]]
            if key.split(":")[2] == "rel":
                sids.append(case.relation(key).target)
            tol += 4.0 * sum(OLD_MAXC_STEP / max(case.maxc[s], 1e-9) for s in sids)
        tol += _floor_slack(case, key, max(g_amount, w_amount))
        if abs(g_amount - w_amount) > tol:
            what = "wielkość" if key in got and key in want else "brak klucza po jednej stronie"
            problems.append(f"{key}: {what}: {g_amount!r} zamiast {w_amount!r} (tol {tol:.2e})")
        elif key in got and tol > REL_TOL * abs(w_amount) + ABS_FLOOR:
            # luz większy niż 1e-6 przenosi się na funkcję celu: d(w·(v/s)²) = 2w·v·dv/s²
            objective_slack += 2.0 * coefficient(got[key]) * (abs(w_amount) + tol) * tol

    def without(obj: float, amounts: list[float]) -> float:
        # termy gamutu: twarde, waga 1, skala 0.01
        return obj - sum(case.hard_weight * (a / 0.01) ** 2 for a in amounts)

    want_obj = without(raw["objective"], [v["amount"] for k, v in want.items() if _is_gamut(k)])
    got_obj = without(
        engine.objective(case.session), [v.amount for k, v in got.items() if _is_gamut(k)]
    )
    discontinuous = [k for k in set(got) | set(want) if _on_ciede_discontinuity(case, k)]
    if discontinuous:
        # wkładu termu na skoku CIEDE2000 nie da się odjąć bez wagi zasady — funkcję celu pomijamy
        return problems
    tol = REL_TOL * abs(want_obj) + ABS_FLOOR + objective_slack
    if abs(got_obj - want_obj) > tol:
        problems.append(f"funkcja celu {got_obj!r} zamiast {want_obj!r} (tol {tol:.3e})")
    return problems


def test_reference_has_300_cases_covering_every_term_kind() -> None:
    assert len(CASES) == 300
    kinds = set()
    for raw in CASES:
        for v in raw["violations"]:
            parts = v["key"].split(":")
            kinds.add(
                parts[3] if parts[0] == "pair" else parts[2] if parts[0] == "slot" else parts[1]
            )
    assert kinds >= {
        "lightness",
        "chroma",
        "hue_range",
        "hue_target",
        "contrast_bg",
        "extreme",
        "min_distance",
        "cvd",
        "rel",
        "lightness_spread",
        "scheme",
        "avoid",
    }


def test_reference_weights_stay_within_the_assumed_bound() -> None:
    def walk(node: Any) -> float:
        if isinstance(node, dict):
            own = node.get("weight")
            best = float(own) if isinstance(own, int | float) else 0.0
            return max([best, *(walk(v) for v in node.values())])
        if isinstance(node, list):
            return max([0.0, *(walk(v) for v in node)])
        return 0.0

    assert walk(CASES) <= MAX_WEIGHT


@pytest.mark.parametrize("index", range(len(CASES)))
def test_evaluation_matches_the_old_engine(index: int) -> None:
    problems = _compare(CASES[index])
    assert not problems, "\n".join(problems[:12])


def test_ciede_discontinuity_is_rare() -> None:
    """Term pominięty z powodu skoku CIEDE2000 to wyjątek, nie furtka: najwyżej kilka w całych
    danych (zmierzone: 4 termy, z czego 1 po innej stronie skoku niż wzorzec)."""
    hits = 0
    for raw in CASES:
        if raw["session"]["globals"]["delta_e"] != "2000":
            continue
        case = Case(raw)
        hits += sum(_on_ciede_discontinuity(case, k) for k in set(case.got) | set(case.want))
    assert 0 < hits <= 6


def test_migration_of_reference_sessions_is_silent() -> None:
    """Żadna sesja wzorcowa nie traci zasady przy migracji — inaczej porównanie nie ma sensu."""
    for raw in CASES:
        assert migrate_v1(raw["session"])[1] == []
