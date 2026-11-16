//! Termy funkcji celu: naruszenie zasady jako funkcja kolorów (port `constraints.py@4b71aeb`).
//!
//! Każda zasada, zależność i ustawienie globalne to [`Term`]: funkcja naruszenia ≥ 0 w
//! jednostkach naturalnych (0 = spełniona). Funkcja jest generyczna po [`Scalar`], więc ten sam
//! kod liczy wartość (`f64`) i gradient (liczby dualne). `m` to margines zaostrzający twarde
//! zasady przy optymalizacji; ocena liczy z `m = 0`.

use serde_json::{Map, Value};

use crate::color::{self, ContrastMetric, CvdKind, CvdMethod, DeltaE};
use crate::scalar::{Dual, Scalar};
use crate::schema::RelOp;
use crate::violation::ViolationKind;

/// Poniżej tego nasycenia odcień traci znaczenie (płynne wygaszanie termów odcienia).
pub(crate) const HUE_FADE_C: f64 = 0.02;
pub(crate) const SCALE_L: f64 = 0.01;
pub(crate) const SCALE_C_ABS: f64 = 0.01;
pub(crate) const SCALE_C_REL: f64 = 0.02;
pub(crate) const SCALE_H: f64 = 1.0;
/// Zaostrzenie twardych zasad przy optymalizacji, w ułamku skali termu.
pub(crate) const MARGIN_FRAC: f64 = 0.5;
/// Zaostrzenie twardych zasad przy końcowym szlifowaniu rozwiązania.
pub(crate) const POLISH_MARGIN_FRAC: f64 = 0.05;

pub(crate) fn scale_contrast(metric: ContrastMetric) -> f64 {
    match metric {
        ContrastMetric::Wcag21 => 0.1,
        ContrastMetric::Apca => 1.0,
    }
}

pub(crate) fn scale_de(method: DeltaE) -> f64 {
    match method {
        DeltaE::Ok | DeltaE::Hyab => 0.01,
        _ => 1.0,
    }
}

/// Kolor w postaci potrzebnej termom: OKLCH, OKLab, największe C przy (L, H) i nasycenie
/// względne.
#[derive(Debug, Clone, Copy)]
pub(crate) struct Col<T> {
    pub l: T,
    pub c: T,
    /// Odcień w stopniach, [0, 360).
    pub h: T,
    pub maxc: T,
    /// `C / maxc` (0, gdy `maxc ≤ 1e-9`).
    pub relc: T,
    pub lab: [T; 3],
}

impl Col<f64> {
    /// Kolor o danych wartościach OKLCH (stały albo oceniany).
    pub fn fixed(lch: [f64; 3]) -> Self {
        let h = lch[2].rem_euclid(360.0);
        let maxc: f64 = color::max_chroma(lch[0], h);
        let relc = if maxc > 1e-9 { lch[1] / maxc } else { 0.0 };
        Self {
            l: lch[0],
            c: lch[1],
            h,
            maxc,
            relc,
            lab: color::oklch_to_oklab([lch[0], lch[1], h]),
        }
    }

    /// Ten sam kolor jako stała typu `T`.
    pub fn constant<T: Scalar>(&self) -> Col<T> {
        Col {
            l: T::c(self.l),
            c: T::c(self.c),
            h: T::c(self.h),
            maxc: T::c(self.maxc),
            relc: T::c(self.relc),
            lab: self.lab.map(T::c),
        }
    }
}

impl<T: Scalar> Col<T> {
    /// Kolor wolny ze zmiennych (L, u, H°): `C = u · max_chroma(L, H)`, więc leży w gamucie.
    /// `boundary` to brzeg gamutu policzony dla wartości (L, H) — bisekcja nie jest powtarzana,
    /// gdy ten sam kolor liczy się drugi raz z pochodnymi.
    pub fn from_vars(l: T, u: T, h: T, boundary: &color::Boundary) -> Self {
        let maxc = boundary.lift(l, h);
        let c = u * maxc;
        let relc = if maxc.val() > 1e-9 { u } else { T::c(0.0) };
        Self { l, c, h, maxc, relc, lab: color::oklch_to_oklab([l, c, h]) }
    }
}

