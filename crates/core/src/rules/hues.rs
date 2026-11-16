//! Układ odcieni: cele H dla akcentów (port `hues.py@4b71aeb`).
//!
//! Układ ma `k` odcieni bazowych. Akcent `i` (od 0, w kolejności kolorów) dostaje
//! `base[i mod k] + (i div k) · 360 / (k · ⌈n / k⌉)`: kolejne „obiegi” przesuwają się równo
//! między odcieniami bazowymi. `jitter` dodaje przesunięcia ±jitter wyznaczone przez ziarno.

use crate::rng::Rng;
use crate::schema::{HueScheme, HueSchemeKind, Session};

/// Strumień losowy przesunięć układu (`Rng::new(seed, JITTER_STREAM)`).
pub const JITTER_STREAM: u64 = 7919;

/// Odcienie bazowe układu dla `n` akcentów (dla `equal` i `analogous` zależą od `n`).
pub fn base_hues(scheme: &HueScheme, n: usize) -> Vec<f64> {
    let r = scheme.rotation;
    match scheme.kind {
        HueSchemeKind::Equal => (0..n).map(|i| r + 360.0 * i as f64 / n as f64).collect(),
        HueSchemeKind::Analogous => {
            if n == 1 {
                return vec![scheme.center];
            }
            let lo = scheme.center - scheme.spread / 2.0;
            (0..n).map(|i| lo + scheme.spread * i as f64 / (n - 1) as f64).collect()
        }
        HueSchemeKind::Complementary => vec![r, r + 180.0],
        HueSchemeKind::Split => vec![r, r + 150.0, r + 210.0],
        HueSchemeKind::Triad => vec![r, r + 120.0, r + 240.0],
        HueSchemeKind::Tetrad => vec![r, r + 90.0, r + 180.0, r + 270.0],
        HueSchemeKind::Custom => scheme.custom.clone(),
        HueSchemeKind::None => Vec::new(),
    }
}

/// Cele odcieni dla `n` akcentów, w [0, 360). Pusta lista, gdy układ nie daje celów.
pub fn scheme_targets(scheme: &HueScheme, n: usize, seed: u64) -> Vec<f64> {
    if n == 0 {
        return Vec::new();
    }
    let base = base_hues(scheme, n);
    let k = base.len();
    if k == 0 {
        return Vec::new();
    }
    let cycles = n.div_ceil(k);
    let step = 360.0 / (k * cycles) as f64;
    let mut out: Vec<f64> = (0..n).map(|i| base[i % k] + (i / k) as f64 * step).collect();
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

    fn scheme(kind: HueSchemeKind) -> HueScheme {
        HueScheme {
            kind,
            rotation: 0.0,
            center: 0.0,
            spread: 90.0,
            custom: Vec::new(),
            tol: 15.0,
            jitter: 0.0,
            hard: false,
            weight: 1.0,
        }
    }

    fn assert_targets(s: &HueScheme, n: usize, want: &[f64]) {
        let got = scheme_targets(s, n, 0);
        assert_eq!(got.len(), want.len(), "{:?} n = {n}: {got:?}", s.kind);
        for (g, w) in got.iter().zip(want) {
            assert!((g - w).abs() < 1e-9, "{:?} n = {n}: {got:?} zamiast {want:?}", s.kind);
        }
    }

    /// Wartości policzone starym `hues.scheme_targets` (commit 4b71aeb) przy `jitter = 0`.
    #[test]
    fn targets_match_the_old_engine() {
        let with = |kind, rotation: f64| HueScheme { rotation, ..scheme(kind) };
        assert_targets(
            &with(HueSchemeKind::Equal, 10.0),
            8,
            &[10.0, 55.0, 100.0, 145.0, 190.0, 235.0, 280.0, 325.0],
        );
        assert_targets(&with(HueSchemeKind::Equal, 350.0), 3, &[350.0, 110.0, 230.0]);
        let analogous =
            HueScheme { center: 200.0, spread: 90.0, ..scheme(HueSchemeKind::Analogous) };
        assert_targets(&analogous, 5, &[155.0, 177.5, 200.0, 222.5, 245.0]);
        let one = HueScheme { center: 30.0, spread: 120.0, ..scheme(HueSchemeKind::Analogous) };
        assert_targets(&one, 1, &[30.0]);
        assert_targets(
            &with(HueSchemeKind::Complementary, 20.0),
            5,
            &[20.0, 200.0, 80.0, 260.0, 140.0],
        );
        assert_targets(
            &with(HueSchemeKind::Split, 0.0),
            7,
            &[0.0, 150.0, 210.0, 40.0, 190.0, 250.0, 80.0],
        );
        assert_targets(
            &with(HueSchemeKind::Triad, 45.0),
            8,
            &[45.0, 165.0, 285.0, 85.0, 205.0, 325.0, 125.0, 245.0],
        );
        assert_targets(
            &with(HueSchemeKind::Tetrad, 300.0),
            14,
            &[
                300.0, 30.0, 120.0, 210.0, 322.5, 52.5, 142.5, 232.5, 345.0, 75.0, 165.0, 255.0,
                7.5, 97.5,
            ],
        );
        let custom =
            HueScheme { custom: vec![15.0, 140.0, 280.0], ..scheme(HueSchemeKind::Custom) };
        assert_targets(&custom, 8, &[15.0, 140.0, 280.0, 55.0, 180.0, 320.0, 95.0, 220.0]);
        assert_targets(&scheme(HueSchemeKind::Custom), 4, &[]);
        assert_targets(&scheme(HueSchemeKind::None), 6, &[]);
        assert_targets(&with(HueSchemeKind::Triad, 45.0), 0, &[]);
    }

    #[test]
    fn jitter_is_bounded_and_fixed_by_the_seed() {
        let base = scheme(HueSchemeKind::Equal);
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
