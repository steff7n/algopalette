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
