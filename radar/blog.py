"""M5 순서 (SPEC F7~F9, T5-3~T5-8) — 지수 이력 → 관점 → 사실 묶음 → LLM 1회 → 게이트 → 초안 → Notion.

M8(F11): 그림 단계(`radar images`)가 끝나면 `rewrite_drafts` 가 LLM 없이 초안에 그림을 넣어 다시 쓰고,
Notion 은 그림까지 올린다.

초안·해설·대응표는 비공개 저장소 작업 폴더(`.private/`, D7)에만 쓴다. 공개 `data/` 에는 쓰지 않는다.
"""

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from radar.clients.claude import FALLBACK_MODELS, LLMClient
from radar.config import PROJECT_ROOT, Config
from radar.core.angles import select_angles
from radar.core.charts_data import week_trend
from radar.inputs.startrend import load_ai_repos, load_categories
from radar.publish import drafts, notion
from radar.publish.budget import Budget, cost_usd, estimate_tokens
from radar.publish.facts import build_facts
from radar.publish.llm import build_request, explain, targets
from radar.store import DATA, json_text, week_path, write_mutable

PRIVATE = PROJECT_ROOT / ".private"
COVER_EXT = ("png", "jpg", "jpeg", "webp")
CAP_USD = 3.0  # D4


def _weeks(data: Path, week: date) -> list[dict[str, Any]]:
    files = sorted(f for f in (data / "index").glob("*.json") if f.stem <= week.isoformat())
    if not files or files[-1].stem != week.isoformat():
        raise FileNotFoundError(f"index/{week.isoformat()}.json 이 없다 — 지수를 먼저 낸다")
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


def _issue(data: Path, week: date) -> int:
    """연재 회차 = 소급이 아닌(정기 수집) 주의 순번."""
    n = 0
    for f in sorted((data / "runs").glob("*.json")):
        if f.stem > week.isoformat() or not f.stem[:4].isdigit() or len(f.stem) != 10:
            continue
        if not json.loads(f.read_text(encoding="utf-8")).get("backfill"):
            n += 1
    return max(n, 1)


def _meta(cfg: Config) -> dict[int, dict[str, Any]]:
    names = load_categories(cfg.startrend_dir)
    return {rid: {"description": m.description, "topics": list(m.topics), "language": m.language,
                  "category": names.get(m.category or "", m.category)}
            for rid, m in load_ai_repos(cfg.startrend_dir).items()}


def facts_for(cfg: Config, week: date, *, data: Path = DATA) -> dict[str, Any]:
    weeks = _weeks(data, week)
    angles = select_angles(weeks, cfg.angles)
    rules = {k: v for k, v in cfg.angles.__dict__.items() if k != "version"}
    trend = week_trend(weeks, load_categories(cfg.startrend_dir))
    return build_facts(weeks, angles, _meta(cfg), issue=_issue(data, week), angle_rules=rules, trend=trend)


def _art(blog: Path, week: date) -> dict[str, Any] | None:
    """그림 단계 결과(charts.json) — 그 주 것이 없으면 None(그림 자리 없이 쓴다, P7)."""
    p = blog / "charts" / "charts.json"
    if not p.exists():
        return None
    art = json.loads(p.read_text(encoding="utf-8"))
    return art if art.get("week") == week.isoformat() else None


def _notes(out: Path) -> dict[str, dict[str, Any]]:
    """그 주 저장소 해설(F10) 사본 — weeks/<주>/cards/*.json. 해설 단계 전이면 빈 묶음(D25)."""
    notes: dict[str, dict[str, Any]] = {}
    for p in sorted((out.parent / "cards").glob("*.json")):
        c = json.loads(p.read_text(encoding="utf-8")).get("card")
        if isinstance(c, dict) and c.get("full_name"):
            notes[c["full_name"]] = c
    return notes


def _cover(out: Path, stem: str) -> str | None:
    """사람이 만든 대표 이미지 — blog/gen/<stem>.<확장자> (D25)."""
    for ext in COVER_EXT:
        if (out / "gen" / f"{stem}.{ext}").is_file():
            return f"gen/{stem}.{ext}"
    return None


def _write(out: Path, f: dict[str, Any], texts: dict[str, str], art: dict[str, Any] | None) -> dict[str, Any]:
    notes, cover = _notes(out), _cover(out, "cover")
    write_mutable(out / "post.md", drafts.post_markdown(f, texts, art, notes=notes, cover=cover))
    write_mutable(out / "angles.md",
                  drafts.angles_markdown(f, texts, art, cover=_cover(out, "cover-angles")))
    return {"notes": len(notes), "cover": cover is not None}


