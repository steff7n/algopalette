//! Minimalizacja z ograniczeniami pudełkowymi: L-BFGS z rzutowaniem na pudełko.
//!
//! Metoda quasi-Newtona o ograniczonej pamięci. W każdym kroku:
//! 1. zmienne przyklejone do granicy, których gradient wypycha na zewnątrz, są zamrażane
//!    (zbiór aktywny); pozostałe są wolne;
//! 2. kierunek to −H·g na zmiennych wolnych (dwupętlowa rekurencja L-BFGS, iloczyny skalarne
//!    tylko po zmiennych wolnych);
//! 3. przeszukiwanie liniowe z nawrotami wzdłuż łuku rzutowanego `P(x + α·d)` z warunkiem
//!    Armijo względem faktycznego przesunięcia;
//! 4. gdy kierunek quasi-Newtona zawodzi (nie jest spadkowy albo rzutowanie go psuje), pamięć
//!    jest czyszczona i krok powtarzany rzutowanym gradientem — to zawsze kierunek spadku.
//!
//! Zmienna bez granic (`-inf`, `+inf`), np. okresowy odcień, nie wymaga niczego szczególnego.
//! Wartość funkcji w zwracanym punkcie nigdy nie jest większa niż w punkcie startowym, a liczba
//! wywołań funkcji nie przekracza `max_evals`. Algorytm jest deterministyczny.

use std::collections::VecDeque;

/// Stała warunku Armijo.
const ARMIJO: f64 = 1e-4;
/// Najwięcej nawrotów w jednym przeszukiwaniu liniowym (krok maleje co najmniej dwukrotnie,
/// więc po 30 nawrotach jest ≤ 1e-9 kroku początkowego — dalsze próby to strata budżetu).
const MAX_BACKTRACKS: usize = 30;
/// Para (s, y) wchodzi do pamięci, gdy `s·y > CURVATURE_EPS · y·y`.
const CURVATURE_EPS: f64 = 1e-10;

/// Parametry minimalizacji.
#[derive(Debug, Clone, PartialEq)]
pub struct Settings {
    /// Największa liczba wywołań funkcji z gradientem.
    pub max_evals: usize,
    /// Liczba pamiętanych par krzywizny.
    pub memory: usize,
    /// Zbieżność: norma maksimum rzutowanego gradientu `‖P(x − g) − x‖∞ ≤ pg_tol`.
    pub pg_tol: f64,
    /// Zbieżność: spadek w kroku `≤ f_tol · max(|f|, |f′|, 1)`.
    pub f_tol: f64,
}

impl Default for Settings {
    fn default() -> Self {
        Self { max_evals: 3000, memory: 10, pg_tol: 1e-9, f_tol: 1e-13 }
    }
}

/// Powód zakończenia.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Stop {
    /// Spełnione kryterium zbieżności.
    Converged,
    /// Wyczerpany budżet wywołań.
    Budget,
    /// Przerwane z zewnątrz (anulowanie, limit czasu).
    Interrupted,
    /// Brak postępu: przeszukiwanie liniowe nie znalazło spadku albo funkcja jest nieskończona.
    Stalled,
}

/// Wynik minimalizacji.
#[derive(Debug, Clone, PartialEq)]
pub struct Minimum {
    pub x: Vec<f64>,
    /// Wartość w `x` (`NaN`, gdy budżet nie pozwolił na żadne wywołanie).
    pub f: f64,
    /// Liczba wykonanych wywołań funkcji.
    pub evals: usize,
    pub stop: Stop,
}

