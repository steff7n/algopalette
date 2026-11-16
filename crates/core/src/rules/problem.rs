//! Problem optymalizacji palety: zmienne kolorów wolnych, granice, funkcja celu z gradientem.
//!
//! Zmienne koloru wolnego to `(L, u, H / 100)`: `C = u · max_chroma(L, H)`, więc kolor z
//! definicji leży w sRGB, a nasycenie względne to po prostu `u`. Odcień jest dzielony przez
//! [`HUE_UNIT`], żeby wszystkie zmienne miały podobną skalę (1° odcienia waży w funkcji celu
//! tyle co 0,01 jasności). Twarde zakresy jasności, nasycenia względnego i odcienia są
//! granicami zmiennych; odcień bez twardego łuku nie ma granic (zmienna okresowa).
//!
//! Gradient jest dokładny: każdy naruszony term liczy się drugi raz na liczbach dualnych z
//! lokalnymi zmiennymi swoich kolorów (3 na kolor), a pochodne trafiają do gradientu regułą
//! łańcuchową. Termy spełnione kosztują tylko wyliczenie wartości. „Skrajny kontrast” i
//! rozrzut jasności różniczkują się przez wybór aktywnego elementu (podgradient).

use crate::color;
use crate::objective::{FEASIBLE_EPS, Objective, Score};
use crate::rng::Rng;
use crate::scalar::Dual;
use crate::schema::{ChromaMode, Session};
use crate::violation::Violation;

use super::compile::{Compiled, compile};
use super::eval::{Active, Evaluation, Frame, Needs};
use super::terms::{Col, Term, arc_width};

/// Stopnie odcienia na jednostkę zmiennej.
pub const HUE_UNIT: f64 = 100.0;
/// Skala kary za zbyt małą różnorodność (jak ΔE ok).
const DIVERSITY_SCALE: f64 = 0.01;
/// Próby losowania nasycenia poza zakazem nasycenia bezwzględnego.
const SAMPLE_TRIES: usize = 64;

/// Opis losowania i granic jednego koloru wolnego.
#[derive(Debug, Clone)]
struct FreeColor {
    slot: usize,
    l: (f64, f64),
    u: (f64, f64),
    /// Twarde granice odcienia w stopniach `[lo, hi]` (`hi − lo < 360`); `None` = bez granic.
    hue_bounds: Option<(f64, f64)>,
    /// Zakres losowania odcienia w stopniach.
    hue_sample: (f64, f64),
    excl_l: Vec<[f64; 2]>,
    excl_c: Vec<[f64; 2]>,
    excl_c_rel: bool,
    /// Zakazy odcienia jako (początek, szerokość).
    excl_h: Vec<(f64, f64)>,
}

/// Skompilowana sesja z wybranymi kolorami wolnymi.
#[derive(Debug, Clone)]
pub struct Problem {
    compiled: Compiled,
    needs: Needs,
    free: Vec<FreeColor>,
    free_ids: Vec<String>,
    /// Pozycja koloru wśród wolnych.
    free_pos: Vec<Option<usize>>,
    /// Kolory z dokumentu (wolne są nadpisywane przy każdej ocenie).
    base: Vec<Col<f64>>,
    /// Termy zależne od co najmniej jednego koloru wolnego.
    live: Vec<usize>,
    /// Wkład termów stałych w funkcję celu (bez marginesu).
    const_total: f64,
    /// Czy któryś term stały jest twardym naruszeniem.
    const_infeasible: bool,
    lower: Vec<f64>,
    upper: Vec<f64>,
}

/// Naruszony term razem z tym, co potrzebne do policzenia jego gradientu.
struct Hit<'a> {
    term: &'a Term,
    active: Active,
    /// Margines twardej zasady.
    m: f64,
    /// `2 · współczynnik · naruszenie` — mnożnik gradientu naruszenia.
    factor: f64,
}

/// Kolory wolne z pochodnymi po swoich zmiennych, liczone dopiero wtedy, gdy są potrzebne.
struct Duals<'a> {
    x: &'a [f64],
    cols: Vec<Option<Col<Dual<3>>>>,
}

impl Duals<'_> {
    fn col(&mut self, k: usize) -> &Col<Dual<3>> {
        let x = self.x;
        self.cols[k].get_or_insert_with(|| Problem::dual_col(x, k))
    }
}

fn inside_linear(x: f64, pairs: &[[f64; 2]]) -> bool {
    pairs.iter().any(|&[a, b]| x > a && x < b)
}

