//! Układ odcieni: cele H dla akcentów.
//!
//! Układ to jawna lista odcieni (rodziny). Akcent `i` (od 0, w kolejności kolorów) dostaje
//! `hues[i mod k]`; pusta lista = brak celów. `jitter` dodaje przesunięcia ±jitter wyznaczone
//! przez ziarno. Harmonie (triada, kwadrat…) i dawne rodzaje rozwija Python do listy.

use crate::rng::Rng;
use crate::schema::{HueScheme, Session};

/// Strumień losowy przesunięć układu (`Rng::new(seed, JITTER_STREAM)`).
pub const JITTER_STREAM: u64 = 7919;

/// Cele odcieni dla `n` akcentów, w [0, 360). Pusta lista, gdy układ nie daje celów.
pub fn scheme_targets(scheme: &HueScheme, n: usize, seed: u64) -> Vec<f64> {
    let k = scheme.hues.len();
    if n == 0 || k == 0 {
        return Vec::new();
    }
    let mut out: Vec<f64> = (0..n).map(|i| scheme.hues[i % k]).collect();
    if scheme.jitter > 0.0 {
        let mut rng = Rng::new(seed, JITTER_STREAM);
        for h in &mut out {
            *h += rng.range(-scheme.jitter, scheme.jitter);
        }
    }
    out.into_iter().map(|h| h.rem_euclid(360.0)).collect()
}

/// Cele układu dla wszystkich akcentów sesji: `(id, stopnie)` w kolejności kolorów.
pub fn hue_targets(session: &Session) -> Vec<(String, f64)> {
    let accents = session.slots.get(2..).unwrap_or(&[]);
    let seed = session.globals.optimizer.seed;
    let targets = scheme_targets(&session.globals.hue_scheme, accents.len(), seed);
    accents.iter().zip(targets).map(|(slot, h)| (slot.id.clone(), h)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scheme(hues: &[f64]) -> HueScheme {
        HueScheme { hues: hues.to_vec(), tol: 15.0, jitter: 0.0, hard: false, weight: 1.0 }
    }

    fn assert_targets(s: &HueScheme, n: usize, want: &[f64]) {
        let got = scheme_targets(s, n, 0);
        assert_eq!(got.len(), want.len(), "n = {n}: {got:?}");
        for (g, w) in got.iter().zip(want) {
            assert!((g - w).abs() < 1e-9, "n = {n}: {got:?} zamiast {want:?}");
        }
    }

    #[test]
    fn accents_cycle_through_the_families() {
        let s = scheme(&[15.0, 140.0, 280.0]);
        assert_targets(&s, 8, &[15.0, 140.0, 280.0, 15.0, 140.0, 280.0, 15.0, 140.0]);
        assert_targets(&s, 2, &[15.0, 140.0]);
        assert_targets(&scheme(&[370.0, -10.0]), 2, &[10.0, 350.0]);
        assert_targets(&scheme(&[]), 4, &[]);
        assert_targets(&s, 0, &[]);
    }

    #[test]
    fn jitter_is_bounded_and_fixed_by_the_seed() {
        let hues: Vec<f64> = (0..8).map(|i| 45.0 * i as f64).collect();
        let base = scheme(&hues);
        let jittered = HueScheme { jitter: 8.0, ..base.clone() };
        let plain = scheme_targets(&base, 8, 5);
        let a = scheme_targets(&jittered, 8, 5);
        assert_eq!(a, scheme_targets(&jittered, 8, 5));
        assert_ne!(a, scheme_targets(&jittered, 8, 6));
        let mut rng = Rng::new(5, JITTER_STREAM);
        for (j, p) in a.iter().zip(&plain) {
            let d = (j - p + 540.0).rem_euclid(360.0) - 180.0;
            assert!(d.abs() <= 8.0 && d != 0.0, "przesunięcie {d}");
            // kolejno `range(−jitter, jitter)` na akcent
            assert!((d - rng.range(-8.0, 8.0)).abs() < 1e-9);
        }
    }
}
