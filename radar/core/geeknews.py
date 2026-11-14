"""GeekNews `/past?day=` 날짜별 목록 해석 (SPEC D12) — 순수 함수. S5 수집기와 해설 근거(F10)가 같이 쓴다.

글 블록은 있는데 하나도 읽지 못하면 형식이 바뀐 것이다(ValueError).
"""

import html
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

_ROW = re.compile(r"<div class='topic_row'")
_ID = re.compile(r"data-topic-state-id='(\d+)'")
_LINK = re.compile(r"<a href='([^']+)'[^>]*class='topic-title-link'>")
_POINTS = re.compile(r"<span id='tp\d+'>(\d+)</span>\s*points")
_TIME = re.compile(r'<time [^>]*datetime="([^"]+)"')
_TITLE = re.compile(r"class='topic-title-heading'>(.*?)</h2>", re.S)
_GH = re.compile(r"github\.com/([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+)", re.I)


@dataclass(frozen=True)
class Topic:
    topic_id: int
    repo: str  # owner/name 소문자
    points: int
    day: date  # UTC 날짜
    title: str = ""
    link: str = ""  # 글이 가리킨 곳(깃허브 URL)


def parse_past(page: str, page_no: int = 1) -> tuple[list[Topic], bool]:
    """날짜별 목록 한 쪽 → (깃허브 저장소를 가리키는 글, 다음 쪽이 있는가). 형식이 바뀌면 ValueError."""
    blocks = ["<div class='topic_row'" + b for b in _ROW.split(page)[1:]]
    topics: list[Topic] = []
    read = 0
    for b in blocks:
        tid, link, tm = _ID.search(b), _LINK.search(b), _TIME.search(b)
        if not tid or not link or not tm:
            continue
        read += 1
        m = _GH.search(html.unescape(link.group(1)))
        if not m:
            continue
        try:
            day = datetime.fromisoformat(tm.group(1)).astimezone(UTC).date()
        except ValueError:
            continue
        pts = _POINTS.search(b)
        repo = f"{m.group(1)}/{m.group(2).removesuffix('.git')}".lower()
        ttl = _TITLE.search(b)
        raw_title = html.unescape(re.sub(r"<[^>]+>", "", ttl.group(1))) if ttl else ""
        title = re.sub(r"\s+", " ", raw_title).strip()
        topics.append(Topic(int(tid.group(1)), repo, int(pts.group(1)) if pts else 0, day, title,
                            html.unescape(link.group(1))))
    if blocks and not read:
        raise ValueError(f"GeekNews 목록 형식이 바뀌었다 (글 {len(blocks)}개를 읽지 못함)")
    has_next = re.search(rf"(?:&|&amp;|\?)page={page_no + 1}(?!\d)", page) is not None
    return topics, has_next
