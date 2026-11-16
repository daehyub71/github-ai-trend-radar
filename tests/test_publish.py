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


# ── M8 글 그림 결합 (T8-6) · Notion 그림 올리기 (T8-7) ──

OBS = ["12주 동안 TOP 10 기여분에서 사용·기여 비중은 51% → 52%입니다.",
       "이번 주 TOP 10 중 8개는 4주 전에 TOP 10 밖이었습니다."]
PIC: dict[str, Any] = {"file": "images/org__r2.png", "kind": "readme", "source": "https://github.com/org/r2",
       "rights": "라이선스 MIT"}
ILL: dict[str, Any] = {"teach": "요청이 답이 되는 흐름",
       "prompt": "A flat educational scene of a request flowing through boxes", "labels": ["요청", "답"]}
ART: dict[str, Any] = {
    "week": "2026-11-01",
    "files": {"c1": "c1-rank-trend.png", "c2": "c2-contribution.png", "c3": "c3-signal-map.png",
              "c4": "c4-trend.png"},
    "intros": [{"repo_id": 2, "full_name": "org/r2", "rank": 1, "picture": PIC,
                "caption": "그림: https://github.com/org/r2 · 라이선스 MIT"},
               {"repo_id": 3, "full_name": "org/r3", "rank": 2, "picture": None, "caption": None}],
    "cards": [{"repo_id": 2, "full_name": "org/r2", "angle": "A", "file": "card-org__r2.png", "picture": PIC,
               "illustration": ILL}],
    "observations": OBS,
}


def _facts_with_angle():
    weeks = _weeks()
    f = build_facts(weeks, select_angles(weeks), {}, issue=1, angle_rules=RULES, trend=OBS)
    ev = {"s1": 40.0, "use": 85.0, "use_basis": "기여·사용"}
    f["angles"]["A"]["items"] = [{"repo": "org/r2", "url": "https://github.com/org/r2", "rank": 2,
                                  "index": 70.5, "evidence": ev}]
    return f


def _texts(f):
    texts, _ = drafts.gate_texts({t: "관측한 내용입니다." for t in targets(f)}, targets(f), f)
    return texts


def test_publish_trend_target_and_section_without_pictures():
    f = _facts_with_angle()
    assert "trend" in targets(f) and f["trend"]["observations"] == OBS
    post = drafts.post_markdown(f, _texts(f))
    assert "### 트렌드 분석" in post and "- 이번 주 TOP 10 중 8개는 4주 전에 TOP 10 밖이었습니다." in post
    assert "![" not in post  # 그림 단계가 없으면 그림 자리 없이 쓴다 (P7)


def test_publish_post_places_charts_and_repo_pictures():
    f = _facts_with_angle()
    post = drafts.post_markdown(f, _texts(f), ART)
    assert "![TOP 10 12주 종합 순위 추이](charts/c1-rank-trend.png)" in post
    assert "![신호 기여 — 지수를 무엇이 채웠나](charts/c2-contribution.png)" in post
    trend = post.index("### 트렌드 분석")
    # 트렌드 관찰이 없는 예전 사실 묶음이면 그림 단계의 관찰 문장을 쓴다
    old = dict(f, trend={"observations": []})
    again = drafts.post_markdown(old, _texts(f), ART)
    assert "- 이번 주 TOP 10 중 8개는 4주 전에 TOP 10 밖이었습니다." in again
    assert post.index("![12주 트렌드 — 신호 비중과 카테고리](charts/c4-trend.png)") > trend
    head = post.index("org/r2 — 지수")
    pic = post.index("![그림: https://github.com/org/r2 · 라이선스 MIT](images/org__r2.png)")
    assert head < pic < post.index("org/r3 — 지수")  # 그 저장소 소제목 아래
    assert post.count("](images/") == 1  # 그림 없는 저장소는 자리 없이


def test_publish_angles_place_map_card_and_illustration_prompt():
    f = _facts_with_angle()
    ang = drafts.angles_markdown(f, _texts(f), ART)
    assert "![신호 지도 — 관심과 실사용](charts/c3-signal-map.png)" in ang
    assert "![관점 카드 — org/r2](charts/card-org__r2.png)" in ang
    assert "🎨 일러스트 프롬프트 — 요청이 답이 되는 흐름" in ang and "gen/org__r2.png" in ang
    assert ILL["prompt"] in ang
    made = dict(ART, cards=[dict(ART["cards"][0], picture=dict(PIC, kind="illustration"))])
    # 이미 만든 일러스트가 있으면 프롬프트는 뺀다
    assert "🎨" not in drafts.angles_markdown(f, _texts(f), made)


