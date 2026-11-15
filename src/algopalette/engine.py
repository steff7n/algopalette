"""Cienka nakładka na silnik natywny (``algopalette._engine``, Rust).

Python koduje sesję do JSON-a w formacie ``algopalette.v2`` (ten sam dokument co plik sesji), silnik
ją parsuje, ocenia zasady albo generuje palety i zwraca liczby. Teksty dla człowieka składa
``forms.violation_text``; hexy i dopasowanie do gamutu liczy ``algopalette.color``.

Kolory stałe (z kłódką albo spoza generowanego zbioru) trafiają do silnika już po dopasowaniu do
gamutu — silnik bierze je, jak są. Kolory wolne silnik zwraca w gamucie sRGB.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, replace
from typing import Any

from algopalette import _engine  # ty: ignore[unresolved-import]
from algopalette import color as col
from algopalette import io as aio
from algopalette.model import OKLCH, Session, role_of

POLL_INTERVAL_S = 0.005  # odstęp odpytywania zadania w blokującym ``generate``


class EngineError(RuntimeError):
    """Silnik natywny zakończył zadanie błędem (komunikat z silnika)."""


@dataclass(frozen=True)
class Violation:
    """Naruszona zasada. ``kind``, ``req`` i ``meta`` według tabeli I3 planu; liczby bez tekstów."""

    key: str
    slot_ids: tuple[str, ...]
    kind: str
    hard: bool
    amount: float
    achieved: float
    req: Mapping[str, Any]
    meta: Mapping[str, Any]


@dataclass(frozen=True)
class Proposal:
    values: Mapping[str, OKLCH]
    hexes: Mapping[str, str]
    fit_deltas: Mapping[str, float]
    score: float
    violations: tuple[Violation, ...]
    timed_out: bool
    seed: int
    slot_ids: tuple[str, ...] = ()  # kolory, które ta propozycja zmieniała (wolne)

    @property
    def ok(self) -> bool:
        """Brak twardych naruszeń i wynik powtarzalny (bez przerwania limitem czasu)."""
        return not self.timed_out and not any(v.hard for v in self.violations)


@dataclass(frozen=True)
class Progress:
    state: str  # "running" | "done" | "cancelled" | "failed"
    fraction: float
    candidates: int
    error: str | None


def slot_label(session: Session, index: int) -> str:
    """Nazwa koloru do komunikatów: własna, a gdy jej nie ma — „tło”, „tekst”, „akcent N”."""
    slot = session.slots[index]
    if slot.name:
        return slot.name
    role = role_of(index)
    return {"bg": "tło", "fg": "tekst"}.get(role, f"akcent {index - 1}")


def _violation(v: Mapping[str, Any]) -> Violation:
    return Violation(
        key=v["key"],
        slot_ids=tuple(v["slots"]),
        kind=v["kind"],
        hard=bool(v["hard"]),
        amount=float(v["amount"]),
        achieved=float(v["achieved"]),
        req=dict(v["req"]),
        meta=dict(v["meta"]),
    )


def _free_ids(session: Session, slot_ids: Collection[str] | None) -> tuple[str, ...]:
    """Kolory wolne: bez kłódki i (gdy podano ``slot_ids``) należące do tego zbioru."""
    return tuple(
        s.id for s in session.slots if not s.locked and (slot_ids is None or s.id in slot_ids)
    )


def to_engine_json(session: Session, free: Collection[str]) -> str:
    """Sesja jako dokument ``algopalette.v2``; kolory spoza ``free`` po dopasowaniu do gamutu."""
    fit = session.globals.fit_method
    slots = tuple(
        s if s.id in free else replace(s, value=col.fitted(s.value, fit)) for s in session.slots
    )
    doc = aio.session_to_dict(replace(session, slots=slots))
    return json.dumps(doc, ensure_ascii=False, allow_nan=False)


class Generation:
    """Uchwyt trwającego generowania. Zadanie liczy się na wątkach silnika (bez GIL);
    interfejs odpytuje je zegarem przez ``poll()``."""

    def __init__(self, session: Session, free: tuple[str, ...]) -> None:
        self._session = session
        self._free = free
        self._job = _engine.start(to_engine_json(session, free), list(free))

    def poll(self) -> Progress:
        p = self._job.poll()
        return Progress(p["state"], float(p["progress"]), int(p["candidates"]), p["error"])

    def cancel(self) -> None:
        self._job.cancel()

    def result(self) -> list[Proposal]:
        """Propozycje zakończonego zadania (po przerwaniu: te z ukończonych przebiegów).

        Błąd silnika → ``EngineError``; zadanie w toku → ``RuntimeError``.
        """
        state = self.poll()
        if state.state == "failed":
            raise EngineError(state.error or "Silnik zakończył zadanie błędem.")
        if state.state == "running":
            raise RuntimeError("Generowanie jeszcze trwa.")
        res = self._job.result()
        return [self._proposal(p, bool(res["timed_out"])) for p in res["proposals"]]

    def _proposal(self, p: Mapping[str, Any], timed_out: bool) -> Proposal:
        s = self._session
        fit = s.globals.fit_method
        values: dict[str, OKLCH] = {}
        for slot in s.slots:
            raw = p["values"].get(slot.id) if slot.id in self._free else None
            if raw is None:  # stałe dokładnie jak na wejściu (bez szumu przeliczeń)
                values[slot.id] = slot.value
            else:
                values[slot.id] = OKLCH(float(raw[0]), float(raw[1]), float(raw[2]) % 360.0)
        return Proposal(
            values=values,
            hexes={sid: col.to_hex(v, fit) for sid, v in values.items()},
            fit_deltas={sid: col.fit_delta(v, fit) for sid, v in values.items()},
            score=float(p["score"]),
            violations=tuple(_violation(v) for v in p["violations"]),
            timed_out=timed_out,
            seed=s.globals.optimizer.seed,
            slot_ids=self._free,
        )


def start(session: Session, slot_ids: Collection[str] | None = None) -> Generation:
    """Uruchamia generowanie dla kolorów wolnych (bez kłódki; ewentualnie tylko ``slot_ids``)."""
    return Generation(session, _free_ids(session, slot_ids))


def generate(
    session: Session,
    *,
    slot_ids: Collection[str] | None = None,
    progress: Callable[[float], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> list[Proposal]:
    """Blokujące generowanie — dla testów i narzędzi; interfejs używa ``start`` i ``poll``."""
    gen = start(session, slot_ids)
    cancelled = False
    while True:
        state = gen.poll()
        if progress is not None:
            progress(state.fraction)
        if state.state != "running":
            break
        if not cancelled and cancel is not None and cancel():
            gen.cancel()
            cancelled = True
        time.sleep(POLL_INTERVAL_S)
    return gen.result()


def _evaluate(session: Session) -> Mapping[str, Any]:
    return _engine.evaluate(to_engine_json(session, ()))


def current_violations(session: Session) -> list[Violation]:
    """Naruszenia bieżącej palety — na kolorach po dopasowaniu (takich, jakie trafią do hexa)."""
    return [_violation(v) for v in _evaluate(session)["violations"]]


def objective(session: Session) -> float:
    """Wartość funkcji celu bieżącej palety (bez marginesu twardych)."""
    return float(_evaluate(session)["objective"])


def hue_targets(session: Session) -> dict[str, float]:
    """Cele odcieni akcentów z układu odcieni (``id`` → stopnie), dla wszystkich akcentów."""
    return {str(k): float(v) for k, v in _engine.hue_targets(to_engine_json(session, ())).items()}


def apply_proposal(
    session: Session, proposal: Proposal, slot_ids: Collection[str] | None = None
) -> Session:
    """Przejmuje wartości propozycji (wszystkich kolorów albo wskazanych). Pomija kolory z kłódką
    i takie, których propozycja nie zna (paleta mogła się zmienić od czasu generowania)."""
    slots = tuple(
        replace(s, value=proposal.values[s.id])
        if (not s.locked and s.id in proposal.values and (slot_ids is None or s.id in slot_ids))
        else s
        for s in session.slots
    )
    return replace(session, slots=slots)
