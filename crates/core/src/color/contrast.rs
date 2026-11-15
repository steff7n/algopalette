//! Kontrast: współczynnik WCAG 2.1 i APCA (SAPC-APCA 0.0.98G-4g).
//!
//! Wzory i stałe jak w `algopalette.color.fast` / `color/apca.py`. Kolejność argumentów ma
//! znaczenie dla APCA: (tekst, tło).

use crate::scalar::Scalar;

use super::ContrastMetric;
use super::convert::{LMS_TO_XYZ, dot3, oklab_to_linear_srgb, oklab_to_lms};

// Stałe APCA 0.0.98G-4g (sRGB: Y z kanałów zakodowanych, prosta potęga mainTRC).
const MAIN_TRC: f64 = 2.4;
const S_RGB: [f64; 3] = [0.2126729, 0.7151522, 0.0721750];
const NORM_BG: f64 = 0.56;
const NORM_TXT: f64 = 0.57;
const REV_BG: f64 = 0.65;
const REV_TXT: f64 = 0.62;
const BLK_THRS: f64 = 0.022;
const BLK_CLMP: f64 = 1.414;
const SCALE: f64 = 1.14;
const LO_OFFSET: f64 = 0.027;
const DELTA_Y_MIN: f64 = 0.0005;
const LO_CLIP: f64 = 0.1;

/// Luminancja względna Y (XYZ D65), obcięta od dołu do 0.
#[inline]
fn luminance<T: Scalar>(lab: [T; 3]) -> T {
    dot3(&LMS_TO_XYZ[1], oklab_to_lms(lab)).maxf(0.0)
}

/// Współczynnik kontrastu WCAG 2.1 (1–21); symetryczny względem argumentów.
pub fn wcag21<T: Scalar>(text_lab: [T; 3], bg_lab: [T; 3]) -> T {
    let (y_t, y_b) = (luminance(text_lab), luminance(bg_lab));
    let (hi, lo) = if y_t.val() >= y_b.val() { (y_t, y_b) } else { (y_b, y_t) };
    hi.offset(0.05) / lo.offset(0.05)
}

/// Luminancja Y wg APCA z miękkim ucięciem czerni; kanały ujemne obcinane do 0.
#[inline]
fn apca_y<T: Scalar>(lab: [T; 3]) -> T {
    let lin = oklab_to_linear_srgb(lab);
    let mut y = T::c(0.0);
    for (k, &coef) in S_RGB.iter().enumerate() {
        let v = lin[k].maxf(0.0);
        let encoded = if v.val() > 0.0031308 {
            v.powf(1.0 / 2.4).scale(1.055).offset(-0.055)
        } else {
            v.scale(12.92)
        };
        y = y + encoded.powf(MAIN_TRC).scale(coef);
    }
    y + (T::c(BLK_THRS) - y).maxf(0.0).powf(BLK_CLMP)
}

/// Lc APCA ze znakiem, w skali ×100: dodatni dla ciemnego tekstu na jasnym tle.
pub fn apca_signed<T: Scalar>(text_lab: [T; 3], bg_lab: [T; 3]) -> T {
    let (y_t, y_b) = (apca_y(text_lab), apca_y(bg_lab));
    if (y_b.val() - y_t.val()).abs() < DELTA_Y_MIN {
        return T::c(0.0);
    }
    if y_b.val() > y_t.val() {
        let sapc = (y_b.powf(NORM_BG) - y_t.powf(NORM_TXT)).scale(SCALE);
        if sapc.val() < LO_CLIP { T::c(0.0) } else { sapc.offset(-LO_OFFSET).scale(100.0) }
    } else {
        let sapc = (y_b.powf(REV_BG) - y_t.powf(REV_TXT)).scale(SCALE);
        if sapc.val() > -LO_CLIP { T::c(0.0) } else { sapc.offset(LO_OFFSET).scale(100.0) }
    }
}

