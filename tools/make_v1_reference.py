"""Dane wzorcowe ze STAREGO silnika (Python, commit 4b71aeb) dla testów nowego silnika.

Uruchamiać wyłącznie na kodzie, w którym istnieją jeszcze ``constraints.py``, ``engine.py``,
``hues.py`` i ``moods.py``. Po ich usunięciu działa tylko ``--check`` (czyta zapisane pliki).
Importy starych modułów są leniwe (w funkcjach zapisu) i oznaczone ``ty: ignore`` — w bieżącym
drzewie tych modułów nie ma; żeby odtworzyć dane, trzeba wziąć ten plik do checkoutu 4b71aeb.

    uv run python tools/make_v1_reference.py              # zapis eval.json + quality.json
    uv run python tools/make_v1_reference.py --eval-only  # zapis samego eval.json
    uv run python tools/make_v1_reference.py --check      # liczby + pokrycie kluczy, bez zapisu
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "v1_reference"
EVAL_PATH = OUT / "eval.json"
QUALITY_PATH = OUT / "quality.json"

SEED = 20261115
N_EVAL = 300
MIN_PER_KIND = 10
KINDS = (
    "lightness",
    "chroma",
    "hue_range",
    "hue_target",
    "contrast_bg",
    "extreme",
    "min_distance",
    "cvd:",
    "rel:hue",
    "rel:lightness",
    "rel:chroma",
    "rel:contrast",
    "rel:distance",
    "rel:mix",
    "lightness_spread",
    "scheme",
    "avoid",
)
MOODS = (
    "neutralny",
    "chłodny mglisty",
    "neon",
    "ziemisty",
    "pastel",
    "nocny wysoki kontrast",
    "monochromatyczny z jednym akcentem",
    "retro terminal",
    "jesienny",
)
POLARITIES = ("dark", "light")
METRICS = ("wcag21", "apca")
DELTA_E = ("ok", "2000", "hyab", "itp", "cam16")
SCHEMES = ("equal", "analogous", "complementary", "split", "triad", "tetrad", "custom", "none")
WEIGHTS = (0.5, 1.0, 2.0)
QUALITY_PROPOSALS = 6
QUALITY_EVALS = 30_000
QUALITY_SEED = 1


def kind_of(key: str) -> str:
    """Rodzaj klucza naruszenia w nazwach z listy ``KINDS`` (albo ``gamut``)."""
    parts = key.split(":")
    if parts[0] == "pair":
        return "cvd:" if parts[3] == "cvd" else "min_distance"
    if parts[0] == "global":
        return parts[1]
    if parts[2] == "rel":
        return f"rel:{parts[3]}"
    return parts[2]


# ---------------------------------------------------------------------------
# Generator sesji v1 (importy starego kodu lokalnie: --check działa bez niego)
# ---------------------------------------------------------------------------


def _flags(rng: random.Random) -> dict[str, Any]:
    return {
        "enabled": rng.random() < 0.9,
        "hard": rng.random() < 0.6,
        "weight": rng.choice(WEIGHTS),
    }


def _interval(rng: random.Random, lo_max: float, w_lo: float, w_hi: float, top: float):
    from algopalette.model import Interval

    lo = rng.uniform(0.0, lo_max)
    hi = min(lo + rng.uniform(w_lo, w_hi), top)
    r = rng.random()
    if r < 0.08:
        return Interval(None, hi)
    if r < 0.16:
        return Interval(lo, None)
    return Interval(lo, hi)


def _random_value(rng: random.Random, field: str, metric: str, de: str) -> Any:
    from algopalette.model import (
        ChromaRange,  # ty: ignore[unresolved-import]
        ContrastBound,
        HueRange,  # ty: ignore[unresolved-import]
        HueTarget,  # ty: ignore[unresolved-import]
    )
    from algopalette.units import DE_SCALE

    if field == "lightness":
        return _interval(rng, 0.8, 0.05, 0.4, 1.0)
    if field == "chroma":
        if rng.random() < 0.6:
            iv = _interval(rng, 0.15, 0.02, 0.15, 0.37)
            return ChromaRange("abs", iv.lo, iv.hi)
        iv = _interval(rng, 0.7, 0.1, 0.3, 1.0)
        return ChromaRange("rel", iv.lo, iv.hi)
    if field == "hue_range":
        lo = rng.uniform(0.0, 360.0)
        return HueRange(lo, (lo + rng.uniform(20.0, 200.0)) % 360.0)
    if field == "hue_target":
        return HueTarget(rng.uniform(0.0, 360.0), rng.uniform(5.0, 40.0))
    if field == "contrast_bg":
        own = None if rng.random() < 0.7 else rng.choice(METRICS)
        m = own or metric
        lo = rng.uniform(1.5, 9.0) if m == "wcag21" else rng.uniform(20.0, 90.0)
        hi = None
        if rng.random() < 0.2:
            hi = lo + (rng.uniform(1.0, 6.0) if m == "wcag21" else rng.uniform(10.0, 30.0))
        return ContrastBound(own, lo, hi)
    if field == "min_distance":
        return rng.uniform(0.03, 0.2) * DE_SCALE[de]
    if field == "cvd_min_distance":
        return rng.uniform(0.02, 0.1) * DE_SCALE[de]
    if field == "extreme":
        return rng.choice(("weakest", "strongest"))
    raise ValueError(field)


def _random_conditions(
    rng: random.Random, base: Any, role: Any, prob: float, metric: str, de: str, hue_kind: Any
) -> Any:
    """Zastępuje pola ``base`` z prawdopodobieństwem ``prob``; najwyżej jeden rodzaj odcienia."""
    from algopalette.forms import fields_for
    from algopalette.model import Cond  # ty: ignore[unresolved-import]

    changes: dict[str, Any] = {}
    names = [f for f in fields_for(role) if f not in ("hue_range", "hue_target")]
    for name in names:
        if rng.random() < prob:
            changes[name] = Cond(_random_value(rng, name, metric, de), **_flags(rng))
    if rng.random() < prob:
        kind = hue_kind or rng.choice(("hue_range", "hue_target"))
        changes[kind] = Cond(_random_value(rng, kind, metric, de), **_flags(rng))
    return replace(base, **changes)


def _random_relation(rng: random.Random, ids: list[str], own: str, metric: str, de: str) -> Any:
    from algopalette.model import Relation
    from algopalette.units import DE_SCALE

    others = [i for i in ids if i != own]
    target = rng.choice(others)
    if rng.random() < 0.05:
        target = f"x{rng.getrandbits(28):07x}"  # zależność zerwana
    kind = rng.choice(("hue", "lightness", "chroma", "contrast", "distance", "mix"))
    op = rng.choice(("eq", "ge", "le"))
    kw: dict[str, Any] = {}
    if kind == "hue":
        value, tol = rng.uniform(-180.0, 180.0), rng.uniform(5.0, 30.0)
    elif kind == "lightness":
        value, tol = rng.uniform(-0.4, 0.4), rng.uniform(0.01, 0.1)
    elif kind == "chroma":
        mode = rng.choice(("abs", "rel"))
        cop = rng.choice(("add", "mul"))
        span, tols = (0.1, (0.005, 0.03)) if mode == "abs" else (0.5, (0.02, 0.1))
        value = rng.uniform(-span, span) if cop == "add" else rng.uniform(0.3, 2.0)
        tol = rng.uniform(*tols)
        kw = {"chroma_op": cop, "chroma_mode": mode}
    elif kind == "contrast":
        own_metric = None if rng.random() < 0.5 else rng.choice(METRICS)
        m = own_metric or metric
        if m == "wcag21":
            value, tol = rng.uniform(1.2, 8.0), rng.uniform(0.1, 1.0)
        else:
            value, tol = rng.uniform(10.0, 90.0), rng.uniform(1.0, 10.0)
        kw = {"metric": own_metric}
    elif kind == "distance":
        own_de = None if rng.random() < 0.5 else rng.choice(DELTA_E)
        scale = DE_SCALE[own_de or de]
        value, tol = rng.uniform(0.03, 0.3) * scale, rng.uniform(0.005, 0.03) * scale
        kw = {"metric": own_de}
    else:  # mix
        rest = [i for i in others if i != target]
        op, value, tol = "eq", 0.0, rng.uniform(0.01, 0.08)
        kw = {"other": rng.choice(rest), "t": rng.random()}
    return Relation(kind=kind, target=target, op=op, value=value, tol=tol, **kw, **_flags(rng))  # type: ignore[arg-type]


def _random_color(rng: random.Random) -> Any:
    from algopalette import color
    from algopalette.model import OKLCH

    l_, h = rng.uniform(0.05, 0.97), rng.uniform(0.0, 360.0)
    c = rng.random() * color.max_chroma(l_, h)
    if rng.random() < 0.1:
        c *= 1.3  # poza gamutem
    return OKLCH(l_, c, h)


def _deterministic_ids(rng: random.Random, session: Any) -> Any:
    used: set[str] = set()
    slots = []
    for s in session.slots:
        sid = f"{rng.getrandbits(32):08x}"
        while sid in used:
            sid = f"{rng.getrandbits(32):08x}"
        used.add(sid)
        slots.append(replace(s, id=sid))
    return replace(session, slots=tuple(slots))


def random_session(rng: random.Random) -> Any:
    from algopalette.globals_logic import change_polarity_or_metric  # ty: ignore[unresolved-import]
    from algopalette.model import (
        OKLCH,
        Cond,  # ty: ignore[unresolved-import]
        CvdSettings,
        HueScheme,
        Interval,
        add_accent,
        default_session,
        remove_slot,
        role_of,
    )

    s = default_session()
    n_acc = rng.randint(1, 14)
    while len(s.slots) - 2 > n_acc:
        s = remove_slot(s, s.slots[-1].id)
    while len(s.slots) - 2 < n_acc:
        s = add_accent(s)
    s = _deterministic_ids(rng, s)
    polarity, metric = rng.choice(POLARITIES), rng.choice(METRICS)
    s = change_polarity_or_metric(s, polarity=polarity, contrast_metric=metric)
    de = "ok" if rng.random() < 0.4 else rng.choice(DELTA_E[1:])
    cvd = CvdSettings()
    if rng.random() < 0.5:
        types: list[Any] = [t for t in ("protan", "deutan", "tritan") if rng.random() < 0.5]
        types = types or [rng.choice(("protan", "deutan", "tritan"))]
        cvd = CvdSettings(
            frozenset(types),
            rng.choice(("brettel", "vienot", "machado")),
            rng.choice((1.0, 0.6)),
        )
    kind = rng.choice(SCHEMES)
    scheme = HueScheme(
        kind=kind,  # type: ignore[arg-type]
        rotation=rng.uniform(0.0, 360.0),
        center=rng.uniform(0.0, 360.0),
        spread=rng.uniform(30.0, 180.0),
        custom=tuple(rng.uniform(0.0, 360.0) for _ in range(rng.randint(1, 6)))
        if kind == "custom"
        else (),
        tol=rng.uniform(5.0, 30.0),
        jitter=0.0,
        hard=rng.random() < 0.2,
        weight=rng.choice(WEIGHTS),
    )
    spread = None
    if rng.random() < 0.3:
        iv = (
            Interval(None, rng.uniform(0.05, 0.3))
            if rng.random() < 0.7
            else Interval(rng.uniform(0.05, 0.3), None)
        )
        spread = Cond(iv, **_flags(rng))

    roles: dict[str, Any] = {}
    role_hue: dict[str, str | None] = {}
    for role in ("bg", "fg", "accent"):
        rc = _random_conditions(rng, s.globals.role_defaults[role], role, 0.5, metric, de, None)
        roles[role] = rc
        role_hue[role] = (
            "hue_range"
            if rc.hue_range is not None
            else "hue_target"
            if rc.hue_target is not None
            else None
        )

    ids = [sl.id for sl in s.slots]
    slots = []
    for i, sl in enumerate(s.slots):
        role = role_of(i)
        cond = _random_conditions(rng, sl.conditions, role, 0.25, metric, de, role_hue[role])
        n_rel = rng.choices((0, 1, 2), weights=(50, 30, 20))[0]
        rels = tuple(_random_relation(rng, ids, sl.id, metric, de) for _ in range(n_rel))
        slots.append(
            replace(
                sl,
                value=_random_color(rng),
                conditions=cond,
                relations=rels,
                locked=rng.random() < 0.15,
            )
        )

    avoid: tuple[Any, ...] = ()
    avoid_distance = 0.0
    if rng.random() < 0.2:
        picked = []
        for _ in range(rng.randint(1, 3)):
            if rng.random() < 0.6:  # blisko któregoś akcentu — żeby term bywał naruszony
                v = rng.choice(slots[2:]).value
                picked.append(OKLCH(min(max(v.l + rng.uniform(-0.01, 0.01), 0.0), 1.0), v.c, v.h))
            else:
                picked.append(_random_color(rng))
        avoid, avoid_distance = tuple(picked), rng.uniform(0.03, 0.08)

    g = replace(
        s.globals,
        role_defaults=roles,
        delta_e=de,
        cvd=cvd,
        hue_scheme=scheme,
        lightness_spread=spread,
        avoid_colors=avoid,
        avoid_distance=avoid_distance,
    )
    return replace(s, globals=g, slots=tuple(slots))


def evaluate_v1(session: Any) -> tuple[float, list[dict[str, Any]]]:
    from algopalette.constraints import compile_terms, objective  # ty: ignore[unresolved-import]
    from algopalette.hues import targets_for_session  # ty: ignore[unresolved-import]

    from algopalette.color import fitted
    from algopalette.forms import current_violations  # ty: ignore[unresolved-import]

    violations = [
        {"key": v.key, "hard": v.hard, "amount": v.amount} for v in current_violations(session)
    ]
    terms = compile_terms(session, hue_targets=targets_for_session(session))
    fit = session.globals.fit_method
    values = {sl.id: fitted(sl.value, fit) for sl in session.slots}
    return objective(terms, values, session.globals.optimizer.hard_weight), violations


def build_eval() -> list[dict[str, Any]]:
    from algopalette.io import session_to_dict

    rng = random.Random(SEED)
    cases = []
    for _ in range(N_EVAL):
        s = random_session(rng)
        obj, violations = evaluate_v1(s)
        cases.append({"session": session_to_dict(s), "objective": obj, "violations": violations})
    return cases


def _quality_case(args: tuple[str, str, str]) -> dict[str, Any]:
    from algopalette.moods import apply_mood  # ty: ignore[unresolved-import]

    from algopalette.engine import generate
    from algopalette.globals_logic import change_polarity_or_metric  # ty: ignore[unresolved-import]
    from algopalette.io import session_to_dict
    from algopalette.model import default_session

    mood, polarity, metric = args
    rng = random.Random(f"{SEED}:{mood}:{polarity}:{metric}")
    s = _deterministic_ids(rng, default_session())
    s = change_polarity_or_metric(s, polarity=polarity, contrast_metric=metric)
    s = apply_mood(s, mood)
    opt = replace(
        s.globals.optimizer,
        n_proposals=QUALITY_PROPOSALS,
        max_evals=QUALITY_EVALS,
        seed=QUALITY_SEED,
    )
    s = replace(s, globals=replace(s.globals, optimizer=opt))
    # Limit czasu to tylko bezpiecznik — przy obciążonej maszynie nie może zmienić wyniku.
    run = replace(s, globals=replace(s.globals, optimizer=replace(opt, time_cap_s=3600.0)))
    proposals = generate(run)
    if len(proposals) != QUALITY_PROPOSALS or any(p.timed_out for p in proposals):
        raise RuntimeError(f"niepełny przebieg: {mood}/{polarity}/{metric}")
    ok = [p.score for p in proposals if p.ok]
    scores = [p.score for p in proposals]
    return {
        "mood": mood,
        "polarity": polarity,
        "metric": metric,
        "session": session_to_dict(s),
        "ok_count": len(ok),
        "best_score": min(ok) if ok else min(scores),
        "scores": scores,
    }


def build_quality() -> list[dict[str, Any]]:
    jobs = [(m, p, k) for m in MOODS for p in POLARITIES for k in METRICS]
    with ProcessPoolExecutor(max_workers=6) as pool:
        return list(pool.map(_quality_case, jobs))


def _write(path: Path, cases: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(c, ensure_ascii=False, separators=(",", ":")) for c in cases]
    path.write_text("[\n" + ",\n".join(lines) + "\n]\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# --check (bez starego kodu)
# ---------------------------------------------------------------------------


def _effective(session: dict[str, Any], index: int, field: str) -> Any:
    role = ("bg", "fg")[index] if index < 2 else "accent"
    own = session["slots"][index]["conditions"][field]
    return own if own is not None else session["globals"]["role_defaults"][role][field]


def check() -> list[str]:
    """Lista problemów (pusta = dane poprawne)."""
    problems: list[str] = []
    cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    quality = json.loads(QUALITY_PATH.read_text(encoding="utf-8"))
    if len(cases) != N_EVAL:
        problems.append(f"eval: {len(cases)} przypadków zamiast {N_EVAL}")
    counts = dict.fromkeys(KINDS, 0)
    for n, case in enumerate(cases):
        s = case["session"]
        if s["format"] != "algopalette.v1":
            problems.append(f"eval[{n}]: format {s['format']!r}")
        if s["globals"]["hue_scheme"]["jitter"] != 0:
            problems.append(f"eval[{n}]: jitter ≠ 0")
        for i in range(len(s["slots"])):
            if (
                _effective(s, i, "hue_range") is not None
                and _effective(s, i, "hue_target") is not None
            ):
                problems.append(f"eval[{n}]: slot {i} ma naraz hue_range i hue_target")
        if not isinstance(case["objective"], float):
            problems.append(f"eval[{n}]: objective nie jest liczbą")
        for v in case["violations"]:
            kind = kind_of(v["key"])
            if kind in counts:
                counts[kind] += 1
            elif kind != "gamut":
                problems.append(f"eval[{n}]: nieznany rodzaj klucza {v['key']!r}")
    for kind, count in counts.items():
        if count < MIN_PER_KIND:
            problems.append(f"eval: rodzaj {kind!r} występuje {count} razy (< {MIN_PER_KIND})")
    expected = {(m, p, k) for m in MOODS for p in POLARITIES for k in METRICS}
    got = {(q["mood"], q["polarity"], q["metric"]) for q in quality}
    if len(quality) != len(expected) or got != expected:
        problems.append(f"quality: {len(quality)} przypadków, oczekiwano {len(expected)} różnych")
    for q in quality:
        opt = q["session"]["globals"]["optimizer"]
        tag = f"quality[{q['mood']}/{q['polarity']}/{q['metric']}]"
        if (opt["n_proposals"], opt["max_evals"], opt["seed"]) != (
            QUALITY_PROPOSALS,
            QUALITY_EVALS,
            QUALITY_SEED,
        ):
            problems.append(f"{tag}: inne ustawienia generowania")
        if len(q["scores"]) != QUALITY_PROPOSALS or not 0 <= q["ok_count"] <= QUALITY_PROPOSALS:
            problems.append(f"{tag}: zła liczba wyników")
        if q["session"]["mood"] != q["mood"]:
            problems.append(f"{tag}: sesja bez nałożonego nastroju")
    if not problems:
        print(
            f"eval: {len(cases)} przypadków, quality: {len(quality)} przypadków, pokrycie kluczy OK"
        )
        print("  " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("--check", action="store_true", help="sprawdź zapisane pliki, nic nie zapisuj")
    ap.add_argument("--eval-only", action="store_true", help="zapisz tylko eval.json")
    ns = ap.parse_args()
    if ns.check:
        problems = check()
        for p in problems:
            print(p, file=sys.stderr)
        return 1 if problems else 0
    _write(EVAL_PATH, build_eval())
    print(f"zapisano {EVAL_PATH}")
    if not ns.eval_only:
        _write(QUALITY_PATH, build_quality())
        print(f"zapisano {QUALITY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