/// Zakazy odcienia (początek, szerokość) rozwinięte na oś liczbową w obrębie `range`.
fn unwrapped(arcs: &[(f64, f64)], range: (f64, f64)) -> Vec<[f64; 2]> {
    let mut out = Vec::new();
    for &(start, width) in arcs {
        let first = start - 360.0 * ((start - range.0) / 360.0).ceil();
        let mut a = first;
        while a < range.1 {
            if a + width > range.0 {
                out.push([a, a + width]);
            }
            a += 360.0;
        }
    }
    out
}

/// Losuje równomiernie z `range` bez wnętrz przedziałów `gaps`. Gdy zakazy pokrywają cały
/// zakres (zasada niespełnialna), losuje z całego zakresu.
fn sample_outside(rng: &mut Rng, range: (f64, f64), gaps: &[[f64; 2]]) -> f64 {
    if gaps.is_empty() {
        return rng.range(range.0, range.1);
    }
    // dozwolone odcinki: zakres minus suma zakazów
    let mut cuts: Vec<[f64; 2]> = gaps
        .iter()
        .map(|&[a, b]| [a.max(range.0), b.min(range.1)])
        .filter(|[a, b]| a < b)
        .collect();
    cuts.sort_by(|p, q| p[0].total_cmp(&q[0]));
    let mut allowed: Vec<[f64; 2]> = Vec::with_capacity(cuts.len() + 1);
    let mut at = range.0;
    for [a, b] in cuts {
        if a > at {
            allowed.push([at, a]);
        }
        at = at.max(b);
    }
    if at < range.1 {
        allowed.push([at, range.1]);
    }
    let total: f64 = allowed.iter().map(|[a, b]| b - a).sum();
    if total <= 0.0 {
        // zakazy pokrywają cały zakres
        return rng.range(range.0, range.1);
    }
    let mut t = rng.uniform() * total;
    for &[a, b] in &allowed {
        if t <= b - a {
            return a + t;
        }
        t -= b - a;
    }
    allowed[allowed.len() - 1][1]
}

