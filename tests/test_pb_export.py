"""Eksport do PaletteBuildera (Task 7). Akceptację przez PB sprawdzono na jego logice (HANDOFF)."""

import json
from pathlib import Path

import pytest

from algopalette.pb_export import pb_json, write_pb_file

FIXTURE = Path(__file__).parent / "fixtures" / "pb_export_expected.json"


def test_golden_shape():
    got = pb_json(["#1E1E2E", "#E0E0E0", "#ff8080", "#80c0ff"], "dark")
    assert got == FIXTURE.read_text(encoding="utf-8").rstrip("\n")


def test_roles_and_order():
    data = json.loads(pb_json([f"#{i:02x}0000" for i in range(16)], "light"))
    assert data["format"] == "palettebuilder.v3"
    assert data["polarity"] == "light"
    assert [p["role"] for p in data["palette"][:3]] == ["bg", "fg", None]
    assert [p["hex"] for p in data["palette"]] == [f"#{i:02x}0000" for i in range(16)]


def test_too_short():
    with pytest.raises(ValueError):
        pb_json(["#000000"], "dark")


def test_write_no_overwrite(tmp_path):
    p = tmp_path / "sub" / "motyw.json"
    write_pb_file("A", p)
    assert p.read_text() == "A"
    with pytest.raises(FileExistsError):
        write_pb_file("B", p)
    assert p.read_text() == "A"
    write_pb_file("C", p, overwrite=True)
    assert p.read_text() == "C"
    assert [x.name for x in p.parent.iterdir()] == ["motyw.json"]
