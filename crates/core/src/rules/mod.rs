//! Zasady palety jako funkcja celu: kompilacja sesji, ocena naruszeń, problem optymalizacji
//! (plan I5, spec §7.2 i §9.4).
//!
//! - `terms` — naruszenie każdego rodzaju zasady jako funkcja generyczna po skalarze;
//! - `compile` — sesja `algopalette.v2` → lista termów;
//! - `eval` — ocena termów na konkretnych kolorach i raport naruszeń ([`evaluate`]);
//! - `hues` — cele układu odcieni ([`hue_targets`]);
//! - `problem` — [`Problem`]: zmienne, granice i funkcja celu z dokładnym gradientem;
//! - `generate` — parametry sterownika z sesji i [`Proposal`] z jego wyniku.

mod compile;
mod eval;
mod generate;
pub mod hues;
mod problem;
mod terms;

pub use eval::{Evaluation, evaluate};
pub use generate::{Proposal, driver_opts, proposals};
pub use hues::hue_targets;
pub use problem::{HUE_UNIT, Problem};

#[cfg(test)]
mod tests {
    use std::collections::BTreeSet;
    use std::time::Duration;

    use serde_json::{Value, json};

    use super::compile::compile;
    use super::*;
    use crate::color;
    use crate::objective::Objective;
    use crate::optim::{Control, DriverOpts, generate};
    use crate::rng::Rng;
    use crate::schema::{self, Session};
    use crate::violation::{Violation, ViolationKind};

    // -----------------------------------------------------------------------
    // Budowanie sesji testowych
    // -----------------------------------------------------------------------

    fn rule(value: Value, hard: bool) -> Value {
        json!({"value": value, "enabled": true, "hard": hard, "weight": 1.0})
    }

    fn slot(id: &str, l: f64, c: f64, h: f64) -> Value {
        json!({
            "id": id, "name": "", "locked": false,
            "value": {"l": l, "c": c, "h": h}, "hex": "", "use_scheme": false,
            "rules": {
                "lightness": null, "chroma": null, "hue": null, "contrast_bg": null,
                "min_distance": null, "extreme": null
            },
            "relations": []
        })
    }

    fn rel(kind: &str, target: &str, op: &str, value: f64) -> Value {
        json!({
            "kind": kind, "target": target, "op": op, "value": value, "tol": 0.0,
            "chroma_op": "add", "chroma_mode": "abs", "metric": null, "other": null, "t": 0.5,
            "enabled": true, "hard": true, "weight": 1.0
        })
    }

    /// Sesja bez żadnych zasad: tło, tekst i `accents` akcentów o rozłożonych odcieniach.
    fn bare(accents: usize) -> Value {
        let mut slots = vec![slot("bg", 0.18, 0.02, 260.0), slot("fg", 0.92, 0.01, 260.0)];
        for i in 0..accents {
            let h = 20.0 + 360.0 * i as f64 / accents as f64;
            slots.push(slot(&format!("a{}", i + 1), 0.7, 0.1, h));
        }
        json!({
            "format": "algopalette.v2", "preset": null, "view_model": "oklch",
            "globals": {
                "polarity": "dark", "contrast_metric": "wcag21", "delta_e": "ok",
                "fit_method": "oklch-chroma",
                "hue_scheme": {"kind": "none", "rotation": 0.0, "center": 0.0, "spread": 90.0,
                    "custom": [], "tol": 15.0, "jitter": 0.0, "hard": false, "weight": 1.0},
                "lightness_spread": null,
                "avoid_colors": [], "avoid_distance": 0.0,
                "optimizer": {"n_proposals": 6, "seed": 0, "budget": 3000, "time_cap_s": 30.0,
                    "min_diversity": 0.05, "hard_weight": 1000.0, "threads": 0}
            },
            "slots": slots
        })
    }

    fn parse(doc: &Value) -> Session {
        schema::parse(&doc.to_string()).expect("poprawna sesja testowa")
    }