impl Problem {
    /// Kompiluje sesję; `free` to id kolorów, które optymalizator może zmieniać (pozostałe
    /// są brane takie, jakie są w dokumencie). Nieznane id są pomijane.
    pub fn compile(session: &Session, free: &[String]) -> Problem {
        let compiled = compile(session);
        let n = compiled.ids.len();
        let scheme = &session.globals.hue_scheme;
        let mut free_pos = vec![None; n];
        let mut colors = Vec::new();
        let mut free_ids = Vec::new();
        for (i, slot) in session.slots.iter().enumerate() {
            if !free.contains(&slot.id) {
                continue;
            }
            free_pos[i] = Some(colors.len());
            free_ids.push(slot.id.clone());
            let rules = &slot.rules;
            let on = |enabled: bool, hard: bool| enabled && hard;

            let mut l = (0.0, 1.0);
            let mut excl_l = Vec::new();
            if let Some(r) = rules.lightness.as_ref().filter(|r| r.enabled) {
                excl_l = r.value.exclude.clone();
                if on(r.enabled, r.hard) {
                    let lo = r.value.lo.unwrap_or(0.0).max(0.0);
                    let hi = r.value.hi.unwrap_or(1.0).min(1.0);
                    // sprzeczny zakres zostaje karze, nie granicom
                    if lo <= hi {
                        l = (lo, hi);
                    }
                }
            }

            let mut u = (0.0, 1.0);
            let (mut excl_c, mut excl_c_rel) = (Vec::new(), false);
            if let Some(r) = rules.chroma.as_ref().filter(|r| r.enabled) {
                excl_c = r.value.exclude.clone();
                excl_c_rel = r.value.mode == ChromaMode::Rel;
                if on(r.enabled, r.hard) && excl_c_rel {
                    let lo = r.value.lo.unwrap_or(0.0).max(0.0);
                    let hi = r.value.hi.unwrap_or(1.0).min(1.0);
                    if lo <= hi {
                        u = (lo, hi);
                    }
                }
            }

            let mut hue_bounds = None;
            let mut hue_sample = (0.0, 360.0);
            let mut excl_h = Vec::new();
            let scheme_target = compiled.targets[i].filter(|_| slot.use_scheme);
            if let Some(t) = scheme_target {
                hue_sample = (t - scheme.tol, t + scheme.tol);
                if scheme.hard && 2.0 * scheme.tol < 360.0 {
                    hue_bounds = Some(hue_sample);
                }
            }
            if let Some(r) = rules.hue.as_ref().filter(|r| r.enabled) {
                excl_h =
                    r.value.exclude.iter().map(|&[a, b]| (a, (b - a).rem_euclid(360.0))).collect();
                let width = arc_width(r.value.lo, r.value.hi);
                if width < 360.0 {
                    // własny łuk (także miękki) wyznacza starty; twardy — granice
                    hue_sample = (r.value.lo, r.value.lo + width);
                    if r.hard {
                        hue_bounds = Some(hue_sample);
                    }
                }
            }
            if let Some(bounds) = hue_bounds {
                hue_sample = bounds;
            }
            colors.push(FreeColor {
                slot: i,
                l,
                u,
                hue_bounds,
                hue_sample,
                excl_l,
                excl_c,
                excl_c_rel,
                excl_h,
            });
        }

        let mut lower = Vec::with_capacity(3 * colors.len());
        let mut upper = Vec::with_capacity(3 * colors.len());
        for c in &colors {
            let (h_lo, h_hi) = match c.hue_bounds {
                Some((lo, hi)) => (lo / HUE_UNIT, hi / HUE_UNIT),
                None => (f64::NEG_INFINITY, f64::INFINITY),
            };
            lower.extend([c.l.0, c.u.0, h_lo]);
            upper.extend([c.l.1, c.u.1, h_hi]);
        }

        let base: Vec<Col<f64>> = compiled.values.iter().map(|&lch| Col::fixed(lch)).collect();
        let needs = Needs::of(&compiled.terms);
        let is_live = |term: &Term| term.slots.iter().any(|&s| free_pos[s].is_some());
        let live: Vec<usize> =
            (0..compiled.terms.len()).filter(|&k| is_live(&compiled.terms[k])).collect();

        // Termy bez kolorów wolnych są stałe: liczone raz, potrzebne tylko w ocenie końcowej.
        let frame = Frame::new(base.clone(), &needs);
        let (mut const_total, mut const_infeasible) = (0.0, false);
        for term in compiled.terms.iter().filter(|t| !is_live(t)) {
            let v = frame.violation(term, &frame.active(term), 0.0);
            const_total += term.coefficient(compiled.hard_weight) * v * v;
            const_infeasible |= term.hard && v > FEASIBLE_EPS;
        }

        Problem {
            compiled,
            needs,
            free: colors,
            free_ids,
            free_pos,
            base,
            live,
            const_total,
            const_infeasible,
            lower,
            upper,
        }
    }

    /// Id kolorów wolnych, w kolejności zmiennych.
    pub fn free_ids(&self) -> &[String] {
        &self.free_ids
    }

    /// Jasność, nasycenie względne i odcień (stopnie, [0, 360)) koloru wolnego nr `k`.
    fn vars(x: &[f64], k: usize) -> (f64, f64, f64) {
        let l = x[3 * k].clamp(0.0, 1.0);
        let u = x[3 * k + 1].clamp(0.0, 1.0);
        let h = (x[3 * k + 2] * HUE_UNIT).rem_euclid(360.0);
        (l, u, if h >= 360.0 { 0.0 } else { h })
    }

    /// OKLCH wszystkich kolorów; wolne — z `x`, zawsze w gamucie sRGB.
    pub fn decode(&self, x: &[f64]) -> Vec<[f64; 3]> {
        let mut out = self.compiled.values.clone();
        for (k, c) in self.free.iter().enumerate() {
            let (l, u, h) = Self::vars(x, k);
            let mut chroma = u * color::max_chroma(l, h);
            // brzeg gamutu wyznaczony do zaokrągleń: w razie potrzeby krok do środka
            while chroma > 0.0 && !color::in_gamut([l, chroma, h]) {
                chroma *= 1.0 - 1e-9;
            }
            out[c.slot] = [l, chroma, h];
        }
        out
    }

    fn cols(&self, x: &[f64]) -> Vec<Col<f64>> {
        let mut cols = self.base.clone();
        for (k, c) in self.free.iter().enumerate() {
            let (l, u, h) = Self::vars(x, k);
            cols[c.slot] = Col::from_vars(l, u, h);
        }
        cols
    }

    fn frame(&self, x: &[f64]) -> Frame {
        Frame::new(self.cols(x), &self.needs)
    }

