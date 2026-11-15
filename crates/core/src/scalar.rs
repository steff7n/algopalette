//! Typ skalarny matematyki koloru: `f64` (sama wartość) albo [`Dual`] (wartość + pochodne).
//!
//! Funkcje koloru są generyczne po [`Scalar`], więc ta sama implementacja liczy wartość i —
//! przez liczby dualne — dokładny gradient (różniczkowanie automatyczne w przód). W gorącej
//! pętli optymalizatora nie ma różnic skończonych.
//!
//! Konwencje w punktach nieróżniczkowalnych (pochodna ma być skończona, Review Focus 2):
//! `sqrt(0)`, `cbrt(0)`, `powf(0, p < 1)`, `abs(0)`, `hypot(0, 0)` i `atan2(0, 0)` mają pochodną 0.
//! Dzięki temu ΔE dwóch identycznych kolorów ma gradient zerowy, a nie NaN.

use std::array;
use std::cmp::Ordering;
use std::ops::{Add, Div, Mul, Neg, Sub};

/// Skalar, po którym generyczne są funkcje koloru (plan I5).
pub trait Scalar:
    Copy
    + PartialOrd
    + Add<Output = Self>
    + Sub<Output = Self>
    + Mul<Output = Self>
    + Div<Output = Self>
    + Neg<Output = Self>
{
    /// Stała (pochodne zerowe).
    fn c(v: f64) -> Self;
    /// Wartość bez pochodnych.
    fn val(self) -> f64;
    fn sqrt(self) -> Self;
    fn cbrt(self) -> Self;
    fn powf(self, p: f64) -> Self;
    fn exp(self) -> Self;
    fn ln(self) -> Self;
    fn sin(self) -> Self;
    fn cos(self) -> Self;
    /// `atan2(self, x)`: kąt punktu (x, self) w radianach.
    fn atan2(self, x: Self) -> Self;
    fn abs(self) -> Self;
    fn hypot(self, o: Self) -> Self;

    // -- dodatki ponad I5: działania ze stałą `f64` bez budowania skalara ze stałej --

    /// `self · k`.
    fn scale(self, k: f64) -> Self {
        self * Self::c(k)
    }

    /// `self + k`.
    fn offset(self, k: f64) -> Self {
        self + Self::c(k)
    }

    /// `max(self, k)`; po stronie obciętej wynik jest stałą.
    fn maxf(self, k: f64) -> Self {
        if self.val() < k { Self::c(k) } else { self }
    }

    /// `min(self, k)`; po stronie obciętej wynik jest stałą.
    fn minf(self, k: f64) -> Self {
        if self.val() > k { Self::c(k) } else { self }
    }

    /// Potęga zachowująca znak: `sign(self) · |self|^p`.
    fn spow(self, p: f64) -> Self {
        if self.val() < 0.0 { -(-self).powf(p) } else { self.powf(p) }
    }

    /// `self²`.
    fn square(self) -> Self {
        self * self
    }

    /// `self³`.
    fn cube(self) -> Self {
        self * self * self
    }
}

impl Scalar for f64 {
    #[inline]
    fn c(v: f64) -> Self {
        v
    }
    #[inline]
    fn val(self) -> f64 {
        self
    }
    #[inline]
    fn sqrt(self) -> Self {
        f64::sqrt(self)
    }
    #[inline]
    fn cbrt(self) -> Self {
        f64::cbrt(self)
    }
    #[inline]
    fn powf(self, p: f64) -> Self {
        f64::powf(self, p)
    }
    #[inline]
    fn exp(self) -> Self {
        f64::exp(self)
    }
    #[inline]
    fn ln(self) -> Self {
        f64::ln(self)
    }
    #[inline]
    fn sin(self) -> Self {
        f64::sin(self)
    }
    #[inline]
    fn cos(self) -> Self {
        f64::cos(self)
    }
    #[inline]
    fn atan2(self, x: Self) -> Self {
        f64::atan2(self, x)
    }
    #[inline]
    fn abs(self) -> Self {
        f64::abs(self)
    }
    #[inline]
    fn hypot(self, o: Self) -> Self {
        f64::hypot(self, o)
    }
    #[inline]
    fn scale(self, k: f64) -> Self {
        self * k
    }
    #[inline]
    fn offset(self, k: f64) -> Self {
        self + k
    }
}