def test_publish_notion_local_images_become_markers(tmp_path):
    (tmp_path / "charts").mkdir()
    (tmp_path / "charts" / "c1.png").write_bytes(b"\x89PNG one")
    md = "# 제목\n\n![차트 하나](charts/c1.png)\n\n본문\n\n![없는 그림](charts/none.png)\n"
    out, found = notion.local_images(md, tmp_path)
    assert out == "# 제목\n\n⟦그림 1⟧\n\n본문\n\n"
    assert found == [("⟦그림 1⟧", "차트 하나", tmp_path / "charts" / "c1.png")]


def test_publish_notion_attach_images_uploads_once_by_hash(tmp_path):
    img = tmp_path / "c1.png"
    img.write_bytes(b"\x89PNG one")
    children = {"results": [{"id": "b1", "type": "paragraph",
                             "paragraph": {"rich_text": [{"plain_text": "⟦그림 1⟧"}]}}], "has_more": False}
    api, t = _api([("/v1/file_uploads/u1/send", ok({"status": "uploaded"})),
                   ("/v1/file_uploads", ok({"id": "u1"})),
                   ("/v1/blocks/p1/children", ok(children)), ("/v1/blocks/b1", ok({}))])
    idx: dict[str, Any] = {}
    found = [("⟦그림 1⟧", "차트 하나", img)]
    assert notion.attach_images(api, idx, "p1", found, save=lambda: None) == 1
    sent = [(m, u.split("api.notion.com")[1]) for m, u, _ in t.requests]
    assert sent == [("GET", "/v1/blocks/p1/children?page_size=100"), ("POST", "/v1/file_uploads"),
                    ("POST", "/v1/file_uploads/u1/send"), ("PATCH", "/v1/blocks/p1/children"),
                    ("DELETE", "/v1/blocks/b1")]
    insert = json.loads(t.bodies[3] or b"")
    assert insert["children"][0]["image"]["file_upload"]["id"] == "u1"
    assert insert["position"]["after_block"]["id"] == "b1"
    assert t.requests[2][2]["Content-Type"].startswith("multipart/form-data; boundary=")
    # 같은 그림은 다시 올리지 않는다
    t.requests.clear()
    assert notion.attach_images(api, idx, "p1", found, save=lambda: None) == 1
    assert not any("/v1/file_uploads" in u for _, u, _ in t.requests)


def test_publish_rewrite_drafts_merges_pictures_without_llm(tmp_path):
    from datetime import date

    from radar import blog

    f = _facts_with_angle()
    out = tmp_path / "weeks" / "2026-11-01" / "blog"
    (out / "charts").mkdir(parents=True)
    (out / "facts.json").write_text(json.dumps(f, ensure_ascii=False), encoding="utf-8")
    texts = {t: "관측한 내용입니다." for t in targets(f)}
    (out / "draft.json").write_text(json.dumps({"texts": texts}, ensure_ascii=False), encoding="utf-8")
    week = date(2026, 11, 1)
    assert blog.rewrite_drafts(week, private=tmp_path) == {"week": "2026-11-01", "pictures": False,
                                                           "notes": 0, "cover": False}
    assert "![" not in (out / "post.md").read_text(encoding="utf-8")
    (out / "charts" / "charts.json").write_text(json.dumps(ART, ensure_ascii=False), encoding="utf-8")
    assert blog.rewrite_drafts(week, private=tmp_path) == {"week": "2026-11-01", "pictures": True,
                                                           "notes": 0, "cover": False}
    assert "](charts/c1-rank-trend.png)" in (out / "post.md").read_text(encoding="utf-8")
    assert "](charts/card-org__r2.png)" in (out / "angles.md").read_text(encoding="utf-8")


# ── 초안의 "무엇인가"는 저장소 해설(README·웹 근거)로 · 대표 이미지 (T8-13, D25) ──

NOTE: dict[str, Any] = {
    "full_name": "org/r2", "week": "2026-11-01",
    "summary": {"what": {"text": "여러 에이전트 CLI 를 한곳에서 제어하는 도구입니다.", "basis": "확인",
                         "sources": ["E1"]}, "why_now": None, "watch": None},
    "what": [{"label": "구조", "text": "WebSocket 서버가 CLI 를 감쌉니다.", "basis": "확인",
              "sources": ["E1"]},
             {"label": "쓰는 사람", "text": "구독을 이미 쓰는 개발자입니다.", "basis": "추정",
              "sources": ["E2"]}],
}


