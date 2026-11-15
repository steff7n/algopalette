//! Przekształcenia OKLCH ↔ OKLab ↔ liniowy sRGB / XYZ D65.
//!
//! Macierze pochodzą z coloraide (te same liczby co `algopalette.color.fast`), więc wyniki
//! zgadzają się z wyrocznią do błędu zaokrągleń.

use crate::scalar::Scalar;

pub(crate) const OKLAB_TO_LMS3: [[f64; 3]; 3] = [
    [1.0, 0.3963377773761749, 0.21580375730991364],
    [1.0, -0.10556134581565857, -0.0638541728258133],
    [1.0, -0.08948417752981186, -1.2914855480194092],
];

pub(crate) const LMS3_TO_OKLAB: [[f64; 3]; 3] = [
    [0.21045426830931396, 0.7936177747023053, -0.0040720430116192585],
    [1.9779985324311686, -2.42859224204858, 0.450593709617411],
    [0.025904042465547734, 0.7827717124575297, -0.8086757549230774],
];

/// LMS → liniowy sRGB (`XYZ_TO_RGB · LMS_TO_XYZD65`, iloczyn policzony przez numpy w `fast.py`).
pub(crate) const LMS_TO_LRGB: [[f64; 3]; 3] = [
    [4.07674163607596, -3.3077115392580634, 0.23096990318210453],
    [-1.2684379732850315, 2.609757349287688, -0.3413193760026571],
    [-0.004196076138675485, -0.7034186179359362, 1.7076146940746115],
];

/// Liniowy sRGB → LMS (`XYZD65_TO_LMS · RGB_TO_XYZ`).
pub(crate) const LRGB_TO_LMS: [[f64; 3]; 3] = [
    [0.4122214694707628, 0.5363325372617349, 0.05144599326750219],
    [0.2119034958178251, 0.6806995506452344, 0.10739695353694051],
    [0.08830245919005637, 0.2817188391361215, 0.6299787016738222],
];

/// LMS → XYZ D65 (biel o Y = 1).
pub(crate) const LMS_TO_XYZ: [[f64; 3]; 3] = [
    [1.226879875845924, -0.5578149944602171, 0.2813910456659647],
    [-0.04057574521480083, 1.112286803280317, -0.07171105806551635],
    [-0.07637293667466008, -0.42149333240224324, 1.5869240198367818],
];

/// Iloczyn macierzy 3×3 przez wektor.
#[inline]
pub(crate) fn mat3<T: Scalar>(m: &[[f64; 3]; 3], v: [T; 3]) -> [T; 3] {
    std::array::from_fn(|i| v[0].scale(m[i][0]) + v[1].scale(m[i][1]) + v[2].scale(m[i][2]))
}

/// Iloczyn skalarny wiersza stałych przez wektor.
#[inline]
pub(crate) fn dot3<T: Scalar>(row: &[f64; 3], v: [T; 3]) -> T {
    v[0].scale(row[0]) + v[1].scale(row[1]) + v[2].scale(row[2])
}

/// OKLCH `[l, c, h°]` → OKLab `[l, a, b]`.
#[inline]
pub fn oklch_to_oklab<T: Scalar>(lch: [T; 3]) -> [T; 3] {
    let h = lch[2].scale(std::f64::consts::PI / 180.0);
    [lch[0], lch[1] * h.cos(), lch[1] * h.sin()]
}

/// OKLab → OKLCH `[l, c, h°]`, odcień w [0, 360); dla `c < 1e-12` odcień to 0.
#[inline]
pub fn oklab_to_oklch<T: Scalar>(lab: [T; 3]) -> [T; 3] {
    let c = lab[1].hypot(lab[2]);
    if c.val() < 1e-12 {
        return [lab[0], c, T::c(0.0)];
    }
    let h = lab[2].atan2(lab[1]).scale(180.0 / std::f64::consts::PI);
    let turns = (h.val() / 360.0).floor();
    let h = h.offset(-360.0 * turns);
    // zaokrąglenie może dać dokładnie 360 dla maleńkiego kąta ujemnego
    [lab[0], c, if h.val() >= 360.0 { h.offset(-360.0) } else { h }]
}

/// OKLab → LMS (po podniesieniu do sześcianu).
#[inline]
pub(crate) fn oklab_to_lms<T: Scalar>(lab: [T; 3]) -> [T; 3] {
    mat3(&OKLAB_TO_LMS3, lab).map(Scalar::cube)
}

/// OKLab → liniowy sRGB (bez obcinania; wartości spoza gamutu zostają).
#[inline]
pub fn oklab_to_linear_srgb<T: Scalar>(lab: [T; 3]) -> [T; 3] {
    mat3(&LMS_TO_LRGB, oklab_to_lms(lab))
}

/// Liniowy sRGB → OKLab.
#[inline]
pub fn linear_srgb_to_oklab<T: Scalar>(lin: [T; 3]) -> [T; 3] {
    mat3(&LMS3_TO_OKLAB, mat3(&LRGB_TO_LMS, lin).map(Scalar::cbrt))
}