/// Liczba dualna: wartość `v` i pochodne `d` po `N` zmiennych niezależnych.
#[derive(Debug, Clone, Copy)]
pub struct Dual<const N: usize> {
    pub v: f64,
    pub d: [f64; N],
}

impl<const N: usize> Dual<N> {
    /// Stała.
    #[inline]
    pub fn constant(v: f64) -> Self {
        Self { v, d: [0.0; N] }
    }

    /// Zmienna niezależna nr `i` o wartości `v` (pochodna po sobie = 1).
    #[inline]
    pub fn var(v: f64, i: usize) -> Self {
        let mut d = [0.0; N];
        d[i] = 1.0;
        Self { v, d }
    }

    /// Reguła łańcuchowa dla funkcji jednej zmiennej: wartość `value`, pochodna `deriv`.
    #[inline]
    fn chain(self, value: f64, deriv: f64) -> Self {
        Self { v: value, d: self.d.map(|x| x * deriv) }
    }
}

/// Porównania patrzą wyłącznie na wartość (gałęzie funkcji kawałkami gładkich).
impl<const N: usize> PartialEq for Dual<N> {
    #[inline]
    fn eq(&self, other: &Self) -> bool {
        self.v == other.v
    }
}

impl<const N: usize> PartialOrd for Dual<N> {
    #[inline]
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        self.v.partial_cmp(&other.v)
    }
}

impl<const N: usize> Add for Dual<N> {
    type Output = Self;
    #[inline]
    fn add(self, o: Self) -> Self {
        Self { v: self.v + o.v, d: array::from_fn(|i| self.d[i] + o.d[i]) }
    }
}

impl<const N: usize> Sub for Dual<N> {
    type Output = Self;
    #[inline]
    fn sub(self, o: Self) -> Self {
        Self { v: self.v - o.v, d: array::from_fn(|i| self.d[i] - o.d[i]) }
    }
}

impl<const N: usize> Mul for Dual<N> {
    type Output = Self;
    // reguła iloczynu: (uv)′ = u′v + uv′
    #[allow(clippy::suspicious_arithmetic_impl)]
    #[inline]
    fn mul(self, o: Self) -> Self {
        Self { v: self.v * o.v, d: array::from_fn(|i| self.d[i] * o.v + self.v * o.d[i]) }
    }
}

impl<const N: usize> Div for Dual<N> {
    type Output = Self;
    // reguła ilorazu: (u/v)′ = (u′ − (u/v)·v′) / v
    #[allow(clippy::suspicious_arithmetic_impl)]
    #[inline]
    fn div(self, o: Self) -> Self {
        let inv = 1.0 / o.v;
        let q = self.v * inv;
        Self { v: q, d: array::from_fn(|i| (self.d[i] - q * o.d[i]) * inv) }
    }
}

impl<const N: usize> Neg for Dual<N> {
    type Output = Self;
    #[inline]
    fn neg(self) -> Self {
        Self { v: -self.v, d: self.d.map(|x| -x) }
    }
}

impl<const N: usize> Scalar for Dual<N> {
    #[inline]
    fn c(v: f64) -> Self {
        Self::constant(v)
    }

    #[inline]
    fn val(self) -> f64 {
        self.v
    }

    #[inline]
    fn sqrt(self) -> Self {
        let r = self.v.sqrt();
        self.chain(r, if self.v == 0.0 { 0.0 } else { 0.5 / r })
    }

    #[inline]
    fn cbrt(self) -> Self {
        let r = self.v.cbrt();
        self.chain(r, if self.v == 0.0 { 0.0 } else { 1.0 / (3.0 * r * r) })
    }

    #[inline]
    fn powf(self, p: f64) -> Self {
        let deriv = if self.v == 0.0 {
            // p·0^(p−1): 1 dla p = 1, 0 dla p > 1; dla p < 1 nieskończoność zastąpiona zerem
            if p == 1.0 { 1.0 } else { 0.0 }
        } else {
            p * self.v.powf(p - 1.0)
        };
        self.chain(self.v.powf(p), deriv)
    }

