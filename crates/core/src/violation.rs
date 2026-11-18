//! Naruszenie zasady w kształcie przekazywanym do Pythona (plan I3, tabela `V`).
//!
//! Rust podaje wyłącznie liczby, identyfikatory i nazwy techniczne; polskie napisy składa
//! `forms.violation_text` po stronie Pythona.

use serde::Serialize;
use serde_json::{Map, Value};

/// Rodzaj naruszenia (`kind` w tabeli I3).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ViolationKind {
    Lightness,
    Chroma,
    ContrastBg,
    Hue,
    Exclude,
    Extreme,
    PairDistance,
    Rel,
    Spread,
    Scheme,
    Avoid,
    Gamut,
    Diversity,
}

impl ViolationKind {
    /// Nazwa przekazywana do Pythona.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Lightness => "lightness",
            Self::Chroma => "chroma",
            Self::ContrastBg => "contrast_bg",
            Self::Hue => "hue",
            Self::Exclude => "exclude",
            Self::Extreme => "extreme",
            Self::PairDistance => "pair_distance",
            Self::Rel => "rel",
            Self::Spread => "spread",
            Self::Scheme => "scheme",
            Self::Avoid => "avoid",
            Self::Gamut => "gamut",
            Self::Diversity => "diversity",
        }
    }
}

/// Jedno naruszenie: klucz termu, kolory, wielkość, wartość osiągnięta i wymaganie w liczbach.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Violation {
    /// Stabilny klucz termu (patrz funkcje `key_*`).
    pub key: String,
    /// Identyfikatory kolorów, których naruszenie dotyczy.
    pub slots: Vec<String>,
    pub kind: ViolationKind,
    pub hard: bool,
    /// Wielkość naruszenia w jednostkach kanału (> 0).
    pub amount: f64,
    /// Wartość osiągnięta.
    pub achieved: f64,
    /// Wymaganie w postaci liczb, np. `{"lo": 4.5, "hi": null}`.
    pub req: Map<String, Value>,
    /// Metadane: metryka, tryb nasycenia itd.
    pub meta: Map<String, Value>,
}

/// `slot:<id>:<kind>` — zasady jednego koloru: `lightness`, `chroma`, `contrast_bg`, `hue`,
/// `extreme`, `gamut`.
pub fn key_slot(id: &str, kind: ViolationKind) -> String {
    format!("slot:{id}:{}", kind.as_str())
}

/// `slot:<id>:<kanał>:exclude:<k>` — zakazany przedział nr `k` kanału `lightness|chroma|hue`.
pub fn key_exclude(id: &str, channel: &str, k: usize) -> String {
    format!("slot:{id}:{channel}:exclude:{k}")
}

/// `pair:<a>:<b>:min_distance`.
pub fn key_pair_distance(a: &str, b: &str) -> String {
    format!("pair:{a}:{b}:min_distance")
}

/// `slot:<id>:rel:<rodzaj>:<n>` — zależność nr `n` koloru.
pub fn key_rel(id: &str, rel_kind: &str, n: usize) -> String {
    format!("slot:{id}:rel:{rel_kind}:{n}")
}

/// `global:lightness_spread`.
pub const KEY_SPREAD: &str = "global:lightness_spread";

/// `global:diversity` (tylko w propozycjach).
pub const KEY_DIVERSITY: &str = "global:diversity";

/// `global:scheme:<id>` — cel układu odcieni dla koloru.
pub fn key_scheme(id: &str) -> String {
    format!("global:scheme:{id}")
}

/// `global:avoid:<id>:<k>` — odległość koloru od unikanego koloru nr `k`.
pub fn key_avoid(id: &str, k: usize) -> String {
    format!("global:avoid:{id}:{k}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    const ALL: [ViolationKind; 13] = [
        ViolationKind::Lightness,
        ViolationKind::Chroma,
        ViolationKind::ContrastBg,
        ViolationKind::Hue,
        ViolationKind::Exclude,
        ViolationKind::Extreme,
        ViolationKind::PairDistance,
        ViolationKind::Rel,
        ViolationKind::Spread,
        ViolationKind::Scheme,
        ViolationKind::Avoid,
        ViolationKind::Gamut,
        ViolationKind::Diversity,
    ];

    #[test]
    fn kind_names_match_i3_table() {
        let names: Vec<&str> = ALL.iter().map(|k| k.as_str()).collect();
        assert_eq!(
            names,
            [
                "lightness",
                "chroma",
                "contrast_bg",
                "hue",
                "exclude",
                "extreme",
                "pair_distance",
                "rel",
                "spread",
                "scheme",
                "avoid",
                "gamut",
                "diversity"
            ]
        );
        // serde i `as_str` muszą dawać tę samą nazwę
        for k in ALL {
            assert_eq!(serde_json::to_value(k).unwrap(), json!(k.as_str()));
        }
    }

    #[test]
    fn keys_match_i3_table() {
        assert_eq!(key_slot("a1", ViolationKind::Lightness), "slot:a1:lightness");
        assert_eq!(key_slot("a1", ViolationKind::ContrastBg), "slot:a1:contrast_bg");
        assert_eq!(key_slot("a1", ViolationKind::Gamut), "slot:a1:gamut");
        assert_eq!(key_exclude("a1", "hue", 2), "slot:a1:hue:exclude:2");
        assert_eq!(key_pair_distance("a1", "b2"), "pair:a1:b2:min_distance");
        assert_eq!(key_rel("a1", "mix", 0), "slot:a1:rel:mix:0");
        assert_eq!(key_scheme("a1"), "global:scheme:a1");
        assert_eq!(key_avoid("a1", 3), "global:avoid:a1:3");
        assert_eq!(KEY_SPREAD, "global:lightness_spread");
        assert_eq!(KEY_DIVERSITY, "global:diversity");
    }

    #[test]
    fn violation_serializes_to_i3_shape() {
        let mut req = Map::new();
        req.insert("lo".into(), json!(4.5));
        req.insert("hi".into(), Value::Null);
        let mut meta = Map::new();
        meta.insert("metric".into(), json!("wcag21"));
        let v = Violation {
            key: key_slot("a1", ViolationKind::ContrastBg),
            slots: vec!["a1".into()],
            kind: ViolationKind::ContrastBg,
            hard: true,
            amount: 0.7,
            achieved: 3.8,
            req,
            meta,
        };
        assert_eq!(
            serde_json::to_value(&v).unwrap(),
            json!({
                "key": "slot:a1:contrast_bg",
                "slots": ["a1"],
                "kind": "contrast_bg",
                "hard": true,
                "amount": 0.7,
                "achieved": 3.8,
                "req": {"lo": 4.5, "hi": null},
                "meta": {"metric": "wcag21"}
            })
        );
    }
}
