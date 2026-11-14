"""Wektorowe numpy: ta sama matematyka co warstwa coloraide, na tablicach ``(..., 3)``.

Wejścia to tablice OKLCH ``[l, c, h]`` (h w stopniach) lub OKLab ``[l, a, b]``; funkcje parami
(``wcag21``, ``apca``, ``delta_e``) rozgłaszają argumenty. Macierze pochodzą z coloraide, żeby
wyniki zgadzały się z wolną ścieżką do 1e-6. ΔE 2000/itp/cam16 nie mają ścieżki numpy
(``NotImplementedError``): silnik liczy je przybliżeniem kalibrowanym, a raport — przez coloraide.
"""

from typing import Literal

import numpy as np
from coloraide.filters import cvd as _cvd
from coloraide.spaces.oklab import LMS3_TO_OKLAB, LMS_TO_XYZD65, OKLAB_TO_LMS3, XYZD65_TO_LMS
from coloraide.spaces.srgb_linear import RGB_TO_XYZ, XYZ_TO_RGB
from numpy.typing import ArrayLike, NDArray

from algopalette.color import apca as _apca

Array = NDArray[np.float64]

_OKLAB_TO_LMS3 = np.array(OKLAB_TO_LMS3)
_LMS3_TO_OKLAB = np.array(LMS3_TO_OKLAB)
_LMS_TO_LRGB = np.array(XYZ_TO_RGB) @ np.array(LMS_TO_XYZD65)
_LRGB_TO_LMS = np.array(XYZD65_TO_LMS) @ np.array(RGB_TO_XYZ)
_LMS_TO_Y = np.array(LMS_TO_XYZD65)[1]

GAMUT_EPS = 1e-6  # tolerancja przynależności do sRGB (kanały liniowe)


def _arr(x: ArrayLike) -> Array:
    return np.asarray(x, dtype=np.float64)


def oklch_to_oklab(lch: ArrayLike) -> Array:
    lch = _arr(lch)
    h = np.radians(lch[..., 2])
    return np.stack([lch[..., 0], lch[..., 1] * np.cos(h), lch[..., 1] * np.sin(h)], axis=-1)


def oklab_to_oklch(lab: ArrayLike) -> Array:
    lab = _arr(lab)
    c = np.hypot(lab[..., 1], lab[..., 2])
    h = np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360.0
    h = np.where(c < 1e-12, 0.0, h)
    return np.stack([lab[..., 0], c, h], axis=-1)


def _oklab_to_lms(lab: Array) -> Array:
    return (lab @ _OKLAB_TO_LMS3.T) ** 3


def oklab_to_linear_srgb(lab: ArrayLike) -> Array:
    """OKLab -> liniowy sRGB (bez obcinania, wartości spoza gamutu zostają)."""
    return _oklab_to_lms(_arr(lab)) @ _LMS_TO_LRGB.T


def linear_srgb_to_oklab(lin: ArrayLike) -> Array:
    return np.cbrt(_arr(lin) @ _LRGB_TO_LMS.T) @ _LMS3_TO_OKLAB.T


def oklch_to_linear_srgb(lch: ArrayLike) -> Array:
    return oklab_to_linear_srgb(oklch_to_oklab(lch))


def in_gamut(lch: ArrayLike, eps: float = GAMUT_EPS) -> NDArray[np.bool_]:
    lin = oklch_to_linear_srgb(lch)
    return np.all((lin >= -eps) & (lin <= 1.0 + eps), axis=-1)


def max_chroma(l: ArrayLike, h: ArrayLike, tol: float = 1e-5) -> Array:
    """Maks. chroma w sRGB przy (L, H): bisekcja, wynik z wnętrza gamutu (dolny koniec)."""
    l_, h_ = np.broadcast_arrays(_arr(l), _arr(h))
    lo = np.zeros_like(l_)
    hi = np.full_like(l_, 0.5)
    for _ in range(max(1, int(np.ceil(np.log2(0.5 / tol))))):
        mid = (lo + hi) / 2
        ok = in_gamut(np.stack([l_, mid, h_], axis=-1))
        lo = np.where(ok, mid, lo)
        hi = np.where(ok, hi, mid)
    return lo


def wcag21(text: ArrayLike, bg: ArrayLike) -> Array:
    """Współczynnik kontrastu WCAG 2.1 (1–21); jak ``coloraide`` ``wcag21``."""
    y_t = np.maximum(_oklab_to_lms(oklch_to_oklab(text)) @ _LMS_TO_Y, 0.0)
    y_b = np.maximum(_oklab_to_lms(oklch_to_oklab(bg)) @ _LMS_TO_Y, 0.0)
    hi, lo = np.maximum(y_t, y_b), np.minimum(y_t, y_b)
    return (hi + 0.05) / (lo + 0.05)


