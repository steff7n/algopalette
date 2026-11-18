//! Schemat `algopalette.v2` (plan I1): jeden format dla pliku sesji i wejścia silnika.
//!
//! Struktury serde odpowiadają dokumentowi 1:1; każda odrzuca nieznane pole, a [`parse`] podaje
//! ścieżkę do miejsca błędu (`slots[2].rules.hue.value.foo`). Po rozbiorze składniowym działa
//! walidacja zakresów (te same reguły co po stronie Pythona, plan I1).
//!
//! Pola `hex`, `name`, `preset` i `view_model` są znane, ale dla silnika bez znaczenia — mogą
//! być pominięte. Wszystkie pozostałe pola są wymagane, także te o wartości `null`.

use std::fmt;

use serde::{Deserialize, Deserializer, Serialize};

/// Znacznik formatu wymagany w polu `format`.
pub const FORMAT: &str = "algopalette.v2";
/// Najmniejsza liczba kolorów: tło, tekst i jeden akcent.
pub const MIN_SLOTS: usize = 3;
/// Największa liczba kolorów: tło, tekst i 14 akcentów.
pub const MAX_SLOTS: usize = 16;

/// Błąd schematu: ścieżka w dokumencie (`$` = korzeń) i krótki opis techniczny.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SchemaError {
    pub path: String,
    pub msg: String,
}

impl SchemaError {
    fn new(path: impl Into<String>, msg: impl Into<String>) -> Self {
        Self { path: path.into(), msg: msg.into() }
    }
}

impl fmt::Display for SchemaError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.path, self.msg)
    }
}

impl std::error::Error for SchemaError {}

