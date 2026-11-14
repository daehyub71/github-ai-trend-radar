"""저장소 해설 — 요청 · JSON 스키마 · 파싱 · 게이트 · 사이트 사본 (SPEC F10-2 · TASKS T7-6).

한 저장소에 한 번 부른다. 근거는 신뢰하지 않는 데이터 태그로 감싸고(K10), 출력은 JSON 스키마로만 받는다.
게이트(코드)가 항목마다 확인한다 — 근거 번호(E1… 또는 사실 F)가 없거나, 링크·사실 밖 숫자·금지 표현이 있으면
그 항목을 뺀다. 사이트 사본 형식은 PLAN §4-1 (v1).
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from radar.clients.claude import LLMRequest
from radar.core import evidence as ev
from radar.core.untrusted import block
from radar.publish.gate import allowed_numbers, check

VERSION = 1
MAX_TOKENS = 8000
FACT = "F"
DOC_LIMITS = {"readme": 6000, "release": 1500, "comment": 600}
DOC_DEFAULT = 800
LABELS = ("푸는 문제", "구조", "쓰는 사람", "대안과 비교한 자리")
NATURES = ("소개", "호평", "논란", "질문", "없음")
CAPS = {"trend_notes": 4, "what": 4, "reactions": 3, "watch": 3}
STRONG_NATURES = ("논란", "호평")
NATURE_MIN_COMMENTS = 10  # 논란·호평은 그 주 글의 댓글 합이 이만큼은 있어야 한다(2026-11-14 검토 뒤)
PROMPT = (Path(__file__).parent / "prompt_card.md").read_text(encoding="utf-8")

_CLAIM_PROPS: dict[str, Any] = {
    "text": {"type": "string"},
    "sources": {"type": "array", "items": {"type": "string"}},
    "basis": {"type": "string", "enum": ["확인", "추정"]},
}
CLAIM: dict[str, Any] = {
    "type": "object",
    "properties": _CLAIM_PROPS,
    "required": ["text", "sources", "basis"],
    "additionalProperties": False,
}
LABELED: dict[str, Any] = {
    "type": "object",
    "properties": {"label": {"type": "string", "enum": list(LABELS)}, **_CLAIM_PROPS},
    "required": ["label", "text", "sources", "basis"],
    "additionalProperties": False,
}


def _obj(props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


SCHEMA: dict[str, Any] = _obj({
    "summary": _obj({"what": CLAIM, "why_now": CLAIM, "watch": CLAIM}),
    "trend_notes": {"type": "array", "items": CLAIM},
    "what": {"type": "array", "items": LABELED},
    "buzz": _obj({"nature": {"type": "string", "enum": list(NATURES)}, "trigger": CLAIM,
                  "reactions": {"type": "array", "items": CLAIM}, "reading": CLAIM}),
    "watch": {"type": "array", "items": CLAIM},
})


class CardError(Exception):
    """해설 응답을 읽지 못했다."""


def doc_block(i: int, d: ev.Evidence) -> str:
    day = (d.published_at or "")[:10] or "날짜 없음"
    info = ""
    if d.kind == "story":
        info = f" · 점수 {d.extra.get('points', 0)} · 댓글 {d.extra.get('comments', 0)}"
    elif d.kind == "comment":
        info = f" · 답글 {d.extra.get('replies', 0)}"
    elif d.kind == "topic":
        info = f" · 점수 {d.extra.get('points', 0)}"
    body = d.text[: DOC_LIMITS.get(d.kind, DOC_DEFAULT)]
    return f"[E{i}] {d.source} · {d.kind} · {day} · {ev.host(d.url)}{info}\n제목: {d.title}\n{body}".rstrip()


def build_request(facts: Mapping[str, Any], docs: Sequence[ev.Evidence]) -> LLMRequest:
    evidence = "\n\n".join(doc_block(i, d) for i, d in enumerate(docs, 1)) or "(근거 없음)"
    facts_text = json.dumps(facts, ensure_ascii=False, indent=1)
    user = (block("facts", facts_text) + "\n\n" + block("evidence", evidence)
            + "\n\n위 사실과 근거로 이 저장소의 해설을 정해진 JSON 형식으로 쓰세요.")
    return LLMRequest(system=PROMPT, user=user, schema=SCHEMA, max_tokens=MAX_TOKENS)


def parse(text: str) -> dict[str, Any]:
    try:
        raw = json.loads(text)
    except ValueError as e:
        raise CardError(f"JSON 이 아니다: {e}") from e
    if not isinstance(raw, dict):
        raise CardError("최상위가 객체가 아니다")
    if not isinstance(raw.get("summary"), dict) or not isinstance(raw.get("buzz"), dict):
        raise CardError("summary·buzz 가 없다")
    for k in ("trend_notes", "what", "watch"):
        if not isinstance(raw.get(k), list):
            raise CardError(f"{k} 가 목록이 아니다")
    return raw


@dataclass
class GateReport:
    checked: int = 0
    excluded: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"checked": self.checked, "excluded": len(self.excluded)}


def gate(raw: Mapping[str, Any], facts: Mapping[str, Any],
         docs: Sequence[ev.Evidence]) -> tuple[dict[str, Any], GateReport]:
    """빼야 할 항목을 빼고 정리한 해설과 보고. 빈 문장은 "없음"으로 보고 세지 않는다."""
    valid = {f"E{i}" for i in range(1, len(docs) + 1)} | {FACT}
    dates = [d.published_at[:10] for d in docs if d.published_at]
    allowed = allowed_numbers({"facts": facts, "dates": dates})
    report = GateReport()

    def claim(c: Any, where: str) -> dict[str, Any] | None:
        if not isinstance(c, Mapping):
            return None
        text = str(c.get("text") or "").strip()
        if not text:
            return None
        report.checked += 1
        srcs = [s for s in dict.fromkeys(str(x) for x in c.get("sources") or []) if s in valid]
        problems = ([] if srcs else ["출처 없음"]) + check(text, allowed)
        if problems:
            report.excluded.append({"where": where, "reason": "; ".join(problems), "text": text[:80]})
            return None
        basis = c.get("basis") if c.get("basis") in ("확인", "추정") else "추정"
        return {"text": text, "sources": srcs, "basis": basis}

    def many(items: Any, where: str, cap: int) -> list[dict[str, Any]]:
        out = [x for i, c in enumerate(items or []) if (x := claim(c, f"{where}[{i}]")) is not None]
        return out[:cap]

    s = raw.get("summary") or {}
    what: list[dict[str, Any]] = []
    for i, c in enumerate(raw.get("what") or []):
        if not isinstance(c, Mapping) or c.get("label") not in LABELS:
            continue
        if any(w["label"] == c["label"] for w in what):
            continue
        x = claim(c, f"what[{i}]")
        if x is not None:
            what.append({"label": c["label"], **x})
    b = raw.get("buzz") or {}
    nature = b.get("nature") if b.get("nature") in NATURES and b.get("nature") != "없음" else None
    posts = [p for p in facts.get("posts_this_week") or [] if isinstance(p, Mapping)]
    comments = sum(int(p.get("comments") or 0) for p in posts)
    if nature in STRONG_NATURES and comments < NATURE_MIN_COMMENTS:
        nature = "소개"  # 댓글 몇 개로 논란·호평이라 부르지 않는다
    clean = {
        "summary": {k: claim(s.get(k), f"summary.{k}") for k in ("what", "why_now", "watch")},
        "trend_notes": many(raw.get("trend_notes"), "trend_notes", CAPS["trend_notes"]),
        "what": what[: CAPS["what"]],
        "buzz": {"nature": nature, "trigger": claim(b.get("trigger"), "buzz.trigger"),
                 "reactions": many(b.get("reactions"), "buzz.reactions", CAPS["reactions"]),
                 "reading": claim(b.get("reading"), "buzz.reading")},
        "watch": many(raw.get("watch"), "watch", CAPS["watch"]),
    }
    return clean, report


def _cited(clean: Mapping[str, Any]) -> set[str]:
    out: set[str] = set()

    def walk(x: Any) -> None:
        if isinstance(x, Mapping):
            if isinstance(x.get("sources"), list):
                out.update(str(s) for s in x["sources"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(clean)
    return out


def site_card(clean: Mapping[str, Any], *, target: ev.Target, week: str, model: str, report: GateReport,
              docs: Sequence[ev.Evidence], posts: Sequence[Mapping[str, Any]],
              releases: Sequence[Mapping[str, str]], generated: str,
              history: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    """PLAN §4-1 사본 형식 v1. 근거 표에는 해설이 실제로 인용한 근거만 남긴다."""
    cited = _cited(clean)
    evidence = [{"id": f"E{i}", "title": ev.short_title(d.title), "site": ev.host(d.url),
                 "date": (d.published_at or "")[:10] or None, "url": d.url}
                for i, d in enumerate(docs, 1) if f"E{i}" in cited]
    why = (clean["summary"].get("why_now") or {}).get("text")
    hist = [dict(h) for h in history if h.get("week") != week]
    hist.append({"week": week, "why_now": why})
    return {
        "version": VERSION, "repo_id": target.repo_id, "full_name": target.full_name, "week": week,
        "generated": generated, "model": model, "gate": report.as_dict(),
        "summary": dict(clean["summary"]),
        "trend_notes": list(clean["trend_notes"]),
        "what": list(clean["what"]),
        "buzz": {"posts": [dict(p) for p in posts], **clean["buzz"]},
        "watch": list(clean["watch"]), "releases": [dict(r) for r in releases], "evidence": evidence,
        "history": sorted(hist, key=lambda h: str(h["week"]), reverse=True),
    }
