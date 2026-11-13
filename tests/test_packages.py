"""T1-4 — S4 사용: 패키지 연결(이름 후보 + 저장소 패키지 파일, D11)·다운로드·의존 수."""

import base64
from datetime import date

from radar.collectors.base import same_repo
from radar.collectors.packages import (
    Package,
    dependents,
    link,
    name_candidates,
    weekly_downloads,
)
from tests.fakes import FakeTransport, ok, status
from tests.test_http import _client

W1, W2 = date(2026, 10, 25), date(2026, 11, 1)


def _content(text: str):
    return ok({"encoding": "base64", "content": base64.b64encode(text.encode()).decode()})


def test_packages_name_candidates():
    assert name_candidates("Org/foo-python", "pypi") == ["foo-python", "foo"]
    assert name_candidates("Org/foo", "npm") == ["foo", "@org/foo"]


def test_packages_same_repo_matching():
    assert same_repo("git+https://github.com/Org/Foo.git", "org/foo")
    assert same_repo("https://github.com/org/foo/tree/main/py", "org/foo")
    assert not same_repo("https://github.com/org/foobar", "org/foo")
    assert not same_repo(None, "org/foo")


def test_packages_link_uses_manifest_names_and_checks_registry_repo():
    t = FakeTransport([
        ("/contents/pyproject.toml", _content('[project]\nname = "Real_Pkg"\n')),
        ("/contents/package.json", _content('{"name": "@org/ui", "private": false}')),
        ("/contents/setup.py", status(404)),
        ("pypi.org/pypi/real-pkg/json", ok({"info": {"project_urls": {"Source": "https://github.com/org/tool"}}})),
        ("pypi.org/pypi/tool/json", ok({"info": {"project_urls": {"Home": "https://github.com/other/tool"}}})),
        ("registry.npmjs.org/@org/ui/latest", ok({"repository": {"url": "git+https://github.com/org/tool.git"}})),
    ])
    c, _ = _client(t)
    r = link(c, "tok", "org/tool")
    assert r.status == "ok"
    assert r.packages == [Package("pypi", "real-pkg"), Package("npm", "@org/ui")]


def test_packages_private_package_json_is_ignored():
    t = FakeTransport([("/contents/package.json", _content('{"name": "app", "private": true}'))])
    c, _ = _client(t)
    assert link(c, "tok", "org/web-ui").packages == []
    assert not any("registry.npmjs.org/app/" in u for u in t.urls())


def test_packages_no_package_is_ok_and_empty():
    c, _ = _client(FakeTransport([]))
    r = link(c, "tok", "org/skill")
    assert r.status == "ok" and r.packages == []


def test_packages_pypi_weekly_downloads():
    data = [{"category": "without_mirrors", "date": "2026-10-26", "downloads": 10},
            {"category": "without_mirrors", "date": "2026-11-02", "downloads": 5},
            {"category": "without_mirrors", "date": "2026-11-03", "downloads": 6},
            {"category": "with_mirrors", "date": "2026-11-03", "downloads": 999}]
    t = FakeTransport([("pypistats.org/api/packages/pkg/overall", ok({"data": data}))])
    c, _ = _client(t)
    got, st = weekly_downloads(c, Package("pypi", "pkg"), [W1, W2])
    assert st == "ok" and got == {W1: 10, W2: 11}


def test_packages_npm_weekly_downloads_and_missing_week():
    days = [{"day": "2026-11-02", "downloads": 3}, {"day": "2026-11-03", "downloads": 4}]
    url = "api.npmjs.org/downloads/range/2026-10-25:2026-11-07/@org/ui"
    t = FakeTransport([(url, ok({"downloads": days}))])
    c, _ = _client(t)
    got, st = weekly_downloads(c, Package("npm", "@org/ui"), [W1, W2])
    assert st == "ok" and got == {W1: None, W2: 7}  # 그 주 날짜가 하나도 없으면 결측


def test_packages_download_failure():
    c, _ = _client(FakeTransport([("pypistats", status(500))]))
    got, st = weekly_downloads(c, Package("pypi", "pkg"), [W2])
    assert st == "failed" and got == {}


def test_packages_dependents_from_ecosystems():
    t = FakeTransport([("registries/pypi.org/packages/pkg", ok({"dependent_packages_count": 12}))])
    c, _ = _client(t)
    assert dependents(c, Package("pypi", "pkg")) == 12
    c2, _ = _client(FakeTransport([]))
    assert dependents(c2, Package("npm", "x")) is None
