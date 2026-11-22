"""Tiny HTTP layer: httpx when installed, requests otherwise. One place to set timeouts and the user agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:  # pragma: no cover - depends on environment
    import httpx as _httpx
except Exception:  # noqa: BLE001
    _httpx = None
try:  # pragma: no cover
    import requests as _requests
except Exception:  # noqa: BLE001
    _requests = None


@dataclass
class HttpResponse:
    status: int
    headers: dict[str, str]
    content: bytes
    url: str

    @property
    def text(self) -> str:
        ctype = self.headers.get("content-type", "")
        enc = "utf-8"
        if "charset=" in ctype:
            enc = ctype.split("charset=")[-1].split(";")[0].strip() or "utf-8"
        try:
            return self.content.decode(enc, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        import json

        return json.loads(self.content.decode("utf-8", errors="replace"))


class HttpError(Exception):
    def __init__(self, code: str, status: int | None = None):
        super().__init__(code)
        self.code = code
        self.status = status


def request(method: str, url: str, *, headers: dict[str, str] | None = None, json: Any = None,
            params: dict[str, Any] | None = None, data: Any = None, timeout: float = 30,
            max_bytes: int | None = None, follow_redirects: bool = True) -> HttpResponse:
    headers = dict(headers or {})
    if _httpx is not None:
        try:
            with _httpx.Client(timeout=timeout, follow_redirects=follow_redirects) as c:
                with c.stream(method, url, headers=headers, json=json, params=params, data=data) as r:
                    buf = bytearray()
                    for part in r.iter_bytes():
                        buf.extend(part)
                        if max_bytes and len(buf) > max_bytes:
                            raise HttpError("TOO_LARGE", r.status_code)
                    return HttpResponse(r.status_code, {k.lower(): v for k, v in r.headers.items()}, bytes(buf),
                                        str(r.url))
        except HttpError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HttpError(f"NETWORK:{type(exc).__name__}") from exc
    if _requests is not None:
        try:
            r = _requests.request(method, url, headers=headers, json=json, params=params, data=data,
                                  timeout=timeout, stream=True, allow_redirects=follow_redirects)
            buf = bytearray()
            for part in r.iter_content(64 * 1024):
                buf.extend(part)
                if max_bytes and len(buf) > max_bytes:
                    raise HttpError("TOO_LARGE", r.status_code)
            return HttpResponse(r.status_code, {k.lower(): v for k, v in r.headers.items()}, bytes(buf), r.url)
        except HttpError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HttpError(f"NETWORK:{type(exc).__name__}") from exc
    raise HttpError("NO_HTTP_CLIENT")


def get(url: str, **kw: Any) -> HttpResponse:
    return request("GET", url, **kw)


def post(url: str, **kw: Any) -> HttpResponse:
    return request("POST", url, **kw)
