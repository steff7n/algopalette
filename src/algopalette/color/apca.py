"""Wtyczka kontrastu APCA dla coloraide: SAPC-APCA 0.0.98G-4g, implementacja własna.

Kolejność argumentów ma znaczenie: ``tekst.contrast(tło, "apca")``. Zwraca |Lc|; wersja ze
znakiem (dodatni: ciemny tekst na jasnym tle, ujemny: odwrotnie) to ``apca_signed``.

Dla kolorów spoza sRGB kanały liniowe są obcinane od dołu do 0 (bez obcinania z góry), tak samo
jak w wektorowej wersji ``fast.apca_signed``.
"""

from collections.abc import Sequence
from typing import Any

from coloraide.contrast import ColorContrast
from coloraide.types import AnyColor

# Stałe 0.0.98G-4g (sRGB: Y z kanałów zakodowanych, prosta potęga mainTRC).
MAIN_TRC = 2.4
S_RCO, S_GCO, S_BCO = 0.2126729, 0.7151522, 0.0721750
NORM_BG, NORM_TXT = 0.56, 0.57  # ciemny tekst na jasnym tle
REV_BG, REV_TXT = 0.65, 0.62  # jasny tekst na ciemnym tle
BLK_THRS, BLK_CLMP = 0.022, 1.414
SCALE_BOW = SCALE_WOB = 1.14
LO_BOW_OFFSET = LO_WOB_OFFSET = 0.027
DELTA_Y_MIN = 0.0005
LO_CLIP = 0.1


def encode_srgb(linear: float) -> float:
    """Linear sRGB -> zakodowany sRGB (kanał nieujemny)."""
    linear = max(linear, 0.0)
    if linear > 0.0031308:
        return 1.055 * linear ** (1 / 2.4) - 0.055
    return 12.92 * linear


def luminance_y(lin_rgb: Sequence[float]) -> float:
    """Y wg APCA z kanałów liniowych sRGB (z miękkim ucięciem czerni)."""
    r, g, b = (encode_srgb(c) for c in lin_rgb[:3])
    y = S_RCO * r**MAIN_TRC + S_GCO * g**MAIN_TRC + S_BCO * b**MAIN_TRC
    if y < BLK_THRS:
        y += (BLK_THRS - y) ** BLK_CLMP
    return y


def lc_from_luminance(y_text: float, y_bg: float) -> float:
    """Lc ze znakiem (skala ×100) dla luminancji tekstu i tła."""
    if abs(y_bg - y_text) < DELTA_Y_MIN:
        return 0.0
    if y_bg > y_text:
        sapc = (y_bg**NORM_BG - y_text**NORM_TXT) * SCALE_BOW
        return 0.0 if sapc < LO_CLIP else (sapc - LO_BOW_OFFSET) * 100.0
    sapc = (y_bg**REV_BG - y_text**REV_TXT) * SCALE_WOB
    return 0.0 if sapc > -LO_CLIP else (sapc + LO_WOB_OFFSET) * 100.0


def apca_signed_color(text: AnyColor, bg: AnyColor) -> float:
    """Lc ze znakiem dla obiektów coloraide (tekst, tło)."""
    lin_t = text.convert("srgb-linear").coords(nans=False)
    lin_b = bg.convert("srgb-linear").coords(nans=False)
    return lc_from_luminance(luminance_y(lin_t), luminance_y(lin_b))


class APCAContrast(ColorContrast):
    """Metoda ``apca`` w ``Color.contrast``: |Lc|, kolejność (tekst, tło)."""

    NAME = "apca"

    def contrast(self, color1: AnyColor, color2: AnyColor, **kwargs: Any) -> float:
        return abs(apca_signed_color(color1, color2))
