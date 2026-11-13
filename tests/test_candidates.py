from radar.core.candidates import select_candidates
from radar.core.models import StarRow


def _rows(*items: tuple[int, str, int]) -> list[StarRow]:
    return [StarRow(id=i, full_name=n, gain=g, stars_end=1000 + g, exact=False) for i, n, g in items]


def test_candidates_keeps_only_ai_and_sorts_by_gain():
    rows = _rows((1, "a/x", 50), (2, "b/y", 900), (3, "c/z", 300))
    got = select_candidates(rows, ai_ids={1, 2}, previous_top=[], cap=10)
    assert [c.full_name for c in got] == ["b/y", "a/x"]
    assert [c.gain_rank for c in got] == [1, 2]
    assert {c.reason for c in got} == {"gain_top"}


def test_candidates_cap_and_deterministic_ties():
    rows = _rows((3, "c/c", 10), (1, "A/a", 10), (2, "b/b", 10))
    got = select_candidates(rows, ai_ids={1, 2, 3}, previous_top=[], cap=2)
    # 동점은 이름(소문자) 순 — 같은 입력이면 같은 결과
    assert [c.full_name for c in got] == ["A/a", "b/b"]


def test_candidates_adds_previous_top_outside_cap():
    rows = _rows((1, "a/a", 100), (2, "b/b", 90), (3, "c/c", 5))
    got = select_candidates(rows, ai_ids={1, 2, 3, 4}, previous_top=[3, 4, 1], cap=2)
    by = {c.id: c for c in got}
    assert by[3].reason == "prev_top" and by[3].gain_rank == 3 and by[3].gain == 5
    # 이번 주 스타 파일에 없는(증가 < 10) 지난주 TOP 은 gain 0, 순위 없음
    assert by[4].reason == "prev_top" and by[4].gain_rank is None and by[4].gain == 0
    assert by[1].reason == "gain_top"
    assert len(got) == 4


def test_candidates_previous_top_must_still_be_ai():
    rows = _rows((1, "a/a", 100), (2, "b/b", 90))
    got = select_candidates(rows, ai_ids={1}, previous_top=[2], cap=5)
    assert [c.id for c in got] == [1]
