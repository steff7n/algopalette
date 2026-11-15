//! Rdzeń silnika AlgoPalette (czysty Rust, bez Pythona).
//!
//! - [`schema`] — dokument `algopalette.v2` (plik sesji = wejście silnika).
//! - [`rng`] — zamrożony generator liczb losowych.
//! - [`objective`] — kontrakt funkcji celu dla optymalizatora.
//! - [`violation`] — naruszenie zasady w kształcie przekazywanym do Pythona.

pub mod color;
pub mod objective;
pub mod rng;
pub mod scalar;
pub mod schema;
pub mod violation;

/// Wersja rdzenia (z `Cargo.toml`).
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
