"""주간 수집 순서 (TASKS T1-6·T1-7, SPEC F1·F3).

입력 읽기 → 후보 선정 → S2 포크 스냅샷 → 패키지 연결(캐시) → 저장소마다 S3·S4·S5 → GeekNews 한 번 →
signals·스냅샷·실행 기록 저장. 한 신호가 실패해도 나머지는 계속 모으고 상태를 남긴다.
지수 계산(정규화·가중 평균)은 M2 에서 이 파일 위에 붙는다.
"""

import json
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from radar.clients.http import HttpClient, Policy
from radar.collectors import activity, forks, mentions, packages
from radar.collectors.base import FAILED, OK, PARTIAL, RepoRef
from radar.config import Config
from radar.core.candidates import select_candidates
from radar.core.models import Candidate
from radar.core.signals import fork_delta_checked
from radar.inputs.startrend import load_ai_repos, load_week_stars
from radar.store import (
    DATA,
    WriteOnceError,
    csv_text,
    json_text,
    read_csv,
    week_path,
    write_mutable,
    write_once,
)

# 종류별 요청 간격 — Search 분당 30회, GeekNews 2초(D12), pypistats 1초
POLICIES: dict[str, Policy] = {
    "gh_search": Policy(min_interval=2.1),
    "geeknews": Policy(min_interval=2.0, attempts=2),
    "pypistats": Policy(min_interval=1.0),
    "ecosystems": Policy(min_interval=0.2),
}
LINK_TTL_DAYS = 28
NONE = "none"  # 패키지가 없다 — 실패가 아니라 해당 없음

SIGNAL_FIELDS = (
    "repo_id", "full_name", "category", "gain_rank", "reason",
    "s1_stars_gain",
    "s2_forks", "s2_fork_delta", "s2_status",
    "s3_merged_prs", "s3_pr_authors", "s3_closed_issues", "s3_status",
    "s4_packages", "s4_downloads", "s4_dependents", "s4_status",
    "s5_hn_stories", "s5_hn_points", "s5_gn_topics", "s5_gn_points", "s5_status",
    "backfilled",
)
FORK_FIELDS = ("repo_id", "full_name", "forks", "stars", "archived", "status", "snapshot_at")


def _previous_top(data: Path, week: date) -> list[int]:
    f = week_path("index", week - timedelta(weeks=1), "json", data)
    if not f.exists():
        return []
    top = json.loads(f.read_text(encoding="utf-8")).get("top", [])
    return [int(x) for x in top]


def _candidates(cfg: Config, week: date, data: Path) -> tuple[list[Candidate], dict[int, Any]]:
    ai = load_ai_repos(cfg.startrend_dir)
    rows = load_week_stars(cfg.startrend_dir, week)
    cands = select_candidates(rows, ai.keys(), _previous_top(data, week)[: cfg.previous_top], cfg.cap)
    return cands, ai


def _load_links(data: Path) -> dict[str, Any]:
    f = data / "meta" / "packages.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def _needs_link(entry: Mapping[str, Any] | None, today: date) -> bool:
    if not entry:
        return True
    return (today - date.fromisoformat(str(entry["checked"]))).days >= LINK_TTL_DAYS


def plan_week(cfg: Config, week: date, *, data: Path = DATA, limit: int | None = None) -> dict[str, Any]:
    """--dry-run — 호출 0. 후보 수와 예상 호출 수."""
    cands, _ = _candidates(cfg, week, data)
    cands = cands[:limit] if limit else cands
    links = _load_links(data)
    today = datetime.now(UTC).date()
    uncached = sum(1 for c in cands if _needs_link(links.get(str(c.id)), today))
    known = sum(len(links.get(str(c.id), {}).get("packages", [])) for c in cands)
    n = len(cands)
    calls = {"gh_rest": n + 3 * uncached, "gh_search": 2 * n, "registry": 4 * uncached,
             "downloads": known, "hn": n, "geeknews": 8}
    minutes = (2 * n * POLICIES["gh_search"].min_interval + 8 * 2.0 + known * 1.0) / 60
    return {"week": week.isoformat(), "candidates": n, "uncached_links": uncached, "calls": calls,
            "min_minutes": round(minutes, 1)}


