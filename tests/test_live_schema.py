"""구조화 출력 스키마가 실제 API 에서 문법으로 컴파일되는지 (실제 호출, 수 토큰).

기본 테스트는 스키마 모양만 본다. 문법 크기 한도(400 "compiled grammar is too large")는 서버만 안다 —
스키마를 바꾸면 `pytest -m live` 로 이것을 돌린다 (11-14 해설 28개가 이 오류로 모두 실패).
"""

import os

import pytest

from radar.clients.claude import ClaudeClient, LLMRequest
from radar.publish import card


@pytest.mark.live
def test_live_card_schema_compiles() -> None:
    key = os.environ.get("STARTREND_ANTHROPIC_API_KEY", "")
    if not key:
        pytest.skip("STARTREND_ANTHROPIC_API_KEY 가 없다 — 이 명령에만 넘긴다")
    reply = ClaudeClient(key).complete(
        LLMRequest(system="짧게 답한다.", user="빈 해설을 JSON 으로.", schema=card.SCHEMA, max_tokens=64,
                   effort="low")
    )
    assert reply.stop_reason in ("end_turn", "max_tokens")
