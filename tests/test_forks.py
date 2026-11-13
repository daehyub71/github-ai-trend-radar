"""T1-2 — S2 포크: 저장소 메타 스냅샷 (D10 — 소급 없음)."""

from radar.collectors.base import RepoRef
from radar.collectors.forks import snapshot
from radar.core.signals import fork_delta
from tests.fakes import FakeTransport, ok, status
from tests.test_http import _client


def test_forks_snapshot_by_id_follows_renames():
    t = FakeTransport([("/repositories/1", ok({"full_name": "new/name", "forks_count": 42,
                                               "stargazers_count": 900, "archived": False}))])
    c, _ = _client(t)
    [s] = snapshot(c, "tok", [RepoRef(1, "old/name")])
    assert (s.full_name, s.forks, s.stars, s.status) == ("new/name", 42, 900, "ok")
    assert t.requests[0][2]["Authorization"] == "Bearer tok"


def test_forks_missing_repo_is_failed_not_zero():
    t = FakeTransport([("/repositories/2", status(404))])
    c, _ = _client(t)
    [s] = snapshot(c, "tok", [RepoRef(2, "gone/repo")])
    assert s.status == "failed" and s.forks is None and "404" in s.note


def test_forks_changed_shape_is_failed():
    t = FakeTransport([("/repositories/3", ok({"full_name": "a/b"}))])
    c, _ = _client(t)
    [s] = snapshot(c, "tok", [RepoRef(3, "a/b")])
    assert s.status == "failed" and "forks_count" in s.note


def test_signals_fork_delta_needs_previous_snapshot():
    assert fork_delta({1: 100, 2: 50}, {1: 130, 2: 40, 3: 9}) == {1: 30, 2: -10, 3: None}
