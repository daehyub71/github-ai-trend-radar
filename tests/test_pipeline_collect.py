"""T1-6·T1-7 — 주간 수집 순서·상태 기록·저장 (SPEC F1·F3). 네트워크 없이 가짜 전송으로 끝까지 돈다."""

import json
from datetime import UTC, date, datetime

import pytest

from radar.config import Config
from radar.pipeline import SIGNAL_FIELDS, collect_week, plan_week
from radar.store import WriteOnceError, read_csv
from tests.fakes import FakeTransport, ok, status
from tests.startrend_fixture import meta, write_tree
from tests.test_http import _client

WEEK = date(2026, 11, 1)
NOW = datetime(2026, 11, 9, 9, 5, tzinfo=UTC)


def _cfg(root, cap=10):
    return Config(root, cap, 10, {"s1": 15, "s2": 15, "s3": 25, "s4": 30, "s5": 15}, 1)


def _tree(tmp_path):
    return write_tree(tmp_path / "st",
                      [meta(1, "org/tool"), meta(2, "org/skill"), meta(3, "x/plain", is_ai=False)],
                      {"2026-11-01": [(1, "org/tool", 500), (2, "org/skill", 300), (3, "x/plain", 900)],
                       "2026-11-08": [(1, "org/tool", 200), (2, "org/skill", 100)]})


def _transport():
    pr = {"total_count": 1, "items": [{"user": {"login": "a", "type": "User"},
                                       "pull_request": {"merged_at": "2026-11-02T00:00:00Z"}}]}
    return FakeTransport([
        ("/repositories/1", ok({"full_name": "org/tool", "forks_count": 40, "stargazers_count": 1})),
        ("/repositories/2", status(404)),
        ("repo%3Aorg%2Ftool+is%3Apr", ok(pr)),
        ("is%3Apr", ok({"total_count": 0, "items": []})),
        ("is%3Aissue", ok({"total_count": 0, "items": []})),
        ("pypi.org/pypi/tool/json", ok({"info": {"project_urls": {"S": "https://github.com/org/tool"}}})),
        ("pypistats.org/api/packages/tool", ok({"data": [
            {"category": "without_mirrors", "date": "2026-11-03", "downloads": 70}]})),
        ("registries/pypi.org/packages/tool", ok({"dependent_packages_count": 4})),
        ("hn.algolia.com", ok({"hits": []})),
        ("news.hada.io", ok("<html></html>")),
    ])


def test_pipeline_collect_writes_signals_and_run_record(tmp_path):
    root = _tree(tmp_path)
    c, _ = _client(_transport())
    rec = collect_week(_cfg(root), c, "tok", WEEK, data=tmp_path / "data", now=NOW)
    rows = {r["full_name"]: r for r in read_csv(tmp_path / "data" / "signals" / "2026-11-01.csv")}
    assert set(rows) == {"org/tool", "org/skill"}  # AI 만
    t = rows["org/tool"]
    # 첫 스냅샷이라 포크 증가는 결측
    assert (t["s1_stars_gain"], t["s2_forks"], t["s2_fork_delta"]) == ("500", "40", "")
    got = (t["s3_merged_prs"], t["s3_pr_authors"], t["s4_downloads"], t["s4_dependents"])
    assert got == ("1", "1", "70", "4")
    assert t["s4_packages"] == "pypi:tool" and t["backfilled"] == "0"
    s = rows["org/skill"]
    # 패키지 없음 = 결측(0 이 아니다)
    assert s["s2_status"] == "failed" and s["s4_packages"] == "" and s["s4_downloads"] == ""
    assert rec["sources"]["s2"] == {"ok": 1, "partial": 0, "failed": 1}
    assert rec["status"] == "partial"
    run = json.loads((tmp_path / "data" / "runs" / "2026-11-01.json").read_text())
    assert run["calls"]["gh_rest"] >= 2 and "tok" not in json.dumps(run)
    assert list(read_csv(tmp_path / "data" / "signals" / "2026-11-01.csv")[0]) == list(SIGNAL_FIELDS)


def test_pipeline_collect_refuses_to_overwrite_a_week(tmp_path):
    root = _tree(tmp_path)
    c, _ = _client(_transport())
    collect_week(_cfg(root), c, "tok", WEEK, data=tmp_path / "data", now=NOW)
    c2, _ = _client(_transport())
    with pytest.raises(WriteOnceError):
        collect_week(_cfg(root), c2, "tok", WEEK, data=tmp_path / "data", now=NOW)


def test_pipeline_package_links_are_cached(tmp_path):
    root = _tree(tmp_path)
    t = _transport()
    c, _ = _client(t)
    collect_week(_cfg(root), c, "tok", WEEK, data=tmp_path / "data", now=NOW)
    cache = json.loads((tmp_path / "data" / "meta" / "packages.json").read_text())
    assert cache["1"]["packages"] == [["pypi", "tool"]] and cache["2"]["packages"] == []
    t2 = _transport()
    c2, _ = _client(t2)
    collect_week(_cfg(root), c2, "tok", date(2026, 11, 8), data=tmp_path / "data",
                 now=datetime(2026, 11, 16, 9, tzinfo=UTC))
    assert not t2.urls("/contents/")  # 4주 안에는 다시 찾지 않는다


def test_pipeline_plan_estimates_calls(tmp_path):
    p = plan_week(_cfg(_tree(tmp_path)), WEEK, data=tmp_path / "data")
    assert p["candidates"] == 2 and p["calls"]["gh_search"] >= 4 and p["uncached_links"] == 2


def test_pipeline_fork_delta_from_weekly_snapshots(tmp_path):
    root = _tree(tmp_path)
    c, _ = _client(_transport())
    collect_week(_cfg(root), c, "tok", WEEK, data=tmp_path / "data", now=NOW)
    t = _transport()
    t.routes.insert(0, ("/repositories/1", ok({"full_name": "org/tool", "forks_count": 55})))
    c2, _ = _client(t)
    collect_week(_cfg(root), c2, "tok", date(2026, 11, 8), data=tmp_path / "data",
                 now=datetime(2026, 11, 16, 9, tzinfo=UTC))
    rows = {r["full_name"]: r for r in read_csv(tmp_path / "data" / "signals" / "2026-11-08.csv")}
    assert rows["org/tool"]["s2_fork_delta"] == "15"