def plan(cfg: Config, week: date, *, data: Path = DATA, model: str = "claude-sonnet-5-5") -> dict[str, Any]:
    """--dry-run — 호출 0. 최악 비용과 대상 수."""
    f = facts_for(cfg, week, data=data)
    req = build_request(f)
    models = (model, *FALLBACK_MODELS)
    worst = cost_usd(models, estimate_tokens(req.system + req.user) + 700, req.max_tokens)
    return {"week": week.isoformat(), "issue": f["issue"], "targets": len(targets(f)),
            "angles": {k: (v["status"], len(v["items"])) for k, v in f["angles"].items()},
            "input_bytes": len((req.system + req.user).encode()), "worst_usd": round(worst, 4),
            "cap_usd": CAP_USD}


def write_drafts(cfg: Config, week: date, llm: LLMClient, *, data: Path = DATA, private: Path = PRIVATE,
                 cap: float = CAP_USD) -> dict[str, Any]:
    """초안을 쓰고 기록을 돌려준다. LLM 이 실패해도 숫자 표만 있는 초안은 쓴다."""
    f = facts_for(cfg, week, data=data)
    com = explain(f, llm, Budget(cap))
    texts, report = drafts.gate_texts(com.texts, targets(f), f)
    out = private / "weeks" / week.isoformat() / "blog"
    _write(out, f, texts, _art(out, week))
    write_mutable(out / "facts.json", json_text(f))
    record = {"week": week.isoformat(), "issue": f["issue"], "status": com.status, "reason": com.reason,
              "model": com.model, "input_tokens": com.input_tokens, "output_tokens": com.output_tokens,
              "cost_usd": com.cost_usd, "cap_usd": cap, "targets": len(targets(f)), "gated": report,
              "texts": com.texts}
    write_mutable(out / "draft.json", json_text(record))
    return {k: v for k, v in record.items() if k != "texts"}


def rewrite_drafts(week: date, *, private: Path = PRIVATE) -> dict[str, Any]:
    """그림 단계 뒤 — 저장해 둔 사실 묶음·해설 글로 초안을 다시 쓴다(LLM 0, 게이트는 다시 거친다)."""
    out = private / "weeks" / week.isoformat() / "blog"
    f = json.loads((out / "facts.json").read_text(encoding="utf-8"))
    raw = json.loads((out / "draft.json").read_text(encoding="utf-8")).get("texts") or {}
    texts, _ = drafts.gate_texts(raw, targets(f), f)
    art = _art(out, week)
    merged = _write(out, f, texts, art)
    return {"week": week.isoformat(), "pictures": art is not None, **merged}


def _title(md: str) -> str:
    first = md.splitlines()[0] if md else ""
    return first.lstrip("# ").strip()


def publish_notion(api: notion.NotionAPI, week: date, *, private: Path = PRIVATE,
                   log: Callable[[str], None] | None = None) -> dict[str, str]:
    """비공개 초안 두 편을 Notion 레이더 DB 에 올린다(초안 상태만 고친다)."""
    say = log or (lambda _m: None)
    idx_file = private / "notion" / "index.json"
    idx: dict[str, Any] = json.loads(idx_file.read_text(encoding="utf-8")) if idx_file.exists() else {}
    blog = private / "weeks" / week.isoformat() / "blog"
    issue = int(json.loads((blog / "draft.json").read_text(encoding="utf-8"))["issue"])

    def save() -> None:
        write_mutable(idx_file, json_text(idx))

    result: dict[str, str] = {}
    for kind, name in (("TOP 10", "post.md"), ("관점", "angles.md")):
        md = (blog / name).read_text(encoding="utf-8")
        body, found = notion.local_images(md, blog)
        result[kind] = notion.upsert(api, idx, week=week.isoformat(), kind=kind, issue=issue,
                                     title=_title(md), markdown=body, save=save)
        if found and result[kind] in ("created", "updated"):
            page_id = idx["pages"][f"{week.isoformat()}:{kind}"]["page_id"]
            n = notion.attach_images(api, idx, page_id, found, save=save)
            result[kind] += f" · 그림 {n}/{len(found)}"
        say(f"Notion {kind}: {result[kind]}")
    save()
    return result


def notion_setup(api: notion.NotionAPI, parent_page_id: str, *, private: Path = PRIVATE) -> dict[str, Any]:
    idx_file = private / "notion" / "index.json"
    idx: dict[str, Any] = json.loads(idx_file.read_text(encoding="utf-8")) if idx_file.exists() else {}
    notion.setup(api, parent_page_id, idx)
    write_mutable(idx_file, json_text(idx))
    return idx


def runs_path(week: date, data: Path = DATA) -> Path:
    return week_path("runs", week, "json", data)
