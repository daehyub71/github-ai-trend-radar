"""HN 근거 — Algolia (SPEC F10-2). 저장소 링크 글(12주)과 이번 주 글의 큰 댓글 타래.

- 글: 저장소 URL(하위 경로 포함)이 정확히 걸린 것만. 점수 순으로 최대 10개를 근거로.
- 댓글: 이번 주 글 중 댓글이 있는 점수 상위 2개를 열어, 맨 위 댓글을 답글이 많은 순으로 5개 — 첫 댓글만 600자.
- 작성자 아이디는 남기지 않는다(개인 이름을 해설에 쓰지 않는다).
근거 URL 은 HN 토론 페이지(item?id=)다. 화면의 "글 목록"은 이번 주 글만.
"""

import html
import re
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from urllib.parse import urlencode

from radar.clients.http import HttpClient
from radar.clients.transport import TransportError
from radar.core import evidence as ev
from radar.evidence.base import SourceError

SEARCH = "https://hn.algolia.com/api/v1/search"
ITEM_API = "https://hn.algolia.com/api/v1/items/"
ITEM = "https://news.ycombinator.com/item?id="
WINDOW_WEEKS = 12
MAX_STORIES = 10
OPEN_STORIES = 2
THREADS = 5
COMMENT_CHARS = 600


def strip_html(s: str) -> str:
    s = re.sub(r"(?i)<p\s*/?>", "\n\n", s)
    s = re.sub(r"<[^>]*>", "", s)
    return html.unescape(s).strip()


def _epoch(d: date) -> int:
    return int(datetime.combine(d, time(), tzinfo=UTC).timestamp())


def _day(h: dict[str, Any]) -> date:
    return datetime.fromtimestamp(int(h["created_at_i"]), tz=UTC).date()


def _size(node: dict[str, Any]) -> int:
    kids = node.get("children") or []
    return 1 + sum(_size(k) for k in kids if isinstance(k, dict))


def _threads(client: HttpClient, story: dict[str, Any]) -> list[ev.Evidence]:
    try:
        st, body = client.get_json("hn", f"{ITEM_API}{story['objectID']}")
    except TransportError:
        return []
    if st != 200 or not isinstance(body, dict):
        return []
    kids = [k for k in body.get("children") or [] if isinstance(k, dict) and k.get("text") and k.get("id")]
    kids.sort(key=lambda k: -_size(k))
    out = []
    for k in kids[:THREADS]:
        text = strip_html(str(k["text"]))[:COMMENT_CHARS]
        out.append(ev.make(url=f"{ITEM}{k['id']}", source="hn", kind="comment",
                           title=f"HN 댓글 — {story['title']}", text=text,
                           published_at=str(k.get("created_at") or "") or None,
                           extra={"replies": _size(k) - 1, "story_id": str(story["objectID"])}))
    return out


def collect_hn(client: HttpClient, t: ev.Target) -> tuple[list[ev.Evidence], list[dict[str, Any]]]:
    """(근거, 이번 주 글 목록). 검색이 실패하면 SourceError."""
    since = t.since - timedelta(weeks=WINDOW_WEEKS - 1)
    end = _epoch(t.until + timedelta(days=1))
    params = {"query": f"github.com/{t.full_name}", "restrictSearchableAttributes": "url", "tags": "story",
              "numericFilters": f"created_at_i>={_epoch(since)},created_at_i<{end}", "hitsPerPage": 1000}
    try:
        st, body = client.get_json("hn", f"{SEARCH}?{urlencode(params)}")
    except TransportError as e:
        raise SourceError(f"HN 연결 실패: {type(e).__name__}") from e
    if st != 200 or not isinstance(body, dict) or not isinstance(body.get("hits"), list):
        raise SourceError(f"HN {st}")
    stories = []
    for h in body["hits"]:
        if not isinstance(h, dict) or not all(h.get(k) for k in ("objectID", "title", "created_at_i")):
            continue
        if ev.github_repo(str(h.get("url") or "")) != t.full_name.lower():
            continue
        stories.append(h)
    stories.sort(key=lambda h: (-int(h.get("points") or 0), str(h["objectID"])))
    docs: list[ev.Evidence] = []
    posts: list[dict[str, Any]] = []
    for h in stories[:MAX_STORIES]:
        body_text = strip_html(str(h.get("story_text") or ""))
        extra = {"points": int(h.get("points") or 0), "comments": int(h.get("num_comments") or 0),
                 "linked_url": h.get("url")}
        docs.append(ev.make(url=f"{ITEM}{h['objectID']}", source="hn", kind="story", title=str(h["title"]),
                            text=f"{h['title']}\n\n{body_text}".strip(),
                            published_at=str(h.get("created_at") or ""), extra=extra))
    this_week = [h for h in stories if t.since <= _day(h) <= t.until]
    for h in this_week:
        posts.append({"site": "HN", "title": str(h["title"]), "url": f"{ITEM}{h['objectID']}",
                      "points": int(h.get("points") or 0), "comments": int(h.get("num_comments") or 0),
                      "date": _day(h).isoformat(), "target": ev.target_label(h.get("url"), t.full_name)})
    for h in [h for h in this_week if int(h.get("num_comments") or 0) > 0][:OPEN_STORIES]:
        docs.extend(_threads(client, h))
    return docs, posts
