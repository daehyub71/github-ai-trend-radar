"""사이트 파생 데이터 (SPEC F6, DESIGN §1, TASKS T4-3) — 웹은 data/site/ 의 작은 파일만 읽는다.

- weeks.json: 주 목록(최신 먼저, 소급 표시·회차)
- week/<주>.json: 종합 TOP 10 · 신호별 TOP 5 · 관점 노트(숫자만) · 숫자 카드
- repo/<id>.json: 저장소 설명(star-trend 공개 메타) · 최신 신호·원값 · 주별 이력
LLM 글(해설·초안)은 넣지 않는다(D7 — 비공개 저장소에만).
"""

import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from radar.config import Config
from radar.core.angles import select_angles
from radar.inputs.startrend import load_ai_repos, load_categories
from radar.store import DATA, json_text, read_csv, week_path, write_mutable

SIGNALS = ("s1", "s2", "s3", "s4", "s5")
TOP_N = 10
BY_SIGNAL_N = 5
RAW_FIELDS = (
    "s1_stars_gain",
    "s2_forks",
    "s2_fork_delta",
    "s3_merged_prs",
    "s3_pr_authors",
    "s3_closed_issues",
    "s4_packages",
    "s4_downloads",
    "s4_dependents",
    "s5_hn_stories",
    "s5_hn_points",
    "s5_gn_topics",
    "s5_gn_points",
)
STATUS_FIELDS = ("s2_status", "s3_status", "s4_status", "s5_status")


def _num(v: str) -> int | float | str | None:
    if v == "":
        return None
    try:
        f = float(v)
    except ValueError:
        return v
    return int(f) if f.is_integer() else f


def _load_weeks(data: Path) -> list[dict[str, Any]]:
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted((data / "index").glob("*.json"))]


def _backfilled(w: Mapping[str, Any]) -> bool:
    return bool(w["rows"]) and all(r.get("backfilled") for r in w["rows"])


def export_site(cfg: Config, *, data: Path = DATA) -> dict[str, int]:
    weeks = _load_weeks(data)
    names = load_categories(cfg.startrend_dir)
    meta = load_ai_repos(cfg.startrend_dir)
    site = data / "site"
    issue = 0
    listing: list[dict[str, Any]] = []
    history: dict[int, list[dict[str, Any]]] = {}
    latest: dict[int, dict[str, Any]] = {}
    for i, w in enumerate(weeks):
        bf = _backfilled(w)
        issue += 0 if bf else 1
        prev = {r["repo_id"]: r["rank"] for r in weeks[i - 1]["rows"]} if i else {}
        sig_file = week_path("signals", date.fromisoformat(w["week"]), "csv", data)
        raw = {int(r["repo_id"]): r for r in read_csv(sig_file)} if sig_file.exists() else {}

        def row(r: Mapping[str, Any], prev: Mapping[int, int] = prev) -> dict[str, Any]:
            return {
                "rank": r["rank"],
                "repo_id": r["repo_id"],
                "full_name": r["full_name"],
                "category": names.get(r["category"] or "", r["category"]),
                "index": r["index"],
                "pct": r["pct"],
                "contrib": r["contrib"],
                "missing": r["missing"],
                "star_rank": r["gain_rank"],
                "prev_rank": prev.get(r["repo_id"]),
            }

        rows = w["rows"]
        by_signal = {
            s: [
                {"repo_id": r["repo_id"], "full_name": r["full_name"], "pct": r["pct"][s]}
                for r in sorted(
                    (r for r in rows if r["pct"][s] is not None), key=lambda r: (-r["pct"][s], r["rank"])
                )[:BY_SIGNAL_N]
            ]
            for s in SIGNALS
        }
        ang = select_angles(weeks[: i + 1], cfg.angles)
        star_top = {r["repo_id"] for r in rows if r["gain_rank"] is not None and r["gain_rank"] <= TOP_N}
        stats = {
            "candidates": w["candidates"],
            "star_top_in_index_top": len(star_top & set(w["top"][:TOP_N])),
            "with_packages": sum(1 for r in rows if r["pct"]["s4"] is not None),
        }
        doc = {
            "week": w["week"],
            "backfilled": bf,
            "issue": None if bf else issue,
            "weights": w["weights"],
            "weights_version": w["weights_version"],
            "stats": stats,
            "top10": [row(r) for r in rows[:TOP_N]],
            "by_signal": by_signal,
            "angles": {
                k: {
                    "status": v["status"],
                    "items": [
                        {"repo_id": it["repo_id"], "full_name": it["full_name"], "evidence": it["evidence"]}
                        for it in v["items"]
                    ],
                }
                for k, v in ang.items()
                if k in ("A", "B", "C", "D")
            },
        }
        write_mutable(site / "week" / f"{w['week']}.json", json_text(doc))
        listing.append(
            {
                "week": w["week"],
                "backfilled": bf,
                "issue": doc["issue"],
                "candidates": w["candidates"],
                "top1": rows[0]["full_name"] if rows else None,
            }
        )
        for r in rows:
            rid = r["repo_id"]
            history.setdefault(rid, []).append(
                {
                    "week": w["week"],
                    "backfilled": bf,
                    "rank": r["rank"],
                    "index": r["index"],
                    "contrib": r["contrib"],
                }
            )
            rr = raw.get(rid, {})
            latest[rid] = {
                **row(r),
                "week": w["week"],
                "backfilled": bf,
                "raw": {k: _num(rr.get(k, "")) for k in RAW_FIELDS},
                "status": {k: rr.get(k) or None for k in STATUS_FIELDS},
            }
    write_mutable(site / "weeks.json", json_text(list(reversed(listing))))
    for rid, hist in history.items():
        m = meta.get(rid)
        doc = {
            "repo_id": rid,
            "full_name": latest[rid]["full_name"],
            "category": latest[rid]["category"],
            "description": m.description if m else None,
            "topics": list(m.topics) if m else [],
            "language": m.language if m else None,
            "latest": latest[rid],
            "history": hist,
        }
        write_mutable(site / "repo" / f"{rid}.json", json_text(doc))
    return {"weeks": len(weeks), "repos": len(history)}