impl Col<Dual<3>> {
    /// Przenosi pochodne po (L, u, H) koloru na pozycję `pos` w liczbie dualnej termu.
    pub fn lift<const N: usize>(&self, pos: usize) -> Col<Dual<N>> {
        let up = |d: Dual<3>| {
            let mut out = Dual::<N>::constant(d.v);
            out.d[3 * pos..3 * pos + 3].copy_from_slice(&d.d);
            out
        };
        Col {
            l: up(self.l),
            c: up(self.c),
            h: up(self.h),
            maxc: up(self.maxc),
            relc: up(self.relc),
            lab: self.lab.map(up),
        }
    }
}

/// Twarde dolne granice nasycenia koloru: (bezwzględna, względna). Poniżej nich wygaszanie
/// odcienia nie działa — optymalizator nie ucieknie od zasady odcienia przez odbarwienie.
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub(crate) struct Floor {
    pub abs: f64,
    pub rel: f64,
}

/// Kanał koloru, którego dotyczy zakres albo zakaz.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Chan {
    L,
    CAbs,
    CRel,
    H,
}

impl Chan {
    pub fn of<T: Scalar>(self, col: &Col<T>) -> T {
        match self {
            Self::L => col.l,
            Self::CAbs => col.c,
            Self::CRel => col.relc,
            Self::H => col.h,
        }
    }

    pub fn scale(self) -> f64 {
        match self {
            Self::L => SCALE_L,
            Self::CAbs => SCALE_C_ABS,
            Self::CRel => SCALE_C_REL,
            Self::H => SCALE_H,
        }
    }

    /// Nazwa kanału w kluczu i metadanych zakazu.
    pub fn name(self) -> &'static str {
        match self {
            Self::L => "lightness",
            Self::CAbs | Self::CRel => "chroma",
            Self::H => "hue",
        }
    }
}

#[inline]
fn relu<T: Scalar>(x: T) -> T {
    x.maxf(0.0)
}

#[inline]
fn min_by_value<T: Scalar>(a: T, b: T) -> T {
    if b.val() < a.val() { b } else { a }
}

/// Odległość wartości od przedziału [lo, hi] zwężonego o `m` z każdej strony.
fn interval_v<T: Scalar>(x: T, lo: Option<f64>, hi: Option<f64>, m: f64) -> T {
    let mut v = T::c(0.0);
    if let Some(lo) = lo {
        v = v + relu(T::c(lo + m) - x);
    }
    if let Some(hi) = hi {
        v = v + relu(x.offset(-(hi - m)));
    }
    v
}

/// Sprowadza kąt do [0, 360).
fn wrap360<T: Scalar>(x: T) -> T {
    let y = x.offset(-360.0 * (x.val() / 360.0).floor());
    if y.val() >= 360.0 { y.offset(-360.0) } else { y }
}

/// Szerokość łuku `lo → hi`; `lo ≠ hi` o tej samej pozycji to pełne koło.
pub(crate) fn arc_width(lo: f64, hi: f64) -> f64 {
    let width = (hi - lo).rem_euclid(360.0);
    if width == 0.0 && lo != hi { 360.0 } else { width }
}

/// Odległość (°) odcienia od łuku `[lo, lo + width]` zwężonego o `m`.
fn hue_outside<T: Scalar>(h: T, lo: f64, width: f64, m: f64) -> T {
    let m = m.min(width / 2.0);
    let width_m = width - 2.0 * m;
    let off = wrap360(h.offset(-(lo + m)));
    if off.val() <= width_m {
        return T::c(0.0);
    }
    let to_lo = T::c(360.0) - off;
    let to_hi = off.offset(-width_m);
    min_by_value(to_lo, to_hi)
}

/// Najkrótszy łuk `b − a` w (−180, 180].
fn angle_diff<T: Scalar>(a: T, b: T) -> T {
    let d = b - a;
    let d = d.offset(-360.0 * (d.val() / 360.0).trunc());
    if d.val() <= -180.0 {
        d.offset(360.0)
    } else if d.val() > 180.0 {
        d.offset(-360.0)
    } else {
        d
    }
}

