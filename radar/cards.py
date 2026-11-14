"""저장소 해설 단계 (SPEC F10 · TASKS T7-7) — 대상 → 근거 → 해설(LLM) → 게이트 → 비공개 저장 → 사이트 사본.

- 대상: 그 주 종합 TOP 10 + 관점 노트 A~D 저장소(D14). 사이트 데이터(data/site/)가 먼저 있어야 한다.
- 근거: GitHub(README·릴리스) · HN(글·큰 댓글 타래) · GeekNews(그 주 한 번 훑기) · 웹 검색(Tavily, D15).
  저장소별로 `.work/evidence/<주>/<id>.json` 에 남겨 다시 돌릴 때 부르지 않는다(실패가 없을 때만 남긴다).
- 해설: 한 저장소에 한 번(Sonnet 5.5). 읽지 못하면 한 번 다시 묻는다. 예산은 실행당 상한에서
  그 주 블로그 초안이 쓴 만큼을 뺀 나머지(N7). 최악 비용이 남은 예산을 넘으면 그 저장소는 건너뛴다.
- 저장(D13): `.private/cards/<id>.json`(최신) · `.private/weeks/<주>/cards/`(주별 기록) ·
  `.private/site-private/`(사이트 사본 — 웹이 빌드 때 받는다). 공개 저장소에는 아무것도 쓰지 않는다.
"""

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from radar.clients.claude import FALLBACK_MODELS, MODEL, LLMClient, LLMRequest
from radar.clients.http import HttpClient
from radar.config import PROJECT_ROOT
from radar.core import evidence as ev
from radar.core.geeknews import Topic
from radar.core.repo_images import explanatory, rank_candidates, readme_images
from radar.core.weeks import week_end
from radar.evidence.base import SourceError
from radar.evidence.geeknews import collect_geeknews, geeknews_week
from radar.evidence.github import collect_github
from radar.evidence.hn import collect_hn
from radar.evidence.images import fetch_image, homepage_og, repo_meta
from radar.evidence.web import collect_web
from radar.publish import card, charts
from radar.publish.budget import Budget, BudgetExceeded, cost_usd
from radar.store import DATA, json_text, write_mutable

PRIVATE = PROJECT_ROOT / ".private"
WORK = PROJECT_ROOT / ".work" / "evidence"
CAP_USD = 3.0
TYPICAL_IN, TYPICAL_OUT = 12_000, 3_000  # star-trend 실측(입력 1만~1.5만, 출력 약 3,600)보다 짧은 해설
WORST_IN = 30_000
SIGNALS = {"s1": "스타", "s2": "포크", "s3": "기여", "s4": "사용", "s5": "언급"}
ANGLE_NAMES = {"A": "조용한 강자", "B": "반짝 관심", "C": "꾸준한 상승", "D": "신호 전환"}
RETRY_NOTE = "\n\n이전 응답을 읽지 못했습니다({}). 정해진 JSON 형식에 맞춰 다시 쓰세요."


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _site(data: Path) -> Path:
    return data / "site"


def targets(week: date, data: Path = DATA) -> list[ev.Target]:
    """그 주 TOP 10 순서대로, 이어서 관점 노트 A~D. 한 저장소는 한 번(까닭은 모두 모은다)."""
    doc = _read(_site(data) / "week" / f"{week.isoformat()}.json")
    reasons: dict[int, list[str]] = {}
    names: dict[int, str] = {}
    for r in doc["top10"]:
        reasons.setdefault(r["repo_id"], []).append(f"종합 {r['rank']}위")
        names[r["repo_id"]] = r["full_name"]
    for k in ("A", "B", "C", "D"):
        for it in (doc.get("angles", {}).get(k) or {}).get("items", []):
            reasons.setdefault(it["repo_id"], []).append(f"관점 {k}({ANGLE_NAMES[k]})")
            names[it["repo_id"]] = it["full_name"]
    return [ev.Target(rid, names[rid], week, week_end(week), tuple(rs)) for rid, rs in reasons.items()]


