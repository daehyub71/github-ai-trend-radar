"""층 사이에 오가는 값 (PLAN §1·§2)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RepoMeta:
    """star-trend 가 AI 로 판정한 저장소."""

    id: int
    full_name: str
    created: str | None
    category: str | None
    secondary: str | None
    kind: str | None  # classify.type (도구/라이브러리 등)
    description: str | None = None  # 저장소 설명(외부 글 — LLM 에는 신뢰하지 않는 데이터로 넘긴다)
    topics: tuple[str, ...] = ()
    language: str | None = None


@dataclass(frozen=True)
class StarRow:
    """star-trend 주간 스타 파일의 한 행."""

    id: int
    full_name: str
    gain: int
    stars_end: int
    exact: bool


@dataclass(frozen=True)
class Candidate:
    """그 주 신호를 모을 후보 (SPEC F2·D2)."""

    id: int
    full_name: str
    gain: int
    gain_rank: int | None  # AI 저장소 안 스타 증가 순위. 스타 파일에 없으면 None
    reason: str  # "gain_top" | "prev_top"
