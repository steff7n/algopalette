//! Optymalizacja: lokalna minimalizacja, wybór różnorodnych rozwiązań, sterownik równoległy
//! i zadanie w tle (plan I5).
//!
//! - [`lbfgsb`] — minimalizacja jednej funkcji w pudełku;
//! - [`select`] — porządek wyniku i zachłanny wybór różnorodnych kandydatów;
//! - [`driver`] — fale niezależnych przebiegów na wielu wątkach, deterministycznie;
//! - [`job`] — to samo jako zadanie w tle z postępem i przerwaniem.

use std::sync::atomic::{AtomicBool, AtomicU64, AtomicUsize, Ordering};
use std::time::Duration;

use crate::objective::Score;

pub mod driver;
pub mod job;
pub mod lbfgsb;
pub mod select;

pub use driver::generate;
pub use job::{Job, JobError, JobResult, JobState, JobStatus};

/// Parametry generowania.
#[derive(Debug, Clone, PartialEq)]
pub struct DriverOpts {
    /// Liczba rozwiązań do zwrócenia.
    pub n: usize,
    /// Ziarno; przebieg `r` używa strumienia `Rng::new(seed, r)`.
    pub seed: u64,
    /// Największa liczba wywołań `value_grad` w jednym przebiegu (z oceną puli startów).
    pub budget: usize,
    /// Limit czasu całego generowania (bezpiecznik).
    pub time_cap: Duration,
    /// Najmniejsza odległość (`Objective::distance`) między rozwiązaniami uznanymi za różne.
    pub min_diversity: f64,
    /// Liczba wątków; 0 = tyle, ile ma maszyna.
    pub threads: usize,
}

/// Część paska postępu na fale po pierwszej (ich wielkości nie znamy z góry).
pub const LATER_WAVES_SHARE: f64 = 0.2;

/// Sterowanie i postęp generowania, współdzielone między wątkami (wszystko atomowe).
#[derive(Debug, Default)]
pub struct Control {
    cancel: AtomicBool,
    evals_done: AtomicU64,
    evals_planned: AtomicU64,
    candidates: AtomicUsize,
    /// Faktyczne wywołania funkcji celu (bez doliczanego niewykorzystanego budżetu).
    evals_real: AtomicU64,
    /// Największy dotąd zwrócony postęp (bity `f64`; dla liczb nieujemnych porządek bitów
    /// jest porządkiem liczb).
    progress_bits: AtomicU64,
}

impl Control {
    pub fn new() -> Self {
        Self::default()
    }

    /// Prosi o przerwanie; sterownik reaguje przed następnym wywołaniem funkcji celu.
    pub fn cancel(&self) {
        self.cancel.store(true, Ordering::Relaxed);
    }

    pub fn is_cancelled(&self) -> bool {
        self.cancel.load(Ordering::Relaxed)
    }

    /// Wykonane wywołania funkcji celu (niewykorzystany budżet ukończonego przebiegu też się
    /// liczy, żeby postęp dochodził do 1).
    pub fn evals_done(&self) -> u64 {
        self.evals_done.load(Ordering::Relaxed)
    }

    /// Faktycznie wykonane wywołania funkcji celu.
    pub fn evals_used(&self) -> u64 {
        self.evals_real.load(Ordering::Relaxed)
    }

    /// Zaplanowane wywołania: liczba przebiegów dotychczasowych fal × budżet.
    pub fn evals_planned(&self) -> u64 {
        self.evals_planned.load(Ordering::Relaxed)
    }

    /// Liczba ukończonych przebiegów (gotowych kandydatów).
    pub fn candidates(&self) -> usize {
        self.candidates.load(Ordering::Relaxed)
    }

    /// Postęp w [0, 1]. Nie cofa się: dołożenie fali zwiększa plan, ale zwracane jest maksimum
    /// z dotychczasowych wartości. Plan obejmuje tylko fale już zaczęte, więc część paska
    /// ([`LATER_WAVES_SHARE`]) jest zarezerwowana na kolejne — 1 daje dopiero `finish`
    /// (przegląd 2026-11-18 M2: pasek stał na ~99 % przez fale 2–3).
    pub fn progress(&self) -> f64 {
        let planned = self.evals_planned();
        let now = if planned == 0 {
            0.0
        } else {
            let share = self.evals_done() as f64 / planned as f64;
            (share * (1.0 - LATER_WAVES_SHARE)).min(1.0)
        };
        let seen = self.progress_bits.fetch_max(now.to_bits(), Ordering::Relaxed);
        f64::from_bits(seen.max(now.to_bits()))
    }

    pub(crate) fn plan(&self, evals: u64) {
        self.evals_planned.fetch_add(evals, Ordering::Relaxed);
    }

    /// Jedno wywołanie funkcji celu.
    pub(crate) fn count_eval(&self) {
        self.evals_real.fetch_add(1, Ordering::Relaxed);
        self.evals_done.fetch_add(1, Ordering::Relaxed);
    }

    /// Niewykorzystany budżet ukończonego przebiegu (tylko dla postępu).
    pub(crate) fn add_done(&self, evals: u64) {
        self.evals_done.fetch_add(evals, Ordering::Relaxed);
    }

    pub(crate) fn add_candidate(&self) {
        self.candidates.fetch_add(1, Ordering::Relaxed);
    }

    /// Generowanie dobiegło końca bez przerwania: postęp = 1.
    pub(crate) fn finish(&self) {
        self.progress_bits.fetch_max(1.0_f64.to_bits(), Ordering::Relaxed);
    }
}

