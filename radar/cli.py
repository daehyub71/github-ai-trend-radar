"""명령줄 — python -m radar <contract|collect|weekly|index|backfill|site|blog|cards|notion> (PLAN §2)."""

import argparse
import json
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from radar.config import ConfigError, load_config
from radar.core.candidates import select_candidates
from radar.core.weeks import parse_week, target_week
from radar.inputs.startrend import ContractError, available_weeks, load_ai_repos, load_week_stars

EXIT_NOT_READY = 4  # star-trend 입력이 아직 그 주로 갱신되지 않았다 — 워크플로가 기다렸다 다시 본다
EXIT_DONE = 5  # 그 주는 이미 끝냈다(공개 데이터에 신호 파일이 있다) — 워크플로가 뒤 단계를 모두 건너뛴다(D26)


def _today() -> date:
    return datetime.now(UTC).date()


def _data_dir() -> Path:
    from radar.store import DATA

    return DATA


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


def _index(week_text: str | None) -> int:
    """이미 모은 signals 로 지수만 다시 낸다 (네트워크 없음)."""
    from radar import pipeline
    from radar.store import WriteOnceError

    try:
        cfg = load_config()
        week = parse_week(week_text) if week_text else available_weeks(cfg.startrend_dir)[-1]
        out = pipeline.build_index(cfg, week)
    except (ConfigError, ContractError, WriteOnceError, ValueError, FileNotFoundError) as e:
        print(f"지수 중단: {e}", file=sys.stderr)
        return 1
    for r in out["rows"][:pipeline.TOP_N]:
        print(f"{r['rank']:>3} {r['index']:>6} {r['full_name']}  (빠짐: {','.join(r['missing']) or '-'})")
    return 0


def _backfill(anchor_text: str | None, n: int, dry_run: bool) -> int:
    """12주 소급 (M2). --dry-run 은 호출 0 으로 예상치만. 이어 하기는 .work/backfill/ 캐시로."""
    from radar import backfill, pipeline
    from radar.clients.transport import UrllibTransport
    from radar.store import WriteOnceError

    try:
        cfg = load_config()
        anchor = parse_week(anchor_text) if anchor_text else available_weeks(cfg.startrend_dir)[-1]
        if dry_run:
            print(json.dumps(backfill.plan_backfill(cfg, anchor, n), ensure_ascii=False, indent=1))
            return 0
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            print("GITHUB_TOKEN 이 없다 — 이 명령에만 넘긴다", file=sys.stderr)
            return 1
        out = backfill.run_backfill(cfg, pipeline.make_client(UrllibTransport()), token, anchor, n,
                                    log=lambda m: print(m, flush=True))
    except (ConfigError, ContractError, WriteOnceError, ValueError) as e:
        print(f"소급 중단: {e}", file=sys.stderr)
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def _weekly(check_input: bool, dry_run: bool) -> int:
    """정기 주간 실행 (M3, SPEC F1·D6) — 지난 완료 주를 수집하고 지수까지 낸다.

    --check-input: star-trend 에 그 주 스타 파일이 있는지만 본다(없으면 종료 코드 4).
                   그 주를 이미 끝냈으면 종료 코드 5 — star-trend 신호 실행과 예약 실행이 겹쳐도 한 번만(D26).
    이미 수집한 주면 0 으로 끝난다(다시 돌려도 안전).
    """
    from radar import pipeline
    from radar.clients.transport import UrllibTransport
    from radar.store import WriteOnceError, week_path

    try:
        cfg = load_config()
        week = target_week(_today())
        if week not in available_weeks(cfg.startrend_dir):
            print(f"star-trend 입력이 아직 {week.isoformat()} 주로 갱신되지 않았다", file=sys.stderr)
            return EXIT_NOT_READY
        data = _data_dir()
        if check_input:
            if week_path("signals", week, "csv", data).exists():
                print(f"{week.isoformat()} 주는 이미 끝냈다 — 이번 실행은 건너뛴다")
                return EXIT_DONE
            print(f"입력 준비됨: {week.isoformat()}")
            return 0
        if dry_run:
            print(json.dumps(pipeline.plan_week(cfg, week, data=data), ensure_ascii=False, indent=1))
            return 0
        if week_path("signals", week, "csv", data).exists():
            print(f"{week.isoformat()} 주는 이미 수집했다 — 건너뛴다")
            return 0
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            print("GITHUB_TOKEN 이 없다 — 이 명령에만 넘긴다", file=sys.stderr)
            return 1
        rec = pipeline.collect_week(cfg, pipeline.make_client(UrllibTransport()), token, week, data=data)
    except (ConfigError, ContractError, WriteOnceError, ValueError) as e:
        print(f"주간 실행 중단: {e}", file=sys.stderr)
        return 1
    print(json.dumps({k: rec[k] for k in ("week", "status", "candidates", "sources", "geeknews", "calls")},
                     ensure_ascii=False, indent=1))
    return 0 if rec["status"] != "failed" else 1


