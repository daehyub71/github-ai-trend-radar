"""LLM 비용 상한 (SPEC D4 — 실행당 $3, T5-2). 최악 비용이 상한을 넘을 수 있으면 부르지 않는다.

최악 비용은 보수적 입력 추정 + 구조화 출력 몫 + `max_tokens` 전부를 출력으로 본 값이다.
거절 시 대체 모델이 이어 받을 수 있어 요청 모델과 대체 모델 중 비싼 단가로 센다.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

# 100만 토큰당 달러 (입력, 출력). 2026-11-03 공식 단가표 기준
PRICES: dict[str, tuple[float, float]] = {
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-sonnet-5": (2.0, 10.0),
}
# github-ai-star-trend 실측 200건에서 가장 촘촘한 요청이 1.52바이트/토큰이었다
BYTES_PER_TOKEN = 1.5
# 구조화 출력(json_schema)이 입력에 더하는 몫 (같은 실측의 회귀 절편 690)
SCHEMA_TOKENS = 700
# 웹 검색 1회 요금과 결과가 입력에 더하는 토큰 몫 (D35). 몫은 동적 필터링 전 결과 크기로 넉넉히 잡는다
SEARCH_USD = 0.01
SEARCH_TOKENS = 25_000


class BudgetExceeded(Exception):
    """이 호출을 하면 비용 상한을 넘을 수 있다."""


def estimate_tokens(text: str) -> int:
    """입력 토큰을 넉넉하게 추정한다. 실제보다 작게 잡으면 안 된다."""
    return math.ceil(len(text.encode("utf-8")) / BYTES_PER_TOKEN)


def cost_usd(models: Sequence[str], input_tokens: int, output_tokens: int) -> float:
    """토큰 수를 비용으로 바꾼다. 여러 모델 중 가장 비싼 단가를 쓴다.

    Args:
        models: 요청 모델과 대체 모델.
        input_tokens: 입력 토큰 수.
        output_tokens: 출력 토큰 수(사고 토큰 포함).

    Returns:
        달러 비용.

    Raises:
        BudgetExceeded: 단가를 모르는 모델이 있을 때. 비용을 셀 수 없으면 부르지 않는다.
    """
    unknown = [model for model in models if model not in PRICES]
    if unknown or not models:
        raise BudgetExceeded(f"단가를 모르는 모델: {', '.join(unknown) or '없음'}")
    input_price = max(PRICES[model][0] for model in models)
    output_price = max(PRICES[model][1] for model in models)
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


@dataclass
class Budget:
    """실행당 비용 계량기."""

    cap_usd: float
    spent_usd: float = 0.0

    def reserve(self, models: Sequence[str], prompt: str, *, max_tokens: int, searches: int = 0) -> float:
        """부르기 전 확인. 최악 비용이 남은 예산을 넘으면 BudgetExceeded를 올린다.

        Args:
            models: 요청 모델과 대체 모델.
            prompt: 보낼 지시문과 입력을 합친 글.
            max_tokens: 출력 상한.
            searches: 허용한 웹 검색 횟수.

        Returns:
            최악 비용.
        """
        input_tokens = estimate_tokens(prompt) + SCHEMA_TOKENS + searches * SEARCH_TOKENS
        worst = cost_usd(models, input_tokens, max_tokens) + searches * SEARCH_USD
        if self.spent_usd + worst > self.cap_usd:
            raise BudgetExceeded(f"최악 ${worst:.4f}, 남은 예산 ${self.cap_usd - self.spent_usd:.4f}")
        return worst

    def record(
        self, models: Sequence[str], input_tokens: int, output_tokens: int, *, searches: int = 0
    ) -> float:
        """실제 사용량을 더하고 그 비용을 돌려준다. 웹 검색 요금도 더한다."""
        actual = cost_usd(models, input_tokens, output_tokens) + searches * SEARCH_USD
        self.spent_usd += actual
        return actual
