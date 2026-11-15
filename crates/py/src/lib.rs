//! Moduł Pythona `algopalette._engine` (plan I3): cienka warstwa PyO3 nad `algopalette_core`.
//!
//! Stan po Tasku 5: działają `build_info`, `validate` i funkcje koloru; `evaluate`, `hue_targets`
//! i `start` są zaślepkami o docelowych sygnaturach (sprawdzają dokument, zwracają pusty wynik).
//! Lista `IMPLEMENTED` rośnie z kolejnymi zadaniami; funkcja niegotowa zgłasza
//! `NotImplementedError`.

use algopalette_core::color::{self, ContrastMetric, CvdKind, CvdMethod, DeltaE};
use algopalette_core::schema::{self, SchemaError, Session};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

/// Funkcje gotowe w tej kompilacji (`build_info()["implemented"]`).
const IMPLEMENTED: &[&str] = &["schema", "color"];

fn schema_error(e: SchemaError) -> PyErr {
    PyValueError::new_err(e.to_string())
}

fn parse(session_json: &str) -> PyResult<Session> {
    schema::parse(session_json).map_err(schema_error)
}

/// Informacja o kompilacji: `{"version", "profile": "release"|"debug", "implemented": [...]}`.
#[pyfunction]
fn build_info(py: Python<'_>) -> PyResult<Bound<'_, PyDict>> {
    let info = PyDict::new(py);
    info.set_item("version", algopalette_core::VERSION)?;
    info.set_item("profile", if cfg!(debug_assertions) { "debug" } else { "release" })?;
    info.set_item("implemented", PyList::new(py, IMPLEMENTED)?)?;
    Ok(info)
}

/// Sprawdza dokument `algopalette.v2`; błąd to `ValueError("<ścieżka>: <opis>")`.
#[pyfunction]
fn validate(session_json: &str) -> PyResult<()> {
    parse(session_json).map(|_| ())
}

/// Ocena bieżących wartości sesji: `{"objective": float, "violations": [V, ...]}`.
/// Zaślepka do Tasku 14: pusty wynik.
#[pyfunction]
fn evaluate<'py>(py: Python<'py>, session_json: &str) -> PyResult<Bound<'py, PyDict>> {
    parse(session_json)?;
    let out = PyDict::new(py);
    out.set_item("objective", 0.0)?;
    out.set_item("violations", PyList::empty(py))?;
    Ok(out)
}

/// Cele układu odcieni `{id: stopnie}`. Zaślepka do Tasku 14: `{}`.
#[pyfunction]
fn hue_targets<'py>(py: Python<'py>, session_json: &str) -> PyResult<Bound<'py, PyDict>> {
    parse(session_json)?;
    Ok(PyDict::new(py))
}

/// Zadanie generowania. Zaślepka do Tasku 16: od razu `done` z pustą listą propozycji.
#[pyclass(frozen, module = "algopalette._engine")]
struct Job {}

#[pymethods]
impl Job {
    /// `{"state": "running"|"done"|"cancelled"|"failed", "progress", "candidates", "error"}`.
    fn poll<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let out = PyDict::new(py);
        out.set_item("state", "done")?;
        out.set_item("progress", 1.0)?;
        out.set_item("candidates", 0)?;
        out.set_item("error", py.None())?;
        Ok(out)
    }

    /// Prosi o przerwanie; zadanie reaguje w ≤ 100 ms.
    fn cancel(&self) {}

    /// `{"proposals": [P, ...], "timed_out", "cancelled", "runs", "elapsed_s"}`.
    fn result<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let out = PyDict::new(py);
        out.set_item("proposals", PyList::empty(py))?;
        out.set_item("timed_out", false)?;
        out.set_item("cancelled", false)?;
        out.set_item("runs", 0)?;
        out.set_item("elapsed_s", 0.0)?;
        Ok(out)
    }
}

/// Uruchamia generowanie dla kolorów wolnych `free` (id). Kolory spoza `free` silnik bierze
/// takie, jakie są w dokumencie (Python podaje je już po dopasowaniu do gamutu).
#[pyfunction]
fn start(session_json: &str, free: Vec<String>) -> PyResult<Job> {
    let session = parse(session_json)?;
    for (k, id) in free.iter().enumerate() {
        if !session.slots.iter().any(|s| &s.id == id) {
            return Err(PyValueError::new_err(format!("free[{k}]: unknown slot id")));
        }
    }
    Ok(Job {})
}

/// Wartość wyliczenia po nazwie; nieznana nazwa to `ValueError("<argument>: ...")`.
fn named<'a, T: serde::Deserialize<'a>>(argument: &str, name: &'a str) -> PyResult<T> {
    schema::enum_from_name(name)
        .ok_or_else(|| PyValueError::new_err(format!("{argument}: unknown value \"{name}\"")))
}

/// Największe C w sRGB przy (L, H°).
#[pyfunction]
fn max_chroma(l: f64, h: f64) -> f64 {
    color::max_chroma(l, h)
}

/// ΔE dwóch kolorów OKLCH `[l, c, h]` metodą `ok|2000|hyab|itp|cam16`.
#[pyfunction]
fn delta_e(a: [f64; 3], b: [f64; 3], method: &str) -> PyResult<f64> {
    let method: DeltaE = named("method", method)?;
    Ok(color::delta_e(color::oklch_to_oklab(a), color::oklch_to_oklab(b), method))
}

/// Kontrast (tekst, tło) w OKLCH metryką `wcag21|apca`; APCA zwraca |Lc|.
#[pyfunction]
fn contrast(text: [f64; 3], bg: [f64; 3], metric: &str) -> PyResult<f64> {
    let metric: ContrastMetric = named("metric", metric)?;
    Ok(color::contrast(color::oklch_to_oklab(text), color::oklch_to_oklab(bg), metric))
}

/// Symulacja daltonizmu koloru OKLCH; zwraca OKLCH `[l, c, h]` bez przycinania do gamutu.
#[pyfunction]
fn simulate_cvd(c: [f64; 3], kind: &str, method: &str, severity: f64) -> PyResult<[f64; 3]> {
    let kind: CvdKind = named("kind", kind)?;
    let method: CvdMethod = named("method", method)?;
    let lab = color::simulate_cvd(color::oklch_to_oklab(c), kind, method, severity);
    Ok(color::oklab_to_oklch(lab))
}

// -- dodatki ponad I3 (testy zgodności z wyrocznią, narzędzia) --

/// OKLCH `[l, c, h]` → liniowy sRGB `[r, g, b]` (bez obcinania).
#[pyfunction]
fn oklch_to_linear_srgb(c: [f64; 3]) -> [f64; 3] {
    color::oklab_to_linear_srgb(color::oklch_to_oklab(c))
}

/// Liniowy sRGB `[r, g, b]` → OKLCH `[l, c, h]`.
#[pyfunction]
fn linear_srgb_to_oklch(rgb: [f64; 3]) -> [f64; 3] {
    color::oklab_to_oklch(color::linear_srgb_to_oklab(rgb))
}

/// Czy kolor OKLCH mieści się w sRGB (kanały liniowe w [−1e-6, 1 + 1e-6]).
#[pyfunction]
fn in_gamut(c: [f64; 3]) -> bool {
    color::in_gamut(c)
}

/// Natywny silnik AlgoPalette.
#[pymodule(name = "_engine")]
mod engine_module {
    #[pymodule_export]
    use super::{
        Job, build_info, contrast, delta_e, evaluate, hue_targets, in_gamut, linear_srgb_to_oklch,
        max_chroma, oklch_to_linear_srgb, simulate_cvd, start, validate,
    };
}
