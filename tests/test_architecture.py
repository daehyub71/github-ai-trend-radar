"""층 규칙 (PLAN §2). 통제군: 검사기가 일부러 만든 위반을 실제로 잡는지 먼저 확인한다."""

import socket
from pathlib import Path

import pytest

from tests.harness import NetworkBlocked, check_sources, project_sources

ROOT = Path(__file__).resolve().parents[1]


def test_architecture_detects_core_importing_clients():
    v = check_sources({"radar/core/x.py": "from radar.clients import transport\n"})
    assert len(v) == 1 and "core 층은 clients 층" in v[0]


def test_architecture_detects_inputs_importing_clients():
    v = check_sources({"radar/inputs/x.py": "import radar.clients.transport\n"})
    assert len(v) == 1 and "inputs 층은 clients 층" in v[0]


def test_architecture_detects_collector_importing_other_collector():
    v = check_sources({"radar/collectors/forks.py": "from radar.collectors import activity\n"})
    assert len(v) == 1 and "수집기끼리" in v[0]
    v = check_sources({"radar/collectors/forks.py": "import radar.collectors.activity\n"})
    assert len(v) == 1 and "수집기끼리" in v[0]


def test_architecture_detects_core_importing_app():
    v = check_sources({"radar/core/x.py": "from radar import config\n"})
    assert len(v) == 1 and "core 층은 app 층" in v[0]
    v = check_sources({"radar/core/x.py": "import radar.config\n"})
    assert len(v) == 1 and "core 층은 app 층" in v[0]


def test_architecture_detects_network_outside_transport():
    v = check_sources({"radar/collectors/forks.py": "import urllib.request\n"})
    assert len(v) == 1 and "네트워크 모듈" in v[0]
    v = check_sources({"radar/pipeline.py": "from urllib import request\n"})
    assert len(v) == 1 and "네트워크 모듈" in v[0]


def test_architecture_detects_llm_sdk_outside_claude_client():
    v = check_sources({"radar/pipeline.py": "import anthropic\n"})
    assert len(v) == 1 and "LLM SDK" in v[0]


def test_architecture_detects_relative_import():
    v = check_sources({"radar/core/x.py": "from . import weeks\n"})
    assert len(v) == 1 and "상대 import" in v[0]


def test_architecture_allows_legal_imports():
    sources = {
        "radar/clients/transport.py": "import urllib.request\nfrom radar.core import weeks\n",
        "radar/collectors/forks.py": (
            "from radar.clients.transport import Transport\nfrom radar.collectors import base\n"
        ),
        "radar/inputs/startrend.py": "from radar.core.weeks import week_start\n",
        "radar/pipeline.py": (
            "from radar.collectors import forks, activity\nfrom radar.inputs import startrend\n"
        ),
        "radar/cli.py": "from radar import pipeline\n",
    }
    assert check_sources(sources) == []


def test_architecture_project_has_no_violations():
    sources = project_sources(ROOT)
    assert sources, "검사할 소스가 없다 — 경로가 틀렸다"
    assert check_sources(sources) == []


def test_network_is_blocked_in_default_tests():
    # 통제군: 기본 테스트에서 실제 접속이 정말 막히는가
    with pytest.raises(NetworkBlocked):
        socket.create_connection(("example.com", 443), timeout=1)
