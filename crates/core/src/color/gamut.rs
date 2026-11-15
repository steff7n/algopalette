//! Gamut sRGB w OKLCH: przynależność i największe nasycenie przy danych (L, H).
//!
//! `max_chroma` odtwarza bisekcję wyroczni (`fast.max_chroma`: przedział [0, 0.5], środek, kolor
//! „w gamucie”, gdy kanały liniowe leżą w [−1e-6, 1 + 1e-6]), tylko doprowadzoną do pełnej
//! precyzji: po 20 krokach bisekcji przedział ma 5e-7, a resztę robi metoda Newtona na kanale,
//! który ogranicza gamut. Pochodne po L i H wynikają z twierdzenia o funkcji niejawnej dla tego
//! kanału: `lin_k(L, C*, H) = próg` ⇒ `dC*/dθ = −(∂lin_k/∂θ) / (∂lin_k/∂C)`.

use crate::scalar::Scalar;

use super::convert::{LMS_TO_LRGB, OKLAB_TO_LMS3, oklab_to_linear_srgb, oklch_to_oklab};

/// Tolerancja przynależności do sRGB (kanały liniowe), jak w wyroczni.
pub const GAMUT_EPS: f64 = 1e-6;

/// Górny koniec przedziału bisekcji (żaden kolor sRGB nie ma większego C).
const C_SEARCH_MAX: f64 = 0.5;
/// Kroki bisekcji przed dokańczaniem metodą Newtona: 0.5 / 2^20 ≈ 4.8e-7.
const BISECT_STEPS: usize = 20;

#[inline]
fn channels_ok(lin: &[f64; 3]) -> bool {
    lin.iter().all(|&v| (-GAMUT_EPS..=1.0 + GAMUT_EPS).contains(&v))
}

/// Czy kolor OKLCH mieści się w sRGB: kanały liniowe w [−1e-6, 1 + 1e-6].
pub fn in_gamut(lch: [f64; 3]) -> bool {
    channels_ok(&oklab_to_linear_srgb(oklch_to_oklab(lch)))
}

/// Półprosta stałych (L, H) w przestrzeni LMS′: `lms′(C) = base + C · step`.
struct Ray {
    base: [f64; 3],
    step: [f64; 3],
}

impl Ray {
    fn new(l: f64, h_deg: f64) -> Self {
        let (sin, cos) = (h_deg * (std::f64::consts::PI / 180.0)).sin_cos();
        let m = &OKLAB_TO_LMS3;
        Self {
            base: std::array::from_fn(|i| l * m[i][0]),
            step: std::array::from_fn(|i| cos * m[i][1] + sin * m[i][2]),
        }
    }

    /// Kanały liniowe sRGB przy nasyceniu `c`.
    #[inline]
    fn lin(&self, c: f64) -> [f64; 3] {
        let q: [f64; 3] = std::array::from_fn(|i| {
            let v = self.base[i] + c * self.step[i];
            v * v * v
        });
        let m = &LMS_TO_LRGB;
        std::array::from_fn(|k| m[k][0] * q[0] + m[k][1] * q[1] + m[k][2] * q[2])
    }

    /// Wartość i pochodna po C kanału `k`.
    #[inline]
    fn channel(&self, c: f64, k: usize) -> (f64, f64) {
        let (mut value, mut slope) = (0.0, 0.0);
        for ((&m, &base), &step) in LMS_TO_LRGB[k].iter().zip(&self.base).zip(&self.step) {
            let v = base + c * step;
            value += m * v * v * v;
            slope += m * 3.0 * v * v * step;
        }
        (value, slope)
    }

    #[inline]
    fn ok(&self, c: f64) -> bool {
        channels_ok(&self.lin(c))
    }

    /// Najmocniej przekroczone ograniczenie w punkcie spoza gamutu: (kanał, próg).
    fn violated(&self, c: f64) -> Option<(usize, f64)> {
        let lin = self.lin(c);
        let mut worst: Option<(usize, f64, f64)> = None;
        for (k, &v) in lin.iter().enumerate() {
            let (bound, excess) = if v < -GAMUT_EPS {
                (-GAMUT_EPS, -GAMUT_EPS - v)
            } else {
                (1.0 + GAMUT_EPS, v - 1.0 - GAMUT_EPS)
            };
            if excess > 0.0 && worst.is_none_or(|w| excess > w.2) {
                worst = Some((k, bound, excess));
            }
        }
        worst.map(|(k, bound, _)| (k, bound))
    }
}