// ---------------------------------------------------------------------------
// Wyliczenia (wartości jak w `model.py`)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Polarity {
    Dark,
    Light,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ContrastMetric {
    Wcag21,
    Apca,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum DeltaE {
    #[serde(rename = "ok")]
    Ok,
    #[serde(rename = "2000")]
    Ciede2000,
    #[serde(rename = "hyab")]
    Hyab,
    #[serde(rename = "itp")]
    Itp,
    #[serde(rename = "cam16")]
    Cam16,
}

/// Metoda sprowadzania do gamutu — używa jej tylko Python (silnik dostaje kolory po dopasowaniu).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum FitMethod {
    #[serde(rename = "clip")]
    Clip,
    #[serde(rename = "minde-chroma")]
    MindeChroma,
    #[serde(rename = "lch-chroma")]
    LchChroma,
    #[serde(rename = "oklch-chroma")]
    OklchChroma,
    #[serde(rename = "raytrace")]
    Raytrace,
    #[serde(rename = "scale")]
    Scale,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum HueSchemeKind {
    Equal,
    Analogous,
    Complementary,
    Split,
    Triad,
    Tetrad,
    Custom,
    None,
}

/// `abs` = nasycenie C wprost; `rel` = ułamek największego C osiągalnego w sRGB przy (L, H).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ChromaMode {
    Abs,
    Rel,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Extreme {
    Weakest,
    Strongest,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum RelKind {
    Hue,
    Lightness,
    Chroma,
    Contrast,
    Distance,
    Mix,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum RelOp {
    Eq,
    Ge,
    Le,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ChromaOp {
    Add,
    Mul,
}

/// Metryka zależności: metryka kontrastu (rodzaj `contrast`) albo metoda ΔE (rodzaj `distance`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum RelMetric {
    #[serde(rename = "wcag21")]
    Wcag21,
    #[serde(rename = "apca")]
    Apca,
    #[serde(rename = "ok")]
    Ok,
    #[serde(rename = "2000")]
    Ciede2000,
    #[serde(rename = "hyab")]
    Hyab,
    #[serde(rename = "itp")]
    Itp,
    #[serde(rename = "cam16")]
    Cam16,
}

impl RelMetric {
    /// Metryka kontrastu, jeśli nią jest.
    pub fn as_contrast(self) -> Option<ContrastMetric> {
        match self {
            Self::Wcag21 => Some(ContrastMetric::Wcag21),
            Self::Apca => Some(ContrastMetric::Apca),
            _ => None,
        }
    }

    /// Metoda ΔE, jeśli nią jest.
    pub fn as_delta_e(self) -> Option<DeltaE> {
        match self {
            Self::Ok => Some(DeltaE::Ok),
            Self::Ciede2000 => Some(DeltaE::Ciede2000),
            Self::Hyab => Some(DeltaE::Hyab),
            Self::Itp => Some(DeltaE::Itp),
            Self::Cam16 => Some(DeltaE::Cam16),
            _ => None,
        }
    }
}

/// Nazwy wartości wyliczeń takie jak w dokumencie — bez alokacji, do raportów naruszeń.
macro_rules! names {
    ($($ty:ident { $($variant:ident => $name:literal),+ $(,)? })+) => {
        $(impl $ty {
            /// Nazwa wartości w dokumencie `algopalette.v2`.
            pub fn as_str(self) -> &'static str {
                match self {
                    $(Self::$variant => $name),+
                }
            }
        })+
    };
}

names! {
    ContrastMetric { Wcag21 => "wcag21", Apca => "apca" }
    DeltaE { Ok => "ok", Ciede2000 => "2000", Hyab => "hyab", Itp => "itp", Cam16 => "cam16" }
    ChromaMode { Abs => "abs", Rel => "rel" }
    ChromaOp { Add => "add", Mul => "mul" }
    Extreme { Weakest => "weakest", Strongest => "strongest" }
    RelKind {
        Hue => "hue", Lightness => "lightness", Chroma => "chroma", Contrast => "contrast",
        Distance => "distance", Mix => "mix",
    }
    RelOp { Eq => "eq", Ge => "ge", Le => "le" }
}

/// Wartość wyliczenia po nazwie z dokumentu, np. `"2000"` → [`DeltaE::Ciede2000`].
pub fn enum_from_name<'a, T: Deserialize<'a>>(name: &'a str) -> Option<T> {
    use serde::de::value::{BorrowedStrDeserializer, Error};
    T::deserialize(BorrowedStrDeserializer::<Error>::new(name)).ok()
}

// ---------------------------------------------------------------------------
// Struktury dokumentu
// ---------------------------------------------------------------------------

/// Pole wymagane, które może mieć wartość `null` (serde domyślnie uznaje brak `Option` za `None`).
fn required<'de, D, T>(de: D) -> Result<Option<T>, D::Error>
where
    D: Deserializer<'de>,
    T: Deserialize<'de>,
{
    Option::<T>::deserialize(de)
}

/// Lista par `[od, do]`. Tablica `[f64; 2]` z serde nie pilnuje nadmiarowych elementów (błąd
/// wychodzi dopiero jako składniowy, bez ścieżki), więc długość sprawdzamy sami.
fn pairs<'de, D>(de: D) -> Result<Vec<[f64; 2]>, D::Error>
where
    D: Deserializer<'de>,
{
    struct Pair([f64; 2]);
    impl<'de> Deserialize<'de> for Pair {
        fn deserialize<D2: Deserializer<'de>>(de: D2) -> Result<Self, D2::Error> {
            let v = Vec::<f64>::deserialize(de)?;
            match v.as_slice() {
                [a, b] => Ok(Pair([*a, *b])),
                _ => Err(serde::de::Error::invalid_length(v.len(), &"a pair [lo, hi]")),
            }
        }
    }
    Ok(Vec::<Pair>::deserialize(de)?.into_iter().map(|p| p.0).collect())
}

/// Kolor OKLCH: `l` 0–1, `c` ≥ 0, `h` w stopniach.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Oklch {
    pub l: f64,
    pub c: f64,
    pub h: f64,
}

/// Zasada: wartość + włączenie + twarda/miękka + waga.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Rule<T> {
    pub value: T,
    pub enabled: bool,
    pub hard: bool,
    pub weight: f64,
}

/// Przedział bez zakazów (rozrzut jasności).
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Interval {
    #[serde(deserialize_with = "required")]
    pub lo: Option<f64>,
    #[serde(deserialize_with = "required")]
    pub hi: Option<f64>,
}

/// Zakres jasności z zakazanymi przedziałami `[od, do]`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Band {
    #[serde(deserialize_with = "required")]
    pub lo: Option<f64>,
    #[serde(deserialize_with = "required")]
    pub hi: Option<f64>,
    #[serde(deserialize_with = "pairs")]
    pub exclude: Vec<[f64; 2]>,
}

