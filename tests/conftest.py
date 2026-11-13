"""공통 픽스처. 기본 테스트는 네트워크 0 — 약속이 아니라 코드로 막는다 (SPEC N2)."""

import socket
from typing import Any

import pytest

from tests.harness import NetworkBlocked


def _guard(*args: Any, **kwargs: Any) -> Any:
    raise NetworkBlocked("기본 테스트에서 네트워크 접속 금지 — 실제 호출은 @pytest.mark.live 로 표시한다")


@pytest.fixture(autouse=True)
def _block_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("live"):
        return
    monkeypatch.setattr(socket.socket, "connect", _guard)
    monkeypatch.setattr(socket.socket, "connect_ex", _guard)
    monkeypatch.setattr(socket, "create_connection", _guard)
    monkeypatch.setattr(socket, "getaddrinfo", _guard)