    fn find<'a>(list: &'a [Violation], key: &str) -> Option<&'a Violation> {
        list.iter().find(|v| v.key == key)
    }

    fn keys(session: &Session) -> Vec<String> {
        compile(session).terms.iter().map(|t| t.key.clone()).collect()
    }

    /// Sesja z każdym rodzajem termu: zakresy z zakazami, kontrast, skrajny kontrast, pary
    /// akcentów, wszystkie rodzaje zależności, rozrzut, układ, unikany kolor.
    fn everything(delta_e: &str, metric: &str) -> Value {
        let mut doc = bare(5);
        doc["globals"]["delta_e"] = json!(delta_e);
        doc["globals"]["contrast_metric"] = json!(metric);
        doc["globals"]["hue_scheme"]["kind"] = json!("triad");
        doc["globals"]["lightness_spread"] = rule(json!({"lo": 0.05, "hi": 0.12}), false);
        doc["globals"]["avoid_colors"] = json!([{"l": 0.7, "c": 0.1, "h": 30.0}]);
        doc["globals"]["avoid_distance"] = json!(0.08);
        let slow = matches!(delta_e, "2000" | "itp" | "cam16");
        let (near, far) = if slow { (8.0, 20.0) } else { (0.08, 0.2) };

        let bg = &mut doc["slots"][0]["rules"];
        bg["lightness"] = rule(json!({"lo": 0.1, "hi": 0.25, "exclude": []}), true);
        bg["chroma"] = rule(json!({"mode": "abs", "lo": null, "hi": 0.04, "exclude": []}), true);
        let fg = &mut doc["slots"][1]["rules"];
        fg["lightness"] = rule(json!({"lo": 0.85, "hi": 0.98, "exclude": []}), true);
        fg["contrast_bg"] = rule(json!({"metric": null, "lo": 7.0, "hi": null}), true);

        let a1 = &mut doc["slots"][2];
        a1["rules"]["lightness"] =
            rule(json!({"lo": 0.6, "hi": 0.85, "exclude": [[0.70, 0.74]]}), true);
        a1["rules"]["chroma"] =
            rule(json!({"mode": "rel", "lo": 0.3, "hi": 0.9, "exclude": [[0.5, 0.6]]}), true);
        a1["rules"]["hue"] =
            rule(json!({"lo": 300.0, "hi": 90.0, "exclude": [[350.0, 10.0]]}), true);
        a1["rules"]["contrast_bg"] = rule(json!({"metric": "apca", "lo": 45.0, "hi": 80.0}), false);
        a1["rules"]["min_distance"] = rule(json!(far), false);
        a1["rules"]["extreme"] = rule(json!("weakest"), true);

        let a2 = &mut doc["slots"][3];
        a2["use_scheme"] = json!(true);
        a2["rules"]["lightness"] = rule(json!({"lo": 0.5, "hi": 0.7, "exclude": []}), false);
        a2["rules"]["chroma"] =
            rule(json!({"mode": "abs", "lo": 0.05, "hi": 0.15, "exclude": [[0.08, 0.1]]}), false);
        a2["rules"]["hue"] =
            rule(json!({"lo": 100.0, "hi": 200.0, "exclude": [[120.0, 140.0]]}), false);
        a2["rules"]["extreme"] = rule(json!("strongest"), false);
        a2["rules"]["min_distance"] = rule(json!(near), true);
        let mut chroma_mul = rel("chroma", "a1", "ge", 0.8);
        chroma_mul["chroma_op"] = json!("mul");
        chroma_mul["chroma_mode"] = json!("rel");
        let mut hue_eq = rel("hue", "a1", "eq", 30.0);
        hue_eq["tol"] = json!(5.0);
        let mut contrast = rel("contrast", "a3", "ge", 1.5);
        contrast["metric"] = json!("wcag21");
        let mut distance = rel("distance", "a5", "ge", 0.3);
        distance["metric"] = json!("hyab");
        a2["relations"] = json!([
            hue_eq,
            rel("hue", "a3", "ge", 40.0),
            rel("lightness", "a1", "ge", 0.05),
            rel("chroma", "a3", "le", -0.02),
            chroma_mul,
            contrast,
            rel("distance", "a1", "ge", far),
            distance,
        ]);

        let a3 = &mut doc["slots"][4];
        a3["use_scheme"] = json!(true);
        let mut mix = rel("mix", "a1", "eq", 0.0);
        mix["other"] = json!("a2");
        mix["t"] = json!(0.3);
        mix["tol"] = json!(0.02);
        a3["relations"] = json!([mix, rel("lightness", "a4", "le", -0.03)]);
        doc["slots"][6]["use_scheme"] = json!(true);
        doc
    }

    fn free_ids(ids: &[&str]) -> Vec<String> {
        ids.iter().map(|s| (*s).to_owned()).collect()
    }

    /// Losowy punkt wewnątrz granic (odcień bez granic: dowolny).
    fn interior(p: &Problem, rng: &mut Rng) -> Vec<f64> {
        let (lo, hi) = p.bounds();
        (0..p.dim())
            .map(|i| {
                if lo[i].is_finite() {
                    let pad = 0.02 * (hi[i] - lo[i]);
                    rng.range(lo[i] + pad, hi[i] - pad)
                } else {
                    rng.range(0.0, 3.6)
                }
            })
            .collect()
    }

    /// Gradient różnicą centralną z krokiem `h`.
    fn fd(f: &dyn Fn(&[f64]) -> f64, x: &[f64], h: f64) -> Vec<f64> {
        (0..x.len())
            .map(|i| {
                let mut p = x.to_vec();
                p[i] = x[i] + h;
                let up = f(&p);
                p[i] = x[i] - h;
                (up - f(&p)) / (2.0 * h)
            })
            .collect()
    }

    fn max_abs(v: &[f64]) -> f64 {
        v.iter().fold(0.0, |m, x| m.max(x.abs()))
    }

    /// Sprawdza gradient w `want` punktach gładkich (różnice z krokami h i 2h zgodne).
    fn check_gradient(
        name: &str,
        p: &Problem,
        seed: u64,
        want: usize,
        f: &dyn Fn(&[f64], &mut [f64]) -> f64,
    ) {
        let value = |x: &[f64]| f(x, &mut vec![0.0; x.len()]);
        let mut rng = Rng::new(seed, 0);
        let (mut checked, mut tried) = (0, 0);
        while checked < want {
            tried += 1;
            assert!(tried <= 40 * want, "{name}: za mało punktów gładkich ({checked}/{tried})");
            let x = interior(p, &mut rng);
            let mut grad = vec![0.0; x.len()];
            let total = f(&x, &mut grad);
            assert!(total.is_finite() && grad.iter().all(|g| g.is_finite()), "{name}: {x:?}");
            let fine = fd(&value, &x, 1e-6);
            let coarse = fd(&value, &x, 2e-6);
            let scale = max_abs(&fine).max(1e-6);
            let spread: Vec<f64> = fine.iter().zip(&coarse).map(|(a, b)| a - b).collect();
            if max_abs(&spread) > 1e-5 * scale {
                continue; // załamanie funkcji w pobliżu punktu
            }
            let diff: Vec<f64> = fine.iter().zip(&grad).map(|(a, b)| a - b).collect();
            let err = max_abs(&diff) / scale;
            assert!(err <= 1e-4, "{name}: błąd gradientu {err:.3e} w {x:?}\n{grad:?}\n{fine:?}");
            checked += 1;
        }
    }

    // -----------------------------------------------------------------------
    // Ocena: zakazy, układ, raport
    // -----------------------------------------------------------------------

    #[test]
    fn lightness_inside_an_exclusion_is_a_hard_violation() {
        let mut doc = bare(2);
        doc["slots"][2]["value"]["l"] = json!(0.72);
        doc["slots"][2]["rules"]["lightness"] =
            rule(json!({"lo": 0.6, "hi": 0.85, "exclude": [[0.70, 0.74]]}), false);
        let e = evaluate(&parse(&doc));
        let v = find(&e.violations, "slot:a1:lightness:exclude:0").expect("naruszenie zakazu");
        assert_eq!(v.kind, ViolationKind::Exclude);
        assert!(v.hard, "zakaz jest twardy także przy miękkiej zasadzie");
        assert!((v.amount - 0.02).abs() < 1e-12, "{}", v.amount);
        assert_eq!(v.achieved, 0.72);
        assert_eq!(v.slots, ["a1"]);
        assert_eq!(serde_json::to_value(&v.req).unwrap(), json!({"lo": 0.70, "hi": 0.74}));
        assert_eq!(serde_json::to_value(&v.meta).unwrap(), json!({"channel": "lightness"}));
        // sam zakres jest spełniony; funkcja celu = hard_weight · (0.02 / 0.01)²
        assert_eq!(e.violations.len(), 1);
        assert!((e.objective - 4000.0).abs() < 1e-6, "{}", e.objective);

        // poza zakazem (także na jego brzegu) — brak naruszenia
        for l in [0.70, 0.74, 0.65, 0.8] {
            doc["slots"][2]["value"]["l"] = json!(l);
            assert!(evaluate(&parse(&doc)).violations.is_empty(), "L = {l}");
        }
        // zasada wyłączona — zakaz nie działa
        doc["slots"][2]["value"]["l"] = json!(0.72);
        doc["slots"][2]["rules"]["lightness"]["enabled"] = json!(false);
        assert!(evaluate(&parse(&doc)).violations.is_empty());
    }

    #[test]
    fn hue_exclusion_wraps_through_zero_and_chroma_exclusion_reports_its_mode() {
        let mut doc = bare(2);
        doc["slots"][2]["value"] = json!({"l": 0.7, "c": 0.1, "h": 5.0});
        doc["slots"][2]["rules"]["hue"] =
            rule(json!({"lo": 0.0, "hi": 360.0, "exclude": [[350.0, 10.0], [100.0, 120.0]]}), true);
        let e = evaluate(&parse(&doc));
        assert_eq!(e.violations.len(), 1);
        let v = &e.violations[0];
        assert_eq!(v.key, "slot:a1:hue:exclude:0");
        assert!((v.amount - 5.0).abs() < 1e-9 && v.hard);
        assert_eq!(serde_json::to_value(&v.req).unwrap(), json!({"lo": 350.0, "hi": 10.0}));
        assert_eq!(serde_json::to_value(&v.meta).unwrap(), json!({"channel": "hue"}));
        doc["slots"][2]["value"]["h"] = json!(110.0);
        let e = evaluate(&parse(&doc));
        assert_eq!(e.violations[0].key, "slot:a1:hue:exclude:1");
        assert!((e.violations[0].amount - 10.0).abs() < 1e-9);
        doc["slots"][2]["value"]["h"] = json!(200.0);
        assert!(evaluate(&parse(&doc)).violations.is_empty());

        // nasycenie względne: zakaz w jednostkach trybu
        let mut doc = bare(2);
        let maxc: f64 = color::max_chroma(0.7, 30.0);
        doc["slots"][2]["value"] = json!({"l": 0.7, "c": 0.55 * maxc, "h": 30.0});
        doc["slots"][2]["rules"]["chroma"] =
            rule(json!({"mode": "rel", "lo": null, "hi": null, "exclude": [[0.5, 0.7]]}), true);
        let e = evaluate(&parse(&doc));
        let v = find(&e.violations, "slot:a1:chroma:exclude:0").unwrap();
        assert!((v.amount - 0.05).abs() < 1e-9, "{}", v.amount);
        assert_eq!(
            serde_json::to_value(&v.meta).unwrap(),
            json!({"channel": "chroma", "mode": "rel"})
        );
    }

    #[test]
    fn exclusions_covering_the_whole_range_stay_violated_everywhere() {
        let mut doc = bare(2);
        doc["slots"][2]["rules"]["lightness"] =
            rule(json!({"lo": 0.6, "hi": 0.8, "exclude": [[0.5, 0.9]]}), true);
        let session = parse(&doc);
        let e = evaluate(&session);
        let v = find(&e.violations, "slot:a1:lightness:exclude:0").expect("stałe naruszenie");
        assert!(v.hard && v.amount > 0.0);

        let p = Problem::compile(&session, &free_ids(&["a1", "a2"]));
        let mut rng = Rng::new(3, 0);
        let mut x = vec![0.0; p.dim()];
        let mut grad = vec![0.0; p.dim()];
        for _ in 0..200 {
            p.sample(&mut rng, &mut x);
            let f = p.value_grad(&x, &mut grad);
            assert!(f.is_finite() && f > 0.0 && grad.iter().all(|g| g.is_finite()));
            assert!(!p.score(&x).feasible);
        }
        // generowanie kończy się w budżecie i oddaje rozwiązania oznaczone jako złe
        let opts = DriverOpts {
            n: 3,
            seed: 1,
            budget: 300,
            time_cap: Duration::from_secs(30),
            min_diversity: 0.05,
            threads: 2,
        };
        let outcome = generate(&p, &opts, &Control::new());
        assert_eq!(outcome.chosen.len(), 3);
        assert!(outcome.chosen.iter().all(|c| !c.score.feasible));
        for c in &outcome.chosen {
            let report = p.evaluate(&c.x);
            let v = find(&report.violations, "slot:a1:lightness:exclude:0").unwrap();
            assert!(v.hard);
        }
    }

    #[test]
    fn scheme_term_follows_use_scheme_independently_of_the_hue_rule() {
        let mut doc = bare(3);
        doc["globals"]["hue_scheme"]["kind"] = json!("triad");
        doc["slots"][2]["use_scheme"] = json!(true);
        doc["slots"][2]["rules"]["hue"] =
            rule(json!({"lo": 0.0, "hi": 270.0, "exclude": []}), true);
        doc["slots"][3]["use_scheme"] = json!(false);
        doc["slots"][4]["use_scheme"] = json!(true);
        // tło i tekst mają use_scheme = true, ale celów układu nie dostają nigdy
        doc["slots"][0]["use_scheme"] = json!(true);
        doc["slots"][1]["use_scheme"] = json!(true);
        let session = parse(&doc);
        let k = keys(&session);
        assert!(
            k.contains(&"slot:a1:hue".to_owned()) && k.contains(&"global:scheme:a1".to_owned())
        );
        assert!(!k.contains(&"global:scheme:a2".to_owned()));
        assert!(k.contains(&"global:scheme:a3".to_owned()));
        assert!(!k.iter().any(|key| key == "global:scheme:bg" || key == "global:scheme:fg"));
        // cele są liczone dla wszystkich akcentów wg pozycji, niezależnie od przełącznika
        assert_eq!(
            hue_targets(&session),
            [("a1".to_owned(), 0.0), ("a2".to_owned(), 120.0), ("a3".to_owned(), 240.0)]
        );
        // a3 ma odcień 260°, cel 240° ± 15° → naruszenie 5°
        let e = evaluate(&session);
        let v = find(&e.violations, "global:scheme:a3").unwrap();
        assert!((v.amount - 5.0).abs() < 1e-9 && !v.hard);
        assert_eq!(serde_json::to_value(&v.req).unwrap(), json!({"target": 240.0, "tol": 15.0}));
        assert!((v.achieved - 260.0).abs() < 1e-12);
    }

    #[test]
    fn report_follows_the_i3_table() {
        let mut doc = everything("ok", "wcag21");
        doc["slots"][2]["rules"]["contrast_bg"]["value"] =
            json!({"metric": "apca", "lo": 75.0, "hi": 100.0});
        doc["slots"][3]["value"]["c"] = json!(0.03); // a2 blade: zależność „≥ 0.8 × a1” naruszona
        let session = parse(&doc);
        let e = evaluate(&session);
        let kinds: BTreeSet<&str> = e.violations.iter().map(|v| v.kind.as_str()).collect();
        for kind in ["contrast_bg", "extreme", "pair_distance", "rel", "spread", "avoid"] {
            assert!(kinds.contains(kind), "brak naruszenia rodzaju {kind}: {kinds:?}");
        }
        let get = |key: &str| find(&e.violations, key).unwrap_or_else(|| panic!("brak {key}"));

        let v = get("slot:a1:contrast_bg");
        assert_eq!(v.slots, ["a1", "bg"]);
        assert_eq!(serde_json::to_value(&v.meta).unwrap(), json!({"metric": "apca"}));
        assert_eq!(serde_json::to_value(&v.req).unwrap(), json!({"lo": 75.0, "hi": 100.0}));
        let lab = |i: usize| {
            let s = &session.slots[i].value;
            color::oklch_to_oklab([s.l, s.c, s.h])
        };
        let apca: f64 = color::contrast(lab(2), lab(0), color::ContrastMetric::Apca);
        assert_eq!(v.achieved, apca);

        // a2 ma mieć najmocniejszy kontrast; granicą jest największy kontrast pozostałych
        let v = get("slot:a2:extreme");
        assert_eq!(v.slots, ["a2", "a1", "a3", "a4", "a5"]);
        assert_eq!(
            serde_json::to_value(&v.meta).unwrap(),
            json!({"which": "strongest", "metric": "wcag21"})
        );
        let wcag =
            |i: usize| -> f64 { color::contrast(lab(i), lab(0), color::ContrastMetric::Wcag21) };
        let rest = [2, 4, 5, 6].into_iter().map(wcag).fold(f64::NEG_INFINITY, f64::max);
        assert_eq!(v.achieved, wcag(3));
        assert_eq!(v.req["bound"], json!(rest));
        assert!((v.amount - (rest - wcag(3))).abs() < 1e-12 && !v.hard);

        let v = get("pair:a1:a2:min_distance");
        assert_eq!(v.slots, ["a1", "a2"]);
        // próg = max z obu kolorów (0.2 miękki, 0.08 twardy) → twarda, 0.2
        assert_eq!(serde_json::to_value(&v.req).unwrap(), json!({"min": 0.2}));
        assert!(v.hard);
        assert_eq!(serde_json::to_value(&v.meta).unwrap(), json!({"method": "ok"}));

        let v = get("slot:a2:rel:chroma:4");
        assert_eq!(v.slots, ["a2", "a1"]);
        assert_eq!(
            serde_json::to_value(&v.meta).unwrap(),
            json!({"rel_kind": "chroma", "chroma_op": "mul", "chroma_mode": "rel", "metric": null})
        );
        assert_eq!(
            serde_json::to_value(&v.req).unwrap(),
            json!({"op": "ge", "value": 0.8, "tol": 0.0})
        );
        let v = get("slot:a2:rel:distance:7");
        assert_eq!(v.meta["metric"], json!("hyab"));
        let v = get("slot:a3:rel:mix:0");
        assert_eq!(v.slots, ["a3", "a1", "a2"]);

        let v = get("global:lightness_spread");
        assert_eq!(v.slots, ["a1", "a2", "a3", "a4", "a5"]);
        assert_eq!(v.achieved, 0.0);
        let v = get("global:avoid:a1:0");
        assert_eq!(serde_json::to_value(&v.req).unwrap(), json!({"min": 0.08}));
        assert!(v.hard);
    }

    #[test]
    fn terms_of_locked_colors_only_and_broken_relations_are_skipped() {
        let mut doc = bare(3);
        doc["slots"][2]["locked"] = json!(true);
        doc["slots"][3]["locked"] = json!(true);
        doc["slots"][2]["rules"]["lightness"] =
            rule(json!({"lo": 0.9, "hi": 1.0, "exclude": []}), true);
        doc["slots"][2]["rules"]["min_distance"] = rule(json!(0.5), true);
        doc["slots"][4]["relations"] =
            json!([rel("lightness", "usuniety", "ge", 0.5), rel("lightness", "a1", "ge", 0.5),]);
        let mut off = rel("lightness", "a1", "ge", 0.5);
        off["enabled"] = json!(false);
        doc["slots"][4]["relations"].as_array_mut().unwrap().push(off);
        let k = keys(&parse(&doc));
        assert!(!k.contains(&"slot:a1:lightness".to_owned()), "term samej kłódki");
        assert!(!k.contains(&"pair:a1:a2:min_distance".to_owned()), "para dwóch kłódek");
        assert!(k.contains(&"pair:a1:a3:min_distance".to_owned()));
        assert!(
            !k.contains(&"slot:a1:gamut".to_owned()) && k.contains(&"slot:a3:gamut".to_owned())
        );
        // numer zależności to jej pozycja na liście koloru, także gdy wcześniejsze są pomijane
        assert!(!k.iter().any(|key| key.starts_with("slot:a3:rel:lightness:0")));
        assert!(k.contains(&"slot:a3:rel:lightness:1".to_owned()));
        assert!(!k.contains(&"slot:a3:rel:lightness:2".to_owned()));
    }

    // -----------------------------------------------------------------------
    // Problem: zmienne, granice, gradient
    // -----------------------------------------------------------------------

    #[test]
    fn gradient_matches_finite_differences_for_every_term_kind() {
        let mut seen: BTreeSet<String> = BTreeSet::new();
        let cases = [
            ("ok", "wcag21"),
            ("hyab", "apca"),
            ("2000", "wcag21"),
            ("itp", "apca"),
            ("cam16", "wcag21"),
        ];
        for (n, (delta_e, metric)) in cases.into_iter().enumerate() {
            let session = parse(&everything(delta_e, metric));
            let p = Problem::compile(&session, &free_ids(&["bg", "fg", "a1", "a2", "a3", "a5"]));
            check_gradient(
                &format!("value_grad {delta_e}/{metric}"),
                &p,
                70 + n as u64,
                50,
                &|x, g| p.value_grad(x, g),
            );
            // które rodzaje termów były naruszone w punktach tej próby
            let mut rng = Rng::new(70 + n as u64, 0);
            for _ in 0..50 {
                for v in p.evaluate(&interior(&p, &mut rng)).violations {
                    let detail = match v.kind {
                        ViolationKind::Rel => {
                            format!("rel:{}", v.meta["rel_kind"].as_str().unwrap())
                        }
                        ViolationKind::Exclude => {
                            format!("exclude:{}", v.meta["channel"].as_str().unwrap())
                        }
                        kind => kind.as_str().to_owned(),
                    };
                    seen.insert(detail);
                }
            }
        }
        for kind in [
            "lightness",
            "chroma",
            "hue",
            "exclude:lightness",
            "exclude:chroma",
            "exclude:hue",
            "contrast_bg",
            "extreme",
            "pair_distance",
            "rel:hue",
            "rel:lightness",
            "rel:chroma",
            "rel:contrast",
            "rel:distance",
            "rel:mix",
            "spread",
            "scheme",
            "avoid",
        ] {
            assert!(
                seen.contains(kind),
                "rodzaj {kind} nie był naruszony w żadnym punkcie: {seen:?}"
            );
        }
    }

    #[test]
    fn repulsion_gradient_matches_finite_differences() {
        let session = parse(&everything("ok", "wcag21"));
        let p = Problem::compile(&session, &free_ids(&["a1", "a2", "a3", "a5"]));
        let mut rng = Rng::new(5, 0);
        let others: Vec<Vec<f64>> = (0..3).map(|_| p.prepare(&interior(&p, &mut rng))).collect();
        // próg większy niż typowa odległość, żeby kara była czynna
        check_gradient("repulsion", &p, 81, 50, &|x, g| {
            g.fill(0.0);
            p.repulsion(x, &others, 0.6, g)
        });
        // rozwiązania dalekie: kara zerowa i gradient nietknięty
        let x = interior(&p, &mut rng);
        let mut grad = vec![7.0; p.dim()];
        assert_eq!(p.repulsion(&x, &others, 1e-6, &mut grad), 0.0);
        assert!(grad.iter().all(|&g| g == 7.0));
        // odległość od samego siebie to 0 i gradient jest skończony (zerowy)
        let me = vec![p.prepare(&x)];
        let mut grad = vec![0.0; p.dim()];
        let pen = p.repulsion(&x, &me, 0.05, &mut grad);
        assert!((pen - 25.0).abs() < 1e-9 && grad.iter().all(|&g| g == 0.0));
    }

    #[test]
    fn distance_is_mean_delta_e_ok_of_free_colors() {
        let session = parse(&bare(3));
        let p = Problem::compile(&session, &free_ids(&["a1", "a3"]));
        let mut rng = Rng::new(9, 0);
        let (a, b) = (interior(&p, &mut rng), interior(&p, &mut rng));
        let (da, db) = (p.decode(&a), p.decode(&b));
        let mut want = 0.0;
        for slot in [2, 4] {
            want += color::delta_e(
                color::oklch_to_oklab(da[slot]),
                color::oklch_to_oklab(db[slot]),
                color::DeltaE::Ok,
            );
        }
        assert!((p.distance(&a, &b) - want / 2.0).abs() < 1e-9);
        assert_eq!(p.distance(&a, &b), p.distance_prepared(&p.prepare(&a), &p.prepare(&b)));
        assert_eq!(p.distance(&a, &a), 0.0);
    }

    #[test]
    fn hard_ranges_become_bounds_and_free_colors_stay_in_gamut() {
        let mut doc = bare(3);
        doc["globals"]["hue_scheme"]["kind"] = json!("triad");
        let a1 = &mut doc["slots"][2]["rules"];
        a1["lightness"] = rule(json!({"lo": 0.6, "hi": 0.85, "exclude": []}), true);
        a1["chroma"] = rule(json!({"mode": "rel", "lo": 0.3, "hi": 0.9, "exclude": []}), true);
        a1["hue"] = rule(json!({"lo": 330.0, "hi": 20.0, "exclude": []}), true);
        let a2 = &mut doc["slots"][3]["rules"];
        a2["lightness"] = rule(json!({"lo": 0.6, "hi": 0.85, "exclude": []}), false);
        a2["chroma"] = rule(json!({"mode": "abs", "lo": 0.05, "hi": 0.1, "exclude": []}), true);
        a2["hue"] = rule(json!({"lo": 0.0, "hi": 360.0, "exclude": []}), true);
        doc["slots"][4]["use_scheme"] = json!(true);
        doc["globals"]["hue_scheme"]["hard"] = json!(true);
        let session = parse(&doc);
        let p = Problem::compile(&session, &free_ids(&["a1", "a2", "a3"]));
        assert_eq!(p.free_ids(), ["a1", "a2", "a3"]);
        let (lo, hi) = p.bounds();
        // a1: twarde zakresy L, C względnego i łuk przez 0° (330–380)
        assert_eq!(&lo[..3], &[0.6, 0.3, 330.0 / HUE_UNIT]);
        assert_eq!(&hi[..3], &[0.85, 0.9, 380.0 / HUE_UNIT]);
        // a2: miękka jasność, nasycenie bezwzględne i pełne koło nie dają granic
        assert_eq!(&lo[3..6], &[0.0, 0.0, f64::NEG_INFINITY]);
        assert_eq!(&hi[3..6], &[1.0, 1.0, f64::INFINITY]);
        // a3: twardy układ odcieni — cel 240° ± 15°
        assert_eq!(&lo[6..], &[0.0, 0.0, 2.25]);
        assert_eq!(&hi[6..], &[1.0, 1.0, 2.55]);

        let mut rng = Rng::new(4, 0);
        let mut x = vec![0.0; p.dim()];
        for round in 0..500 {
            p.sample(&mut rng, &mut x);
            for i in 0..p.dim() {
                assert!(x[i] >= lo[i] && x[i] <= hi[i], "start poza granicami: {x:?}");
            }
            if round % 5 == 0 {
                // skrajny przypadek: największe nasycenie i brzegi jasności
                x[1] = hi[1];
                x[4] = 1.0;
                x[3] = if round % 10 == 0 { 0.0 } else { 1.0 };
            }
            for (slot, lch) in p.decode(&x).into_iter().enumerate().skip(2) {
                assert!(color::in_gamut(lch), "kolor {slot} poza gamutem: {lch:?}");
                assert!((0.0..360.0).contains(&lch[2]));
            }
        }
        // kolory stałe wracają dokładnie jak w dokumencie
        let all = p.decode(&x);
        assert_eq!(all[0], [0.18, 0.02, 260.0]);
        assert_eq!(all[1], [0.92, 0.01, 260.0]);
    }

    #[test]
    fn samples_avoid_excluded_intervals() {
        let mut doc = bare(2);
        let a1 = &mut doc["slots"][2]["rules"];
        a1["lightness"] = rule(json!({"lo": 0.5, "hi": 0.9, "exclude": [[0.6, 0.8]]}), true);
        a1["chroma"] =
            rule(json!({"mode": "rel", "lo": 0.2, "hi": 1.0, "exclude": [[0.3, 0.9]]}), true);
        a1["hue"] = rule(json!({"lo": 300.0, "hi": 90.0, "exclude": [[330.0, 60.0]]}), true);
        let a2 = &mut doc["slots"][3]["rules"];
        a2["chroma"] =
            rule(json!({"mode": "abs", "lo": null, "hi": null, "exclude": [[0.03, 0.4]]}), false);
        let session = parse(&doc);
        let p = Problem::compile(&session, &free_ids(&["a1", "a2"]));
        let mut rng = Rng::new(6, 0);
        let mut x = vec![0.0; p.dim()];
        let mut low_and_high = (false, false);
        for _ in 0..300 {
            p.sample(&mut rng, &mut x);
            let c = p.decode(&x);
            let (l, h) = (c[2][0], c[2][2]);
            assert!(!(l > 0.6 && l < 0.8), "jasność w zakazie: {l}");
            assert!(!(x[1] > 0.3 && x[1] < 0.9), "nasycenie względne w zakazie: {}", x[1]);
            assert!(!(h > 330.0 || h < 60.0), "odcień w zakazie: {h}");
            assert!(!(c[3][1] > 0.03 && c[3][1] < 0.4), "nasycenie w zakazie: {}", c[3][1]);
            low_and_high.0 |= l <= 0.6;
            low_and_high.1 |= l >= 0.8;
        }
        assert!(low_and_high.0 && low_and_high.1, "starty tylko po jednej stronie zakazu");
    }

    #[test]
    fn current_point_reproduces_the_session_colors() {
        let mut doc = bare(3);
        doc["slots"][2]["rules"]["hue"] =
            rule(json!({"lo": 330.0, "hi": 40.0, "exclude": []}), true);
        doc["slots"][2]["value"]["h"] = json!(10.0);
        // kolor spoza gamutu: nasycenie obcinane do największego
        doc["slots"][3]["value"] = json!({"l": 0.7, "c": 0.4, "h": 140.0});
        let session = parse(&doc);
        let p = Problem::compile(&session, &free_ids(&["a1", "a2", "a3"]));
        let mut x = vec![0.0; p.dim()];
        p.current(&mut x);
        let (lo, hi) = p.bounds();
        assert!((0..p.dim()).all(|i| x[i] >= lo[i] && x[i] <= hi[i]));
        let c = p.decode(&x);
        assert!((c[2][2] - 10.0).abs() < 1e-9 && (c[2][1] - 0.1).abs() < 1e-12);
        assert_eq!(x[4], 1.0);
        assert!(color::in_gamut(c[3]) && (c[3][1] - color::max_chroma(0.7, 140.0)).abs() < 1e-9);
        assert!((c[4][1] - 0.1).abs() < 1e-12 && (c[4][0] - 0.7).abs() < 1e-12);
    }

    #[test]
    fn score_equals_the_report_and_counts_fixed_colors() {
        let session = parse(&everything("ok", "wcag21"));
        let p = Problem::compile(&session, &free_ids(&["a1", "a2", "a3"]));
        let mut rng = Rng::new(8, 0);
        for _ in 0..50 {
            let x = interior(&p, &mut rng);
            let report = p.evaluate(&x);
            let score = p.score(&x);
            let tol = 1e-9 * report.objective.abs().max(1.0);
            assert!(
                (score.total - report.objective).abs() <= tol,
                "{} / {}",
                score.total,
                report.objective
            );
            assert_eq!(score.feasible, !report.violations.iter().any(|v| v.hard));
        }
        // ocena bieżących wartości = ocena sesji
        let mut x = vec![0.0; p.dim()];
        p.current(&mut x);
        let whole = evaluate(&session);
        let here = p.evaluate(&x);
        assert!((whole.objective - here.objective).abs() <= 1e-6 * whole.objective.max(1.0));
        // termy samych kolorów stałych (np. jasność tekstu) nie wchodzą do value_grad
        let mut grad = vec![0.0; p.dim()];
        let with_margin = p.value_grad(&x, &mut grad);
        assert!(with_margin.is_finite());
        let only_fixed = Problem::compile(&session, &[]);
        assert_eq!(only_fixed.dim(), 0);
        assert!((only_fixed.score(&[]).total - whole.objective).abs() <= 1e-9 * whole.objective);
        assert_eq!(only_fixed.value_grad(&[], &mut []), 0.0);
    }

    #[test]
    fn degenerate_colors_give_finite_value_and_gradient() {
        for (delta_e, metric) in
            [("ok", "wcag21"), ("2000", "apca"), ("itp", "wcag21"), ("cam16", "apca")]
        {
            let session = parse(&everything(delta_e, metric));
            let p =
                Problem::compile(&session, &free_ids(&["bg", "fg", "a1", "a2", "a3", "a4", "a5"]));
            let (lo, hi) = p.bounds();
            let mut rng = Rng::new(2, 0);
            let base = interior(&p, &mut rng);
            let clamp = |x: &mut [f64]| {
                for i in 0..x.len() {
                    x[i] = x[i].max(lo[i]).min(hi[i]);
                }
            };
            let mut cases: Vec<Vec<f64>> = Vec::new();
            // wszystkie szare; wszystkie czarne; wszystkie białe (w granicach zmiennych)
            for (l, u) in
                [(None, Some(0.0)), (Some(0.0), None), (Some(1.0), None), (Some(0.0), Some(0.0))]
            {
                let mut x = base.clone();
                for k in 0..x.len() / 3 {
                    if let Some(l) = l {
                        x[3 * k] = l;
                    }
                    if let Some(u) = u {
                        x[3 * k + 1] = u;
                    }
                }
                clamp(&mut x);
                cases.push(x);
            }
            // dwa akcenty identyczne (a2 = a3) i wszystkie akcenty identyczne
            let mut twins = base.clone();
            let (a2, a3) = (9, 12);
            twins.copy_within(a2..a2 + 3, a3);
            cases.push(twins);
            let mut same = base.clone();
            for k in 3..7 {
                same.copy_within(6..9, 3 * k);
            }
            cases.push(same);

            let mut grad = vec![0.0; p.dim()];
            for x in &cases {
                let f = p.value_grad(x, &mut grad);
                assert!(f.is_finite(), "{delta_e}/{metric}: wartość {f} w {x:?}");
                assert!(grad.iter().all(|g| g.is_finite()), "{delta_e}/{metric}: {grad:?}");
                let score = p.score(x);
                assert!(score.total.is_finite());
                let report = p.evaluate(x);
                assert!(
                    report
                        .violations
                        .iter()
                        .all(|v| v.amount.is_finite() && v.achieved.is_finite())
                );
                let others = vec![p.prepare(x)];
                let pen = p.repulsion(x, &others, 0.05, &mut grad);
                assert!(pen.is_finite() && grad.iter().all(|g| g.is_finite()));
            }
        }
    }

    #[test]
    fn proposals_carry_free_colors_scores_and_diversity_violations() {
        // jeden akcent z twardym, wąskim zakresem: różnych rozwiązań nie ma
        let mut doc = bare(2);
        doc["slots"][2]["rules"]["lightness"] =
            rule(json!({"lo": 0.699, "hi": 0.701, "exclude": []}), true);
        doc["slots"][2]["rules"]["chroma"] =
            rule(json!({"mode": "rel", "lo": 0.5, "hi": 0.501, "exclude": []}), true);
        doc["slots"][2]["rules"]["hue"] =
            rule(json!({"lo": 40.0, "hi": 40.5, "exclude": []}), true);
        doc["globals"]["optimizer"]["n_proposals"] = json!(3);
        doc["globals"]["optimizer"]["budget"] = json!(200);
        doc["globals"]["optimizer"]["min_diversity"] = json!(0.2);
        let session = parse(&doc);
        let p = Problem::compile(&session, &free_ids(&["a1"]));
        let opts = driver_opts(&session, &p);
        assert_eq!((opts.n, opts.budget, opts.seed, opts.min_diversity), (3, 200, 0, 0.2));
        assert_eq!(opts.time_cap, Duration::from_secs(30));
        let outcome = generate(&p, &opts, &Control::new());
        let list = proposals(&p, &outcome, opts.min_diversity);
        assert_eq!(list.len(), 3);
        for (i, prop) in list.iter().enumerate() {
            assert_eq!(prop.values.len(), 1);
            assert_eq!(prop.values[0].0, "a1");
            assert!(color::in_gamut(prop.values[0].1));
            assert!(prop.feasible());
            assert_eq!(prop.score, p.evaluate(&outcome.chosen[i].x).objective);
            let diversity: Vec<&Violation> =
                prop.violations.iter().filter(|v| v.kind == ViolationKind::Diversity).collect();
            if i == 0 {
                assert!(
                    diversity.is_empty(),
                    "najlepsza propozycja nie ma naruszenia różnorodności"
                );
            } else {
                let v = diversity[0];
                assert!(!v.hard && v.key == "global:diversity" && v.slots == ["a1"]);
                assert!(v.achieved < 0.2 && (v.amount - (0.2 - v.achieved)).abs() < 1e-12);
                assert_eq!(serde_json::to_value(&v.req).unwrap(), json!({"min": 0.2}));
            }
        }
        // bez kolorów wolnych: jedna propozycja
        let fixed = Problem::compile(&session, &[]);
        assert_eq!(driver_opts(&session, &fixed).n, 1);
        let outcome = generate(&fixed, &driver_opts(&session, &fixed), &Control::new());
        let list = proposals(&fixed, &outcome, 0.2);
        assert_eq!(list.len(), 1);
        assert!(list[0].values.is_empty());
        assert_eq!(list[0].violations, evaluate(&session).violations);
        // limit czasu 0 s = bez limitu
        doc["globals"]["optimizer"]["time_cap_s"] = json!(0.0);
        let session = parse(&doc);
        assert_eq!(driver_opts(&session, &p).time_cap, Duration::MAX);
        // limit bliski zera: natychmiastowy limit, brak propozycji, wynik oznaczony
        doc["globals"]["optimizer"]["time_cap_s"] = json!(1e-9);
        let session = parse(&doc);
        let outcome = generate(&p, &driver_opts(&session, &p), &Control::new());
        assert!(outcome.timed_out && proposals(&p, &outcome, 0.2).is_empty());
    }

    #[test]
    fn optimizer_solves_a_simple_session() {
        let mut doc = bare(4);
        for i in 2..6 {
            let rules = &mut doc["slots"][i]["rules"];
            rules["lightness"] =
                rule(json!({"lo": 0.6, "hi": 0.85, "exclude": [[0.70, 0.74]]}), true);
            rules["chroma"] =
                rule(json!({"mode": "abs", "lo": 0.06, "hi": 0.2, "exclude": []}), true);
            rules["contrast_bg"] = rule(json!({"metric": null, "lo": 4.5, "hi": null}), true);
            rules["min_distance"] = rule(json!(0.08), true);
        }
        let session = parse(&doc);
        let ids = free_ids(&["a1", "a2", "a3", "a4"]);
        let p = Problem::compile(&session, &ids);
        let opts = DriverOpts {
            n: 4,
            seed: 0,
            budget: 1500,
            time_cap: Duration::from_secs(30),
            min_diversity: 0.05,
            threads: 4,
        };
        let outcome = generate(&p, &opts, &Control::new());
        assert_eq!(outcome.chosen.len(), 4);
        for c in &outcome.chosen {
            assert!(c.score.feasible, "przebieg {}: {:?}", c.run, p.evaluate(&c.x).violations);
            let colors = p.decode(&c.x);
            for lch in &colors[2..] {
                assert!(color::in_gamut(*lch));
                assert!(!(lch[0] > 0.70 && lch[0] < 0.74), "jasność w zakazie: {}", lch[0]);
            }
            assert!(p.evaluate(&c.x).violations.is_empty());
        }
    }
}
