//! Kontrakt funkcji celu widzianej przez optymalizator (plan I5).
//!
//! Optymalizator (`optim`) nie wie nic o kolorach: dostaje wektor zmiennych, granice pudełkowe,
//! wartość z gradientem i sposób mierzenia różnorodności. Prawdziwą funkcję celu palety
//! (`rules::Problem`) buduje kompilacja sesji; testy optymalizatora używają funkcji syntetycznych.

use crate::rng::Rng;

/// Próg, powyżej którego twardy term uznaje się za naruszony.
pub const FEASIBLE_EPS: f64 = 1e-9;

/// Ocena końcowa punktu (bez marginesu twardych zasad).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Score {
    /// `true`, gdy żaden twardy term nie przekracza [`FEASIBLE_EPS`].
    pub feasible: bool,
    /// Wartość funkcji celu bez marginesu.
    pub total: f64,
}

/// Funkcja celu minimalizowana przez sterownik. `Sync`, bo przebiegi fali liczą równolegle.
///
/// Implementacja nie może mieć stanu zmienianego przez wywołania: wynik każdej metody zależy
/// wyłącznie od argumentów (warunek determinizmu niezależnego od liczby wątków).
pub trait Objective: Sync {
    /// Liczba zmiennych.
    fn dim(&self) -> usize;

    /// Granice (dolne, górne), każda długości [`Objective::dim`]. Zmienna okresowa (odcień bez
    /// granic) ma `-inf` i `+inf`.
    fn bounds(&self) -> (&[f64], &[f64]);

    /// Losowy punkt startowy w granicach.
    fn sample(&self, rng: &mut Rng, out: &mut [f64]);

    /// Punkt startowy z bieżących wartości palety.
    fn current(&self, out: &mut [f64]);

    /// Wartość funkcji celu (z marginesem twardych zasad) i jej gradient zapisany do `grad`.
    fn value_grad(&self, x: &[f64], grad: &mut [f64]) -> f64;

    /// Ocena końcowa punktu, bez marginesu.
    fn score(&self, x: &[f64]) -> Score;

    /// Odległość dwóch rozwiązań: średnie ΔE ok odpowiadających sobie kolorów wolnych.
    fn distance(&self, a: &[f64], b: &[f64]) -> f64;

    /// Kara odpychająca od rozwiązań `others` bliższych niż `min_div`. Zwraca wartość kary
    /// i DODAJE jej gradient do `grad` (nie zeruje go).
    fn repulsion(&self, x: &[f64], others: &[Vec<f64>], min_div: f64, grad: &mut [f64]) -> f64;
}
