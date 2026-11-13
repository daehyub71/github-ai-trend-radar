"""Notion 레이더 DB (SPEC F7·F9, D8, TASKS T5-7·T5-8) — star-trend 의 Notion 연결을 함께 쓴다.

- `Notion-Version: 2026-03-11` 고정(star-trend 와 같음). 본문은 마크다운 API 로 넣는다.
- **상태가 "초안"인 페이지만** 고친다. 검토 중·게시한 페이지, 휴지통·지워진 페이지는 건드리지 않는다.
- 대응표(DB·페이지 ID)는 비공개 저장소 `notion/index.json` 에만 둔다(D7). 토큰은 헤더에만 싣는다.
"""

import json
from collections.abc import Callable, Mapping
from typing import Any

from radar.clients.http import HttpClient

API = "https://api.notion.com"
NOTION_VERSION = "2026-03-11"
KIND = "notion"
DB_TITLE = "깃허브 AI 트렌드 레이더"
STATUS = "상태"
DRAFT = "초안"
STATUS_OPTIONS = (("초안", "gray", "To-do"), ("검토 중", "blue", "In progress"),
                  ("승인", "purple", "In progress"), ("게시됨", "green", "Complete"))
POST_KINDS = ("TOP 10", "관점")


class NotionError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class NotionAPI:
    def __init__(self, client: HttpClient, token: str):
        self._c = client
        self._token = token

    def __repr__(self) -> str:
        return "NotionAPI()"

    def _call(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> dict[str, Any]:
        h = {"Authorization": f"Bearer {self._token}", "Notion-Version": NOTION_VERSION}
        if body is None:
            r = self._c.request(KIND, method, API + path, {"Accept": "application/json", **h})
            try:
                status, data = r.status, (json.loads(r.body) if r.body else {})
            except ValueError:
                status, data = r.status, {}
        else:
            status, data = self._c.send_json(KIND, method, API + path, body, h)
        data = data if isinstance(data, dict) else {}
        if status >= 400:
            code = data.get("code") or ""
            raise NotionError(f"{method} {path.split('?')[0]}: HTTP {status} {code}", status)
        return data

    def create_database(self, parent_page_id: str, title: str, props: Mapping[str, Any]) -> dict[str, str]:
        d = self._call("POST", "/v1/databases", {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "initial_data_source": {"properties": dict(props)}})
        sources = d.get("data_sources") or []
        if not sources or not sources[0].get("id"):
            raise NotionError("데이터베이스 응답에 data_sources 가 없다")
        return {"id": str(d["id"]), "data_source_id": str(sources[0]["id"]), "url": str(d.get("url") or "")}

    def create_page(self, data_source_id: str, props: Mapping[str, Any], markdown: str) -> dict[str, str]:
        parent = {"type": "data_source_id", "data_source_id": data_source_id}
        body = {"parent": parent, "properties": dict(props), "markdown": markdown}
        d = self._call("POST", "/v1/pages", body)
        return {"page_id": str(d["id"]), "url": str(d.get("url") or "")}

    def get_page(self, page_id: str) -> dict[str, Any]:
        return self._call("GET", f"/v1/pages/{page_id}")

    def update_properties(self, page_id: str, props: Mapping[str, Any]) -> None:
        self._call("PATCH", f"/v1/pages/{page_id}", {"properties": dict(props)})

    def replace_markdown(self, page_id: str, markdown: str) -> None:
        self._call("PATCH", f"/v1/pages/{page_id}/markdown", {
            "type": "replace_content",
            "replace_content": {"new_str": markdown, "allow_deleting_content": False}})


def schema() -> dict[str, Any]:
    status = {"type": "status", "status": {"options": [{"name": n, "color": c, "group": g}
                                                       for n, c, g in STATUS_OPTIONS]}}
    return {"제목": {"type": "title", "title": {}}, STATUS: status,
            "글 종류": {"type": "select", "select": {"options": [{"name": k} for k in POST_KINDS]}},
            "주 시작": {"type": "date", "date": {}},
            "회차": {"type": "number", "number": {"format": "number"}},
            "네이버 글 주소": {"type": "url", "url": {}}}


def setup(api: NotionAPI, parent_page_id: str, idx: dict[str, Any]) -> dict[str, Any]:
    """한 번만 — 이미 만들었으면 그대로 둔다(같은 DB 를 둘 만들지 않게)."""
    if idx.get("database"):
        return idx
    idx["parent_page_id"] = parent_page_id
    idx["database"] = api.create_database(parent_page_id, DB_TITLE, schema())
    idx.setdefault("pages", {})
    return idx


def _status(page: Mapping[str, Any]) -> str | None:
    v = (page.get("properties") or {}).get(STATUS)
    s = v.get("status") if isinstance(v, Mapping) else None
    n = s.get("name") if isinstance(s, Mapping) else None
    return n if isinstance(n, str) else None


def props(title: str, kind: str, week: str, issue: int, *, new: bool) -> dict[str, Any]:
    p: dict[str, Any] = {"제목": {"title": [{"type": "text", "text": {"content": title[:2000]}}]},
                         "글 종류": {"select": {"name": kind}}, "주 시작": {"date": {"start": week}},
                         "회차": {"number": issue}}
    if new:
        p[STATUS] = {"status": {"name": DRAFT}}
    return p


def upsert(api: NotionAPI, idx: dict[str, Any], *, week: str, kind: str, issue: int, title: str,
           markdown: str, save: Callable[[], None]) -> str:
    """대응표에 있으면 초안일 때만 고치고, 없으면 만든다. 결과: created·updated·kept:<사유>."""
    if not idx.get("database"):
        raise NotionError("레이더 DB 가 없다 — notion-setup 을 먼저 실행한다")
    pages = idx.setdefault("pages", {})
    key = f"{week}:{kind}"
    known = pages.get(key)
    if known is None:
        ds = idx["database"]["data_source_id"]
        pages[key] = api.create_page(ds, props(title, kind, week, issue, new=True), markdown)
        save()
        return "created"
    try:
        page = api.get_page(known["page_id"])
    except NotionError as e:
        if e.status != 404:
            raise
        return "kept:deleted"
    if page.get("in_trash"):
        return "kept:trash"
    state = _status(page)
    if state != DRAFT:
        return f"kept:{state or 'none'}"
    api.update_properties(known["page_id"], props(title, kind, week, issue, new=False))
    api.replace_markdown(known["page_id"], markdown)
    return "updated"
