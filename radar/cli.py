"""명령줄 — python -m radar <contract> (PLAN §2)."""

import argparse
import sys

from radar.config import ConfigError, load_config
from radar.core.candidates import select_candidates
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="radar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("contract", help="star-trend 입력 계약 점검 (네트워크 없음)")
    args = ap.parse_args(argv)
    if args.cmd == "contract":
        return _contract()
    return 2
