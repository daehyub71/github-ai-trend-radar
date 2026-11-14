"""S4 사용 — 패키지 연결·주간 다운로드·의존 수 (TASKS T1-4, SPEC D11, PLAN P2).

- 이름 후보: 저장소 패키지 파일(pyproject.toml·setup.py·package.json, 루트만)의 이름
  + 저장소 이름에서 만든 후보.
- 레지스트리(PyPI JSON·npm latest)에 적힌 저장소 URL 이 이 저장소일 때만 연결한다
  — 이름만 같은 남의 패키지를 막는다.
- 다운로드: pypistats(without_mirrors 일별) · npm downloads range. 그 주 날짜가 하나도 없으면 결측(None).
- 의존 수: ecosyste.ms 의 dependent_packages_count (CC BY-SA 4.0 — 화면·글에 출처를 적는다).
"""

import base64
import json
import re
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from urllib.parse import quote

from radar.clients.http import HttpClient
from radar.collectors.base import FAILED, GH_API, OK, gh_headers, same_repo
from radar.core.weeks import week_end, week_start

ECOSYSTEMS = ("pypi", "npm")
ATTRIBUTION = "ecosyste.ms (CC BY-SA 4.0)"
_SUFFIXES = ("-python", "-py", ".py", "-js", ".js", "-node", "-ts", "-sdk", "-cli")
_PREFIXES = ("python-", "py-", "node-", "js-")
_SETUP_NAME = re.compile(r"""\bname\s*=\s*['"]([A-Za-z0-9._\-]+)['"]""")
# 안내용 자리표시·이전 패키지 — 연결하지 않고, 설명에 적힌 npm 패키지가 이 저장소면
# 그쪽을 연결한다(2026-11-14)
_POINTER = re.compile(
    r"(?i)\b(pointer to|moved to|has moved|renamed to|deprecated in favou?r of|use \S+ instead)\b"
)
_NPM_SCOPED = re.compile(r"@[a-z0-9][a-z0-9._~-]*/[a-z0-9][a-z0-9._~-]*")


@dataclass(frozen=True)
class Package:
    ecosystem: str  # "pypi" | "npm"
    name: str


@dataclass
class LinkResult:
    full_name: str
    packages: list[Package] = field(default_factory=list)
    status: str = OK
    note: str = ""


def _pypi_norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def name_candidates(full_name: str, ecosystem: str) -> list[str]:
    owner, repo = full_name.lower().split("/", 1)
    names = [repo] + [repo[: -len(s)] for s in _SUFFIXES if repo.endswith(s)]
    names += [repo[len(p):] for p in _PREFIXES if repo.startswith(p)]
    if ecosystem == "npm":
        names.append(f"@{owner}/{repo}")
    return list(dict.fromkeys(n for n in names if n))


def _file(client: HttpClient, token: str, full_name: str, path: str) -> str | None:
    st, body = client.get_json("gh_rest", f"{GH_API}/repos/{full_name}/contents/{path}", gh_headers(token))
    if st != 200 or not isinstance(body, dict) or body.get("encoding") != "base64":
        return None
    try:
        return base64.b64decode(str(body.get("content", ""))).decode("utf-8", errors="replace")
    except ValueError:
        return None


def manifest_names(client: HttpClient, token: str, full_name: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"pypi": [], "npm": []}
    text = _file(client, token, full_name, "pyproject.toml")
    if text:
        try:
            d: Any = tomllib.loads(text)
            poetry = (d.get("tool") or {}).get("poetry") or {}
            name = (d.get("project") or {}).get("name") or poetry.get("name")
            if isinstance(name, str):
                out["pypi"].append(name)
        except tomllib.TOMLDecodeError:
            pass
    text = _file(client, token, full_name, "setup.py")
    if text and (m := _SETUP_NAME.search(text)):
        out["pypi"].append(m.group(1))
    text = _file(client, token, full_name, "package.json")
    if text:
        try:
            pj = json.loads(text)
            if isinstance(pj, dict) and isinstance(pj.get("name"), str) and not pj.get("private"):
                out["npm"].append(pj["name"])
        except ValueError:
            pass
    return out


