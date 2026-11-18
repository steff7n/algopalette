//! Moduł Pythona `algopalette._engine` (plan I3): cienka warstwa PyO3 nad `algopalette_core`.
//!
//! Wszystkie funkcje I3 są gotowe (`build_info()["implemented"]`): schemat, kolor, ocena zasad,
//! generowanie. Rust zwraca liczby i nazwy techniczne; napisy dla człowieka składa Python.

use algopalette_core::color::{self, ContrastMetric, DeltaE};
use algopalette_core::optim;
use algopalette_core::rules::{self, Problem};
use algopalette_core::schema::{self, SchemaError, Session};
use algopalette_core::violation::Violation;
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use std::sync::Arc;

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use serde_json::{Map, Value};

/// Funkcje gotowe w tej kompilacji (`build_info()["implemented"]`).
const IMPLEMENTED: &[&str] = &["schema", "color", "evaluate", "generate"];

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

/// Wartość JSON z raportu naruszenia jako obiekt Pythona.
fn json_to_py<'py>(py: Python<'py>, value: &Value) -> PyResult<Bound<'py, PyAny>> {
    Ok(match value {
        Value::Null => py.None().into_bound(py),
        Value::Bool(b) => b.into_pyobject(py)?.to_owned().into_any(),
        Value::Number(n) => match n.as_f64() {
            Some(f) => f.into_pyobject(py)?.into_any(),
            None => py.None().into_bound(py),
        },
        Value::String(s) => s.into_pyobject(py)?.into_any(),
        Value::Array(items) => {
            let converted: PyResult<Vec<_>> = items.iter().map(|v| json_to_py(py, v)).collect();
            PyList::new(py, converted?)?.into_any()
        }
        Value::Object(map) => map_to_py(py, map)?.into_any(),
    })
}

fn map_to_py<'py>(py: Python<'py>, map: &Map<String, Value>) -> PyResult<Bound<'py, PyDict>> {
    let out = PyDict::new(py);
    for (key, value) in map {
        out.set_item(key, json_to_py(py, value)?)?;
    }
    Ok(out)
}

/// Naruszenie w kształcie `V` z tabeli I3.
fn violation_to_py<'py>(py: Python<'py>, v: &Violation) -> PyResult<Bound<'py, PyDict>> {
    let out = PyDict::new(py);
    out.set_item("key", &v.key)?;
    out.set_item("slots", PyList::new(py, &v.slots)?)?;
    out.set_item("kind", v.kind.as_str())?;
    out.set_item("hard", v.hard)?;
    out.set_item("amount", v.amount)?;
    out.set_item("achieved", v.achieved)?;
    out.set_item("req", map_to_py(py, &v.req)?)?;
    out.set_item("meta", map_to_py(py, &v.meta)?)?;
    Ok(out)
}

fn violations_to_py<'py>(py: Python<'py>, list: &[Violation]) -> PyResult<Bound<'py, PyList>> {
    let converted: PyResult<Vec<_>> = list.iter().map(|v| violation_to_py(py, v)).collect();
    PyList::new(py, converted?)
}

/// Ocena bieżących wartości sesji: `{"objective": float, "violations": [V, ...]}` — funkcja
/// celu bez marginesu twardych zasad i naruszenia o wielkości > 1e-9.
#[pyfunction]
fn evaluate<'py>(py: Python<'py>, session_json: &str) -> PyResult<Bound<'py, PyDict>> {
    let evaluation = rules::evaluate(&parse(session_json)?);
    let out = PyDict::new(py);
    out.set_item("objective", evaluation.objective)?;
    out.set_item("violations", violations_to_py(py, &evaluation.violations)?)?;
    Ok(out)
}

/// Cele układu odcieni `{id: stopnie}` dla wszystkich akcentów (pusty, gdy układ nie daje celów).
#[pyfunction]
fn hue_targets<'py>(py: Python<'py>, session_json: &str) -> PyResult<Bound<'py, PyDict>> {
    let out = PyDict::new(py);
    for (id, hue) in rules::hue_targets(&parse(session_json)?) {
        out.set_item(id, hue)?;
    }
    Ok(out)
}

/// Zadanie generowania: wątki Rusta bez GIL, odpytywane przez `poll`.
#[pyclass(frozen, module = "algopalette._engine")]
struct Job {
    job: optim::Job,
    problem: Arc<Problem>,
    min_diversity: f64,
}

#[pymethods]
impl Job {
    /// `{"state": "running"|"done"|"cancelled"|"failed", "progress", "candidates", "error"}`.
    /// Nie blokuje.
    fn poll<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let status = self.job.poll();
        let out = PyDict::new(py);
        out.set_item("state", status.state.as_str())?;
        out.set_item("progress", status.progress)?;
        out.set_item("candidates", status.candidates)?;
        out.set_item("error", status.error)?;
        Ok(out)
    }

    /// Prosi o przerwanie; zadanie kończy się w ≤ 100 ms z propozycjami z ukończonych przebiegów.
    fn cancel(&self) {
        self.job.cancel();
    }

    /// `{"proposals": [P, ...], "timed_out", "cancelled", "runs", "elapsed_s"}`. Zadanie w toku
    /// albo zakończone błędem → `RuntimeError`.
    fn result<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let finished = self.job.result().map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        let proposals = PyList::empty(py);
        for p in rules::proposals(&self.problem, &finished.outcome, self.min_diversity) {
            let values = PyDict::new(py);
            for (id, lch) in &p.values {
                values.set_item(id, PyList::new(py, lch)?)?;
            }
            let item = PyDict::new(py);
            item.set_item("values", values)?;
            item.set_item("score", p.score)?;
            item.set_item("violations", violations_to_py(py, &p.violations)?)?;
            item.set_item("run", p.run)?;
            item.set_item("wave", p.wave)?;
            proposals.append(item)?;
        }
        let out = PyDict::new(py);
        out.set_item("proposals", proposals)?;
        out.set_item("timed_out", finished.outcome.timed_out)?;
        out.set_item("cancelled", finished.outcome.cancelled)?;
        out.set_item("runs", finished.outcome.runs)?;
        out.set_item("elapsed_s", finished.elapsed.as_secs_f64())?;
        Ok(out)
    }
}

/// Uruchamia generowanie dla kolorów wolnych `free` (id) i wraca natychmiast. Kolory spoza
/// `free` silnik bierze takie, jakie są w dokumencie (Python podaje je już po dopasowaniu do
/// gamutu). Parametry z `globals.optimizer`.
#[pyfunction]
fn start(session_json: &str, free: Vec<String>) -> PyResult<Job> {
    let session = parse(session_json)?;
    for (k, id) in free.iter().enumerate() {
        if !session.slots.iter().any(|s| &s.id == id) {
            return Err(PyValueError::new_err(format!("free[{k}]: unknown slot id")));
        }
    }
    let problem = Arc::new(Problem::compile(&session, &free));
    let opts = rules::driver_opts(&session, &problem);
    let min_diversity = opts.min_diversity;
    Ok(Job { job: optim::Job::spawn(Arc::clone(&problem), opts), problem, min_diversity })
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
        max_chroma, oklch_to_linear_srgb, start, validate,
    };
}
