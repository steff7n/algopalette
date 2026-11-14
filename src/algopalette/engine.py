"""Silnik optymalizacji palety (podejście B, spec §7).

Zmienne wolnego slotu: ``(L, u, H)``, gdzie ``C = u · maxC(L, H)`` — kolor z definicji leży w sRGB,
a warunki nasycenia względnego stają się zwykłymi zakresami ``u``. Twarde zakresy L, nasycenia
względnego i odcienia przechodzą w granice zmiennych; reszta to kara z ``constraints``.

Algorytm jednej propozycji: losowanie wsadowe w granicach (seed) → najlepsze, różne starty →
L-BFGS-B z gradientem różnic skończonych liczonym jednym wywołaniem wsadowym → (dla ΔE spoza numpy)
kalibracja przybliżenia i krótkie dopracowanie. Budżet = ``max_evals`` ewaluacji kandydatów na
propozycję (deterministycznie); ``time_cap_s`` to tylko bezpiecznik (``timed_out``).
"""

import time
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, replace
from typing import cast

import numpy as np
from scipy.optimize import minimize

from algopalette import color as col
from algopalette import hues
from algopalette.color import fast
from algopalette.constraints import (
    VECTOR_DE,
    Ctx,
    Term,
    Violation,
    compile_terms,
    evaluate,
    objective,
    objective_batch,
)
from algopalette.model import OKLCH, DeltaEMethod, Session, effective_conditions

Array = np.ndarray
MARGIN_FRAC = 0.5  # zaostrzenie twardych warunków przy optymalizacji (× skala termu)
DIVERSITY_SCALE = 0.01
N_STARTS = 4
STALL_FRAC = 0.05
FTOL = 1e-6  # względna tolerancja L-BFGS-B
SOLVED = 1e-12  # funkcja celu ≈ 0: kolejne starty niczego nie poprawią
REFINE_ROUNDS = 2  # rundy kalibracji przybliżenia ΔE 2000/itp/cam16


@dataclass(frozen=True)
class Proposal:
    values: Mapping[str, OKLCH]
    hexes: Mapping[str, str]
    fit_deltas: Mapping[str, float]
    score: float
    violations: tuple[Violation, ...]
    timed_out: bool
    seed: int
    slot_ids: tuple[str, ...] = ()  # sloty, które ta propozycja zmieniała (wolne)

    @property
    def ok(self) -> bool:
        """Brak twardych naruszeń i wynik powtarzalny (bez przerwania limitem czasu)."""
        return not self.timed_out and not any(v.hard for v in self.violations)


