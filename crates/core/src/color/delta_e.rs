//! Odległość kolorów ΔE: `ok`, `hyab` (oba w OKLab), `2000`, `itp`, `cam16`.
//!
//! `2000`, `itp` i `cam16` odtwarzają coloraide (to ono jest wyrocznią): CIEDE2000 w CIELAB D65,
//! ΔE ITP w ICtCp (biel 203 cd/m²) i odległość euklidesowa w CAM16-UCS przy warunkach
//! obserwacji coloraide (biel D65, luminancja adaptacji 64/π · 0,2 cd/m², tło 20 %, otoczenie
//! „average”, bez pełnej adaptacji). Stałe środowiska CAM16 są przepisane z coloraide.
//!
//! Znane odstępstwo: dla kolorów daleko poza gamutem, w których CAM16 daje ujemną barwność M,
//! coloraide przelicza kolor ponownie; tu tego nie ma (kolory palety i wyniki symulacji CVD
//! leżą w gamucie albo tuż przy nim).

use std::f64::consts::{PI, TAU};

use crate::scalar::Scalar;

use super::DeltaE;
use super::convert::{mat3, oklab_to_xyz};

const DEG: f64 = PI / 180.0;

/// ΔE dwóch kolorów OKLab wybraną metodą. Dla identycznych kolorów wynik to 0 z pochodną 0.
pub fn delta_e<T: Scalar>(a_lab: [T; 3], b_lab: [T; 3], method: DeltaE) -> T {
    match method {
        DeltaE::Ok => delta_e_ok(a_lab, b_lab),
        DeltaE::Hyab => delta_e_hyab(a_lab, b_lab),
        DeltaE::Ciede2000 => ciede2000(lab_d65(a_lab), lab_d65(b_lab)),
        DeltaE::Itp => delta_e_itp(a_lab, b_lab),
        DeltaE::Cam16 => delta_e_cam16(a_lab, b_lab),
    }
}

/// Pierwiastek z liczby nieujemnej z dokładnością do zaokrągleń (ujemny szum → 0).
#[inline]
fn sqrt_pos<T: Scalar>(v: T) -> T {
    v.maxf(0.0).sqrt()
}

/// ΔE ok: odległość euklidesowa w OKLab.
#[inline]
pub fn delta_e_ok<T: Scalar>(a: [T; 3], b: [T; 3]) -> T {
    let (dl, da, db) = (a[0] - b[0], a[1] - b[1], a[2] - b[2]);
    (dl.square() + da.square() + db.square()).sqrt()
}

/// HyAB w OKLab: |ΔL| + odległość w płaszczyźnie (a, b).
#[inline]
pub fn delta_e_hyab<T: Scalar>(a: [T; 3], b: [T; 3]) -> T {
    (a[0] - b[0]).abs() + (a[1] - b[1]).hypot(a[2] - b[2])
}

// ---------------------------------------------------------------------------
// CIEDE2000 (CIELAB D65)
// ---------------------------------------------------------------------------

/// Biel D65 coloraide: xy = (0.3127, 0.3290), Y = 1.
const WHITE_D65: [f64; 3] = [0.9504559270516716, 1.0, 1.0890577507598784];
const LAB_EPSILON: f64 = 216.0 / 24389.0;
const LAB_KAPPA: f64 = 24389.0 / 27.0;

/// OKLab → CIELAB D65 (L 0–100).
fn lab_d65<T: Scalar>(lab: [T; 3]) -> [T; 3] {
    let xyz = oklab_to_xyz(lab);
    let f: [T; 3] = std::array::from_fn(|i| {
        let t = xyz[i].scale(1.0 / WHITE_D65[i]);
        if t.val() > LAB_EPSILON {
            t.cbrt()
        } else {
            t.scale(LAB_KAPPA).offset(16.0).scale(1.0 / 116.0)
        }
    });
    [f[1].scale(116.0).offset(-16.0), (f[0] - f[1]).scale(500.0), (f[1] - f[2]).scale(200.0)]
}

