"""T7-4 — 코드 관찰 I1~I7 (SPEC F10-1). 숫자만으로 내는 문장, 데이터가 없으면 내지 않는다."""

from datetime import date, timedelta

from radar.core.insights import RULES_V1, WeekPoint, mention_counts, observe, trend_rows

CUR = date(2026, 11, 1)

# remotion-dev/remotion 12주 실제 값(시안 v2 기준) — (주, 순위, 스타, 다운로드, PR 작성자, HN 글, HN 점수)
REMOTION = [
    ("2026-08-16", 31, 689, 1693953, 8, 0, 0),
    ("2026-08-23", 37, 635, 1668831, 5, 0, 0),
    ("2026-08-30", 26, 721, 1808453, 5, 0, 0),
    ("2026-09-06", 38, 660, 1288255, 8, 0, 0),
    ("2026-09-13", 34, 764, 1549382, 9, 0, 0),
    ("2026-09-20", 12, 859, 1856188, 10, 1, 1),
    ("2026-09-27", 17, 1138, 2152396, 9, 0, 0),
    ("2026-10-04", 22, 1419, 2143918, 18, 0, 0),
    ("2026-10-11", 22, 1756, 1859251, 15, 0, 0),
    ("2026-10-18", 11, 2413, 2050419, 18, 0, 0),
    ("2026-10-25", 10, 2369, 3529761, 14, 0, 0),
    ("2026-11-01", 6, 2110, 3501735, 22, 0, 0),
]


def _remotion() -> list[WeekPoint]:
    out = []
    for wk, rank, stars, dl, auth, hs, hp in REMOTION:
        cur = wk == "2026-11-01"
        out.append(WeekPoint(week=wk, rank=rank, stars=stars, downloads=dl, pr_authors=auth,
                             hn_stories=hs, hn_points=hp, gn_topics=0, gn_points=0,
                             forks=6091 if cur else None, dependents=50 if cur else None))
    return out


def _pop(n_better: int, n_worse: int) -> list[WeekPoint]:
    """이번 주 후보 — 다운로드/스타 비가 remotion(약 1,660)보다 큰 것 n_better, 작은 것 n_worse."""
    pts = [WeekPoint(week="2026-11-01", stars=10, downloads=10 * 5000) for _ in range(n_better)]
    pts += [WeekPoint(week="2026-11-01", stars=10, downloads=10 * 100) for _ in range(n_worse)]
    return pts


def _by_id(items):
    return {i.id: i for i in items}


def test_insights_remotion_matches_design_v2():
    pts = _remotion()
    got = _by_id(observe(pts, _pop(5, 41) + [pts[-1]], RULES_V1))
    assert got["I1"].big == "스타 1개당 다운로드 1,660회"
    assert got["I1"].text == "패키지가 있는 후보 47개 중 6위 — 관심보다 실제 사용이 앞선 저장소입니다."
    assert got["I2"].big == "4주 평균의 1.46배"
    assert got["I2"].text == "12주 첫 주(08-16, 1,693,953)의 2.07배. 10-25 주에 한 번에 72% 늘었습니다."
    assert got["I3"].big == "누적 포크 6,091"
    assert "스냅샷" in got["I3"].text
    assert got["I4"].big == "PR 작성자 22명"
    assert got["I4"].text == "4주 전 18명, 12주 첫 주 8명 — 기여하는 사람이 늘고 있습니다."
    assert got["I5"].big == "12주 HN 1건 · 1점"
    assert got["I5"].text == "언급 점수 합이 10 미만 — 커뮤니티 화제보다 사용으로 오른 저장소입니다."
    assert got["I6"].big == "의존 패키지 50개"
    assert got["I7"].big == "10위 → 6위"
    assert got["I7"].text == "12주 최고 6위(이번 주), 최저 38위(09-06 주)."
    assert [i.id for i in observe(pts, [pts[-1]], RULES_V1)] == ["I1", "I2", "I3", "I4", "I5", "I6", "I7"]


def test_insights_skip_when_data_missing():
    only = [WeekPoint(week="2026-11-01", rank=3, stars=100, hn_stories=0, hn_points=0)]
    got = _by_id(observe(only, only, RULES_V1))
    # 다운로드·포크·PR 작성자·의존이 없으면 I1·I2·I3·I4·I6 은 없다. 순위는 처음 들어온 주
    assert set(got) == {"I5", "I7"}
    assert got["I7"].big == "3위 (처음)"
    assert got["I5"].text == "언급 점수 합이 10 미만 — 커뮤니티 화제가 거의 없었습니다."
    # 언급을 수집하지 못한 주(값 없음)에는 "화제가 없었다"고 말하지 않는다
    blind = [WeekPoint(week="2026-11-01", rank=3)]
    assert set(_by_id(observe(blind, blind, RULES_V1))) == {"I7"}


def test_insights_i1_zero_stars_skipped_and_low_ratio_suffix():
    p = WeekPoint(week="2026-11-01", stars=0, downloads=500)
    assert "I1" not in _by_id(observe([p], [p], RULES_V1))
    low = WeekPoint(week="2026-11-01", stars=100, downloads=100)
    got = _by_id(observe([low], _pop(9, 0) + [low], RULES_V1))
    assert got["I1"].text == "패키지가 있는 후보 10개 중 10위 — 다운로드에 비해 관심이 큰 저장소입니다."