    #[inline]
    fn exp(self) -> Self {
        let e = self.v.exp();
        self.chain(e, e)
    }

    #[inline]
    fn ln(self) -> Self {
        self.chain(self.v.ln(), 1.0 / self.v)
    }

    #[inline]
    fn sin(self) -> Self {
        let (s, c) = self.v.sin_cos();
        self.chain(s, c)
    }

    #[inline]
    fn cos(self) -> Self {
        let (s, c) = self.v.sin_cos();
        self.chain(c, -s)
    }

    #[inline]
    fn atan2(self, x: Self) -> Self {
        let r2 = self.v * self.v + x.v * x.v;
        let v = self.v.atan2(x.v);
        if r2 == 0.0 {
            return Self::constant(v);
        }
        let (dy, dx) = (x.v / r2, -self.v / r2);
        Self { v, d: array::from_fn(|i| self.d[i] * dy + x.d[i] * dx) }
    }

    #[inline]
    fn abs(self) -> Self {
        if self.v > 0.0 {
            self
        } else if self.v < 0.0 {
            -self
        } else {
            Self::constant(self.v.abs())
        }
    }

    #[inline]
    fn hypot(self, o: Self) -> Self {
        let h = self.v.hypot(o.v);
        if h == 0.0 {
            return Self::constant(0.0);
        }
        let (da, db) = (self.v / h, o.v / h);
        Self { v: h, d: array::from_fn(|i| self.d[i] * da + o.d[i] * db) }
    }

    #[inline]
    fn scale(self, k: f64) -> Self {
        Self { v: self.v * k, d: self.d.map(|x| x * k) }
    }