def _registry(client: HttpClient, eco: str, name: str) -> tuple[list[object], str, bool] | None:
    """레지스트리에 적힌 (URL 들, 설명, 폐기 여부). 패키지가 없으면 None."""
    if eco == "pypi":
        st, body = client.get_json("pypi", f"https://pypi.org/pypi/{quote(name)}/json")
        if st != 200 or not isinstance(body, dict):
            return None
        info = body.get("info") or {}
        urls = list((info.get("project_urls") or {}).values())
        return urls + [info.get("home_page"), info.get("download_url")], str(info.get("summary") or ""), False
    st, body = client.get_json("npm_registry", f"https://registry.npmjs.org/{quote(name, safe='@/')}/latest")
    if st != 200 or not isinstance(body, dict):
        return None
    repo = body.get("repository")
    urls = [repo.get("url") if isinstance(repo, dict) else repo, body.get("homepage"),
            (body.get("bugs") or {}).get("url") if isinstance(body.get("bugs"), dict) else None]
    return urls, str(body.get("description") or ""), bool(body.get("deprecated"))


def _verified(client: HttpClient, eco: str, name: str, full_name: str, *,
              follow: bool = True) -> Package | None:
    """레지스트리 저장소 URL 이 이 저장소인 패키지(D11). 자리표시·폐기 패키지는 빼고, 설명이 가리키는
    npm 패키지를 한 번만 따라간다 — 그 패키지도 이 저장소여야 한다."""
    reg = _registry(client, eco, name)
    if reg is None:
        return None
    urls, desc, deprecated = reg
    if not any(same_repo(u, full_name) for u in urls):
        return None
    if not deprecated and not _POINTER.search(desc):
        return Package(eco, name)
    target = _NPM_SCOPED.search(desc.lower()) if eco == "npm" and follow else None
    if target and target.group(0) != name:
        return _verified(client, eco, target.group(0), full_name, follow=False)
    return None


def link(client: HttpClient, token: str, full_name: str) -> LinkResult:
    res = LinkResult(full_name)
    manifest = manifest_names(client, token, full_name)
    for eco in ECOSYSTEMS:
        names = manifest[eco] + name_candidates(full_name, eco)
        if eco == "pypi":
            names = [_pypi_norm(n) for n in names]
        for name in dict.fromkeys(names):
            pkg = _verified(client, eco, name, full_name)
            if pkg is not None and pkg not in res.packages:
                res.packages.append(pkg)
    return res


def weekly_downloads(client: HttpClient, pkg: Package,
                     weeks: Sequence[date]) -> tuple[dict[date, int | None], str]:
    """({주: 다운로드 또는 None}, 상태). 실패하면 ({}, failed)."""
    since, until = weeks[0], week_end(weeks[-1])
    days: dict[date, int] = {}
    if pkg.ecosystem == "pypi":
        st, body = client.get_json("pypistats", f"https://pypistats.org/api/packages/{quote(pkg.name)}"
                                   "/overall?mirrors=false")
        if st != 200 or not isinstance(body, dict) or not isinstance(body.get("data"), list):
            return {}, FAILED
        for x in body["data"]:
            if isinstance(x, dict) and x.get("category") == "without_mirrors":
                days[date.fromisoformat(str(x["date"]))] = int(x.get("downloads") or 0)
    else:
        url = (f"https://api.npmjs.org/downloads/range/{since.isoformat()}:{until.isoformat()}/"
               + quote(pkg.name, safe="@/"))
        st, body = client.get_json("npm", url)
        if st != 200 or not isinstance(body, dict) or not isinstance(body.get("downloads"), list):
            return {}, FAILED
        for x in body["downloads"]:
            if isinstance(x, dict):
                days[date.fromisoformat(str(x["day"]))] = int(x.get("downloads") or 0)
    out: dict[date, int | None] = {}
    for w in weeks:
        vals = [n for d, n in days.items() if week_start(d) == w]
        out[w] = sum(vals) if vals else None
    return out, OK


def dependents(client: HttpClient, pkg: Package) -> int | None:
    reg = "pypi.org" if pkg.ecosystem == "pypi" else "npmjs.org"
    st, body = client.get_json("ecosystems", f"https://packages.ecosyste.ms/api/v1/registries/{reg}/packages/"
                               + quote(pkg.name, safe=""))
    if st != 200 or not isinstance(body, dict):
        return None
    n = body.get("dependent_packages_count")
    return n if isinstance(n, int) else None



