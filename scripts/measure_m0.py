"""M0 API 실측 (TASKS T0-9·T0-10) — 후보 20개로 S2~S5 호출 수·시간·연결률·소급 범위를 잰다.

실제 외부 호출을 한다. GITHUB_TOKEN 은 이 명령에만 넘긴다(전역 export 금지). 토큰·응답 헤더는 남기지 않는다.
결과는 요약 JSON 하나(공개 저장소 메타·개수만)로 쓴다.

    GITHUB_TOKEN=... .venv/bin/python scripts/measure_m0.py --out <scratchpad>/m0.json
"""

import argparse
import json
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from radar.clients.transport import HttpResponse, UrllibTransport  # noqa: E402
from radar.config import load_config  # noqa: E402
from radar.core.candidates import select_candidates  # noqa: E402
from radar.inputs.startrend import available_weeks, load_ai_repos, load_week_stars  # noqa: E402

UA = "radar/0.0.1"
GH = "https://api.github.com"
T = UrllibTransport()
CALLS: dict[str, int] = {}
SECONDS: dict[str, float] = {}


def get(kind: str, url: str, headers: dict[str, str] | None = None, timeout: float = 60) -> HttpResponse:
    h = {"User-Agent": UA, "Accept": "application/json", **(headers or {})}
    started = time.monotonic()
    r = T("GET", url, h, timeout)
    CALLS[kind] = CALLS.get(kind, 0) + 1
    SECONDS[kind] = SECONDS.get(kind, 0.0) + time.monotonic() - started
    return r


def gh(kind: str, path: str, token: str) -> tuple[int, Any, HttpResponse]:
    for _ in range(3):
        r = get(kind, GH + path, {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                                  "X-GitHub-Api-Version": "2022-11-28"})
        if r.status in (403, 429) and r.headers.get("x-ratelimit-remaining") == "0":
            wait = max(1, int(r.headers.get("x-ratelimit-reset", "0")) - int(time.time()) + 1)
            print(f"  한도 대기 {wait}s ({kind})", file=sys.stderr, flush=True)
            time.sleep(min(wait, 90))
            continue
        break
    body = json.loads(r.body) if r.body and r.status == 200 else None
    return r.status, body, r


def iso(s: str | None) -> date | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC).date() if s else None


def week_of(d: date) -> date:
    return d - timedelta(days=(d.weekday() + 1) % 7)


# --- S2 포크 -----------------------------------------------------------------

def forks(full: str, token: str, since: date, max_pages: int) -> dict[str, Any]:
    st, meta, _ = gh("gh_rest", f"/repos/{full}", token)
    if st != 200:
        return {"status": st}
    weekly: dict[str, int] = {}
    pages, reached = 0, False
    for page in range(1, max_pages + 1):
        st, items, _ = gh("gh_rest", f"/repos/{full}/forks?sort=newest&per_page=100&page={page}", token)
        pages += 1
        if st != 200 or not items:
            reached = True
            break
        for it in items:
            d = iso(it.get("created_at"))
            if d and d >= since:
                k = week_of(d).isoformat()
                weekly[k] = weekly.get(k, 0) + 1
        last = iso(items[-1].get("created_at"))
        if last and last < since:
            reached = True
            break
    return {"forks_count": meta.get("forks_count"), "pages": pages, "reached_since": reached,
            "weekly": dict(sorted(weekly.items()))}


# --- S3 기여 (12주를 질의 한 번으로 받아 주별로 나눈다) ----------------------

def search_period(full: str, token: str, q: str, since: date, until: date) -> dict[str, Any]:
    qs = f"repo:{full} {q}:{since.isoformat()}..{until.isoformat()}"
    weekly: dict[str, int] = {}
    authors: dict[str, set[str]] = {}
    bots = 0
    total, pages = None, 0
    for page in range(1, 11):  # Search 는 최대 1,000건
        st, body, _ = gh("gh_search", "/search/issues?" + urlencode({"q": qs, "per_page": 100, "page": page}),
                         token)
        pages += 1
        if st != 200 or body is None:
            return {"status": st, "pages": pages}
        total = body.get("total_count")
        for it in body.get("items", []):
            when = (it.get("pull_request") or {}).get("merged_at") or it.get("closed_at")
            d = iso(when)
            if not d:
                continue
            k = week_of(d).isoformat()
            weekly[k] = weekly.get(k, 0) + 1
            user = it.get("user") or {}
            if user.get("type") == "Bot" or str(user.get("login", "")).endswith("[bot]"):
                bots += 1
                continue
            authors.setdefault(k, set()).add(str(user.get("login")))
        if len(body.get("items", [])) < 100 or page * 100 >= (total or 0):
            break
        time.sleep(2.1)  # 분당 30회
    return {"total": total, "pages": pages, "capped": (total or 0) > 1000, "bots": bots,
            "weekly": dict(sorted(weekly.items())),
            "authors": {k: len(v) for k, v in sorted(authors.items())}}


