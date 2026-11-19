//! Kontrakt schematu `algopalette.v2` (plan I1): Python i Rust czytają te same bajty.
//!
//! Część pozytywna czyta WSZYSTKIE `*.json` z `tests/fixtures/v2_contract/` (pliki `manual_*`
//! pisane ręcznie + pliki generowane z `eval.json` przez `migrate_v1` po stronie Pythona).
//! Część negatywna psuje jeden z ręcznych plików i sprawdza ścieżkę w komunikacie.

use std::fs;
use std::path::PathBuf;

use algopalette_core::schema::{self, ChromaMode, RelKind, SchemaError};
use serde_json::{Value, json};

fn contract_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../tests/fixtures/v2_contract")
}

fn read(name: &str) -> String {
    fs::read_to_string(contract_dir().join(name)).expect("plik kontraktu")
}

fn base() -> Value {
    serde_json::from_str(&read("manual_exclusions.json")).expect("poprawny JSON")
}

/// Parsuje zepsuty dokument i zwraca błąd (test pada, gdy dokument przechodzi).
fn err_of(doc: &Value) -> SchemaError {
    match schema::parse(&doc.to_string()) {
        Ok(_) => panic!("dokument powinien zostać odrzucony"),
        Err(e) => e,
    }
}

#[test]
fn every_contract_file_parses() {
    let mut names: Vec<String> = fs::read_dir(contract_dir())
        .expect("katalog kontraktu")
        .map(|e| e.expect("wpis").file_name().into_string().expect("nazwa utf-8"))
        .filter(|n| n.ends_with(".json"))
        .collect();
    names.sort();
    assert!(names.len() >= 12, "za mało plików kontraktu: {}", names.len());
    for name in &names {
        if let Err(e) = schema::parse(&read(name)) {
            panic!("{name}: {e}");
        }
    }
}

#[test]
fn exclusions_are_read_in_all_three_channels() {
    let s = schema::parse(&read("manual_exclusions.json")).unwrap();
    assert_eq!(s.slots.len(), 4);
    let r = &s.slots[2].rules;
    let l = r.lightness.as_ref().unwrap();
    assert_eq!(l.value.exclude, vec![[0.6, 0.65], [0.8, 0.82]]);
    assert_eq!((l.value.lo, l.value.hi), (Some(0.55), Some(0.9)));
    let c = r.chroma.as_ref().unwrap();
    assert_eq!(c.value.mode, ChromaMode::Rel);
    assert_eq!(c.value.exclude, vec![[0.5, 0.6]]);
    assert!(!c.hard);
    assert_eq!(c.weight, 2.5);
    let h = r.hue.as_ref().unwrap();
    // łuk przez 0° i zakaz przez 0°
    assert_eq!((h.value.lo, h.value.hi), (300.0, 90.0));
    assert_eq!(h.value.exclude, vec![[350.0, 10.0], [40.0, 55.0]]);
    assert_eq!(s.preset, None);
}

#[test]
fn full_circle_and_integer_numbers_are_accepted() {
    let s = schema::parse(&read("manual_full_circle.json")).unwrap();
    let h = s.slots[2].rules.hue.as_ref().unwrap();
    assert_eq!((h.value.lo, h.value.hi), (0.0, 360.0));
    assert!(s.globals.hue_scheme.hues.is_empty());
    assert!(!s.slots[3].use_scheme);
}

#[test]
fn sixteen_slots_and_wide_seed_are_accepted() {
    let s = schema::parse(&read("manual_16_colors.json")).unwrap();
    assert_eq!(s.slots.len(), 16);
    assert_eq!(s.globals.optimizer.seed, 12_345_678_901_234);
    assert_eq!(s.globals.optimizer.n_proposals, 128);
    assert_eq!(s.globals.optimizer.threads, 16);
    assert!(s.slots[4].locked);
}

#[test]
fn null_rules_and_null_spread_are_accepted() {
    let s = schema::parse(&read("manual_all_null.json")).unwrap();
    assert!(s.globals.lightness_spread.is_none());
    for slot in &s.slots {
        let r = &slot.rules;
        assert!(r.lightness.is_none() && r.chroma.is_none() && r.hue.is_none());
        assert!(r.contrast_bg.is_none() && r.min_distance.is_none() && r.extreme.is_none());
    }
}

