"""Kompilacja warunków do funkcji kary (Task 3)."""

from dataclasses import replace

import numpy as np
import pytest

from algopalette.color import from_css
from algopalette.constraints import Ctx, compile_terms, evaluate, objective
from algopalette.model import (
    OKLCH,
    ChromaRange,
    Cond,
    ContrastBound,
    CvdSettings,
    HueRange,
    HueTarget,
    Interval,
    Relation,
    Session,
    Slot,
    SlotConditions,
    default_session,
)

EMPTY = SlotConditions()
DARK_BG = OKLCH(0.2, 0.0, 0.0)
LIGHT_FG = OKLCH(0.9, 0.0, 0.0)


def _bare(session: Session) -> Session:
    """Sesja bez domyślnych warunków ról i bez układu odcieni — testujemy pojedyncze warunki."""
    g = replace(
        session.globals,
        role_defaults={"bg": EMPTY, "fg": EMPTY, "accent": EMPTY},
        hue_scheme=replace(session.globals.hue_scheme, kind="none"),
    )
    return replace(session, globals=g)


def make(
    *accents: Slot,
    bg: OKLCH = DARK_BG,
    fg: OKLCH = LIGHT_FG,
    bg_cond: SlotConditions = EMPTY,
    **globals_kw,
) -> Session:
    s = _bare(default_session())
    slots = (
        Slot(id="bg", value=bg, conditions=bg_cond),
        Slot(id="fg", value=fg),
        *accents,
    )
    s = replace(s, slots=slots)
    if globals_kw:
        s = replace(s, globals=replace(s.globals, **globals_kw))
    return s


def values(s: Session) -> dict[str, OKLCH]:
    return {sl.id: sl.value for sl in s.slots}


def viol(s: Session, **override: OKLCH) -> list:
    v = values(s)
    v.update(override)
    return evaluate(compile_terms(s), v)


def acc(sid: str, value: OKLCH, **cond) -> Slot:
    return Slot(id=sid, value=value, conditions=SlotConditions(**cond))


def hue_session(h: float) -> Session:
    return make(acc("a", OKLCH(0.7, 0.1, h), hue_range=Cond(HueRange(330, 20))))


@pytest.mark.parametrize(("h", "amount"), [(5, 0.0), (340, 0.0), (25, 5.0), (300, 30.0)])
def test_hue_range_wraps(h, amount):
    v = viol(hue_session(h))
    got = sum(x.amount for x in v if x.key.endswith("hue_range"))
    assert got == pytest.approx(amount, abs=1e-6)


def test_gray_has_no_hue_violation():
    s = make(bg_cond=SlotConditions(hue_range=Cond(HueRange(100, 120))))
    assert viol(s) == []


def test_hue_target_tolerance():
    s = make(acc("a", OKLCH(0.7, 0.1, 50), hue_target=Cond(HueTarget(30, 10))))
    (v,) = viol(s)
    assert v.amount == pytest.approx(10.0)
    assert v.label.startswith("cel odcienia")


def test_lightness_and_chroma_rel():
    s = make(
        acc(
            "a",
            OKLCH(0.5, 0.01, 200),
            lightness=Cond(Interval(0.6, 0.8)),
            chroma=Cond(ChromaRange("rel", 0.5, None)),
        )
    )
    v = {x.key.rsplit(":", 1)[-1]: x for x in viol(s)}
    assert v["lightness"].amount == pytest.approx(0.1)
    assert v["chroma"].amount > 0.3
    assert v["lightness"].required == "0.600–0.800"


def test_contrast_bg_wcag_and_apca():
    fg = from_css("#777777")
    s = make(
        bg=from_css("#1e1e1e"),
        fg=fg,
    )
    s = replace(
        s,
        slots=(
            s.slots[0],
            replace(
                s.slots[1],
                conditions=SlotConditions(contrast_bg=Cond(ContrastBound(None, 7.0, None))),
            ),
        ),
    )
    (v,) = viol(s)
    assert v.label == "kontrast z tłem"
    assert v.required == "≥ 7.00"
    assert float(v.achieved) < 7.0
    fg_apca = replace(
        s.slots[1], conditions=SlotConditions(contrast_bg=Cond(ContrastBound("apca", 75.0, None)))
    )
    s_apca = replace(s, slots=(s.slots[0], fg_apca))
    (va,) = viol(s_apca)
    assert va.required == "≥ 75.0 Lc"
    assert float(va.achieved.split()[0]) < 75.0


