import pytest

from radar.core.index import compute, rank

W = {"s1": 15, "s2": 15, "s3": 25, "s4": 30, "s5": 15}


def test_index_weighted_average_all_present():
    rows = compute({"s1": {1: 100.0}, "s2": {1: 100.0}, "s3": {1: 0.0}, "s4": {1: 0.0}, "s5": {1: 100.0}}, W)
    r = rows[1]
    assert r.index == pytest.approx(45.0)
    assert r.missing == ()


def test_index_missing_signal_weight_is_redistributed():
    # S2·S4 없음 → 남은 15+25+15=55 로 다시 나눈다
    rows = compute({"s1": {1: 100.0}, "s2": {1: None}, "s3": {1: 50.0}, "s4": {1: None}, "s5": {1: 0.0}}, W)
    r = rows[1]
    assert r.index == pytest.approx((15 * 100 + 25 * 50) / 55)
    assert r.missing == ("s2", "s4")


def test_index_contributions_sum_to_index():
    rows = compute({"s1": {1: 80.0}, "s2": {1: None}, "s3": {1: 40.0}, "s4": {1: 10.0}, "s5": {1: 60.0}}, W)
    r = rows[1]
    assert sum(r.contrib.values()) == pytest.approx(r.index)
    assert r.contrib["s2"] == 0.0
    assert r.contrib["s4"] == pytest.approx(30 * 10.0 / 85)


def test_index_no_signal_at_all_is_none():
    rows = compute({"s1": {1: None}}, W)
    assert rows[1].index is None
    assert set(rows[1].missing) == set(W)


def test_index_repo_absent_from_a_signal_counts_as_missing():
    rows = compute({"s1": {1: 50.0, 2: 70.0}, "s3": {1: 20.0}}, W)
    assert "s3" in rows[2].missing
    assert rows[2].index == pytest.approx(70.0)


def test_index_rank_desc_with_deterministic_tiebreak():
    rows = compute({"s1": {1: 50.0, 2: 50.0, 3: 90.0, 4: None}}, W)
    # 같은 지수는 스타 증가 순위(작을수록 앞)로, 지수 없음은 맨 뒤
    order = rank(rows, {1: 7, 2: 3, 3: 9, 4: 1})
    assert order == [3, 2, 1, 4]


def _row(rid, **kw):
    base = {"repo_id": str(rid), "s1_stars_gain": "", "s2_fork_delta": "", "s2_status": "ok",
            "s3_merged_prs": "", "s3_pr_authors": "", "s3_closed_issues": "", "s3_status": "ok",
            "s4_downloads": "", "s4_dependents": "", "s4_status": "none",
            "s5_hn_stories": "", "s5_hn_points": "", "s5_gn_topics": "", "s5_gn_points": "",
            "s5_status": "ok"}
    base.update({k: str(v) for k, v in kw.items()})
    return base


def test_index_signal_percentiles_from_signal_rows():
    from radar.core.index import signal_percentiles

    rows = [
        _row(1, s1_stars_gain=900, s3_merged_prs=10, s3_pr_authors=3, s3_closed_issues=0,
             s4_downloads=500, s4_dependents=0, s4_status="ok",
             s5_hn_stories=1, s5_hn_points=40, s5_gn_topics=0, s5_gn_points=0),
        _row(2, s1_stars_gain=300, s3_merged_prs=0, s3_pr_authors=0, s3_closed_issues=5,
             s5_hn_stories=0, s5_hn_points=0, s5_gn_topics=1, s5_gn_points=3),
        _row(3, s1_stars_gain=600, s2_fork_delta=4, s3_status="failed",
             s4_downloads=50, s4_dependents=2, s4_status="ok",
             s5_hn_stories=0, s5_hn_points=0, s5_gn_topics=0, s5_gn_points=0),
    ]
    p = signal_percentiles(rows)
    assert p["s1"] == {1: 100.0, 2: 0.0, 3: 50.0}
    # 포크 증가는 하나뿐 → 100, 나머지 결측
    assert p["s2"] == {1: None, 2: None, 3: 100.0}
    # S3: 세 값 각 백분위 평균(D5), 실패는 결측
    assert p["s3"][1] == pytest.approx((100 + 100 + 0) / 3)
    assert p["s3"][2] == pytest.approx((0 + 0 + 100) / 3)
    assert p["s3"][3] is None
    # S4: 패키지 없음(none)은 결측 — 다운로드·의존 수 평균
    assert p["s4"][2] is None
    assert p["s4"][1] == pytest.approx((100 + 0) / 2)
    assert p["s4"][3] == pytest.approx((0 + 100) / 2)
    # S5: HN+GeekNews 합 글 수·점수 백분위 평균
    # 글 수는 1·2 가 1건으로 동점 → 둘 다 75
    assert p["s5"][1] == pytest.approx((75 + 100) / 2)
    assert p["s5"][2] == pytest.approx((75 + 50) / 2)
    assert p["s5"][3] == pytest.approx(0.0)


def test_index_signal_percentiles_failed_s2_and_s5_are_missing():
    from radar.core.index import signal_percentiles

    rows = [_row(1, s1_stars_gain=5, s2_fork_delta=3, s2_status="failed", s5_status="failed",
                 s5_hn_stories=2, s5_hn_points=9)]
    p = signal_percentiles(rows)
    assert p["s2"][1] is None and p["s5"][1] is None