def test_insights_i2_needs_two_prior_weeks_and_no_jump_sentence_below_threshold():
    def pts(vals):
        return [WeekPoint(week=(CUR - timedelta(weeks=len(vals) - 1 - i)).isoformat(), downloads=v)
                for i, v in enumerate(vals)]

    assert "I2" not in _by_id(observe(pts([100, 120]), [], RULES_V1))
    got = _by_id(observe(pts([100, 110, 120]), [], RULES_V1))["I2"]
    assert got.big == "4주 평균의 1.14배" and got.text == ""


def test_insights_i3_fork_ratio_top_share():
    me = WeekPoint(week="2026-11-01", stars=100, forks=900, fork_delta=20)
    pop = [WeekPoint(week="2026-11-01", stars=100, fork_delta=1) for _ in range(9)] + [me]
    got = _by_id(observe([me], pop, RULES_V1))["I3"]
    assert got.big == "스타 100개당 포크 20.0개"
    assert got.text == "포크 증가가 있는 후보 10개 중 1위 — 직접 고쳐 쓰려는 수요가 큰 편입니다."


def test_insights_i5_single_post_dominates_and_busy_week():
    cc = WeekPoint(week="2026-11-01", hn_stories=1, hn_points=1615, gn_topics=1, gn_points=2)
    got = _by_id(observe([cc], [cc], RULES_V1))["I5"]
    assert got.big == "언급 점수의 99.9%가 글 하나"
    assert got.text == "글 하나가 이번 주 언급 신호를 만들었습니다."
    two = WeekPoint(week="2026-11-01", hn_stories=2, hn_points=50, gn_topics=1, gn_points=30)
    got = _by_id(observe([two], [two], RULES_V1))["I5"]
    assert got.big == "이번 주 글 3건 · 80점"
    assert got.text == "Hacker News 2건(50점) · GeekNews 1건(30점)."


def test_insights_i5_quiet_week_after_buzz():
    old = WeekPoint(week="2026-10-25", hn_stories=3, hn_points=300)
    now = WeekPoint(week="2026-11-01", hn_stories=0, hn_points=0, gn_topics=0, gn_points=0)
    got = _by_id(observe([old, now], [now], RULES_V1))["I5"]
    assert got.big == "이번 주 언급 0건"
    assert got.text == "2주 동안 글 3건 · 300점 — 이번 주는 조용했습니다."


def test_insights_i4_shrinking_and_i7_best_in_past():
    w = [WeekPoint(week=(CUR - timedelta(weeks=4 - i)).isoformat(), rank=r, pr_authors=a)
         for i, (r, a) in enumerate([(2, 30), (5, 20), (8, 15), (9, 12), (12, 10)])]
    got = _by_id(observe(w, [w[-1]], RULES_V1))
    # 첫 주가 곧 4주 전이면 한 번만 쓴다
    assert got["I4"].text == "4주 전 30명 — 기여하는 사람이 줄었습니다."
    assert got["I7"].big == "9위 → 12위"
    assert got["I7"].text == "5주 최고 2위(10-04 주), 최저 12위(이번 주)."


def test_insights_dict_shape_for_site():
    pts = _remotion()
    d = observe(pts, [pts[-1]], RULES_V1)[0].as_dict()
    assert set(d) == {"id", "title", "big", "text", "signal"} and d["signal"] == "s4"


IDX = [68.02, 65.5, 67.21, 65.45, 67.94, 78.66, 74.02, 72.05, 71.8, 74.94, 76.96, 78.09]
PRS = [176, 122, 85, 98, 113, 141, 135, 150, 127, 178, 106, 104]
ISS = [88, 63, 45, 47, 69, 50, 69, 97, 42, 24, 131, 56]


def test_trend_rows_remotion_matches_design_v2():
    pts = [WeekPoint(**{**p.__dict__, "index": i, "merged_prs": m, "closed_issues": c})
           for p, i, m, c in zip(_remotion(), IDX, PRS, ISS, strict=True)]
    rows = {r["key"]: (r["prev"], r["now"], r["avg"]) for r in trend_rows(pts)}
    assert rows == {
        "종합 순위": ("10위", "6위", "16위"),
        "지수": ("77.0", "78.1", "73.9"),
        "스타 증가": ("2,369", "2,110", "1,989"),
        "주간 다운로드": ("3,529,761", "3,501,735", "2,395,837"),
        "머지 PR": ("106", "104", "140"),
        "PR 작성자": ("14", "22", "16"),
        "닫힌 이슈": ("131", "56", "74"),
        "HN·GeekNews 글": ("0", "0", "0"),
        "포크 (누적)": ("—", "6,091", "—"),
    }
    assert [r["key"] for r in trend_rows(pts)][:2] == ["종합 순위", "지수"]


def test_trend_rows_skip_signals_without_value_this_week():
    only = [WeekPoint(week="2026-11-01", rank=4, index=80.0, stars=10)]
    assert [r["key"] for r in trend_rows(only)] == ["종합 순위", "지수", "스타 증가"]
    assert trend_rows(only)[0] == {"key": "종합 순위", "prev": "—", "now": "4위", "avg": "—"}


def test_mention_counts_week_and_window():
    got = mention_counts(_remotion(), RULES_V1)
    assert got == {"week": {"hn_stories": 0, "hn_points": 0, "gn_topics": 0, "gn_points": 0},
                   "window": {"weeks": 12, "hn_stories": 1, "hn_points": 1, "gn_topics": 0, "gn_points": 0}}
    assert mention_counts([WeekPoint(week="2026-11-01")], RULES_V1) is None