#[inline]
fn pow7<T: Scalar>(v: T) -> T {
    let v2 = v.square();
    v2.square() * v2 * v
}

/// Kąt odcienia CIEDE2000 w stopniach [0, 360); 0 dla koloru achromatycznego.
#[inline]
fn hue_prime<T: Scalar>(b: T, ap: T) -> T {
    if ap.val() == 0.0 && b.val() == 0.0 {
        return T::c(0.0);
    }
    let h = b.atan2(ap);
    (if h.val() < 0.0 { h.offset(TAU) } else { h }).scale(1.0 / DEG)
}

/// CIEDE2000 (kl = kc = kh = 1), tłumaczenie wzorów (2)–(22) z coloraide.
fn ciede2000<T: Scalar>(lab1: [T; 3], lab2: [T; 3]) -> T {
    const G_CONST: f64 = 6_103_515_625.0; // 25^7
    let [l1, a1, b1] = lab1;
    let [l2, a2, b2] = lab2;

    let cm = (a1.hypot(b1) + a2.hypot(b2)).scale(0.5);
    let c7 = pow7(cm);
    let g = (T::c(1.0) - (c7 / c7.offset(G_CONST)).sqrt()).scale(0.5);

    let (ap1, ap2) = (g.offset(1.0) * a1, g.offset(1.0) * a2);
    let (cp1, cp2) = (ap1.hypot(b1), ap2.hypot(b2));
    let (hp1, hp2) = (hue_prime(b1, ap1), hue_prime(b2, ap2));

    let dl = l1 - l2;
    let dc = cp1 - cp2;
    let cpp = cp1 * cp2;
    let achromatic = cpp.val() == 0.0;

    let hdiff = hp1 - hp2;
    let dh_deg = if achromatic {
        T::c(0.0)
    } else if hdiff.val().abs() <= 180.0 {
        hdiff
    } else if hdiff.val() > 180.0 {
        hdiff.offset(-360.0)
    } else {
        hdiff.offset(360.0)
    };
    let dh = cpp.sqrt().scale(2.0) * dh_deg.scale(0.5 * DEG).sin();

    let lpm = (l1 + l2).scale(0.5);
    let cpm = (cp1 + cp2).scale(0.5);
    let hsum = hp1 + hp2;
    let hpm = if achromatic {
        hsum
    } else if hdiff.val().abs() > 180.0 {
        hsum.offset(if hsum.val() < 360.0 { 360.0 } else { -360.0 }).scale(0.5)
    } else {
        hsum.scale(0.5)
    };

    let t = T::c(1.0) - hpm.offset(-30.0).scale(DEG).cos().scale(0.17)
        + hpm.scale(2.0 * DEG).cos().scale(0.24)
        + hpm.scale(3.0).offset(6.0).scale(DEG).cos().scale(0.32)
        - hpm.scale(4.0).offset(-63.0).scale(DEG).cos().scale(0.20);
    let dt = (-(hpm.offset(-275.0).scale(1.0 / 25.0).square())).exp().scale(30.0);
    let cpm7 = pow7(cpm);
    let rc = (cpm7 / cpm7.offset(G_CONST)).sqrt().scale(2.0);
    let l_temp = lpm.offset(-50.0).square();
    let sl = (l_temp.scale(0.015) / l_temp.offset(20.0).sqrt()).offset(1.0);
    let sc = cpm.scale(0.045).offset(1.0);
    let sh = (cpm * t).scale(0.015).offset(1.0);
    let rt = -(dt.scale(2.0 * DEG).sin() * rc);

    let (x, y, z) = (dl / sl, dc / sc, dh / sh);
    sqrt_pos(x.square() + y.square() + z.square() + rt * y * z)
}

// ---------------------------------------------------------------------------
// ΔE ITP (ICtCp, PQ)
// ---------------------------------------------------------------------------

