"""Snapshot celów układu odcieni (``engine.hue_targets``) — punkt odniesienia zgodności.

Uruchomione 2026-11-19 na kodzie sprzed zmiany „układ odcieni = lista” (``main`` @ ``3b6ae15``);
``tests/test_hue_list_compat.py`` sprawdza, że po zmianie cele są identyczne. Klucze:
``preset:<nazwa>:<polaryzacja>:<liczba kolorów>``, ``file:<plik>``, ``default``.

    uv run python tools/snapshot_hue_targets.py > tests/fixtures/hue_targets_snapshot.json
"""

import json
import sys
from pathlib import Path

from algopalette import engine
from algopalette import io as aio
from algopalette.model import Session, default_session, remove_slot
from algopalette.presets import apply_preset
from algopalette.presets_builtin import BUILTIN

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "v2_contract"
SIZES = (7, 10)


def sized(n_colors: int) -> Session:
    """``default_session()`` przycięta do ``n_colors`` kolorów (usuwa akcenty od końca)."""
    s = default_session()
    while len(s.slots) > n_colors:
        s = remove_slot(s, s.slots[-1].id)
    return s


def targets(s: Session) -> list[float]:
    t = engine.hue_targets(s)
    return [t[sl.id] for sl in s.slots[2:] if sl.id in t]


def main() -> None:
    out: dict[str, list[float]] = {"default": targets(default_session())}
    for p in BUILTIN:
        for pol in p.polarities:
            for n in SIZES:
                s = apply_preset(sized(n), p.name, polarity=pol)
                out[f"preset:{p.name}:{pol}:{n}"] = targets(s)
    for path in sorted(FIXTURES.glob("manual_*.json")):
        out[f"file:{path.name}"] = targets(aio.load_session(path))
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
