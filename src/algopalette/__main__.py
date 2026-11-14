"""Punkt wejścia: ``algopalette [PLIK_SESJI] [--fresh]``."""

import argparse
from pathlib import Path

from algopalette import io as aio
from algopalette.model import Session, default_session
from algopalette.moods import apply_mood


def fresh_session() -> Session:
    return apply_mood(default_session(), "neutralny")


def startup_session(file: Path | None, fresh: bool) -> tuple[Session, str | None, Path | None]:
    """Sesja startowa + ewentualny komunikat dla użytkownika + ścieżka otwartego pliku."""
    if file is not None:
        try:
            return aio.load_session(file), None, file
        except FileNotFoundError:
            return fresh_session(), f"Nie ma pliku {file} — start od nowej palety.", None
        except (aio.SessionFormatError, OSError) as e:
            return fresh_session(), f"Nie można wczytać {file}: {e}", None
    if not fresh:
        path = aio.autosave_path()
        if path.exists():
            try:
                return aio.load_session(path), None, None
            except (aio.SessionFormatError, OSError) as e:
                return fresh_session(), f"Autozapis uszkodzony ({e}) — start od nowej palety.", None
    return fresh_session(), None, None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="algopalette", description="Generator palet kolorów pod motywy IDE (OKLCH, TUI)."
    )
    parser.add_argument("plik", nargs="?", type=Path, help="plik sesji AlgoPalette (.json)")
    parser.add_argument("--fresh", action="store_true", help="ignoruj autozapis, zacznij od nowa")
    args = parser.parse_args(argv)
    session, notice, path = startup_session(args.plik, args.fresh)

    from algopalette.tui.app import AlgoPaletteApp

    AlgoPaletteApp(session, notice=notice, file_path=path).run()


if __name__ == "__main__":
    main()