    /// Kolor wolny nr `k` z pochodnymi po swoich trzech zmiennych.
    fn dual_col(x: &[f64], k: usize) -> Col<Dual<3>> {
        let (l, u, h) = Self::vars(x, k);
        // obcięcie i sprowadzenie odcienia do [0, 360) nie zmieniają pochodnych wewnątrz granic
        Col::from_vars(Dual::var(l, 0), Dual::var(u, 1), Dual { v: h, d: [0.0, 0.0, HUE_UNIT] })
    }

    /// Dodaje do `grad` gradient naruszonego termu pomnożony przez `hit.factor`: term liczony
    /// na liczbach dualnych o 3 zmiennych na kolor aktywny.
    fn term_grad<const N: usize>(&self, hit: &Hit, duals: &mut Duals, grad: &mut [f64]) {
        let slots = hit.active.as_slice();
        let mut cols: [Col<Dual<N>>; 3] = [self.base[0].constant(); 3];
        for (pos, &slot) in slots.iter().enumerate() {
            cols[pos] = match self.free_pos[slot] {
                Some(k) => duals.col(k).lift(pos),
                None => self.base[slot].constant(),
            };
        }
        let v = hit.term.body.violation(&cols[..slots.len()], hit.m);
        for (pos, &slot) in slots.iter().enumerate() {
            if let Some(k) = self.free_pos[slot] {
                for j in 0..3 {
                    grad[3 * k + j] += hit.factor * v.d[3 * pos + j];
                }
            }
        }
    }

    /// Ocena palety zakodowanej w `x`: funkcja celu bez marginesu i naruszenia.
    pub fn evaluate(&self, x: &[f64]) -> Evaluation {
        let cols = self.decode(x).into_iter().map(Col::fixed).collect();
        Frame::new(cols, &self.needs).report(&self.compiled)
    }

    /// Miękkie naruszenie „różnorodność” dla rozwiązania odległego o `distance` od wybranych.
    pub fn diversity_violation(&self, distance: f64, min_diversity: f64) -> Violation {
        use serde_json::json;
        Violation {
            key: crate::violation::KEY_DIVERSITY.to_owned(),
            slots: self.free_ids.clone(),
            kind: crate::violation::ViolationKind::Diversity,
            hard: false,
            amount: min_diversity - distance,
            achieved: distance,
            req: [("min".to_owned(), json!(min_diversity))].into_iter().collect(),
            meta: serde_json::Map::new(),
        }
    }

    /// OKLab kolorów wolnych, spłaszczone (3 liczby na kolor).
    fn free_labs(&self, x: &[f64]) -> Vec<f64> {
        let mut out = Vec::with_capacity(3 * self.free.len());
        for k in 0..self.free.len() {
            let (l, u, h) = Self::vars(x, k);
            let chroma = u * color::max_chroma(l, h);
            out.extend(color::oklch_to_oklab([l, chroma, h]));
        }
        out
    }
}

/// Średnie ΔE ok odpowiadających sobie kolorów (OKLab spłaszczone po 3).
fn mean_delta_e(a: &[f64], b: &[f64]) -> f64 {
    let n = a.len() / 3;
    if n == 0 {
        return 0.0;
    }
    let mut sum = 0.0;
    for k in 0..n {
        let d: f64 = (0..3).map(|j| (a[3 * k + j] - b[3 * k + j]).powi(2)).sum();
        sum += d.sqrt();
    }
    sum / n as f64
}

impl Objective for Problem {
    fn dim(&self) -> usize {
        self.lower.len()
    }

    fn bounds(&self) -> (&[f64], &[f64]) {
        (&self.lower, &self.upper)
    }

    /// Losowy start: jasność i nasycenie względne w granicach, odcień przy celu układu albo we
    /// własnym łuku — zawsze poza zakazanymi przedziałami (o ile zakazy zostawiają miejsce).
    fn sample(&self, rng: &mut Rng, out: &mut [f64]) {
        for (k, c) in self.free.iter().enumerate() {
            let l = sample_outside(rng, c.l, &c.excl_l);
            let hue_gaps: Vec<[f64; 2]> = unwrapped(&c.excl_h, c.hue_sample);
            let h = sample_outside(rng, c.hue_sample, &hue_gaps);
            let u = if c.excl_c_rel {
                sample_outside(rng, c.u, &c.excl_c)
            } else {
                // zakaz nasycenia bezwzględnego zależy od największego C przy (L, H): odrzucanie
                let maxc: f64 = color::max_chroma(l, h.rem_euclid(360.0));
                let mut u = rng.range(c.u.0, c.u.1);
                for _ in 0..SAMPLE_TRIES {
                    if !inside_linear(u * maxc, &c.excl_c) {
                        break;
                    }
                    u = rng.range(c.u.0, c.u.1);
                }
                u
            };
            out[3 * k] = l;
            out[3 * k + 1] = u;
            out[3 * k + 2] = h / HUE_UNIT;
        }
    }