def _week_arg(cfg_week: str | None) -> date:
    cfg = load_config()
    return parse_week(cfg_week) if cfg_week else available_weeks(cfg.startrend_dir)[-1]


def _blog(week_text: str | None, cap: float, dry_run: bool) -> int:
    """M5 — TOP 10 글·관점 노트 초안 (LLM 1회, 상한 cap 달러). 초안은 .private/ 에만."""
    from radar import blog
    from radar.clients.claude import ClaudeClient

    try:
        cfg = load_config()
        week = _week_arg(week_text)
        if dry_run:
            print(json.dumps(blog.plan(cfg, week), ensure_ascii=False, indent=1))
            return 0
        key = os.environ.get("STARTREND_ANTHROPIC_API_KEY", "")
        if not key:
            print("STARTREND_ANTHROPIC_API_KEY 가 없다 — 이 명령에만 넘긴다", file=sys.stderr)
            return 1
        rec = blog.write_drafts(cfg, week, ClaudeClient(key), cap=cap)
    except (ConfigError, ContractError, ValueError, FileNotFoundError) as e:
        print(f"초안 중단: {e}", file=sys.stderr)
        return 1
    print(json.dumps({k: rec[k] for k in ("week", "issue", "status", "reason", "cost_usd", "targets")}
                     | {"gated": len(rec["gated"])}, ensure_ascii=False, indent=1))
    return 0 if rec["status"] == "ok" else 1


def _cards(week_text: str | None, cap: float, dry_run: bool, only: list[str],
           images_only: bool = False) -> int:
    """M7 — 저장소 해설 (TOP 10 + 관점 저장소, LLM 저장소당 1회). 해설은 .private/ 에만 (D13)."""
    from radar import cards, pipeline
    from radar.clients.claude import ClaudeClient
    from radar.clients.transport import UrllibTransport

    try:
        week = _week_arg(week_text)
        if dry_run:
            print(json.dumps(cards.plan(week, cap=cap, only=only), ensure_ascii=False, indent=1))
            return 0
        key = os.environ.get("STARTREND_ANTHROPIC_API_KEY", "")
        token = os.environ.get("GITHUB_TOKEN", "")
        if images_only and token:
            picked = cards.pick_images(week, client=pipeline.make_client(UrllibTransport()), token=token,
                                       tavily_key=os.environ.get("STARTREND_TAVILY_API_KEY", ""), only=only)
            kinds: dict[str, int] = {}
            for v in picked.values():
                kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
            print(json.dumps({"week": week.isoformat(), "pictures": len(picked), "kinds": kinds},
                             ensure_ascii=False, indent=1))
            return 0
        if not key or not token:
            print("STARTREND_ANTHROPIC_API_KEY · GITHUB_TOKEN 이 필요하다 — 이 명령에만 넘긴다",
                  file=sys.stderr)
            return 1
        tavily = os.environ.get("STARTREND_TAVILY_API_KEY", "")
        if not tavily:
            print("STARTREND_TAVILY_API_KEY 가 없다 — 웹 검색 근거 없이 쓴다(D15 미충족)", file=sys.stderr)
        rec = cards.write_cards(week, ClaudeClient(key), client=pipeline.make_client(UrllibTransport()),
                                token=token, tavily_key=tavily, cap=cap, only=only)
    except (ConfigError, ContractError, ValueError, FileNotFoundError) as e:
        print(f"해설 중단: {e}", file=sys.stderr)
        return 1
    print(json.dumps({k: rec[k] for k in ("week", "targets", "ok", "skipped", "failed", "cost_usd",
                                          "tavily_credits")}, ensure_ascii=False, indent=1))
    return 0 if rec["failed"] == 0 else 1


