"""GeekNews 근거 — 그 주 `/past?day=` 목록을 한 번 훑어 저장소별로 나눈다 (SPEC D12·F10-2).

요청 간격 2초는 HttpClient 정책(geeknews)이 지킨다. 날짜는 KST 라 UTC 주 끝을 덮도록 하루 더 읽는다.
댓글 수는 목록에 없어 None 으로 둔다.
"""

from datetime import date, timedelta
from typing import Any
from urllib.parse import urlencode

from radar.clients.http import HttpClient
from radar.clients.transport import TransportError
from radar.core import evidence as ev
from radar.core.geeknews import Topic, parse_past
from radar.core.weeks import week_end

GEEKNEWS = "https://news.hada.io"
MAX_PAGES = 3


def geeknews_week(client: HttpClient, week: date,
                  max_pages: int = MAX_PAGES) -> tuple[dict[str, list[Topic]], list[str]]:
    """({저장소 소문자: [그 주 글]}, 실패한 날)."""
    end = week_end(week)
    idx: dict[str, list[Topic]] = {}
    failed: list[str] = []
    seen: set[int] = set()
    day = week
    while day <= end + timedelta(days=1):
        for page_no in range(1, max_pages + 1):
            q = {"day": day.isoformat()} | ({"page": str(page_no)} if page_no > 1 else {})
            try:
                url = f"{GEEKNEWS}/past?{urlencode(q)}"
                st, text = client.get_text("geeknews", url, {"Accept": "text/html"})
                if st != 200:
                    raise ValueError(f"{st}")
                topics, has_next = parse_past(text, page_no)
            except (ValueError, TransportError) as e:
                failed.append(f"{day.isoformat()}({e})")
                break
            for tp in topics:
                if week <= tp.day <= end and tp.topic_id not in seen:
                    seen.add(tp.topic_id)
                    idx.setdefault(tp.repo, []).append(tp)
            if not has_next:
                break
        day += timedelta(days=1)
    return idx, failed


def collect_geeknews(index: dict[str, list[Topic]],
                     t: ev.Target) -> tuple[list[ev.Evidence], list[dict[str, Any]]]:
    docs: list[ev.Evidence] = []
    posts: list[dict[str, Any]] = []
    for tp in sorted(index.get(t.full_name.lower(), []), key=lambda x: (-x.points, x.topic_id)):
        url = f"{GEEKNEWS}/topic?id={tp.topic_id}"
        title = tp.title or f"GeekNews 글 {tp.topic_id}"
        docs.append(ev.make(url=url, source="geeknews", kind="topic", title=title, text=title,
                            published_at=tp.day.isoformat(), extra={"points": tp.points}))
        posts.append({"site": "GeekNews", "title": title, "url": url, "points": tp.points, "comments": None,
                      "date": tp.day.isoformat(), "target": ev.target_label(tp.link, t.full_name)})
    return docs, posts