const XYZ_TO_ICTCP_LMS: [[f64; 3]; 3] = [
    [0.3592832590121218, 0.6976051147779497, -0.0358915932320289],
    [-0.19208084637049927, 1.1004767970374318, 0.07537486585191187],
    [0.0070797844607477164, 0.07483966621863658, 0.8433265453898765],
];
const LMS_P_TO_ICTCP: [[f64; 3]; 3] = [
    [0.5, 0.5, 0.0],
    [1.61376953125, -3.323486328125, 1.709716796875],
    [4.378173828125, -4.24560546875, -0.132568359375],
];
/// Luminancja bieli odniesienia w cd/m² (coloraide `ictcp.YW`).
const ITP_YW: f64 = 203.0;
const PQ_M1: f64 = 2610.0 / 16384.0;
const PQ_M2: f64 = 2523.0 / 32.0;
const PQ_C1: f64 = 3424.0 / 4096.0;
const PQ_C2: f64 = 2413.0 / 128.0;
const PQ_C3: f64 = 2392.0 / 128.0;

/// OKLab → ICtCp (odwrotna EOTF ST 2084 na LMS w cd/m²).
fn ictcp<T: Scalar>(lab: [T; 3]) -> [T; 3] {
    let abs_xyz = oklab_to_xyz(lab).map(|v| v.scale(ITP_YW));
    let pq = mat3(&XYZ_TO_ICTCP_LMS, abs_xyz).map(|c| {
        let c = c.scale(1.0 / 10000.0).spow(PQ_M1);
        (c.scale(PQ_C2).offset(PQ_C1) / c.scale(PQ_C3).offset(1.0)).spow(PQ_M2)
    });
    mat3(&LMS_P_TO_ICTCP, pq)
}

fn delta_e_itp<T: Scalar>(a: [T; 3], b: [T; 3]) -> T {
    let (p, q) = (ictcp(a), ictcp(b));
    let (di, dt, dp) = (p[0] - q[0], p[1] - q[1], p[2] - q[2]);
    (di.square() + dt.square().scale(0.25) + dp.square()).sqrt().scale(720.0)
}

// ---------------------------------------------------------------------------
// CAM16-UCS
// ---------------------------------------------------------------------------

const CAT16: [[f64; 3]; 3] = [
    [0.401288, 0.650173, -0.051461],
    [-0.250268, 1.204414, 0.045854],
    [-0.002079, 0.048952, 0.953127],
];
// Środowisko `CAM16JMh.ENV` z coloraide (wartości policzone tam, przepisane z pełną precyzją).
const CAM16_D_RGB: [f64; 3] = [1.0208562217209207, 0.9865141521462044, 0.9348569172102289];
const CAM16_FL: f64 = 0.27313053667320736;
const CAM16_FL_ROOT: f64 = 0.7229238694926879;
const CAM16_Z: f64 = 1.9272135954999579;
const CAM16_NBB: f64 = 1.0003040045593807;
const CAM16_NCB: f64 = 1.0003040045593807;
const CAM16_C: f64 = 0.69;
const CAM16_NC: f64 = 1.0;
const CAM16_A_W: f64 = 25.518496218771627;
/// `(1.64 − 0.29^n)^0.73` dla n = 0.2.
const CAM16_ALPHA_K: f64 = 0.8952178848134279;
/// Współczynniki modelu „ucs”: (kl, c1, c2).
const UCS_C1: f64 = 0.007;
const UCS_C2: f64 = 0.0228;