def _images(week_text: str | None) -> int:
    """M8 — 글 그림(차트 4종 · 관점 저장소 카드) 뒤 초안에 그림을 넣어 다시 쓴다.

    네트워크·LLM 0, 비공개 저장소 초안 폴더에만.
    """
    from radar import blog, images

    try:
        week = _week_arg(week_text)
        rec = images.render_images(load_config(), week)
        drafted = (blog.PRIVATE / "weeks" / week.isoformat() / "blog" / "draft.json").exists()
        merged = blog.rewrite_drafts(week) if drafted else None
    except (ConfigError, ContractError, ValueError, FileNotFoundError) as e:
        print(f"그림 중단: {e}", file=sys.stderr)
        return 1
    print(json.dumps({"week": rec["week"], "charts": len(rec["files"]), "cards": len(rec["cards"]),
                      "intros": sum(1 for i in rec["intros"] if i["picture"]),
                      "drafts": (f"그림 넣어 다시 씀 · 해설 {merged['notes']}개 · 대표 이미지 "
                                 + ("있음" if merged["cover"] else "없음")) if merged else "초안 없음",
                      "observations": rec["observations"]}, ensure_ascii=False, indent=1))
    return 0


def _notion(week_text: str | None, parent: str | None) -> int:
    """M5 — 레이더 DB 만들기(--setup PARENT) 또는 그 주 초안 두 편 올리기."""
    from radar import blog, pipeline
    from radar.clients.transport import UrllibTransport
    from radar.publish.notion import NotionAPI, NotionError

    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        print("NOTION_TOKEN 이 없다 — 이 명령에만 넘긴다", file=sys.stderr)
        return 1
    api = NotionAPI(pipeline.make_client(UrllibTransport()), token)
    try:
        if parent:
            idx = blog.notion_setup(api, parent)
            print(f"레이더 DB 준비됨 (페이지 {len(idx.get('pages', {}))}개 기록)")
            return 0
        res = blog.publish_notion(api, _week_arg(week_text), log=print)
    except (NotionError, ConfigError, ContractError, ValueError, FileNotFoundError, KeyError) as e:
        print(f"Notion 중단: {e}", file=sys.stderr)
        return 1
    return 0 if all(not v.startswith("error") for v in res.values()) else 1


