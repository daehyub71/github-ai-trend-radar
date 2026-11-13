"""T1-5 — S5 언급: HN Algolia + GeekNews `/past?day=` (D12). GeekNews 픽스처는 합성 HTML 이다."""

from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from radar.collectors.mentions import geeknews_index, hn_mentions, parse_past
from tests.fakes import FakeTransport, ok, status
from tests.test_http import _client

W1, W2 = date(2026, 10, 25), date(2026, 11, 1)
PAGE = (Path(__file__).parent / "fixtures" / "geeknews_past.html").read_text(encoding="utf-8")
EMPTY = "<html><body><div class='topics'></div></body></html>"


def test_mentions_hn_counts_exact_repo_urls_by_week():
    nov3 = 1793664000  # 2026-11-03T00:00Z
    # 두 번째는 이름만 비슷한 저장소 — 세지 않는다
    hits = [{"url": "https://github.com/org/tool", "points": 30, "created_at_i": nov3},
            {"url": "https://github.com/org/toolbox", "points": 99, "created_at_i": nov3}]
    t = FakeTransport([("hn.algolia.com", ok({"hits": hits}))])
    c, _ = _client(t)
    got, st = hn_mentions(c, "org/tool", [W1, W2])
    assert st == "ok" and got == {W1: (0, 0), W2: (1, 30)}
    q = parse_qs(urlsplit(t.requests[0][1]).query)
    assert q["restrictSearchableAttributes"] == ["url"] and "created_at_i>=" in q["numericFilters"][0]


def test_mentions_hn_failure():
    c, _ = _client(FakeTransport([("hn.algolia.com", status(503))]))
    assert hn_mentions(c, "org/tool", [W2]) == ({}, "failed")


def test_mentions_parse_past_reads_github_links():
    topics, has_next = parse_past(PAGE)
    assert has_next
    assert [(t.topic_id, t.repo, t.points, t.day) for t in topics] == [
        (9001, "synth-lab/agent-kit", 38, date(2026, 11, 2)),
        (9003, "synth-lab/agent-kit", 5, date(2026, 10, 31)),  # KST 11-01 08:00 = UTC 10-31
    ]


def test_mentions_parse_past_detects_layout_change():
    broken = "<div class='topic_row' data-topic-state-id='1'><div>바뀐 모양</div></div>"
    try:
        parse_past(broken)
    except ValueError as e:
        assert "형식" in str(e)
    else:
        raise AssertionError("형식 변경을 잡아야 한다")


def test_mentions_geeknews_index_buckets_by_week_and_pages():
    def route(url):
        q = parse_qs(urlsplit(url).query)
        if q["day"] == ["2026-11-02"] and q.get("page", ["1"]) == ["1"]:
            return ok(PAGE)
        return ok(EMPTY)

    t = FakeTransport([("news.hada.io/past", route)])
    c, _ = _client(t)
    idx, st, note = geeknews_index(c, [W1, W2])
    assert st == "ok"
    assert idx == {"synth-lab/agent-kit": {W1: (1, 5), W2: (1, 38)}}
    days = {parse_qs(urlsplit(u).query)["day"][0] for u in t.urls("past")}
    assert "2026-10-25" in days and "2026-11-08" in days  # UTC 주 끝을 덮도록 하루 더
    assert any("page=2" in u for u in t.urls())


def test_mentions_geeknews_failed_day_is_partial():
    t = FakeTransport([("day=2026-11-03", status(500)), ("news.hada.io/past", ok(EMPTY))])
    c, _ = _client(t)
    idx, st, note = geeknews_index(c, [W2])
    assert st == "partial" and "2026-11-03" in note


def test_mentions_parse_past_next_page_is_exact():
    assert parse_past(PAGE, page_no=1)[1] is True
    assert parse_past(PAGE, page_no=2)[1] is False  # page=3 이 없다
