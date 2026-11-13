"""T1-1 — 재시도·한도 대기·요청 간격·호출 집계 (PLAN §3)."""

from radar.clients.http import HttpClient, Policy
from radar.clients.transport import TransportError
from tests.fakes import FakeTransport, ok, status


def _client(t, now=1000.0, **policies):
    clock = {"t": now}
    slept: list[float] = []

    def sleep(s: float) -> None:
        slept.append(s)
        clock["t"] += s

    c = HttpClient(t, sleep=sleep, clock=lambda: clock["t"], policies=policies)
    return c, slept


def test_http_returns_json_and_counts_calls():
    t = FakeTransport([("/a", ok({"x": 1}))])
    c, _ = _client(t)
    st, body = c.get_json("gh_rest", "https://h/a")
    assert (st, body) == (200, {"x": 1})
    assert c.calls == {"gh_rest": 1}


def test_http_retries_5xx_then_succeeds():
    t = FakeTransport([("/a", [status(502), status(503), ok({"ok": True})])])
    c, slept = _client(t)
    assert c.get_json("k", "https://h/a") == (200, {"ok": True})
    assert len(t.requests) == 3 and len(slept) == 2


def test_http_gives_up_after_max_attempts():
    t = FakeTransport([("/a", status(500))])
    c, _ = _client(t, k=Policy(attempts=3))
    st, body = c.get_json("k", "https://h/a")
    assert st == 500 and body is None and len(t.requests) == 3


def test_http_waits_for_github_rate_limit_reset():
    reset = {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1060"}
    t = FakeTransport([("/a", [status(403, reset), ok([])])])
    c, slept = _client(t, now=1000.0)
    assert c.get_json("k", "https://h/a") == (200, [])
    assert slept[0] == 61  # reset 까지 + 1초


def test_http_honors_retry_after():
    t = FakeTransport([("/a", [status(429, {"retry-after": "7"}), ok({})])])
    c, slept = _client(t)
    c.get_json("k", "https://h/a")
    assert slept[0] == 7


def test_http_404_is_an_answer_not_a_retry():
    t = FakeTransport([("/a", status(404))])
    c, _ = _client(t)
    assert c.get_json("k", "https://h/a") == (404, None)
    assert len(t.requests) == 1


def test_http_transport_error_is_retried_then_raised():
    t = FakeTransport([("/a", TransportError("boom"))])
    c, _ = _client(t, k=Policy(attempts=2))
    try:
        c.get_json("k", "https://h/a")
    except TransportError:
        pass
    else:
        raise AssertionError("TransportError 가 나와야 한다")
    assert len(t.requests) == 2


def test_http_spaces_requests_per_kind():
    t = FakeTransport([("/a", ok({}))])
    c, slept = _client(t, search=Policy(min_interval=2.0))
    c.get_json("search", "https://h/a")
    c.get_json("search", "https://h/a")
    c.get_json("other", "https://h/a")
    assert slept == [2.0]


def test_http_bad_json_is_none_body():
    t = FakeTransport([("/a", ok("<html>"))])
    c, _ = _client(t)
    assert c.get_json("k", "https://h/a") == (200, None)


def test_http_get_text_and_headers_never_logged():
    t = FakeTransport([("/a", ok("hello"))])
    c, _ = _client(t)
    assert c.get_text("k", "https://h/a", {"Authorization": "Bearer secret"}) == (200, "hello")
    assert "secret" not in repr(c.calls)
