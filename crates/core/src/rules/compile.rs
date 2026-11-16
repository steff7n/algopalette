//! Kompilacja sesji `algopalette.v2` do listy termów (port `compile_terms@4b71aeb` + spec §7.2).
//!
//! Kolejność termów: zasady kolorów (jasność, nasycenie, odcień — każda ze swoimi zakazami —
//! kontrast z tłem, skrajny kontrast), pary akcentów, zależności, rozrzut jasności, układ
//! odcieni, unikane kolory, gamut. Termy dotyczące wyłącznie kolorów pod kłódką są pomijane,
//! tak samo zależności wyłączone i zerwane (cel nie istnieje).

use serde_json::{Map, Value, json};

use crate::color::{self, ContrastMetric, CvdKind, DeltaE};
use crate::schema::{ChromaMode, ChromaOp, Extreme, RelKind, Relation, Rule, Session};
use crate::violation::{
    KEY_SPREAD, ViolationKind, key_avoid, key_exclude, key_pair_cvd, key_pair_distance, key_rel,
    key_scheme, key_slot,
};

use super::hues;
use super::terms::{
    Body, Chan, Cvd, Floor, Quantity, SCALE_C_ABS, SCALE_C_REL, SCALE_H, SCALE_L, Term, arc_width,
    scale_contrast, scale_de,
};

/// Sesja po kompilacji: kolory w kolejności dokumentu i termy.
#[derive(Debug, Clone)]
pub(crate) struct Compiled {
    pub ids: Vec<String>,
    /// Wartości OKLCH kolorów z dokumentu.
    pub values: Vec<[f64; 3]>,
    pub terms: Vec<Term>,
    /// Cel układu odcieni koloru (tylko akcenty, gdy układ daje cele).
    pub targets: Vec<Option<f64>>,
    pub hard_weight: f64,
}

fn obj(pairs: &[(&str, Value)]) -> Map<String, Value> {
    pairs.iter().map(|(k, v)| ((*k).to_owned(), v.clone())).collect()
}

fn enabled<T>(rule: &Option<Rule<T>>) -> Option<&Rule<T>> {
    rule.as_ref().filter(|r| r.enabled)
}

/// Twarde dolne granice nasycenia kolorów (dla wygaszania odcienia).
fn chroma_floors(session: &Session) -> Vec<Floor> {
    session
        .slots
        .iter()
        .map(|slot| match enabled(&slot.rules.chroma) {
            Some(r) if r.hard => match r.value.lo {
                Some(lo) if lo > 0.0 => match r.value.mode {
                    ChromaMode::Abs => Floor { abs: lo, rel: 0.0 },
                    ChromaMode::Rel => Floor { abs: 0.0, rel: lo },
                },
                _ => Floor::default(),
            },
            _ => Floor::default(),
        })
        .collect()
}

struct Builder<'a> {
    session: &'a Session,
    locked: Vec<bool>,
    terms: Vec<Term>,
}