#[test]
fn relations_keep_v1_shape() {
    let s = schema::parse(&read("manual_relations.json")).unwrap();
    let rels = &s.slots[2].relations;
    assert_eq!(rels.len(), 16);
    let kinds: Vec<RelKind> = rels.iter().map(|r| r.kind).collect();
    for k in [
        RelKind::Hue,
        RelKind::Lightness,
        RelKind::Chroma,
        RelKind::Contrast,
        RelKind::Distance,
        RelKind::Mix,
    ] {
        assert!(kinds.contains(&k), "brak zależności rodzaju {k:?}");
    }
    let mix = rels.iter().find(|r| r.kind == RelKind::Mix).unwrap();
    assert_eq!(mix.other.as_deref(), Some("acc00003"));
    assert_eq!(mix.t, 0.25);
    // zerwana zależność (cel nie istnieje) to nie błąd schematu
    assert_eq!(rels[15].target, "usuniety");
}

#[test]
fn avoid_colors_and_custom_scheme_are_read() {
    let s = schema::parse(&read("manual_avoid_custom.json")).unwrap();
    assert_eq!(s.globals.avoid_colors.len(), 3);
    assert_eq!(s.globals.avoid_distance, 0.05);
    assert_eq!(s.globals.hue_scheme.hues[..3], [15.0, 140.0, 280.0]);
    assert!(s.globals.lightness_spread.is_some());
}

// ---------------------------------------------------------------------------
// Przypadki negatywne
// ---------------------------------------------------------------------------

#[test]
fn unknown_field_is_rejected_with_its_path() {
    let mut doc = base();
    doc["slots"][2]["rules"]["hue"]["value"]["foo"] = json!(1);
    let e = err_of(&doc);
    assert_eq!(e.path, "slots[2].rules.hue.value.foo");
    assert!(e.to_string().starts_with("slots[2].rules.hue.value.foo: "), "{e}");
}

#[test]
fn unknown_top_level_and_globals_fields_are_rejected() {
    let mut doc = base();
    doc["mood"] = Value::Null;
    assert_eq!(err_of(&doc).path, "mood");
    let mut doc = base();
    doc["globals"]["role_defaults"] = json!({});
    assert_eq!(err_of(&doc).path, "globals.role_defaults");
    let mut doc = base();
    doc["globals"]["optimizer"]["max_evals"] = json!(8000);
    assert_eq!(err_of(&doc).path, "globals.optimizer.max_evals");
}

#[test]
fn lightness_exclusion_needs_lo_below_hi() {
    for pair in [json!([0.7, 0.7]), json!([0.74, 0.70])] {
        let mut doc = base();
        doc["slots"][2]["rules"]["lightness"]["value"]["exclude"][1] = pair;
        assert_eq!(err_of(&doc).path, "slots[2].rules.lightness.value.exclude[1]");
    }
}

#[test]
fn chroma_exclusion_needs_lo_below_hi() {
    let mut doc = base();
    doc["slots"][2]["rules"]["chroma"]["value"]["exclude"][0] = json!([0.6, 0.5]);
    assert_eq!(err_of(&doc).path, "slots[2].rules.chroma.value.exclude[0]");
}

#[test]
fn hue_exclusion_ends_must_differ_mod_360() {
    for pair in [json!([10.0, 10.0]), json!([10.0, 370.0]), json!([0.0, 360.0])] {
        let mut doc = base();
        doc["slots"][2]["rules"]["hue"]["value"]["exclude"][0] = pair;
        assert_eq!(err_of(&doc).path, "slots[2].rules.hue.value.exclude[0]");
    }
}

#[test]
fn exclusion_pair_must_have_two_numbers() {
    for bad in [json!([10.0, 20.0, 30.0]), json!([10.0]), json!([])] {
        let mut doc = base();
        doc["slots"][2]["rules"]["hue"]["value"]["exclude"][0] = bad;
        assert_eq!(err_of(&doc).path, "slots[2].rules.hue.value.exclude[0]");
    }
}

#[test]
fn duplicate_slot_id_is_rejected() {
    let mut doc = base();
    doc["slots"][3]["id"] = doc["slots"][1]["id"].clone();
    assert_eq!(err_of(&doc).path, "slots[3].id");
}