/// Zakres nasycenia (bezwzględny albo względny) z zakazanymi przedziałami.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ChromaBand {
    pub mode: ChromaMode,
    #[serde(deserialize_with = "required")]
    pub lo: Option<f64>,
    #[serde(deserialize_with = "required")]
    pub hi: Option<f64>,
    #[serde(deserialize_with = "pairs")]
    pub exclude: Vec<[f64; 2]>,
}

/// Łuk odcienia w stopniach; `lo > hi` = przez 0°, `lo = 0, hi = 360` = pełne koło.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HueArc {
    pub lo: f64,
    pub hi: f64,
    #[serde(deserialize_with = "pairs")]
    pub exclude: Vec<[f64; 2]>,
}

/// Wymagany kontrast z tłem; `metric = null` = metryka globalna.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ContrastBound {
    #[serde(deserialize_with = "required")]
    pub metric: Option<ContrastMetric>,
    #[serde(deserialize_with = "required")]
    pub lo: Option<f64>,
    #[serde(deserialize_with = "required")]
    pub hi: Option<f64>,
}

/// Zasady jednego koloru; wszystkie siedem kluczy zawsze obecne (`null` = brak zasady).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SlotRules {
    #[serde(deserialize_with = "required")]
    pub lightness: Option<Rule<Band>>,
    #[serde(deserialize_with = "required")]
    pub chroma: Option<Rule<ChromaBand>>,
    #[serde(deserialize_with = "required")]
    pub hue: Option<Rule<HueArc>>,
    #[serde(deserialize_with = "required")]
    pub contrast_bg: Option<Rule<ContrastBound>>,
    #[serde(deserialize_with = "required")]
    pub min_distance: Option<Rule<f64>>,
    #[serde(deserialize_with = "required")]
    pub extreme: Option<Rule<Extreme>>,
}

/// Zależność od innego koloru (pola jak w v1).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Relation {
    pub kind: RelKind,
    pub target: String,
    pub op: RelOp,
    pub value: f64,
    pub tol: f64,
    pub chroma_op: ChromaOp,
    pub chroma_mode: ChromaMode,
    #[serde(deserialize_with = "required")]
    pub metric: Option<RelMetric>,
    /// Tylko `mix`: kolor ≈ mieszanka(`target`, `other`, `t`) w OKLab.
    #[serde(deserialize_with = "required")]
    pub other: Option<String>,
    pub t: f64,
    pub enabled: bool,
    pub hard: bool,
    pub weight: f64,
}