def test_publish_post_what_prefers_commentary_card():
    f = _facts_with_angle()
    post = drafts.post_markdown(f, _texts(f), ART, notes={"org/r2": NOTE})
    sec = post[post.index("org/r2 — 지수"):post.index("org/r3 — 지수")]
    assert "**무엇인가** 여러 에이전트 CLI 를 한곳에서 제어하는 도구입니다." in sec
    assert "- **구조** WebSocket 서버가 CLI 를 감쌉니다." in sec
    assert "- **쓰는 사람** (추정) 구독을 이미 쓰는 개발자입니다." in sec
    assert sec.index("**무엇인가**") < sec.index("- **쓰는 사람**") < sec.index("**어떤 신호로 떴나**")
    assert "**무엇인가** 관측한 내용입니다." not in sec
    # 해설이 없는 저장소는 초안 LLM 문단(설명·토픽·언어 근거)을 그대로 쓴다
    r3 = post[post.index("org/r3 — 지수"):]
    assert "**무엇인가** 관측한 내용입니다." in r3
    # 게이트에 모두 걸려 무엇인가가 비면 초안 LLM 문단으로 돌아간다
    empty = dict(NOTE, summary={"what": None}, what=[])
    again = drafts.post_markdown(f, _texts(f), ART, notes={"org/r2": empty})
    assert "**무엇인가** 관측한 내용입니다." in again


def test_publish_cover_goes_under_title():
    f = _facts_with_angle()
    post = drafts.post_markdown(f, _texts(f), ART, cover="gen/cover.png").split("\n")
    assert post[0].startswith("# 📡 ") and post[2] == "![대표 이미지](gen/cover.png)"
    ang = drafts.angles_markdown(f, _texts(f), ART, cover="gen/cover-angles.png").split("\n")
    assert ang[2] == "![대표 이미지](gen/cover-angles.png)"
    assert "대표 이미지" not in drafts.post_markdown(f, _texts(f), ART)


def test_publish_rewrite_drafts_uses_week_commentary_and_cover(tmp_path):
    from datetime import date

    from radar import blog

    f = _facts_with_angle()
    out = tmp_path / "weeks" / "2026-11-01" / "blog"
    (out / "charts").mkdir(parents=True)
    (out / "facts.json").write_text(json.dumps(f, ensure_ascii=False), encoding="utf-8")
    texts = {t: "관측한 내용입니다." for t in targets(f)}
    (out / "draft.json").write_text(json.dumps({"texts": texts}, ensure_ascii=False), encoding="utf-8")
    cards = tmp_path / "weeks" / "2026-11-01" / "cards"
    cards.mkdir(parents=True)
    (cards / "org__r2.json").write_text(json.dumps({"card": NOTE}, ensure_ascii=False), encoding="utf-8")
    (cards / "run.json").write_text(json.dumps({"week": "2026-11-01", "cards": 1}), encoding="utf-8")
    (out / "gen").mkdir()
    (out / "gen" / "cover.png").write_bytes(b"\x89PNG cover")
    got = blog.rewrite_drafts(date(2026, 11, 1), private=tmp_path)
    assert got == {"week": "2026-11-01", "pictures": False, "notes": 1, "cover": True}
    post = (out / "post.md").read_text(encoding="utf-8")
    assert "**무엇인가** 여러 에이전트 CLI 를 한곳에서 제어하는 도구입니다." in post
    assert post.split("\n")[2] == "![대표 이미지](gen/cover.png)"
    angles = (out / "angles.md").read_text(encoding="utf-8")
    assert "대표 이미지" not in angles  # 관점 글은 cover-angles.*
    assert "**무엇인가** 여러 에이전트 CLI 를 한곳에서 제어하는 도구입니다." in angles  # 관점 글도 해설로


UNKNOWN = "설명과 토픽이 없어 자세한 용도는 저장소에서 확인이 필요합니다."