/// Kontrast (tekst, tło) w OKLab: współczynnik WCAG 2.1 albo |Lc| APCA.
pub fn contrast<T: Scalar>(text_lab: [T; 3], bg_lab: [T; 3], metric: ContrastMetric) -> T {
    match metric {
        ContrastMetric::Wcag21 => wcag21(text_lab, bg_lab),
        ContrastMetric::Apca => apca_signed(text_lab, bg_lab).abs(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::color::convert::oklch_to_oklab;
    use crate::color::testutil::{check_gradients, random_lch};
    use crate::rng::Rng;
    use crate::scalar::Dual;

    type D6 = Dual<6>;

    const WHITE: [f64; 3] = [1.0, 0.0, 0.0];
    const BLACK: [f64; 3] = [0.0, 0.0, 0.0];

    fn pair(rng: &mut Rng) -> [f64; 6] {
        let a = oklch_to_oklab(random_lch(rng));
        let b = oklch_to_oklab(random_lch(rng));
        [a[0], a[1], a[2], b[0], b[1], b[2]]
    }

    fn split<T: Copy>(x: &[T; 6]) -> ([T; 3], [T; 3]) {
        ([x[0], x[1], x[2]], [x[3], x[4], x[5]])
    }

    fn vars(x: &[f64; 6]) -> [D6; 6] {
        std::array::from_fn(|i| D6::var(x[i], i))
    }

    #[test]
    fn black_on_white_has_extreme_contrast() {
        let w: f64 = contrast(BLACK, WHITE, ContrastMetric::Wcag21);
        assert!((w - 21.0).abs() < 1e-6, "{w}");
        assert_eq!(contrast(WHITE, BLACK, ContrastMetric::Wcag21), w);
        // wartości wzorcowe APCA 0.0.98G-4g: czarny na białym 106.04, biały na czarnym −107.88
        let bow: f64 = apca_signed(BLACK, WHITE);
        let wob: f64 = apca_signed(WHITE, BLACK);
        assert!((bow - 106.04067).abs() < 1e-4, "{bow}");
        assert!((wob + 107.88473).abs() < 1e-4, "{wob}");
        assert_eq!(contrast(WHITE, BLACK, ContrastMetric::Apca), -wob);
    }

    #[test]
    fn derivatives_match_finite_differences() {
        for (seed, metric) in [(21, ContrastMetric::Wcag21), (22, ContrastMetric::Apca)] {
            check_gradients(
                &format!("contrast {metric:?}"),
                seed,
                200,
                &pair,
                &|x| {
                    let (t, b) = split(x);
                    contrast(t, b, metric)
                },
                &|x| {
                    let (t, b) = split(&vars(x));
                    contrast(t, b, metric).d
                },
            );
        }
    }

    #[test]
    fn degenerate_colors_give_finite_values_and_derivatives() {
        let grey = [0.5, 0.0, 0.0];
        let vivid = oklch_to_oklab([0.7, 0.1, 30.0]);
        for metric in [ContrastMetric::Wcag21, ContrastMetric::Apca] {
            for (t, b) in [
                (BLACK, BLACK),
                (WHITE, WHITE),
                (BLACK, WHITE),
                (WHITE, BLACK),
                (grey, grey),
                (vivid, vivid),
                (grey, BLACK),
                (vivid, WHITE),
            ] {
                let x = [t[0], t[1], t[2], b[0], b[1], b[2]];
                let (dt, db) = split(&vars(&x));
                let c = contrast(dt, db, metric);
                assert!(c.v.is_finite(), "{metric:?} {t:?}/{b:?}: {c:?}");
                assert!(c.d.iter().all(|d| d.is_finite()), "{metric:?} {t:?}/{b:?}: {c:?}");
            }
        }
    }

    #[test]
    fn contrast_of_a_color_with_itself() {
        let mut rng = Rng::new(23, 0);
        for _ in 0..100 {
            let lab = oklch_to_oklab(random_lch(&mut rng));
            assert_eq!(contrast(lab, lab, ContrastMetric::Wcag21), 1.0);
            assert_eq!(contrast(lab, lab, ContrastMetric::Apca), 0.0);
        }
    }
}
