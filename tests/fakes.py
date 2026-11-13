"""가짜 전송 — URL 규칙으로 녹화 응답을 돌려준다. 네트워크 없이 수집기를 검사한다 (SPEC N2)."""

import json
from collections.abc import Callable, Mapping
from typing import Any

from radar.clients.transport import HttpResponse

Route = Callable[[str], HttpResponse | Exception | None]


def ok(body: Any, headers: Mapping[str, str] | None = None) -> HttpResponse:
    raw = body.encode() if isinstance(body, str) else json.dumps(body).encode()
    return HttpResponse(200, dict(headers or {}), raw)


def status(code: int, headers: Mapping[str, str] | None = None, body: str = "") -> HttpResponse:
    return HttpResponse(code, dict(headers or {}), body.encode())


class FakeTransport:
    """routes: [(URL 에 들어 있는 조각, 응답 또는 응답 목록)].

    앞에서부터 처음 맞는 규칙을 쓴다. 목록이면 차례로 꺼낸다.
    """

    def __init__(self, routes: list[tuple[str, Any]], default: HttpResponse | None = None):
        self.routes = [(frag, list(r) if isinstance(r, list) else r) for frag, r in routes]
        self.default = default or status(404)
        self.requests: list[tuple[str, str, dict[str, str]]] = []
        self.bodies: list[bytes | None] = []

    def __call__(self, method: str, url: str, headers: Mapping[str, str], timeout: float,
                 body: bytes | None = None) -> HttpResponse:
        self.requests.append((method, url, dict(headers)))
        self.bodies.append(body)
        for frag, r in self.routes:
            if frag in url:
                item = (r.pop(0) if len(r) > 1 else r[0]) if isinstance(r, list) else r
                if callable(item) and not isinstance(item, HttpResponse):
                    item = item(url)
                if isinstance(item, Exception):
                    raise item
                assert isinstance(item, HttpResponse)
                return item
        return self.default

    def urls(self, frag: str = "") -> list[str]:
        return [u for _, u, _ in self.requests if frag in u]
