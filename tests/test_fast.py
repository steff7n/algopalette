"""fast.py (numpy) musi zgadzać się z coloraide / wtyczką APCA do 1e-6."""

import numpy as np
import pytest

from algopalette.color import Color, apca_signed_color, fast

N = 1000
TOL = 1e-6


def _pairs() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(0)

    def draw() -> np.ndarray:
        return np.column_stack(
            [rng.uniform(0, 1, N), rng.uniform(0, 0.4, N), rng.uniform(0, 360, N)]
        )

    return draw(), draw()


A, B = _pairs()


def _col(row: np.ndarray) -> Color:
    return Color("oklch", [float(row[0]), float(row[1]), float(row[2])])


def _cvd_ref(kind: str, method: str, severity: float) -> np.ndarray:
    out = []
    for row in A:
        f = _col(row).filter(kind, severity, method=method, space="srgb-linear")
        out.append(f.convert("oklab").coords(nans=False))
    return np.array(out)


def _cvd_fast(kind: str, method: str, severity: float) -> np.ndarray:
    return fast.oklch_to_oklab(fast.simulate_cvd(A, kind, method, severity))


def test_oklab_to_linear_srgb():
    got = fast.oklab_to_linear_srgb(fast.oklch_to_oklab(A))
    ref = np.array([_col(r).convert("srgb-linear").coords(nans=False) for r in A])
    assert np.abs(got - ref).max() < TOL


def test_linear_srgb_roundtrip():
    lab = fast.oklch_to_oklab(A)
    back = fast.linear_srgb_to_oklab(fast.oklab_to_linear_srgb(lab))
    assert np.abs(back - lab).max() < 1e-9


def test_wcag21():
    got = fast.wcag21(A, B)
    ref = np.array([_col(a).contrast(_col(b), "wcag21") for a, b in zip(A, B, strict=True)])
    assert np.abs(got - ref).max() < TOL


def test_apca():
    got = fast.apca_signed(A, B)
    ref = np.array([apca_signed_color(_col(a), _col(b)) for a, b in zip(A, B, strict=True)])
    assert np.abs(got - ref).max() < TOL
    abs_ref = np.array([_col(a).contrast(_col(b), "apca") for a, b in zip(A, B, strict=True)])
    assert np.abs(fast.apca(A, B) - abs_ref).max() < TOL


def test_delta_e_ok():
    got = fast.delta_e(A, B, "ok")
    ref = np.array([_col(a).delta_e(_col(b), method="ok") for a, b in zip(A, B, strict=True)])
    assert np.abs(got - ref).max() < TOL


def test_delta_e_hyab():
    got = fast.delta_e(A, B, "hyab")
    ref = np.array(
        [_col(a).delta_e(_col(b), method="hyab", space="oklab") for a, b in zip(A, B, strict=True)]
    )
    assert np.abs(got - ref).max() < TOL


@pytest.mark.parametrize("kind", ["protan", "deutan", "tritan"])
@pytest.mark.parametrize("method", ["vienot", "machado"])
@pytest.mark.parametrize("severity", [0.5, 1.0])
def test_cvd_matches_coloraide(kind, method, severity):
    assert np.abs(_cvd_fast(kind, method, severity) - _cvd_ref(kind, method, severity)).max() < TOL


def test_unsupported_raises():
    with pytest.raises(NotImplementedError):
        fast.delta_e(A, B, "2000")
    with pytest.raises(NotImplementedError):
        fast.simulate_cvd(A, "deutan", "brettel", 1.0)


def test_max_chroma_matches_scalar():
    from algopalette.color import max_chroma

    l, h = A[:20, 0] * 0.9 + 0.05, A[:20, 2]
    got = fast.max_chroma(l, h)
    ref = np.array([max_chroma(float(a), float(b)) for a, b in zip(l, h, strict=True)])
    assert np.abs(got - ref).max() < 2e-5


def test_in_gamut():
    lch = np.array([[0.5, 0.05, 200.0], [0.75, 0.4, 140.0]])
    assert fast.in_gamut(lch).tolist() == [True, False]
