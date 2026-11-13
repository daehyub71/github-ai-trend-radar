"""T2-4 — 12주 소급 (SPEC F5, D10). 네트워크 없이 가짜 전송으로 끝까지 돈다."""

import json
from datetime import UTC, date, datetime

from radar.backfill import plan_backfill, run_backfill
from radar.config import Config
from radar.store import read_csv, week_path
from tests.fakes import FakeTransport, ok
from tests.startrend_fixture import meta, write_tree
from tests.test_http import _client

ANCHOR = date(2026, 11, 1)
W1, W2 = date(2026, 10, 18), date(2026, 10, 25)
NOW = datetime(2026, 11, 13, 3, tzinfo=UTC)


def _cfg(root, cap=2):
    return Config(root, cap, 10, {"s1": 15, "s2": 15, "s3": 25, "s4": 30, "s5": 15}, 1)


def _tree(tmp_path):
    metas = [meta(1, "org/one"), meta(2, "org/two"), meta(3, "org/three"), meta(4, "org/four"),
             meta(9, "x/notai", is_ai=False)]
    return write_tree(tmp_path / "st", metas, {
        "2026-10-18": [(1, "org/one", 500), (2, "org/two", 300), (3, "org/three", 100), (9, "x/notai", 999)],
        # 2 는 이 주 스타 파일에 없다 — 지난주 TOP 보충으로만 들어온다
        "2026-10-25": [(1, "org/one", 50), (3, "org/three", 400), (4, "org/four", 300)],
        "2026-11-01": [(3, "org/three", 10)],
    })


def _transport():
    pr = {"total_count": 2, "items": [
        {"user": {"login": "a", "type": "User"}, "pull_request": {"merged_at": "2026-10-19T00:00:00Z"}},
        {"user": {"login": "b", "type": "User"}, "pull_request": {"merged_at": "2026-10-26T00:00:00Z"}}]}
    return FakeTransport([
        ("repo%3Aorg%2Fone+is%3Apr", ok(pr)),
        ("is%3Apr", ok({"total_count": 0, "items": []})),
        ("is%3Aissue", ok({"total_count": 0, "items": []})),
        ("pypi.org/pypi/one/json", ok({"info": {"project_urls": {"S": "https://github.com/org/one"}}})),
        ("pypistats.org/api/packages/one", ok({"data": [
            {"category": "without_mirrors", "date": "2026-10-20", "downloads": 70},
            {"category": "without_mirrors", "date": "2026-10-27", "downloads": 30}]})),
        ("hn.algolia.com", ok({"hits": []})),
        ("news.hada.io", ok("<html></html>")),
    ])


def test_backfill_plan_counts_union_without_calls(tmp_path):
    root = _tree(tmp_path)
    plan = plan_backfill(_cfg(root), ANCHOR, 2, data=tmp_path / "data")
    assert plan["weeks"] == ["2026-10-18", "2026-10-25"]
    assert plan["repos"] == 4  # 1·2(첫 주) + 3·4(둘째 주), AI 만
    assert plan["uncached_links"] == 4
    assert plan["calls"]["gh_search"] >= 2 * 4
    assert plan["min_minutes"] > 0


def test_backfill_writes_marked_weeks_with_index_and_prev_top(tmp_path):
    root = _tree(tmp_path)
    data, work = tmp_path / "data", tmp_path / "work"
    c, _ = _client(_transport())
    summary = run_backfill(_cfg(root), c, "tok", ANCHOR, 2, data=data, work=work, now=NOW)
    assert summary["weeks"] == ["2026-10-18", "2026-10-25"]

    w1 = {r["full_name"]: r for r in read_csv(week_path("signals", W1, "csv", data))}
    assert set(w1) == {"org/one", "org/two"}
    one = w1["org/one"]
    assert one["backfilled"] == "1"
    # S2 는 소급하지 않는다(D10), 의존 수도 소급 불가
    assert (one["s2_fork_delta"], one["s2_status"], one["s4_dependents"]) == ("", "none", "")
    assert (one["s3_merged_prs"], one["s4_downloads"], one["s4_status"]) == ("1", "70", "ok")

    w2 = {r["full_name"]: r for r in read_csv(week_path("signals", W2, "csv", data))}
    # 3·4 는 스타 상위, 1·2 는 지난주 TOP 에서 빠져 보충 — 2 는 스타 파일에 없어도 이름이 채워진다
    assert {n: r["reason"] for n, r in w2.items()} == {
        "org/three": "gain_top", "org/four": "gain_top", "org/one": "prev_top", "org/two": "prev_top"}
    assert w2["org/two"]["gain_rank"] == ""
    assert (w2["org/one"]["s3_merged_prs"], w2["org/one"]["s4_downloads"]) == ("1", "30")

    for w in (W1, W2):
        idx = json.loads(week_path("index", w, "json", data).read_text(encoding="utf-8"))
        assert all(r["backfilled"] for r in idx["rows"])
        run = json.loads(week_path("runs", w, "json", data).read_text(encoding="utf-8"))
        assert run["backfill"] is True
    # 소급 주에는 포크 스냅샷을 쓰지 않는다
    assert not week_path("meta/forks", W1, "csv", data).exists()
    # 키 값은 어디에도 남지 않는다
    for f in list(data.rglob("*")) + list(work.rglob("*")):
        if f.is_file():
            assert "tok" not in f.read_text(encoding="utf-8").replace("topics", "")


def test_backfill_resumes_from_work_cache_and_skips_written_weeks(tmp_path):
    root = _tree(tmp_path)
    data, work = tmp_path / "data", tmp_path / "work"
    c, _ = _client(_transport())
    run_backfill(_cfg(root), c, "tok", ANCHOR, 2, data=data, work=work, now=NOW)
    t2 = _transport()
    c2, _ = _client(t2)
    again = run_backfill(_cfg(root), c2, "tok", ANCHOR, 2, data=data, work=work, now=NOW)
    assert t2.requests == []  # 저장소 캐시·GeekNews 캐시로 호출 0
    assert again["skipped_weeks"] == ["2026-10-18", "2026-10-25"]
