"""Wstępna kontrola spełnialności presetów wbudowanych (bez generowania): czy dla jakiegoś tła
istnieją tekst i każdy akcent w twardych zakresach L/C, z kontrastem w wymaganym przedziale,
przy odcieniu w tolerancji celu układu."""

import sys
from dataclasses import replace

from algopalette import _engine
from algopalette.model import HueScheme, Session, default_session, remove_slot
from algopalette.presets import apply_preset
from algopalette.presets_builtin import BUILTIN


def targets(sc: HueScheme, n: int) -> list[float | None]:
    k = len(sc.hues)
    if k == 0:
        return [None] * n
    return [sc.hues[i % k] % 360.0 for i in range(n)]


def grid(lo: float, hi: float, n: int) -> list[float]:
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


def in_arc(h: float, lo: float, hi: float) -> bool:
    if (hi - lo) % 360.0 == 0.0 and hi != lo:
        return True
    return (h - lo) % 360.0 <= (hi - lo) % 360.0


def candidates(slot, hue_target, tol, metric, need_contrast=True):
    r = slot.rules
    lband = r.lightness.value if r.lightness and r.lightness.enabled else None
    llo = lband.lo if lband and lband.lo is not None else 0.02
    lhi = lband.hi if lband and lband.hi is not None else 0.99
    if hue_target is not None:
        hues = [(hue_target + d) % 360.0 for d in grid(-tol, tol, 5)]
    else:
        hues = grid(0.0, 330.0, 12)
    if r.hue and r.hue.enabled and r.hue.hard:
        arc = r.hue.value
        own = [h for h in hues if in_arc(h, arc.lo, arc.hi)]
        hues = own or [(arc.lo + ((arc.hi - arc.lo) % 360.0) * t) % 360.0 for t in (0.2, 0.5, 0.8)]
    out = []
    for h in hues:
        for l in grid(llo, lhi, 12):
            mc = _engine.max_chroma(l, h)
            ch = r.chroma.value if r.chroma and r.chroma.enabled else None
            if ch is None:
                cs = [0.0, mc / 2]
            elif ch.mode == "abs":
                if ch.lo > mc + 1e-9:
                    continue
                cs = grid(ch.lo, min(ch.hi, mc), 3)
            else:
                cs = [mc * v for v in grid(ch.lo, ch.hi, 3)]
            out += [(l, c, h) for c in cs]
    return out


def ok_contrast(slot, color, bg, metric) -> bool:
    rule = slot.rules.contrast_bg
    if rule is None or not rule.enabled or not rule.hard:
        return True
    b = rule.value
    v = abs(_engine.contrast(color, bg, b.metric or metric))
    return (b.lo is None or v >= b.lo) and (b.hi is None or v <= b.hi)


def check(s: Session) -> list[str]:
    g = s.globals
    accents = s.slots[2:]
    tg = targets(g.hue_scheme, len(accents))
    bgs = candidates(s.slots[0], None, 0.0, g.contrast_metric)
    bgs = [b for b in bgs if b[2] == bgs[0][2]]  # jeden odcień wystarczy
    best: list[str] = ["brak tła"]
    for bg in bgs:
        bad = []
        for i, slot in enumerate(s.slots[1:]):
            t = tg[i - 1] if i >= 1 and slot.use_scheme else None
            cand = candidates(slot, t, g.hue_scheme.tol, g.contrast_metric)
            if not any(ok_contrast(slot, c, bg, g.contrast_metric) for c in cand):
                bad.append(slot.name or f"#{i + 1}")
        if not bad:
            return []
        if len(bad) < len(best) or best == ["brak tła"]:
            best = bad
    return best


def main() -> None:
    only = sys.argv[1:]
    n_bad = 0
    for p in BUILTIN:
        if only and p.name not in only:
            continue
        for pol in p.polarities:
            for metric in ("wcag21", "apca"):
                for accents in (8, 5):
                    s = default_session()
                    s = replace(s, globals=replace(s.globals, polarity=pol, contrast_metric=metric))
                    while len(s.slots) - 2 > accents:
                        s = remove_slot(s, s.slots[-1].id)
                    s = apply_preset(s, p.name, polarity=pol)
                    bad = check(s)
                    if bad:
                        n_bad += 1
                        print(f"{p.name} | {pol} | {metric} | {accents + 2}: {', '.join(bad)}")
    print("niespełnialnych kombinacji:", n_bad)


main()