    #[inline]
    fn offset(self, k: f64) -> Self {
        Self { v: self.v + k, d: self.d }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    type D1 = Dual<1>;
    type D2 = Dual<2>;

    /// Pochodna funkcji jednej zmiennej różnicą centralną 4. rzędu.
    fn fd(f: impl Fn(f64) -> f64, x: f64) -> f64 {
        let h = 1e-4 * x.abs().max(1.0);
        (f(x - 2.0 * h) - 8.0 * f(x - h) + 8.0 * f(x + h) - f(x + 2.0 * h)) / (12.0 * h)
    }

    fn assert_close(got: f64, want: f64, what: &str) {
        let tol = 1e-9 * want.abs().max(1.0);
        assert!((got - want).abs() <= tol, "{what}: {got} zamiast {want}");
    }

    /// Sprawdza wartość i pochodną funkcji generycznej `f` w punkcie `x`.
    fn check_unary(name: &str, x: f64, f64_f: impl Fn(f64) -> f64, dual_f: impl Fn(D1) -> D1) {
        let got = dual_f(D1::var(x, 0));
        assert_close(got.v, f64_f(x), &format!("{name}({x}) wartość"));
        assert_close(got.d[0], fd(&f64_f, x), &format!("{name}({x}) pochodna"));
    }

    #[test]
    fn arithmetic_follows_calculus_rules() {
        let x = D2::var(3.0, 0);
        let y = D2::var(-2.0, 1);
        let s = x + y;
        assert_eq!((s.v, s.d), (1.0, [1.0, 1.0]));
        let s = x - y;
        assert_eq!((s.v, s.d), (5.0, [1.0, -1.0]));
        let p = x * y;
        assert_eq!((p.v, p.d), (-6.0, [-2.0, 3.0]));
        let q = x / y;
        assert_eq!((q.v, q.d), (-1.5, [-0.5, -0.75]));
        let n = -x;
        assert_eq!((n.v, n.d), (-3.0, [-1.0, 0.0]));
        let k = D2::c(7.0);
        assert_eq!((k.v, k.d), (7.0, [0.0, 0.0]));
        assert_eq!(x.scale(2.0).d, [2.0, 0.0]);
        assert_eq!(x.offset(2.0).v, 5.0);
        assert_eq!(x.offset(2.0).d, [1.0, 0.0]);
        assert_eq!(x.square().d, [6.0, 0.0]);
        assert_eq!(x.cube().d, [27.0, 0.0]);
    }

    #[test]
    fn unary_functions_match_finite_differences() {
        for x in [0.3, 1.0, 2.7, 15.0] {
            check_unary("sqrt", x, f64::sqrt, Scalar::sqrt);
            check_unary("ln", x, f64::ln, Scalar::ln);
            check_unary("powf 0.42", x, |v| v.powf(0.42), |v| v.powf(0.42));
            check_unary("powf 2.4", x, |v| v.powf(2.4), |v| v.powf(2.4));
        }
        for x in [-4.0, -0.3, 0.3, 1.0, 2.7] {
            check_unary("cbrt", x, f64::cbrt, Scalar::cbrt);
            check_unary("exp", x, f64::exp, Scalar::exp);
            check_unary("sin", x, f64::sin, Scalar::sin);
            check_unary("cos", x, f64::cos, Scalar::cos);
            check_unary("abs", x, f64::abs, Scalar::abs);
            check_unary("spow 0.9", x, |v| v.abs().powf(0.9).copysign(v), |v| v.spow(0.9));
            check_unary("square", x, |v| v * v, Scalar::square);
            check_unary("cube", x, |v| v * v * v, Scalar::cube);
            check_unary("scale", x, |v| v * -3.5, |v| v.scale(-3.5));
            check_unary("maxf", x, |v| v.max(0.1), |v| v.maxf(0.1));
            check_unary("minf", x, |v| v.min(0.1), |v| v.minf(0.1));
        }
    }

    #[test]
    fn binary_functions_match_finite_differences() {
        for (a, b) in [(0.4, 1.3), (-2.0, 0.5), (3.0, -1.5), (-0.7, -0.2)] {
            let (x, y) = (D2::var(a, 0), D2::var(b, 1));
            let at = x.atan2(y);
            assert_close(at.v, a.atan2(b), "atan2 wartość");
            assert_close(at.d[0], fd(|v| v.atan2(b), a), "atan2 po y");
            assert_close(at.d[1], fd(|v| a.atan2(v), b), "atan2 po x");
            let hy = x.hypot(y);
            assert_close(hy.v, a.hypot(b), "hypot wartość");
            assert_close(hy.d[0], fd(|v| v.hypot(b), a), "hypot po a");
            assert_close(hy.d[1], fd(|v| a.hypot(v), b), "hypot po b");
            let q = x / y;
            assert_close(q.d[0], fd(|v| v / b, a), "iloraz po liczniku");
            assert_close(q.d[1], fd(|v| a / v, b), "iloraz po mianowniku");
        }
    }

    #[test]
    fn derivatives_are_finite_at_singular_points() {
        let zero = D1::var(0.0, 0);
        for (name, got) in [
            ("sqrt", zero.sqrt()),
            ("cbrt", zero.cbrt()),
            ("powf 0.42", zero.powf(0.42)),
            ("powf 2.4", zero.powf(2.4)),
            ("spow 0.9", zero.spow(0.9)),
            ("abs", zero.abs()),
            ("hypot", zero.hypot(zero)),
            ("atan2", zero.atan2(zero)),
        ] {
            assert_eq!(got.v, 0.0, "{name}");
            assert_eq!(got.d, [0.0], "{name}");
        }
        assert_eq!(zero.powf(1.0).d, [1.0]);
    }

    #[test]
    fn comparisons_look_at_values_only() {
        let a = D1 { v: 1.0, d: [5.0] };
        let b = D1 { v: 1.0, d: [-5.0] };
        let c = D1 { v: 2.0, d: [0.0] };
        assert!(a == b);
        assert!(a < c && c > b);
        assert_eq!(a.maxf(1.5).d, [0.0]);
        assert_eq!(a.maxf(0.5).d, [5.0]);
        assert_eq!(a.minf(0.5).d, [0.0]);
    }

    #[test]
    fn f64_is_a_scalar_with_plain_math() {
        fn poly<T: Scalar>(x: T) -> T {
            (x.square().scale(3.0) + x.sqrt()).offset(-1.0)
        }
        assert_eq!(poly(4.0_f64), 49.0);
        let d = poly(D1::var(4.0, 0));
        assert_eq!((d.v, d.d), (49.0, [24.25]));
        assert_eq!(<f64 as Scalar>::c(2.5), 2.5);
        assert_eq!((-8.0_f64).spow(1.0 / 3.0), -2.0);
    }
}