/// Naruszenie warunku `d (op) value` z tolerancją `tol` (tylko dla `eq`).
fn op_v<T: Scalar>(d: T, op: RelOp, value: f64, tol: f64, m: f64) -> T {
    match op {
        RelOp::Eq => relu(d.offset(-value).abs().offset(m - tol)),
        RelOp::Ge => relu(T::c(value + m) - d),
        RelOp::Le => relu(d.offset(-(value - m))),
    }
}

/// Wygaszanie odcienia przy C → 0: `clip(C / 0.02, 0, 1)²`, z podłogą twardego minimum
/// nasycenia.
fn hue_weight<T: Scalar>(col: &Col<T>, floor: Floor) -> T {
    let mut c = col.c;
    if floor.abs > 0.0 || floor.rel > 0.0 {
        let rel = col.maxc.scale(floor.rel);
        let bottom = if rel.val() > floor.abs { rel } else { T::c(floor.abs) };
        if bottom.val() > c.val() {
            c = bottom;
        }
    }
    c.scale(1.0 / HUE_FADE_C).maxf(0.0).minf(1.0).square()
}

/// Ustawienia symulacji CVD dla termu pary.
#[derive(Debug, Clone, Copy, PartialEq)]
pub(crate) struct Cvd {
    pub kind: CvdKind,
    pub method: CvdMethod,
    pub severity: f64,
}

/// Wielkość porównywana przez zależność liniową.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Quantity {
    Lightness,
    /// Nasycenie: względne albo bezwzględne; `mul` = „val × cel” zamiast różnicy.
    Chroma {
        rel: bool,
        mul: bool,
    },
}

/// Treść termu. Kolory dostaje w kolejności opisanej przy wariancie.
#[derive(Debug, Clone, PartialEq)]
pub(crate) enum Body {
    /// Zakres jasności albo nasycenia. Kolory: [kolor].
    Interval { chan: Chan, lo: Option<f64>, hi: Option<f64> },
    /// Łuk odcienia. Kolory: [kolor].
    HueArc { lo: f64, width: f64, floor: Floor },
    /// Zakazany przedział `(lo, hi)`; dla odcienia `hi = lo + szerokość`. Kolory: [kolor].
    Exclude { chan: Chan, lo: f64, hi: f64, floor: Floor },
    /// Kontrast z tłem. Kolory: [tekst, tło].
    Contrast { metric: ContrastMetric, lo: Option<f64>, hi: Option<f64> },
    /// Najsłabszy / najmocniejszy kontrast wśród akcentów. Kolory: [własny, aktywny inny, tło].
    Extreme { weakest: bool, metric: ContrastMetric, others: Vec<usize>, bg: usize },
    /// Minimalna odległość pary (także po symulacji CVD). Kolory: [a, b].
    Pair { min: f64, method: DeltaE, cvd: Option<Cvd> },
    /// Zależność odcienia. Kolory: [kolor, cel].
    RelHue { op: RelOp, value: f64, tol: f64, floors: [Floor; 2] },
    /// Zależność jasności albo nasycenia. Kolory: [kolor, cel].
    RelLinear { quantity: Quantity, op: RelOp, value: f64, tol: f64 },
    /// Zależność kontrastu (kolor jako tekst, cel jako tło). Kolory: [kolor, cel].
    RelContrast { metric: ContrastMetric, op: RelOp, value: f64, tol: f64 },
    /// Zależność odległości. Kolory: [kolor, cel].
    RelDistance { method: DeltaE, op: RelOp, value: f64, tol: f64 },
    /// Kolor ≈ mieszanka(cel, inny, t) w OKLab. Kolory: [kolor, cel, inny].
    RelMix { t: f64, tol: f64 },
    /// Rozrzut jasności akcentów. Kolory: [najjaśniejszy, najciemniejszy].
    Spread { accents: Vec<usize>, lo: Option<f64>, hi: Option<f64> },
    /// Cel układu odcieni. Kolory: [kolor].
    Scheme { target: f64, tol: f64, floor: Floor },
    /// Odległość ΔE ok od unikanego koloru. Kolory: [kolor].
    Avoid { reference: [f64; 3], min: f64 },
    /// Nasycenie ponad największe C w sRGB. Kolory: [kolor].
    Gamut,
}