def test_min_distance_pairs():
    same = OKLCH(0.7, 0.1, 100)
    s = make(
        acc("a", same, min_distance=Cond(0.08)),
        acc("b", same, min_distance=Cond(0.08)),
        acc("c", OKLCH(0.7, 0.1, 250), min_distance=Cond(0.08)),
    )
    v = [x for x in viol(s) if "min_distance" in x.key]
    assert len(v) == 1
    assert set(v[0].slot_ids) == {"a", "b"}


def test_cvd_pairs():
    red, green = from_css("#c0392b"), from_css("#2e8b3a")
    red = OKLCH(0.6, red.c * 0.6, red.h)
    green = OKLCH(0.6, green.c * 0.6, green.h)
    s = make(
        acc("r", red, cvd_min_distance=Cond(0.05)),
        acc("g", green, cvd_min_distance=Cond(0.05)),
        cvd=CvdSettings(types=frozenset({"deutan"}), method="machado", severity=1.0),
    )
    assert any("cvd" in x.key for x in viol(s))
    s_off = replace(s, globals=replace(s.globals, cvd=CvdSettings()))
    assert not any("cvd" in x.key for x in viol(s_off))


def _rel_session(b_h: float) -> Session:
    a = Slot(id="a", value=OKLCH(0.7, 0.1, 30))
    b = Slot(
        id="b",
        value=OKLCH(0.7, 0.1, b_h),
        relations=(Relation(kind="hue", target="a", op="eq", value=180, tol=10),),
    )
    return make(a, b)


def test_relation_hue_opposite():
    assert viol(_rel_session(200)) == []
    (v,) = viol(_rel_session(240))
    assert v.amount == pytest.approx(20.0)  # 210 ± 10 → 240 wychodzi o 20°
    assert v.label.startswith("relacja")


def test_relation_lightness_and_chroma():
    a = Slot(id="a", value=OKLCH(0.7, 0.10, 30))
    b = Slot(
        id="b",
        value=OKLCH(0.65, 0.05, 200),
        relations=(
            Relation(kind="lightness", target="a", op="le", value=-0.10),
            Relation(kind="chroma", target="a", op="ge", value=1.0, chroma_op="mul"),
        ),
    )
    v = {x.key.split(":")[3]: x for x in viol(make(a, b))}
    assert v["lightness"].amount == pytest.approx(0.05)
    assert v["chroma"].amount == pytest.approx(0.05)


def test_relation_mix():
    a, b = OKLCH(0.5, 0.1, 30), OKLCH(0.8, 0.1, 200)
    lab_mid = (np.array(_lab(a)) + np.array(_lab(b))) / 2
    mid = _lch(lab_mid)
    m = Slot(
        id="m",
        value=mid,
        relations=(Relation(kind="mix", target="a", other="b", op="eq", value=0, tol=0.01, t=0.5),),
    )
    s = make(Slot(id="a", value=a), Slot(id="b", value=b), m)
    assert viol(s) == []
    assert viol(s, m=OKLCH(0.5, 0.1, 30)) != []


def _lab(c: OKLCH) -> tuple[float, float, float]:
    h = np.radians(c.h)
    return (c.l, c.c * np.cos(h), c.c * np.sin(h))


def _lch(lab: np.ndarray) -> OKLCH:
    return OKLCH(
        float(lab[0]),
        float(np.hypot(lab[1], lab[2])),
        float(np.degrees(np.arctan2(lab[2], lab[1])) % 360),
    )


def test_extreme_weakest():
    s = make(
        acc("dim", OKLCH(0.75, 0.1, 30), extreme=Cond("weakest")),
        acc("x", OKLCH(0.55, 0.08, 200)),
    )
    (v,) = viol(s)
    assert "najsłabszy" in v.label
    s_ok = make(
        acc("dim", OKLCH(0.45, 0.1, 30), extreme=Cond("weakest")), acc("x", OKLCH(0.75, 0.1, 200))
    )
    assert viol(s_ok) == []


def test_disabled_and_broken_skipped():
    a = acc("a", OKLCH(0.5, 0.1, 30), lightness=Cond(Interval(0.8, 0.9), enabled=False))
    b = Slot(
        id="b",
        value=OKLCH(0.7, 0.1, 30),
        relations=(Relation(kind="hue", target="gone", op="eq", value=180, tol=1),),
    )
    s = make(a, b)
    assert compile_terms(s) == [] or all("gone" not in t.slot_ids for t in compile_terms(s))
    assert viol(s) == []


def test_locked_only_terms_dropped():
    a = replace(acc("a", OKLCH(0.7, 0.1, 30), min_distance=Cond(0.5)), locked=True)
    b = replace(acc("b", OKLCH(0.7, 0.1, 31), min_distance=Cond(0.5)), locked=True)
    s = make(a, b)
    s = replace(
        s, slots=(replace(s.slots[0], locked=True), replace(s.slots[1], locked=True), *s.slots[2:])
    )
    assert all(not {"a", "b"} >= set(t.slot_ids) for t in compile_terms(s))