@dataclass
class Collected:
    docs: list[ev.Evidence]
    posts: list[dict[str, Any]]
    releases: list[dict[str, str]]
    failures: list[str] = field(default_factory=list)
    credits: int = 0
    cached: bool = False
    images: list[dict[str, str]] = field(default_factory=list)  # 웹 이미지 검색 결과 (D21)


def _cache(work: Path, week: date, name: str) -> Path:
    return work / week.isoformat() / name


def _geeknews(client: HttpClient, week: date, work: Path) -> tuple[dict[str, list[Topic]], list[str]]:
    p = _cache(work, week, "geeknews.json")
    if p.exists():
        raw = _read(p)
        return {
            k: [
                Topic(
                    t["topic_id"], t["repo"], t["points"], date.fromisoformat(t["day"]), t["title"], t["link"]
                )
                for t in v
            ]
            for k, v in raw.items()
        }, []
    idx, failed = geeknews_week(client, week)
    if not failed:
        write_mutable(
            p,
            json_text(
                {
                    k: [
                        {
                            "topic_id": t.topic_id,
                            "repo": t.repo,
                            "points": t.points,
                            "day": t.day.isoformat(),
                            "title": t.title,
                            "link": t.link,
                        }
                        for t in v
                    ]
                    for k, v in idx.items()
                }
            ),
        )
    return idx, failed


def collect(
    t: ev.Target,
    *,
    client: HttpClient,
    token: str,
    tavily_key: str,
    gn: Mapping[str, list[Topic]],
    work: Path,
) -> Collected:
    p = _cache(work, t.since, f"{t.repo_id}.json")
    if p.exists():
        raw = _read(p)
        return Collected(
            [ev.from_record(r) for r in raw["docs"]],
            raw["posts"],
            raw["releases"],
            cached=True,
            images=list(raw.get("images") or []),
        )
    failures: list[str] = []
    gh_docs, releases, problems = collect_github(client, token, t)
    failures += [f"github {x}" for x in problems]
    hn_docs: list[ev.Evidence] = []
    posts: list[dict[str, Any]] = []
    try:
        hn_docs, posts = collect_hn(client, t)
    except SourceError as e:
        failures.append(f"hn {e}")
    gn_docs, gn_posts = collect_geeknews(dict(gn), t)
    web_docs: list[ev.Evidence] = []
    web_images: list[dict[str, str]] = []
    credits = 0
    if tavily_key:
        try:
            web_docs, credits, web_images = collect_web(client, tavily_key, t)
        except SourceError as e:
            failures.append(f"web {e}")
            credits = 3
    else:
        failures.append("web 키 없음")
    docs = [d for d in ev.dedupe(gh_docs + hn_docs + gn_docs + web_docs) if ev.until_ok(d, t.until)]
    posts = sorted(posts + gn_posts, key=lambda x: (-int(x["points"] or 0), str(x["url"])))
    col = Collected(docs, posts, releases, failures, credits, images=web_images)
    if not failures:
        record = {
            "docs": [d.record(with_text=True) for d in docs],
            "posts": posts,
            "releases": releases,
            "images": web_images,
        }
        write_mutable(p, json_text(record))
    return col