class _Stop(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def hue_targets_for(session: Session) -> Mapping[str, float] | None:
    """Cele odcieni akcentów z układu odcieni sesji (``hues``)."""
    return hues.targets_for_session(session)


# ---------------------------------------------------------------------------
# Przestrzeń zmiennych
# ---------------------------------------------------------------------------


@dataclass
class _Space:
    ids: list[str]
    base: Array  # (n, 3) wartości startowe wszystkich slotów
    free: list[int]  # indeksy slotów wolnych
    lo: Array  # (D,)
    hi: Array  # (D,)
    hue_bounded: Array  # (F,) bool — odcień z twardym zakresem (granice), inaczej zawijany
    base_maxc: Array  # (n,) maxC wartości startowych
    sample_lo: Array  # (D,) zakres losowania startów (odcień zawężony do celu układu)
    sample_hi: Array

    @property
    def dim(self) -> int:
        return 3 * len(self.free)

    def decode(self, x: Array) -> Array:
        """``(B, D)`` → ``(B, n, 3)`` OKLCH."""
        return self.decode_with_maxc(x)[0]

    def decode_with_maxc(self, x: Array) -> tuple[Array, Array]:
        """Jak ``decode``, plus ``maxC`` wszystkich slotów ``(B, n)`` (do ``Ctx``)."""
        x = np.atleast_2d(x)
        b = x.shape[0]
        lch = np.broadcast_to(self.base, (b, *self.base.shape)).copy()
        maxc = np.broadcast_to(self.base_maxc, (b, len(self.base_maxc))).copy()
        if not self.free:
            return lch, maxc
        v = x.reshape(b, len(self.free), 3)
        L = np.clip(v[..., 0], 0.0, 1.0)
        h = v[..., 2] % 360.0
        u = np.clip(v[..., 1], 0.0, 1.0)
        mc = fast.max_chroma(L, h)
        lch[:, self.free, 0] = L
        lch[:, self.free, 1] = u * mc
        lch[:, self.free, 2] = h
        maxc[:, self.free] = mc
        return lch, maxc

    def encode(self, lch: Array) -> Array:
        """``(n, 3)`` → ``(D,)`` (u liczone względem maxC; kolor spoza gamutu → u = 1)."""
        rows = lch[self.free]
        maxc = fast.max_chroma(rows[:, 0], rows[:, 2])
        u = np.where(maxc > 1e-9, np.minimum(rows[:, 1] / np.maximum(maxc, 1e-9), 1.0), 0.0)
        h = rows[:, 2].copy()
        h_lo = self.lo[2::3]
        # Odcień z granicami (np. 330–380): rozwiń do [lo, lo + 360), dopiero potem przytnij.
        h = np.where(self.hue_bounded, h_lo + (h - h_lo) % 360.0, h)
        out = np.stack([rows[:, 0], u, h], axis=1)
        return np.clip(out.reshape(-1), self.lo, self.hi)

    def sample(self, rng: np.random.Generator, count: int) -> Array:
        return rng.uniform(self.sample_lo, self.sample_hi, size=(count, self.dim))


def _space(
    session: Session, free_ids: Collection[str], targets: Mapping[str, float] | None = None
) -> _Space:
    ids = [s.id for s in session.slots]
    fit = session.globals.fit_method
    # Sloty stałe liczymy w wartości po fit — taki kolor naprawdę trafi do hexa (przegląd I8).
    rows = [s.value if s.id in free_ids else col.fitted(s.value, fit) for s in session.slots]
    base = np.array([[v.l, v.c, v.h] for v in rows], dtype=np.float64)
    free = [i for i, s in enumerate(session.slots) if s.id in free_ids]
    scheme = session.globals.hue_scheme
    lo, hi, bounded, s_lo, s_hi = [], [], [], [], []
    for i in free:
        c, _ = effective_conditions(session, ids[i])
        l_lo, l_hi = 0.0, 1.0
        if c.lightness is not None and c.lightness.enabled and c.lightness.hard:
            iv = c.lightness.value
            l_lo = max(l_lo, iv.lo if iv.lo is not None else 0.0)
            l_hi = min(l_hi, iv.hi if iv.hi is not None else 1.0)
            if l_lo > l_hi:  # sprzeczny zakres — zostaw karze, nie granicom
                l_lo, l_hi = 0.0, 1.0
        u_lo, u_hi = 0.0, 1.0
        cr = c.chroma
        if cr is not None and cr.enabled and cr.hard and cr.value.mode == "rel":
            u_lo = max(0.0, cr.value.lo if cr.value.lo is not None else 0.0)
            u_hi = min(1.0, cr.value.hi if cr.value.hi is not None else 1.0)
            if u_lo > u_hi:
                u_lo, u_hi = 0.0, 1.0
        h_lo, h_hi, hb = 0.0, 360.0, False
        if c.hue_range is not None and c.hue_range.enabled and c.hue_range.hard:
            hr = c.hue_range.value
            width = (hr.hi - hr.lo) % 360.0 or (360.0 if hr.hi != hr.lo else 0.0)
            h_lo, h_hi, hb = hr.lo, hr.lo + width, True
        elif c.hue_target is not None and c.hue_target.enabled and c.hue_target.hard:
            ht = c.hue_target.value
            h_lo, h_hi, hb = ht.target - ht.tol, ht.target + ht.tol, True
        smp_lo, smp_hi = h_lo, h_hi
        own_hue = c.hue_range is not None or c.hue_target is not None
        if not own_hue and targets is not None and ids[i] in targets:
            t = targets[ids[i]]
            smp_lo, smp_hi = t - scheme.tol, t + scheme.tol  # starty przy celu układu
            if scheme.hard:  # twardy układ odcieni = granice (jak twardy cel odcienia)
                h_lo, h_hi, hb = smp_lo, smp_hi, True
        lo += [l_lo, u_lo, h_lo]
        hi += [l_hi, u_hi, h_hi]
        s_lo += [l_lo, u_lo, smp_lo]
        s_hi += [l_hi, u_hi, smp_hi]
        bounded.append(hb)
    base_maxc = fast.max_chroma(base[:, 0], base[:, 2])
    return _Space(
        ids,
        base,
        free,
        np.array(lo),
        np.array(hi),
        np.array(bounded, dtype=bool),
        base_maxc,
        np.array(s_lo),
        np.array(s_hi),
    )


def _eps(space: _Space) -> Array:
    return np.tile([1e-4, 1e-4, 1e-2], len(space.free))


# ---------------------------------------------------------------------------
# Generowanie
# ---------------------------------------------------------------------------


@dataclass
class _Run:
    terms: list[Term]
    session: Session
    space: _Space
    hard_weight: float
    previous: list[Array]  # wolne wiersze (F, 3) OKLCH wcześniejszych propozycji
    min_div: float
    calib: dict[tuple[int, int, str], float]
    deadline: float
    cancel: Callable[[], bool] | None
    budget: int
    used: int = 0
    best_f: float = np.inf
    best_x: Array | None = None
    progress: Callable[[float], None] | None = None
    progress_base: float = 0.0
    progress_span: float = 1.0

    def f_batch(self, x: Array) -> Array:
        """Funkcja celu dla ``(B, D)``; liczy budżet, pilnuje przerwania i najlepszego punktu."""
        if self.cancel is not None and self.cancel():
            raise _Stop("cancel")
        if time.monotonic() > self.deadline:
            raise _Stop("time")
        lch, maxc = self.space.decode_with_maxc(x)
        ctx = Ctx(lch, self.space.ids, self.session.globals, calib=self.calib, maxc=maxc)
        f = objective_batch(self.terms, ctx, self.hard_weight, MARGIN_FRAC)
        if self.previous:
            f = f + _diversity_penalty(lch[:, self.space.free], self.previous, self.min_div)
        self.used += x.shape[0]
        k = int(np.argmin(f))
        if f[k] < self.best_f:
            self.best_f, self.best_x = float(f[k]), np.array(x[k], copy=True)
        if self.progress is not None:
            frac = min(self.used / max(self.budget, 1), 1.0)
            self.progress(self.progress_base + self.progress_span * frac)
        return f

    def f_and_grad(self, x: Array) -> tuple[float, Array]:
        eps = _eps(self.space)
        pts = np.vstack([x, x + np.diag(eps)])
        f = self.f_batch(pts)
        return float(f[0]), (f[1:] - f[0]) / eps


def _diversity_penalty(free_lch: Array, previous: list[Array], min_div: float) -> Array:
    total = np.zeros(free_lch.shape[0])
    for p in previous:
        d = fast.delta_e(free_lch, p[None], "ok").mean(axis=1)
        v = np.maximum(min_div - d, 0.0) / DIVERSITY_SCALE
        total = total + v * v
    return total


def _local(run: _Run, x0: Array, maxfun: int) -> Array:
    bounds = [
        (lo, hi) if not (k % 3 == 2 and not run.space.hue_bounded[k // 3]) else (None, None)
        for k, (lo, hi) in enumerate(zip(run.space.lo, run.space.hi, strict=True))
    ]
    res = minimize(
        run.f_and_grad,
        x0,
        jac=True,
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxfun": max(maxfun, 2), "maxiter": max(maxfun, 2), "ftol": FTOL},
    )
    return np.asarray(res.x)


def _uses_slow_de(session: Session) -> set[str]:
    methods = {session.globals.delta_e}
    for s in session.slots:
        for r in s.relations:
            if r.kind == "distance" and r.metric is not None:
                methods.add(str(r.metric))
    return {m for m in methods if m not in VECTOR_DE}


def _calibrate(
    lch: Array, methods: set[str], accents: list[int]
) -> dict[tuple[int, int, str], float]:
    """Stosunek ΔE metody do ΔE ok dla każdej pary slotów z ``accents`` (wszystkie sloty, także tło
    i tekst — relacje odległości mogą ich dotyczyć; przegląd I2)."""
    out: dict[tuple[int, int, str], float] = {}
    rows = [OKLCH(float(r[0]), float(r[1]), float(r[2])) for r in lch]
    for m in methods:
        for a_pos, i in enumerate(accents):
            for j in accents[a_pos + 1 :]:
                ok = col.delta_e(rows[i], rows[j], "ok")
                exact = col.delta_e(rows[i], rows[j], cast(DeltaEMethod, m))
                out[(i, j, m)] = exact / ok if ok > 1e-6 else 100.0
    return out


def generate(
    session: Session,
    *,
    slot_ids: Collection[str] | None = None,
    progress: Callable[[float], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> list[Proposal]:
    """N propozycji (``optimizer.n_proposals``) dla wolnych slotów (bez kłódki; ew. podzbiór)."""
    opt = session.globals.optimizer
    targets = hue_targets_for(session)
    terms = compile_terms(session, hue_targets=targets)
    free_ids = {
        s.id for s in session.slots if not s.locked and (slot_ids is None or s.id in slot_ids)
    }
    space = _space(session, free_ids, targets)
    n = max(1, opt.n_proposals) if space.free else 1
    deadline = time.monotonic() + opt.time_cap_s
    accents = list(range(len(session.slots)))  # pary do kalibracji: wszystkie sloty
    slow = _uses_slow_de(session)
    calib = _calibrate(space.base, slow, accents) if slow else {}

    proposals: list[Proposal] = []
    previous: list[Array] = []
    for k in range(n):
        run = _Run(
            terms=terms,
            session=session,
            space=space,
            hard_weight=opt.hard_weight,
            previous=previous,
            min_div=opt.min_diversity,
            calib=dict(calib),
            deadline=deadline,
            cancel=cancel,
            budget=opt.max_evals,
            progress=progress,
            progress_base=k / n,
            progress_span=1 / n,
        )
        timed_out = False
        try:
            x = _optimize(run, np.random.default_rng([seed_entropy(opt.seed), k]), slow, accents)
        except _Stop as stop:
            if stop.reason == "cancel":
                break
            timed_out = True
            x = run.best_x if run.best_x is not None else space.encode(space.base)
        lch = space.decode(x)[0]
        proposals.append(_finish(session, terms, space, lch, previous, opt, timed_out))
        previous.append(lch[space.free].copy())
        if timed_out:
            break
    if progress is not None:
        progress(1.0)
    return proposals


def seed_entropy(seed: int) -> int:
    """numpy nie przyjmuje ujemnych ziaren → deterministyczne mapowanie na nieujemne (C3)."""
    return seed & 0xFFFFFFFFFFFFFFFF


def _hard_ok(run: _Run, x: Array) -> bool:
    lch, maxc = run.space.decode_with_maxc(x[None])
    ctx = Ctx(lch, run.space.ids, run.session.globals, calib=run.calib, maxc=maxc)
    hard = [t for t in run.terms if t.hard]
    return not hard or float(objective_batch(hard, ctx, 1.0, MARGIN_FRAC)[0]) <= SOLVED


def _optimize(run: _Run, rng: np.random.Generator, slow: set[str], accents: list[int]) -> Array:
    space = run.space
    if not space.free:
        return np.zeros((0,))
    d = space.dim
    n_samples = int(min(4096, max(16, run.budget // 4), max(2, run.budget // 2)))
    pool = space.sample(rng, n_samples)
    pool[0] = space.encode(space.base)  # bieżące wartości też są kandydatem
    f = run.f_batch(pool)
    order = np.argsort(f)
    if run.budget - run.used < d + 1:  # budżet nie starcza na lokalne kroki (przegląd M8)
        return pool[order[0]]
    starts: list[Array] = []
    for idx in order:
        cand = pool[idx]
        if all(np.abs(cand - s).max() > 0.05 for s in starts):
            starts.append(cand)
        if len(starts) >= N_STARTS:
            break
    remaining = max(run.budget - run.used, 0)
    per_start = max(remaining // (len(starts) * (d + 1) * (1 + (REFINE_ROUNDS if slow else 0))), 2)
    best_x, best_f = starts[0], np.inf
    for s in starts:
        if run.budget - run.used < d + 1:
            break
        x = _local(run, s, per_start)
        fx = float(run.f_batch(x[None])[0])
        improved = best_f - fx
        prev = best_f
        if fx < best_f:
            best_x, best_f = x, fx
        if best_f <= SOLVED:
            break
        # Stagnacja (I4): twarde spełnione, a kolejny start poprawił < 5 % → koniec startów.
        if np.isfinite(prev) and improved < STALL_FRAC * prev and _hard_ok(run, best_x):
            break
    if slow:
        for _ in range(REFINE_ROUNDS):
            lch = space.decode(best_x)[0]
            run.calib.update(_calibrate(lch, slow, accents))
            best_x = _local(run, best_x, per_start)
    return best_x


def _finish(
    session: Session,
    terms: list[Term],
    space: _Space,
    lch: Array,
    previous: list[Array],
    opt,
    timed_out: bool,
) -> Proposal:
    values = {
        sid: OKLCH(float(lch[i, 0]), float(lch[i, 1]), float(lch[i, 2]) % 360.0)
        for i, sid in enumerate(space.ids)
    }
    free_ids = {space.ids[i] for i in space.free}
    fit = session.globals.fit_method
    # Kłódki dokładnie jak na wejściu (bez szumu przeliczeń); ocena — na kolorach po fit (I8).
    for s in session.slots:
        if s.id not in free_ids:
            values[s.id] = s.value
    shown = {sid: col.fitted(v, fit) for sid, v in values.items()}
    violations = evaluate(terms, shown)
    if previous and space.free:
        free_lch = lch[space.free][None]
        dmin = min(float(fast.delta_e(free_lch, p[None], "ok").mean()) for p in previous)
        if dmin < opt.min_diversity - 1e-9:
            violations.append(
                Violation(
                    "global:diversity",
                    tuple(space.ids[i] for i in space.free),
                    "różnorodność",
                    False,
                    f"średnie ΔE ≥ {opt.min_diversity:.3f}",
                    f"{dmin:.3f}",
                    opt.min_diversity - dmin,
                )
            )
    return Proposal(
        values=values,
        hexes={sid: col.to_hex(v, fit) for sid, v in values.items()},
        fit_deltas={sid: col.fit_delta(v, fit) for sid, v in values.items()},
        score=objective(terms, shown, opt.hard_weight),
        violations=tuple(violations),
        timed_out=timed_out,
        seed=opt.seed,
        slot_ids=tuple(sid for sid in space.ids if sid in free_ids),
    )


def apply_proposal(
    session: Session, proposal: Proposal, slot_ids: Collection[str] | None = None
) -> Session:
    """Przejmuje wartości propozycji do slotów (wszystkich lub wskazanych), pomija kłódki."""
    slots = tuple(
        replace(s, value=proposal.values[s.id])
        if (not s.locked and s.id in proposal.values and (slot_ids is None or s.id in slot_ids))
        else s
        for s in session.slots
    )
    return replace(session, slots=slots)