# --- S4 패키지 ----------------------------------------------------------------

_SUFFIXES = ("-python", "-py", ".py", "-js", ".js", "-node", "-ts", "-sdk", "-cli")
_PREFIXES = ("python-", "py-", "node-", "js-")


def name_candidates(full: str, eco: str) -> list[str]:
    owner, repo = full.lower().split("/", 1)
    names = [repo] + [repo[: -len(s)] for s in _SUFFIXES if repo.endswith(s)]
    names += [repo[len(p):] for p in _PREFIXES if repo.startswith(p)]
    if eco == "npm":
        names.append(f"@{owner}/{repo}")
    return list(dict.fromkeys(n for n in names if n))


def _same_repo(url: str | None, full: str) -> bool:
    if not url:
        return False
    u = url.lower().rstrip("/").removesuffix(".git")
    return u.endswith("github.com/" + full.lower())


def packages(full: str, since: date, until: date) -> dict[str, Any]:
    found: list[dict[str, Any]] = []
    for eco in ("pypi", "npm"):
        for name in name_candidates(full, eco):
            r = get("ecosystems", "https://packages.ecosyste.ms/api/v1/packages/lookup?"
                    + urlencode({"ecosystem": eco, "name": name}))
            if r.status != 200:
                continue
            for p in json.loads(r.body):
                if isinstance(p, dict) and _same_repo(p.get("repository_url"), full):
                    found.append({"ecosystem": eco, "name": p.get("name"),
                                  "dependent_packages": p.get("dependent_packages_count"),
                                  "dependent_repos": p.get("dependent_repos_count")})
            time.sleep(0.3)
    for f in found:
        f["downloads"] = downloads(f["ecosystem"], f["name"], since, until)
    return {"packages": found}


def downloads(eco: str, name: str, since: date, until: date) -> dict[str, Any]:
    weekly: dict[str, int] = {}
    if eco == "pypi":
        r = get("pypistats", f"https://pypistats.org/api/packages/{quote(name.lower())}/overall?mirrors=false")
        time.sleep(1.0)
        if r.status != 200:
            return {"status": r.status}
        rows = [x for x in json.loads(r.body).get("data", []) if x.get("category") == "without_mirrors"]
        days = sorted(date.fromisoformat(x["date"]) for x in rows)
        for x in rows:
            d = date.fromisoformat(x["date"])
            if since <= d <= until:
                k = week_of(d).isoformat()
                weekly[k] = weekly.get(k, 0) + int(x["downloads"])
        return {"first_day": days[0].isoformat() if days else None, "weekly": dict(sorted(weekly.items()))}
    r = get("npm", f"https://api.npmjs.org/downloads/range/{since.isoformat()}:{until.isoformat()}/"
            + quote(name, safe="@/"))
    if r.status != 200:
        return {"status": r.status}
    days_ = json.loads(r.body).get("downloads", [])
    for x in days_:
        d = date.fromisoformat(x["day"])
        k = week_of(d).isoformat()
        weekly[k] = weekly.get(k, 0) + int(x["downloads"])
    return {"first_day": days_[0]["day"] if days_ else None, "weekly": dict(sorted(weekly.items()))}


# --- S5 언급 ------------------------------------------------------------------

def hn(full: str, since: date, until: date) -> dict[str, Any]:
    a = int(datetime(since.year, since.month, since.day, tzinfo=UTC).timestamp())
    b = int(datetime(until.year, until.month, until.day, tzinfo=UTC).timestamp()) + 86400
    params = {"query": f"github.com/{full}", "restrictSearchableAttributes": "url", "tags": "story",
              "numericFilters": f"created_at_i>={a},created_at_i<{b}", "hitsPerPage": 100}
    r = get("hn", "https://hn.algolia.com/api/v1/search?" + urlencode(params))
    if r.status != 200:
        return {"status": r.status}
    hits = json.loads(r.body).get("hits", [])
    exact = [h for h in hits if _same_repo_prefix(h.get("url"), full)]
    weekly: dict[str, list[int]] = {}
    for h in exact:
        k = week_of(datetime.fromtimestamp(h["created_at_i"], UTC).date()).isoformat()
        weekly.setdefault(k, []).append(int(h.get("points") or 0))
    return {"hits": len(hits), "exact": len(exact),
            "weekly": {k: {"stories": len(v), "points": sum(v)} for k, v in sorted(weekly.items())}}


