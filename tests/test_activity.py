"""T1-3 — S3 기여: 머지 PR·고유 작성자·닫힌 이슈, 봇 제외, 12주 한 질의 → 주별 (D5, PLAN §3)."""

from datetime import date
from urllib.parse import parse_qs, urlsplit

from radar.collectors.activity import collect
from tests.fakes import FakeTransport, ok, status
from tests.test_http import _client

W1, W2 = date(2026, 10, 25), date(2026, 11, 1)


def _pr(login, merged, kind="User"):
    return {"user": {"login": login, "type": kind}, "pull_request": {"merged_at": merged},
            "closed_at": merged}


def _issue(login, closed, kind="User"):
    return {"user": {"login": login, "type": kind}, "closed_at": closed}


def _q(url):
    return parse_qs(urlsplit(url).query)["q"][0]


def test_activity_buckets_one_query_by_week_and_excludes_bots():
    prs = [_pr("a", "2026-10-26T01:00:00Z"), _pr("a", "2026-10-27T01:00:00Z"),
           _pr("b", "2026-11-02T01:00:00Z"), _pr("dependabot[bot]", "2026-11-03T01:00:00Z", "Bot"),
           _pr("x", "2026-10-20T01:00:00Z")]  # 창 밖은 버린다
    issues = [_issue("c", "2026-11-04T00:00:00Z"), _issue("renovate[bot]", "2026-11-04T00:00:00Z")]
    t = FakeTransport([("is%3Apr", ok({"total_count": 5, "items": prs})),
                       ("is%3Aissue", ok({"total_count": 2, "items": issues}))])
    c, _ = _client(t)
    r = collect(c, "tok", "o/r", [W1, W2])
    assert r.status == "ok"
    assert (r.weekly[W1].merged_prs, r.weekly[W1].pr_authors, r.weekly[W1].closed_issues) == (2, 1, 0)
    assert (r.weekly[W2].merged_prs, r.weekly[W2].pr_authors, r.weekly[W2].closed_issues) == (1, 1, 1)
    assert len(t.requests) == 2
    assert "merged:2026-10-25..2026-11-07" in _q(t.requests[0][1])


def test_activity_splits_by_week_when_over_1000():
    big = {"total_count": 1500, "items": [_pr("a", "2026-10-26T00:00:00Z")] * 100}

    def route(url):
        q = _q(url)
        if "2026-10-25..2026-11-07" in q:
            return ok(big)
        if "2026-10-25..2026-10-31" in q:
            return ok({"total_count": 1, "items": [_pr("a", "2026-10-26T00:00:00Z")]})
        two = [_pr("b", "2026-11-02T00:00:00Z"), _pr("c", "2026-11-02T00:00:00Z")]
        return ok({"total_count": 2, "items": two})

    t = FakeTransport([("is%3Apr", route), ("is%3Aissue", ok({"total_count": 0, "items": []}))])
    c, _ = _client(t)
    r = collect(c, "tok", "o/r", [W1, W2])
    assert r.status == "ok"
    assert r.weekly[W1].merged_prs == 1 and r.weekly[W2].merged_prs == 2 and r.weekly[W2].pr_authors == 2


def test_activity_single_week_over_1000_is_partial():
    many = {"total_count": 1200, "items": [_pr(f"u{i}", "2026-11-02T00:00:00Z") for i in range(100)]}
    t = FakeTransport([("is%3Apr", ok(many)), ("is%3Aissue", ok({"total_count": 0, "items": []}))])
    c, _ = _client(t)
    r = collect(c, "tok", "o/r", [W2])
    assert r.status == "partial" and "1,000" in r.note
    assert r.weekly[W2].merged_prs == 1000  # 10쪽 × 100 — 받을 수 있는 만큼만


def test_activity_search_failure_is_failed():
    t = FakeTransport([("is%3Apr", status(422))])
    c, _ = _client(t)
    r = collect(c, "tok", "o/r", [W2])
    assert r.status == "failed" and r.weekly == {}


def test_activity_paginates():
    page1 = {"total_count": 150, "items": [_pr("a", "2026-11-02T00:00:00Z")] * 100}
    page2 = {"total_count": 150, "items": [_pr("b", "2026-11-02T00:00:00Z")] * 50}
    t = FakeTransport([("page=2", ok(page2)), ("is%3Apr", ok(page1)),
                       ("is%3Aissue", ok({"total_count": 0, "items": []}))])
    c, _ = _client(t)
    r = collect(c, "tok", "o/r", [W2])
    assert r.weekly[W2].merged_prs == 150 and r.weekly[W2].pr_authors == 2
