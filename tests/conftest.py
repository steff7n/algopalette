"""Wspólne dla całego zestawu: zero prawdziwej sieci i zero zapisu do prawdziwego ``~/.cache``."""

import httpx
import pytest


def _blocked(self, request):
    raise RuntimeError(f"sieć zablokowana w testach: {request.url}")


@pytest.fixture(autouse=True)
def _no_network_no_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _blocked)
