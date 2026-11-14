"""Model danych AlgoPalette (kontrakt z Shared Interfaces; rozszerzany w Task 2)."""

from dataclasses import dataclass
from typing import Literal

Role = Literal["bg", "fg", "accent"]
ContrastMetric = Literal["wcag21", "apca"]
DeltaEMethod = Literal["ok", "2000", "hyab", "itp", "cam16"]
CvdType = Literal["protan", "deutan", "tritan"]
CvdMethod = Literal["brettel", "vienot", "machado"]
FitMethod = Literal["clip", "minde-chroma", "lch-chroma", "oklch-chroma", "raytrace", "scale"]
ChromaMode = Literal["abs", "rel"]  # rel = ułamek max C w sRGB przy (L, H), 0–1


@dataclass(frozen=True)
class OKLCH:
    """Kolor w OKLCH: l 0–1, c ≥ 0, h w stopniach [0, 360)."""

    l: float
    c: float
    h: float
