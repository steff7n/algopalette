"""Warstwa koloru AlgoPalette: OKLCH, gamut, kontrast WCAG/APCA, ΔE, daltonizm.

Wolna, dokładna ścieżka opiera się na coloraide (klasa ``Color`` = ``ColorAll`` + metoda ``apca``);
szybka ścieżka numpy jest w ``algopalette.color.fast``.
"""

import math

from coloraide.everything import ColorAll

from algopalette.color import fast
from algopalette.color.apca import APCAContrast, apca_signed_color
from algopalette.model import (
    OKLCH,
    ContrastMetric,
    CvdMethod,
    CvdType,
    DeltaEMethod,
    FitMethod,
)

__all__ = [
    "Color",
    "apca_signed",
    "apca_signed_color",
    "contrast",
    "contrast_hex",
    "delta_e",
    "fast",
    "fit_delta",
    "fitted",
    "from_css",
    "from_hsl",
    "hue_diff",
    "in_gamut",
    "max_chroma",
    "simulate_cvd",
    "to_color",
    "to_hex",
    "to_hsl",
]


class Color(ColorAll):
    """coloraide ze wszystkimi przestrzeniami oraz własną metodą kontrastu ``apca``."""


Color.register(APCAContrast())

GAMUT_EPS = fast.GAMUT_EPS


def to_color(c: OKLCH) -> Color:
    """OKLCH -> obiekt coloraide (bez obcinania)."""
    return Color("oklch", [c.l, c.c, c.h])


def _from_color(col: Color) -> OKLCH:
    l_, c, h = col.convert("oklch").coords(nans=False)
    return OKLCH(float(l_), max(float(c), 0.0), float(h) % 360.0)


def in_gamut(c: OKLCH) -> bool:
    """Czy kolor mieści się w sRGB (tolerancja 1e-6 w kanałach liniowych)."""
    return to_color(c).in_gamut("srgb-linear", tolerance=GAMUT_EPS)


def max_chroma(l: float, h: float) -> float:
    """Maks. chroma w sRGB przy (L, H): bisekcja, tol 1e-5, wynik z wnętrza gamutu."""
    return float(fast.max_chroma(l, h))


def _fitted(c: OKLCH, fit: FitMethod) -> Color | None:
    """Kolor po fit() i obcięciu do sRGB; None gdy kolor już mieści się w gamucie."""
    if in_gamut(c):
        return None
    col = to_color(c).fit("srgb", method=fit)
    return col.convert("srgb").clip()


def to_hex(c: OKLCH, fit: FitMethod) -> str:
    """Hex #rrggbb; kolor spoza sRGB jest wpierw sprowadzany metodą ``fit``."""
    col = _fitted(c, fit) or to_color(c).convert("srgb").clip()
    return col.to_string(hex=True, fit=False, upper=False)


def fitted(c: OKLCH, fit: FitMethod) -> OKLCH:
    """Kolor, który naprawdę trafi do hexa: ``c`` w gamucie, inaczej wynik ``fit`` + obcięcia."""
    col = _fitted(c, fit)
    return c if col is None else _from_color(col)


def fit_delta(c: OKLCH, fit: FitMethod) -> float:
    """ΔE ok między kolorem a jego wersją po ``fit`` (0.0, gdy kolor mieści się w gamucie)."""
    col = _fitted(c, fit)
    if col is None:
        return 0.0
    return float(to_color(c).delta_e(col, method="ok"))


def from_css(text: str) -> OKLCH:
    """Hex, ``oklch()``, nazwy i inne zapisy CSS -> OKLCH. ``ValueError`` z polskim komunikatem."""
    try:
        col = Color(text.strip())
    except Exception:  # coloraide zgłasza ValueError, ale i inne błędy parsowania
        raise ValueError(f"Nie można odczytać koloru „{text}”.") from None
    c = _from_color(col)
    # Zaokrąglenie usuwa szum numeryczny (np. 70% vs 0.7, chroma ≈ 1e-17 dla szarości).
    return OKLCH(round(c.l, 12), round(c.c, 12), round(c.h, 12) % 360.0)


def to_hsl(c: OKLCH, fit: FitMethod) -> tuple[float, float, float]:
    """(H °, S %, L %) koloru po fit — tylko do pokazywania/edycji (spec §11)."""
    h, s, l_ = to_color(fitted(c, fit)).convert("hsl").coords(nans=False)
    return float(h) % 360.0, float(s) * 100.0, float(l_) * 100.0


def from_hsl(h: float, s: float, l: float) -> OKLCH:
    """HSL (H °, S %, L %) → OKLCH."""
    col = Color(
        "hsl", [h % 360.0, min(max(s, 0.0), 100.0) / 100.0, min(max(l, 0.0), 100.0) / 100.0]
    )
    return _from_color(col)


def contrast(text: OKLCH, bg: OKLCH, metric: ContrastMetric) -> float:
    """Kontrast: współczynnik WCAG 2.1 albo |Lc| APCA. Kolejność (tekst, tło)."""
    return float(to_color(text).contrast(to_color(bg), metric))


def apca_signed(text: str, bg: str) -> float:
    """Lc APCA ze znakiem dla zapisów CSS/hex (tekst, tło)."""
    return apca_signed_color(Color(text), Color(bg))


def contrast_hex(text: str, bg: str, metric: ContrastMetric) -> float:
    """Jak ``contrast``, ale dla zapisów CSS/hex."""
    return float(Color(text).contrast(Color(bg), metric))


def delta_e(a: OKLCH, b: OKLCH, method: DeltaEMethod) -> float:
    """ΔE; ``ok`` w skali OKLab (0–~1), ``hyab`` liczone w OKLab, reszta wg coloraide."""
    kwargs = {"space": "oklab"} if method == "hyab" else {}
    return float(to_color(a).delta_e(to_color(b), method=method, **kwargs))


def simulate_cvd(c: OKLCH, kind: CvdType, method: CvdMethod, severity: float) -> OKLCH:
    """Symulacja daltonizmu; wynik może leżeć poza sRGB (nie jest obcinany)."""
    col = to_color(c).filter(kind, severity, method=method, space="srgb-linear")
    return _from_color(col)


def hue_diff(a: float, b: float) -> float:
    """Najkrótszy łuk od ``a`` do ``b`` w stopniach, wynik w (−180, 180]."""
    d = math.fmod(b - a, 360.0)
    if d <= -180.0:
        d += 360.0
    elif d > 180.0:
        d -= 360.0
    return d