def _apca_y(lch: ArrayLike) -> Array:
    lin = np.maximum(oklch_to_linear_srgb(lch), 0.0)
    enc = np.where(lin > 0.0031308, 1.055 * np.power(lin, 1 / 2.4) - 0.055, 12.92 * lin)
    y = (
        _apca.S_RCO * enc[..., 0] ** _apca.MAIN_TRC
        + _apca.S_GCO * enc[..., 1] ** _apca.MAIN_TRC
        + _apca.S_BCO * enc[..., 2] ** _apca.MAIN_TRC
    )
    return y + np.maximum(_apca.BLK_THRS - y, 0.0) ** _apca.BLK_CLMP


def apca_signed(text: ArrayLike, bg: ArrayLike) -> Array:
    """Lc ze znakiem (tekst, tło), SAPC-APCA 0.0.98G-4g."""
    y_t, y_b = np.broadcast_arrays(_apca_y(text), _apca_y(bg))
    bow = (y_b**_apca.NORM_BG - y_t**_apca.NORM_TXT) * _apca.SCALE_BOW
    wob = (y_b**_apca.REV_BG - y_t**_apca.REV_TXT) * _apca.SCALE_WOB
    bow_out = np.where(bow < _apca.LO_CLIP, 0.0, bow - _apca.LO_BOW_OFFSET)
    wob_out = np.where(wob > -_apca.LO_CLIP, 0.0, wob + _apca.LO_WOB_OFFSET)
    out = np.where(y_b > y_t, bow_out, wob_out) * 100.0
    return np.where(np.abs(y_b - y_t) < _apca.DELTA_Y_MIN, 0.0, out)


def apca(text: ArrayLike, bg: ArrayLike) -> Array:
    """|Lc|."""
    return np.abs(apca_signed(text, bg))


def contrast(text: ArrayLike, bg: ArrayLike, metric: Literal["wcag21", "apca"]) -> Array:
    return wcag21(text, bg) if metric == "wcag21" else apca(text, bg)


def delta_e(a: ArrayLike, b: ArrayLike, method: str) -> Array:
    """ΔE ``ok`` (euklides w OKLab) i ``hyab`` (|ΔL| + dystans a,b w OKLab)."""
    d = oklch_to_oklab(a) - oklch_to_oklab(b)
    if method == "ok":
        return np.sqrt(np.sum(d * d, axis=-1))
    if method == "hyab":
        return np.abs(d[..., 0]) + np.hypot(d[..., 1], d[..., 2])
    raise NotImplementedError(f"Brak ścieżki numpy dla ΔE '{method}'")


_VIENOT = {"protan": _cvd.VIENOT_PROTAN, "deutan": _cvd.VIENOT_DEUTAN, "tritan": _cvd.VIENOT_TRITAN}
_BRETTEL = {
    "protan": _cvd.BRETTEL_PROTAN,
    "deutan": _cvd.BRETTEL_DEUTAN,
    "tritan": _cvd.BRETTEL_TRITAN,
}
_MACHADO = {
    "protan": _cvd.MACHADO_PROTAN,
    "deutan": _cvd.MACHADO_DEUTAN,
    "tritan": _cvd.MACHADO_TRITAN,
}


def simulate_cvd(lch: ArrayLike, kind: str, method: str, severity: float) -> Array:
    """Symulacja daltonizmu (brettel, vienot, machado) w liniowym sRGB; zwraca OKLCH."""
    lin = oklch_to_linear_srgb(lch)
    severity = min(max(float(severity), 0.0), 1.0)
    if method == "vienot":
        full = lin @ np.array(_VIENOT[kind]).T
        out = full if severity >= 1 else lin + (full - lin) * severity
    elif method == "machado":
        matrices = _MACHADO[kind]
        s = severity * 10
        i = int(s)
        out = lin @ np.array(matrices[i]).T
        if i != s and i < 10:
            out2 = lin @ np.array(matrices[i + 1]).T
            out = out + (out2 - out) * (s - i)
    elif method == "brettel":
        w1, w2, sep = (np.array(m) for m in _BRETTEL[kind])
        lms = lin @ np.array(_cvd.LRGB_TO_LMS).T
        side = (lms @ sep) > 0
        full = np.where(side[..., None], lms @ w2.T, lms @ w1.T)
        out = full if severity >= 1 else lin + (full - lin) * severity
    else:
        raise NotImplementedError(f"Brak ścieżki numpy dla metody CVD '{method}'")
    return oklab_to_oklch(linear_srgb_to_oklab(out))
