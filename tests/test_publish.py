"""M5 — 게이트 통제군·초안·예산·Notion 초안만 갱신 (SPEC F7~F9, TASKS T5-2~T5-8). 네트워크·과금 0."""

import json
from typing import Any

from radar.clients.claude import LLMResponse, MockLLM
from radar.core.angles import select_angles
from radar.publish import drafts, notion
from radar.publish.budget import Budget
from radar.publish.facts import build_facts
from radar.publish.gate import allowed_numbers, check
from radar.publish.llm import explain, targets
from tests.fakes import FakeTransport, ok, status
from tests.test_http import _client

RULES = {"a_star_max": 50.0, "a_use_min": 80.0, "b_attention_min": 90.0, "b_use_max": 30.0, "c_rises": 4,
         "lookback": 4, "d_shift_min": 20.0, "cap": 5}


def _row(rid, rank, index, s4=None):
    pct = {"s1": 90.0 - rid, "s2": None, "s3": 85.0, "s4": s4, "s5": 47.5}
    contrib = {"s1": 20.0, "s2": 0.0, "s3": 30.0, "s4": 0.0 if s4 is None else 10.0, "s5": 10.0}
    return {"rank": rank, "repo_id": rid, "full_name": f"org/r{rid}", "category": "mcp-tools",
            "gain_rank": rid, "index": index, "pct": pct, "contrib": contrib,
            "missing": ["s2"] + ([] if s4 is not None else ["s4"]), "backfilled": False}


def _weeks():
    w1 = {"week": "2026-10-25", "weights": {"s1": 15, "s2": 15, "s3": 25, "s4": 30, "s5": 15},
          "weights_version": 1, "candidates": 200, "rows": [_row(i, i, 70.0 - i) for i in range(1, 13)]}
    rows2 = [_row(i, i, 72.5 - i, s4=60.0 if i == 2 else None) for i in range(2, 14)]
    w2 = dict(w1, week="2026-11-01", rows=rows2)
    return [w1, w2]


def _facts():
    weeks = _weeks()
    meta = {2: {"description": "MCP server for Qwen3 agents", "topics": ["mcp"], "language": "Python",
                "category": "MCP 서버·도구"}}
    return build_facts(weeks, select_angles(weeks), meta, issue=1, angle_rules=RULES)


def test_publish_facts_rank_change_and_dropped():
    f = _facts()
    assert f["week_end"] == "2026-11-07" and len(f["top10"]) == 10
    first = f["top10"][0]
    assert (first["repo"], first["rank"], first["prev_rank"]) == ("org/r2", 2, 2)
    assert first["description"].startswith("MCP") and first["missing"] == ["포크"]
    assert {d["repo"] for d in f["dropped"]} == {"org/r1"}  # 지난주 1위가 이번 주 후보 밖
    assert f["angles"]["C"]["status"] == "insufficient"


def test_publish_gate_control_group_catches_numbers_links_and_wording():
    f = _facts()
    allowed = allowed_numbers(f)
    assert check("이번 주 2위에 오른 org/r2 는 지수 70.5 입니다. Qwen3 를 씁니다.", allowed) == []
    assert check("11월 1일부터 7일까지 TOP 10", allowed) == []
    assert check("지수가 지난주보다 3.7 올랐습니다", allowed) == ["숫자 3.7"]      # 계산해서 만든 숫자
    assert check("자세한 내용은 https://example.com 에서", allowed) == ["링크"]
    assert check("이건 거품입니다", allowed) == ["표현 '거품'"]
    assert check("반드시 써야 할 도구", allowed) == ["표현 '반드시'"]


def _reply(fn):
    return lambda req: LLMResponse(json.dumps({"items": fn(req)}, ensure_ascii=False), "end_turn",
                                   "claude-sonnet-5-5", 1000, 500)