/// Kolor palety. Indeks 0 = tło, 1 = tekst, dalsze = akcenty.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Slot {
    pub id: String,
    #[serde(default)]
    pub name: String,
    pub locked: bool,
    pub value: Oklch,
    #[serde(default)]
    pub hex: String,
    pub use_scheme: bool,
    pub rules: SlotRules,
    pub relations: Vec<Relation>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HueScheme {
    pub kind: HueSchemeKind,
    pub rotation: f64,
    pub center: f64,
    pub spread: f64,
    pub custom: Vec<f64>,
    pub tol: f64,
    pub jitter: f64,
    pub hard: bool,
    pub weight: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OptimizerSettings {
    pub n_proposals: usize,
    pub seed: u64,
    /// Największa liczba ocen funkcji z gradientem na jeden przebieg.
    pub budget: usize,
    pub time_cap_s: f64,
    pub min_diversity: f64,
    pub hard_weight: f64,
    /// 0 = wszystkie wątki maszyny.
    pub threads: usize,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct GlobalSettings {
    pub polarity: Polarity,
    pub contrast_metric: ContrastMetric,
    pub delta_e: DeltaE,
    pub fit_method: FitMethod,
    pub hue_scheme: HueScheme,
    #[serde(deserialize_with = "required")]
    pub lightness_spread: Option<Rule<Interval>>,
    pub avoid_colors: Vec<Oklch>,
    pub avoid_distance: f64,
    pub optimizer: OptimizerSettings,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Session {
    pub format: String,
    #[serde(default)]
    pub preset: Option<String>,
    #[serde(default)]
    pub view_model: Option<String>,
    pub globals: GlobalSettings,
    pub slots: Vec<Slot>,
}

// ---------------------------------------------------------------------------
// Rozbiór i walidacja
// ---------------------------------------------------------------------------

/// Czyta i sprawdza dokument `algopalette.v2`.
pub fn parse(json: &str) -> Result<Session, SchemaError> {
    let mut de = serde_json::Deserializer::from_str(json);
    let session: Session = serde_path_to_error::deserialize(&mut de).map_err(|e| {
        let path = e.path().to_string();
        let inner = e.into_inner();
        // Błąd składni nie ma sensownej ścieżki (wskazywałaby ostatnie czytane pole).
        let path = if inner.is_data() && path != "." { path } else { "$".to_owned() };
        SchemaError::new(path, inner.to_string())
    })?;
    de.end().map_err(|e| SchemaError::new("$", e.to_string()))?;
    validate(&session)?;
    Ok(session)
}

fn non_negative(v: f64, path: impl FnOnce() -> String) -> Result<(), SchemaError> {
    if v >= 0.0 { Ok(()) } else { Err(SchemaError::new(path(), "must not be negative")) }
}

fn check_color(c: &Oklch, path: &str) -> Result<(), SchemaError> {
    if !(0.0..=1.0).contains(&c.l) {
        return Err(SchemaError::new(format!("{path}.l"), "lightness must be within 0..=1"));
    }
    non_negative(c.c, || format!("{path}.c"))
}

/// Zakaz na osi liniowej (jasność, nasycenie): wymaga `od < do`.
fn check_linear_exclusions(pairs: &[[f64; 2]], path: &str) -> Result<(), SchemaError> {
    for (k, [a, b]) in pairs.iter().enumerate() {
        if a >= b {
            return Err(SchemaError::new(
                format!("{path}.exclude[{k}]"),
                "excluded interval needs lo < hi",
            ));
        }
    }
    Ok(())
}

/// Zakaz na kole odcieni: końce różne modulo 360 (zawijanie przez 0° dozwolone).
fn check_hue_exclusions(pairs: &[[f64; 2]], path: &str) -> Result<(), SchemaError> {
    for (k, [a, b]) in pairs.iter().enumerate() {
        if (b - a).rem_euclid(360.0) == 0.0 {
            return Err(SchemaError::new(
                format!("{path}.exclude[{k}]"),
                "excluded hue arc needs distinct ends (mod 360)",
            ));
        }
    }
    Ok(())
}

fn check_rule_weight<T>(rule: &Option<Rule<T>>, path: &str) -> Result<(), SchemaError> {
    match rule {
        Some(r) => non_negative(r.weight, || format!("{path}.weight")),
        None => Ok(()),
    }
}

fn check_rules(rules: &SlotRules, path: &str) -> Result<(), SchemaError> {
    check_rule_weight(&rules.lightness, &format!("{path}.lightness"))?;
    check_rule_weight(&rules.chroma, &format!("{path}.chroma"))?;
    check_rule_weight(&rules.hue, &format!("{path}.hue"))?;
    check_rule_weight(&rules.contrast_bg, &format!("{path}.contrast_bg"))?;
    check_rule_weight(&rules.min_distance, &format!("{path}.min_distance"))?;
    check_rule_weight(&rules.extreme, &format!("{path}.extreme"))?;
    if let Some(r) = &rules.lightness {
        check_linear_exclusions(&r.value.exclude, &format!("{path}.lightness.value"))?;
    }
    if let Some(r) = &rules.chroma {
        check_linear_exclusions(&r.value.exclude, &format!("{path}.chroma.value"))?;
    }
    if let Some(r) = &rules.hue {
        check_hue_exclusions(&r.value.exclude, &format!("{path}.hue.value"))?;
    }
    Ok(())
}

fn check_relation(rel: &Relation, path: &str) -> Result<(), SchemaError> {
    non_negative(rel.tol, || format!("{path}.tol"))?;
    non_negative(rel.weight, || format!("{path}.weight"))?;
    if let Some(metric) = rel.metric {
        let fits = match rel.kind {
            RelKind::Contrast => metric.as_contrast().is_some(),
            RelKind::Distance => metric.as_delta_e().is_some(),
            _ => false,
        };
        if !fits {
            return Err(SchemaError::new(
                format!("{path}.metric"),
                "metric does not match the relation kind",
            ));
        }
    }
    if !(0.0..=1.0).contains(&rel.t) {
        return Err(SchemaError::new(format!("{path}.t"), "mix ratio must be within 0..=1"));
    }
    Ok(())
}

fn check_globals(g: &GlobalSettings) -> Result<(), SchemaError> {
    non_negative(g.hue_scheme.tol, || "globals.hue_scheme.tol".to_owned())?;
    non_negative(g.hue_scheme.jitter, || "globals.hue_scheme.jitter".to_owned())?;
    non_negative(g.hue_scheme.weight, || "globals.hue_scheme.weight".to_owned())?;
    check_rule_weight(&g.lightness_spread, "globals.lightness_spread")?;
    for (k, c) in g.avoid_colors.iter().enumerate() {
        check_color(c, &format!("globals.avoid_colors[{k}]"))?;
    }
    non_negative(g.avoid_distance, || "globals.avoid_distance".to_owned())?;
    let o = &g.optimizer;
    if o.n_proposals < 1 {
        return Err(SchemaError::new("globals.optimizer.n_proposals", "must be at least 1"));
    }
    if o.budget < 1 {
        return Err(SchemaError::new("globals.optimizer.budget", "must be at least 1"));
    }
    non_negative(o.time_cap_s, || "globals.optimizer.time_cap_s".to_owned())?;
    non_negative(o.min_diversity, || "globals.optimizer.min_diversity".to_owned())?;
    non_negative(o.hard_weight, || "globals.optimizer.hard_weight".to_owned())
}

fn validate(s: &Session) -> Result<(), SchemaError> {
    if s.format != FORMAT {
        return Err(SchemaError::new("format", format!("expected \"{FORMAT}\"")));
    }
    check_globals(&s.globals)?;
    if !(MIN_SLOTS..=MAX_SLOTS).contains(&s.slots.len()) {
        return Err(SchemaError::new(
            "slots",
            format!("expected {MIN_SLOTS} to {MAX_SLOTS} slots, found {}", s.slots.len()),
        ));
    }
    for (i, slot) in s.slots.iter().enumerate() {
        if s.slots[..i].iter().any(|other| other.id == slot.id) {
            return Err(SchemaError::new(format!("slots[{i}].id"), "duplicate slot id"));
        }
        check_color(&slot.value, &format!("slots[{i}].value"))?;
        check_rules(&slot.rules, &format!("slots[{i}].rules"))?;
        for (n, rel) in slot.relations.iter().enumerate() {
            check_relation(rel, &format!("slots[{i}].relations[{n}]"))?;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `as_str` musi dawać tę samą nazwę co serde (dokument i raport naruszeń mówią jednym
    /// językiem).
    #[test]
    fn static_names_match_serde_names() {
        fn check<T: Serialize + Copy>(values: &[T], name: fn(T) -> &'static str) {
            for &v in values {
                assert_eq!(serde_json::to_value(v).unwrap(), serde_json::json!(name(v)));
            }
        }
        check(&[ContrastMetric::Wcag21, ContrastMetric::Apca], ContrastMetric::as_str);
        check(
            &[DeltaE::Ok, DeltaE::Ciede2000, DeltaE::Hyab, DeltaE::Itp, DeltaE::Cam16],
            DeltaE::as_str,
        );
        check(&[ChromaMode::Abs, ChromaMode::Rel], ChromaMode::as_str);
        check(&[ChromaOp::Add, ChromaOp::Mul], ChromaOp::as_str);
        check(&[Extreme::Weakest, Extreme::Strongest], Extreme::as_str);
        check(
            &[
                RelKind::Hue,
                RelKind::Lightness,
                RelKind::Chroma,
                RelKind::Contrast,
                RelKind::Distance,
                RelKind::Mix,
            ],
            RelKind::as_str,
        );
        check(&[RelOp::Eq, RelOp::Ge, RelOp::Le], RelOp::as_str);
    }

    #[test]
    fn enums_are_found_by_document_name() {
        assert_eq!(enum_from_name::<DeltaE>("2000"), Some(DeltaE::Ciede2000));
        assert_eq!(enum_from_name::<DeltaE>("ok"), Some(DeltaE::Ok));
        assert_eq!(enum_from_name::<ContrastMetric>("apca"), Some(ContrastMetric::Apca));
        assert_eq!(enum_from_name::<FitMethod>("oklch-chroma"), Some(FitMethod::OklchChroma));
        assert_eq!(enum_from_name::<DeltaE>("76"), None);
        assert_eq!(enum_from_name::<DeltaE>("Ok"), None);
        assert_eq!(enum_from_name::<FitMethod>(""), None);
    }
}