def facts_for(t: ev.Target, week: date, col: Collected, data: Path = DATA) -> dict[str, Any]:
    """코드가 계산한 사실 묶음 — 게이트가 허용하는 숫자의 출처이기도 하다."""
    repo = _read(_site(data) / "repo" / f"{t.repo_id}.json")
    wk = _read(_site(data) / "week" / f"{week.isoformat()}.json")
    latest = repo["latest"]
    if latest["week"] != week.isoformat():
        raise ValueError(f"{t.full_name}: 사이트 데이터의 최신 주가 {latest['week']} 이다 (요청 {week})")
    signals: dict[str, Any] = {}
    for s, name in SIGNALS.items():
        pct = latest["pct"].get(s)
        base = {"weight": wk["weights"][s]}
        signals[name] = base | (
            {"percentile": pct, "contribution": latest["contrib"][s]}
            if pct is not None
            else {"missing": True}
        )
    return {
        "repository": {
            k: repo.get(k) for k in ("full_name", "description", "topics", "language", "category")
        },
        "week": week.isoformat(),
        "reasons": list(t.reasons),
        "rank": latest["rank"],
        "prev_rank": latest["prev_rank"],
        "star_rank": latest["star_rank"],
        "index": latest["index"],
        "signals": signals,
        "trend": repo.get("trend") or [],
        "observations": [
            {k: o[k] for k in ("id", "title", "big", "text")} for o in repo.get("insights") or []
        ],
        "mentions": repo.get("mentions"),
        "posts_this_week": col.posts,
        "releases_this_week": col.releases,
    }


def slug(full_name: str) -> str:
    return full_name.replace("/", "__")


def pick_image(
    t: ev.Target,
    col: Collected,
    meta: Mapping[str, Any] | None,
    *,
    client: HttpClient,
    folder: Path,
    known: Mapping[str, Any],
) -> dict[str, Any] | None:
    """저장소 설명 그림 하나 (SPEC F11 · D21) — 후보를 차례로 받아 설명이 되는 첫 그림.

    받아 둔 것이 있으면 그대로 쓴다.
    """
    key = slug(t.full_name)
    old = known.get(key)
    if old and (folder / old["file"]).exists():
        return dict(old)
    m = meta or {}
    readme = next((d.text for d in col.docs if d.kind == "readme"), "")
    home = m.get("homepage")
    cands = rank_candidates(
        readme=readme_images(readme, t.full_name),
        license_id=m.get("license"),
        social=m.get("social"),
        homepage_og=homepage_og(client, home) if home else None,
        homepage=home,
        web=col.images,
        full_name=t.full_name,
    )
    for c in cands:
        data = fetch_image(client, c.url)
        info = charts.inspect_image(data) if data else None
        if data is None or info is None or not explanatory(info[1], info[2]):
            continue
        ext, w, h = info
        name = f"{key}.{ext}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
        return {
            "kind": c.kind,
            "url": c.url,
            "source": c.source,
            "rights": c.rights,
            "file": name,
            "width": w,
            "height": h,
        }
    return None


def _meta(client: HttpClient, token: str, ts: Sequence[ev.Target], work: Path, week: date) -> dict[str, Any]:
    """소셜 미리보기·홈페이지·라이선스 — 그 주에 한 번(캐시)."""
    path = _cache(work, week, "meta.json")
    if path.exists():
        cached: dict[str, Any] = _read(path)
        if cached:
            return cached
    meta = repo_meta(client, token, [t.full_name for t in ts])
    if meta:
        write_mutable(path, json_text(meta))
    return meta


def pick_images(
    week: date,
    *,
    client: HttpClient,
    token: str,
    tavily_key: str,
    data: Path = DATA,
    private: Path = PRIVATE,
    work: Path = WORK,
    only: Sequence[str] = (),
) -> dict[str, Any]:
    """--images-only — LLM 없이 저장소 설명 그림만 고른다(근거 캐시를 쓴다)."""
    ts = _filter(targets(week, data), only)
    folder = private / "weeks" / week.isoformat() / "blog" / "images"
    index = folder / "images.json"
    known: dict[str, Any] = _read(index) if index.exists() else {}
    meta = _meta(client, token, ts, work, week)
    gn, _ = _geeknews(client, week, work)
    for t in ts:
        col = collect(t, client=client, token=token, tavily_key=tavily_key, gn=gn, work=work)
        picked = pick_image(t, col, meta.get(t.full_name.lower()), client=client, folder=folder, known=known)
        if picked:
            known[slug(t.full_name)] = picked
    write_mutable(index, json_text(known))
    return known


