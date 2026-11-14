"""S5 언급 — Hacker News(Algolia) · GeekNews 날짜별 목록 (TASKS T1-5, SPEC D12).

- 저장소 URL 이 정확히 들어간 글만 센다(이름만 비슷한 저장소는 뺀다).
- GeekNews 는 공식 API 가 없어 `/past?day=` HTML 을 읽는다. 요청 간격 2초(HttpClient 정책)·하루 최대 3쪽.
  한 번 훑어 저장소별로 나눠 두고 후보마다 꺼낸다. 글 블록은 있는데 하나도 읽지 못하면 형식이 바뀐 것이다.
- 주는 글 시각(UTC)으로 정한다. GeekNews 날짜는 KST 라 UTC 주 끝을 덮도록 하루 더 읽는다.
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlencode

from radar.clients.http import HttpClient
from radar.clients.transport import TransportError
from radar.collectors.base import FAILED, OK, PARTIAL, same_repo
from radar.core.geeknews import Topic as Topic
from radar.core.geeknews import parse_past as parse_past
from radar.core.weeks import week_end, week_start

HN = "https://hn.algolia.com/api/v1/search"
GEEKNEWS = "https://news.hada.io"
MAX_PAGES = 3

def _utc_ts(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())


def hn_mentions(client: HttpClient, full_name: str,
                weeks: Sequence[date]) -> tuple[dict[date, tuple[int, int]], str]:
    """({주: (글 수, 점수 합)}, 상태)."""
    a, b = _utc_ts(weeks[0]), _utc_ts(week_end(weeks[-1]) + timedelta(days=1))
    params = {"query": f"github.com/{full_name}", "restrictSearchableAttributes": "url", "tags": "story",
              "numericFilters": f"created_at_i>={a},created_at_i<{b}", "hitsPerPage": 1000}
    st, body = client.get_json("hn", f"{HN}?{urlencode(params)}")
    if st != 200 or not isinstance(body, dict) or not isinstance(body.get("hits"), list):
        return {}, FAILED
    out = {w: (0, 0) for w in weeks}
    for h in body["hits"]:
        if not isinstance(h, dict) or not same_repo(h.get("url"), full_name):
            continue
        w = week_start(datetime.fromtimestamp(int(h.get("created_at_i") or 0), UTC).date())
        if w in out:
            n, p = out[w]
            out[w] = (n + 1, p + int(h.get("points") or 0))
    return out, OK


def geeknews_index(client: HttpClient, weeks: Sequence[date],
                   max_pages: int = MAX_PAGES) -> tuple[dict[str, dict[date, tuple[int, int]]], str, str]:
    """({저장소: {주: (글 수, 점수 합)}}, 상태, 메모). 창의 날마다 1쪽부터 다음 쪽이 있으면 max_pages 까지."""
    first, last = weeks[0], week_end(weeks[-1]) + timedelta(days=1)
    wanted = set(weeks)
    idx: dict[str, dict[date, tuple[int, int]]] = {}
    failed: list[str] = []
    seen: set[int] = set()  # 글 ID — 같은 글이 이틀 목록에 걸쳐 나와도 한 번만
    day = first
    while day <= last:
        for page_no in range(1, max_pages + 1):
            q = {"day": day.isoformat()} | ({"page": str(page_no)} if page_no > 1 else {})
            try:
                st, text = client.get_text("geeknews", f"{GEEKNEWS}/past?{urlencode(q)}",
                                           {"Accept": "text/html"})
                if st != 200:
                    raise ValueError(f"{st}")
                topics, has_next = parse_past(text, page_no)
            except (ValueError, TransportError) as e:
                failed.append(f"{day.isoformat()}({e})")
                break
            for t in topics:
                w = week_start(t.day)
                if w not in wanted or t.topic_id in seen:
                    continue
                seen.add(t.topic_id)
                per = idx.setdefault(t.repo, {})
                n, p = per.get(w, (0, 0))
                per[w] = (n + 1, p + t.points)
            if not has_next:
                break
        day += timedelta(days=1)
    if failed:
        days = (last - first).days + 1
        status = FAILED if len(failed) >= days else PARTIAL
        return idx, status, "읽지 못한 날: " + ", ".join(failed)
    return idx, OK, ""
