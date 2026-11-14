"""저장소 설명 그림 받기 (SPEC F11 · D21 · TASKS T8-10) — GraphQL 메타 · 홈페이지 og:image · 그림 파일.

- repo_meta: 저장소 여럿의 소셜 미리보기(주인이 올린 것만) · 홈페이지 · 라이선스를 GraphQL 한 번에.
- homepage_og: 홈페이지 HTML 한 번 — og:image 주소.
- fetch_image: 그림 파일 — 이미지 형식만(SVG 제외), 5MB 이하. 내용이 진짜 그림인지는 그림 층(Pillow)이 본다.
실패는 None/빈 값으로 돌려준다 — 그림이 없으면 구조도로 넘어가면 된다.
"""

import json
from collections.abc import Mapping, Sequence
from typing import Any

from radar.clients.http import HttpClient
from radar.clients.transport import TransportError
from radar.core.repo_images import og_image
from radar.evidence.base import gh_headers

GRAPHQL = "https://api.github.com/graphql"
MAX_BYTES = 5 * 1024 * 1024
BATCH = 25


def _header(headers: Mapping[str, str], name: str) -> str:
    return next((v for k, v in headers.items() if k.lower() == name.lower()), "")


def repo_meta(client: HttpClient, token: str, names: Sequence[str]) -> dict[str, dict[str, Any]]:
    """{owner/name 소문자: {social, homepage, license}}. 실패한 묶음은 빠진다."""
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(names), BATCH):
        parts = []
        for j, full in enumerate(names[i : i + BATCH]):
            owner, name = full.split("/", 1)
            parts.append(
                f"r{j}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) "
                "{ nameWithOwner usesCustomOpenGraphImage openGraphImageUrl homepageUrl "
                "licenseInfo { spdxId } }"
            )
        try:
            st, body = client.send_json(
                "gh_graphql", "POST", GRAPHQL, {"query": "query {" + " ".join(parts) + "}"}, gh_headers(token)
            )
        except TransportError:
            continue
        if st != 200 or not isinstance(body, dict) or not isinstance(body.get("data"), dict):
            continue
        for r in body["data"].values():
            if not isinstance(r, dict) or not r.get("nameWithOwner"):
                continue
            out[str(r["nameWithOwner"]).lower()] = {
                "social": r.get("openGraphImageUrl") if r.get("usesCustomOpenGraphImage") else None,
                "homepage": r.get("homepageUrl") or None,
                "license": (r.get("licenseInfo") or {}).get("spdxId"),
            }
    return out


def homepage_og(client: HttpClient, homepage: str) -> str | None:
    if not homepage.startswith(("http://", "https://")):
        return None
    try:
        st, page = client.get_text("homepage", homepage, {"Accept": "text/html"})
    except TransportError:
        return None
    return og_image(page[:400_000], homepage) if st == 200 else None


def fetch_image(client: HttpClient, url: str) -> bytes | None:
    try:
        r = client.get("image", url, {"Accept": "image/png,image/jpeg,image/gif,image/webp"})
    except TransportError:
        return None
    ctype = _header(r.headers, "Content-Type").lower()
    if r.status != 200 or not ctype.startswith("image/") or "svg" in ctype or len(r.body) > MAX_BYTES:
        return None
    return r.body