def test_publish_drafts_fill_tables_and_gate_bad_paragraphs():
    f = _facts()
    want = targets(f)

    def items(_req):
        out = [{"target": t, "text": "관측한 내용입니다."} for t in want]
        out[0] = {"target": "title:1", "text": "다섯 신호로 본 첫 주"}
        out[3] = {"target": "lead", "text": "지수가 99.9 입니다"}   # 없는 숫자 → 걸러진다
        return out[:-1]                                            # 마지막 target 은 빠뜨린다

    com = explain(f, MockLLM(_reply(items)), Budget(3.0))
    assert com.status == "ok" and com.cost_usd > 0
    texts, report = drafts.gate_texts(com.texts, want, f)
    assert report["lead"] == ["숫자 99.9"] and report[want[-1]] == ["빠짐"]
    post = drafts.post_markdown(f, texts)
    assert post.startswith("# 📡 깃허브 AI 트렌드 레이더 1회 📡 다섯 신호로 본 첫 주")
    assert "| 1 | org/r2 |" not in post and "| 2 | org/r2 | 70.5 | 지난주 2위 |" in post
    assert "〔초안 없음 — 숫자 99.9" in post
    assert "2026년 11월 1일(일) ~ 11월 7일(토)" in post
    assert "org/r1 — 지난주 1위 → 이번 주 후보 밖" in post
    ang = drafts.angles_markdown(f, texts)
    assert "### C. 꾸준한 상승" in ang and "이력이 모자라" in ang


def test_publish_budget_too_small_skips_call():
    llm = MockLLM([])
    com = explain(_facts(), llm, Budget(0.001))
    assert com.status == "skipped" and llm.requests == []


def test_publish_llm_failure_is_status_not_exception():
    def boom(_req):
        raise RuntimeError("secret-in-message")

    com = explain(_facts(), MockLLM(boom), Budget(3.0))
    assert (com.status, com.reason) == ("failed", "RuntimeError")


def _api(routes):
    t = FakeTransport(routes)
    c, _ = _client(t)
    return notion.NotionAPI(c, "ntn_x"), t


def test_publish_notion_creates_then_updates_only_drafts():
    page = {"id": "p1", "url": "https://notion.so/p1", "properties": {"상태": {"status": {"name": "초안"}}}}
    api, t = _api([("/v1/pages/p1/markdown", ok({})), ("/v1/pages/p1", ok(page)), ("/v1/pages", ok(page))])
    idx: dict[str, Any] = {"database": {"id": "d", "data_source_id": "ds1", "url": ""}}
    saved = []
    kw: dict[str, Any] = {"week": "2026-11-01", "kind": "TOP 10", "issue": 1, "title": "t", "markdown": "# t"}
    assert notion.upsert(api, idx, save=lambda: saved.append(1), **kw) == "created"
    assert idx["pages"]["2026-11-01:TOP 10"]["page_id"] == "p1" and saved
    assert notion.upsert(api, idx, save=lambda: None, **kw) == "updated"
    assert all(h["Notion-Version"] == "2026-03-11" for _, _, h in t.requests)
    body = json.loads(t.bodies[0] or b"")
    assert body["properties"]["상태"]["status"]["name"] == "초안"


def test_publish_notion_leaves_reviewed_and_deleted_pages():
    reviewed = {"id": "p1", "properties": {"상태": {"status": {"name": "검토 중"}}}}
    api, t = _api([("/v1/pages/p1", ok(reviewed)), ("/v1/pages/p2", status(404))])
    pages = {"w:TOP 10": {"page_id": "p1"}, "w:관점": {"page_id": "p2"}}
    idx: dict[str, Any] = {"database": {"data_source_id": "ds1"}, "pages": pages}
    kw: dict[str, Any] = {"week": "w", "issue": 1, "title": "t", "markdown": "m", "save": lambda: None}
    assert notion.upsert(api, idx, kind="TOP 10", **kw) == "kept:검토 중"
    assert notion.upsert(api, idx, kind="관점", **kw) == "kept:deleted"
    assert [m for m, _, _ in t.requests] == ["GET", "GET"]  # 고치는 요청이 없다
