"""T8-3 — 차트 데이터 (SPEC F11, D18·D19). 그리기 전 숫자를 코드가 정한다 — 순수 함수, 네트워크 0."""

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Any

from radar.core.charts_data import (
    category_mix,
    contribution_bars,
    quadrant,
    rank_series,
    repo_card_lines,
    repo_ranks,
    signal_map,
    signal_shares,
    trend_observations,
    week_trend,
)

END = date(2026, 11, 1)
SIG = ("s1", "s2", "s3", "s4", "s5")


def _row(
    rid: int,
    rank: int,
    *,
    cat: str = "agent",
    pct: dict[str, float | None] | None = None,
    contrib: dict[str, float] | None = None,
    bf: bool = False,
) -> dict[str, Any]:
    pct = pct or {"s1": 50.0, "s2": None, "s3": 50.0, "s4": None, "s5": 50.0}
    contrib = contrib or {"s1": 10.0, "s2": 0.0, "s3": 20.0, "s4": 0.0, "s5": 5.0}
    return {
        "repo_id": rid,
        "full_name": f"o/r{rid}",
        "rank": rank,
        "category": cat,
        "index": sum(contrib.values()),
        "pct": pct,
        "contrib": contrib,
        "missing": [s for s in SIG if pct.get(s) is None],
        "backfilled": bf,
    }


def _weeks(
    n: int, ranks: Mapping[int, Sequence[int | None]], cats: Mapping[int, str] | None = None
) -> list[dict[str, Any]]:
    """ranks: {repo_id: [n 주 순위, None 이면 후보 밖]} — 오래된 주부터."""
    out = []
    for i in range(n):
        wk = (END - timedelta(weeks=n - 1 - i)).isoformat()
        rows: list[dict[str, Any]] = []
        for rid, r in ranks.items():
            rank = r[i]
            if rank is not None:
                rows.append(_row(rid, rank, cat=(cats or {}).get(rid, "agent"), bf=i < n - 1))
        rows.sort(key=lambda x: int(x["rank"]))
        out.append({"week": wk, "rows": rows})
    return out


def test_rank_series_top_now_across_window_with_gaps():
    weeks = _weeks(
        13,
        {
            1: [None] * 12 + [1],
            2: [30, 25, 20, 18, 15, 12, 11, 9, 8, 6, 4, 3, 2],
            3: [3] * 13,
            4: [1] * 12 + [40],
        },
    )
    got = rank_series(weeks, top_n=3, n_weeks=12)
    assert [s.full_name for s in got] == ["o/r1", "o/r2", "o/r3"]  # 이번 주 순위 차례
    assert len(got[0].points) == 12 and got[0].points[0] == ("2026-08-16", None, True)
    assert got[0].points[-1] == ("2026-11-01", 1, False)
    assert [p[1] for p in got[1].points][:3] == [25, 20, 18]  # 12주 창 — 첫 주(30위)는 빠진다
    assert got[0].new_entry and not got[2].new_entry  # 4주 전 TOP 3 밖에서 들어왔나


def test_contribution_bars_keep_order_and_missing():
    weeks = _weeks(1, {7: [2], 8: [1]})
    bars = contribution_bars(weeks[-1], top_n=10)
    assert [b.rank for b in bars] == [1, 2] and bars[0].full_name == "o/r8"
    assert bars[0].contrib["s3"] == 20.0 and bars[0].missing == ("s2", "s4") and bars[0].index == 35.0


def test_signal_map_points_marks_and_quadrants():
    week = {
        "week": "2026-11-01",
        "rows": [
            _row(1, 1, pct={"s1": 90.0, "s2": None, "s3": 80.0, "s4": 70.0, "s5": 70.0}),
            _row(2, 30, pct={"s1": 20.0, "s2": None, "s3": 90.0, "s4": 95.0, "s5": 10.0}),
            _row(3, 50, pct={"s1": None, "s2": None, "s3": None, "s4": None, "s5": None}),
        ],
    }
    angles = {"A": {"items": [{"repo_id": 2}]}, "B": {"items": []}, "C": {"items": []}, "D": {"items": []}}
    pts = {p.repo_id: p for p in signal_map(week, angles, top_n=10)}
    assert 3 not in pts  # 값이 하나도 없으면 점을 찍지 않는다
    assert (pts[1].attention, pts[1].usage, pts[1].mark) == (80.0, 75.0, "1")
    assert (pts[2].attention, pts[2].usage, pts[2].mark) == (15.0, 92.5, "A")
    assert quadrant(80.0, 75.0) == "화제·사용 모두" and quadrant(15.0, 92.5) == "조용한 강자"
    assert quadrant(90.0, 20.0) == "반짝 관심" and quadrant(10.0, 10.0) == "아직 작은 신호"


def test_signal_shares_and_category_mix():
    weeks = _weeks(2, {1: [1, 1], 2: [2, 2], 3: [3, None]}, cats={1: "agent", 2: "agent", 3: "mcp"})
    shares = signal_shares(weeks, top_n=10, n_weeks=12)
    assert [s.week for s in shares] == ["2026-10-25", "2026-11-01"] and shares[0].backfilled
    assert round(sum(shares[0].shares.values()), 6) == 100.0
    assert round(shares[0].shares["s3"], 2) == round(60 / 105 * 100, 2)
    names = {"agent": "에이전트", "mcp": "MCP"}
    cats, rows = category_mix(weeks, names, top_n=10, n_weeks=12, keep=1)
    assert cats == ["에이전트", "기타"]
    assert rows == [("2026-10-25", {"에이전트": 2, "기타": 1}), ("2026-11-01", {"에이전트": 2, "기타": 0})]


def test_trend_observations_sentences():
    weeks = _weeks(13, {1: [None] * 12 + [1], 2: [2] * 13, 3: [3] * 13})
    shares = signal_shares(weeks, top_n=3, n_weeks=12)
    cats, rows = category_mix(weeks, {"agent": "에이전트"}, top_n=3, n_weeks=12, keep=5)
    lines = trend_observations(shares, rows, rank_series(weeks, top_n=3, n_weeks=12), top_n=3)
    assert lines[0].startswith("12주 동안 TOP 3 기여분에서 사용·기여 비중은 ")
    assert "이번 주 TOP 3 중 1개는 4주 전에 TOP 3 밖이었습니다." in lines
    assert "이번 주 TOP 3 에 가장 많은 카테고리는 에이전트(3개)입니다." in lines
    # 초안(F11 트렌드 분석)과 그림 단계가 같은 문장을 쓴다
    assert week_trend(weeks, {"agent": "에이전트"}, top_n=3, n_weeks=12) == lines


def test_repo_card_lines_from_commentary_or_observations():
    card = {"summary": {"what": {"text": "무엇"}, "why_now": {"text": "왜"}, "watch": None}}
    assert repo_card_lines(card, []) == ["무엇", "왜"]
    ins = [
        {"big": "스타 1개당 다운로드 1,660회", "text": "후보 47개 중 6위."},
        {"big": "PR 작성자 22명", "text": ""},
        {"big": "셋째", "text": "x"},
    ]
    assert repo_card_lines(None, ins) == ["스타 1개당 다운로드 1,660회 — 후보 47개 중 6위.", "PR 작성자 22명"]


def test_repo_ranks_for_any_repo():
    weeks = _weeks(13, {5: [None, *range(40, 28, -1)]})
    got = repo_ranks(weeks, 5, n_weeks=12)
    assert len(got) == 12 and got[0] == ("2026-08-16", 40) and got[-1] == ("2026-11-01", 29)
    assert repo_ranks(weeks, 99, n_weeks=12)[0] == ("2026-08-16", None)
