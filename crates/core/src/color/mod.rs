//! Matematyka koloru silnika: przekształcenia, gamut, kontrast, ΔE, symulacja CVD (plan I5).
//!
//! Wszystkie funkcje publiczne są generyczne po [`Scalar`](crate::scalar::Scalar): z `f64` liczą
//! wartość, z [`Dual`](crate::scalar::Dual) — wartość i dokładne pochodne. Funkcje kontrastu, ΔE
//! i CVD przyjmują OKLab (konwersja z OKLCH raz na kolor, [`oklch_to_oklab`]).
//!
//! Wyrocznią zgodności jest kod Pythona (`algopalette.color` = coloraide, `algopalette.color.fast`
//! = numpy); stałe są przepisane stamtąd z pełną precyzją. Test: `tests/test_engine_color.py`.

pub mod contrast;
pub mod convert;
pub mod cvd;
pub mod delta_e;
pub mod gamut;

pub use crate::schema::{ContrastMetric, CvdKind, CvdMethod, DeltaE};
pub use contrast::{apca_signed, contrast, wcag21};
pub use convert::{
    linear_srgb_to_oklab, oklab_to_linear_srgb, oklab_to_oklch, oklab_to_xyz, oklch_to_oklab,
};
pub use cvd::simulate_cvd;
pub use delta_e::{delta_e, delta_e_prepared, prepare};
pub use gamut::{Boundary, GAMUT_EPS, boundary, in_gamut, max_chroma};

/// Wspólne narzędzia testów koloru: losowe kolory i sprawdzanie pochodnych.
#[cfg(test)]
pub(crate) mod testutil {
    use crate::rng::Rng;

    use super::gamut::max_chroma;

    /// Losowy kolor OKLCH wewnątrz gamutu sRGB, z dala od czerni, bieli, szarości i brzegu.
    pub fn random_lch(rng: &mut Rng) -> [f64; 3] {
        let l = rng.range(0.1, 0.95);
        let h = rng.range(0.0, 360.0);
        let c = rng.range(0.1, 0.9) * max_chroma(l, h);
        [l, c, h]
    }

    /// Gradient różnicą centralną 4. rzędu z krokiem `h`.
    pub fn fd_grad<const M: usize>(f: &dyn Fn(&[f64; M]) -> f64, x: &[f64; M], h: f64) -> [f64; M] {
        std::array::from_fn(|i| {
            let at = |k: f64| {
                let mut p = *x;
                p[i] += k * h;
                f(&p)
            };
            (at(-2.0) - 8.0 * at(-1.0) + 8.0 * at(1.0) - at(2.0)) / (12.0 * h)
        })
    }

    fn max_abs<const M: usize>(v: &[f64; M]) -> f64 {
        v.iter().fold(0.0, |m, x| m.max(x.abs()))
    }

    /// Błąd względny gradientu `dual` wobec różnicy centralnej albo `None`, gdy punkt leży przy
    /// załamaniu funkcji (różnice z dwoma krokami nie zgadzają się ze sobą — ocena niezależna
    /// od sprawdzanej implementacji pochodnych).
    pub fn grad_error<const M: usize>(
        f: &dyn Fn(&[f64; M]) -> f64,
        x: &[f64; M],
        dual: &[f64; M],
    ) -> Option<f64> {
        let coarse = fd_grad(f, x, 2e-4);
        let fine = fd_grad(f, x, 1e-4);
        let scale = max_abs(&fine).max(1e-9);
        let spread: [f64; M] = std::array::from_fn(|i| coarse[i] - fine[i]);
        if max_abs(&spread) > 1e-7 * scale {
            return None;
        }
        let diff: [f64; M] = std::array::from_fn(|i| dual[i] - fine[i]);
        Some(max_abs(&diff) / scale)
    }

    /// Sprawdza pochodne w `want` losowych punktach gładkich: `sample` losuje punkt, `f` liczy
    /// wartość, `dual` gradient z liczb dualnych. Błąd względny ma być ≤ 1e-5.
    pub fn check_gradients<const M: usize>(
        name: &str,
        seed: u64,
        want: usize,
        sample: &dyn Fn(&mut Rng) -> [f64; M],
        f: &dyn Fn(&[f64; M]) -> f64,
        dual: &dyn Fn(&[f64; M]) -> [f64; M],
    ) {
        let mut rng = Rng::new(seed, 0);
        let (mut checked, mut tried) = (0, 0);
        while checked < want {
            tried += 1;
            assert!(tried <= 20 * want, "{name}: za mało punktów gładkich ({checked}/{tried})");
            let x = sample(&mut rng);
            let g = dual(&x);
            assert!(g.iter().all(|v| v.is_finite()), "{name}: pochodna nieskończona w {x:?}");
            if let Some(err) = grad_error(f, &x, &g) {
                assert!(err <= 1e-5, "{name}: błąd pochodnej {err:.3e} w {x:?}: {g:?}");
                checked += 1;
            }
        }
    }
}
