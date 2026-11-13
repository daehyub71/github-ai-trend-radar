from datetime import date

import pytest

from radar.core.weeks import parse_week, week_end, week_start, weeks_back


def test_weeks_start_is_sunday():
    assert week_start(date(2026, 11, 1)) == date(2026, 11, 1)   # 일요일
    assert week_start(date(2026, 11, 7)) == date(2026, 11, 1)   # 토요일
    assert week_start(date(2026, 11, 9)) == date(2026, 11, 8)   # 월요일


def test_weeks_end_is_saturday():
    assert week_end(date(2026, 11, 1)) == date(2026, 11, 7)


def test_weeks_back_oldest_first():
    assert weeks_back(date(2026, 11, 1), 3) == [date(2026, 10, 11), date(2026, 10, 18), date(2026, 10, 25)]


def test_weeks_parse_rejects_non_sunday():
    assert parse_week("2026-11-01") == date(2026, 11, 1)
    with pytest.raises(ValueError):
        parse_week("2026-11-02")
