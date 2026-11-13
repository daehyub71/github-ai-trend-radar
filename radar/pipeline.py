"""주간 수집 순서 (TASKS T1-6·T1-7, SPEC F1·F3).

입력 읽기 → 후보 선정 → S2 포크 스냅샷 → 패키지 연결(캐시) → 저장소마다 S3·S4·S5 → GeekNews 한 번 →
signals·스냅샷·실행 기록 저장. 한 신호가 실패해도 나머지는 계속 모으고 상태를 남긴다.
수집이 끝나면 정규화·지수(build_index)로 index/<주>.json 을 쓴다(M2).
"""

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from radar.clients.http import HttpClient, Policy
from radar.collectors import activity, forks, mentions, packages
from radar.collectors.base import FAILED, OK, PARTIAL, RepoRef
from radar.config import Config
from radar.core.candidates import select_candidates
from radar.core.index import compute, rank, signal_percentiles
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
    "notion": Policy(min_interval=0.34),  # 초당 3회 미만
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


def previous_top(data: Path, week: date) -> list[int]:
    """지난주 index 의 종합 TOP (없으면 빈 목록)."""
    f = week_path("index", week - timedelta(weeks=1), "json", data)
    if not f.exists():
        return []
    top = json.loads(f.read_text(encoding="utf-8")).get("top", [])
    return [int(x) for x in top]


def _candidates(cfg: Config, week: date, data: Path) -> tuple[list[Candidate], dict[int, Any]]:
    ai = load_ai_repos(cfg.startrend_dir)
    rows = load_week_stars(cfg.startrend_dir, week)
    cands = select_candidates(rows, ai.keys(), previous_top(data, week)[: cfg.previous_top], cfg.cap)
    return cands, ai


def load_links(data: Path) -> dict[str, Any]:
    f = data / "meta" / "packages.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def needs_link(entry: Mapping[str, Any] | None, today: date) -> bool:
    if not entry:
        return True
    return (today - date.fromisoformat(str(entry["checked"]))).days >= LINK_TTL_DAYS


def plan_week(cfg: Config, week: date, *, data: Path = DATA, limit: int | None = None) -> dict[str, Any]:
    """--dry-run — 호출 0. 후보 수와 예상 호출 수."""
    cands, _ = _candidates(cfg, week, data)
    cands = cands[:limit] if limit else cands
    links = load_links(data)
    today = datetime.now(UTC).date()
    uncached = sum(1 for c in cands if needs_link(links.get(str(c.id)), today))
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


def worst(*states: str) -> str:
    """가장 나쁜 상태 (failed > partial > ok)."""
    for s in (FAILED, PARTIAL):
        if s in states:
            return s
    return OK


def s4_state(pkgs: Sequence[packages.Package], states: Sequence[str]) -> str:
    """패키지가 없으면 none, 모두 실패면 failed, 아니면 가장 나쁜 상태."""
    if not pkgs:
        return NONE
    if all(s == FAILED for s in states):
        return FAILED
    return worst(*states)


def signal_row(c: Candidate, full: str, category: str | None, *,
               s2: tuple[int | None, int | None, str],
               s3: tuple[activity.WeekActivity | None, str],
               s4: tuple[Sequence[packages.Package], int | None, int | None, str],
               s5: tuple[tuple[int, int] | None, tuple[int, int] | None, str],
               backfilled: bool) -> dict[str, Any]:
    """signals CSV 한 행 — 주간 수집과 소급이 같은 형식을 쓴다(F5)."""
    forks_n, fork_delta, s2_status = s2
    wa, s3_status = s3
    pkgs, dl, dep, s4_status = s4
    hn_w, gn, s5_status = s5
    return {
        "repo_id": c.id, "full_name": full, "category": category,
        "gain_rank": c.gain_rank, "reason": c.reason, "s1_stars_gain": c.gain,
        "s2_forks": forks_n, "s2_fork_delta": fork_delta, "s2_status": s2_status,
        "s3_merged_prs": wa.merged_prs if wa else None, "s3_pr_authors": wa.pr_authors if wa else None,
        "s3_closed_issues": wa.closed_issues if wa else None, "s3_status": s3_status,
        "s4_packages": " ".join(f"{p.ecosystem}:{p.name}" for p in pkgs) or None,
        "s4_downloads": dl, "s4_dependents": dep, "s4_status": s4_status,
        "s5_hn_stories": hn_w[0] if hn_w else None, "s5_hn_points": hn_w[1] if hn_w else None,
        "s5_gn_topics": gn[0] if gn else None, "s5_gn_points": gn[1] if gn else None,
        "s5_status": s5_status, "backfilled": int(backfilled),
    }


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
    links = load_links(data)
    for c in cands:
        if needs_link(links.get(str(c.id)), today):
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
        s4_status = s4_state(pkgs, s4_states)

        hn, hn_status = mentions.hn_mentions(client, full, weeks)
        gn = gn_idx.get(full.lower(), {}).get(week, (0, 0)) if gn_status != FAILED else None
        s5_status = worst(hn_status, gn_status)
        hn_w = hn.get(week)

        rows.append(signal_row(
            c, full, ai[c.id].category if c.id in ai else None,
            s2=(snap.forks if snap else None, delta.get(c.id), s2_status),
            s3=(wa, act.status), s4=(pkgs, dl_total, dep_total, s4_status),
            s5=(hn_w, gn, s5_status), backfilled=False))
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
    build_index(cfg, week, data=data)
    return record


TOP_N = 10


def _r(v: float | None) -> float | None:
    return None if v is None else round(v, 2)


def build_index(cfg: Config, week: date, *, data: Path = DATA) -> dict[str, Any]:
    """signals/<주>.csv → index/<주>.json (SPEC F4). 같은 입력이면 같은 파일, 다른 가중치로 덮어쓰지 않는다.

    신호가 실패한 저장소도 남은 신호로 지수를 낸다(결측 재분배).
    """
    rows = read_csv(week_path("signals", week, "csv", data))
    pcts = signal_percentiles(rows)
    idx = compute(pcts, cfg.weights)
    by_id = {int(r["repo_id"]): r for r in rows}
    # 지난주 TOP 보충 저장소는 그 주 스타 순위가 없을 수 있다 → 동점이면 맨 뒤
    order = rank(idx, {rid: int(r["gain_rank"]) for rid, r in by_id.items() if r["gain_rank"]})
    out_rows = [{
        "rank": i + 1, "repo_id": rid, "full_name": by_id[rid]["full_name"],
        "category": by_id[rid]["category"] or None,
        "gain_rank": int(by_id[rid]["gain_rank"]) if by_id[rid]["gain_rank"] else None,
        "index": _r(idx[rid].index),
        "pct": {k: _r(pcts[k].get(rid)) for k in cfg.weights},
        "contrib": {k: round(v, 2) for k, v in idx[rid].contrib.items()},
        "missing": list(idx[rid].missing), "backfilled": by_id[rid]["backfilled"] == "1",
    } for i, rid in enumerate(order)]
    out = {"week": week.isoformat(), "weights_version": cfg.weights_version, "weights": dict(cfg.weights),
           "candidates": len(rows), "top": [r["repo_id"] for r in out_rows[:TOP_N]], "rows": out_rows}
    write_once(week_path("index", week, "json", data), json_text(out))
    return out


def make_client(transport: Any, policies: Mapping[str, Policy] | None = None) -> HttpClient:
    return HttpClient(transport, policies=policies or POLICIES)

