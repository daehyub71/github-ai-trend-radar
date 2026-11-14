"""차트 데이터 (SPEC F11 · TASKS T8-3) — 그리기 전에 숫자를 코드가 정한다. 순수 함수, LLM 0.

입력은 주별 지수 문서(`data/index/<주>.json` 모양: week · rows[rank·repo_id·full_name·category·index·
pct·contrib·missing·backfilled]), 오래된 주부터. "TOP n" 은 순위 값이 n 이하인 저장소다.
- C1 rank_series: 이번 주 TOP n 의 창(n_weeks) 순위 — 후보 밖 주는 None
- C2 contribution_bars: 이번 주 TOP n 의 신호별 기여분
- C3 signal_map / quadrant: 관심(스타·언급 백분위 평균) × 실사용(기여·사용 백분위 평균)
- C4 signal_shares / category_mix / trend_observations: 주별 TOP n 기여분의 신호 비중,
  카테고리 분포, 관찰 문장
- R1 repo_card_lines: 저장소 카드에 넣을 줄(해설 3줄 요약, 없으면 코드 관찰 2개)
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

SIGNALS = ("s1", "s2", "s3", "s4", "s5")
ATTENTION = ("s1", "s5")
USE = ("s3", "s4")
CUT = 50.0
OTHER = "기타"


def _top(week: Mapping[str, Any], top_n: int) -> list[Mapping[str, Any]]:
    return sorted(
        (r for r in week["rows"] if r["rank"] is not None and r["rank"] <= top_n), key=lambda r: r["rank"]
    )


def _backfilled(week: Mapping[str, Any]) -> bool:
    return bool(week["rows"]) and all(r.get("backfilled") for r in week["rows"])


def _mean(vals: Sequence[float | None]) -> float | None:
    got = [v for v in vals if v is not None]
    return sum(got) / len(got) if got else None


@dataclass(frozen=True)
class Series:
    repo_id: int
    full_name: str
    rank_now: int
    points: tuple[tuple[str, int | None, bool], ...]  # (주, 순위 또는 None, 소급 주인가)
    new_entry: bool  # 4주 전에 TOP n 밖이었나


def rank_series(weeks: Sequence[Mapping[str, Any]], *, top_n: int = 10, n_weeks: int = 12) -> list[Series]:
    win = list(weeks)[-n_weeks:]
    if not win:
        return []
    ranks = [{r["repo_id"]: r["rank"] for r in w["rows"]} for w in win]
    past = {}
    cur = date.fromisoformat(win[-1]["week"])
    four = (cur - timedelta(weeks=4)).isoformat()
    for w, rk in zip(win, ranks, strict=True):
        if w["week"] == four:
            past = rk
    out = []
    for r in _top(win[-1], top_n):
        rid = r["repo_id"]
        pts = tuple((w["week"], rk.get(rid), _backfilled(w)) for w, rk in zip(win, ranks, strict=True))
        before = past.get(rid)
        out.append(Series(rid, r["full_name"], r["rank"], pts, before is None or before > top_n))
    return out


@dataclass(frozen=True)
class Bar:
    rank: int
    repo_id: int
    full_name: str
    index: float
    contrib: dict[str, float]
    missing: tuple[str, ...]


def contribution_bars(week: Mapping[str, Any], *, top_n: int = 10) -> list[Bar]:
    return [
        Bar(
            r["rank"],
            r["repo_id"],
            r["full_name"],
            float(r["index"]),
            {s: float(r["contrib"].get(s) or 0.0) for s in SIGNALS},
            tuple(r.get("missing") or ()),
        )
        for r in _top(week, top_n)
    ]


@dataclass(frozen=True)
class MapPoint:
    repo_id: int
    full_name: str
    attention: float
    usage: float
    mark: str | None  # TOP 순위("1"~) · 관점 유형("A"~"D") · 없음


def signal_map(week: Mapping[str, Any], angles: Mapping[str, Any], *, top_n: int = 10) -> list[MapPoint]:
    """관심·실사용 두 값이 모두 있는 후보만 찍는다. 표시는 TOP 순위가 관점 유형보다 앞선다."""
    angle_of = {
        it["repo_id"]: k for k in ("A", "B", "C", "D") for it in (angles.get(k) or {}).get("items", [])
    }
    out = []
    for r in week["rows"]:
        att = _mean([r["pct"].get(s) for s in ATTENTION])
        use = _mean([r["pct"].get(s) for s in USE])
        if att is None or use is None:
            continue
        mark = str(r["rank"]) if r["rank"] is not None and r["rank"] <= top_n else angle_of.get(r["repo_id"])
        out.append(MapPoint(r["repo_id"], r["full_name"], att, use, mark))
    return out


def quadrant(attention: float, usage: float, cut: float = CUT) -> str:
    if attention >= cut and usage >= cut:
        return "화제·사용 모두"
    if usage >= cut:
        return "조용한 강자"
    if attention >= cut:
        return "반짝 관심"
    return "아직 작은 신호"


@dataclass(frozen=True)
class Share:
    week: str
    backfilled: bool
    shares: dict[str, float]  # 신호 → TOP n 기여분 합에서의 비중(%)


def signal_shares(weeks: Sequence[Mapping[str, Any]], *, top_n: int = 10, n_weeks: int = 12) -> list[Share]:
    out = []
    for w in list(weeks)[-n_weeks:]:
        sums = {s: sum(float(r["contrib"].get(s) or 0.0) for r in _top(w, top_n)) for s in SIGNALS}
        total = sum(sums.values())
        shares = {s: (v / total * 100 if total else 0.0) for s, v in sums.items()}
        out.append(Share(w["week"], _backfilled(w), shares))
    return out


def category_mix(
    weeks: Sequence[Mapping[str, Any]],
    names: Mapping[str, str],
    *,
    top_n: int = 10,
    n_weeks: int = 12,
    keep: int = 5,
) -> tuple[list[str], list[tuple[str, dict[str, int]]]]:
    """(카테고리 이름들 — 창 전체에서 많은 순 keep 개 + 기타, [(주, {이름: 수})])."""
    win = list(weeks)[-n_weeks:]

    def name(r: Mapping[str, Any]) -> str:
        cid = r.get("category") or ""
        return names.get(cid, cid or OTHER)

    total = Counter(name(r) for w in win for r in _top(w, top_n))
    kept = [c for c, _ in total.most_common() if c != OTHER][:keep]
    cats = kept + ([OTHER] if any(c not in kept for c in total) else [])
    rows = []
    for w in win:
        c = Counter(n if n in kept else OTHER for n in (name(r) for r in _top(w, top_n)))
        rows.append((w["week"], {k: c.get(k, 0) for k in cats}))
    return cats, rows


def trend_observations(
    shares: Sequence[Share],
    mix: Sequence[tuple[str, Mapping[str, int]]],
    series: Sequence[Series],
    *,
    top_n: int = 10,
) -> list[str]:
    """ "트렌드 분석" 소제목의 코드 관찰 문장(LLM 이 이 문장들을 풀어 쓴다)."""
    lines: list[str] = []
    if shares:
        first, last = shares[0].shares, shares[-1].shares
        use0, use1 = sum(first[s] for s in USE), sum(last[s] for s in USE)
        att0, att1 = sum(first[s] for s in ATTENTION), sum(last[s] for s in ATTENTION)
        span = len(shares)
        lines.append(
            f"{span}주 동안 TOP {top_n} 기여분에서 사용·기여 비중은 {use0:.0f}% → {use1:.0f}%, "
            f"관심(스타·언급) 비중은 {att0:.0f}% → {att1:.0f}%입니다."
        )
    if series:
        new = sum(1 for s in series if s.new_entry)
        lines.append(f"이번 주 TOP {top_n} 중 {new}개는 4주 전에 TOP {top_n} 밖이었습니다.")
    if mix:
        counts = {k: v for k, v in mix[-1][1].items() if k != OTHER and v}
        if counts:
            cat, n = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
            lines.append(f"이번 주 TOP {top_n} 에 가장 많은 카테고리는 {cat}({n}개)입니다.")
    return lines


def week_trend(
    weeks: Sequence[Mapping[str, Any]], names: Mapping[str, str], *, top_n: int = 10, n_weeks: int = 12
) -> list[str]:
    """12주 트렌드 관찰 문장 — 초안의 "트렌드 분석"(F11)과 그림 단계가 같은 문장을 쓴다."""
    _, mix = category_mix(weeks, names, top_n=top_n, n_weeks=n_weeks)
    return trend_observations(
        signal_shares(weeks, top_n=top_n, n_weeks=n_weeks),
        mix,
        rank_series(weeks, top_n=top_n, n_weeks=n_weeks),
        top_n=top_n,
    )


def repo_card_lines(card: Mapping[str, Any] | None, insights: Sequence[Mapping[str, Any]]) -> list[str]:
    """저장소 카드의 글 — 해설 3줄 요약(빠진 줄은 건너뛴다), 해설이 없으면 코드 관찰 2개."""
    if card:
        s = card.get("summary") or {}
        lines = [str(s[k]["text"]) for k in ("what", "why_now", "watch") if isinstance(s.get(k), Mapping)]
        if lines:
            return lines
    out = []
    for i in list(insights)[:2]:
        big, text = str(i.get("big") or ""), str(i.get("text") or "")
        out.append(f"{big} — {text}" if text else big)
    return out


def repo_ranks(
    weeks: Sequence[Mapping[str, Any]], repo_id: int, *, n_weeks: int = 12
) -> list[tuple[str, int | None]]:
    """저장소 하나의 창 순위 — 저장소 카드(R1)의 12주 미니 추이."""
    return [(w["week"], next((r["rank"] for r in w["rows"] if r["repo_id"] == repo_id), None))
            for w in list(weeks)[-n_weeks:]]