def _site() -> int:
    """사이트 파생 데이터 (네트워크 없음) — data/site/."""
    from radar.site import export_site

    try:
        out = export_site(load_config())
    except (ConfigError, ContractError, ValueError) as e:
        print(f"사이트 데이터 중단: {e}", file=sys.stderr)
        return 1
    print(f"사이트 데이터: 주 {out['weeks']} · 저장소 {out['repos']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="radar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("contract", help="star-trend 입력 계약 점검 (네트워크 없음)")
    col = sub.add_parser("collect", help="주간 신호 수집 (S2~S5)")
    col.add_argument("--week", help="주 시작일(일요일). 없으면 star-trend 최신 주")
    col.add_argument("--limit", type=int, help="후보 앞 N개만 (시험용)")
    col.add_argument("--dry-run", action="store_true", help="호출 없이 예상치만")
    ix = sub.add_parser("index", help="signals 로 종합 지수 계산 (네트워크 없음)")
    ix.add_argument("--week", help="주 시작일(일요일). 없으면 star-trend 최신 주")
    bf = sub.add_parser("backfill", help="12주 소급 (S1·S3·S4·S5, 포크 제외)")
    bf.add_argument("--anchor", help="이 주 바로 앞 주들을 소급한다(일요일). 없으면 star-trend 최신 주")
    bf.add_argument("--weeks", type=int, default=12, help="소급할 주 수 (기본 12)")
    bf.add_argument("--dry-run", action="store_true", help="호출 없이 예상치만")
    wk = sub.add_parser("weekly", help="정기 주간 실행 — 지난 완료 주 수집·지수 (Actions 크론)")
    wk.add_argument("--check-input", action="store_true", help="star-trend 입력이 그 주로 갱신됐는지만")
    wk.add_argument("--dry-run", action="store_true", help="호출 없이 예상치만")
    bl = sub.add_parser("blog", help="TOP 10 글·관점 노트 초안 (LLM, 비공개 저장소에만)")
    bl.add_argument("--week", help="주 시작일(일요일). 없으면 star-trend 최신 주")
    bl.add_argument("--cap", type=float, default=3.0, help="LLM 비용 상한(달러, D4 $3)")
    bl.add_argument("--dry-run", action="store_true", help="호출 없이 최악 비용만")
    cd = sub.add_parser("cards", help="저장소 해설 — TOP 10 + 관점 저장소 (LLM·웹 검색, 비공개 저장소에만)")
    cd.add_argument("--week", help="주 시작일(일요일). 없으면 star-trend 최신 주")
    cd.add_argument("--cap", type=float, default=3.0,
                    help="LLM 비용 상한(달러) — 그 주 초안 비용을 뺀 나머지를 쓴다")
    cd.add_argument("--dry-run", action="store_true", help="호출 없이 대상·예상 호출·비용만")
    cd.add_argument("--only", action="append", default=[], metavar="OWNER/NAME", help="이 저장소만 (여러 번)")
    cd.add_argument("--images-only", action="store_true",
                    help="LLM 없이 저장소 설명 그림만 고른다(근거 캐시 사용)")
    im = sub.add_parser("images",
                        help="글 그림 — 차트 4종·관점 저장소 카드 PNG (네트워크·LLM 0, 비공개 저장소에만)")
    im.add_argument("--week", help="주 시작일(일요일). 없으면 star-trend 최신 주")
    no = sub.add_parser("notion", help="초안을 Notion 레이더 DB 에 (상태 '초안'인 페이지만 고친다)")
    no.add_argument("--week", help="주 시작일(일요일). 없으면 star-trend 최신 주")
    no.add_argument("--setup", metavar="PARENT_PAGE_ID", help="레이더 DB 를 이 페이지 아래에 한 번 만든다")
    sub.add_parser("site", help="사이트 파생 데이터 data/site/ (네트워크 없음)")
    args = ap.parse_args(argv)
    if args.cmd == "contract":
        return _contract()
    if args.cmd == "collect":
        return _collect(args.week, args.limit, args.dry_run)
    if args.cmd == "site":
        return _site()
    if args.cmd == "blog":
        return _blog(args.week, args.cap, args.dry_run)
    if args.cmd == "cards":
        return _cards(args.week, args.cap, args.dry_run, args.only, args.images_only)
    if args.cmd == "images":
        return _images(args.week)
    if args.cmd == "notion":
        return _notion(args.week, args.setup)
    if args.cmd == "weekly":
        return _weekly(args.check_input, args.dry_run)
    if args.cmd == "backfill":
        return _backfill(args.anchor, args.weeks, args.dry_run)
    if args.cmd == "index":
        return _index(args.week)
    return 2