def _prev_forks(data: Path, week: date) -> tuple[dict[int, int], datetime | None]:
    f = week_path("meta/forks", week - timedelta(weeks=1), "csv", data)
    if not f.exists():
        return {}, None
    rows = read_csv(f)
    vals = {int(r["repo_id"]): int(r["forks"]) for r in rows if r["forks"]}
    at = next((datetime.fromisoformat(r["snapshot_at"]) for r in rows if r["snapshot_at"]), None)
    return vals, at


def _worst(*states: str) -> str:
    for s in (FAILED, PARTIAL):
        if s in states:
            return s
    return OK


def collect_week(cfg: Config, client: HttpClient, token: str, week: date, *, data: Path = DATA,
                 now: datetime | None = None, limit: int | None = None) -> dict[str, Any]:
    """그 주 신호를 모아 저장하고 실행 기록을 돌려준다. 주간 파일이 이미 있으면 WriteOnceError."""
    started = now or datetime.now(UTC)
    today = started.date()
    for kind, suffix in (("signals", "csv"), ("meta/forks", "csv")):
        f = week_path(kind, week, suffix, data)
        if f.exists():
            raise WriteOnceError(f"{kind}/{f.name} 이 이미 있다 — 주간 파일은 다시 쓰지 않는다")
    cands, ai = _candidates(cfg, week, data)
    cands = cands[:limit] if limit else cands
    weeks = [week]
    notes: list[str] = []

    # S2 포크 스냅샷 (ID 로 — 지금 이름도 여기서 얻는다)
    snaps = {s.id: s for s in forks.snapshot(client, token, [RepoRef(c.id, c.full_name) for c in cands])}
    prev, prev_at = _prev_forks(data, week)
    cur = {rid: s.forks for rid, s in snaps.items() if s.forks is not None}
    delta, delta_note = fork_delta_checked(prev, prev_at, cur, started)
    if delta_note:
        notes.append(f"S2: {delta_note}")
    name = {c.id: (snaps[c.id].full_name if c.id in snaps else c.full_name) for c in cands}

    # 패키지 연결 (4주 캐시)
    links = _load_links(data)
    for c in cands:
        if _needs_link(links.get(str(c.id)), today):
            lr = packages.link(client, token, name[c.id])
            links[str(c.id)] = {"checked": today.isoformat(), "full_name": name[c.id], "status": lr.status,
                                "packages": [[p.ecosystem, p.name] for p in lr.packages]}

    gn_idx, gn_status, gn_note = mentions.geeknews_index(client, weeks)
    if gn_note:
        notes.append(f"GeekNews: {gn_note}")

    rows: list[dict[str, Any]] = []
    dep_rows: list[dict[str, Any]] = []
    tally: dict[str, dict[str, int]] = {k: {OK: 0, PARTIAL: 0, FAILED: 0} for k in ("s2", "s3", "s4", "s5")}
    tally["s4"][NONE] = 0
    for c in cands:
        full = name[c.id]
        snap = snaps.get(c.id)
        s2_status = snap.status if snap else FAILED
        if snap and snap.note:
            notes.append(f"{full} S2: {snap.note}")

        act = activity.collect(client, token, full, weeks)
        wa = act.weekly.get(week)
        if act.note:
            notes.append(f"{full} S3: {act.note}")

        pkgs = [packages.Package(e, n) for e, n in links.get(str(c.id), {}).get("packages", [])]
        dl_total: int | None = None
        dep_total: int | None = None
        s4_states: list[str] = []
        for p in pkgs:
            got, st = packages.weekly_downloads(client, p, weeks)
            s4_states.append(st)
            v = got.get(week)
            if v is not None:
                dl_total = (dl_total or 0) + v
            dep = packages.dependents(client, p)
            dep_rows.append({"repo_id": c.id, "ecosystem": p.ecosystem, "name": p.name, "dependents": dep})
            if dep is not None:
                dep_total = (dep_total or 0) + dep
        if not pkgs:
            s4_status = NONE
        elif all(s == FAILED for s in s4_states):
            s4_status = FAILED
        else:
            s4_status = _worst(*s4_states)

        hn, hn_status = mentions.hn_mentions(client, full, weeks)
        gn = gn_idx.get(full.lower(), {}).get(week, (0, 0)) if gn_status != FAILED else None
        s5_status = _worst(hn_status, gn_status)
        hn_w = hn.get(week)

        rows.append({
            "repo_id": c.id, "full_name": full, "category": ai[c.id].category if c.id in ai else None,
            "gain_rank": c.gain_rank, "reason": c.reason, "s1_stars_gain": c.gain,
            "s2_forks": snap.forks if snap else None, "s2_fork_delta": delta.get(c.id),
            "s2_status": s2_status,
            "s3_merged_prs": wa.merged_prs if wa else None, "s3_pr_authors": wa.pr_authors if wa else None,
            "s3_closed_issues": wa.closed_issues if wa else None, "s3_status": act.status,
            "s4_packages": " ".join(f"{p.ecosystem}:{p.name}" for p in pkgs) or None,
            "s4_downloads": dl_total, "s4_dependents": dep_total, "s4_status": s4_status,
            "s5_hn_stories": hn_w[0] if hn_w else None, "s5_hn_points": hn_w[1] if hn_w else None,
            "s5_gn_topics": gn[0] if gn else (0 if gn is not None else None),
            "s5_gn_points": gn[1] if gn else (0 if gn is not None else None),
            "s5_status": s5_status, "backfilled": 0,
        })
        for key, st in (("s2", s2_status), ("s3", act.status), ("s4", s4_status), ("s5", s5_status)):
            tally[key][st] += 1

    finished = datetime.now(UTC) if now is None else now
    snap_at = started.isoformat(timespec="seconds")
    fork_rows = [{"repo_id": s.id, "full_name": s.full_name, "forks": s.forks, "stars": s.stars,
                  "archived": None if s.archived is None else int(s.archived), "status": s.status,
                  "snapshot_at": snap_at} for s in snaps.values()]
    states = [st for k, t in tally.items() for st, n in t.items() if n and st != NONE]
    status = OK if set(states) <= {OK} else (FAILED if set(states) == {FAILED} else PARTIAL)
    record = {"week": week.isoformat(), "started_at": snap_at,
              "finished_at": finished.isoformat(timespec="seconds"), "candidates": len(cands),
              "status": status, "sources": tally, "geeknews": gn_status, "calls": dict(client.calls),
              "notes": notes[:100]}

    write_once(week_path("candidates", week, "json", data), json_text(
        [{"id": c.id, "full_name": name[c.id], "gain": c.gain, "gain_rank": c.gain_rank, "reason": c.reason}
         for c in cands]))
    write_once(week_path("meta/forks", week, "csv", data), csv_text(FORK_FIELDS, fork_rows))
    write_once(week_path("meta/dependents", week, "csv", data),
               csv_text(("repo_id", "ecosystem", "name", "dependents"), dep_rows))
    write_mutable(data / "meta" / "packages.json", json_text(links))
    write_once(week_path("signals", week, "csv", data), csv_text(SIGNAL_FIELDS, rows))
    write_once(week_path("runs", week, "json", data), json_text(record))
    return record


def make_client(transport: Any, policies: Mapping[str, Policy] | None = None) -> HttpClient:
    return HttpClient(transport, policies=policies or POLICIES)

