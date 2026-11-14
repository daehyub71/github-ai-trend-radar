"""코드 관찰 I1~I7 (SPEC F10-1 · TASKS T7-4) — 숫자만으로 내는 문장. LLM 0.

모든 저장소에 낸다. 데이터가 없으면 그 관찰은 내지 않는다(값 없음을 0 으로 읽지 않는다).
- I1 사용 대비 관심: 주간 다운로드 ÷ 스타 증가 — 패키지가 있는 후보 안 순위
- I2 다운로드 추세: 이번 주 ÷ 지난 4주 평균, 창의 첫 주 대비 배수, 최근 4주 안 가장 큰 한 주 증가
- I3 포크 비율: 포크 증가 ÷ 스타 증가 — 후보 안 순위. 포크 증가가 없으면 누적 포크만
- I4 기여 폭: PR 작성자 수 — 4주 전·창의 첫 주와 비교
- I5 언급: 글 하나가 점수의 대부분인지, 이번 주 글 수·점수, 창 전체가 조용한지
- I6 의존: 의존 패키지 수(ecosyste.ms)
- I7 순위 이동: 지난주 → 이번 주, 창 안 최고·최저
창(window)은 이번 주를 포함한 최근 window_weeks 주. 문구·임계값은 settings.toml [insights] (규칙 v1).

trend_rows: 저장소 화면 02절 "이번 주 동향" 표 — 지난주 · 이번 주 · 지난 4주 평균(값이 둘 이상일 때).
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class InsightRules:
    window_weeks: int = 12
    ratio_top: float = 0.2  # I1·I3 — 후보 안 상위 이 비율이면 뜻을 붙인다(하위도 같은 비율)
    jump_min: float = 0.3  # I2 — 한 주 증가가 이 이상이면 문장으로
    single_share: float = 0.8  # I5 — 글 하나가 점수의 이 비율 이상
    quiet_points: int = 10  # I5 — 창 전체 점수 합이 이 미만이면 "조용하다"
    version: int = 1


RULES_V1 = InsightRules()


@dataclass(frozen=True)
class WeekPoint:
    """한 저장소의 한 주 값. None = 값 없음(수집 안 됨·해당 없음)."""

    week: str
    rank: int | None = None
    index: float | None = None
    stars: float | None = None
    downloads: float | None = None
    packages: str | None = None  # 다운로드를 잰 패키지(s4_packages) — 바뀐 주끼리는 견주지 않는다
    dependents: float | None = None
    forks: float | None = None
    fork_delta: float | None = None
    merged_prs: float | None = None
    pr_authors: float | None = None
    closed_issues: float | None = None
    hn_stories: float | None = None
    hn_points: float | None = None
    gn_topics: float | None = None
    gn_points: float | None = None


@dataclass(frozen=True)
class Insight:
    id: str
    title: str
    big: str
    text: str
    signal: str  # 화면 색 — s1~s5 또는 index

    def as_dict(self) -> dict[str, str]:
        return {"id": self.id, "title": self.title, "big": self.big, "text": self.text, "signal": self.signal}


def _d(week: str) -> date:
    return date.fromisoformat(week)


def _md(week: str) -> str:
    return week[5:]


def _n(v: float) -> str:
    return f"{v:,.0f}"


def _rank_desc(me: float, values: Sequence[float]) -> int:
    """큰 값이 1위. 같은 값은 같은 순위(앞선 개수 + 1)."""
    return 1 + sum(1 for v in values if v > me)


def _side(rank: int, n: int, top_share: float) -> str:
    k = max(1, math.ceil(n * top_share))
    if rank <= k:
        return "top"
    if rank > n - k:
        return "bottom"
    return ""


def _window(points: Sequence[WeekPoint], weeks: int) -> list[WeekPoint]:
    cur = _d(points[-1].week)
    start = cur - timedelta(weeks=weeks - 1)
    return sorted((p for p in points if start <= _d(p.week) <= cur), key=lambda p: p.week)


def _span(win: Sequence[WeekPoint]) -> int:
    return (_d(win[-1].week) - _d(win[0].week)).days // 7 + 1


def _i1(cur: WeekPoint, pop: Sequence[WeekPoint], r: InsightRules) -> Insight | None:
    def ratio(p: WeekPoint) -> float | None:
        if p.downloads is None or not p.stars or p.stars <= 0:
            return None
        return p.downloads / p.stars

    mine = ratio(cur)
    if mine is None:
        return None
    others = [v for v in (ratio(p) for p in pop if p is not cur) if v is not None]
    n = len(others) + 1
    rank = _rank_desc(mine, others)
    side = _side(rank, n, r.ratio_top)
    tail = {"top": " — 관심보다 실제 사용이 앞선 저장소입니다.",
            "bottom": " — 다운로드에 비해 관심이 큰 저장소입니다."}.get(side, ".")
    return Insight("I1", "사용 대비 관심", f"스타 1개당 다운로드 {_n(mine)}회",
                   f"패키지가 있는 후보 {n}개 중 {rank}위{tail}", "s4")


def _i2(win: Sequence[WeekPoint], r: InsightRules) -> Insight | None:
    cur = win[-1]
    if cur.downloads is None:
        return None
    if cur.packages:  # 패키지 연결이 바뀌기 전 주는 다른 패키지의 다운로드다
        win = [p for p in win if not p.packages or p.packages == cur.packages]
    c = _d(cur.week)
    by = {p.week: p.downloads for p in win if p.downloads is not None}
    prior = [by[w] for w in ((c - timedelta(weeks=k)).isoformat() for k in range(1, 5)) if w in by]
    if len(prior) < 2:
        return None
    avg = sum(prior) / len(prior)
    if avg <= 0:
        return None
    parts: list[str] = []
    first = next((p for p in win if p.downloads is not None), None)
    if first is not None and _d(first.week) < c - timedelta(weeks=4) and first.downloads:
        times = cur.downloads / first.downloads
        parts.append(f"{_span(win)}주 첫 주({_md(first.week)}, {_n(first.downloads)})의 {times:.2f}배.")
    best: tuple[float, str] | None = None
    for k in range(4):
        w = (c - timedelta(weeks=k)).isoformat()
        pw = (c - timedelta(weeks=k + 1)).isoformat()
        if w in by and pw in by and by[pw] > 0:
            jump = by[w] / by[pw] - 1
            if jump >= r.jump_min and (best is None or jump > best[0]):
                best = (jump, w)
    if best is not None:
        parts.append(f"{_md(best[1])} 주에 한 번에 {best[0] * 100:.0f}% 늘었습니다.")
    return Insight("I2", "다운로드 추세", f"4주 평균의 {cur.downloads / avg:.2f}배", " ".join(parts), "s4")


def _i3(cur: WeekPoint, pop: Sequence[WeekPoint], r: InsightRules) -> Insight | None:
    def ratio(p: WeekPoint) -> float | None:
        if p.fork_delta is None or not p.stars or p.stars <= 0:
            return None
        return p.fork_delta / p.stars

    mine = ratio(cur)
    if mine is None:
        if cur.forks is None:
            return None
        return Insight("I3", "포크 비율", f"누적 포크 {_n(cur.forks)}",
                       "주간 포크 증가는 6~8일 간격 스냅샷이 두 번 쌓인 뒤부터 나옵니다.", "s2")
    others = [v for v in (ratio(p) for p in pop if p is not cur) if v is not None]
    n = len(others) + 1
    rank = _rank_desc(mine, others)
    tail = " — 직접 고쳐 쓰려는 수요가 큰 편입니다." if _side(rank, n, r.ratio_top) == "top" else "."
    return Insight("I3", "포크 비율", f"스타 100개당 포크 {mine * 100:.1f}개",
                   f"포크 증가가 있는 후보 {n}개 중 {rank}위{tail}", "s2")


def _i4(win: Sequence[WeekPoint]) -> Insight | None:
    cur = win[-1]
    if cur.pr_authors is None:
        return None
    c = _d(cur.week)
    by = {p.week: p.pr_authors for p in win if p.pr_authors is not None}
    refs: list[tuple[str, float]] = []
    w4 = (c - timedelta(weeks=4)).isoformat()
    if w4 in by:
        refs.append(("4주 전", by[w4]))
    first = next((p for p in win if p.pr_authors is not None), None)
    if first is not None and first.pr_authors is not None and _d(first.week) < c - timedelta(weeks=4):
        refs.append((f"{_span(win)}주 첫 주", first.pr_authors))
    now = cur.pr_authors
    text = ", ".join(f"{label} {_n(v)}명" for label, v in refs)
    if refs:
        vals = [v for _, v in refs]
        if now > max(vals):
            text += " — 기여하는 사람이 늘고 있습니다."
        elif now < min(vals):
            text += " — 기여하는 사람이 줄었습니다."
        else:
            text += "."
    return Insight("I4", "기여 폭", f"PR 작성자 {_n(now)}명", text, "s3")


def _z(v: float | None) -> float:
    return v or 0.0


def _i5(win: Sequence[WeekPoint], r: InsightRules) -> Insight | None:
    cur = win[-1]
    if cur.hn_stories is None and cur.gn_topics is None:
        return None
    sources = (
        ("Hacker News", _z(cur.hn_stories), _z(cur.hn_points)),
        ("GeekNews", _z(cur.gn_topics), _z(cur.gn_points)),
    )
    posts = sum(n for _, n, _ in sources)
    pts = sum(p for _, _, p in sources)
    if posts > 0 and pts > 0:
        for _, n, p in sources:
            if n == 1 and p / pts >= r.single_share:
                return Insight("I5", "언급", f"언급 점수의 {p / pts * 100:.1f}%가 글 하나",
                               "글 하나가 이번 주 언급 신호를 만들었습니다.", "s5")
    if posts > 0:
        detail = " · ".join(f"{name} {_n(n)}건({_n(p)}점)" for name, n, p in sources if n > 0)
        return Insight("I5", "언급", f"이번 주 글 {_n(posts)}건 · {_n(pts)}점", f"{detail}.", "s5")
    span = _span(win)
    hs = sum(_z(p.hn_stories) for p in win)
    gs = sum(_z(p.gn_topics) for p in win)
    total = sum(_z(p.hn_points) + _z(p.gn_points) for p in win)
    if total < r.quiet_points:
        parts = [f"HN {_n(hs)}건"] + ([f"GeekNews {_n(gs)}건"] if gs else []) + [f"{_n(total)}점"]
        big = f"{span}주 " + " · ".join(parts) if hs or gs else f"{span}주 언급 0건"
        why = ("커뮤니티 화제보다 사용으로 오른 저장소입니다." if cur.downloads is not None
               else "커뮤니티 화제가 거의 없었습니다.")
        return Insight("I5", "언급", big, f"언급 점수 합이 {r.quiet_points} 미만 — {why}", "s5")
    return Insight("I5", "언급", "이번 주 언급 0건",
                   f"{span}주 동안 글 {_n(hs + gs)}건 · {_n(total)}점 — 이번 주는 조용했습니다.", "s5")


def _i6(cur: WeekPoint) -> Insight | None:
    if not cur.dependents:
        return None
    return Insight("I6", "의존", f"의존 패키지 {_n(cur.dependents)}개",
                   "다른 패키지가 기대어 쓰는 저장소입니다 (ecosyste.ms).", "s4")


def _i7(win: Sequence[WeekPoint]) -> Insight | None:
    cur = win[-1]
    if cur.rank is None:
        return None
    ranked = [p for p in win if p.rank is not None]
    prev_w = (_d(cur.week) - timedelta(weeks=1)).isoformat()
    prev = next((p.rank for p in ranked if p.week == prev_w), None)
    big = f"{prev}위 → {cur.rank}위" if prev is not None else f"{cur.rank}위 (처음)"
    if len(ranked) < 2:
        return Insight("I7", "순위 이동", big, "", "index")

    def label(p: WeekPoint) -> str:
        return "이번 주" if p is cur else f"{_md(p.week)} 주"

    # 같은 순위면 최근 주를 쓴다
    best = min(ranked, key=lambda p: (p.rank or 0, -_d(p.week).toordinal()))
    worst = max(ranked, key=lambda p: (p.rank or 0, _d(p.week).toordinal()))
    text = f"{_span(win)}주 최고 {best.rank}위({label(best)}), 최저 {worst.rank}위({label(worst)})."
    return Insight("I7", "순위 이동", big, text, "index")


def observe(
    points: Sequence[WeekPoint], population: Sequence[WeekPoint], rules: InsightRules
) -> list[Insight]:
    """points: 한 저장소의 주별 값(마지막 = 이번 주). population: 이번 주 후보 전체(자기 포함 가능)."""
    if not points:
        return []
    win = _window(points, rules.window_weeks)
    cur = win[-1]
    found = [_i1(cur, population, rules), _i2(win, rules), _i3(cur, population, rules), _i4(win),
             _i5(win, rules), _i6(cur), _i7(win)]
    return [i for i in found if i is not None]


DASH = "—"


def _posts(p: WeekPoint) -> float | None:
    if p.hn_stories is None and p.gn_topics is None:
        return None
    return _z(p.hn_stories) + _z(p.gn_topics)


TREND: tuple[tuple[str, Callable[[WeekPoint], float | None], Callable[[float], str]], ...] = (
    ("종합 순위", lambda p: p.rank, lambda v: f"{v:,.0f}위"),
    ("지수", lambda p: p.index, lambda v: f"{v:.1f}"),
    ("스타 증가", lambda p: p.stars, _n),
    ("주간 다운로드", lambda p: p.downloads, _n),
    ("머지 PR", lambda p: p.merged_prs, _n),
    ("PR 작성자", lambda p: p.pr_authors, _n),
    ("닫힌 이슈", lambda p: p.closed_issues, _n),
    ("HN·GeekNews 글", _posts, _n),
    ("포크 (누적)", lambda p: p.forks, _n),
    ("포크 증가", lambda p: p.fork_delta, _n),
)


def trend_rows(points: Sequence[WeekPoint]) -> list[dict[str, str]]:
    """이번 주에 값이 있는 항목만. 지난주·4주 평균은 없으면 대시."""
    if not points:
        return []
    by = {p.week: p for p in points}
    cur = max(points, key=lambda p: p.week)
    c = _d(cur.week)
    prev = by.get((c - timedelta(weeks=1)).isoformat())
    prior = [by[w] for w in ((c - timedelta(weeks=k)).isoformat() for k in range(1, 5)) if w in by]
    rows: list[dict[str, str]] = []
    for key, get, fmt in TREND:
        now = get(cur)
        if now is None:
            continue
        pv = get(prev) if prev is not None else None
        vals = [v for v in (get(p) for p in prior) if v is not None]
        avg = sum(vals) / len(vals) if len(vals) >= 2 else None
        rows.append({"key": key, "prev": DASH if pv is None else fmt(pv), "now": fmt(now),
                     "avg": DASH if avg is None else fmt(avg)})
    return rows


MENTION_KEYS = ("hn_stories", "hn_points", "gn_topics", "gn_points")


def mention_counts(points: Sequence[WeekPoint], rules: InsightRules) -> dict[str, dict[str, int]] | None:
    """04절 숫자 상자 — 이번 주와 창 전체의 HN·GeekNews 글 수·점수. 이번 주 언급 값이 없으면 None."""
    if not points:
        return None
    win = _window(points, rules.window_weeks)
    cur = win[-1]
    if cur.hn_stories is None and cur.gn_topics is None:
        return None
    week = {k: int(_z(getattr(cur, k))) for k in MENTION_KEYS}
    window = {"weeks": _span(win)} | {k: int(sum(_z(getattr(p, k)) for p in win)) for k in MENTION_KEYS}
    return {"week": week, "window": window}
