"""주 경계 (SPEC §4) — 주는 일요일에 시작한다(UTC). star-trend 와 같은 경계다."""

from datetime import date, timedelta


def week_start(d: date) -> date:
    """d 가 속한 주의 일요일."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


def week_end(week: date) -> date:
    """주의 마지막 날(토요일, 포함)."""
    return week + timedelta(days=6)


def weeks_back(week: date, n: int) -> list[date]:
    """week 바로 앞의 n 주, 오래된 주부터."""
    return [week - timedelta(weeks=k) for k in range(n, 0, -1)]


def parse_week(text: str) -> date:
    """'YYYY-MM-DD' → 주 시작일. 일요일이 아니면 ValueError."""
    d = date.fromisoformat(text)
    if week_start(d) != d:
        raise ValueError(f"주 이름은 일요일이어야 한다: {text}")
    return d


def target_week(today: date) -> date:
    """주간 실행이 처리할 주 — 오늘 기준 마지막으로 끝난 주(일~토)."""
    return week_start(today) - timedelta(weeks=1)
