"""Bezpieczne pobieranie z sieci: lista dozwolonych hostów, limity, postęp i anulowanie.

Treści z sieci to dane niezaufane — ten moduł tylko je pobiera (bajty); parsowanie robią adaptery.
Komunikaty ``FetchError`` są po polsku i nadają się wprost do pokazania w interfejsie.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from typing import Literal

import httpx

ALLOWED_HOSTS: frozenset[str] = frozenset(
    {"codeload.github.com", "raw.githubusercontent.com", "lospec.com"}
)
TIMEOUT_S = 20.0
MAX_BYTES = 20 * 1024 * 1024
_CHUNK = 64 * 1024

FetchErrorKind = Literal["offline", "http", "host", "size", "cancelled"]


class FetchError(Exception):
    """Nieudane pobranie; ``str(e)`` to komunikat PL, ``kind`` — kategoria błędu."""

    def __init__(self, kind: FetchErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind: FetchErrorKind = kind


def _user_agent() -> str:
    try:
        ver = version("algopalette")
    except PackageNotFoundError:
        ver = "dev"
    return f"algopalette/{ver}"


def _check_host(request: httpx.Request) -> None:
    """Hook żądania: wywoływany dla każdego żądania łańcucha przekierowań."""
    host = request.url.host
    if request.url.scheme != "https" or host not in ALLOWED_HOSTS:
        raise FetchError("host", f"Adres spoza dozwolonych źródeł: {host or request.url}.")


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(
        timeout=TIMEOUT_S,
        follow_redirects=True,
        headers={"User-Agent": _user_agent()},
        event_hooks={"request": [_check_host]},
        transport=transport,
    )


def _too_big(host: str) -> FetchError:
    mb = MAX_BYTES // (1024 * 1024)
    return FetchError("size", f"Odpowiedź z {host} jest za duża (limit {mb} MB).")


def fetch(
    client: httpx.Client,
    url: str,
    *,
    on_progress: Callable[[int, int | None], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> bytes:
    """Pobiera ``url`` strumieniowo; ``on_progress(odebrane, content_length | None)``."""
    host = httpx.URL(url).host or url
    try:
        with client.stream("GET", url) as resp:
            if resp.status_code >= 400:
                raise FetchError(
                    "http", f"Serwer {resp.url.host} odpowiedział błędem {resp.status_code}."
                )
            total: int | None = None
            raw_len = resp.headers.get("content-length")
            if raw_len is not None:
                try:
                    total = int(raw_len)
                except ValueError:
                    total = None
            if total is not None and total > MAX_BYTES:
                raise _too_big(resp.url.host)
            buf = bytearray()
            for chunk in resp.iter_bytes(_CHUNK):
                if cancelled is not None and cancelled():
                    raise FetchError("cancelled", "Anulowano.")
                buf += chunk
                if len(buf) > MAX_BYTES:
                    raise _too_big(resp.url.host)
                if on_progress is not None:
                    on_progress(len(buf), total)
            if cancelled is not None and cancelled():
                raise FetchError("cancelled", "Anulowano.")
            if on_progress is not None and not buf:
                on_progress(0, total)
            return bytes(buf)
    except FetchError:
        raise
    except (httpx.TimeoutException, httpx.TransportError) as e:
        raise FetchError("offline", f"Brak połączenia z {host}.") from e
