//! Ocena termów na konkretnych kolorach: wartości naruszeń i raport dla Pythona.
//!
//! [`Frame`] to kolory jednej palety razem z wielkościami liczonymi raz na kolor, a używanymi
//! przez wiele termów (kontrast akcentów z tłem dla zasad „skrajny kontrast”, współrzędne ΔE
//! akcentów — także po symulacji CVD — dla termów par).

use serde_json::json;

use crate::color::{self, ContrastMetric, DeltaE};
use crate::objective::FEASIBLE_EPS;
use crate::schema::Session;
use crate::violation::Violation;

use super::compile::{Compiled, compile};
use super::terms::{Body, Col, Cvd, Term};

/// Wynik oceny bieżących wartości sesji.
#[derive(Debug, Clone, PartialEq)]
pub struct Evaluation {
    /// Funkcja celu bez marginesu twardych zasad.
    pub objective: f64,
    /// Naruszone zasady (wielkość > 1e-9), w kolejności kompilacji.
    pub violations: Vec<Violation>,
}

/// Co trzeba policzyć raz na paletę, żeby ocenić termy.
#[derive(Debug, Clone, Default, PartialEq)]
pub(crate) struct Needs {
    /// Metryka zasad „skrajny kontrast” (kontrast każdego akcentu z tłem).
    pub extreme: Option<ContrastMetric>,
    /// Metoda ΔE termów par (ta sama dla wszystkich: globalna).
    pub pair_method: Option<DeltaE>,
    /// Czy są pary bez symulacji CVD.
    pub pair_plain: bool,
    /// Symulacje CVD używane przez pary.
    pub cvds: Vec<Cvd>,
}

impl Needs {
    pub fn of(terms: &[Term]) -> Self {
        let mut needs = Self::default();
        for term in terms {
            match &term.body {
                Body::Extreme { metric, .. } => needs.extreme = Some(*metric),
                Body::Pair { method, cvd, .. } => {
                    needs.pair_method = Some(*method);
                    match cvd {
                        None => needs.pair_plain = true,
                        Some(c) if !needs.cvds.contains(c) => needs.cvds.push(*c),
                        Some(_) => {}
                    }
                }
                _ => {}
            }
        }
        needs
    }
}

/// Kolory, od których term zależy przy tej ocenie (najwyżej trzy).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct Active {
    pub slots: [usize; 3],
    pub len: usize,
}

impl Active {
    fn of(slots: &[usize]) -> Self {
        let mut out = Self { slots: [0; 3], len: slots.len() };
        out.slots[..slots.len()].copy_from_slice(slots);
        out
    }

    pub fn as_slice(&self) -> &[usize] {
        &self.slots[..self.len]
    }
}

/// Kolory jednej palety z wielkościami wspólnymi dla wielu termów.
#[derive(Debug, Clone)]
pub(crate) struct Frame {
    pub cols: Vec<Col<f64>>,
    /// Kontrast koloru z tłem w metryce zasad „skrajny kontrast” (akcenty).
    bg_contrast: Vec<f64>,
    /// Współrzędne ΔE akcentów bez symulacji.
    prep: Vec<[f64; 3]>,
    /// Współrzędne ΔE akcentów po każdej symulacji CVD.
    prep_cvd: Vec<(Cvd, Vec<[f64; 3]>)>,
}

impl Frame {
    pub fn new(cols: Vec<Col<f64>>, needs: &Needs) -> Self {
        let n = cols.len();
        let accents = 2.min(n)..n;
        let mut bg_contrast = Vec::new();
        if let Some(metric) = needs.extreme {
            bg_contrast = vec![f64::NAN; n];
            for i in accents.clone() {
                bg_contrast[i] = color::contrast(cols[i].lab, cols[0].lab, metric);
            }
        }
        let mut prep = Vec::new();
        let mut prep_cvd = Vec::new();
        if let Some(method) = needs.pair_method {
            if needs.pair_plain {
                prep = vec![[f64::NAN; 3]; n];
                for i in accents.clone() {
                    prep[i] = color::prepare(cols[i].lab, method);
                }
            }
            for cvd in &needs.cvds {
                let mut sim = vec![[f64::NAN; 3]; n];
                for i in accents.clone() {
                    let lab = color::simulate_cvd(cols[i].lab, cvd.kind, cvd.method, cvd.severity);
                    sim[i] = color::prepare(lab, method);
                }
                prep_cvd.push((*cvd, sim));
            }
        }
        Self { cols, bg_contrast, prep, prep_cvd }
    }