def blog_spent(week: date, private: Path = PRIVATE) -> float:
    p = private / "weeks" / week.isoformat() / "blog" / "draft.json"
    if not p.exists():
        return 0.0
    return float(_read(p).get("cost_usd") or 0.0)


def _filter(ts: Sequence[ev.Target], only: Sequence[str]) -> list[ev.Target]:
    want = {o.lower() for o in only}
    return [t for t in ts if not want or t.full_name.lower() in want]


def plan(
    week: date,
    *,
    data: Path = DATA,
    work: Path = WORK,
    private: Path = PRIVATE,
    cap: float = CAP_USD,
    only: Sequence[str] = (),
    model: str = MODEL,
) -> dict[str, Any]:
    """--dry-run — 호출 0. 대상·예상 호출 수·비용."""
    ts = _filter(targets(week, data), only)
    new = [t for t in ts if not _cache(work, week, f"{t.repo_id}.json").exists()]
    models = (model, *FALLBACK_MODELS)
    typical = cost_usd(models, TYPICAL_IN, TYPICAL_OUT)
    worst = cost_usd(models, WORST_IN, card.MAX_TOKENS)
    spent = blog_spent(week, private)
    return {
        "week": week.isoformat(),
        "targets": len(ts),
        "reasons": {t.full_name: list(t.reasons) for t in ts},
        "evidence_cached": len(ts) - len(new),
        "calls": {
            "github": 2 * len(new),
            "hn": 3 * len(new),
            "tavily_credits": 3 * len(new),
            "geeknews_pages": "0" if _cache(work, week, "geeknews.json").exists() else "8~24",
        },
        "llm": {
            "cards": len(ts),
            "typical_usd": round(typical * len(ts), 2),
            "worst_per_card_usd": round(worst, 3),
            "cap_usd": cap,
            "blog_spent_usd": round(spent, 4),
            "remaining_usd": round(max(0.0, cap - spent), 4),
        },
    }


def _complete(
    llm: LLMClient, req: LLMRequest, budget: Budget, models: Sequence[str]
) -> tuple[dict[str, Any] | None, str, str, int, int, float]:
    """(해설 원본 또는 None, 상태, 모델, 입력 토큰, 출력 토큰, 비용). 읽지 못하면 한 번 다시 묻는다."""
    tin = tout = 0
    spent = 0.0
    model = llm.model
    for attempt in range(2):
        try:
            budget.reserve(models, req.system + req.user, max_tokens=req.max_tokens)
        except BudgetExceeded:
            return None, "skipped:budget", model, tin, tout, spent
        try:
            reply = llm.complete(req)
        except Exception as e:  # noqa: BLE001 — 예외 메시지에 키가 섞일 수 있어 이름만 남긴다
            return None, f"failed:{type(e).__name__}", model, tin, tout, spent
        spent += budget.record(models, reply.input_tokens, reply.output_tokens)
        tin, tout, model = tin + reply.input_tokens, tout + reply.output_tokens, reply.model
        if reply.stop_reason in ("refusal", "max_tokens"):
            return None, f"failed:{reply.stop_reason}", model, tin, tout, spent
        try:
            return card.parse(reply.text), "ok", model, tin, tout, spent
        except card.CardError as e:
            if attempt == 0:
                req = LLMRequest(
                    req.system, req.user + RETRY_NOTE.format(e), req.schema, req.max_tokens, req.effort
                )
    return None, "failed:invalid_output", model, tin, tout, spent


def _write_index(private: Path) -> None:
    cards_dir = private / "site-private" / "cards"
    rows = []
    for f in sorted(cards_dir.glob("*.json")):
        if f.name == "index.json":
            continue
        c = _read(f)
        rows.append({"repo_id": c["repo_id"], "full_name": c["full_name"], "week": c["week"]})
    write_mutable(cards_dir / "index.json", json_text(rows))


