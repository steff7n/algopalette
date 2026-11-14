"""Układy odcieni: cele H dla akcentów (spec §5.4).

Układ ma k bazowych odcieni. Akcent ``i`` (0-based, kolejność slotów) dostaje
``base[i % k] + c · 360 / (k · ⌈n / k⌉)``, gdzie ``c = i // k``: kolejne „obiegi” przesuwają się
równo między bazowymi odcieniami. ``jitter`` dodaje deterministyczne przesunięcia ±jitter z ziarna.
"""

import math

import numpy as np

from algopalette.model import HueScheme, Session


def base_hues(scheme: HueScheme, n: int) -> list[float]:
    """Bazowe odcienie układu (dla ``equal`` i ``analogous`` zależą od liczby akcentów n)."""
    r = scheme.rotation
    match scheme.kind:
        case "equal":
            return [r + 360.0 * i / n for i in range(n)]
        case "analogous":
            if n == 1:
                return [scheme.center]
            lo = scheme.center - scheme.spread / 2
            return [lo + scheme.spread * i / (n - 1) for i in range(n)]
        case "complementary":
            return [r, r + 180.0]
        case "split":
            return [r, r + 150.0, r + 210.0]
        case "triad":
            return [r, r + 120.0, r + 240.0]
        case "tetrad":
            return [r, r + 90.0, r + 180.0, r + 270.0]
        case "custom":
            return list(scheme.custom)
        case _:
            return []


def scheme_targets(scheme: HueScheme, n: int, seed: int) -> list[float]:
    """Cele odcieni dla n akcentów, w [0, 360)."""
    if n <= 0:
        return []
    base = base_hues(scheme, n)
    k = len(base)
    if k == 0:
        return []
    cycles = math.ceil(n / k)
    out = [(base[i % k] + (i // k) * 360.0 / (k * cycles)) for i in range(n)]
    if scheme.jitter > 0:
        rng = np.random.default_rng([seed & 0xFFFFFFFFFFFFFFFF, 7919])  # ujemne ziarno OK
        out = [
            h + float(d)
            for h, d in zip(out, rng.uniform(-scheme.jitter, scheme.jitter, n), strict=True)
        ]
    return [h % 360.0 for h in out]


def targets_for_session(session: Session) -> dict[str, float]:
    """Cele odcieni akcentów sesji (slot id → H) wg układu i ziarna optymalizatora."""
    accents = session.slots[2:]
    hs = scheme_targets(session.globals.hue_scheme, len(accents), session.globals.optimizer.seed)
    return {s.id: h for s, h in zip(accents, hs, strict=False)}
