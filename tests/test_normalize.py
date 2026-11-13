import pytest

from radar.core.normalize import combine, percentiles


def test_normalize_rank_percentile_0_to_100():
    p = percentiles({1: 10, 2: 1000, 3: 100})
    assert p == {1: 0.0, 3: 50.0, 2: 100.0}


def test_normalize_ties_take_mid_rank():
    # 0 이 셋 — 순위 1·2·3 의 가운데(2) → 백분위 (2-1)/(4-1)*100
    p = percentiles({1: 0, 2: 0, 3: 0, 4: 5})
    assert p[1] == p[2] == p[3] == pytest.approx(100 / 3)
    assert p[4] == 100.0


def test_normalize_missing_stays_missing_and_is_not_ranked():
    p = percentiles({1: None, 2: 3, 3: 7})
    assert p == {1: None, 2: 0.0, 3: 100.0}


def test_normalize_single_or_empty():
    assert percentiles({1: 4}) == {1: 100.0}
    assert percentiles({1: None}) == {1: None}
    assert percentiles({}) == {}


def test_normalize_negative_values_rank_below_zero():
    # 포크 증가는 음수일 수 있다(삭제·비공개 전환)
    p = percentiles({1: -2, 2: 0, 3: 9})
    assert p == {1: 0.0, 2: 50.0, 3: 100.0}


def test_normalize_log_does_not_change_rank():
    import math

    raw = {1: 3, 2: 90000, 3: 41, 4: 41}
    logged = {k: math.log1p(v) for k, v in raw.items()}
    assert percentiles(raw) == percentiles(logged)


def test_normalize_same_input_same_output_regardless_of_order():
    a = percentiles({3: 5, 1: 5, 2: 1})
    b = percentiles({1: 5, 2: 1, 3: 5})
    assert a == b


def test_normalize_combine_averages_available_parts():
    merged = {1: 100.0, 2: 0.0, 3: None}
    authors = {1: 50.0, 2: None, 3: None}
    issues = {1: 0.0, 2: 30.0, 3: None}
    c = combine([merged, authors, issues])
    assert c[1] == pytest.approx(50.0)
    assert c[2] == pytest.approx(15.0)
    assert c[3] is None
