import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))


@pytest.fixture
def win(qtbot):
    from algopalette.__main__ import fresh_session
    from algopalette.gui.app import MainWindow

    w = MainWindow(fresh_session(), autosave=False)
    qtbot.addWidget(w)
    w.show()
    return w


class FakeGeneration:
    """Zadanie silnika sterowane ręcznie przez test (zamiast prawdziwego ``engine.Generation``)."""

    def __init__(self, session, free) -> None:
        self.session, self.free = session, tuple(free)
        self.state, self.fraction, self.error = "running", 0.0, None
        self.cancelled = False
        self.proposals: list = []

    def poll(self):
        from algopalette.engine import Progress

        return Progress(self.state, self.fraction, len(self.proposals), self.error)

    def cancel(self) -> None:
        self.cancelled = True
        if self.state == "running":
            self.state = "cancelled"

    def result(self) -> list:
        return list(self.proposals)

    def finish(self, n: int = 3, *, hard: bool = False) -> None:
        """Kończy zadanie z ``n`` propozycjami (kolory wolne przesunięte, stałe bez zmian)."""
        from algopalette import color
        from algopalette.engine import Proposal, Violation
        from algopalette.model import OKLCH

        s = self.session
        fit = s.globals.fit_method
        for k in range(n):
            values = {
                sl.id: OKLCH(0.6 + 0.02 * k, 0.1, (sl.value.h + 30.0 * (k + 1)) % 360.0)
                if sl.id in self.free
                else sl.value
                for sl in s.slots
            }
            bad = Violation(
                "k", self.free[:1], "lightness", True, 0.1, 0.5, {"lo": 0.6, "hi": None}, {}
            )
            self.proposals.append(
                Proposal(
                    values=values,
                    hexes={i: color.to_hex(v, fit) for i, v in values.items()},
                    fit_deltas=dict.fromkeys(values, 0.0),
                    score=float(k),
                    violations=(bad,) if hard and k == 0 else (),
                    timed_out=False,
                    seed=s.globals.optimizer.seed,
                    slot_ids=self.free,
                )
            )
        self.state, self.fraction = "done", 1.0


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list = []
        self.gen: FakeGeneration | None = None
        self.fail_start: str | None = None

    def start(self, session, slot_ids=None):
        if self.fail_start is not None:
            raise ValueError(self.fail_start)
        free = [
            s.id for s in session.slots if not s.locked and (slot_ids is None or s.id in slot_ids)
        ]
        self.calls.append(None if slot_ids is None else set(slot_ids))
        self.gen = FakeGeneration(session, free)
        return self.gen


@pytest.fixture
def fake_engine(monkeypatch):
    """``engine.start`` zwraca zadanie sterowane przez test — testy okna nie zależą od silnika."""
    from algopalette import engine

    fake = FakeEngine()
    monkeypatch.setattr(engine, "start", fake.start)
    return fake
