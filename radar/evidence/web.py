"""웹 근거 — Tavily 검색 (SPEC D15 · star-trend 결정 46·52 방식, PLAN P5).

저장소마다 검색어 3개(basic = 1크레딧씩). 결과 URL·제목·스니펫·발행일을 근거로 남긴다. 저장소 자신의
GitHub 페이지는 GitHub 출처가 맡으므로 뺀다. 그 주 끝 날 뒤에 발행된 결과도 뺀다.
페이지 본문은 읽지 않는다(Reddit·X 포함 — 링크와 스니펫만). 키는 Authorization 머리말로만 보내고
오류 메시지에 남기지 않는다.
"""

from datetime import UTC, date
from email.utils import parsedate_to_datetime

from radar.clients.http import HttpClient
from radar.clients.transport import TransportError
from radar.core import evidence as ev
from radar.evidence.base import SourceError

API = "https://api.tavily.com/search"
MAX_RESULTS = 8


def iso_date(raw: str) -> str | None:
    """Tavily 발행일(RFC 1123 또는 ISO) → ISO. 읽을 수 없으면 None."""
    s = raw.strip()
    try:
        date.fromisoformat(s[:10])
        return s
    except ValueError:
        pass
    try:
        t = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_queries(t: ev.Target) -> list[str]:
    return [t.full_name, f"{t.name} github tutorial", f"{t.name} review"]


def collect_web(
    client: HttpClient, api_key: str, t: ev.Target
) -> tuple[list[ev.Evidence], int, list[dict[str, str]]]:
    """(근거, 쓴 크레딧, 이미지 결과 [{url, description, query}]).

    실패한 요청도 크레딧을 쓸 수 있어 크게 센다.
    """
    if not api_key:
        raise SourceError("Tavily 키가 없다")
    own = ev.normalize_url(f"https://github.com/{t.full_name}") or ""
    docs: list[ev.Evidence] = []
    images: list[dict[str, str]] = []
    credits = 0
    for q in default_queries(t):
        payload = {"query": q, "search_depth": "basic", "max_results": MAX_RESULTS, "include_answer": False,
                   "include_raw_content": False, "include_published_date": True,
                   "include_images": True, "include_image_descriptions": True}
        try:
            credits += 1
            auth = {"Authorization": f"Bearer {api_key}"}
            st, body = client.send_json("tavily", "POST", API, payload, auth)
        except TransportError as e:
            raise SourceError(f"Tavily 연결 실패: {type(e).__name__}") from e
        if st != 200 or not isinstance(body, dict) or not isinstance(body.get("results"), list):
            raise SourceError(f"Tavily {st}")
        for im in body.get("images") or []:
            url = im.get("url") if isinstance(im, dict) else im
            new = all(x["url"] != url for x in images)
            if isinstance(url, str) and url.startswith(("http://", "https://")) and new:
                desc = str(im.get("description") or "") if isinstance(im, dict) else ""
                images.append({"url": url, "description": desc, "query": q})
        for r in body["results"]:
            if not isinstance(r, dict) or not isinstance(r.get("url"), str):
                continue
            key = ev.normalize_url(r["url"])
            if key is None or key == own or key.startswith(own + "/"):
                continue
            pub = iso_date(str(r["published_date"])) if r.get("published_date") else None
            d = ev.make(url=r["url"], source="web", kind="search", title=str(r.get("title") or ""),
                        text=str(r.get("content") or ""), published_at=pub, extra={"query": q})
            if ev.until_ok(d, t.until):
                docs.append(d)
    return ev.dedupe(docs), credits, images