fn chroma_of<T: Scalar>(col: &Col<T>, rel: bool) -> T {
    if rel { col.relc } else { col.c }
}

fn simulated<T: Scalar>(lab: [T; 3], cvd: Option<Cvd>) -> [T; 3] {
    match cvd {
        Some(c) => color::simulate_cvd(lab, c.kind, c.method, c.severity),
        None => lab,
    }
}

fn mix_distance<T: Scalar>(cols: &[Col<T>], t: f64) -> T {
    let mut sum = T::c(0.0);
    for k in 0..3 {
        let mixed = cols[1].lab[k].scale(1.0 - t) + cols[2].lab[k].scale(t);
        sum = sum + (cols[0].lab[k] - mixed).square();
    }
    sum.sqrt()
}

impl Body {
    /// Naruszenie (≥ 0) dla kolorów `cols` i marginesu `m`.
    pub fn violation<T: Scalar>(&self, cols: &[Col<T>], m: f64) -> T {
        match self {
            Self::Interval { chan, lo, hi } => interval_v(chan.of(&cols[0]), *lo, *hi, m),
            Self::HueArc { lo, width, floor } => {
                hue_outside(cols[0].h, *lo, *width, m) * hue_weight(&cols[0], *floor)
            }
            Self::Exclude { chan: Chan::H, lo, hi, floor } => {
                // zakaz poszerzony o margines; wielkość = odległość do bliższego brzegu
                let width = (hi - lo + 2.0 * m).min(360.0);
                let off = wrap360(cols[0].h.offset(-(lo - m)));
                if off.val() >= width {
                    return T::c(0.0);
                }
                let depth = min_by_value(off, T::c(width) - off);
                relu(depth) * hue_weight(&cols[0], *floor)
            }
            Self::Exclude { chan, lo, hi, .. } => {
                let x = chan.of(&cols[0]);
                relu(min_by_value(x.offset(m - lo), T::c(hi + m) - x))
            }
            Self::Contrast { metric, lo, hi } => {
                interval_v(color::contrast(cols[0].lab, cols[1].lab, *metric), *lo, *hi, m)
            }
            Self::Extreme { weakest, metric, .. } => {
                let own = color::contrast(cols[0].lab, cols[2].lab, *metric);
                let other = color::contrast(cols[1].lab, cols[2].lab, *metric);
                if *weakest { relu((own - other).offset(m)) } else { relu((other - own).offset(m)) }
            }
            Self::Pair { min, method, cvd } => {
                let d = color::delta_e(
                    simulated(cols[0].lab, *cvd),
                    simulated(cols[1].lab, *cvd),
                    *method,
                );
                relu(T::c(min + m) - d)
            }
            Self::RelHue { op, value, tol, floors } => {
                let d = angle_diff(cols[1].h, cols[0].h);
                let v = match op {
                    RelOp::Eq => relu(angle_diff(T::c(*value), d).abs().offset(m - tol)),
                    // liniowo na łuku — drugie zawijanie odwracałoby znak
                    RelOp::Ge => relu(T::c(value + m) - d),
                    RelOp::Le => relu(d.offset(-(value - m))),
                };
                v * hue_weight(&cols[0], floors[0]) * hue_weight(&cols[1], floors[1])
            }
            Self::RelLinear { quantity, op, value, tol } => match *quantity {
                Quantity::Lightness => op_v(cols[0].l - cols[1].l, *op, *value, *tol, m),
                Quantity::Chroma { rel, mul: false } => {
                    op_v(chroma_of(&cols[0], rel) - chroma_of(&cols[1], rel), *op, *value, *tol, m)
                }
                Quantity::Chroma { rel, mul: true } => {
                    let d = chroma_of(&cols[0], rel) - chroma_of(&cols[1], rel).scale(*value);
                    op_v(d, *op, 0.0, *tol, m)
                }
            },
            Self::RelContrast { metric, op, value, tol } => {
                op_v(color::contrast(cols[0].lab, cols[1].lab, *metric), *op, *value, *tol, m)
            }
            Self::RelDistance { method, op, value, tol } => {
                op_v(color::delta_e(cols[0].lab, cols[1].lab, *method), *op, *value, *tol, m)
            }
            Self::RelMix { t, tol } => relu(mix_distance(cols, *t).offset(m - tol)),
            Self::Spread { lo, hi, .. } => interval_v(cols[0].l - cols[1].l, *lo, *hi, m),
            Self::Scheme { target, tol, floor } => {
                let off = angle_diff(cols[0].h, T::c(*target)).abs();
                relu(off.offset(m - tol)) * hue_weight(&cols[0], *floor)
            }
            Self::Avoid { reference, min } => {
                relu(T::c(min + m) - color::delta_e::delta_e_ok(cols[0].lab, reference.map(T::c)))
            }
            Self::Gamut => relu(cols[0].c - cols[0].maxc),
        }
    }

