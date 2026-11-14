"""Przeniesienie palety do PaletteBuildera — jednokierunkowo (spec §9).

Wynik to JSON, który okno „Wczytaj…” PaletteBuildera przyjmuje wklejony (``PB.import.motif``):
``palettebuilder.v3`` z polaryzacją i paletą ``[{hex, role}]`` w kolejności slotów (tło, tekst,
akcenty). AlgoPalette niczego z PaletteBuildera nie czyta.
"""

import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

PB_FORMAT = "palettebuilder.v3"


def pb_json(hexes: Sequence[str], polarity: Literal["dark", "light"]) -> str:
    """JSON dla PaletteBuildera; ``hexes`` w kolejności slotów (0 = tło, 1 = tekst)."""
    if len(hexes) < 2:
        raise ValueError("Paleta dla PaletteBuildera potrzebuje co najmniej tła i tekstu.")
    roles = ["bg", "fg"]
    palette = [{"hex": h.lower(), "role": roles[i] if i < 2 else None} for i, h in enumerate(hexes)]
    data = {"format": PB_FORMAT, "polarity": polarity, "palette": palette}
    return json.dumps(data, ensure_ascii=False, indent=1)


def default_pb_dir() -> Path:
    return Path.home() / "Dokumenty" / "motifs"


def write_pb_file(text: str, path: str | os.PathLike[str], overwrite: bool = False) -> None:
    """Zapis atomowy; istniejący plik bez ``overwrite`` → ``FileExistsError`` (plik nietknięty)."""
    p = Path(path)
    if p.exists() and not overwrite:
        raise FileExistsError(f"Plik {p} już istnieje.")
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{p.name}.", suffix=".tmp", dir=p.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, 0o644)
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
