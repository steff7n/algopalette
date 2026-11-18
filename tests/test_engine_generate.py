"""Generowanie palet silnikiem natywnym przez nakładkę ``engine`` (Task 16, spec §9.4–§9.6).

Jakość jest sprawdzana na 36 sesjach wzorcowych starego silnika
(``tests/fixtures/v1_reference/quality.json``): nowy silnik przy budżecie domyślnym ma dać co
najmniej tyle propozycji bez twardych naruszeń i najlepszy wynik nie gorszy niż wzorzec × 1,05.
"""

import json
import statistics
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from algopalette import _engine, color, engine
from algopalette import io as aio
from algopalette.migrate import migrate_v1
from algopalette.model import (
    OKLCH,
    Band,
    OptimizerSettings,
    Rule,
    Session,
    default_session,
    with_slot,
)

pytestmark = pytest.mark.skipif(
    "generate" not in _engine.build_info()["implemented"],
    reason="silnik natywny jeszcze nie generuje",
)

FIXTURES = Path(__file__).parent / "fixtures"
QUALITY: list[dict[str, Any]] = json.loads(
    (FIXTURES / "v1_reference" / "quality.json").read_text(encoding="utf-8")
)


def _bench(name: str) -> Session:
    data = json.loads((FIXTURES / "bench" / f"{name}.json").read_text(encoding="utf-8"))
    return aio.session_from_dict(data)


def _with_optimizer(session: Session, **changes: Any) -> Session:
    opt: OptimizerSettings = replace(session.globals.optimizer, **changes)
    return replace(session, globals=replace(session.globals, optimizer=opt))


def _lock(session: Session, index: int) -> Session:
    return with_slot(session, replace(session.slots[index], locked=True))


# ---------------------------------------------------------------------------
# Sesja startowa
# ---------------------------------------------------------------------------


def test_default_session_gives_six_ok_proposals_in_gamut() -> None:
    s = default_session()
    proposals = engine.generate(s)
    assert len(proposals) == 6
    ids = tuple(slot.id for slot in s.slots)
    for p in proposals:
        assert p.ok, [v.key for v in p.violations if v.hard]
        assert not p.timed_out and p.seed == s.globals.optimizer.seed
        assert p.slot_ids == ids
        assert set(p.values) == set(ids) and set(p.hexes) == set(ids)
        for sid in ids:
            assert color.in_gamut(p.values[sid]), (sid, p.values[sid])
            assert p.fit_deltas[sid] == 0.0
    # kolejność: rosnąco wg wyniku
    scores = [p.score for p in proposals]
    assert scores == sorted(scores)
    # propozycje różnią się od siebie
    assert len({tuple(p.hexes.values()) for p in proposals}) == 6


def test_score_and_violations_agree_with_live_evaluation() -> None:
    """Wynik propozycji to funkcja celu palety po jej przejęciu (bez kary za różnorodność)."""
    s = _bench("w2")
    s = _with_optimizer(s, n_proposals=4)
    for p in engine.generate(s):
        applied = engine.apply_proposal(s, p)
        assert engine.objective(applied) == pytest.approx(p.score, rel=1e-9, abs=1e-12)
        live = {v.key: v.amount for v in engine.current_violations(applied)}
        mine = {v.key: v.amount for v in p.violations if v.kind != "diversity"}
        assert live.keys() == mine.keys()
        for key, amount in mine.items():
            assert live[key] == pytest.approx(amount, rel=1e-9, abs=1e-12)


def test_locked_and_unselected_colors_stay_unchanged() -> None:
    s = _lock(_lock(default_session(), 3), 6)
    chosen = [s.slots[i].id for i in (2, 3, 4, 5)]  # w tym kolor z kłódką (3)
    proposals = engine.generate(s, slot_ids=chosen)
    free = tuple(s.slots[i].id for i in (2, 4, 5))
    assert len(proposals) == 6
    for p in proposals:
        assert p.slot_ids == free
        for slot in s.slots:
            if slot.id not in free:
                assert p.values[slot.id] == slot.value, slot.id
        assert any(
            p.values[sid] != s.slots[i].value for sid, i in zip(free, (2, 4, 5), strict=True)
        )