def test_publish_what_keeps_draft_sentence_when_commentary_has_no_summary():
    # D25 보강(2026-11-16) — 11-08 1위 meta/astryx: 해설 요약 문장이 없어 항목 하나만 남았다.
    # 요약이 없으면 초안 문단에서 "확인이 필요" 문장을 뺀 나머지를 첫 줄로 쓰고 항목을 붙인다
    f = _facts_with_angle()
    items_only = dict(NOTE, summary={"what": None})
    texts = dict(_texts(f), **{"what:org/r2": "org/r2 는 디자인 시스템입니다. " + UNKNOWN})
    post = drafts.post_markdown(f, texts, ART, notes={"org/r2": items_only})
    sec = post[post.index("org/r2 — 지수"):post.index("org/r3 — 지수")]
    assert "**무엇인가** org/r2 는 디자인 시스템입니다.\n" in sec
    assert "- **구조** WebSocket 서버가 CLI 를 감쌉니다." in sec and "확인이 필요" not in sec
    # 남는 문장이 없으면 첫 줄 없이 항목만
    texts = dict(texts, **{"what:org/r2": UNKNOWN})
    post = drafts.post_markdown(f, texts, ART, notes={"org/r2": items_only})
    sec = post[post.index("org/r2 — 지수"):post.index("org/r3 — 지수")]
    assert "**무엇인가**\n" in sec and "확인이 필요" not in sec


def test_publish_angles_use_commentary_and_drop_unknown_sentence():
    # D25 보강 — 관점 글에도 해설의 무엇인가를 넣고, 해설이 있으면 "확인이 필요" 문장은 뺀다
    f = _facts_with_angle()
    texts = dict(_texts(f), **{"angle:org/r2": "사용 백분위가 높습니다. " + UNKNOWN})
    ang = drafts.angles_markdown(f, texts, ART, notes={"org/r2": NOTE})
    sec = ang[ang.index("#### org/r2"):]
    assert "**무엇인가** 여러 에이전트 CLI 를 한곳에서 제어하는 도구입니다." in sec
    assert "- **쓰는 사람** (추정) 구독을 이미 쓰는 개발자입니다." in sec
    assert "사용 백분위가 높습니다." in sec and "확인이 필요" not in sec
    assert sec.index("**무엇인가**") < sec.index("근거:")
    # 해설이 없으면 관점 문단 그대로(대신할 설명이 없다)
    plain = drafts.angles_markdown(f, texts, ART)
    assert UNKNOWN in plain and "**무엇인가**" not in plain


# ── 관점 노트 일러스트 색 (D27) ──

STYLE = ("16:9 dark blueprint technical schematic, deep navy background (#0B1220) "
         "with a faint engineering grid, thin cyan (#22D3EE) and indigo (#6366F1) line art, "
         "isometric engineering-drawing precision.")
BODY = " A worker pool feeds a vector index through a message bus. No people, characters, logos, or text."


def test_publish_restyle_varies_illustration_colors_by_angle_and_order():
    # 2026-11-16 사용자 "관점 노트 그림의 색들을 다양하게"
    # — 유형마다 강조색, 같은 유형 안에서는 바탕 4종을 차례로(유형마다 시작 바탕을 하나씩 민다).
    # LLM 이 쓴 다크 블루프린트 첫 문장만 바꾸고 나머지는 그대로 둔다
    got = {(k, i): drafts.restyle(STYLE + BODY, k, i) for k in "ABCD" for i in range(4)}
    assert len(set(got.values())) == 16
    assert all(p.endswith(BODY) and p.startswith("16:9 ") for p in got.values())
    a0, a1, a2, a3 = (got["A", i] for i in range(4))
    assert "emerald" in a0 and "#0B1220" in a0 and "#22D3EE" not in a0
    assert "light drafting paper" in a1 and "#0B1220" not in a1
    assert "graphite" in a2 and "warm vellum" in a3
    assert drafts.restyle(STYLE + BODY, "A", 4) == a0  # 바탕은 네 개씩 돈다
    firsts = [got[k, 0] for k in "ABCD"]  # 네 섹션의 첫 그림 바탕이 모두 다르다
    grounds = ("deep navy", "light drafting paper", "graphite", "warm vellum")
    assert [next(g for g in grounds if g in x) for x in firsts] == list(grounds)
    assert "crimson" in got["B", 0] and "magenta" in got["B", 1] and "violet" in got["D", 0]
    assert "orthographic" in drafts.restyle(STYLE.replace("isometric", "orthographic") + BODY, "C", 0)
    # 양식 문장을 찾지 못하면(LLM 이 다르게 썼으면) 고치지 않는다
    assert drafts.restyle(BODY.strip(), "A", 0) == BODY.strip()


