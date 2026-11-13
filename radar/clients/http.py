"""HTTP 클라이언트 — 재시도·한도 대기·요청 간격·호출 집계 (TASKS T1-1, PLAN §3).

- 429·5xx·연결 실패는 지수 대기로 다시 보낸다. 404 는 답이다(다시 보내지 않는다).
- GitHub 한도(403/429 + x-ratelimit-remaining=0)는 reset 시각까지, retry-after 가 있으면 그만큼 기다린다.
- 종류(kind)별 최소 간격을 둔다 — Search 분당 30회, GeekNews 2초 (D12).
- 헤더(토큰)는 어디에도 남기지 않는다. 집계는 종류별 호출 수뿐이다.
"""

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from radar.clients.transport import HttpResponse, Transport, TransportError

USER_AGENT = "radar/0.0.1"
MAX_WAIT = 900.0  # 한도 대기 상한(초). 넘으면 그 요청은 실패로 돌려준다


@dataclass(frozen=True)
class Policy:
    attempts: int = 4
    backoff: float = 2.0  # 첫 재시도 대기(초), 매번 두 배
    min_interval: float = 0.0  # 같은 종류 요청 사이 최소 간격(초)
    timeout: float = 60.0


class HttpClient:
    def __init__(self, transport: Transport, *, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.time, policies: Mapping[str, Policy] | None = None):
        self._t = transport
        self._sleep = sleep
        self._clock = clock
        self._policies = dict(policies or {})
        self._last: dict[str, float] = {}
        self.calls: dict[str, int] = {}

    def _policy(self, kind: str) -> Policy:
        return self._policies.get(kind, Policy())

    def _space(self, kind: str, p: Policy) -> None:
        last = self._last.get(kind)
        if last is not None and p.min_interval > 0:
            gap = p.min_interval - (self._clock() - last)
            if gap > 0:
                self._sleep(round(gap, 3))

    def _rate_wait(self, r: HttpResponse) -> float | None:
        """한도 응답이면 기다릴 초, 아니면 None."""
        if r.status not in (403, 429):
            return None
        if "retry-after" in r.headers:
            try:
                return float(r.headers["retry-after"])
            except ValueError:
                return None
        if r.headers.get("x-ratelimit-remaining") == "0":
            try:
                return max(1.0, float(r.headers["x-ratelimit-reset"]) - self._clock() + 1)
            except (KeyError, ValueError):
                return None
        return None

    def get(self, kind: str, url: str, headers: Mapping[str, str] | None = None) -> HttpResponse:
        return self.request(kind, "GET", url, headers)

    def request(self, kind: str, method: str, url: str, headers: Mapping[str, str] | None = None,
                body: bytes | None = None) -> HttpResponse:
        """한 번 보낸다. GET 은 429·5xx·연결 실패를 재시도하고, 그 밖의 방법은 중복 생성을 막으려고
        429·한도 대기만 재시도한다(요청이 처리되지 않은 것이 확실한 경우)."""
        p = self._policy(kind)
        safe = method == "GET"
        h = {"User-Agent": USER_AGENT, **(headers or {})}
        wait = p.backoff
        for attempt in range(1, p.attempts + 1):
            self._space(kind, p)
            self.calls[kind] = self.calls.get(kind, 0) + 1
            try:
                r = self._t(method, url, h, p.timeout, body)
            except TransportError:
                self._last[kind] = self._clock()
                if attempt == p.attempts or not safe:
                    raise
                self._sleep(wait)
                wait *= 2
                continue
            self._last[kind] = self._clock()
            limit = self._rate_wait(r)
            if limit is not None and limit <= MAX_WAIT and attempt < p.attempts:
                self._sleep(limit)
                continue
            if (r.status == 429 or (safe and r.status >= 500)) and attempt < p.attempts:
                self._sleep(wait)
                wait *= 2
                continue
            return r
        raise AssertionError("도달하지 않는다")

    def get_json(self, kind: str, url: str, headers: Mapping[str, str] | None = None) -> tuple[int, Any]:
        """(상태, 본문). 200 이 아니거나 JSON 이 아니면 본문은 None."""
        r = self.get(kind, url, {"Accept": "application/json", **(headers or {})})
        if r.status != 200:
            return r.status, None
        try:
            return 200, json.loads(r.body)
        except ValueError:
            return 200, None

    def send_json(self, kind: str, method: str, url: str, payload: Any,
                  headers: Mapping[str, str] | None = None) -> tuple[int, Any]:
        """JSON 본문을 보내고 (상태, JSON 본문 또는 None) 을 돌려준다."""
        h = {"Accept": "application/json", "Content-Type": "application/json", **(headers or {})}
        r = self.request(kind, method, url, h, json.dumps(payload, ensure_ascii=False).encode())
        try:
            return r.status, json.loads(r.body) if r.body else None
        except ValueError:
            return r.status, None

    def get_text(self, kind: str, url: str, headers: Mapping[str, str] | None = None) -> tuple[int, str]:
        r = self.get(kind, url, headers)
        return r.status, r.body.decode("utf-8", errors="replace")