def test_session_without_free_colors_gives_one_unchanged_proposal() -> None:
    s = default_session()
    for i in range(len(s.slots)):
        s = _lock(s, i)
    proposals = engine.generate(s)
    assert len(proposals) == 1
    assert proposals[0].slot_ids == ()
    assert all(proposals[0].values[slot.id] == slot.value for slot in s.slots)


# ---------------------------------------------------------------------------
# Determinizm
# ---------------------------------------------------------------------------


def _signature(proposals: list[engine.Proposal]) -> list[tuple[Any, ...]]:
    return [
        (p.score, tuple((sid, v.l, v.c, v.h) for sid, v in sorted(p.values.items())))
        for p in proposals
    ]


@pytest.mark.parametrize("name", ["w1", "w2"])
def test_result_does_not_depend_on_thread_count(name: str) -> None:
    s = _with_optimizer(_bench(name), n_proposals=8)
    reference = _signature(engine.generate(_with_optimizer(s, threads=1)))
    assert len(reference) == 8
    assert _signature(engine.generate(_with_optimizer(s, threads=0))) == reference
    assert _signature(engine.generate(_with_optimizer(s, threads=3))) == reference
    assert _signature(engine.generate(_with_optimizer(s, threads=1))) == reference
    # inne ziarno daje inne palety
    assert _signature(engine.generate(_with_optimizer(s, seed=1))) != reference


# ---------------------------------------------------------------------------
# Jakość wobec starego silnika
# ---------------------------------------------------------------------------


def _quality_id(case: dict[str, Any]) -> str:
    return f"{case['mood']}/{case['polarity']}/{case['metric']}"


@pytest.mark.parametrize("case", QUALITY, ids=_quality_id)
def test_quality_is_not_worse_than_the_old_engine(case: dict[str, Any]) -> None:
    data, notes = migrate_v1(case["session"])
    assert notes == []
    session = aio.session_from_dict(data)
    assert session.globals.optimizer.budget == default_session().globals.optimizer.budget
    proposals = engine.generate(session)
    assert len(proposals) == 6
    ok = [p for p in proposals if p.ok]
    assert len(ok) >= case["ok_count"], f"bez twardych naruszeń: {len(ok)} < {case['ok_count']}"
    best = min(p.score for p in (ok or proposals))
    assert best <= case["best_score"] * 1.05 + 1e-9, f"{best} > {case['best_score']} × 1,05"


def test_reference_has_36_quality_cases() -> None:
    assert len(QUALITY) == 36
    assert len({_quality_id(c) for c in QUALITY}) == 36


# ---------------------------------------------------------------------------
# Różnorodność, limit czasu, przerwanie, zasada niespełnialna
# ---------------------------------------------------------------------------


def _narrow_session() -> Session:
    """Trzy kolory, każdy z twardym, bardzo wąskim zakresem: sześć różnych palet nie istnieje."""
    s = default_session()
    while len(s.slots) > 3:
        s = replace(s, slots=s.slots[:-1])
    slots = []
    for slot in s.slots:
        v = slot.value
        rules = replace(
            slot.rules,
            lightness=Rule(Band(v.l - 0.002, v.l + 0.002)),
            contrast_bg=None,
            min_distance=None,
        )
        slots.append(replace(slot, rules=rules, use_scheme=False))
    locked_bg = replace(slots[0], locked=True)
    return replace(s, slots=(locked_bg, slots[1], slots[2]))


def test_too_similar_proposals_get_a_soft_diversity_violation() -> None:
    s = _narrow_session()
    s = _with_optimizer(s, min_diversity=0.2)
    proposals = engine.generate(s)
    assert len(proposals) == 6
    tagged = [p for p in proposals if any(v.kind == "diversity" for v in p.violations)]
    assert 1 <= len(tagged) <= 5
    assert not any(v.kind == "diversity" for v in proposals[0].violations)
    for p in tagged:
        v = next(v for v in p.violations if v.kind == "diversity")
        assert not v.hard and v.key == "global:diversity"
        assert v.slot_ids == p.slot_ids
        assert v.req == {"min": 0.2}
        assert 0.0 <= v.achieved < 0.2
        assert v.amount == pytest.approx(0.2 - v.achieved)
        assert p.ok, "naruszenie różnorodności jest miękkie"


