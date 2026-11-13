"""12주 소급 (SPEC F5, D10·D12 · TASKS T2-4).

두 단계로 나눈다.
1. 모으기 — 12주 동안 한 번이라도 후보였던 저장소(합집합)마다 처음 후보가 된 주부터 소급 끝 주까지를
   창 하나로 받는다(S3 PR·이슈, S4 다운로드, S5 HN). GeekNews 는 전체 기간을 한 번 읽는다.
   저장소마다 `.work/backfill/` 에 바로 저장하고, 다시 실행하면 저장된 저장소는 건너뛴다(긴 실행 이어 하기).
2. 주별 쓰기 — 오래된 주부터 후보 선정(지난주 TOP 보충은 앞 주 지수가 있어야 한다) → signals → 지수.

S2 포크는 소급하지 않는다(D10, 상태 none). 의존 수는 소급할 수 없어 비운다. 행에는 backfilled=1 을 남긴다.
"""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from radar.clients.http import HttpClient
from radar.collectors import activity, mentions, packages
from radar.collectors.base import FAILED, OK
from radar.config import PROJECT_ROOT, Config
from radar.core.candidates import select_candidates
from radar.core.models import Candidate, RepoMeta
from radar.core.weeks import weeks_back
from radar.inputs.startrend import load_ai_repos, load_week_stars
from radar.pipeline import (
    NONE,
    POLICIES,
    SIGNAL_FIELDS,
    build_index,
    load_links,
    needs_link,
    previous_top,
    s4_state,
    signal_row,
    worst,
)
from radar.store import DATA, csv_text, json_text, week_path, write_mutable, write_once

WORK = PROJECT_ROOT / ".work" / "backfill"
WEEKS = 12
# M0 실측(MEASURE §1): 12주 창 저장소당 Search 평균 약 8질의
SEARCH_PER_REPO_TYPICAL = 8

Log = Callable[[str], None]


def _gain_candidates(cfg: Config, ai: dict[int, RepoMeta], weeks: list[date]) -> dict[date, list[Candidate]]:
    """주마다 스타 증가 상위(지난주 TOP 보충 없이) — 합집합과 창을 정하는 데 쓴다."""
    return {w: select_candidates(load_week_stars(cfg.startrend_dir, w), ai.keys(), [], cfg.cap)
            for w in weeks}


def _first_seen(by_week: dict[date, list[Candidate]]) -> dict[int, date]:
    """저장소 → 처음 후보가 된 주. 지난주 TOP 보충 저장소는 앞 주 후보였으므로 창(→ 끝 주) 안에 든다."""
    first: dict[int, date] = {}
    for w in sorted(by_week):
        for c in by_week[w]:
            first.setdefault(c.id, w)
    return first


def plan_backfill(cfg: Config, anchor: date, n: int = WEEKS, *, data: Path = DATA) -> dict[str, Any]:
    """--dry-run — 호출 0. 합집합 저장소 수와 예상 호출·시간."""
    weeks = weeks_back(anchor, n)
    ai = load_ai_repos(cfg.startrend_dir)
    first = _first_seen(_gain_candidates(cfg, ai, weeks))
    links = load_links(data)
    today = datetime.now(UTC).date()
    uncached = sum(1 for rid in first if needs_link(links.get(str(rid)), today))
    known = sum(len(links.get(str(rid), {}).get("packages", [])) for rid in first)
    repos = len(first)
    days = 7 * n + 1
    gap = POLICIES["gh_search"].min_interval
    calls = {"gh_rest": 3 * uncached, "gh_search": 2 * repos,
             "gh_search_typical": SEARCH_PER_REPO_TYPICAL * repos, "registry": 4 * uncached,
             "downloads": known, "hn": repos, "geeknews": days}
    base = days * POLICIES["geeknews"].min_interval + known * POLICIES["pypistats"].min_interval
    return {"anchor": anchor.isoformat(), "weeks": [w.isoformat() for w in weeks], "repos": repos,
            "uncached_links": uncached, "calls": calls,
            "min_minutes": round((2 * repos * gap + base) / 60, 1),
            "typical_minutes": round((SEARCH_PER_REPO_TYPICAL * repos * gap + base) / 60, 1),
            "existing_weeks": [w.isoformat() for w in weeks if week_path("signals", w, "csv", data).exists()]}