impl Builder<'_> {
    #[allow(clippy::too_many_arguments)]
    fn add(
        &mut self,
        key: String,
        kind: ViolationKind,
        report: Vec<usize>,
        slots: Vec<usize>,
        (hard, weight, scale): (bool, f64, f64),
        body: Body,
        req: Map<String, Value>,
        meta: Map<String, Value>,
    ) {
        // term samych kłódek niczego nie może zmienić — pomijany także w ocenie
        if !report.is_empty() && report.iter().all(|&i| self.locked[i]) {
            return;
        }
        self.terms.push(Term { key, kind, report, hard, weight, scale, body, slots, req, meta });
    }

    fn id(&self, i: usize) -> &str {
        &self.session.slots[i].id
    }

    /// Zakazane przedziały jednego kanału: zawsze twarde, bez wagi.
    fn exclusions(&mut self, i: usize, chan: Chan, pairs: &[[f64; 2]], floor: Floor) {
        for (k, &[a, b]) in pairs.iter().enumerate() {
            let hi = if chan == Chan::H { a + (b - a).rem_euclid(360.0) } else { b };
            let mut meta = obj(&[("channel", json!(chan.name()))]);
            match chan {
                Chan::CAbs => drop(meta.insert("mode".into(), json!("abs"))),
                Chan::CRel => drop(meta.insert("mode".into(), json!("rel"))),
                _ => {}
            }
            self.add(
                key_exclude(self.id(i), chan.name(), k),
                ViolationKind::Exclude,
                vec![i],
                vec![i],
                (true, 1.0, chan.scale()),
                Body::Exclude { chan, lo: a, hi, floor },
                obj(&[("lo", json!(a)), ("hi", json!(b))]),
                meta,
            );
        }
    }

    fn slot_rules(&mut self, i: usize, floors: &[Floor], accents: &[usize]) {
        let session = self.session;
        let rules = &session.slots[i].rules;
        let metric_g = session.globals.contrast_metric;
        let floor = floors[i];
        if let Some(r) = enabled(&rules.lightness) {
            self.add(
                key_slot(self.id(i), ViolationKind::Lightness),
                ViolationKind::Lightness,
                vec![i],
                vec![i],
                (r.hard, r.weight, SCALE_L),
                Body::Interval { chan: Chan::L, lo: r.value.lo, hi: r.value.hi },
                obj(&[("lo", json!(r.value.lo)), ("hi", json!(r.value.hi))]),
                Map::new(),
            );
            self.exclusions(i, Chan::L, &r.value.exclude, floor);
        }
        if let Some(r) = enabled(&rules.chroma) {
            let chan = if r.value.mode == ChromaMode::Rel { Chan::CRel } else { Chan::CAbs };
            self.add(
                key_slot(self.id(i), ViolationKind::Chroma),
                ViolationKind::Chroma,
                vec![i],
                vec![i],
                (r.hard, r.weight, chan.scale()),
                Body::Interval { chan, lo: r.value.lo, hi: r.value.hi },
                obj(&[("lo", json!(r.value.lo)), ("hi", json!(r.value.hi))]),
                obj(&[("mode", json!(r.value.mode))]),
            );
            self.exclusions(i, chan, &r.value.exclude, floor);
        }
        if let Some(r) = enabled(&rules.hue) {
            self.add(
                key_slot(self.id(i), ViolationKind::Hue),
                ViolationKind::Hue,
                vec![i],
                vec![i],
                (r.hard, r.weight, SCALE_H),
                Body::HueArc { lo: r.value.lo, width: arc_width(r.value.lo, r.value.hi), floor },
                obj(&[("lo", json!(r.value.lo)), ("hi", json!(r.value.hi))]),
                Map::new(),
            );
            self.exclusions(i, Chan::H, &r.value.exclude, floor);
        }
        if i >= 1
            && let Some(r) = enabled(&rules.contrast_bg)
        {
            let metric = r.value.metric.unwrap_or(metric_g);
            self.add(
                key_slot(self.id(i), ViolationKind::ContrastBg),
                ViolationKind::ContrastBg,
                vec![i, 0],
                vec![i, 0],
                (r.hard, r.weight, scale_contrast(metric)),
                Body::Contrast { metric, lo: r.value.lo, hi: r.value.hi },
                obj(&[("lo", json!(r.value.lo)), ("hi", json!(r.value.hi))]),
                obj(&[("metric", json!(metric))]),
            );
        }
        if i >= 2
            && let Some(r) = enabled(&rules.extreme)
        {
            let others: Vec<usize> = accents.iter().copied().filter(|&j| j != i).collect();
            if !others.is_empty() {
                let report: Vec<usize> = std::iter::once(i).chain(others.iter().copied()).collect();
                let mut slots = report.clone();
                slots.push(0);
                self.add(
                    key_slot(self.id(i), ViolationKind::Extreme),
                    ViolationKind::Extreme,
                    report,
                    slots,
                    (r.hard, r.weight, scale_contrast(metric_g)),
                    Body::Extreme {
                        weakest: r.value == Extreme::Weakest,
                        metric: metric_g,
                        others,
                        bg: 0,
                    },
                    Map::new(),
                    obj(&[("which", json!(r.value)), ("metric", json!(metric_g))]),
                );
            }
        }
    }

    /// Para akcentów: próg = max z obu kolorów, twarda, gdy którakolwiek; waga = max.
    fn pair(&mut self, i: usize, j: usize, cvd: Option<CvdKind>) {
        let session = self.session;
        let pick = |k: usize| {
            let rules = &session.slots[k].rules;
            enabled(if cvd.is_some() { &rules.cvd_min_distance } else { &rules.min_distance })
        };
        let reqs: Vec<&Rule<f64>> = [pick(i), pick(j)].into_iter().flatten().collect();
        if reqs.is_empty() {
            return;
        }
        let min = reqs.iter().fold(f64::NEG_INFINITY, |m, r| m.max(r.value));
        let hard = reqs.iter().any(|r| r.hard);
        let weight = reqs.iter().fold(f64::NEG_INFINITY, |m, r| m.max(r.weight));
        let method = session.globals.delta_e;
        let g = &session.globals.cvd;
        let (key, kind, meta) = match cvd {
            None => (
                key_pair_distance(self.id(i), self.id(j)),
                ViolationKind::PairDistance,
                obj(&[("method", json!(method))]),
            ),
            Some(kind) => {
                let name = json!(kind);
                (
                    key_pair_cvd(self.id(i), self.id(j), name.as_str().unwrap_or_default()),
                    ViolationKind::PairCvd,
                    obj(&[("method", json!(method)), ("cvd", name)]),
                )
            }
        };
        let cvd = cvd.map(|kind| Cvd { kind, method: g.method, severity: g.severity });
        self.add(
            key,
            kind,
            vec![i, j],
            vec![i, j],
            (hard, weight, scale_de(method)),
            Body::Pair { min, method, cvd },
            obj(&[("min", json!(min))]),
            meta,
        );
    }

    fn relation(&mut self, i: usize, n: usize, rel: &Relation, floors: &[Floor]) {
        let session = self.session;
        let index = |id: &str| session.slots.iter().position(|s| s.id == id);
        let Some(j) = index(&rel.target) else { return };
        let (op, value, tol) = (rel.op, rel.value, rel.tol);
        let mut slots = vec![i, j];
        let mut metric_name = Value::Null;
        let (scale, body) = match rel.kind {
            RelKind::Hue => {
                (SCALE_H, Body::RelHue { op, value, tol, floors: [floors[i], floors[j]] })
            }
            RelKind::Lightness => {
                (SCALE_L, Body::RelLinear { quantity: Quantity::Lightness, op, value, tol })
            }
            RelKind::Chroma => {
                let rel_mode = rel.chroma_mode == ChromaMode::Rel;
                let quantity =
                    Quantity::Chroma { rel: rel_mode, mul: rel.chroma_op == ChromaOp::Mul };
                (
                    if rel_mode { SCALE_C_REL } else { SCALE_C_ABS },
                    Body::RelLinear { quantity, op, value, tol },
                )
            }
            RelKind::Contrast => {
                let metric: ContrastMetric = rel
                    .metric
                    .and_then(|m| m.as_contrast())
                    .unwrap_or(session.globals.contrast_metric);
                metric_name = json!(metric);
                (scale_contrast(metric), Body::RelContrast { metric, op, value, tol })
            }
            RelKind::Distance => {
                let method: DeltaE =
                    rel.metric.and_then(|m| m.as_delta_e()).unwrap_or(session.globals.delta_e);
                metric_name = json!(method);
                (scale_de(method), Body::RelDistance { method, op, value, tol })
            }
            RelKind::Mix => {
                let Some(k) = rel.other.as_deref().and_then(index) else { return };
                slots.push(k);
                (scale_de(DeltaE::Ok), Body::RelMix { t: rel.t, tol })
            }
        };
        let kind_name = json!(rel.kind);
        self.add(
            key_rel(self.id(i), kind_name.as_str().unwrap_or_default(), n),
            ViolationKind::Rel,
            slots.clone(),
            slots,
            (rel.hard, rel.weight, scale),
            body,
            obj(&[("op", json!(op)), ("value", json!(value)), ("tol", json!(tol))]),
            obj(&[
                ("rel_kind", kind_name),
                ("chroma_op", json!(rel.chroma_op)),
                ("chroma_mode", json!(rel.chroma_mode)),
                ("metric", metric_name),
            ]),
        );
    }
}

