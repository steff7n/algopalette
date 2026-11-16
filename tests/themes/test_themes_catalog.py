import json

import httpx
import pytest

from algopalette.themes import cache, catalog, net

ANSI = {f"color_{i:02d}": f"#{i * 15:02x}{(255 - i * 15):02x}80" for i in range(1, 17)}
GOGH = json.dumps(
    [{"name": "Test", "author": "A", "background": "#101010", "foreground": "#eeeeee", **ANSI}]
).encode()
LOSPEC = json.dumps(
    {
        "palettes": [
            {
                "title": "Warm 4",
                "slug": "warm-4",
                "colors": ["000000", "ffffff", "ff0000", "00ff00"],
                "user": {"name": "U"},
            }
        ],
        "totalCount": 37,
    }
).encode()


class Server:
    def __init__(self, fail: Exception | None = None):
        self.requests: list[httpx.Request] = []
        self.fail = fail

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail is not None:
            raise self.fail
        body = LOSPEC if request.url.host == "lospec.com" else GOGH
        return httpx.Response(200, content=body)

    def client(self) -> httpx.Client:
        return net.make_client(transport=httpx.MockTransport(self))


def test_fresh_cache_skips_network_and_refresh_forces_it():
    srv = Server()
    c = srv.client()
    first = catalog.load_catalog("gogh", c, now=1000.0)
    assert len(srv.requests) == 1 and len(first.themes) == 1 and not first.offline
    catalog.load_catalog("gogh", c, now=2000.0)
    assert len(srv.requests) == 1
    catalog.load_catalog("gogh", c, now=2000.0, refresh=True)
    assert len(srv.requests) == 2


def test_stale_cache_used_offline():
    catalog.load_catalog("gogh", Server().client(), now=0.0)
    down = Server(fail=httpx.ConnectError("x"))
    res = catalog.load_catalog("gogh", down.client(), now=catalog.CATALOG_TTL_S + 10)
    assert res.offline and len(res.themes) == 1 and res.fetched_at == 0.0


def test_no_cache_and_no_network_raises():
    down = Server(fail=httpx.ConnectError("x"))
    with pytest.raises(net.FetchError) as e:
        catalog.load_catalog("gogh", down.client())
    assert e.value.kind == "offline"


def test_cache_write_failure_is_reported_not_raised(monkeypatch):
    def boom(*a, **k):
        raise OSError(13, "Brak dostępu")

    monkeypatch.setattr(cache, "save", boom)
    res = catalog.load_catalog("gogh", Server().client())
    assert len(res.themes) == 1 and res.cache_error and "Brak dostępu" in res.cache_error


def test_lospec_url_and_page():
    url = catalog.lospec_url("Warm pastel", 2)
    assert url.endswith("&page=2&tag=warm&sortingType=downloads")
    assert "colorNumberFilterType=max&colorNumber=16" in url
    srv = Server()
    res = catalog.lospec_page("", 0, srv.client())
    assert res.total == 37 and res.themes[0].id == "warm-4"
    assert "tag=&" in str(srv.requests[0].url)


def test_refresh_all_clears_only_lospec():
    srv = Server()
    c = srv.client()
    catalog.load_catalog("gogh", c, now=1.0)
    catalog.lospec_page("warm", 0, c, now=1.0)
    catalog.refresh_all()
    assert cache.load("gogh") is not None
    assert cache.load("lospec-warm-0") is None
