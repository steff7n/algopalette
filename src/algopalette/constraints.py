"""Kompilacja warunków sesji do funkcji kary (spec §5, §7).

Każdy warunek, relacja i ustawienie globalne staje się ``Term``: funkcją naruszenia ≥ 0
w jednostkach naturalnych (0 = spełniony). Termy liczą się **wsadowo**: ``Ctx`` trzyma tablicę
``(B, n, 3)`` OKLCH (B kandydatów × n slotów), więc silnik ocenia populację jednym wywołaniem.

``margin`` (jednostki naturalne) zaostrza warunek przy optymalizacji, żeby wynik nie stał na samej
granicy; raport (``evaluate``) liczy zawsze z ``margin = 0``.

ΔE ``2000``/``itp``/``cam16`` nie mają ścieżki numpy: w trybie przybliżonym (optymalizacja) term
porównuje ΔE ok z progiem przeskalowanym przez współczynnik kalibracji pary (``Ctx.calib``), a w
trybie dokładnym (``evaluate``) woła coloraide.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Literal

import numpy as np

from algopalette import color as col
from algopalette.color import fast
from algopalette.model import (
    OKLCH,
    ContrastMetric,
    DeltaEMethod,
    GlobalSettings,
    Interval,
    Relation,
    Session,
    effective_conditions,
    role_of,
)

Array = np.ndarray
VECTOR_DE: frozenset[str] = frozenset({"ok", "hyab"})
HUE_FADE_C = 0.02  # poniżej tej chromy odcień traci znaczenie (płynne wygaszanie)

SCALE_L = 0.01
SCALE_C_ABS = 0.01
SCALE_C_REL = 0.02
SCALE_H = 1.0
SCALE_CONTRAST: Mapping[str, float] = {"wcag21": 0.1, "apca": 1.0}
SCALE_DE: Mapping[str, float] = {"ok": 0.01, "hyab": 0.01}  # pozostałe metody: 1.0


def scale_de(method: str) -> float:
    return SCALE_DE.get(method, 1.0)


# ---------------------------------------------------------------------------
# Kontekst wsadowy
# ---------------------------------------------------------------------------


class Ctx:
    """Wsadowe wartości slotów: ``lch`` ma kształt ``(B, n, 3)``; slot = indeks wg ``ids``.

    ``exact=True`` (tylko B = 1) liczy ΔE spoza numpy przez coloraide; inaczej przybliżenie
    kalibrowane ``calib[(i, j, metoda)]`` (stosunek ΔE metody do ΔE ok; brak = 1.0).
    """

    def __init__(
        self,
        lch: Array,
        ids: Sequence[str],
        settings: GlobalSettings,
        *,
        exact: bool = False,
        calib: Mapping[tuple[int, int, str], float] | None = None,
    ) -> None:
        lch = np.asarray(lch, dtype=np.float64)
        if lch.ndim == 2:
            lch = lch[None]
        self.lch = lch
        self.ids = list(ids)
        self.index = {sid: i for i, sid in enumerate(self.ids)}
        self.g = settings
        self.exact = exact
        self.calib = dict(calib or {})
        self._contrast: dict[tuple[int, int, str], Array] = {}
        self._de: dict[tuple[int, int, str], Array] = {}
        self._cvd: dict[str, Array] = {}

    @property
    def batch(self) -> int:
        return self.lch.shape[0]

    def L(self, i: int) -> Array:
        return self.lch[:, i, 0]

    def C(self, i: int) -> Array:
        return self.lch[:, i, 1]

    def H(self, i: int) -> Array:
        return self.lch[:, i, 2]

    @cached_property
    def lab(self) -> Array:
        return fast.oklch_to_oklab(self.lch)

    @cached_property
    def maxc(self) -> Array:
        return fast.max_chroma(self.lch[..., 0], self.lch[..., 2])

    def rel_c(self, i: int) -> Array:
        m = self.maxc[:, i]
        return np.where(m > 1e-9, self.lch[:, i, 1] / np.maximum(m, 1e-9), 0.0)

    def hue_weight(self, *idx: int) -> Array:
        w = np.ones(self.batch)
        for i in idx:
            w = w * np.clip(self.lch[:, i, 1] / HUE_FADE_C, 0.0, 1.0) ** 2
        return w

    def contrast(self, text: int, bg: int, metric: ContrastMetric) -> Array:
        key = (text, bg, metric)
        if key not in self._contrast:
            self._contrast[key] = fast.contrast(self.lch[:, text], self.lch[:, bg], metric)
        return self._contrast[key]

    def de(self, i: int, j: int, method: DeltaEMethod, lch: Array | None = None) -> Array:
        """ΔE slotów i, j (na ``lch`` albo wartościach slotów). Dokładne lub kalibrowane."""
        src = self.lch if lch is None else lch
        key = (i, j, method) if lch is None else None
        if key is not None and key in self._de:
            return self._de[key]
        if method in VECTOR_DE:
            out = fast.delta_e(src[:, i], src[:, j], method)
        elif self.exact:
            out = np.array(
                [col.delta_e(_ok(src[k, i]), _ok(src[k, j]), method) for k in range(src.shape[0])]
            )
        else:
            ratio = self.calib.get((min(i, j), max(i, j), method), 1.0)
            out = fast.delta_e(src[:, i], src[:, j], "ok") * ratio
        if key is not None:
            self._de[key] = out
        return out

    def cvd_lch(self, kind: str) -> Array:
        if kind not in self._cvd:
            c = self.g.cvd
            self._cvd[kind] = fast.simulate_cvd(self.lch, kind, c.method, c.severity)
        return self._cvd[kind]


def _ok(row: Array) -> OKLCH:
    return OKLCH(float(row[0]), float(row[1]), float(row[2]))


# ---------------------------------------------------------------------------
# Term, Violation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    key: str
    slot_ids: tuple[str, ...]
    label: str
    hard: bool
    required: str
    achieved: str
    amount: float


VFn = Callable[[Ctx, float], Array]
DescFn = Callable[[Ctx], tuple[str, str]]


@dataclass(frozen=True)
class Term:
    """Jeden warunek. ``vfn(ctx, margin)`` → naruszenie ``(B,)``; ``describe(ctx)`` dla B = 1."""

    key: str
    slot_ids: tuple[str, ...]
    label: str
    hard: bool
    weight: float
    scale: float
    vfn: VFn
    describe: DescFn
    settings: GlobalSettings
    ids: tuple[str, ...]

    def ctx(self, values: Mapping[str, OKLCH]) -> Ctx:
        return values_ctx(values, self.ids, self.settings)

    def fn(self, values: Mapping[str, OKLCH]) -> float:
        """Naruszenie skalarne (dokładne, margin 0)."""
        return float(self.vfn(self.ctx(values), 0.0)[0])


def values_ctx(values: Mapping[str, OKLCH], ids: Sequence[str], settings: GlobalSettings) -> Ctx:
    arr = np.array([[values[i].l, values[i].c, values[i].h] for i in ids], dtype=np.float64)
    return Ctx(arr[None], ids, settings, exact=True)


def _relu(x: Array) -> Array:
    return np.maximum(x, 0.0)


def _interval_v(x: Array, lo: float | None, hi: float | None, m: float) -> Array:
    v = np.zeros_like(x)
    if lo is not None:
        v = v + _relu(lo + m - x)
    if hi is not None:
        v = v + _relu(x - (hi - m))
    return v


def _fmt_interval(lo: float | None, hi: float | None, fmt: str, unit: str = "") -> str:
    u = f" {unit}" if unit else ""
    if lo is not None and hi is not None:
        return f"{lo:{fmt}}–{hi:{fmt}}{u}"
    if lo is not None:
        return f"≥ {lo:{fmt}}{u}"
    if hi is not None:
        return f"≤ {hi:{fmt}}{u}"
    return "—"


def _contrast_fmt(metric: str) -> tuple[str, str]:
    return (".2f", "") if metric == "wcag21" else (".1f", "Lc")


def _hue_outside(h: Array, lo: float, hi: float, m: float) -> Array:
    """Odległość (°) odcienia od zakresu [lo, hi] (zawijanego przez 0°) zwężonego o ``m``."""
    width = (hi - lo) % 360.0
    if width == 0 and lo != hi:
        width = 360.0
    m = min(m, width / 2)
    lo_m, width_m = (lo + m) % 360.0, width - 2 * m
    off = (h - lo_m) % 360.0
    inside = off <= width_m
    to_lo = 360.0 - off
    to_hi = off - width_m
    return np.where(inside, 0.0, np.minimum(to_lo, to_hi))


def _angle_diff(a: Array, b: Array | float) -> Array:
    """Najkrótszy łuk b − a w (−180, 180]."""
    d = np.fmod(np.asarray(b) - a, 360.0)
    d = np.where(d <= -180.0, d + 360.0, d)
    return np.where(d > 180.0, d - 360.0, d)


def _op_v(d: Array, op: str, value: float, tol: float, m: float) -> Array:
    if op == "eq":
        return _relu(np.abs(d - value) - tol + m)
    if op == "ge":
        return _relu(value + m - d)
    return _relu(d - (value - m))


def _op_req(op: str, value: float, tol: float, fmt: str, unit: str = "") -> str:
    u = f" {unit}" if unit else ""
    if op == "eq":
        return f"{value:{fmt}} ± {tol:{fmt}}{u}"
    return f"{'≥' if op == 'ge' else '≤'} {value:{fmt}}{u}"


# ---------------------------------------------------------------------------
# Kompilacja
# ---------------------------------------------------------------------------

_CVD_NAMES = {"protan": "protanopii", "deutan": "deuteranopii", "tritan": "tritanopii"}
_REL_NAMES = {
    "hue": "odcień",
    "lightness": "jasność",
    "chroma": "nasycenie",
    "contrast": "kontrast",
    "distance": "odległość",
    "mix": "mieszanka",
}


def slot_label(session: Session, index: int) -> str:
    slot = session.slots[index]
    if slot.name:
        return slot.name
    role = role_of(index)
    return {"bg": "tło", "fg": "tekst"}.get(role, f"akcent {index - 1}")


def compile_terms(session: Session, hue_targets: Mapping[str, float] | None = None) -> list[Term]:
    """Termy wszystkich włączonych warunków; pomija relacje zerwane i termy samych kłódek."""
    g = session.globals
    ids = tuple(s.id for s in session.slots)
    idx = {sid: i for i, sid in enumerate(ids)}
    locked = {s.id for s in session.slots if s.locked}
    metric_g = g.contrast_metric
    de_g = g.delta_e
    terms: list[Term] = []

    def add(
        key: str,
        slots: tuple[str, ...],
        label: str,
        hard: bool,
        weight: float,
        scale: float,
        vfn: VFn,
        describe: DescFn,
    ) -> None:
        if slots and all(s in locked for s in slots):
            return
        terms.append(Term(key, slots, label, hard, weight, scale, vfn, describe, g, ids))

    accents = [i for i in range(len(ids)) if i >= 2]
    eff = {sid: effective_conditions(session, sid)[0] for sid in ids}

    for i, sid in enumerate(ids):
        c = eff[sid]
        name = slot_label(session, i)
        if c.lightness is not None and c.lightness.enabled:
            iv = c.lightness.value
            add(
                f"slot:{sid}:lightness",
                (sid,),
                f"jasność ({name})",
                c.lightness.hard,
                c.lightness.weight,
                SCALE_L,
                lambda x, m, i=i, iv=iv: _interval_v(x.L(i), iv.lo, iv.hi, m),
                lambda x, i=i, iv=iv: (_fmt_interval(iv.lo, iv.hi, ".3f"), f"{x.L(i)[0]:.3f}"),
            )
        if c.chroma is not None and c.chroma.enabled:
            cr = c.chroma.value
            rel = cr.mode == "rel"
            add(
                f"slot:{sid}:chroma",
                (sid,),
                f"nasycenie ({name})",
                c.chroma.hard,
                c.chroma.weight,
                SCALE_C_REL if rel else SCALE_C_ABS,
                lambda x, m, i=i, cr=cr, rel=rel: _interval_v(
                    x.rel_c(i) if rel else x.C(i), cr.lo, cr.hi, m
                ),
                lambda x, i=i, cr=cr, rel=rel: (
                    _fmt_interval(cr.lo, cr.hi, ".3f", "względne" if rel else ""),
                    f"{(x.rel_c(i) if rel else x.C(i))[0]:.3f}",
                ),
            )
        if c.hue_range is not None and c.hue_range.enabled:
            hr = c.hue_range.value
            add(
                f"slot:{sid}:hue_range",
                (sid,),
                f"odcień ({name})",
                c.hue_range.hard,
                c.hue_range.weight,
                SCALE_H,
                lambda x, m, i=i, hr=hr: _hue_outside(x.H(i), hr.lo, hr.hi, m) * x.hue_weight(i),
                lambda x, i=i, hr=hr: (f"{hr.lo:.0f}°–{hr.hi:.0f}°", f"{x.H(i)[0]:.1f}°"),
            )
        if c.hue_target is not None and c.hue_target.enabled:
            ht = c.hue_target.value
            add(
                f"slot:{sid}:hue_target",
                (sid,),
                f"cel odcienia ({name})",
                c.hue_target.hard,
                c.hue_target.weight,
                SCALE_H,
                lambda x, m, i=i, ht=ht: (
                    _relu(np.abs(_angle_diff(x.H(i), ht.target)) - ht.tol + m) * x.hue_weight(i)
                ),
                lambda x, i=i, ht=ht: (f"{ht.target:.0f}° ± {ht.tol:.0f}°", f"{x.H(i)[0]:.1f}°"),
            )
        if i >= 1 and c.contrast_bg is not None and c.contrast_bg.enabled:
            cb = c.contrast_bg.value
            metric: ContrastMetric = cb.metric or metric_g
            fmt, unit = _contrast_fmt(metric)
            add(
                f"slot:{sid}:contrast_bg",
                (sid, ids[0]),
                "kontrast z tłem",
                c.contrast_bg.hard,
                c.contrast_bg.weight,
                SCALE_CONTRAST[metric],
                lambda x, m, i=i, cb=cb, metric=metric: _interval_v(
                    x.contrast(i, 0, metric), cb.lo, cb.hi, m
                ),
                lambda x, i=i, cb=cb, metric=metric, fmt=fmt, unit=unit: (
                    _fmt_interval(cb.lo, cb.hi, fmt, unit),
                    f"{x.contrast(i, 0, metric)[0]:{fmt}}" + (f" {unit}" if unit else ""),
                ),
            )
        if i >= 2 and c.extreme is not None and c.extreme.enabled:
            weakest = c.extreme.value == "weakest"
            others = [j for j in accents if j != i]
            if others:
                add(
                    f"slot:{sid}:extreme",
                    (sid, *(ids[j] for j in others)),
                    f"{'najsłabszy' if weakest else 'najmocniejszy'} kontrast ({name})",
                    c.extreme.hard,
                    c.extreme.weight,
                    SCALE_CONTRAST[metric_g],
                    lambda x, m, i=i, o=others, w=weakest: _extreme_v(x, i, o, w, metric_g, m),
                    lambda x, i=i, o=others, w=weakest: _extreme_desc(x, i, o, w, metric_g),
                )

    # Pary akcentów: minimalna odległość i odróżnialność przy daltonizmie.
    for a_pos, i in enumerate(accents):
        for j in accents[a_pos + 1 :]:
            si, sj = ids[i], ids[j]
            _pair_term(add, eff, si, sj, i, j, "min_distance", de_g, session, None)
            for kind in sorted(g.cvd.types):
                _pair_term(add, eff, si, sj, i, j, "cvd_min_distance", de_g, session, kind)

    # Relacje.
    for i, slot in enumerate(session.slots):
        for r_i, rel in enumerate(slot.relations):
            if not rel.enabled or rel.target not in idx:
                continue
            if rel.kind == "mix" and (rel.other is None or rel.other not in idx):
                continue
            _relation_term(add, session, i, r_i, rel, idx, metric_g, de_g)

    # Rozrzut jasności akcentów.
    sp = g.lightness_spread
    if sp is not None and sp.enabled and len(accents) >= 2:
        iv: Interval = sp.value
        acc_ids = tuple(ids[j] for j in accents)
        add(
            "global:lightness_spread",
            acc_ids,
            "rozrzut jasności akcentów",
            sp.hard,
            sp.weight,
            SCALE_L,
            lambda x, m, iv=iv: _interval_v(_spread(x, accents), iv.lo, iv.hi, m),
            lambda x, iv=iv: (_fmt_interval(iv.lo, iv.hi, ".3f"), f"{_spread(x, accents)[0]:.3f}"),
        )

    # Układ odcieni: cele dla akcentów bez własnego warunku odcienia.
    scheme = g.hue_scheme
    for sid, target in (hue_targets or {}).items():
        if sid not in idx or idx[sid] < 2:
            continue
        c = eff[sid]
        if c.hue_range is not None or c.hue_target is not None:
            continue
        i = idx[sid]
        add(
            f"global:scheme:{sid}",
            (sid,),
            f"układ odcieni ({slot_label(session, i)})",
            scheme.hard,
            scheme.weight,
            SCALE_H,
            lambda x, m, i=i, t=target: (
                _relu(np.abs(_angle_diff(x.H(i), t)) - scheme.tol + m) * x.hue_weight(i)
            ),
            lambda x, i=i, t=target: (f"{t:.0f}° ± {scheme.tol:.0f}°", f"{x.H(i)[0]:.1f}°"),
        )

    # Unikanie kolorów źródła (tryb „charakter”).
    if g.avoid_colors and g.avoid_distance > 0:
        for i in accents:
            sid = ids[i]
            for k, src in enumerate(g.avoid_colors):
                ref = np.array([src.l, src.c, src.h])
                add(
                    f"global:avoid:{sid}:{k}",
                    (sid,),
                    f"unikanie koloru źródła ({slot_label(session, i)})",
                    True,
                    1.0,
                    SCALE_DE["ok"],
                    lambda x, m, i=i, ref=ref: _relu(
                        g.avoid_distance + m - fast.delta_e(x.lch[:, i], ref, "ok")
                    ),
                    lambda x, i=i, ref=ref: (
                        f"ΔE ≥ {g.avoid_distance:.3f}",
                        f"{float(fast.delta_e(x.lch[:, i], ref, 'ok')[0]):.3f}",
                    ),
                )

    # Gamut dla kolorów wolnych.
    for i, slot in enumerate(session.slots):
        if slot.locked:
            continue
        add(
            f"slot:{slot.id}:gamut",
            (slot.id,),
            f"gamut sRGB ({slot_label(session, i)})",
            True,
            1.0,
            SCALE_C_ABS,
            lambda x, m, i=i: _relu(x.C(i) - x.maxc[:, i]),
            lambda x, i=i: (f"C ≤ {x.maxc[0, i]:.3f}", f"{x.C(i)[0]:.3f}"),
        )
    return terms


def _spread(x: Ctx, accents: list[int]) -> Array:
    ls = x.lch[:, accents, 0]
    return ls.max(axis=1) - ls.min(axis=1)


def _extreme_v(
    x: Ctx, i: int, others: list[int], weakest: bool, metric: ContrastMetric, m: float
) -> Array:
    own = x.contrast(i, 0, metric)
    rest = np.stack([x.contrast(j, 0, metric) for j in others], axis=1)
    if weakest:
        return _relu(own - rest.min(axis=1) + m)
    return _relu(rest.max(axis=1) - own + m)


def _extreme_desc(
    x: Ctx, i: int, others: list[int], weakest: bool, metric: ContrastMetric
) -> tuple[str, str]:
    fmt, unit = _contrast_fmt(metric)
    rest = [float(x.contrast(j, 0, metric)[0]) for j in others]
    bound = min(rest) if weakest else max(rest)
    u = f" {unit}" if unit else ""
    req = f"{'<' if weakest else '>'} {bound:{fmt}}{u}"
    return req, f"{x.contrast(i, 0, metric)[0]:{fmt}}{u}"


def _pair_term(
    add, eff, si, sj, i, j, field, method: DeltaEMethod, session: Session, kind: str | None
) -> None:
    ci, cj = getattr(eff[si], field), getattr(eff[sj], field)
    reqs = [c for c in (ci, cj) if c is not None and c.enabled]
    if not reqs:
        return
    req = max(float(c.value) for c in reqs)
    hard = any(c.hard for c in reqs)
    weight = max(c.weight for c in reqs)
    a, b = slot_label(session, i), slot_label(session, j)
    if kind is None:
        key, label = f"pair:{si}:{sj}:min_distance", f"odległość {a} – {b}"

        def vfn(x: Ctx, m: float) -> Array:
            return _relu(req + m - x.de(i, j, method))

        def desc(x: Ctx) -> tuple[str, str]:
            return f"ΔE ≥ {req:.3f}", f"{x.de(i, j, method)[0]:.3f}"
    else:
        key = f"pair:{si}:{sj}:cvd:{kind}"
        label = f"odróżnialność przy {_CVD_NAMES[kind]}: {a} – {b}"

        def vfn(x: Ctx, m: float) -> Array:
            return _relu(req + m - x.de(i, j, method, x.cvd_lch(kind)))

        def desc(x: Ctx) -> tuple[str, str]:
            return f"ΔE ≥ {req:.3f}", f"{x.de(i, j, method, x.cvd_lch(kind))[0]:.3f}"

    add(key, (si, sj), label, hard, weight, scale_de(method), vfn, desc)


def _relation_term(
    add, session: Session, i: int, r_i: int, rel: Relation, idx, metric_g, de_g
) -> None:
    sid = session.slots[i].id
    j = idx[rel.target]
    tname = slot_label(session, j)
    key = f"slot:{sid}:rel:{rel.kind}:{r_i}"
    label = f"relacja: {_REL_NAMES[rel.kind]} względem {tname} ({slot_label(session, i)})"
    op, val, tol = rel.op, rel.value, rel.tol
    slots: tuple[str, ...] = (sid, rel.target)
    if rel.kind == "hue":
        scale = SCALE_H

        def measure(x: Ctx) -> Array:
            return _angle_diff(x.H(j), x.H(i))

        def vfn(x: Ctx, m: float) -> Array:
            e = _angle_diff(np.full(x.batch, val), measure(x))
            if op == "eq":
                v = _relu(np.abs(e) - tol + m)
            elif op == "ge":
                v = _relu(m - e)
            else:
                v = _relu(e + m)
            return v * x.hue_weight(i, j)

        fmt, unit = ".0f", "°"
    elif rel.kind == "lightness":
        scale = SCALE_L

        def measure(x: Ctx) -> Array:
            return x.L(i) - x.L(j)

        def vfn(x: Ctx, m: float) -> Array:
            return _op_v(measure(x), op, val, tol, m)

        fmt, unit = ".3f", ""
    elif rel.kind == "chroma":
        rel_mode = rel.chroma_mode == "rel"
        scale = SCALE_C_REL if rel_mode else SCALE_C_ABS

        def cval(x: Ctx, k: int) -> Array:
            return x.rel_c(k) if rel_mode else x.C(k)

        if rel.chroma_op == "add":

            def measure(x: Ctx) -> Array:
                return cval(x, i) - cval(x, j)

            def vfn(x: Ctx, m: float) -> Array:
                return _op_v(measure(x), op, val, tol, m)
        else:

            def measure(x: Ctx) -> Array:
                return cval(x, i)

            def vfn(x: Ctx, m: float) -> Array:
                return _op_v(cval(x, i) - val * cval(x, j), op, 0.0, tol, m)

        fmt, unit = ".3f", ""
    elif rel.kind == "contrast":
        metric: ContrastMetric = rel.metric if rel.metric in ("wcag21", "apca") else metric_g  # type: ignore[assignment]
        scale = SCALE_CONTRAST[metric]
        fmt, unit = _contrast_fmt(metric)

        def measure(x: Ctx) -> Array:
            return x.contrast(i, j, metric)

        def vfn(x: Ctx, m: float) -> Array:
            return _op_v(measure(x), op, val, tol, m)
    elif rel.kind == "distance":
        method: DeltaEMethod = (
            rel.metric if rel.metric in ("ok", "2000", "hyab", "itp", "cam16") else de_g
        )  # type: ignore[assignment]
        scale = scale_de(method)

        def measure(x: Ctx) -> Array:
            return x.de(i, j, method)

        def vfn(x: Ctx, m: float) -> Array:
            return _op_v(measure(x), op, val, tol, m)

        fmt, unit = ".3f", ""
    else:  # mix
        assert rel.other is not None
        k = idx[rel.other]
        t = rel.t
        slots = (sid, rel.target, rel.other)
        label = f"relacja: mieszanka {tname} i {slot_label(session, k)} ({slot_label(session, i)})"
        scale = SCALE_DE["ok"]

        def measure(x: Ctx) -> Array:
            mix_lab = x.lab[:, j] * (1 - t) + x.lab[:, k] * t
            d = x.lab[:, i] - mix_lab
            return np.sqrt(np.sum(d * d, axis=-1))

        def vfn(x: Ctx, m: float) -> Array:
            return _relu(measure(x) - tol + m)

        add(
            key,
            slots,
            label,
            rel.hard,
            rel.weight,
            scale,
            vfn,
            lambda x: (f"ΔE od mieszanki ≤ {tol:.3f}", f"{measure(x)[0]:.3f}"),
        )
        return

    u = f" {unit}" if unit and unit != "°" else unit

    def desc(x: Ctx) -> tuple[str, str]:
        req = _op_req(op, val, tol, fmt, unit if unit != "°" else "")
        if unit == "°":
            req += "°"
        if rel.kind == "chroma" and rel.chroma_op == "mul":
            req = f"{'=' if op == 'eq' else '≥' if op == 'ge' else '≤'} {val:.2f} × {tname}"
        return req, f"{measure(x)[0]:{fmt}}{u}"

    add(key, slots, label, rel.hard, rel.weight, scale, vfn, desc)


# ---------------------------------------------------------------------------
# Ocena
# ---------------------------------------------------------------------------

VIOLATION_EPS = 1e-9


def evaluate(terms: Sequence[Term], values: Mapping[str, OKLCH]) -> list[Violation]:
    """Naruszone termy (dokładnie, margin 0), z polskimi opisami wymagań i stanu."""
    if not terms:
        return []
    ctx = values_ctx(values, terms[0].ids, terms[0].settings)
    out: list[Violation] = []
    for t in terms:
        amount = float(t.vfn(ctx, 0.0)[0])
        if amount > VIOLATION_EPS:
            req, got = t.describe(ctx)
            out.append(Violation(t.key, t.slot_ids, t.label, t.hard, req, got, amount))
    return out


def objective_batch(
    terms: Sequence[Term], ctx: Ctx, hard_weight: float, margin_frac: float = 0.0
) -> Array:
    """Σ w·(v/scale)² (×hard_weight dla twardych) dla każdego kandydata; margines = frac × scale."""
    total = np.zeros(ctx.batch)
    for t in terms:
        m = margin_frac * t.scale if t.hard else 0.0
        v = t.vfn(ctx, m) / t.scale
        total = total + (hard_weight if t.hard else 1.0) * t.weight * v * v
    return total


def objective(terms: Sequence[Term], values: Mapping[str, OKLCH], hard_weight: float) -> float:
    """Skalarna funkcja celu (dokładna, bez marginesu)."""
    if not terms:
        return 0.0
    ctx = values_ctx(values, terms[0].ids, terms[0].settings)
    return float(objective_batch(terms, ctx, hard_weight)[0])


SourceKind = Literal["mood", "global", "slot"]
