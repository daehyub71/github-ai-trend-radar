"""S3 기여 — 머지 PR 수·고유 PR 작성자 수·닫힌 이슈 수 (TASKS T1-3, SPEC D5, PLAN §3).

- 창 전체(여러 주)를 질의 한 번으로 받아 `merged_at`·`closed_at` 으로 주별로 나눈다.
- Search 는 1,000건까지만 준다. 넘으면 주 단위로 쪼개 다시 묻는다. 한 주가 1,000건을 넘으면
  받을 수 있는 만큼만 세고 partial 로 남긴다.
- 봇(`type == Bot` 또는 `[bot]`)은 PR·이슈 모두 뺀다.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from urllib.parse import urlencode

from radar.clients.http import HttpClient
from radar.collectors.base import FAILED, GH_API, OK, PARTIAL, gh_headers, is_bot, utc_day
from radar.core.weeks import week_end, week_start

SEARCH_CAP = 1000
PER_PAGE = 100


@dataclass(frozen=True)
class WeekActivity:
    merged_prs: int
    pr_authors: int
    closed_issues: int


@dataclass
class ActivityResult:
    full_name: str
    weekly: dict[date, WeekActivity] = field(default_factory=dict)
    status: str = OK
    note: str = ""


class _SearchFailed(Exception):
    pass


def _search(client: HttpClient, token: str, q: str) -> tuple[int, list[dict[str, Any]]]:
    """(총계, 받은 결과). 실패하면 _SearchFailed."""
    items: list[dict[str, Any]] = []
    total = 0
    for page in range(1, SEARCH_CAP // PER_PAGE + 1):
        url = f"{GH_API}/search/issues?" + urlencode({"q": q, "per_page": PER_PAGE, "page": page})
        st, body = client.get_json("gh_search", url, gh_headers(token))
        if st != 200 or not isinstance(body, dict) or not isinstance(body.get("items"), list):
            raise _SearchFailed(f"Search {st}")
        total = int(body.get("total_count") or 0)
        got = [it for it in body["items"] if isinstance(it, dict)]
        items += got
        if len(got) < PER_PAGE or len(items) >= total:
            break
    return total, items


def _fetch(client: HttpClient, token: str, full_name: str, qual: str, weeks: Sequence[date],
           notes: list[str]) -> list[dict[str, Any]]:
    """창을 한 번에 묻고, 1,000건을 넘으면 주 단위로 다시 묻는다."""
    since, until = weeks[0], week_end(weeks[-1])
    total, items = _search(client, token, f"repo:{full_name} {qual}:{since.isoformat()}..{until.isoformat()}")
    if total <= SEARCH_CAP:
        return items
    if len(weeks) == 1:
        notes.append(f"{qual} {since.isoformat()} 주 {total:,}건 — Search 상한 1,000건까지만 셌다")
        return items
    out: list[dict[str, Any]] = []
    for w in weeks:
        out += _fetch(client, token, full_name, qual, [w], notes)
    return out


def collect(client: HttpClient, token: str, full_name: str, weeks: Sequence[date]) -> ActivityResult:
    """weeks: 이어진 주 시작일 목록(오래된 순)."""
    res = ActivityResult(full_name)
    notes: list[str] = []
    try:
        prs = _fetch(client, token, full_name, "is:pr is:merged merged", weeks, notes)
        issues = _fetch(client, token, full_name, "is:issue is:closed closed", weeks, notes)
    except _SearchFailed as e:
        res.status, res.note = FAILED, str(e)
        return res
    wanted = set(weeks)
    merged: dict[date, int] = dict.fromkeys(weeks, 0)
    authors: dict[date, set[str]] = {w: set() for w in weeks}
    closed: dict[date, int] = dict.fromkeys(weeks, 0)
    for it in prs:
        d = utc_day((it.get("pull_request") or {}).get("merged_at") or it.get("closed_at"))
        if d is None or is_bot(it.get("user")) or week_start(d) not in wanted:
            continue
        merged[week_start(d)] += 1
        authors[week_start(d)].add(str((it.get("user") or {}).get("login")))
    for it in issues:
        d = utc_day(it.get("closed_at"))
        if d is None or is_bot(it.get("user")) or week_start(d) not in wanted:
            continue
        closed[week_start(d)] += 1
    res.weekly = {w: WeekActivity(merged[w], len(authors[w]), closed[w]) for w in weeks}
    if notes:
        res.status, res.note = PARTIAL, "; ".join(notes)
    return res
