"""사실 묶음 (SPEC F7·F9) — 글에 들어갈 숫자는 모두 여기서 코드가 확정한다. LLM 은 이 묶음만 본다."""

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Any

SERIES = "깃허브 AI 트렌드 레이더"
SIGNAL_NAMES = {"s1": "스타", "s2": "포크", "s3": "기여", "s4": "사용", "s5": "언급"}
ANGLE_NAMES = {"A": "조용한 강자", "B": "반짝 관심", "C": "꾸준한 상승", "D": "신호 전환"}
TOP_N = 10


def repo_url(full_name: str) -> str:
    return f"https://github.com/{full_name}"


def _meta(meta: Mapping[int, Mapping[str, Any]], rid: int) -> dict[str, Any]:
    m = meta.get(rid, {})
    return {"description": m.get("description"), "topics": list(m.get("topics") or [])[:8],
            "language": m.get("language"), "category": m.get("category")}


def build_facts(weeks: Sequence[Mapping[str, Any]], angles: Mapping[str, Any],
                meta: Mapping[int, Mapping[str, Any]], *, issue: int,
                angle_rules: Mapping[str, Any] | None = None, trend: Sequence[str] = ()) -> dict[str, Any]:
    """weeks: index/<주>.json 들(오래된 순, 마지막이 이번 주). meta: 저장소 ID → 설명·카테고리 이름.

    Args:
        weeks: 지수 파일들.
        angles: core.angles.select_angles 결과.
        meta: 저장소 메타(설명·토픽·언어·카테고리 표시 이름).
        issue: 연재 회차.
        angle_rules: 관점 유형 임계값(글에서 규칙을 설명할 때 쓰는 숫자).
        trend: 12주 트렌드 관찰 문장(코드가 쓴 것, F11 "트렌드 분석").

    Returns:
        사실 묶음.
    """
    cur = weeks[-1]
    prev = weeks[-2] if len(weeks) > 1 else None
    prev_rank = {r["repo_id"]: r["rank"] for r in prev["rows"]} if prev else {}
    prev_top = [r for r in prev["rows"][:TOP_N]] if prev else []
    start = date.fromisoformat(cur["week"])
    top = []
    for r in cur["rows"][:TOP_N]:
        top.append({
            "rank": r["rank"], "prev_rank": prev_rank.get(r["repo_id"]), "repo": r["full_name"],
            "url": repo_url(r["full_name"]), "index": r["index"], "star_rank": r["gain_rank"],
            "pct": r["pct"], "contrib": r["contrib"],
            "missing": [SIGNAL_NAMES[s] for s in r["missing"]], **_meta(meta, r["repo_id"]),
        })
    now_rank = {r["repo_id"]: r["rank"] for r in cur["rows"]}
    dropped = [{"repo": r["full_name"], "prev_rank": r["rank"], "now_rank": now_rank.get(r["repo_id"])}
               for r in prev_top if now_rank.get(r["repo_id"], TOP_N + 1) > TOP_N]
    by_id = {r["repo_id"]: r for r in cur["rows"]}
    ang: dict[str, Any] = {}
    for key in ("A", "B", "C", "D"):
        a = angles[key]
        ang[key] = {"name": ANGLE_NAMES[key], "status": a["status"], "items": [
            {"repo": it["full_name"], "url": repo_url(it["full_name"]), "evidence": it["evidence"],
             "rank": by_id[it["repo_id"]]["rank"], "index": by_id[it["repo_id"]]["index"],
             **_meta(meta, it["repo_id"])} for it in a["items"]]}
    return {
        "series": SERIES, "issue": issue, "week": cur["week"],
        "week_end": (start + timedelta(days=6)).isoformat(),
        "weights": cur["weights"], "weights_version": cur["weights_version"],
        "candidates": cur["candidates"], "history_weeks": len(weeks),
        "top10": top, "dropped": dropped, "angles": ang, "trend": {"observations": list(trend)},
        "rules": {"top_n": TOP_N, "backfill_weeks": 12, "angles": dict(angle_rules or {})},
    }
