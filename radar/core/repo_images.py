"""저장소 설명 그림 후보 (SPEC F11 · D21 · TASKS T8-10) — 순수 함수. 받기·확인은 다른 층이 한다.

우선순위(앞이 이긴다): README 그림(허용형 라이선스만) → 주인이 올린 소셜 미리보기 →
홈페이지 og:image → 웹 이미지 검색.
사람이 만든 일러스트(gen/)와 구조도 자동 생성은 그림 단계가 이 앞뒤에 붙인다.
그림마다 출처(source)와 저작권 상태(rights)를 남긴다 — "확인 필요"는 게시 전에 사람이 본다.
"""

import html
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

PERMISSIVE = {
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "Unlicense",
    "0BSD",
    "CC0-1.0",
    "CC-BY-4.0",
    "Zlib",
}
_MD_IMG = re.compile(r"!\[[^\]]*\]\(\s*<?([^\s)>]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)")
_HTML_IMG = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)
_BADGE = re.compile(
    r"shields\.io|badgen\.net|/badge\.svg|badge|codecov\.io|travis-ci|circleci|"
    r"img\.shields|buymeacoffee|ko-fi|star-history|api\.star-history",
    re.I,
)
_BLOB = re.compile(r"^https?://github\.com/([^/]+)/([^/]+)/(?:blob|raw)/([^/]+)/(.+)$", re.I)
_META = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR = re.compile(r"""(\w[\w:-]*)\s*=\s*["']([^"']*)["']""")


@dataclass(frozen=True)
class Candidate:
    url: str
    kind: str  # readme · social · homepage · web
    source: str  # 그림 아래에 적을 출처 — 저장소·홈페이지 주소 또는 웹 사이트 이름
    rights: str  # 저작권 상태 — 라이선스 · 공개용 · 확인 필요


def permissive(license_id: str | None) -> bool:
    return bool(license_id) and license_id in PERMISSIVE


def _resolve(url: str, full_name: str) -> str | None:
    u = html.unescape(url.strip())
    if u.startswith(("http://", "https://")):
        m = _BLOB.match(u)
        if m:
            path = m.group(4).split("?", 1)[0]
            return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}/{path}"
        return u
    if ":" in u.split("/", 1)[0] or u.startswith(("#", "//")):
        return None  # javascript:·data:·조각 등
    path = u.split("?", 1)[0].removeprefix("./").lstrip("/")
    return f"https://raw.githubusercontent.com/{full_name}/HEAD/{path}" if path else None


def readme_images(readme: str, full_name: str) -> list[str]:
    """README 안 그림 주소 — 나온 순서, 배지·SVG·중복 제외."""
    found: list[tuple[int, str]] = [(m.start(), m.group(1)) for m in _MD_IMG.finditer(readme)]
    found += [(m.start(), m.group(1)) for m in _HTML_IMG.finditer(readme)]
    out: list[str] = []
    for _, raw in sorted(found):
        if _BADGE.search(raw):
            continue
        url = _resolve(raw, full_name)
        if url is None or urlsplit(url).path.lower().endswith(".svg") or url in out:
            continue
        out.append(url)
    return out


def og_image(page: str, base_url: str) -> str | None:
    """홈페이지 대표 이미지 — og:image, 없으면 twitter:image. 상대 주소는 base_url 기준."""
    metas = [dict((k.lower(), v) for k, v in _ATTR.findall(m.group(0))) for m in _META.finditer(page)]
    for key in ("og:image", "og:image:url", "twitter:image"):
        for a in metas:
            if (a.get("property") or a.get("name") or "").lower() == key and a.get("content"):
                url = urljoin(base_url, html.unescape(a["content"].strip()))
                return url if url.startswith(("http://", "https://")) else None
    return None


def rank_candidates(
    *,
    readme: Sequence[str],
    license_id: str | None,
    social: str | None,
    homepage_og: str | None,
    homepage: str | None,
    web: Sequence[Mapping[str, str]],
    full_name: str,
) -> list[Candidate]:
    repo = f"https://github.com/{full_name}"
    out: list[Candidate] = []
    if permissive(license_id):
        out += [Candidate(u, "readme", repo, f"라이선스 {license_id}") for u in readme[:5]]
    if social:
        out.append(Candidate(social, "social", repo, "공개용(소셜 미리보기)"))
    if homepage_og and homepage:
        out.append(Candidate(homepage_og, "homepage", homepage, "공개용(홈페이지 대표 이미지)"))
    for w in list(web)[:3]:
        url = w.get("url") or ""
        if url.startswith(("http://", "https://")):
            out.append(Candidate(url, "web", urlsplit(url).hostname or "", "확인 필요(웹 검색)"))
    return out


def explanatory(width: int, height: int) -> bool:
    """설명이 되는 그림인가 — 앱 아이콘(작은 정사각형)과 가는 배너는 빼고 다음 후보로 넘어간다."""
    if width < 480 or height < 200:
        return False
    ratio = width / height
    if not 0.5 <= ratio <= 3.2:
        return False
    return not (abs(width - height) <= width * 0.1 and width < 800)
