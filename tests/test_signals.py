from datetime import datetime

from radar.core.signals import fork_delta_checked


def test_signals_fork_delta_only_for_weekly_gap():
    a = datetime(2026, 11, 9, 9)
    b = datetime(2026, 11, 16, 9, 30)
    assert fork_delta_checked({1: 10}, a, {1: 15, 2: 3}, b) == ({1: 5, 2: None}, "")
    d, note = fork_delta_checked({1: 10}, datetime(2026, 11, 13), {1: 15}, b)
    assert d == {1: None} and "3일" in note
    assert fork_delta_checked({}, None, {1: 15}, b) == ({1: None}, "지난 스냅샷 없음")