/// Jedno rozwiązanie: punkt, ocena końcowa i pochodzenie.
#[derive(Debug, Clone, PartialEq)]
pub struct Candidate {
    pub x: Vec<f64>,
    pub score: Score,
    /// Numer przebiegu (ciągły między falami); rozstrzyga remisy.
    pub run: u32,
    /// Numer fali, od 1.
    pub wave: u32,
    /// `false`, gdy rozwiązanie jest bliżej niż `min_diversity` od lepszego wybranego
    /// (dopełnienie listy po ostatniej fali).
    pub diverse: bool,
}

/// Wynik generowania.
#[derive(Debug, Clone, PartialEq)]
pub struct Outcome {
    /// Najwyżej `n` rozwiązań: bez twardych naruszeń najpierw, potem rosnąco wg `total`,
    /// remisy wg numeru przebiegu.
    pub chosen: Vec<Candidate>,
    /// Zadziałał limit czasu — wynik nie jest powtarzalny.
    pub timed_out: bool,
    /// Generowanie przerwano; `chosen` pochodzi z przebiegów ukończonych przed przerwaniem.
    pub cancelled: bool,
    /// Liczba ukończonych przebiegów.
    pub runs: u32,
}

/// Syntetyczne funkcje celu do testów optymalizatora (niezależne od zasad palety).
#[cfg(test)]
pub(crate) mod testutil {
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::time::Duration;

    use crate::objective::{Objective, Score};
    use crate::rng::Rng;

    /// „Studnie”: `f(x) = min_k (‖x − c_k‖² + depth_k)` — minimum lokalne w każdym `c_k`.
    pub struct Wells {
        pub centers: Vec<Vec<f64>>,
        pub depths: Vec<f64>,
        pub lower: Vec<f64>,
        pub upper: Vec<f64>,
        /// Rozwiązanie jest „bez twardych naruszeń”, gdy `f ≤ feasible_below`.
        pub feasible_below: f64,
        /// Czy `repulsion` odpycha (inaczej zwraca 0).
        pub repel: bool,
        /// Sztuczne opóźnienie każdego wywołania `value_grad`.
        pub delay: Option<Duration>,
        /// Panika w wywołaniu o tym numerze (od 0).
        pub panic_at: Option<usize>,
        pub calls: AtomicUsize,
    }

    impl Wells {
        /// Siatka `side × side` studni w kwadracie [0, side]², głębokości rosnące z numerem.
        pub fn grid(side: usize) -> Self {
            let mut centers = Vec::new();
            for i in 0..side {
                for j in 0..side {
                    centers.push(vec![i as f64 + 0.5, j as f64 + 0.5]);
                }
            }
            let depths = (0..centers.len()).map(|k| 0.01 * k as f64).collect();
            Self {
                centers,
                depths,
                lower: vec![0.0; 2],
                upper: vec![side as f64; 2],
                feasible_below: f64::INFINITY,
                repel: true,
                delay: None,
                panic_at: None,
                calls: AtomicUsize::new(0),
            }
        }

        /// Jedna studnia: wszystkie przebiegi zbiegają do tego samego punktu.
        pub fn single() -> Self {
            let mut w = Self::grid(1);
            w.lower = vec![-3.0; 2];
            w.upper = vec![4.0; 2];
            w.repel = false;
            w
        }

        /// Numer studni, w której leży `x`, i wartość funkcji.
        pub fn well(&self, x: &[f64]) -> (usize, f64) {
            let mut best = (0, f64::INFINITY);
            for (k, c) in self.centers.iter().enumerate() {
                let d2: f64 = x.iter().zip(c).map(|(a, b)| (a - b) * (a - b)).sum();
                if d2 + self.depths[k] < best.1 {
                    best = (k, d2 + self.depths[k]);
                }
            }
            best
        }
    }

    impl Objective for Wells {
        fn dim(&self) -> usize {
            self.lower.len()
        }

        fn bounds(&self) -> (&[f64], &[f64]) {
            (&self.lower, &self.upper)
        }

        fn sample(&self, rng: &mut Rng, out: &mut [f64]) {
            for (i, v) in out.iter_mut().enumerate() {
                *v = rng.range(self.lower[i], self.upper[i]);
            }
        }

        fn current(&self, out: &mut [f64]) {
            for (i, v) in out.iter_mut().enumerate() {
                *v = 0.5 * (self.lower[i] + self.upper[i]);
            }
        }

        fn value_grad(&self, x: &[f64], grad: &mut [f64]) -> f64 {
            let call = self.calls.fetch_add(1, Ordering::Relaxed);
            if self.panic_at == Some(call) {
                panic!("celowa panika funkcji celu");
            }
            if let Some(delay) = self.delay {
                std::thread::sleep(delay);
            }
            let (k, f) = self.well(x);
            for (i, g) in grad.iter_mut().enumerate() {
                *g = 2.0 * (x[i] - self.centers[k][i]);
            }
            f
        }

        fn score(&self, x: &[f64]) -> Score {
            let total = self.well(x).1;
            Score { feasible: total <= self.feasible_below, total }
        }

        fn distance(&self, a: &[f64], b: &[f64]) -> f64 {
            a.iter().zip(b).map(|(p, q)| (p - q) * (p - q)).sum::<f64>().sqrt()
        }

        fn repulsion(&self, x: &[f64], others: &[Vec<f64>], min_div: f64, grad: &mut [f64]) -> f64 {
            if !self.repel {
                return 0.0;
            }
            // kara 50·(2·min_div − d)² dla d < 2·min_div
            let reach = 2.0 * min_div;
            let mut total = 0.0;
            for o in others {
                let d = self.distance(x, o);
                if d < reach && d > 0.0 {
                    let gap = reach - d;
                    total += 50.0 * gap * gap;
                    for (i, g) in grad.iter_mut().enumerate() {
                        *g -= 100.0 * gap * (x[i] - o[i]) / d;
                    }
                }
            }
            total
        }
    }
}