def test_publish_angles_restyle_each_illustration_prompt():
    f = _facts_with_angle()
    ill = dict(ILL, prompt=STYLE + BODY)
    art = dict(ART, cards=[dict(ART["cards"][0], illustration=ill)])
    ang = drafts.angles_markdown(f, _texts(f), art)
    assert drafts.restyle(STYLE + BODY, "A", 0) in ang and STYLE not in ang


# ── 한 장 요약 그림 프롬프트 (D28) ──


def _summary_facts():
    from radar.core.charts_data import Share, trend_observations

    f = _facts_with_angle()
    top = [dict(r, rank=i, prev_rank=i) for i, r in enumerate(f["top10"], 1)]
    top[0].update(repo="org/lead", prev_rank=49, category="코딩 에이전트·IDE")
    top[1].update(category="코딩 에이전트·IDE")
    top[2].update(category="코딩 에이전트·IDE", prev_rank=None)
    shares = [Share("2026-08-16", False, {"s1": 30.0, "s2": 0.0, "s3": 40.0, "s4": 15.0, "s5": 15.0}),
              Share("2026-11-01", False, {"s1": 33.0, "s2": 0.0, "s3": 38.0, "s4": 13.0, "s5": 16.0})]
    # 관심 비중은 core 의 트렌드 관찰 문장에서 읽는다 — 그 문장 형식이 바뀌면 이 테스트가 잡는다
    return dict(f, top10=top, trend={"observations": trend_observations(shares, [], [])})


def test_publish_summary_prompt_comes_from_facts():
    # 2026-11-16 사용자 "한장요약을 형상화할 수 있는 이미지 생성 프롬프트를 추가" — 사실로만, LLM 0
    prompt, labels = drafts.summary_prompt(_summary_facts())
    assert labels == ["지수 1위 org/lead · 49위 → 1위", "포크·사용 신호 빈칸", "코딩 에이전트·IDE 3개",
                      "관심 비중 45% → 49%", "새로 진입 2개"]
    assert "climbs along a steep arrow from far below the column into the top slot" in prompt
    assert "the second and fourth columns are mostly empty outlines" in prompt
    assert "one column of 3 stacked units stands taller" in prompt
    assert "attention band widens slightly toward the right" in prompt
    assert "2 new nodes enter the top-ten column" in prompt
    assert prompt.startswith("16:9 ") and prompt.endswith("No people, characters, logos, or text.")
    assert "#F59E0B" in prompt and "#DB2777" in prompt  # 사이트 차트의 신호 색
    from radar.publish.card import STYLE_BANNED

    assert not STYLE_BANNED.search(prompt)  # D24 금지 양식을 쓰지 않는다


def test_publish_summary_prompt_handles_quiet_weeks():
    f = _summary_facts()
    top = [dict(r, prev_rank=r["rank"], category=None, missing=[]) for r in f["top10"]]
    top[0]["prev_rank"] = 1
    prompt, labels = drafts.summary_prompt(dict(f, top10=top, trend={"observations": []}))
    assert labels[0].endswith("지난주도 1위") and labels[1:] == ["다섯 신호 고르게", "카테고리 고르게",
                                                                "관심·사용 비중 추이", "새로 진입 없음"]
    assert "holds its position" in prompt and "closed gateway frame" in prompt


def test_publish_summary_section_gets_prompt_or_made_picture():
    f = _summary_facts()
    post = drafts.post_markdown(f, _texts(f), ART)
    sec = post[post.index("### 한 장 요약"):]
    assert "> 🎨 한 장 요약 그림 프롬프트" in sec and "`gen/summary.png`" in sec
    assert "얹을 한글 라벨: ① 지수 1위 org/lead · 49위 → 1위 ② 포크·사용 신호 빈칸 ③ 코딩" in sec
    assert sec.index("관측한 내용입니다.") < sec.index("> 🎨")  # 요약 글 다음에
    made = drafts.post_markdown(f, _texts(f), ART, summary_image="gen/summary.png")
    sec = made[made.index("### 한 장 요약"):]
    assert sec.split("\n")[2] == "![한 장 요약](gen/summary.png)" and "🎨" not in sec
    # v0.7.10 — 그림 안 라벨 상자는 비어 있으니 라벨 5개를 그림 바로 아래 한 줄로
    assert sec.split("\n")[4].startswith("그림 라벨(왼쪽부터): ① 지수 1위 org/lead · 49위 → 1위 ② 포크·사용")
    assert sec.split("\n")[4].count("⑤") == 1