    /// Wartość osiągnięta, pokazywana w raporcie naruszeń (jak `describe` w v1).
    pub fn achieved(&self, cols: &[Col<f64>]) -> f64 {
        match self {
            Self::Interval { chan, .. } | Self::Exclude { chan, .. } => chan.of(&cols[0]),
            Self::HueArc { .. } | Self::Scheme { .. } => cols[0].h,
            Self::Contrast { metric, .. } | Self::RelContrast { metric, .. } => {
                color::contrast(cols[0].lab, cols[1].lab, *metric)
            }
            Self::Extreme { metric, .. } => color::contrast(cols[0].lab, cols[2].lab, *metric),
            Self::Pair { method, cvd, .. } => {
                color::delta_e(simulated(cols[0].lab, *cvd), simulated(cols[1].lab, *cvd), *method)
            }
            Self::RelHue { .. } => angle_diff(cols[1].h, cols[0].h),
            Self::RelLinear { quantity, .. } => match *quantity {
                Quantity::Lightness => cols[0].l - cols[1].l,
                Quantity::Chroma { rel, mul: false } => {
                    chroma_of(&cols[0], rel) - chroma_of(&cols[1], rel)
                }
                Quantity::Chroma { rel, mul: true } => chroma_of(&cols[0], rel),
            },
            Self::RelDistance { method, .. } => color::delta_e(cols[0].lab, cols[1].lab, *method),
            Self::RelMix { t, .. } => mix_distance(cols, *t),
            Self::Spread { .. } => cols[0].l - cols[1].l,
            Self::Avoid { reference, .. } => color::delta_e::delta_e_ok(cols[0].lab, *reference),
            Self::Gamut => cols[0].c,
        }
    }
}

/// Wartość pola wymagania albo metadanych naruszenia. Na JSON zamieniana dopiero w raporcie
/// naruszenia: kompilacja sesji (kilkaset termów) nie buduje map, których nikt nie przeczyta.
#[derive(Debug, Clone, Copy, PartialEq)]
pub(crate) enum Field {
    Num(f64),
    Opt(Option<f64>),
    Text(&'static str),
    Null,
}

impl From<f64> for Field {
    fn from(v: f64) -> Self {
        Self::Num(v)
    }
}

impl From<Option<f64>> for Field {
    fn from(v: Option<f64>) -> Self {
        Self::Opt(v)
    }
}

impl From<&'static str> for Field {
    fn from(v: &'static str) -> Self {
        Self::Text(v)
    }
}