/// Minimalizuje `fg` w pudełku `[lower, upper]`, startując z `x0` (rzutowanego na pudełko).
///
/// `fg(x, grad)` zwraca wartość i zapisuje gradient. `known` to wartość i gradient w `x0`, jeśli
/// są już policzone (oszczędza jedno wywołanie; ignorowane, gdy `x0` leży poza pudełkiem).
/// `interrupted` jest pytane przed każdym wywołaniem funkcji.
pub fn minimize<F, S>(
    mut fg: F,
    lower: &[f64],
    upper: &[f64],
    x0: &[f64],
    known: Option<(f64, &[f64])>,
    settings: &Settings,
    interrupted: S,
) -> Minimum
where
    F: FnMut(&[f64], &mut [f64]) -> f64,
    S: Fn() -> bool,
{
    let n = x0.len();
    debug_assert!(lower.len() == n && upper.len() == n);
    let clamp = |v: f64, i: usize| v.max(lower[i]).min(upper[i]);

    let mut x: Vec<f64> = (0..n).map(|i| clamp(x0[i], i)).collect();
    let mut g = vec![0.0; n];
    let mut evals = 0;

    let mut f = match known {
        Some((f0, g0)) if x == x0 => {
            g.copy_from_slice(g0);
            f0
        }
        _ => {
            if interrupted() {
                return Minimum { x, f: f64::NAN, evals, stop: Stop::Interrupted };
            }
            if settings.max_evals == 0 {
                return Minimum { x, f: f64::NAN, evals, stop: Stop::Budget };
            }
            evals += 1;
            fg(&x, &mut g)
        }
    };
    if !f.is_finite() {
        return Minimum { x, f, evals, stop: Stop::Stalled };
    }

    let mut memory = Memory::new(settings.memory, n);
    let mut free = vec![true; n];
    let mut d = vec![0.0; n];
    let mut x_new = vec![0.0; n];
    let mut g_new = vec![0.0; n];
    // długość ostatniego przyjętego kroku: skala pierwszego kroku po wyczyszczeniu pamięci
    let mut last_move: Option<f64> = None;

    let stop = 'outer: loop {
        let pg = (0..n).fold(0.0, |m: f64, i| m.max((clamp(x[i] - g[i], i) - x[i]).abs()));
        if pg.is_nan() {
            break Stop::Stalled;
        }
        if pg <= settings.pg_tol {
            break Stop::Converged;
        }
        if evals >= settings.max_evals {
            break Stop::Budget;
        }
        for i in 0..n {
            let pinned = (x[i] <= lower[i] && g[i] > 0.0) || (x[i] >= upper[i] && g[i] < 0.0);
            free[i] = !pinned;
        }

        let mut quasi_newton = memory.direction(&g, &free, &mut d);
        loop {
            let slope = dot_free(&g, &d, &free);
            let d_norm = dot_free(&d, &d, &free).sqrt();
            if slope < 0.0 && d_norm.is_finite() {
                let mut step = if quasi_newton {
                    1.0
                } else {
                    // rzutowany gradient: pierwszy ruch długości 1 albo dwukrotności ostatniego
                    last_move.map_or(1.0, |m| (2.0 * m).min(1.0)) / d_norm
                };
                for _ in 0..=MAX_BACKTRACKS {
                    let mut moved: f64 = 0.0;
                    let mut gdx = 0.0;
                    for i in 0..n {
                        x_new[i] = if free[i] { clamp(x[i] + step * d[i], i) } else { x[i] };
                        let dx = x_new[i] - x[i];
                        moved = moved.max(dx.abs());
                        gdx += g[i] * dx;
                    }
                    if moved == 0.0 {
                        break; // krok zniknął w zaokrągleniach albo w rzutowaniu
                    }
                    if evals >= settings.max_evals {
                        break 'outer Stop::Budget;
                    }
                    if interrupted() {
                        break 'outer Stop::Interrupted;
                    }
                    evals += 1;
                    let f_new = fg(&x_new, &mut g_new);
                    if f_new.is_finite() && gdx < 0.0 && f_new <= f + ARMIJO * gdx {
                        // przyjęty: aktualizacja pamięci i przejście do nowego punktu
                        let mut sq = 0.0;
                        for i in 0..n {
                            let dx = x_new[i] - x[i];
                            sq += dx * dx;
                        }
                        memory.push(&x, &x_new, &g, &g_new);
                        last_move = Some(sq.sqrt());
                        let drop = f - f_new;
                        let scale = f.abs().max(f_new.abs()).max(1.0);
                        std::mem::swap(&mut x, &mut x_new);
                        std::mem::swap(&mut g, &mut g_new);
                        f = f_new;
                        if drop <= settings.f_tol * scale {
                            break 'outer Stop::Converged;
                        }
                        continue 'outer;
                    }
                    // nawrót: minimum paraboli przez f(0), f′(0), f(step), w granicach [0.1, 0.5]
                    let shrink = if f_new.is_finite() {
                        let curvature = f_new - f - slope * step;
                        let t = -slope * step / (2.0 * curvature);
                        if t.is_finite() { t.clamp(0.1, 0.5) } else { 0.5 }
                    } else {
                        0.1
                    };
                    step *= shrink;
                }
            }
            // kierunek zawiódł
            if !quasi_newton {
                break 'outer Stop::Stalled;
            }
            memory.clear();
            quasi_newton = memory.direction(&g, &free, &mut d);
        }
    };
    Minimum { x, f, evals, stop }
}

