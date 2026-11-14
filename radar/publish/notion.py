"""Notion 레이더 DB (SPEC F7·F9, D8, TASKS T5-7·T5-8) — star-trend 의 Notion 연결을 함께 쓴다.

- `Notion-Version: 2026-03-11` 고정(star-trend 와 같음). 본문은 마크다운 API 로 넣는다.
- **상태가 "초안"인 페이지만** 고친다. 검토 중·게시한 페이지, 휴지통·지워진 페이지는 건드리지 않는다.
- 대응표(DB·페이지 ID)는 비공개 저장소 `notion/index.json` 에만 둔다(D7). 토큰은 헤더에만 싣는다.
- 그림(F11)은 마크다운이 업로드를 못 가리키므로, 그림 줄을 표시 문단으로 바꿔 올린 뒤
  파일 업로드 API(만들기 → multipart 보내기)로 올리고 블록 API 로 표시 문단 뒤에 끼운다
  (star-trend 결정 62 방식).
  같은 그림(내용 해시)은 다시 올리지 않는다.
"""

import hashlib
import json
import re
import secrets
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
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
# 초안 폴더(blog/) 안의 그림만 — 하위 폴더 이름과 파일 이름을 좁혀 폴더 밖을 가리키지 못하게 한다
LOCAL_IMAGE = re.compile(
    r"^!\[([^\]]*)\]\(((?:charts|images|gen)/[A-Za-z0-9_.-]+\.(?:png|jpe?g|webp|gif))\)$"
)
IMAGE_MARK = "⟦그림 {}⟧"
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
               ".gif": "image/gif"}
UPLOAD_MAX = 20 * 1024 * 1024  # 한 번에 보내는 파일 업로드 한도


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

    def _call(self, method: str, path: str, body: Mapping[str, Any] | None = None, *,
              raw: tuple[bytes, str] | None = None) -> dict[str, Any]:
        h = {"Authorization": f"Bearer {self._token}", "Notion-Version": NOTION_VERSION}
        if body is None:
            extra = {"Content-Type": raw[1]} if raw else {}
            r = self._c.request(KIND, method, API + path, {"Accept": "application/json", **h, **extra},
                                raw[0] if raw else None)
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

    def list_children(self, block_id: str) -> list[tuple[str, str, str]]:
        """(블록 ID, 종류, 글) — 페이지 바로 아래 블록."""
        out: list[tuple[str, str, str]] = []
        cursor: str | None = None
        while True:
            q = "?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
            d = self._call("GET", f"/v1/blocks/{block_id}/children{q}")
            for b in d.get("results") or []:
                kind = str(b.get("type") or "")
                rich = (b.get(kind) or {}).get("rich_text") or []
                out.append((str(b["id"]), kind, "".join(str(x.get("plain_text", "")) for x in rich)))
            if not d.get("has_more") or not d.get("next_cursor"):
                return out
            cursor = str(d["next_cursor"])

    def upload_file(self, filename: str, data: bytes, content_type: str) -> str:
        """작은 파일(20MB 이하) 올리기 — 만들기 → 보내기. 1시간 안에 블록에 붙여야 한다."""
        d = self._call("POST", "/v1/file_uploads", {"filename": filename, "content_type": content_type})
        fid = str(d.get("id") or "")
        if not fid:
            raise NotionError(f"파일 업로드 응답에 id 가 없다: {filename}")
        boundary = secrets.token_hex(16)
        name = filename.replace('"', "")
        head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
                f"Content-Type: {content_type}\r\n\r\n")
        body = head.encode() + data + f"\r\n--{boundary}--\r\n".encode()
        r = self._call("POST", f"/v1/file_uploads/{fid}/send",
                       raw=(body, f"multipart/form-data; boundary={boundary}"))
        if r.get("status") != "uploaded":
            raise NotionError(f"파일 올리기 상태가 {r.get('status')}: {filename}")
        return fid

    def insert_image(self, parent_id: str, after_block_id: str, file_upload_id: str, caption: str) -> None:
        cap = [{"type": "text", "text": {"content": caption[:2000]}}] if caption else []
        image = {"type": "file_upload", "file_upload": {"id": file_upload_id}, "caption": cap}
        self._call("PATCH", f"/v1/blocks/{parent_id}/children", {
            "children": [{"type": "image", "image": image}],
            "position": {"type": "after_block", "after_block": {"id": after_block_id}}})

    def delete_block(self, block_id: str) -> None:
        self._call("DELETE", f"/v1/blocks/{block_id}")


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


def local_images(markdown: str, base_dir: Path) -> tuple[str, list[tuple[str, str, Path]]]:
    """그림 줄 → 표시 문단. (보낼 마크다운, [(표시, 캡션, 파일)]). 파일이 없거나 너무 크면 줄을 뺀다."""
    lines: list[str] = []
    found: list[tuple[str, str, Path]] = []
    for line in markdown.split("\n"):
        m = LOCAL_IMAGE.match(line.strip())
        if not m:
            lines.append(line)
            continue
        path = base_dir / m.group(2)
        if not path.is_file() or path.stat().st_size > UPLOAD_MAX:
            continue
        mark = IMAGE_MARK.format(len(found) + 1)
        lines.append(mark)
        found.append((mark, m.group(1), path))
    return "\n".join(lines), found


def attach_images(api: NotionAPI, idx: dict[str, Any], page_id: str, found: Sequence[tuple[str, str, Path]],
                  *, save: Callable[[], None]) -> int:
    """표시 문단 뒤에 그림 블록을 끼우고 표시 문단을 지운다. 끼운 그림 수."""
    blocks = {text.strip(): bid for bid, kind, text in api.list_children(page_id) if kind == "paragraph"}
    uploads: dict[str, str] = idx.setdefault("uploads", {})
    n = 0
    for mark, caption, path in found:
        bid = blocks.get(mark)
        if bid is None:
            continue
        data = path.read_bytes()
        key = hashlib.sha256(data).hexdigest()
        up = uploads.get(key)
        if up is not None:
            try:
                api.insert_image(page_id, bid, up, caption)
            except NotionError as e:
                if e.status not in (400, 404):
                    raise
                up = None  # 붙이지 못한 채 만료된 업로드 — 다시 올린다
        if up is None:
            up = api.upload_file(path.name, data, IMAGE_TYPES[path.suffix.lower()])
            api.insert_image(page_id, bid, up, caption)
        uploads[key] = up
        save()
        api.delete_block(bid)
        n += 1
    return n