#[test]
fn slot_count_must_be_3_to_16() {
    let mut doc = base();
    doc["slots"].as_array_mut().unwrap().truncate(2);
    assert_eq!(err_of(&doc).path, "slots");

    let mut doc = base();
    let template = doc["slots"][2].clone();
    let slots = doc["slots"].as_array_mut().unwrap();
    while slots.len() < 17 {
        let mut s = template.clone();
        s["id"] = json!(format!("extra{:03}", slots.len()));
        slots.push(s);
    }
    assert_eq!(err_of(&doc).path, "slots");
    // 16 z tej samej konstrukcji przechodzi — odrzucenie wynika z liczby, nie z treści
    doc["slots"].as_array_mut().unwrap().truncate(16);
    schema::parse(&doc.to_string()).unwrap();
}

#[test]
fn color_values_are_range_checked() {
    let mut doc = base();
    doc["slots"][0]["value"]["l"] = json!(1.01);
    assert_eq!(err_of(&doc).path, "slots[0].value.l");
    let mut doc = base();
    doc["slots"][1]["value"]["c"] = json!(-0.001);
    assert_eq!(err_of(&doc).path, "slots[1].value.c");
    let mut doc = base();
    doc["globals"]["avoid_colors"] = json!([{"l": -0.1, "c": 0.1, "h": 0.0}]);
    assert_eq!(err_of(&doc).path, "globals.avoid_colors[0].l");
}

#[test]
fn weights_must_be_non_negative() {
    let mut doc = base();
    doc["slots"][2]["rules"]["chroma"]["weight"] = json!(-1.0);
    assert_eq!(err_of(&doc).path, "slots[2].rules.chroma.weight");
    let mut doc = base();
    doc["globals"]["hue_scheme"]["weight"] = json!(-0.5);
    assert_eq!(err_of(&doc).path, "globals.hue_scheme.weight");
    let mut doc = base();
    doc["globals"]["lightness_spread"]["weight"] = json!(-0.5);
    assert_eq!(err_of(&doc).path, "globals.lightness_spread.weight");
}

#[test]
fn optimizer_limits_are_checked() {
    let cases = [
        ("seed", json!(-1)),
        ("budget", json!(0)),
        ("threads", json!(-1)),
        ("n_proposals", json!(0)),
        ("budget", json!(2.5)),
        ("time_cap_s", json!(-1.0)),
    ];
    for (key, bad) in cases {
        let mut doc = base();
        doc["globals"]["optimizer"][key] = bad;
        assert_eq!(err_of(&doc).path, format!("globals.optimizer.{key}"));
    }
}

#[test]
fn wrong_format_tag_is_rejected() {
    let mut doc = base();
    doc["format"] = json!("algopalette.v1");
    assert_eq!(err_of(&doc).path, "format");
}

#[test]
fn every_rule_key_must_be_present() {
    let mut doc = base();
    doc["slots"][2]["rules"].as_object_mut().unwrap().remove("extreme");
    let e = err_of(&doc);
    assert_eq!(e.path, "slots[2].rules");
    assert!(e.msg.contains("extreme"), "{e}");

    let mut doc = base();
    doc["globals"].as_object_mut().unwrap().remove("lightness_spread");
    let e = err_of(&doc);
    assert_eq!(e.path, "globals");
    assert!(e.msg.contains("lightness_spread"), "{e}");
}

#[test]
fn enum_values_are_checked() {
    let mut doc = base();
    doc["globals"]["delta_e"] = json!("cie76");
    assert_eq!(err_of(&doc).path, "globals.delta_e");
    let mut doc = base();
    doc["slots"][2]["rules"]["chroma"]["value"]["mode"] = json!("relative");
    assert_eq!(err_of(&doc).path, "slots[2].rules.chroma.value.mode");
}

#[test]
fn relation_metric_must_match_its_kind() {
    let mut doc: Value = serde_json::from_str(&read("manual_relations.json")).unwrap();
    // zależność nr 5 to kontrast; metryka ΔE do niej nie pasuje
    assert_eq!(doc["slots"][2]["relations"][5]["kind"], json!("contrast"));
    doc["slots"][2]["relations"][5]["metric"] = json!("2000");
    assert_eq!(err_of(&doc).path, "slots[2].relations[5].metric");

    let mut doc: Value = serde_json::from_str(&read("manual_relations.json")).unwrap();
    doc["slots"][2]["relations"][14]["t"] = json!(1.5);
    assert_eq!(err_of(&doc).path, "slots[2].relations[14].t");
}

#[test]
fn malformed_json_reports_root_path() {
    let e = schema::parse("{\"format\": ").unwrap_err();
    assert_eq!(e.path, "$");
    let e = schema::parse("[]").unwrap_err();
    assert_eq!(e.path, "$");
}