/// Brzeg gamutu: największe C oraz ograniczenie, które go wyznacza (kanał, próg). `None`, gdy
/// brzegu nie ma w przedziale (L poza [0, 1] albo C nieograniczone do 0.5) — pochodna jest
/// wtedy zerowa.
fn boundary(ray: &Ray) -> (f64, Option<(usize, f64)>) {
    let (mut lo, mut hi) = (0.0, C_SEARCH_MAX);
    for _ in 0..BISECT_STEPS {
        let mid = (lo + hi) / 2.0;
        if ray.ok(mid) {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    if hi == C_SEARCH_MAX {
        return (finish_bisection(ray, lo, hi).0, None);
    }
    // Newton na ograniczeniu przekroczonym w `hi`; start po stronie spoza gamutu.
    if let Some((k, bound)) = ray.violated(hi) {
        let mut c = hi;
        let mut converged = false;
        for _ in 0..8 {
            let (value, slope) = ray.channel(c, k);
            if slope == 0.0 {
                break;
            }
            let next = c - (value - bound) / slope;
            if !(lo..=hi).contains(&next) {
                break;
            }
            let moved = (next - c).abs();
            c = next;
            if moved <= 4.0 * f64::EPSILON * c.abs() {
                converged = true;
                break;
            }
        }
        // Pierwiastek jest brzegiem tylko wtedy, gdy tuż pod nim kolor jest w gamucie (inne
        // ograniczenie mogło zadziałać wcześniej wewnątrz przedziału).
        if converged && c > 0.0 && ray.ok(c * (1.0 - 1e-12)) {
            return (c, Some((k, bound)));
        }
    }
    let (c, top) = finish_bisection(ray, lo, hi);
    if c == 0.0 {
        return (0.0, None);
    }
    (c, ray.violated(top))
}

/// Bisekcja do wyczerpania precyzji; zwraca (dolny koniec, górny koniec).
fn finish_bisection(ray: &Ray, mut lo: f64, mut hi: f64) -> (f64, f64) {
    loop {
        let mid = (lo + hi) / 2.0;
        if mid <= lo || mid >= hi {
            return (lo, hi);
        }
        if ray.ok(mid) {
            lo = mid;
        } else {
            hi = mid;
        }
    }
}

/// Największe C w sRGB przy jasności `l` i odcieniu `h` (stopnie).
///
/// Wartość: brzeg zbioru kolorów „w gamucie” (z tolerancją [`GAMUT_EPS`]) na półprostej C ≥ 0.
/// Pochodne po `l` i `h`: z funkcji niejawnej na kanale ograniczającym. W punkcie, w którym
/// kanał ograniczający się zmienia, pochodna jest jednostronna (załamanie).
pub fn max_chroma<T: Scalar>(l: T, h: T) -> T {
    let ray = Ray::new(l.val(), h.val());
    let (c, limit) = boundary(&ray);
    let Some((k, _)) = limit else {
        return T::c(c);
    };
    let slope = ray.channel(c, k).1;
    if slope == 0.0 || !slope.is_finite() {
        return T::c(c);
    }
    // F(l, h) = lin_k(l, C*, h) przy stałym C*; jego pochodne to ∂lin_k/∂θ.
    let f = oklab_to_linear_srgb(oklch_to_oklab([l, T::c(c), h]))[k];
    T::c(c) - (f - T::c(f.val())).scale(1.0 / slope)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::color::testutil::check_gradients;
    use crate::rng::Rng;
    use crate::scalar::Dual;

    type D2 = Dual<2>;

    #[test]
    fn in_gamut_uses_linear_channel_tolerance() {
        assert!(in_gamut([0.0, 0.0, 0.0]));
        assert!(in_gamut([1.0, 0.0, 0.0]));
        assert!(in_gamut([0.7, 0.1, 30.0]));
        assert!(!in_gamut([0.7, 0.3, 30.0]));
        assert!(!in_gamut([1.01, 0.0, 0.0]));
        assert!(!in_gamut([f64::NAN, 0.0, 0.0]));
    }

    /// Wartości wyroczni: `fast.max_chroma(l, h, tol=1e-14)`.
    #[test]
    fn max_chroma_matches_oracle_values() {
        for (l, h, want) in [
            (0.7, 30.0, 0.19151256341891099),
            (0.0, 30.0, 0.011573504561461334),
            (1.0, 30.0, 1.602464223537936e-07),
            (0.5, 264.0, 0.28102871164509224),
            (1.2, 264.0, 0.0),
            (-0.2, 264.0, 0.0),
        ] {
            let got: f64 = max_chroma(l, h);
            assert!((got - want).abs() <= 1e-12, "max_chroma({l}, {h}) = {got}, wzorzec {want}");
        }
    }

    #[test]
    fn max_chroma_is_the_boundary_of_the_gamut() {
        let mut rng = Rng::new(11, 0);
        for _ in 0..2000 {
            let (l, h) = (rng.range(0.0, 1.0), rng.range(0.0, 360.0));
            let c: f64 = max_chroma(l, h);
            assert!(c > 0.0 && c < 0.4, "max_chroma({l}, {h}) = {c}");
            assert!(in_gamut([l, c * (1.0 - 1e-9), h]), "({l}, {h}): {c} poza gamutem");
            assert!(!in_gamut([l, c + 1e-9, h]), "({l}, {h}): {c} to nie brzeg");
        }
    }

    #[test]
    fn dual_value_equals_f64_value() {
        let mut rng = Rng::new(12, 0);
        for _ in 0..200 {
            let (l, h) = (rng.range(0.0, 1.0), rng.range(0.0, 360.0));
            let plain: f64 = max_chroma(l, h);
            let dual = max_chroma(D2::var(l, 0), D2::var(h, 1));
            assert_eq!(dual.v, plain);
        }
    }

    #[test]
    fn derivatives_match_finite_differences() {
        check_gradients(
            "max_chroma",
            13,
            200,
            &|rng| [rng.range(0.05, 0.95), rng.range(0.0, 360.0)],
            &|x| max_chroma(x[0], x[1]),
            &|x| max_chroma(D2::var(x[0], 0), D2::var(x[1], 1)).d,
        );
    }

    #[test]
    fn degenerate_inputs_have_finite_derivatives() {
        for (l, h) in
            [(0.0, 0.0), (0.0, 123.0), (1.0, 0.0), (1.0, 300.0), (1.5, 10.0), (-0.5, 10.0)]
        {
            let c = max_chroma(D2::var(l, 0), D2::var(h, 1));
            assert!(c.v.is_finite() && c.v >= 0.0, "({l}, {h}): {c:?}");
            assert!(c.d.iter().all(|d| d.is_finite()), "({l}, {h}): {c:?}");
        }
    }
}
