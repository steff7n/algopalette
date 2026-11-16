//! Kontrakt funkcji celu widzianej przez optymalizator (plan I5).
//!
//! Optymalizator (`optim`) nie wie nic o kolorach: dostaje wektor zmiennych, granice pudełkowe,
//! wartość z gradientem i sposób mierzenia różnorodności. Prawdziwą funkcję celu palety
//! (`rules::Problem`) buduje kompilacja sesji; testy optymalizatora używają funkcji syntetycznych.

use std::sync::Arc;

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
    /// i DODAJE jej gradient do `grad` (nie zeruje go). `others` to wyniki
    /// [`Objective::prepare`] (domyślnie: same punkty).
    fn repulsion(&self, x: &[f64], others: &[Vec<f64>], min_div: f64, grad: &mut [f64]) -> f64;

    // -- dodatki ponad I5 --

    /// Czy funkcja ma wariant doszlifowujący: tę samą funkcję celu z ciaśniejszym marginesem
    /// twardych zasad (i sztywniejszą karą), którym sterownik na końcu zbliża rozwiązanie do
    /// granicy twardych zasad. Wybiera go `polish = true` w [`Objective::penalized_grad`].
    fn has_polish(&self) -> bool {
        false
    }

    /// To, co minimalizuje przebieg: [`Objective::value_grad`] plus [`Objective::repulsion`]
    /// od `others` (wyniki [`Objective::prepare`]; puste = bez kary). Zeruje `grad`.
    /// Implementacja może nadpisać tę metodę, żeby policzyć oba składniki za jednym razem.
    fn penalized_grad(
        &self,
        x: &[f64],
        others: &[Vec<f64>],
        min_div: f64,
        _polish: bool,
        grad: &mut [f64],
    ) -> f64 {
        let value = self.value_grad(x, grad);
        if others.is_empty() { value } else { value + self.repulsion(x, others, min_div, grad) }
    }

    /// Postać rozwiązania, w której mierzy się różnorodność (np. kolory wolne w OKLab).
    /// Sterownik liczy ją raz na kandydata i podaje do [`Objective::distance_prepared`] oraz
    /// jako `others` do [`Objective::repulsion`]. Domyślnie: sam punkt.
    fn prepare(&self, x: &[f64]) -> Vec<f64> {
        x.to_vec()
    }

    /// Odległość dwóch rozwiązań w postaci z [`Objective::prepare`]; ta sama liczba co
    /// [`Objective::distance`] punktów wyjściowych.
    fn distance_prepared(&self, a: &[f64], b: &[f64]) -> f64 {
        self.distance(a, b)
    }
}

/// Funkcja celu za `Arc`: zadanie w tle bierze funkcję na własność, a wywołujący zachowuje
/// swój uchwyt (np. do odkodowania wyniku).
impl<T: Objective + Send + ?Sized> Objective for Arc<T> {
    fn dim(&self) -> usize {
        (**self).dim()
    }

    fn bounds(&self) -> (&[f64], &[f64]) {
        (**self).bounds()
    }

    fn sample(&self, rng: &mut Rng, out: &mut [f64]) {
        (**self).sample(rng, out);
    }

    fn current(&self, out: &mut [f64]) {
        (**self).current(out);
    }

    fn value_grad(&self, x: &[f64], grad: &mut [f64]) -> f64 {
        (**self).value_grad(x, grad)
    }

    fn score(&self, x: &[f64]) -> Score {
        (**self).score(x)
    }

    fn distance(&self, a: &[f64], b: &[f64]) -> f64 {
        (**self).distance(a, b)
    }

    fn repulsion(&self, x: &[f64], others: &[Vec<f64>], min_div: f64, grad: &mut [f64]) -> f64 {
        (**self).repulsion(x, others, min_div, grad)
    }

    fn has_polish(&self) -> bool {
        (**self).has_polish()
    }

    fn penalized_grad(
        &self,
        x: &[f64],
        others: &[Vec<f64>],
        min_div: f64,
        polish: bool,
        grad: &mut [f64],
    ) -> f64 {
        (**self).penalized_grad(x, others, min_div, polish, grad)
    }

    fn prepare(&self, x: &[f64]) -> Vec<f64> {
        (**self).prepare(x)
    }

    fn distance_prepared(&self, a: &[f64], b: &[f64]) -> f64 {
        (**self).distance_prepared(a, b)
    }
}
