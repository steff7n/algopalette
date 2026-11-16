from types import SimpleNamespace

import httpx
import pytest

from algopalette.themes import net
from algopalette.themes.net import FetchError, fetch, make_client

OK_URL = "https://raw.githubusercontent.com/x/y/master/themes.json"


def _client(handler):
    return make_client(transport=httpx.MockTransport(handler))


def test_200_zwraca_bajty():
    c = _client(lambda r: httpx.Response(200, content=b"abc"))
    assert fetch(c, OK_URL) == b"abc"


def test_naglowek_user_agent():
    seen = {}

    def handler(r):
        seen["ua"] = r.headers["user-agent"]
        return httpx.Response(200, content=b"")

    fetch(_client(handler), OK_URL)
    assert seen["ua"].startswith("algopalette/")


def test_404_to_http():
    c = _client(lambda r: httpx.Response(404))
    with pytest.raises(FetchError) as e:
        fetch(c, OK_URL)
    assert e.value.kind == "http"
    assert "404" in str(e.value)
    assert "raw.githubusercontent.com" in str(e.value)


def test_connect_error_to_offline():
    def handler(r):
        raise httpx.ConnectError("boom")

    with pytest.raises(FetchError) as e:
        fetch(_client(handler), OK_URL)
    assert e.value.kind == "offline"
    assert str(e.value) == "Brak połączenia z raw.githubusercontent.com."


def test_timeout_to_offline():
    def handler(r):
        raise httpx.ReadTimeout("slow")

    with pytest.raises(FetchError) as e:
        fetch(_client(handler), OK_URL)
    assert e.value.kind == "offline"


def test_host_spoza_listy():
    called = []
    c = _client(lambda r: called.append(r) or httpx.Response(200))
    with pytest.raises(FetchError) as e:
        fetch(c, "https://evil.example/x")
    assert e.value.kind == "host"
    assert "evil.example" in str(e.value)
    assert not called


def test_http_bez_tls_odrzucony():
    c = _client(lambda r: httpx.Response(200))
    with pytest.raises(FetchError) as e:
        fetch(c, "http://lospec.com/x")
    assert e.value.kind == "host"


def test_przekierowanie_na_niedozwolony_host():
    def handler(r):
        if r.url.host == "lospec.com":
            return httpx.Response(302, headers={"location": "https://evil.example/x"})
        raise AssertionError("żądanie dotarło do transportu")

    with pytest.raises(FetchError) as e:
        fetch(_client(handler), "https://lospec.com/palette-list")
    assert e.value.kind == "host"


def test_przekierowanie_na_dozwolony_host():
    def handler(r):
        if r.url.host == "lospec.com":
            return httpx.Response(302, headers={"location": "https://codeload.github.com/a"})
        return httpx.Response(200, content=b"ok")

    assert fetch(_client(handler), "https://lospec.com/x") == b"ok"


def test_limit_rozmiaru_w_trakcie(monkeypatch):
    monkeypatch.setattr(net, "MAX_BYTES", 100)
    c = _client(lambda r: httpx.Response(200, content=b"x" * 500))
    with pytest.raises(FetchError) as e:
        fetch(c, OK_URL)
    assert e.value.kind == "size"


def test_limit_rozmiaru_z_naglowka(monkeypatch):
    monkeypatch.setattr(net, "MAX_BYTES", 100)
    c = _client(lambda r: httpx.Response(200, headers={"content-length": "5000"}, content=b"x"))
    with pytest.raises(FetchError) as e:
        fetch(c, OK_URL)
    assert e.value.kind == "size"


def test_anulowanie():
    c = _client(lambda r: httpx.Response(200, content=b"abc"))
    with pytest.raises(FetchError) as e:
        fetch(c, OK_URL, cancelled=lambda: True)
    assert e.value.kind == "cancelled"
    assert str(e.value) == "Anulowano."


def test_postep_przy_sukcesie():
    calls = []
    c = _client(lambda r: httpx.Response(200, content=b"x" * 10))
    fetch(c, OK_URL, on_progress=lambda got, total: calls.append((got, total)))
    assert calls
    assert calls[-1] == (10, 10)


def test_zbyt_wiele_przekierowań_to_http():
    def handler(r):
        return httpx.Response(302, headers={"location": OK_URL})

    with pytest.raises(FetchError) as e:
        fetch(_client(handler), OK_URL)
    assert e.value.kind == "http"
    assert str(e.value) == "Serwer raw.githubusercontent.com przekierowuje w kółko."


def test_uszkodzona_kompresja_to_http():
    c = _client(
        lambda r: httpx.Response(200, headers={"content-encoding": "gzip"}, content=b"nie-gzip")
    )
    with pytest.raises(FetchError) as e:
        fetch(c, OK_URL)
    assert e.value.kind == "http"
    assert str(e.value) == "Uszkodzona odpowiedź z raw.githubusercontent.com."


def test_inny_request_error_to_offline():
    def handler(r):
        raise httpx.RequestError("coś innego")

    with pytest.raises(FetchError) as e:
        fetch(_client(handler), OK_URL)
    assert e.value.kind == "offline"
    assert str(e.value) == "Brak połączenia z raw.githubusercontent.com."


def test_łączny_limit_czasu(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(net, "time", SimpleNamespace(monotonic=lambda: now[0]))
    monkeypatch.setattr(net, "TOTAL_TIMEOUT_S", 60.0)

    def body():
        for _ in range(5):
            now[0] += 25.0  # każda porcja „przychodzi” 25 s później
            yield b"x"

    c = _client(lambda r: httpx.Response(200, content=body()))
    with pytest.raises(FetchError) as e:
        fetch(c, OK_URL)
    assert e.value.kind == "offline"
    assert str(e.value) == "Pobieranie z raw.githubusercontent.com trwa zbyt długo."


def test_porcje_bez_stałego_rozmiaru_postęp_i_anulowanie_per_porcja():
    def body():
        yield b"aa"
        yield b"bbb"
        yield b"c"

    seen = []
    c = _client(lambda r: httpx.Response(200, content=body()))
    assert fetch(c, OK_URL, on_progress=lambda got, total: seen.append(got)) == b"aabbbc"
    assert seen == [2, 5, 6]

    n = [0]

    def cancelled():
        n[0] += 1
        return n[0] > 1  # anuluj przy drugiej porcji

    c = _client(lambda r: httpx.Response(200, content=body()))
    with pytest.raises(FetchError) as e:
        fetch(c, OK_URL, cancelled=cancelled)
    assert e.value.kind == "cancelled"
    assert n[0] == 2
