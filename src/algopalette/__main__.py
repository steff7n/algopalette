"""Punkt wejścia: ``algopalette [PLIK_SESJI] [--fresh]``."""

import argparse
import sys
import time
from pathlib import Path

from algopalette import io as aio
from algopalette.model import Session, default_session
from algopalette.moods import apply_mood


def fresh_session() -> Session:
    return apply_mood(default_session(), "neutralny")


def _keep_autosave(suffix: str) -> str | None:
    """Przenosi istniejący autozapis obok (żeby pierwsza zmiana go nie nadpisała; przegląd I7)."""
    path = aio.autosave_path()
    if not path.exists():
        return None
    target = path.with_name(f"{path.stem}.{suffix}.json")
    try:
        path.replace(target)
    except OSError:
        return None
    return str(target)


def startup_session(file: Path | None, fresh: bool) -> tuple[Session, str | None, Path | None]:
    """Sesja startowa + ewentualny komunikat dla użytkownika + ścieżka otwartego pliku.

    Gdy sesja NIE pochodzi z autozapisu, a autozapis istnieje, jest on przenoszony do
    ``last.prev.json`` (uszkodzony: ``last.corrupt-<czas>.json``) — nic nie ginie.
    """
    notes: list[str] = []
    session: Session | None = None
    opened: Path | None = None
    if file is not None:
        try:
            session, opened = aio.load_session(file), file
        except FileNotFoundError:
            notes.append(f"Nie ma pliku {file} — start od nowej palety.")
        except (aio.SessionFormatError, OSError) as e:
            notes.append(f"Nie można wczytać {file}: {e}")
    elif not fresh:
        path = aio.autosave_path()
        if path.exists():
            try:
                return aio.load_session(path), None, None
            except (aio.SessionFormatError, OSError) as e:
                kept = _keep_autosave(f"corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
                notes.append(f"Autozapis uszkodzony ({e}) — start od nowej palety.")
                if kept:
                    notes.append(f"Uszkodzony plik zachowano jako {kept}.")
    if session is None:
        session = fresh_session()
    kept = _keep_autosave("prev")
    if kept:
        notes.append(f"Poprzedni autozapis zachowano jako {kept}.")
    return session, " ".join(notes) or None, opened


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="algopalette", description="Generator palet kolorów pod motywy IDE (OKLCH)."
    )
    parser.add_argument("plik", nargs="?", type=Path, help="plik sesji AlgoPalette (.json)")
    parser.add_argument("--fresh", action="store_true", help="ignoruj autozapis, zacznij od nowa")
    args = parser.parse_args(argv)
    session, notice, path = startup_session(args.plik, args.fresh)

    from algopalette.gui.app import run

    sys.exit(run(session, notice=notice, file_path=path))


if __name__ == "__main__":
    main()