/// Kompiluje sesję do termów.
pub(crate) fn compile(session: &Session) -> Compiled {
    let g = &session.globals;
    let n = session.slots.len();
    let accents: Vec<usize> = (2..n).collect();
    let floors = chroma_floors(session);
    let mut targets: Vec<Option<f64>> = vec![None; n];
    let scheme_targets = hues::scheme_targets(&g.hue_scheme, accents.len(), g.optimizer.seed);
    for (&i, &t) in accents.iter().zip(&scheme_targets) {
        targets[i] = Some(t);
    }

    let mut b = Builder {
        session,
        locked: session.slots.iter().map(|s| s.locked).collect(),
        terms: Vec::new(),
    };
    for i in 0..n {
        b.slot_rules(i, &floors, &accents);
    }

    // Pary akcentów: minimalna odległość i odróżnialność przy daltonizmie.
    let mut kinds = g.cvd.types.clone();
    kinds.sort_by_key(|k| json!(k).as_str().unwrap_or_default().to_owned());
    kinds.dedup();
    for (pos, &i) in accents.iter().enumerate() {
        for &j in &accents[pos + 1..] {
            b.pair(i, j, None);
            for &kind in &kinds {
                b.pair(i, j, Some(kind));
            }
        }
    }

    for (i, slot) in session.slots.iter().enumerate() {
        for (r_i, rel) in slot.relations.iter().enumerate() {
            if rel.enabled {
                b.relation(i, r_i, rel, &floors);
            }
        }
    }

    if let Some(sp) = enabled(&g.lightness_spread)
        && accents.len() >= 2
    {
        b.add(
            KEY_SPREAD.to_owned(),
            ViolationKind::Spread,
            accents.clone(),
            accents.clone(),
            (sp.hard, sp.weight, SCALE_L),
            Body::Spread { accents: accents.clone(), lo: sp.value.lo, hi: sp.value.hi },
            obj(&[("lo", json!(sp.value.lo)), ("hi", json!(sp.value.hi))]),
            Map::new(),
        );
    }

    // Układ odcieni: cel dla każdego akcentu z `use_scheme`, niezależnie od własnej zasady odcienia.
    let scheme = &g.hue_scheme;
    for &i in &accents {
        let Some(target) = targets[i] else { continue };
        if !session.slots[i].use_scheme {
            continue;
        }
        b.add(
            key_scheme(b.id(i)),
            ViolationKind::Scheme,
            vec![i],
            vec![i],
            (scheme.hard, scheme.weight, SCALE_H),
            Body::Scheme { target, tol: scheme.tol, floor: floors[i] },
            obj(&[("target", json!(target)), ("tol", json!(scheme.tol))]),
            Map::new(),
        );
    }

    // Unikane kolory (tryb „charakter”): zawsze twarde, ΔE ok.
    if !g.avoid_colors.is_empty() && g.avoid_distance > 0.0 {
        for &i in &accents {
            for (k, src) in g.avoid_colors.iter().enumerate() {
                b.add(
                    key_avoid(b.id(i), k),
                    ViolationKind::Avoid,
                    vec![i],
                    vec![i],
                    (true, 1.0, scale_de(DeltaE::Ok)),
                    Body::Avoid {
                        reference: color::oklch_to_oklab([src.l, src.c, src.h]),
                        min: g.avoid_distance,
                    },
                    obj(&[("min", json!(g.avoid_distance))]),
                    Map::new(),
                );
            }
        }
    }

    // Gamut dla kolorów bez kłódki.
    for i in 0..n {
        if !session.slots[i].locked {
            b.add(
                key_slot(b.id(i), ViolationKind::Gamut),
                ViolationKind::Gamut,
                vec![i],
                vec![i],
                (true, 1.0, SCALE_C_ABS),
                Body::Gamut,
                Map::new(),
                Map::new(),
            );
        }
    }

    Compiled {
        ids: session.slots.iter().map(|s| s.id.clone()).collect(),
        values: session.slots.iter().map(|s| [s.value.l, s.value.c, s.value.h]).collect(),
        terms: b.terms,
        targets,
        hard_weight: g.optimizer.hard_weight,
    }
}
