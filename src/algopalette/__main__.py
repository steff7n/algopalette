"""Punkt wejścia: ``algopalette [PLIK_SESJI] [--fresh]``."""

import argparse
import contextlib
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from algopalette import io as aio
from algopalette.model import Session, default_session
from algopalette.presets import migrate_user_moods


def fresh_session() -> Session:
    return default_session()  # ma już zasady presetu „neutralny”


KEEP_PREV = 10  # ile kopii „prev” autozapisu zostaje (najstarsze nadmiarowe znikają)


def _keep_autosave(suffix: str) -> str | None:
    """Przenosi istniejący autozapis obok (żeby pierwsza zmiana go nie nadpisała; przegląd I7).

    Nazwa ma znacznik czasu, więc kolejne starty z pliku nie nadpisują wcześniejszej kopii
    (przegląd 2026-11-18 M14); kopii „prev” zostaje najwyżej ``KEEP_PREV``."""
    path = aio.autosave_path()
    if not path.exists():
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.stem}.{suffix}-{stamp}.json")
    n = 1
    while target.exists():
        n += 1
        target = path.with_name(f"{path.stem}.{suffix}-{stamp}-{n}.json")
    try:
        path.replace(target)
    except OSError:
        return None
    if suffix == "prev":
        old = sorted(path.parent.glob(f"{path.stem}.prev-*.json"))  # nazwa = czas
        for p in old[:-KEEP_PREV]:
            with contextlib.suppress(OSError):
                p.unlink()
    return str(target)


@dataclass(frozen=True)
class Startup:
    session: Session
    notice: str | None = None  # komunikat na pasku stanu
    path: Path | None = None  # plik otwarty z wiersza poleceń
    migration_notes: tuple[str, ...] = ()  # co przepadło albo się zmieniło przy migracji z v1


def _migrated_autosave(path: Path, session: Session) -> str:
    """Autozapis był w formacie v1: zostawia obok kopię ``last.v1.json`` i zapisuje autozapis
    w nowym formacie, żeby następny start nie migrował drugi raz. Zwraca komunikat.

    Istniejącej kopii nie nadpisuje (to ten sam stary plik z wcześniejszego startu). Gdy kopii
    nie da się zrobić, autozapis zostaje nietknięty — stary plik jest wtedy jedynym egzemplarzem.
    """
    backup = path.with_name(f"{path.stem}.v1.json")
    if not backup.exists():
        try:
            shutil.copy2(path, backup)
        except OSError as e:
            return (
                "Autozapis był w starszym formacie — zasady przeniesiono do nowego. Kopii starego "
                f"pliku nie udało się zrobić ({e.strerror or e}), więc autozapis zostaje bez zmian."
            )
    with contextlib.suppress(OSError):
        aio.save_session(session, path, overwrite=True)
    return (
        "Autozapis był w starszym formacie — zasady przeniesiono do nowego. "
        f"Kopię starego pliku zachowano jako {backup}."
    )


def startup_session(file: Path | None, fresh: bool) -> Startup:
    """Sesja startowa, komunikat dla użytkownika, ścieżka otwartego pliku i komunikaty migracji.

    Gdy sesja NIE pochodzi z autozapisu, a autozapis istnieje, jest on przenoszony do
    ``last.prev-<czas>.json`` (ostatnie ``KEEP_PREV``; uszkodzony: ``last.corrupt-<czas>.json``)
    — nic nie ginie. Autozapis
    w formacie v1 jest migrowany, a stary plik zostaje obok jako ``last.v1.json``.
    """
    notes: list[str] = []
    session: Session | None = None
    opened: Path | None = None
    migration: tuple[str, ...] = ()
    if file is not None:
        try:
            session, migration = aio.load_session_ex(file)
            opened = file
        except FileNotFoundError:
            notes.append(f"Nie ma pliku {file} — start od nowej palety.")
        except (aio.SessionFormatError, OSError) as e:
            notes.append(f"Nie można wczytać {file}: {e}")
    elif not fresh:
        path = aio.autosave_path()
        if path.exists():
            try:
                session, migration = aio.load_session_ex(path)
            except (aio.SessionFormatError, OSError) as e:
                kept = _keep_autosave("corrupt")
                notes.append(f"Autozapis uszkodzony ({e}) — start od nowej palety.")
                if kept:
                    notes.append(f"Uszkodzony plik zachowano jako {kept}.")
            else:
                notice = _migrated_autosave(path, session) if aio.is_v1_file(path) else None
                return Startup(session, notice, None, migration)
    if session is None:
        session = fresh_session()
    kept = _keep_autosave("prev")
    if kept:
        notes.append(f"Poprzedni autozapis zachowano jako {kept}.")
    return Startup(session, " ".join(notes) or None, opened, migration)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="algopalette", description="Generator palet kolorów pod motywy IDE (OKLCH)."
    )
    parser.add_argument("plik", nargs="?", type=Path, help="plik sesji AlgoPalette (.json)")
    parser.add_argument("--fresh", action="store_true", help="ignoruj autozapis, zacznij od nowa")
    args = parser.parse_args(argv)
    # Jednorazowo: dawne nastroje użytkownika → presety. Uszkodzony plik presetów zgłosi
    # zakładka „Zasady” przy pierwszym użyciu.
    with contextlib.suppress(ValueError, OSError):
        migrate_user_moods()
    st = startup_session(args.plik, args.fresh)

    from algopalette.gui.app import run

    sys.exit(
        run(st.session, notice=st.notice, file_path=st.path, migration_notes=st.migration_notes)
    )


if __name__ == "__main__":
    main()
