//! Spięcie zasad ze sterownikiem: parametry generowania z sesji i propozycje z wyniku.

use std::time::Duration;

use crate::objective::Objective;
use crate::optim::{DriverOpts, Outcome};
use crate::schema::Session;
use crate::violation::Violation;

use super::problem::Problem;

/// Jedna propozycja palety (plan I3, kształt `P`).
#[derive(Debug, Clone, PartialEq)]
pub struct Proposal {
    /// Kolory wolne: `(id, [l, c, h])`, w gamucie sRGB.
    pub values: Vec<(String, [f64; 3])>,
    /// Funkcja celu bez marginesu twardych zasad i bez kary za różnorodność.
    pub score: f64,
    /// Naruszenia zasad; propozycja zbyt podobna do lepszej ma dodatkowo miękkie `diversity`.
    pub violations: Vec<Violation>,
    pub run: u32,
    pub wave: u32,
}

impl Proposal {
    /// Czy propozycja nie ma twardych naruszeń.
    pub fn feasible(&self) -> bool {
        !self.violations.iter().any(|v| v.hard)
    }
}

/// Parametry sterownika z ustawień optymalizatora sesji. Bez kolorów wolnych wynik to jedna
/// propozycja (nie ma czego różnicować).
pub fn driver_opts(session: &Session, problem: &Problem) -> DriverOpts {
    let o = &session.globals.optimizer;
    DriverOpts {
        n: if problem.dim() == 0 { 1 } else { o.n_proposals },
        seed: o.seed,
        budget: o.budget,
        time_cap: Duration::try_from_secs_f64(o.time_cap_s).unwrap_or(Duration::MAX),
        min_diversity: o.min_diversity,
        threads: o.threads,
    }
}

/// Propozycje z wyniku sterownika, w jego kolejności (bez twardych naruszeń najpierw, potem
/// rosnąco wg wyniku).
pub fn proposals(problem: &Problem, outcome: &Outcome, min_diversity: f64) -> Vec<Proposal> {
    let prepared: Vec<Vec<f64>> = outcome.chosen.iter().map(|c| problem.prepare(&c.x)).collect();
    let free = problem.free_ids();
    outcome
        .chosen
        .iter()
        .enumerate()
        .map(|(i, cand)| {
            let colors = problem.decode(&cand.x);
            let report = problem.evaluate(&cand.x);
            let mut violations = report.violations;
            if !cand.diverse {
                // odległość do najbliższego lepszego rozwiązania uznanego za różnorodne
                let nearest = (0..i)
                    .filter(|&j| outcome.chosen[j].diverse)
                    .map(|j| problem.distance_prepared(&prepared[i], &prepared[j]))
                    .fold(f64::INFINITY, f64::min);
                if nearest < min_diversity {
                    violations.push(problem.diversity_violation(nearest, min_diversity));
                }
            }
            let values = free
                .iter()
                .zip(problem.free_slots())
                .map(|(id, slot)| (id.clone(), colors[slot]))
                .collect();
            Proposal { values, score: report.objective, violations, run: cand.run, wave: cand.wave }
        })
        .collect()
}
