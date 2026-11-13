"""신호 값 계산 — 순수 함수 (SPEC §4)."""

from collections.abc import Mapping
from datetime import datetime


def fork_delta(previous: Mapping[int, int], current: Mapping[int, int]) -> dict[int, int | None]:
    """주간 포크 증가 = 이번 스냅샷 − 지난 스냅샷. 지난 값이 없으면 None(결측, 0 이 아니다).

    포크가 지워지면 음수가 될 수 있다 — 그대로 둔다.
    """
    return {rid: (n - previous[rid]) if rid in previous else None for rid, n in current.items()}


def fork_delta_checked(previous: Mapping[int, int], previous_at: datetime | None,
                       current: Mapping[int, int], current_at: datetime,
                       min_days: int = 6, max_days: int = 8) -> tuple[dict[int, int | None], str]:
    """두 스냅샷 사이가 6~8일일 때만 주간 증가로 인정한다. 아니면 전부 결측과 이유."""
    if previous_at is None or not previous:
        return dict.fromkeys(current, None), "지난 스냅샷 없음"
    gap = (current_at - previous_at).total_seconds() / 86400
    if not min_days <= gap <= max_days:
        return dict.fromkeys(current, None), f"스냅샷 간격 {gap:.0f}일 — 주간 증가로 쓰지 않는다"
    return fork_delta(previous, current), ""
