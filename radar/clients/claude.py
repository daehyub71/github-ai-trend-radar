"""Anthropic API 클라이언트 (SPEC D4 — Sonnet 5.5). LLM SDK 는 이 파일에서만 import 한다(PLAN §2).

구조화 출력(json_schema)과 서버 대체 모델(거절 시 Sonnet 5)을 쓴다. temperature 는 주지 않는다.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

MODEL = "claude-sonnet-5-5"
EFFORT = "medium"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS: tuple[str, ...] = ("claude-sonnet-5",)


@dataclass(frozen=True)
class LLMRequest:
    system: str
    user: str
    schema: dict[str, Any]
    max_tokens: int = 16000
    effort: str = EFFORT


@dataclass(frozen=True)
class LLMResponse:
    """토큰 수는 사고 토큰을 포함한 청구 기준."""

    text: str
    stop_reason: str
    model: str
    input_tokens: int
    output_tokens: int


class LLMClient(Protocol):
    @property
    def model(self) -> str: ...

    def complete(self, request: LLMRequest) -> LLMResponse: ...


class ClaudeClient:
    """한 번 부르고 글 블록만 모은다. 키는 표시하지 않는다."""

    def __init__(self, api_key: str, *, model: str = MODEL, client: Any = None) -> None:
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key, timeout=600.0, max_retries=2)
        self._client = client
        self._model = model

    def __repr__(self) -> str:
        return f"ClaudeClient(model={self._model!r})"

    @property
    def model(self) -> str:
        return self._model

    def complete(self, request: LLMRequest) -> LLMResponse:
        # ai-trend-batch 에서 실제로 쓰는 형태 그대로 (max_tokens 16000 은 비스트리밍 한도 안)
        message = self._client.beta.messages.create(
            model=self._model,
            max_tokens=request.max_tokens,
            system=request.system,
            messages=[{"role": "user", "content": request.user}],
            output_config={"effort": request.effort,
                           "format": {"type": "json_schema", "schema": request.schema}},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
        text = "".join(b.text for b in message.content if getattr(b, "type", None) == "text")
        u = message.usage
        return LLMResponse(text, str(message.stop_reason or ""), str(message.model),
                           int(u.input_tokens or 0), int(u.output_tokens or 0))


@dataclass
class MockLLM:
    """테스트용 — 준비한 응답이나 함수로 답하고 받은 요청을 남긴다."""

    script: list[LLMResponse] | Callable[[LLMRequest], LLMResponse]
    model: str = MODEL
    requests: list[LLMRequest] = field(default_factory=list)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if callable(self.script):
            return self.script(request)
        if not self.script:
            raise AssertionError("MockLLM: 준비한 응답보다 많이 불렀다")
        return self.script.pop(0)