#[inline]
fn dot_free(a: &[f64], b: &[f64], free: &[bool]) -> f64 {
    let mut sum = 0.0;
    for i in 0..a.len() {
        if free[i] {
            sum += a[i] * b[i];
        }
    }
    sum
}

/// Pamięć par krzywizny (s, y) = (Δx, Δg), od najstarszej do najnowszej.
struct Memory {
    capacity: usize,
    pairs: VecDeque<(Vec<f64>, Vec<f64>)>,
    // bufory robocze rekurencji dwupętlowej
    alpha: Vec<f64>,
    rho: Vec<f64>,
    q: Vec<f64>,
}

impl Memory {
    fn new(capacity: usize, n: usize) -> Self {
        Self {
            capacity,
            pairs: VecDeque::with_capacity(capacity),
            alpha: vec![0.0; capacity],
            rho: vec![0.0; capacity],
            q: vec![0.0; n],
        }
    }

    fn clear(&mut self) {
        self.pairs.clear();
    }

    /// Dodaje parę z przejścia `x → x_new`, jeśli ma dodatnią krzywiznę.
    fn push(&mut self, x: &[f64], x_new: &[f64], g: &[f64], g_new: &[f64]) {
        if self.capacity == 0 {
            return;
        }
        let (mut sy, mut yy) = (0.0, 0.0);
        for i in 0..x.len() {
            let (s, y) = (x_new[i] - x[i], g_new[i] - g[i]);
            sy += s * y;
            yy += y * y;
        }
        if !(sy.is_finite() && yy.is_finite() && sy > CURVATURE_EPS * yy) {
            return;
        }
        // najstarsza para oddaje swoje bufory nowej
        let (mut s, mut y) = if self.pairs.len() == self.capacity {
            self.pairs.pop_front().expect("pamięć niepusta")
        } else {
            (vec![0.0; x.len()], vec![0.0; x.len()])
        };
        for i in 0..x.len() {
            s[i] = x_new[i] - x[i];
            y[i] = g_new[i] - g[i];
        }
        self.pairs.push_back((s, y));
    }