/// Pola wymagania / metadanych w kolejności dodania.
pub(crate) type Fields = Vec<(&'static str, Field)>;

/// Pola jako obiekt JSON raportu naruszenia.
pub(crate) fn fields_to_map(fields: &Fields) -> Map<String, Value> {
    fields
        .iter()
        .map(|&(name, field)| {
            let value = match field {
                Field::Num(v) => Value::from(v),
                Field::Opt(v) => v.map_or(Value::Null, Value::from),
                Field::Text(t) => Value::from(t),
                Field::Null => Value::Null,
            };
            (name.to_owned(), value)
        })
        .collect()
}

/// Jeden term funkcji celu.
#[derive(Debug, Clone, PartialEq)]
pub(crate) struct Term {
    pub key: String,
    pub kind: ViolationKind,
    /// Kolory wymieniane w raporcie (indeksy).
    pub report: Vec<usize>,
    pub hard: bool,
    pub weight: f64,
    pub scale: f64,
    pub body: Body,
    /// Kolory, od których term zależy. Dla [`Body::Extreme`] i [`Body::Spread`] to wszyscy
    /// kandydaci; aktywna trójka / para jest wybierana przy każdej ocenie.
    pub slots: Vec<usize>,
    /// Wymaganie w liczbach (pola stałe; `bound` i `hi` dopisuje ocena).
    pub req: Fields,
    pub meta: Fields,
}

impl Term {
    /// Margines twardej zasady przy optymalizacji: `frac × skala`.
    pub fn margin(&self, frac: f64) -> f64 {
        if self.hard { frac * self.scale } else { 0.0 }
    }

    /// Mnożnik `waga · (twarda ? hard_weight : 1) / skala²` przy kwadracie naruszenia.
    pub fn coefficient(&self, hard_weight: f64) -> f64 {
        self.weight * if self.hard { hard_weight } else { 1.0 } / (self.scale * self.scale)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn col(l: f64, c: f64, h: f64) -> Col<f64> {
        Col::fixed([l, c, h])
    }

    #[test]
    fn interval_measures_distance_to_the_range() {
        assert_eq!(interval_v(0.5, Some(0.6), Some(0.8), 0.0), 0.09999999999999998);
        assert_eq!(interval_v(0.7, Some(0.6), Some(0.8), 0.0), 0.0);
        assert!((interval_v(0.85, Some(0.6), Some(0.8), 0.0) - 0.05).abs() < 1e-12);
        // margines zwęża zakres z obu stron
        assert!((interval_v(0.61, Some(0.6), Some(0.8), 0.02) - 0.01).abs() < 1e-12);
        assert_eq!(interval_v(0.3, None, None, 0.0), 0.0);
    }

    #[test]
    fn hue_outside_handles_wrapping_and_full_circle() {
        let w = arc_width(300.0, 90.0);
        assert_eq!(w, 150.0);
        assert_eq!(hue_outside(10.0, 300.0, w, 0.0), 0.0);
        assert_eq!(hue_outside(350.0, 300.0, w, 0.0), 0.0);
        assert!((hue_outside(100.0, 300.0, w, 0.0) - 10.0).abs() < 1e-12);
        assert!((hue_outside(280.0, 300.0, w, 0.0) - 20.0).abs() < 1e-12);
        assert!((hue_outside(195.0, 300.0, w, 0.0) - 105.0).abs() < 1e-12);
        // pełne koło: nic nie jest poza
        assert_eq!(arc_width(0.0, 360.0), 360.0);
        assert_eq!(hue_outside(123.0, 0.0, 360.0, 0.0), 0.0);
        // łuk zerowej szerokości: odległość od punktu
        assert_eq!(arc_width(40.0, 40.0), 0.0);
        assert!((hue_outside(50.0, 40.0, 0.0, 0.0) - 10.0).abs() < 1e-12);
    }

    #[test]
    fn angle_diff_is_the_shortest_arc() {
        assert_eq!(angle_diff(10.0, 30.0), 20.0);
        assert_eq!(angle_diff(350.0, 10.0), 20.0);
        assert_eq!(angle_diff(10.0, 350.0), -20.0);
        assert_eq!(angle_diff(0.0, 180.0), 180.0);
        assert_eq!(angle_diff(180.0, 0.0), 180.0);
        assert_eq!(angle_diff(0.0, 181.0), -179.0);
    }

    #[test]
    fn hue_fades_out_at_low_chroma_unless_a_hard_floor_holds_it() {
        let vivid = col(0.7, 0.1, 40.0);
        let pale = col(0.7, 0.01, 40.0);
        let grey = col(0.7, 0.0, 40.0);
        assert_eq!(hue_weight(&vivid, Floor::default()), 1.0);
        assert!((hue_weight(&pale, Floor::default()) - 0.25).abs() < 1e-12);
        assert_eq!(hue_weight(&grey, Floor::default()), 0.0);
        // twarde minimum nasycenia 0.05: wygaszanie nie działa
        assert_eq!(hue_weight(&grey, Floor { abs: 0.05, rel: 0.0 }), 1.0);
        let rel = hue_weight(&grey, Floor { abs: 0.0, rel: 0.05 });
        assert!((rel - (0.05 * grey.maxc / 0.02).min(1.0).powi(2)).abs() < 1e-12);
    }

    #[test]
    fn exclusion_is_the_distance_to_the_nearer_edge() {
        let ex = Body::Exclude { chan: Chan::L, lo: 0.70, hi: 0.74, floor: Floor::default() };
        let at = |l: f64| ex.violation(&[col(l, 0.1, 40.0)], 0.0);
        assert!((at(0.72) - 0.02).abs() < 1e-12);
        assert!((at(0.71) - 0.01).abs() < 1e-12);
        assert!((at(0.735) - 0.005).abs() < 1e-12);
        assert_eq!(at(0.70), 0.0);
        assert_eq!(at(0.74), 0.0);
        assert_eq!(at(0.5), 0.0);
        // margines poszerza zakaz
        assert!((ex.violation(&[col(0.699, 0.1, 40.0)], 0.005) - 0.004).abs() < 1e-12);
    }

    #[test]
    fn hue_exclusion_wraps_through_zero() {
        // zakaz 350–10 zapisany jako lo = 350, hi = lo + 20
        let ex = Body::Exclude { chan: Chan::H, lo: 350.0, hi: 370.0, floor: Floor::default() };
        let at = |h: f64| ex.violation(&[col(0.7, 0.1, h)], 0.0);
        assert!((at(5.0) - 5.0).abs() < 1e-9);
        assert!((at(355.0) - 5.0).abs() < 1e-9);
        assert!((at(0.0) - 10.0).abs() < 1e-9);
        assert_eq!(at(10.0), 0.0);
        assert_eq!(at(350.0), 0.0);
        assert_eq!(at(200.0), 0.0);
        // szarość: odcień bez znaczenia
        assert_eq!(ex.violation(&[col(0.7, 0.0, 5.0)], 0.0), 0.0);
    }

    #[test]
    fn op_v_covers_the_three_operators() {
        assert!((op_v(0.3, RelOp::Eq, 0.5, 0.05, 0.0) - 0.15).abs() < 1e-12);
        assert_eq!(op_v(0.48, RelOp::Eq, 0.5, 0.05, 0.0), 0.0);
        assert!((op_v(0.3, RelOp::Ge, 0.5, 0.0, 0.0) - 0.2).abs() < 1e-12);
        assert_eq!(op_v(0.6, RelOp::Ge, 0.5, 0.0, 0.0), 0.0);
        assert!((op_v(0.6, RelOp::Le, 0.5, 0.0, 0.0) - 0.1).abs() < 1e-12);
        assert!((op_v(0.5, RelOp::Le, 0.5, 0.0, 0.02) - 0.02).abs() < 1e-12);
    }

    #[test]
    fn lifted_color_keeps_value_and_moves_derivatives() {
        let edge = color::boundary(0.7, 40.0);
        let c =
            Col::from_vars(Dual::<3>::var(0.7, 0), Dual::var(0.5, 1), Dual::var(40.0, 2), &edge);
        let up: Col<Dual<9>> = c.lift(2);
        assert_eq!(up.c.v, c.c.v);
        assert_eq!(&up.c.d[6..9], &c.c.d);
        assert!(up.c.d[..6].iter().all(|&d| d == 0.0));
        assert_eq!(up.lab[1].d[6..9], c.lab[1].d);
        // kolor wolny leży w gamucie, a nasycenie względne to zmienna u
        assert!((c.relc.v - 0.5).abs() < 1e-15 && c.relc.d == [0.0, 1.0, 0.0]);
        assert!(crate::color::in_gamut([c.l.v, c.c.v, c.h.v]));
    }
}