    /// Bieżące wartości kolorów wolnych, sprowadzone do granic zmiennych.
    fn current(&self, out: &mut [f64]) {
        for (k, c) in self.free.iter().enumerate() {
            let col = &self.base[c.slot];
            let u = if col.maxc > 1e-9 { (col.c / col.maxc).min(1.0) } else { 0.0 };
            // odcień z granicami (np. 330–380): rozwinięcie do [lo, lo + 360), potem obcięcie
            let h = match c.hue_bounds {
                Some((lo, _)) => lo + (col.h - lo).rem_euclid(360.0),
                None => col.h,
            };
            let raw = [col.l, u, h / HUE_UNIT];
            for j in 0..3 {
                out[3 * k + j] = raw[j].max(self.lower[3 * k + j]).min(self.upper[3 * k + j]);
            }
        }
    }

    fn value_grad(&self, x: &[f64], grad: &mut [f64]) -> f64 {
        grad.fill(0.0);
        let frame = self.frame(x);
        let mut duals = Duals { x, cols: vec![None; self.free.len()] };
        let mut total = 0.0;
        for &index in &self.live {
            let term = &self.compiled.terms[index];
            let m = term.margin();
            let active = frame.active(term);
            let v = frame.violation(term, &active, m);
            if v <= 0.0 {
                continue;
            }
            let coefficient = term.coefficient(self.compiled.hard_weight);
            total += coefficient * v * v;
            let hit = Hit { term, active, m, factor: 2.0 * coefficient * v };
            match active.len {
                1 => self.term_grad::<3>(&hit, &mut duals, grad),
                2 => self.term_grad::<6>(&hit, &mut duals, grad),
                _ => self.term_grad::<9>(&hit, &mut duals, grad),
            }
        }
        total
    }

    fn score(&self, x: &[f64]) -> Score {
        let frame = self.frame(x);
        let mut total = self.const_total;
        let mut feasible = !self.const_infeasible;
        for &index in &self.live {
            let term = &self.compiled.terms[index];
            let v = frame.violation(term, &frame.active(term), 0.0);
            total += term.coefficient(self.compiled.hard_weight) * v * v;
            feasible &= !(term.hard && v > FEASIBLE_EPS);
        }
        Score { feasible, total }
    }

    fn distance(&self, a: &[f64], b: &[f64]) -> f64 {
        mean_delta_e(&self.free_labs(a), &self.free_labs(b))
    }

    fn prepare(&self, x: &[f64]) -> Vec<f64> {
        self.free_labs(x)
    }

    fn distance_prepared(&self, a: &[f64], b: &[f64]) -> f64 {
        mean_delta_e(a, b)
    }

    /// Kara `((min_div − d) / 0.01)²` za każde rozwiązanie z `others` bliższe niż `min_div`
    /// (`d` = średnie ΔE ok kolorów wolnych). `others` to wyniki [`Objective::prepare`].
    fn repulsion(&self, x: &[f64], others: &[Vec<f64>], min_div: f64, grad: &mut [f64]) -> f64 {
        let n = self.free.len();
        if n == 0 || others.is_empty() {
            return 0.0;
        }
        let labs = self.free_labs(x);
        let mut total = 0.0;
        let mut duals: Option<Vec<Col<Dual<3>>>> = None;
        for other in others {
            let d = mean_delta_e(&labs, other);
            if d >= min_div {
                continue;
            }
            let v = (min_div - d) / DIVERSITY_SCALE;
            total += v * v;
            // d(v²)/d(d) = −2v / skala; d = średnia ΔE ok po kolorach
            let factor = -2.0 * v / DIVERSITY_SCALE / n as f64;
            let cols = duals.get_or_insert_with(|| (0..n).map(|k| Self::dual_col(x, k)).collect());
            for (k, col) in cols.iter().enumerate() {
                let reference = [other[3 * k], other[3 * k + 1], other[3 * k + 2]];
                let de = color::delta_e::delta_e_ok(col.lab, reference.map(Dual::constant));
                for j in 0..3 {
                    grad[3 * k + j] += factor * de.d[j];
                }
            }
        }
        total
    }
}