    /// Zapisuje do `d` kierunek spadku na zmiennych wolnych (zamrożone dostają 0). Zwraca
    /// `true` dla kierunku quasi-Newtona, `false` dla minus gradientu (brak użytecznych par).
    fn direction(&mut self, g: &[f64], free: &[bool], d: &mut [f64]) -> bool {
        let n = g.len();
        for i in 0..n {
            self.q[i] = if free[i] { g[i] } else { 0.0 };
        }
        // skala początkowa H₀ = γ·I z najnowszej pary o dodatniej krzywiźnie na zmiennych wolnych
        let mut gamma = None;
        for (j, (s, y)) in self.pairs.iter().enumerate().rev() {
            let sy = dot_free(s, y, free);
            let yy = dot_free(y, y, free);
            let useful = sy > CURVATURE_EPS * yy; // fałsz także dla NaN
            if !useful {
                self.rho[j] = 0.0; // para bezużyteczna w tej podprzestrzeni
                continue;
            }
            if gamma.is_none() {
                gamma = Some(sy / yy);
            }
            self.rho[j] = 1.0 / sy;
            self.alpha[j] = self.rho[j] * dot_free(s, &self.q, free);
            for i in 0..n {
                if free[i] {
                    self.q[i] -= self.alpha[j] * y[i];
                }
            }
        }
        let Some(gamma) = gamma else {
            for (di, qi) in d.iter_mut().zip(&self.q) {
                *di = -qi;
            }
            return false;
        };
        for v in self.q.iter_mut() {
            *v *= gamma;
        }
        for (j, (s, y)) in self.pairs.iter().enumerate() {
            if self.rho[j] == 0.0 {
                continue;
            }
            let beta = self.rho[j] * dot_free(y, &self.q, free);
            let k = self.alpha[j] - beta;
            for i in 0..n {
                if free[i] {
                    self.q[i] += k * s[i];
                }
            }
        }
        for (di, qi) in d.iter_mut().zip(&self.q) {
            *di = -qi;
        }
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::Cell;

    const INF: f64 = f64::INFINITY;

    fn never() -> bool {
        false
    }

    fn settings(max_evals: usize) -> Settings {
        Settings { max_evals, ..Settings::default() }
    }

    fn max_diff(a: &[f64], b: &[f64]) -> f64 {
        a.iter().zip(b).fold(0.0, |m, (x, y)| m.max((x - y).abs()))
    }

    /// Σ wᵢ (xᵢ − cᵢ)².
    fn separable(w: &[f64], c: &[f64]) -> impl Fn(&[f64], &mut [f64]) -> f64 {
        move |x, g| {
            let mut f = 0.0;
            for i in 0..x.len() {
                let d = x[i] - c[i];
                f += w[i] * d * d;
                g[i] = 2.0 * w[i] * d;
            }
            f
        }
    }

    /// Łańcuchowa funkcja Rosenbrocka.
    fn rosenbrock(x: &[f64], g: &mut [f64]) -> f64 {
        g.fill(0.0);
        let mut f = 0.0;
        for i in 0..x.len() - 1 {
            let a = x[i + 1] - x[i] * x[i];
            let b = 1.0 - x[i];
            f += 100.0 * a * a + b * b;
            g[i] += -400.0 * a * x[i] - 2.0 * b;
            g[i + 1] += 200.0 * a;
        }
        f
    }

    #[test]
    fn bounded_quadratic_reaches_optimum_on_the_boundary() {
        let w = [1.0, 10.0, 0.1, 5.0, 3.0];
        let c = [-0.5, 0.3, 1.7, 0.9, -2.0];
        let m = minimize(
            separable(&w, &c),
            &[0.0; 5],
            &[1.0; 5],
            &[0.5; 5],
            None,
            &settings(500),
            never,
        );
        assert_eq!(m.stop, Stop::Converged);
        assert!(max_diff(&m.x, &[0.0, 0.3, 1.0, 0.9, 0.0]) <= 1e-6, "{m:?}");
        assert!(m.evals < 60, "za dużo wywołań: {}", m.evals);
    }

    /// Funkcja kwadratowa ze sprzężeniami: ½ xᵀAx − bᵀx, A trójdiagonalna dodatnio określona.
    fn coupled(x: &[f64], g: &mut [f64]) -> f64 {
        let n = x.len();
        let b = [3.0, -2.0, 1.5, 4.0, -1.0, 2.5];
        let mut f = 0.0;
        for i in 0..n {
            let mut ax = (2.0 + i as f64) * x[i];
            if i > 0 {
                ax -= 0.9 * x[i - 1];
            }
            if i + 1 < n {
                ax -= 0.9 * x[i + 1];
            }
            g[i] = ax - b[i];
            f += 0.5 * x[i] * ax - b[i] * x[i];
        }
        f
    }

    #[test]
    fn coupled_bounded_quadratic_matches_projected_gradient_reference() {
        let lower = [0.0, -0.5, 0.0, 0.0, -INF, 0.2];
        let upper = [1.0, 0.5, 0.4, INF, 0.0, 0.3];
        // rozwiązanie wzorcowe: zwykły rzutowany gradient ze stałym krokiem, do zbieżności
        let mut r = [0.0, 0.0, 0.0, 0.0, 0.0, 0.25];
        let mut g = [0.0; 6];
        for _ in 0..20_000 {
            coupled(&r, &mut g);
            for i in 0..6 {
                r[i] = (r[i] - 0.1 * g[i]).max(lower[i]).min(upper[i]);
            }
        }
        let m = minimize(coupled, &lower, &upper, &[0.5; 6], None, &settings(500), never);
        assert_eq!(m.stop, Stop::Converged);
        assert!(max_diff(&m.x, &r) <= 1e-6, "{:?} zamiast {r:?}", m.x);
        // część zmiennych siedzi na granicy, część wewnątrz
        assert_eq!(m.x[0], 1.0);
        assert_eq!(m.x[2], 0.4);
        assert!(m.x[3] > 0.0 && m.x[3] < 5.0);
    }

    #[test]
    fn rosenbrock_10d_converges_within_2000_evals() {
        let x0: Vec<f64> = (0..10).map(|i| if i % 2 == 0 { -1.2 } else { 1.0 }).collect();
        for (lower, upper) in [([-INF; 10], [INF; 10]), ([-5.0; 10], [5.0; 10])] {
            let m = minimize(rosenbrock, &lower, &upper, &x0, None, &settings(2000), never);
            assert!(m.f <= 1e-8, "f = {} po {} wywołaniach ({:?})", m.f, m.evals, m.stop);
            assert!(m.evals <= 2000);
            assert!(max_diff(&m.x, &[1.0; 10]) <= 1e-3, "{:?}", m.x);
        }
    }

    #[test]
    fn rosenbrock_with_active_bound_stops_at_constrained_minimum() {
        // x₀ ≤ 0.5 odcina minimum globalne (1, 1): optimum leży na granicy x₀ = 0.5, x₁ = 0.25
        let m = minimize(
            rosenbrock,
            &[-2.0, -2.0],
            &[0.5, 2.0],
            &[-1.2, 1.0],
            None,
            &settings(500),
            never,
        );
        assert_eq!(m.stop, Stop::Converged);
        assert!(max_diff(&m.x, &[0.5, 0.25]) <= 1e-6, "{m:?}");
    }

    #[test]
    fn periodic_variable_without_bounds_converges_to_nearest_minimum() {
        // x w [0, 1], kąt θ bez granic; minimum co 2π
        let fg = |x: &[f64], g: &mut [f64]| {
            let (dx, dt) = (x[0] - 0.3, x[1] - 2.0);
            g[0] = 2.0 * dx + 0.1 * dt.sin();
            g[1] = dt.sin() + 0.1 * dx * dt.cos();
            dx * dx + 1.0 - dt.cos() + 0.1 * dx * dt.sin()
        };
        for theta0 in [40.0, -17.0, 2.5, 1000.0] {
            let m = minimize(
                fg,
                &[0.0, -INF],
                &[1.0, INF],
                &[0.9, theta0],
                None,
                &settings(300),
                never,
            );
            assert_eq!(m.stop, Stop::Converged, "θ₀ = {theta0}");
            assert!(m.f <= 1e-12, "θ₀ = {theta0}: f = {}", m.f);
            assert!((m.x[0] - 0.3).abs() <= 1e-6);
            assert!(((m.x[1] - 2.0).cos() - 1.0).abs() <= 1e-10);
            assert!(
                (m.x[1] - theta0).abs() < std::f64::consts::PI + 1e-6,
                "θ: {theta0} → {}",
                m.x[1]
            );
        }
    }

    #[test]
    fn never_exceeds_the_evaluation_budget() {
        let x0: Vec<f64> = (0..10).map(|i| if i % 2 == 0 { -1.2 } else { 1.0 }).collect();
        for budget in [0, 1, 2, 3, 7, 20, 60] {
            let calls = Cell::new(0usize);
            let fg = |x: &[f64], g: &mut [f64]| {
                calls.set(calls.get() + 1);
                rosenbrock(x, g)
            };
            let m = minimize(fg, &[-5.0; 10], &[5.0; 10], &x0, None, &settings(budget), never);
            assert_eq!(calls.get(), m.evals, "budżet {budget}");
            assert!(m.evals <= budget, "budżet {budget}: {} wywołań", m.evals);
            assert_eq!(m.stop, Stop::Budget, "budżet {budget}");
            if budget == 0 {
                assert!(m.f.is_nan());
                assert_eq!(m.x, x0);
            } else {
                let mut g = [0.0; 10];
                assert_eq!(m.f, rosenbrock(&m.x, &mut g));
                assert!(m.f <= rosenbrock(&x0, &mut g));
            }
        }
    }

    #[test]
    fn known_start_value_saves_one_evaluation() {
        let x0 = [-1.2, 1.0];
        let mut g0 = [0.0; 2];
        let f0 = rosenbrock(&x0, &mut g0);
        let seen_start = Cell::new(false);
        let fg = |x: &[f64], g: &mut [f64]| {
            if x == x0 {
                seen_start.set(true);
            }
            rosenbrock(x, g)
        };
        let with = minimize(fg, &[-5.0; 2], &[5.0; 2], &x0, Some((f0, &g0)), &settings(500), never);
        assert!(!seen_start.get(), "punkt startowy policzony drugi raz");
        let without = minimize(rosenbrock, &[-5.0; 2], &[5.0; 2], &x0, None, &settings(500), never);
        assert_eq!(with.x, without.x);
        assert_eq!(with.evals + 1, without.evals);
        // budżet 0 ze znaną wartością: zwraca start bez wywołań
        let m =
            minimize(rosenbrock, &[-5.0; 2], &[5.0; 2], &x0, Some((f0, &g0)), &settings(0), never);
        assert_eq!((m.f, m.evals, m.stop), (f0, 0, Stop::Budget));
    }

    #[test]
    fn interruption_stops_before_the_next_evaluation() {
        let calls = Cell::new(0usize);
        let fg = |x: &[f64], g: &mut [f64]| {
            calls.set(calls.get() + 1);
            rosenbrock(x, g)
        };
        let m = minimize(fg, &[-5.0; 2], &[5.0; 2], &[-1.2, 1.0], None, &settings(500), || {
            calls.get() >= 5
        });
        assert_eq!(m.stop, Stop::Interrupted);
        assert_eq!(m.evals, 5);
        let m =
            minimize(rosenbrock, &[-5.0; 2], &[5.0; 2], &[-1.2, 1.0], None, &settings(500), || {
                true
            });
        assert_eq!((m.evals, m.stop), (0, Stop::Interrupted));
    }

    #[test]
    fn start_is_projected_and_fixed_variables_stay_fixed() {
        let w = [1.0, 1.0, 1.0];
        let c = [0.2, 0.9, 0.5];
        let m = minimize(
            separable(&w, &c),
            &[0.0, 0.4, 0.0],
            &[1.0, 0.4, 1.0],
            &[7.0, -3.0, 0.5],
            None,
            &settings(200),
            never,
        );
        assert_eq!(m.stop, Stop::Converged);
        assert_eq!(m.x[1], 0.4);
        assert!(max_diff(&m.x, &[0.2, 0.4, 0.5]) <= 1e-7, "{m:?}");
    }

    #[test]
    fn non_finite_regions_are_backed_out_of() {
        // za x > 2 funkcja jest NaN; minimum w x = 1.9 tuż przed ścianą, start daleko
        let fg = |x: &[f64], g: &mut [f64]| {
            if x[0] > 2.0 {
                g[0] = f64::NAN;
                return f64::NAN;
            }
            g[0] = 2.0 * (x[0] - 1.9);
            (x[0] - 1.9) * (x[0] - 1.9)
        };
        let m = minimize(fg, &[-INF], &[INF], &[-50.0], None, &settings(200), never);
        assert!((m.x[0] - 1.9).abs() <= 1e-6, "{m:?}");
        // start w obszarze NaN: brak postępu, ale bez paniki i bez pętli
        let m = minimize(fg, &[-INF], &[INF], &[3.0], None, &settings(200), never);
        assert_eq!(m.stop, Stop::Stalled);
        assert_eq!(m.x, [3.0]);
    }

    #[test]
    fn stationary_start_converges_immediately() {
        let w = [1.0, 2.0];
        let c = [0.25, 0.75];
        let m = minimize(separable(&w, &c), &[0.0; 2], &[1.0; 2], &c, None, &settings(100), never);
        assert_eq!((m.evals, m.stop, m.f), (1, Stop::Converged, 0.0));
        // punkt na granicy z gradientem wypychającym na zewnątrz też jest stacjonarny
        let c = [-1.0, 2.0];
        let m = minimize(
            separable(&w, &c),
            &[0.0; 2],
            &[1.0; 2],
            &[0.0, 1.0],
            None,
            &settings(100),
            never,
        );
        assert_eq!((m.evals, m.stop), (1, Stop::Converged));
    }

    #[test]
    fn zero_dimensional_problem_is_trivial() {
        let m = minimize(|_: &[f64], _: &mut [f64]| 7.5, &[], &[], &[], None, &settings(10), never);
        assert_eq!((m.x.len(), m.f, m.evals, m.stop), (0, 7.5, 1, Stop::Converged));
    }

    #[test]
    fn result_is_bitwise_reproducible() {
        let x0: Vec<f64> = (0..10).map(|i| if i % 2 == 0 { -1.2 } else { 1.0 }).collect();
        let a = minimize(rosenbrock, &[-5.0; 10], &[5.0; 10], &x0, None, &settings(700), never);
        let b = minimize(rosenbrock, &[-5.0; 10], &[5.0; 10], &x0, None, &settings(700), never);
        assert_eq!(a, b);
        assert!(a.x.iter().zip(&b.x).all(|(p, q)| p.to_bits() == q.to_bits()));
    }
}
