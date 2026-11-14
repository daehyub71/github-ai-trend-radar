"""GitHub 근거 — README · 그 주 끝까지의 최근 릴리스 (star-trend FR-5.1 방식, PLAN P5).

README 가 없으면(404) 실패가 아니다. 그 밖의 오류는 그 부분만 비우고 problems 에 적는다.
릴리스 근거는 그 주 끝 날까지 나온 최근 5개, 화면의 "이번 주 릴리스"는 그 주 안에 나온 것만.
"""

import base64
import binascii
from datetime import UTC, datetime
from typing import Any

from radar.clients.http import HttpClient
from radar.clients.transport import TransportError
from radar.core import evidence as ev
from radar.evidence.base import GH_API, gh_headers

README_CHARS = 20_000
RELEASES_FETCHED = 10
MAX_RELEASES = 5


def _day(stamp: object) -> str | None:
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(UTC).date().isoformat()
    except ValueError:
        return None


def _readme(body: Any) -> str:
    if not isinstance(body, dict) or not isinstance(body.get("content"), str):
        return ""
    if body.get("encoding") != "base64":
        return str(body["content"])
    try:
        return base64.b64decode(body["content"]).decode("utf-8", errors="replace")
    except (ValueError, binascii.Error):
        return ""


def collect_github(client: HttpClient, token: str,
                   t: ev.Target) -> tuple[list[ev.Evidence], list[dict[str, str]], list[str]]:
    """(근거, 그 주 릴리스 [{tag, date, url}], 문제 목록)."""
    docs: list[ev.Evidence] = []
    problems: list[str] = []
    try:
        st, body = client.get_json("gh_rest", f"{GH_API}/repos/{t.full_name}/readme", gh_headers(token))
    except TransportError as e:
        st, body = 0, None
        problems.append(f"readme {type(e).__name__}")
    else:
        if st not in (200, 404):
            problems.append(f"readme {st}")
    text = _readme(body) if st == 200 else ""
    if text.strip():
        docs.append(ev.make(url=f"https://github.com/{t.full_name}", source="github", kind="readme",
                            title=f"{t.full_name} — README", text=text[:README_CHARS]))
    releases: list[dict[str, str]] = []
    try:
        url = f"{GH_API}/repos/{t.full_name}/releases?per_page={RELEASES_FETCHED}"
        st, body = client.get_json("gh_rest", url, gh_headers(token))
    except TransportError as e:
        problems.append(f"releases {type(e).__name__}")
        return docs, releases, problems
    if st != 200 or not isinstance(body, list):
        problems.append(f"releases {st}")
        return docs, releases, problems
    kept = 0
    for r in body:
        if not isinstance(r, dict) or r.get("draft") or not isinstance(r.get("html_url"), str):
            continue
        day = _day(r.get("published_at"))
        if day is None or day > t.until.isoformat():
            continue
        tag = str(r.get("tag_name") or "")
        if t.since.isoformat() <= day:
            releases.append({"tag": tag, "date": day, "url": r["html_url"]})
        if kept < MAX_RELEASES:
            docs.append(ev.make(url=r["html_url"], source="github", kind="release",
                                title=f"{t.full_name} {r.get('name') or tag}", text=str(r.get("body") or ""),
                                published_at=str(r["published_at"]), extra={"tag": tag}))
            kept += 1
    return docs, releases, problems
