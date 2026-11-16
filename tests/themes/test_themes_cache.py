import json

import pytest

from algopalette.themes import cache
from algopalette.themes.cache import Cached
from algopalette.themes.model import Theme

DAY = 86400.0


def _theme(i: str = "a", source="base16") -> Theme:
    return Theme(
        source=source,
        id=i,
        name=f"Motyw {i}",
        author="Ł",
        url=None,
        colors=("#000000", "#ffffff", "#ff0000"),
        accent_names=("red",),
        has_roles=True,
        license="MIT",
    )


def test_round_trip():
    ts = [_theme("a"), _theme("b")]
    cache.save("base16", ts, total=42, now=1000.0)
    c = cache.load("base16")
    assert c == Cached(tuple(ts), 1000.0, 42)


def test_brak_pliku():
    assert cache.load("nie-ma") is None


@pytest.mark.parametrize(
    "raw",
    [
        b"{",
        b"[]",
        b'{"version": 2, "fetched_at": 1, "themes": []}',
        b'{"version": 1, "themes": []}',
        b'{"version": 1, "fetched_at": "x", "themes": []}',
        b'{"version": 1, "fetched_at": 1, "themes": [{"source": "x"}]}',
        b'{"version": 1, "fetched_at": 1, "themes": "no"}',
        b"\xff\xfe",
    ],
)
def test_uszkodzony_plik_to_none(raw):
    d = cache.cache_dir()
    d.mkdir(parents=True)
    (d / "k.json").write_bytes(raw)
    assert cache.load("k") is None


def test_is_fresh_ttl_7_dni():
    c = Cached((), 0.0)
    assert cache.is_fresh(c, 7 * DAY, 6 * DAY)
    assert not cache.is_fresh(c, 7 * DAY, 8 * DAY)


def test_clear_prefiks():
    for k in ("lospec-popular-1", "lospec-new-2", "base16", "gogh"):
        cache.save(k, [_theme()])
    cache.clear("lospec")
    names = sorted(p.stem for p in cache.cache_dir().glob("*.json"))
    assert names == ["base16", "gogh"]
    cache.clear()
    assert not list(cache.cache_dir().glob("*.json"))


def test_clear_bez_katalogu_nie_rzuca():
    cache.clear("lospec")


def test_klucz_jest_sanityzowany():
    cache.save("Lospec/../x y", [_theme()])
    files = [p.name for p in cache.cache_dir().iterdir()]
    assert files == ["lospec----x-y.json"]
    assert cache.load("Lospec/../x y") is not None


def test_zapis_atomowy_bez_resztek(monkeypatch):
    cache.save("k", [_theme()])
    before = (cache.cache_dir() / "k.json").read_text(encoding="utf-8")

    def boom(*a, **k):
        raise OSError("dysk pełny")

    monkeypatch.setattr(cache.os, "replace", boom)
    with pytest.raises(OSError):
        cache.save("k", [_theme("zz")])
    assert (cache.cache_dir() / "k.json").read_text(encoding="utf-8") == before
    assert [p.name for p in cache.cache_dir().iterdir()] == ["k.json"]
    assert json.loads(before)["version"] == 1


def test_cache_dir_z_xdg(tmp_path):
    assert cache.cache_dir() == tmp_path / "cache" / "algopalette" / "themes"