def test_time_cap_marks_every_proposal_timed_out() -> None:
    s = _with_optimizer(_bench("w3"), n_proposals=128, budget=100_000, time_cap_s=0.15, threads=2)
    started = time.perf_counter()
    proposals = engine.generate(s)
    elapsed = time.perf_counter() - started
    assert elapsed < 1.0, f"limit czasu nie zadziałał: {elapsed:.2f} s"
    assert len(proposals) < 128
    assert all(p.timed_out and not p.ok for p in proposals)


def test_cancel_ends_the_job_within_100_ms() -> None:
    s = _with_optimizer(_bench("w3"), n_proposals=128, budget=100_000, threads=2)
    generation = engine.start(s)
    time.sleep(0.15)
    assert generation.poll().state == "running"
    with pytest.raises(RuntimeError):
        generation.result()
    cancelled_at = time.perf_counter()
    generation.cancel()
    while generation.poll().state == "running":
        assert time.perf_counter() - cancelled_at < 2.0, "zadanie nie reaguje na przerwanie"
        time.sleep(0.002)
    lag = time.perf_counter() - cancelled_at
    assert lag <= 0.1, f"przerwanie po {lag * 1000:.0f} ms"
    state = generation.poll()
    assert state.state == "cancelled" and state.error is None
    assert 0.0 <= state.fraction < 1.0
    # wynik to propozycje z przebiegów ukończonych przed przerwaniem
    proposals = generation.result()
    assert len(proposals) <= state.candidates


def test_blocking_generate_reports_progress_and_honours_cancel_callback() -> None:
    seen: list[float] = []
    proposals = engine.generate(_bench("w2"), progress=seen.append)
    assert len(proposals) == 128
    assert seen == sorted(seen) and seen[-1] == 1.0 and all(0.0 <= f <= 1.0 for f in seen)

    heavy = _with_optimizer(_bench("w3"), budget=100_000, threads=2)
    started = time.perf_counter()
    engine.generate(heavy, cancel=lambda: time.perf_counter() - started > 0.1)
    assert time.perf_counter() - started < 1.0


def test_unsatisfiable_rule_gives_six_proposals_marked_bad() -> None:
    """Zakazy pokrywające cały dozwolony zakres jasności akcentu (Review Focus 1)."""
    s = default_session()
    target = s.slots[4]
    rules = replace(target.rules, lightness=Rule(Band(0.6, 0.8, exclude=((0.5, 0.9),))))
    s = with_slot(s, replace(target, rules=rules))
    started = time.perf_counter()
    proposals = engine.generate(s)
    assert time.perf_counter() - started < 10.0
    assert len(proposals) == 6
    key = f"slot:{target.id}:lightness:exclude:0"
    for p in proposals:
        assert not p.ok and not p.timed_out
        v = next(v for v in p.violations if v.key == key)
        assert v.hard and v.kind == "exclude" and v.amount > 0.0
        assert all(color.in_gamut(c) for c in p.values.values())
    # ocena na żywo pokazuje to samo naruszenie
    assert any(v.key == key and v.hard for v in engine.current_violations(s))


def test_excluded_intervals_are_respected_by_generated_palettes() -> None:
    s = default_session()
    for index in (2, 5):
        slot = s.slots[index]
        rules = replace(slot.rules, lightness=Rule(Band(0.60, 0.85, exclude=((0.64, 0.80),))))
        s = with_slot(s, replace(slot, rules=rules))
    proposals = engine.generate(s)
    assert all(p.ok for p in proposals)
    lightness = [p.values[s.slots[i].id].l for p in proposals for i in (2, 5)]
    assert all(not 0.64 < value < 0.80 for value in lightness)
    assert any(v <= 0.64 for v in lightness) and any(v >= 0.80 for v in lightness)


