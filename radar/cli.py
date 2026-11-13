"""명령줄 — python -m radar <contract> (PLAN §2)."""

import argparse
import json
import os
import sys

from radar.config import ConfigError, load_config
from radar.core.candidates import select_candidates
from radar.core.weeks import parse_week
from radar.inputs.startrend import ContractError, available_weeks, load_ai_repos, load_week_stars


def _contract() -> int:
    """star-trend 입력 계약 점검 — 네트워크 없이 최신 주 후보까지 만들어 본다."""
    try:
        cfg = load_config()
        ai = load_ai_repos(cfg.startrend_dir)
        weeks = available_weeks(cfg.startrend_dir)
        if not weeks:
            raise ContractError("주간 스타 파일이 없다")
        week = weeks[-1]
        rows = load_week_stars(cfg.startrend_dir, week)
    except (ConfigError, ContractError) as e:
        print(f"입력 계약 위반: {e}", file=sys.stderr)
        return 1
    cands = select_candidates(rows, ai_ids=ai.keys(), previous_top=[], cap=cfg.cap)
    ai_rows = sum(1 for r in rows if r.id in ai)
    cutoff = cands[-1].gain if cands else 0
    print(f"AI 저장소 {len(ai)} · 주 {len(weeks)}개 (최신 {week.isoformat()})")
    print(f"최신 주 스타 파일 {len(rows)}행 · 그중 AI {ai_rows} · 후보 {len(cands)} (마지막 +{cutoff})")
    return 0


def _collect(week_text: str | None, limit: int | None, dry_run: bool) -> int:
    """주간 신호 수집 (M1). --dry-run 은 호출 0 으로 예상치만 보인다."""
    from radar import pipeline
    from radar.clients.transport import UrllibTransport
    from radar.store import WriteOnceError

    try:
        cfg = load_config()
        week = parse_week(week_text) if week_text else available_weeks(cfg.startrend_dir)[-1]
        if dry_run:
            print(json.dumps(pipeline.plan_week(cfg, week, limit=limit), ensure_ascii=False, indent=1))
            return 0
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            print("GITHUB_TOKEN 이 없다 — 이 명령에만 넘긴다", file=sys.stderr)
            return 1
        rec = pipeline.collect_week(cfg, pipeline.make_client(UrllibTransport()), token, week, limit=limit)
    except (ConfigError, ContractError, WriteOnceError, ValueError) as e:
        print(f"수집 중단: {e}", file=sys.stderr)
        return 1
    print(json.dumps({k: rec[k] for k in ("week", "status", "candidates", "sources", "geeknews", "calls")},
                     ensure_ascii=False, indent=1))
    return 0 if rec["status"] != "failed" else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="radar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("contract", help="star-trend 입력 계약 점검 (네트워크 없음)")
    col = sub.add_parser("collect", help="주간 신호 수집 (S2~S5)")
    col.add_argument("--week", help="주 시작일(일요일). 없으면 star-trend 최신 주")
    col.add_argument("--limit", type=int, help="후보 앞 N개만 (시험용)")
    col.add_argument("--dry-run", action="store_true", help="호출 없이 예상치만")
    args = ap.parse_args(argv)
    if args.cmd == "contract":
        return _contract()
    if args.cmd == "collect":
        return _collect(args.week, args.limit, args.dry_run)
    return 2
