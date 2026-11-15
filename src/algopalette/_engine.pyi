"""Typy modułu natywnego ``algopalette._engine`` (Rust: ``crates/py``, plan I3).

Sam moduł to plik ``_engine.abi3.so`` budowany przez maturin; ten plik istnieje tylko dla
narzędzi sprawdzających typy.
"""

from collections.abc import Sequence
from typing import Any

def build_info() -> dict[str, Any]:
    """``{"version": str, "profile": "release" | "debug", "implemented": list[str]}``."""

def validate(session_json: str) -> None:
    """Sprawdza dokument ``algopalette.v2``; ``ValueError("<ścieżka>: <opis>")``."""

def evaluate(session_json: str) -> dict[str, Any]:
    """``{"objective": float, "violations": [V, ...]}``."""

def hue_targets(session_json: str) -> dict[str, float]:
    """Cele układu odcieni ``{id: stopnie}``."""

def start(session_json: str, free: Sequence[str]) -> Job:
    """Uruchamia generowanie dla kolorów wolnych ``free`` (id)."""

class Job:
    def poll(self) -> dict[str, Any]:
        """``{"state", "progress", "candidates", "error"}``; nie blokuje."""

    def cancel(self) -> None: ...
    def result(self) -> dict[str, Any]:
        """``{"proposals": [P, ...], "timed_out", "cancelled", "runs", "elapsed_s"}``."""

def max_chroma(l: float, h: float) -> float:
    """Największe C w sRGB przy (L, H°)."""

def delta_e(a: Sequence[float], b: Sequence[float], method: str) -> float:
    """ΔE dwóch kolorów OKLCH ``[l, c, h]``; ``method``: ok, 2000, hyab, itp, cam16."""

def contrast(text: Sequence[float], bg: Sequence[float], metric: str) -> float:
    """Kontrast (tekst, tło) w OKLCH; ``metric``: wcag21, apca (|Lc|)."""

def simulate_cvd(c: Sequence[float], kind: str, method: str, severity: float) -> list[float]:
    """Symulacja daltonizmu koloru OKLCH; wynik OKLCH bez przycinania do gamutu."""