/// OKLab → XYZ D65 (biel o Y = 1).
#[inline]
pub fn oklab_to_xyz<T: Scalar>(lab: [T; 3]) -> [T; 3] {
    mat3(&LMS_TO_XYZ, oklab_to_lms(lab))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::color::testutil::{check_gradients, random_lch};
    use crate::rng::Rng;
    use crate::scalar::Dual;

    type D3 = Dual<3>;

    fn vars(x: &[f64; 3]) -> [D3; 3] {
        std::array::from_fn(|i| D3::var(x[i], i))
    }

    /// Sprawdza pochodne każdej z trzech współrzędnych wyniku przekształcenia.
    fn check_map(
        name: &str,
        sample: &dyn Fn(&mut Rng) -> [f64; 3],
        f: fn([f64; 3]) -> [f64; 3],
        d: fn([D3; 3]) -> [D3; 3],
    ) {
        for k in 0..3 {
            check_gradients(
                &format!("{name}[{k}]"),
                100 + k as u64,
                200,
                sample,
                &|x| f(*x)[k],
                &|x| d(vars(x))[k].d,
            );
        }
    }

    fn random_lab(rng: &mut Rng) -> [f64; 3] {
        oklch_to_oklab(random_lch(rng))
    }

    #[test]
    fn known_colors_convert_exactly() {
        // biel i czerń
        let white = oklab_to_linear_srgb([1.0, 0.0, 0.0]);
        for v in white {
            assert!((v - 1.0).abs() < 1e-9, "{white:?}");
        }
        assert_eq!(oklab_to_linear_srgb([0.0, 0.0, 0.0]), [0.0, 0.0, 0.0]);
        // czysta czerwień sRGB w OKLCH (wartości z coloraide)
        let red = oklab_to_oklch(linear_srgb_to_oklab([1.0, 0.0, 0.0]));
        assert!((red[0] - 0.627955363921431).abs() < 1e-9, "{red:?}");
        assert!((red[1] - 0.2576833038053605).abs() < 1e-9, "{red:?}");
        assert!((red[2] - 29.23388027962792).abs() < 1e-7, "{red:?}");
        // Y bieli = 1
        assert!((oklab_to_xyz([1.0, 0.0, 0.0])[1] - 1.0).abs() < 1e-9);
    }

    #[test]
    fn round_trips_are_identity() {
        let mut rng = Rng::new(5, 0);
        for _ in 0..500 {
            let lch = random_lch(&mut rng);
            let lab = oklch_to_oklab(lch);
            let back = oklab_to_oklch(lab);
            let lab2 = linear_srgb_to_oklab(oklab_to_linear_srgb(lab));
            for k in 0..3 {
                assert!((back[k] - lch[k]).abs() < 1e-9, "{lch:?} → {back:?}");
                assert!((lab2[k] - lab[k]).abs() < 1e-12, "{lab:?} → {lab2:?}");
            }
        }
    }

    #[test]
    fn hue_is_normalized_to_0_360() {
        assert_eq!(oklab_to_oklch([0.5, 0.0, 0.0])[2], 0.0);
        assert_eq!(oklab_to_oklch([0.5, 1e-13, -1e-13])[2], 0.0);
        let h = oklab_to_oklch([0.5, 0.1, -0.1])[2];
        assert!((h - 315.0).abs() < 1e-12);
        let h = oklab_to_oklch([0.5, 0.1, -1e-18])[2];
        assert!((0.0..360.0).contains(&h), "{h}");
    }

    #[test]
    fn derivatives_match_finite_differences() {
        check_map("oklch_to_oklab", &random_lch, oklch_to_oklab, oklch_to_oklab);
        check_map("oklab_to_oklch", &random_lab, oklab_to_oklch, oklab_to_oklch);
        check_map("oklab_to_linear_srgb", &random_lab, oklab_to_linear_srgb, oklab_to_linear_srgb);
        check_map("oklab_to_xyz", &random_lab, oklab_to_xyz, oklab_to_xyz);
        check_map(
            "linear_srgb_to_oklab",
            &|rng| oklab_to_linear_srgb(random_lab(rng)),
            linear_srgb_to_oklab,
            linear_srgb_to_oklab,
        );
    }

    #[test]
    fn degenerate_colors_have_finite_derivatives() {
        for lch in [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.5, 0.0, 200.0], [0.0, 0.0, 77.0]] {
            let lab = oklch_to_oklab(vars(&lch));
            let lin = oklab_to_linear_srgb(lab);
            let back = linear_srgb_to_oklab(lin);
            let polar = oklab_to_oklch(back);
            let xyz = oklab_to_xyz(lab);
            for v in lab.iter().chain(&lin).chain(&back).chain(&polar).chain(&xyz) {
                assert!(v.v.is_finite(), "{lch:?}: {v:?}");
                assert!(v.d.iter().all(|d| d.is_finite()), "{lch:?}: {v:?}");
            }
        }
    }
}