    /// Kolory, od których term zależy przy tych wartościach. Dla „skrajnego kontrastu” to
    /// [własny, akcent o najmniejszym / największym kontraście, tło]; dla rozrzutu jasności
    /// [najjaśniejszy, najciemniejszy akcent]. Remisy rozstrzyga kolejność kolorów.
    pub fn active(&self, term: &Term) -> Active {
        match &term.body {
            Body::Extreme { weakest, others, bg, .. } => {
                let mut pick = others[0];
                for &j in &others[1..] {
                    let (cj, cp) = (self.bg_contrast[j], self.bg_contrast[pick]);
                    if (*weakest && cj < cp) || (!*weakest && cj > cp) {
                        pick = j;
                    }
                }
                Active::of(&[term.slots[0], pick, *bg])
            }
            Body::Spread { accents, .. } => {
                let (mut hi, mut lo) = (accents[0], accents[0]);
                for &j in &accents[1..] {
                    if self.cols[j].l > self.cols[hi].l {
                        hi = j;
                    }
                    if self.cols[j].l < self.cols[lo].l {
                        lo = j;
                    }
                }
                Active::of(&[hi, lo])
            }
            _ => Active::of(&term.slots),
        }
    }

    fn cols_of(&self, active: &Active) -> [Col<f64>; 3] {
        let pick = |k: usize| self.cols[active.slots[k.min(active.len.saturating_sub(1))]];
        [pick(0), pick(1), pick(2)]
    }

    /// Naruszenie termu przy marginesie `m`.
    pub fn violation(&self, term: &Term, active: &Active, m: f64) -> f64 {
        match &term.body {
            Body::Pair { min, method, cvd } => {
                let table = match cvd {
                    None => &self.prep,
                    Some(c) => {
                        let found = self.prep_cvd.iter().find(|(k, _)| k == c);
                        &found.expect("symulacja CVD przygotowana przy budowie ramki").1
                    }
                };
                let d = color::delta_e_prepared(
                    table[active.slots[0]],
                    table[active.slots[1]],
                    *method,
                );
                (min + m - d).max(0.0)
            }
            Body::Extreme { weakest, .. } => {
                let own = self.bg_contrast[active.slots[0]];
                let other = self.bg_contrast[active.slots[1]];
                (if *weakest { own - other + m } else { other - own + m }).max(0.0)
            }
            body => body.violation(&self.cols_of(active)[..active.len], m),
        }
    }

    /// Funkcja celu (bez marginesu) i naruszenia wszystkich termów.
    pub fn report(&self, compiled: &Compiled) -> Evaluation {
        let mut objective = 0.0;
        let mut violations = Vec::new();
        for term in &compiled.terms {
            let active = self.active(term);
            let amount = self.violation(term, &active, 0.0);
            objective += term.coefficient(compiled.hard_weight) * amount * amount;
            if amount > FEASIBLE_EPS {
                violations.push(self.describe(compiled, term, &active, amount));
            }
        }
        Evaluation { objective, violations }
    }

    fn describe(
        &self,
        compiled: &Compiled,
        term: &Term,
        active: &Active,
        amount: f64,
    ) -> Violation {
        let cols = self.cols_of(active);
        let cols = &cols[..active.len];
        let mut req = term.req.clone();
        match &term.body {
            Body::Extreme { .. } => {
                req.insert("bound".into(), json!(self.bg_contrast[active.slots[1]]));
            }
            Body::Gamut => {
                req.insert("hi".into(), json!(cols[0].maxc));
            }
            _ => {}
        }
        Violation {
            key: term.key.clone(),
            slots: term.report.iter().map(|&i| compiled.ids[i].clone()).collect(),
            kind: term.kind,
            hard: term.hard,
            amount,
            achieved: term.body.achieved(cols),
            req,
            meta: term.meta.clone(),
        }
    }
}

/// Ocenia wartości kolorów z sesji: funkcja celu bez marginesu i lista naruszeń.
pub fn evaluate(session: &Session) -> Evaluation {
    let compiled = compile(session);
    let cols = compiled.values.iter().map(|&lch| Col::fixed(lch)).collect();
    Frame::new(cols, &Needs::of(&compiled.terms)).report(&compiled)
}