def test_objective_hard_weight():
    soft = make(acc("a", OKLCH(0.5, 0.1, 30), lightness=Cond(Interval(0.6, 0.8), hard=False)))
    hard = make(acc("a", OKLCH(0.5, 0.1, 30), lightness=Cond(Interval(0.6, 0.8), hard=True)))
    o_soft = objective(compile_terms(soft), values(soft), hard_weight=1000.0)
    o_hard = objective(compile_terms(hard), values(hard), hard_weight=1000.0)
    assert o_hard == pytest.approx(o_soft * 1000.0)
    assert o_soft == pytest.approx((0.1 / 0.01) ** 2)


def test_cycle_relations_ok():
    a = Slot(id="a", value=OKLCH(0.7, 0.1, 30), relations=(Relation("lightness", "b", "ge", 0.0),))
    b = Slot(id="b", value=OKLCH(0.6, 0.1, 30), relations=(Relation("lightness", "a", "ge", 0.0),))
    v = viol(make(a, b))
    assert len(v) == 1  # b ≥ a złamane, a ≥ b spełnione


def test_lightness_spread_and_hue_targets():
    s = make(
        acc("a", OKLCH(0.7, 0.1, 10)),
        acc("b", OKLCH(0.72, 0.1, 200)),
        lightness_spread=Cond(Interval(0.1, None)),
    )
    terms = compile_terms(s, hue_targets={"a": 40.0, "b": 200.0})
    keys = [x.key for x in evaluate(terms, values(s))]
    assert "global:lightness_spread" in keys
    assert "global:scheme:a" in keys  # 10° vs cel 40° ± 15° (tol układu)
    assert "global:scheme:b" not in keys


def test_avoid_colors():
    src = OKLCH(0.7, 0.1, 30)
    s = make(acc("a", OKLCH(0.7, 0.1, 32)), avoid_colors=(src,), avoid_distance=0.05)
    assert any("avoid" in x.key for x in viol(s))


def test_batched_ctx_matches_scalar():
    s = make(
        acc(
            "a",
            OKLCH(0.5, 0.1, 30),
            lightness=Cond(Interval(0.6, 0.8)),
            contrast_bg=Cond(ContrastBound(None, 4.5, None)),
        ),
        acc("b", OKLCH(0.7, 0.15, 200), min_distance=Cond(0.2)),
    )
    terms = compile_terms(s)
    ids = [sl.id for sl in s.slots]
    base = np.array([[sl.value.l, sl.value.c, sl.value.h] for sl in s.slots])
    batch = np.stack([base, base * [1.0, 0.5, 1.0]])
    ctx = Ctx(batch, ids, s.globals)
    for t in terms:
        got = t.vfn(ctx, 0.0)
        assert got.shape == (2,)
        assert got[0] == pytest.approx(t.fn(values(s)), abs=1e-9)


@pytest.mark.parametrize(
    ("b_h", "op", "value", "amount"),
    [
        (280, "ge", 90, 200.0),  # różnica −110° → ≥ 90 złamane o 200 (przegląd C1)
        (200, "ge", 90, 0.0),  # różnica 170°
        (300, "ge", 90, 180.0),  # różnica −90°
        (60, "le", -90, 120.0),  # różnica 30° → ≤ −90 złamane o 120
        (300, "le", -50, 0.0),  # różnica −90°
    ],
)
def test_relation_hue_ge_le_not_wrapped(b_h, op, value, amount):
    a = Slot(id="a", value=OKLCH(0.7, 0.1, 30))
    b = Slot(id="b", value=OKLCH(0.7, 0.1, b_h), relations=(Relation("hue", "a", op, value),))
    got = sum(x.amount for x in viol(make(a, b)) if ":rel:" in x.key)
    assert got == pytest.approx(amount)


def test_hue_fade_respects_hard_chroma_floor():
    gray = OKLCH(0.7, 0.0, 100)
    soft_floor = make(acc("a", gray, hue_range=Cond(HueRange(200, 220))))
    assert viol(soft_floor) == []  # szarość bez warunku nasycenia: odcień nie liczy się
    hard_floor = make(
        acc(
            "a",
            gray,
            hue_range=Cond(HueRange(200, 220)),
            chroma=Cond(ChromaRange("abs", 0.05, None)),
        )
    )
    keys = {x.key.rsplit(":", 1)[-1] for x in viol(hard_floor)}
    assert "hue_range" in keys  # twarde C ≥ 0.05 → odcień liczy się w pełni