def _collect_repo(client: HttpClient, token: str, full: str, window: list[date],
                  pkgs: list[packages.Package]) -> dict[str, Any]:
    act = activity.collect(client, token, full, window)
    dl: dict[str, int | None] = {w.isoformat(): None for w in window}
    states: list[str] = []
    for p in pkgs:
        got, st = packages.weekly_downloads(client, p, window)
        states.append(st)
        for w in window:
            v = got.get(w)
            if v is not None:
                dl[w.isoformat()] = (dl[w.isoformat()] or 0) + v
    hn, hn_status = mentions.hn_mentions(client, full, window)
    return {
        "full_name": full, "window": [w.isoformat() for w in window],
        "s3": {w.isoformat(): [a.merged_prs, a.pr_authors, a.closed_issues] for w, a in act.weekly.items()},
        "s3_status": act.status, "s3_note": act.note,
        "packages": [[p.ecosystem, p.name] for p in pkgs], "downloads": dl, "s4_states": states,
        "hn": {w.isoformat(): list(v) for w, v in hn.items()}, "hn_status": hn_status,
    }


def _pair(v: Any) -> tuple[int, int] | None:
    return (int(v[0]), int(v[1])) if v is not None else None


def _read(f: Path) -> dict[str, Any] | None:
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def run_backfill(cfg: Config, client: HttpClient, token: str, anchor: date, n: int = WEEKS, *,
                 data: Path = DATA, work: Path = WORK, now: datetime | None = None,
                 log: Log | None = None) -> dict[str, Any]:
    """anchor 바로 앞 n 주를 소급해 signals·candidates·runs·index 를 쓴다. 이미 쓴 주는 건너뛴다."""
    say = log or (lambda _m: None)
    started = now or datetime.now(UTC)
    today = started.date()
    weeks = weeks_back(anchor, n)
    end = weeks[-1]
    ai = load_ai_repos(cfg.startrend_dir)
    first = _first_seen(_gain_candidates(cfg, ai, weeks))
    name = {rid: ai[rid].full_name for rid in first}
    cache_dir = work / f"{anchor.isoformat()}-{n}"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 1-a 패키지 연결 (주간 수집과 같은 4주 캐시)
    links = load_links(data)
    linked = 0
    for rid in sorted(first):
        if needs_link(links.get(str(rid)), today):
            lr = packages.link(client, token, name[rid])
            links[str(rid)] = {"checked": today.isoformat(), "full_name": name[rid], "status": lr.status,
                               "packages": [[p.ecosystem, p.name] for p in lr.packages]}
            linked += 1
            if linked % 25 == 0:
                write_mutable(data / "meta" / "packages.json", json_text(links))
    write_mutable(data / "meta" / "packages.json", json_text(links))
    say(f"패키지 연결 새로 {linked} · 합집합 {len(first)}")

    # 1-b GeekNews 전체 기간 한 번
    gn_file = cache_dir / "geeknews.json"
    gn = _read(gn_file)
    if gn is None:
        idx, gn_status, gn_note = mentions.geeknews_index(client, weeks)
        gn = {"status": gn_status, "note": gn_note,
              "idx": {repo: {w.isoformat(): list(v) for w, v in by_w.items()} for repo, by_w in idx.items()}}
        write_mutable(gn_file, json_text(gn))
    say(f"GeekNews {gn['status']}")

    # 1-c 저장소마다 창 하나
    for i, rid in enumerate(sorted(first, key=lambda r: (first[r], r)), 1):
        f = cache_dir / f"{rid}.json"
        if f.exists():
            continue
        window = [w for w in weeks if first[rid] <= w <= end]
        pkgs = [packages.Package(e, p) for e, p in links.get(str(rid), {}).get("packages", [])]
        write_mutable(f, json_text(_collect_repo(client, token, name[rid], window, pkgs)))
        say(f"{i:>4}/{len(first)} {name[rid]} ({len(window)}주)")

    # 2 주별 쓰기 — 오래된 주부터
    gn_ok = gn["status"] != FAILED
    written: list[str] = []
    skipped: list[str] = []
    for w in weeks:
        key = w.isoformat()
        if week_path("signals", w, "csv", data).exists():
            skipped.append(key)
            if not week_path("index", w, "json", data).exists():
                build_index(cfg, w, data=data)
            continue
        stars = load_week_stars(cfg.startrend_dir, w)
        cands = select_candidates(stars, ai.keys(), previous_top(data, w)[: cfg.previous_top], cfg.cap)
        rows: list[dict[str, Any]] = []
        tally: dict[str, dict[str, int]] = {k: {} for k in ("s3", "s4", "s5")}
        for c in cands:
            full = name.get(c.id) or ai[c.id].full_name
            rc = _read(cache_dir / f"{c.id}.json")
            s3: tuple[activity.WeekActivity | None, str]
            if rc and key in rc["s3"]:
                m, a, cl = rc["s3"][key]
                s3 = (activity.WeekActivity(m, a, cl), str(rc["s3_status"]))
            else:
                s3 = (None, FAILED)
            pkgs = [packages.Package(e, p) for e, p in (rc or {}).get("packages", [])]
            s4_st = s4_state(pkgs, rc["s4_states"]) if rc else FAILED
            dl = rc["downloads"].get(key) if rc else None
            hn_w = _pair(rc["hn"].get(key)) if rc else None
            hn_status = str(rc["hn_status"]) if rc else FAILED
            gn_w = _pair(gn["idx"].get(full.lower(), {}).get(key, [0, 0])) if gn_ok else None
            s5_st = worst(hn_status, str(gn["status"]))
            rows.append(signal_row(
                c, full, ai[c.id].category if c.id in ai else None,
                s2=(None, None, NONE), s3=s3, s4=(pkgs, dl, None, s4_st),
                s5=(hn_w, gn_w, s5_st), backfilled=True))
            for k, st in (("s3", s3[1]), ("s4", s4_st), ("s5", s5_st)):
                tally[k][st] = tally[k].get(st, 0) + 1
        states = {st for t in tally.values() for st in t if st != NONE}
        status = OK if states <= {OK} else (FAILED if states == {FAILED} else "partial")
        write_once(week_path("candidates", w, "json", data), json_text(
            [{"id": c.id, "full_name": name.get(c.id) or ai[c.id].full_name, "gain": c.gain,
              "gain_rank": c.gain_rank, "reason": c.reason} for c in cands]))
        write_once(week_path("signals", w, "csv", data), csv_text(SIGNAL_FIELDS, rows))
        write_once(week_path("runs", w, "json", data), json_text({
            "week": key, "backfill": True, "anchor": anchor.isoformat(), "candidates": len(cands),
            "status": status, "sources": tally, "geeknews": gn["status"],
            "started_at": started.isoformat(timespec="seconds")}))
        build_index(cfg, w, data=data)
        written.append(key)
        say(f"주 {key} 후보 {len(cands)} · {status}")

    finished = datetime.now(UTC) if now is None else now
    summary = {"anchor": anchor.isoformat(), "weeks": [w.isoformat() for w in weeks], "repos": len(first),
               "written_weeks": written, "skipped_weeks": skipped, "new_links": linked,
               "calls": dict(client.calls), "started_at": started.isoformat(timespec="seconds"),
               "finished_at": finished.isoformat(timespec="seconds"),
               "minutes": round((finished - started) / timedelta(minutes=1), 1)}
    write_mutable(cache_dir / "summary.json", json_text(summary))
    return summary