def _same_repo_prefix(url: str | None, full: str) -> bool:
    if not url:
        return False
    u = url.lower().split("?", 1)[0].split("#", 1)[0].rstrip("/")
    base = "github.com/" + full.lower()
    return u.endswith(base) or (base + "/") in u


def geeknews(days: list[date]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    r = get("geeknews", "https://news.hada.io/robots.txt", {"Accept": "text/plain"})
    out["robots"] = r.body.decode("utf-8", "ignore")[:600] if r.status == 200 else r.status
    for d in days:
        time.sleep(2.0)
        r = get("geeknews", f"https://news.hada.io/past?day={d.isoformat()}", {"Accept": "text/html"})
        page = r.body.decode("utf-8", "ignore")
        out[d.isoformat()] = {"status": r.status, "topics": page.count("<div class='topic_row'"),
                              "github_links": page.count("github.com/"),
                              "has_next": f"past?day={d.isoformat()}&page=2" in page
                              or f"past?day={d.isoformat()}&amp;page=2" in page}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--fork-pages", type=int, default=100)
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("GITHUB_TOKEN 이 없다", file=sys.stderr)
        return 1
    cfg = load_config()
    ai = load_ai_repos(cfg.startrend_dir)
    week = available_weeks(cfg.startrend_dir)[-1]
    cands = select_candidates(load_week_stars(cfg.startrend_dir, week), ai.keys(), [], cfg.cap)
    step = max(1, len(cands) // args.n)
    sample = cands[::step][: args.n]   # 1·11·21…위 — 상위만이 아니라 후보 전체에 고르게
    since = week - timedelta(weeks=11)   # 12주 = since 주부터 week 주까지
    until = week + timedelta(days=6)
    print(f"주 {week} · 소급 {since}~{until} · 표본 {len(sample)}", file=sys.stderr)
    t0 = time.monotonic()
    res: dict[str, Any] = {"week": week.isoformat(), "since": since.isoformat(), "until": until.isoformat(),
                           "repos": {}}
    for c in sample:
        print(f"- {c.gain_rank:>3} {c.full_name}", file=sys.stderr, flush=True)
        one: dict[str, Any] = {"gain_rank": c.gain_rank, "gain": c.gain,
                               "category": ai[c.id].category}
        s = time.monotonic()
        one["s2"] = forks(c.full_name, token, since, args.fork_pages)
        one["s2_sec"] = round(time.monotonic() - s, 1)
        s = time.monotonic()
        one["s3_pr"] = search_period(c.full_name, token, "is:pr is:merged merged", since, until)
        time.sleep(2.1)
        one["s3_issue"] = search_period(c.full_name, token, "is:issue is:closed closed", since, until)
        time.sleep(2.1)
        one["s3_sec"] = round(time.monotonic() - s, 1)
        s = time.monotonic()
        one["s4"] = packages(c.full_name, since, until)
        one["s4_sec"] = round(time.monotonic() - s, 1)
        one["s5_hn"] = hn(c.full_name, since, until)
        res["repos"][c.full_name] = one
        # 중간에 멈춰도 결과가 남게 저장소마다 쓴다
        res["calls"] = CALLS
        Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"    S2 {one['s2_sec']}s(쪽 {one['s2'].get('pages')}) · S3 {one['s3_sec']}s · "
              f"S4 {one['s4_sec']}s · 누적 {round(time.monotonic() - t0)}s", file=sys.stderr, flush=True)
    res["geeknews"] = geeknews([until - timedelta(days=2), since, since - timedelta(weeks=40)])
    res["calls"] = CALLS
    res["seconds"] = {k: round(v, 1) for k, v in SECONDS.items()}
    res["total_sec"] = round(time.monotonic() - t0, 1)
    Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"끝 — {res['total_sec']}s · 호출 {CALLS}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