# ---------------------------------------------------------------------------
# Dokument dla silnika
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["w1", "w2", "w3"])
def test_engine_document_equals_the_plain_encoding(name: str) -> None:
    """``to_engine_json`` składa dokument z zapamiętanych fragmentów — ma to być dokładnie
    ``io.session_to_dict`` sesji z kolorami stałymi po dopasowaniu do gamutu."""
    s = _bench(name)
    # jeden kolor spoza gamutu, żeby dopasowanie miało co robić
    wild = replace(s.slots[3], value=OKLCH(0.7, 0.35, 140.0))
    s = with_slot(s, wild)
    fit = s.globals.fit_method
    for free in [(), (wild.id,), tuple(slot.id for slot in s.slots)]:
        fixed = tuple(
            slot if slot.id in free else replace(slot, value=color.fitted(slot.value, fit))
            for slot in s.slots
        )
        plain = aio.session_to_dict(replace(s, slots=fixed))
        assert json.loads(engine.to_engine_json(s, free)) == plain
        # drugi raz (z pamięci podręcznej) — to samo
        assert json.loads(engine.to_engine_json(s, free)) == plain
    # zmiana metody dopasowania i zasad zmienia dokument (pamięć podręczna nie myli sesji)
    other = replace(s, globals=replace(s.globals, fit_method="clip", delta_e="hyab"))
    doc = json.loads(engine.to_engine_json(other, ()))
    assert doc == aio.session_to_dict(
        replace(
            other,
            slots=tuple(replace(x, value=color.fitted(x.value, "clip")) for x in other.slots),
        )
    )
    assert doc["globals"]["delta_e"] == "hyab" and doc["slots"][3]["hex"] != ""


def test_live_evaluation_follows_edits() -> None:
    """Ocena po każdej zmianie koloru widzi nową wartość (a nie zapamiętany dokument)."""
    s = _bench("w1")
    slot = s.slots[2]
    seen = set()
    for lightness in (0.2, 0.7, 0.95):
        edited = with_slot(s, replace(slot, value=replace(slot.value, l=lightness)))
        amounts = {
            v.key: v.amount
            for v in engine.current_violations(edited)
            if v.key == f"slot:{slot.id}:lightness"
        }
        seen.add(tuple(amounts.items()))
    assert len(seen) == 3


# ---------------------------------------------------------------------------
# Sesje benchmarkowe i wydajność
# ---------------------------------------------------------------------------


def test_bench_sessions_match_their_description() -> None:
    w1, w2, w3 = _bench("w1"), _bench("w2"), _bench("w3")
    default_budget = default_session().globals.optimizer.budget
    for s in (w1, w2, w3):
        assert s.globals.optimizer.budget == default_budget
        _engine.validate(engine.to_engine_json(s, ()))
    assert len(w1.slots) == 10 and w1.globals.optimizer.n_proposals == 6
    assert w1.preset == "neutralny"
    assert len(w2.slots) == 10 and w2.globals.optimizer.n_proposals == 128
    assert w2.preset == "chłodny mglisty"
    assert len(w3.slots) == 16 and w3.globals.optimizer.n_proposals == 128
    assert w3.globals.delta_e == "2000"
    assert all(slot.rules.min_distance is not None for slot in w3.slots[2:])


@pytest.mark.slow
def test_128_palettes_for_cool_misty_take_at_most_6_s() -> None:
    """W2 z luźnym progiem (cel: ≤ 2 s; dokładne liczby w HANDOFF §0d)."""
    s = _bench("w2")
    started = time.perf_counter()
    proposals = engine.generate(s)
    elapsed = time.perf_counter() - started
    assert len(proposals) == 128
    assert sum(p.ok for p in proposals) >= 120
    assert elapsed <= 6.0, f"{elapsed:.2f} s"


def _editing(session: Session, rounds: int) -> list[Session]:
    """Kolejne stany palety przy edycji: w każdym kroku zmienia się jeden kolor."""
    out = []
    for n in range(rounds):
        slot = session.slots[2 + n % (len(session.slots) - 2)]
        value = replace(slot.value, h=(slot.value.h + 0.37 * (n + 1)) % 360.0)
        session = with_slot(session, replace(slot, value=value))
        out.append(session)
    return out


@pytest.mark.slow
def test_live_evaluation_of_16_colors_is_fast() -> None:
    """W4 z luźnym progiem (cel: ≤ 1 ms; dokładne liczby w HANDOFF §0d). Każdy pomiar to ocena
    palety, w której od poprzedniej oceny zmienił się jeden kolor — jak przy edycji."""
    states = _editing(_bench("w3"), 300)
    assert len(engine.current_violations(states[0])) >= 20
    times = []
    for state in states:
        started = time.perf_counter()
        engine.current_violations(state)
        times.append(time.perf_counter() - started)
    assert statistics.median(times) <= 0.003, f"{statistics.median(times) * 1000:.2f} ms"