/// OKLab → CAM16-UCS (J′, a′, b′).
fn cam16_ucs<T: Scalar>(lab: [T; 3]) -> [T; 3] {
    let rgb = mat3(&CAT16, oklab_to_xyz(lab).map(|v| v.scale(100.0)));
    let rgb_a: [T; 3] = std::array::from_fn(|i| {
        let c = rgb[i].scale(CAM16_D_RGB[i]);
        let x = c.abs().scale(CAM16_FL * 0.01).powf(0.42);
        let adapted = x.scale(400.0) / x.offset(27.13);
        if c.val() < 0.0 { -adapted } else { adapted }
    });

    let p2 = rgb_a[0].scale(2.0) + rgb_a[1] + rgb_a[2].scale(0.05);
    let a = rgb_a[0] + (rgb_a[1].scale(-12.0) + rgb_a[2]).scale(1.0 / 11.0);
    let b = (rgb_a[0] + rgb_a[1] - rgb_a[2].scale(2.0)).scale(1.0 / 9.0);
    let u = rgb_a[0] + rgb_a[1] + rgb_a[2].scale(1.05);
    let h = b.atan2(a);

    let et = h.offset(2.0).cos().offset(3.8).scale(0.25);
    let p1 = et.scale(5e4 / 13.0 * CAM16_NC * CAM16_NCB);
    let denom = u.offset(0.305);
    let t = if denom.val() == 0.0 { T::c(0.0) } else { p1 * a.hypot(b) / denom };
    let alpha = t.spow(0.9).scale(CAM16_ALPHA_K);

    let mut j = p2.scale(CAM16_NBB / CAM16_A_W).spow(CAM16_C * CAM16_Z).scale(100.0);
    let j_root = j.scale(0.01).spow(0.5);
    let m = (alpha * j_root).scale(CAM16_FL_ROOT);

    if j.val() == 0.0 {
        if m.val() == 0.0 {
            return [T::c(0.0); 3];
        }
        j = T::c(f64::EPSILON);
    }
    let m_ucs = m.scale(UCS_C2).offset(1.0).maxf(1.0).ln().scale(1.0 / UCS_C2);
    let abs_j = j.abs();
    let j_ucs = abs_j.scale(1.0 + 100.0 * UCS_C1) / abs_j.scale(UCS_C1).offset(1.0);
    [if j.val() < 0.0 { -j_ucs } else { j_ucs }, m_ucs * h.cos(), m_ucs * h.sin()]
}

