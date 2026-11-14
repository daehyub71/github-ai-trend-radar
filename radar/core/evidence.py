"""해설 근거 (SPEC F10-2 · TASKS T7-5) — star-trend `core/evidence.py` 를 옮겨 줄였다(PLAN P5).

근거 목록이 해설 게이트의 기준이다. 해설은 근거 번호(E1…)로만 출처를 달고,
화면의 링크는 이 목록의 URL 만 쓴다.
URL 은 정규화한 형태로 비교한다(대소문자·www·끝 슬래시·추적 파라미터·조각). 원문(text)은 프롬프트에만 쓰고
사이트 사본에는 제목(120자)·사이트·날짜·URL 만 남긴다.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

EXCERPT_CHARS = 300
TITLE_MAX = 120
_DROP_PARAMS = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid")
_PATH_SAFE = "/:@!$&'()*+,;=-._~"
_CASELESS_PATH_HOSTS = ("github.com",)
_GITHUB_REPO = re.compile(r"^(?:git\+)?https?://(?:www\.)?github\.com/([^/?#]+)/([^/?#]+)", re.I)


def normalize_url(raw: str) -> str | None:
    """웹 링크(http·https, 또는 www. 로 시작)를 비교용 형태로. 그 밖(javascript:·상대 경로 등)은 None."""
    s = raw.strip()
    if s.lower().startswith("www."):
        s = "https://" + s
    try:
        parts = urlsplit(s)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    netloc = host if port in (None, 80, 443) else f"{host}:{port}"
    if parts.username is not None:  # 사용자 정보는 지우지 않는다 — 다른 호스트로 보이게 하는 속임수
        netloc = f"{parts.username}@{netloc}"
    path = quote(unquote(parts.path), safe=_PATH_SAFE).rstrip("/")
    if host in _CASELESS_PATH_HOSTS:
        segs = path.split("/")
        path = "/".join(x.lower() if i <= 2 else x for i, x in enumerate(segs))
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                             if not k.lower().startswith(_DROP_PARAMS)))
    return urlunsplit(("https", netloc, path, query, ""))


def github_repo(url: str) -> str | None:
    """github.com/<owner>/<repo>(하위 경로 포함)를 가리키면 소문자 "owner/repo". 아니면 None."""
    m = _GITHUB_REPO.match(url.strip())
    if not m:
        return None
    repo = re.sub(r"(?i)\.git$", "", m.group(2))
    return f"{m.group(1)}/{repo}".lower()


def host(url: str) -> str:
    """화면에 보일 사이트 이름 — 정규화한 호스트(www 없음)."""
    key = normalize_url(url) or ""
    return key.split("/")[2].rsplit("@", 1)[-1] if key.count("/") >= 2 else ""


def short_title(title: str) -> str:
    t = re.sub(r"\s+", " ", title).strip()
    return t if len(t) <= TITLE_MAX else t[: TITLE_MAX - 1] + "…"


def target_label(url: str | None, full_name: str) -> str:
    """HN·GeekNews 글이 가리킨 곳 — 저장소 자신·이슈·PR·릴리스·파일 등. 저장소 밖이면 사이트 이름."""
    if not url:
        return "글"
    if github_repo(url) != full_name.lower():
        return host(url) or "외부 페이지"
    rest = (normalize_url(url) or "").split("/")[5:]
    if not rest or rest == [""]:
        return "저장소"
    kind = rest[0]
    num = rest[1] if len(rest) > 1 and rest[1].isdigit() else ""
    if kind == "issues" and num:
        return f"저장소 이슈 #{num}"
    if kind == "pull" and num:
        return f"저장소 PR #{num}"
    if kind == "releases":
        return "릴리스"
    if kind in ("blob", "tree"):
        return "저장소 파일"
    return "저장소 하위 페이지"


@dataclass(frozen=True)
class Evidence:
    url: str  # 쓰여 있던 그대로 — 비교는 key 로
    source: str  # github · hn · geeknews · web
    kind: str  # readme · release · story · comment · topic · search
    title: str
    excerpt: str
    published_at: str | None = None  # ISO 날짜 또는 시각
    extra: Mapping[str, Any] = field(default_factory=dict)
    text: str = field(default="", repr=False)  # 원문 — 프롬프트에만

    @property
    def key(self) -> str:
        k = normalize_url(self.url)
        assert k is not None  # make 가 검사했다
        return k

    @property
    def day(self) -> date | None:
        try:
            return date.fromisoformat((self.published_at or "")[:10])
        except ValueError:
            return None

    def record(self, *, with_text: bool = False) -> dict[str, Any]:
        rec = {"url": self.url, "source": self.source, "kind": self.kind, "title": self.title,
               "excerpt": self.excerpt, "published_at": self.published_at, "extra": dict(self.extra)}
        return rec | ({"text": self.text} if with_text else {})


def make(*, url: str, source: str, kind: str, title: str, text: str, published_at: str | None = None,
         extra: Mapping[str, Any] | None = None) -> Evidence:
    if normalize_url(url) is None:
        raise ValueError(f"웹 링크가 아니다: {url[:80]!r}")
    excerpt = re.sub(r"\s+", " ", text).strip()[:EXCERPT_CHARS]
    return Evidence(url=url, source=source, kind=kind, title=title.strip(), excerpt=excerpt,
                    published_at=published_at, extra=dict(extra or {}), text=text)


def from_record(rec: Mapping[str, Any]) -> Evidence:
    return Evidence(url=rec["url"], source=rec["source"], kind=rec["kind"], title=rec["title"],
                    excerpt=rec["excerpt"], published_at=rec.get("published_at"),
                    extra=dict(rec.get("extra") or {}), text=str(rec.get("text") or ""))


def dedupe(docs: Iterable[Evidence]) -> list[Evidence]:
    """정규화한 URL 이 같으면 처음 것만 남긴다 (출처 순서가 우선순위)."""
    seen: set[str] = set()
    out: list[Evidence] = []
    for d in docs:
        if d.key not in seen:
            seen.add(d.key)
            out.append(d)
    return out


def until_ok(d: Evidence, until: date) -> bool:
    """그 주 끝 날 뒤에 발행된 근거는 뺀다(SPEC F10-2). 날짜를 모르면 남긴다."""
    return d.day is None or d.day <= until


@dataclass(frozen=True)
class Target:
    repo_id: int
    full_name: str
    since: date  # 그 주 첫날(포함)
    until: date  # 그 주 끝 날(포함)
    reasons: tuple[str, ...] = ()  # "종합 6위" · "관점 A" — 해설 대상이 된 까닭

    @property
    def owner(self) -> str:
        return self.full_name.split("/", 1)[0]

    @property
    def name(self) -> str:
        return self.full_name.split("/", 1)[1]
