"""HTTP 전송. 표준 라이브러리 urllib 만 쓴다 (PLAN P4). 네트워크는 이 파일에서만 (PLAN §2).

HTTP 오류 상태도 예외가 아니라 응답으로 돌려준다. 재시도 판단은 호출하는 쪽이 한다(M1 T1-1).
"""

import http.client
import urllib.error
import urllib.request
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]  # 키는 소문자
    body: bytes


class TransportError(Exception):
    """연결 자체가 실패했다 (DNS·타임아웃·끊긴 연결 등)."""


class Transport(Protocol):
    def __call__(self, method: str, url: str, headers: Mapping[str, str], timeout: float) -> HttpResponse: ...


def _lower(items: Iterable[tuple[str, str]]) -> dict[str, str]:
    return {k.lower(): v for k, v in items}


class UrllibTransport:
    def __call__(self, method: str, url: str, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        req = urllib.request.Request(url, method=method, headers=dict(headers))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return HttpResponse(resp.status, _lower(resp.headers.items()), resp.read())
        except urllib.error.HTTPError as e:
            return HttpResponse(e.code, _lower(e.headers.items()), e.read())
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            # URL 의 질의 문자열은 남기지 않는다
            raise TransportError(f"{method} {url.split('?', 1)[0]}: {e}") from e
