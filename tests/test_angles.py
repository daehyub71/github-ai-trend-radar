"""T2-8 — 관점 유형 A~D 선정 (SPEC F9). 경계값·중복 우선순위·5개 상한·이력 부족."""

from radar.core.angles import RULES_V1, AngleRules, select_angles


def _row(rid, s1=50.0, s2=None, s3=50.0, s4=None, s5=50.0, index=50.0, contrib=None):
    pct = {"s1": s1, "s2": s2, "s3": s3, "s4": s4, "s5": s5}
    return {"repo_id": rid, "full_name": f"o/r{rid}", "index": index, "pct": pct,
            "contrib": contrib or {"s1": 10.0, "s2": 0.0, "s3": 20.0, "s4": 0.0, "s5": 20.0}}


def _week(rows):
    return {"rows": rows}


def test_angles_a_quiet_strong_boundaries():
    rows = [_row(1, s1=49.9, s3=80.0, s4=80.0),   # 경계 안
            _row(2, s1=50.0, s3=90.0, s4=90.0),   # 스타 50 은 아니다
            _row(3, s1=10.0, s3=79.0, s4=80.0),   # 평균 79.5
            _row(4, s1=10.0, s2=90.0, s3=80.0)]   # S4 없으면 S2·S3
    out = select_angles([_week(rows)])
    assert [x["repo_id"] for x in out["A"]["items"]] == [4, 1]


def test_angles_b_flash_interest_needs_low_usage():
    rows = [_row(1, s1=95.0, s3=10.0, s4=20.0), _row(2, s1=50.0, s5=90.0, s3=30.0),
            _row(3, s1=99.0, s3=31.0), _row(4, s1=99.0, s3=None)]  # 4: 포크·기여·사용 모두 없음 → 판단 불가
    out = select_angles([_week(rows)])
    assert [x["repo_id"] for x in out["B"]["items"]] == [1, 2]


def test_angles_c_d_need_five_weeks_else_insufficient():
    out = select_angles([_week([_row(1)])] * 4)
    assert out["C"]["status"] == "insufficient" and out["C"]["items"] == []
    assert out["D"]["status"] == "insufficient"
    assert out["A"]["status"] == "ok"


def test_angles_c_steady_rise_four_consecutive():
    weeks = [_week([_row(1, index=v), _row(2, index=w)])
             for v, w in ((10, 10), (20, 30), (30, 25), (40, 40), (50, 60))]
    out = select_angles(weeks)
    assert [x["repo_id"] for x in out["C"]["items"]] == [1]
    assert out["C"]["items"][0]["evidence"]["index"] == [10, 20, 30, 40, 50]


def test_angles_c_requires_presence_every_week():
    weeks = [_week([_row(1, index=v)]) for v in (10, 20, 30, 40)] + [_week([_row(1, index=50), _row(2)])]
    weeks[2] = _week([])
    assert select_angles(weeks)["C"]["items"] == []


def test_angles_d_signal_shift():
    then = {"s1": 30.0, "s2": 0.0, "s3": 10.0, "s4": 0.0, "s5": 10.0}   # 관심 80%, 사용·기여 20%
    now = {"s1": 15.0, "s2": 0.0, "s3": 25.0, "s4": 5.0, "s5": 5.0}     # 관심 40%, 사용·기여 60%
    small = {"s1": 25.0, "s2": 0.0, "s3": 15.0, "s4": 0.0, "s5": 10.0}  # +10%p
    weeks = [_week([_row(1, contrib=then), _row(2, contrib=then)])] + [_week([_row(1), _row(2)])] * 3
    weeks.append(_week([_row(1, contrib=now), _row(2, contrib=small)]))
    out = select_angles(weeks)
    assert [x["repo_id"] for x in out["D"]["items"]] == [1]
    ev = out["D"]["items"][0]["evidence"]
    assert ev["use_share"] == [20.0, 60.0] and ev["attention_share"] == [80.0, 40.0]


def test_angles_overlap_priority_and_cap():
    # 1 은 A·C 둘 다 → C 에 들어가고 A 에서 빠진다
    weeks = [_week([_row(1, s1=10.0, s3=90.0, s4=90.0, index=v)]) for v in (10, 20, 30, 40, 50)]
    out = select_angles(weeks)
    assert [x["repo_id"] for x in out["C"]["items"]] == [1]
    assert out["A"]["items"] == []
    many = [_row(i, s1=10.0, s3=80.0 + i, s4=90.0) for i in range(1, 9)]
    a = select_angles([_week(many)])["A"]["items"]
    assert [x["repo_id"] for x in a] == [8, 7, 6, 5, 4]  # 넉넉히 넘는 순, 5개


def test_angles_rules_are_configurable_and_versioned():
    rules = AngleRules(**{**RULES_V1.__dict__, "a_use_min": 95.0, "version": 2})
    out = select_angles([_week([_row(1, s1=10.0, s3=90.0, s4=90.0)])], rules)
    assert out["A"]["items"] == [] and out["rules_version"] == 2