def write_cards(
    week: date,
    llm: LLMClient,
    *,
    client: HttpClient,
    token: str,
    tavily_key: str,
    data: Path = DATA,
    private: Path = PRIVATE,
    work: Path = WORK,
    cap: float = CAP_USD,
    only: Sequence[str] = (),
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """해설을 쓰고 실행 기록을 돌려준다. 저장소 하나가 실패해도 다음으로 간다."""
    ts = _filter(targets(week, data), only)
    spent_before = blog_spent(week, private)
    budget = Budget(max(0.0, cap - spent_before))
    models = (llm.model, *FALLBACK_MODELS)
    gn, gn_failed = _geeknews(client, week, work)
    wk = week.isoformat()
    lines_path = private / "site-private" / "weeks" / f"{wk}.json"
    lines: dict[str, str] = _read(lines_path)["lines"] if lines_path.exists() else {}
    results: list[dict[str, Any]] = []
    credits = 0
    img_dir = private / "weeks" / wk / "blog" / "images"
    img_index = img_dir / "images.json"
    known: dict[str, Any] = _read(img_index) if img_index.exists() else {}
    meta = _meta(client, token, ts, work, week)
    for t in ts:
        col = collect(t, client=client, token=token, tavily_key=tavily_key, gn=gn, work=work)
        credits += col.credits
        picked = pick_image(t, col, meta.get(t.full_name.lower()), client=client, folder=img_dir, known=known)
        if picked:
            known[slug(t.full_name)] = picked
        facts = facts_for(t, week, col, data)
        req = card.build_request(facts, col.docs)
        raw, status, model, tin, tout, cost = _complete(llm, req, budget, models)
        row: dict[str, Any] = {
            "repo": t.full_name,
            "status": status,
            "evidence": len(col.docs),
            "failures": col.failures,
            "cached": col.cached,
            "input_tokens": tin,
            "output_tokens": tout,
            "cost_usd": round(cost, 6),
        }
        if raw is None:
            results.append(row)
            log(f"  {t.full_name}: {status}")
            continue
        clean, report = card.gate(raw, facts, col.docs)
        latest = private / "cards" / f"{t.repo_id}.json"
        history = _read(latest).get("history", []) if latest.exists() else []
        site = card.site_card(
            clean,
            target=t,
            week=wk,
            model=model,
            report=report,
            docs=col.docs,
            posts=col.posts,
            releases=col.releases,
            generated=now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            history=history,
        )
        write_mutable(latest, json_text(site))
        write_mutable(private / "site-private" / "cards" / f"{t.repo_id}.json", json_text(site))
        fname = slug(t.full_name)
        write_mutable(
            private / "weeks" / wk / "cards" / f"{fname}.json",
            json_text(
                {
                    "card": site,
                    "excluded": report.excluded,
                    "facts": facts,
                    "evidence": [d.record() for d in col.docs],
                    "failures": col.failures,
                }
            ),
        )
        why = (site["summary"].get("why_now") or {}).get("text")
        if why:
            lines[str(t.repo_id)] = why
        row["excluded"] = len(report.excluded)
        results.append(row)
        log(f"  {t.full_name}: ok · 근거 {len(col.docs)} · 제외 {len(report.excluded)} · ${cost:.4f}")
    write_mutable(lines_path, json_text({"week": wk, "lines": lines}))
    write_mutable(img_index, json_text(known))
    _write_index(private)
    record = {
        "week": wk,
        "targets": len(ts),
        "ok": sum(r["status"] == "ok" for r in results),
        "skipped": sum(r["status"].startswith("skipped") for r in results),
        "failed": sum(r["status"].startswith("failed") for r in results),
        "cost_usd": round(budget.spent_usd, 6),
        "cap_usd": cap,
        "blog_spent_usd": spent_before,
        "tavily_credits": credits,
        "calls": dict(client.calls),
        "geeknews_failed": gn_failed,
        "model": llm.model,
        "results": results,
    }
    write_mutable(private / "weeks" / wk / "cards" / "run.json", json_text(record))
    return record