fn delta_e_cam16<T: Scalar>(a: [T; 3], b: [T; 3]) -> T {
    let (p, q) = (cam16_ucs(a), cam16_ucs(b));
    let (dj, da, db) = (p[0] - q[0], p[1] - q[1], p[2] - q[2]);
    (dj.square() + da.square() + db.square()).sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::color::convert::oklch_to_oklab;
    use crate::color::testutil::{check_gradients, random_lch};
    use crate::rng::Rng;
    use crate::scalar::Dual;

    type D6 = Dual<6>;

    const METHODS: [DeltaE; 5] =
        [DeltaE::Ok, DeltaE::Hyab, DeltaE::Ciede2000, DeltaE::Itp, DeltaE::Cam16];

    fn pair(rng: &mut Rng) -> [f64; 6] {
        let a = oklch_to_oklab(random_lch(rng));
        let b = oklch_to_oklab(random_lch(rng));
        [a[0], a[1], a[2], b[0], b[1], b[2]]
    }

    /// Para bliskich kolorów — okolica, w której działa kara za zbyt małą odległość.
    fn close_pair(rng: &mut Rng) -> [f64; 6] {
        let a = oklch_to_oklab(random_lch(rng));
        let d = [rng.range(-0.03, 0.03), rng.range(-0.02, 0.02), rng.range(-0.02, 0.02)];
        [a[0], a[1], a[2], a[0] + d[0], a[1] + d[1], a[2] + d[2]]
    }

    fn split<T: Copy>(x: &[T; 6]) -> ([T; 3], [T; 3]) {
        ([x[0], x[1], x[2]], [x[3], x[4], x[5]])
    }

    fn vars(x: &[f64; 6]) -> [D6; 6] {
        std::array::from_fn(|i| D6::var(x[i], i))
    }

    /// Wartości wyroczni: `algopalette.color.delta_e` (coloraide) dla dwóch par kolorów.
    #[test]
    fn values_match_coloraide() {
        let a = oklch_to_oklab([0.7, 0.12, 40.0]);
        let b = oklch_to_oklab([0.45, 0.09, 250.0]);
        let grey = oklch_to_oklab([0.5, 0.0, 0.0]);
        for (method, want_ab, want_ag, tol) in [
            (DeltaE::Ok, 0.3220343905885578, 0.23323807579381198, 1e-12),
            (DeltaE::Hyab, 0.4529929770256691, 0.31999999999999995, 1e-12),
            (DeltaE::Ciede2000, 47.3327920229999, 31.729757748954935, 1e-9),
            (DeltaE::Itp, 157.5347472885783, 100.19590736275262, 1e-9),
            (DeltaE::Cam16, 50.71313753708744, 33.58111784611801, 1e-9),
        ] {
            let got: f64 = delta_e(a, b, method);
            assert!((got - want_ab).abs() <= tol, "{method:?}: {got} zamiast {want_ab}");
            let got: f64 = delta_e(a, grey, method);
            assert!((got - want_ag).abs() <= tol, "{method:?} (szary): {got} zamiast {want_ag}");
        }
    }

    #[test]
    fn distance_is_symmetric_and_zero_for_identical_colors() {
        let mut rng = Rng::new(31, 0);
        for _ in 0..200 {
            let (a, b) = split(&pair(&mut rng));
            for method in METHODS {
                let ab: f64 = delta_e(a, b, method);
                let ba: f64 = delta_e(b, a, method);
                assert!(ab > 0.0 && (ab - ba).abs() <= 1e-9 * ab, "{method:?}: {ab} / {ba}");
                assert_eq!(delta_e(a, a, method), 0.0, "{method:?}");
            }
        }
    }

    #[test]
    fn derivatives_match_finite_differences() {
        for (i, method) in METHODS.into_iter().enumerate() {
            for (j, sample) in
                [pair as fn(&mut Rng) -> [f64; 6], close_pair].into_iter().enumerate()
            {
                check_gradients(
                    &format!("delta_e {method:?} (próbka {j})"),
                    40 + (2 * i + j) as u64,
                    200,
                    &sample,
                    &|x| {
                        let (a, b) = split(x);
                        delta_e(a, b, method)
                    },
                    &|x| {
                        let (a, b) = split(&vars(x));
                        delta_e(a, b, method).d
                    },
                );
            }
        }
    }

    #[test]
    fn identical_colors_have_zero_derivative() {
        let colors = [
            oklch_to_oklab([0.7, 0.12, 40.0]),
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, 0.0, 0.0],
            oklch_to_oklab([0.3, 0.05, 300.0]),
        ];
        for method in METHODS {
            for c in colors {
                let x = [c[0], c[1], c[2], c[0], c[1], c[2]];
                let (a, b) = split(&vars(&x));
                let d = delta_e(a, b, method);
                assert_eq!(d.v, 0.0, "{method:?} {c:?}");
                assert_eq!(d.d, [0.0; 6], "{method:?} {c:?}");
            }
        }
    }

    #[test]
    fn degenerate_colors_give_finite_values_and_derivatives() {
        let colors = [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, 0.0, 0.0],
            [0.25, 0.0, 0.0],
            oklch_to_oklab([0.7, 0.12, 40.0]),
            oklch_to_oklab([0.0, 0.004, 40.0]),
        ];
        for method in METHODS {
            for p in colors {
                for q in colors {
                    let x = [p[0], p[1], p[2], q[0], q[1], q[2]];
                    let (a, b) = split(&vars(&x));
                    let d = delta_e(a, b, method);
                    assert!(d.v.is_finite() && d.v >= 0.0, "{method:?} {p:?}/{q:?}: {d:?}");
                    assert!(d.d.iter().all(|g| g.is_finite()), "{method:?} {p:?}/{q:?}: {d:?}");
                }
            }
        }
    }
}
