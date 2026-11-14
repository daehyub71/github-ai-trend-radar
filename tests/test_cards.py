"""T7-7 — 해설 단계: 대상 · 근거 캐시 · 예산 · 실패 · 비공개 저장 · 사이트 사본 (SPEC F10, PLAN §4-1).

녹화 응답과 가짜 LLM 만 쓴다 — 네트워크·과금 0.
"""

import json
from datetime import date
from pathlib import Path
from typing import Any

from radar import cards
from radar.clients.claude import LLMRequest, LLMResponse, MockLLM
from radar.store import json_text
from tests.fakes import FakeTransport, ok, status
from tests.test_http import _client

W = date(2026, 11, 1)
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "card_v1.json").read_text(encoding="utf-8"))
EMPTY = "<html><body><div class='topics'></div></body></html>"


def _repo(rid: int, name: str, rank: int) -> dict[str, Any]:
    return {
        "repo_id": rid,
        "full_name": name,
        "category": "MCP 서버·도구",
        "description": "Tool",
        "topics": [],
        "language": "Python",
        "latest": {
            "week": W.isoformat(),
            "rank": rank,
            "prev_rank": 9,
            "star_rank": 40,
            "index": 70.5,
            "pct": {"s1": 60.0, "s2": None, "s3": 80.0, "s4": 90.0, "s5": 10.0},
            "contrib": {"s1": 10.0, "s2": 0.0, "s3": 25.0, "s4": 30.0, "s5": 5.5},
        },
        "trend": [{"key": "종합 순위", "prev": "9위", "now": f"{rank}위", "avg": "—"}],
        "insights": [
            {"id": "I7", "title": "순위 이동", "big": f"9위 → {rank}위", "text": "", "signal": "index"}
        ],
        "mentions": None,
        "history": [],
    }


def _data(tmp: Path) -> Path:
    data = tmp / "data"
    site = data / "site"
    (site / "repo").mkdir(parents=True)
    (site / "week").mkdir(parents=True)
    week = {
        "week": W.isoformat(),
        "weights": {"s1": 15, "s2": 15, "s3": 25, "s4": 30, "s5": 15},
        "top10": [{"rank": 1, "repo_id": 1, "full_name": "org/tool"}],
        "angles": {
            "A": {
                "status": "ok",
                "items": [
                    {"repo_id": 2, "full_name": "org/lib", "evidence": {}},
                    {"repo_id": 1, "full_name": "org/tool", "evidence": {}},
                ],
            },
            "B": {"status": "ok", "items": []},
            "C": {"status": "insufficient", "items": []},
            "D": {"status": "insufficient", "items": []},
        },
    }
    (site / "week" / f"{W.isoformat()}.json").write_text(json_text(week), encoding="utf-8")
    for rid, name, rank in ((1, "org/tool", 1), (2, "org/lib", 14)):
        (site / "repo" / f"{rid}.json").write_text(json_text(_repo(rid, name, rank)), encoding="utf-8")
    return data


def _transport() -> FakeTransport:
    readme = {"content": "IyBUb29s", "encoding": "base64"}  # "# Tool"
    return FakeTransport(
        [
            ("/readme", ok(readme)),
            ("/releases", ok([])),
            ("hn.algolia.com/api/v1/search", ok({"hits": []})),
            ("news.hada.io/past", ok(EMPTY)),
            (
                "api.tavily.com",
                ok({"results": [{"url": "https://blog.example.com/t", "title": "Guide", "content": "s"}]}),
            ),
            (
                "api.github.com/graphql",
                ok(
                    {
                        "data": {
                            "r0": {
                                "nameWithOwner": "org/tool",
                                "usesCustomOpenGraphImage": False,
                                "openGraphImageUrl": "",
                                "homepageUrl": "",
                                "licenseInfo": None,
                            }
                        }
                    }
                ),
            ),
        ]
    )


def _answer(text: str = "") -> LLMResponse:
    claim = {"text": "도구입니다.", "sources": ["E1"], "basis": "확인"}
    body = {
        "summary": {
            "what": claim,
            "why_now": {"text": "기여와 사용으로 1위에 올랐습니다.", "sources": ["F"], "basis": "확인"},
            "watch": claim,
        },
        "trend_notes": [claim],
        "what": [{"label": "푸는 문제", **claim}],
        "buzz": {
            "nature": "없음",
            "trigger": {"text": "", "sources": [], "basis": "추정"},
            "reactions": [],
            "reading": {"text": "화제보다 사용으로 오른 저장소입니다.", "sources": ["F"], "basis": "추정"},
        },
        "watch": [claim],
    }
    return LLMResponse(
        text or json.dumps(body, ensure_ascii=False), "end_turn", "claude-sonnet-5-5", 9000, 2500
    )


def test_cards_targets_top10_then_angles_with_reasons(tmp_path):
    ts = cards.targets(W, _data(tmp_path))
    assert [(t.full_name, t.reasons) for t in ts] == [
        ("org/tool", ("종합 1위", "관점 A(조용한 강자)")),
        ("org/lib", ("관점 A(조용한 강자)",)),
    ]
    assert ts[0].until == date(2026, 11, 7)


def test_cards_write_private_copies_lines_index_and_run(tmp_path):
    data, private, work = _data(tmp_path), tmp_path / "private", tmp_path / "work"
    t = _transport()
    client, _ = _client(t)
    llm = MockLLM(lambda req: _answer())
    rec = cards.write_cards(
        W,
        llm,
        client=client,
        token="tok",
        tavily_key="tv",
        data=data,
        private=private,
        work=work,
        log=lambda s: None,
    )
    assert rec["ok"] == 2 and rec["failed"] == 0 and rec["tavily_credits"] == 6
    assert rec["cost_usd"] == round(2 * (9000 * 2 + 2500 * 10) / 1e6, 6)
    c1 = json.loads((private / "site-private" / "cards" / "1.json").read_text(encoding="utf-8"))
    assert set(c1) == set(FIXTURE) and c1["week"] == W.isoformat()
    assert [e["site"] for e in c1["evidence"]] == ["github.com"]  # 인용한 근거만
    assert c1["buzz"]["nature"] is None and c1["buzz"]["posts"] == []
    assert (private / "cards" / "1.json").read_text(encoding="utf-8") == json_text(c1)
    lines = json.loads((private / "site-private" / "weeks" / "2026-11-01.json").read_text(encoding="utf-8"))
    assert lines == {
        "week": "2026-11-01",
        "lines": {"1": "기여와 사용으로 1위에 올랐습니다.", "2": "기여와 사용으로 1위에 올랐습니다."},
    }
    index = json.loads((private / "site-private" / "cards" / "index.json").read_text(encoding="utf-8"))
    assert [r["full_name"] for r in index] == ["org/tool", "org/lib"]
    weekly = json.loads(
        (private / "weeks" / "2026-11-01" / "cards" / "org__tool.json").read_text(encoding="utf-8")
    )
    assert set(weekly) == {"card", "excluded", "facts", "evidence", "failures"}
    assert "text" not in weekly["evidence"][0]  # 주별 기록에도 원문은 넣지 않는다
    # 프롬프트: 사실 묶음 안에 코드 관찰·동향 표가 들어간다
    req: LLMRequest = llm.requests[0]
    assert '"observations"' in req.user and '"trend"' in req.user and "[E1] github · readme" in req.user


def test_cards_rerun_uses_evidence_cache_no_new_calls(tmp_path):
    data, private, work = _data(tmp_path), tmp_path / "private", tmp_path / "work"
    client, _ = _client(_transport())
    cards.write_cards(
        W,
        MockLLM(lambda r: _answer()),
        client=client,
        token="tok",
        tavily_key="tv",
        data=data,
        private=private,
        work=work,
        log=lambda s: None,
    )
    t2 = FakeTransport([])
    c2, _ = _client(t2)
    rec = cards.write_cards(
        W,
        MockLLM(lambda r: _answer()),
        client=c2,
        token="tok",
        tavily_key="tv",
        data=data,
        private=private,
        work=work,
        log=lambda s: None,
    )
    assert t2.requests == [] and rec["tavily_credits"] == 0 and all(r["cached"] for r in rec["results"])
    hist = json.loads((private / "cards" / "1.json").read_text(encoding="utf-8"))["history"]
    assert [h["week"] for h in hist] == ["2026-11-01"]  # 같은 주는 덮어쓴다


def test_cards_failed_source_is_recorded_and_not_cached(tmp_path):
    data, private, work = _data(tmp_path), tmp_path / "private", tmp_path / "work"
    t = _transport()
    t.routes.insert(0, ("api.tavily.com", status(500)))
    client, _ = _client(t)
    rec = cards.write_cards(
        W,
        MockLLM(lambda r: _answer()),
        client=client,
        token="tok",
        tavily_key="tv",
        data=data,
        private=private,
        work=work,
        only=["org/tool"],
        log=lambda s: None,
    )
    assert rec["targets"] == 1 and rec["results"][0]["failures"] == ["web Tavily 500"]
    assert not (work / "2026-11-01" / "1.json").exists()


def test_cards_budget_skips_and_invalid_output_retries_once(tmp_path):
    data, private, work = _data(tmp_path), tmp_path / "private", tmp_path / "work"
    client, _ = _client(_transport())
    llm = MockLLM(lambda r: _answer())
    rec = cards.write_cards(
        W,
        llm,
        client=client,
        token="tok",
        tavily_key="tv",
        data=data,
        private=private,
        work=work,
        cap=0.01,
        log=lambda s: None,
    )
    assert rec["skipped"] == 2 and llm.requests == []
    bad = MockLLM([_answer("not json"), _answer("still not json")])
    rec = cards.write_cards(
        W,
        bad,
        client=client,
        token="tok",
        tavily_key="tv",
        data=data,
        private=private,
        work=work,
        only=["org/lib"],
        log=lambda s: None,
    )
    assert rec["results"][0]["status"] == "failed:invalid_output" and len(bad.requests) == 2
    assert "다시 쓰세요" in bad.requests[1].user
    assert not (private / "cards" / "2.json").exists()


def test_cards_budget_subtracts_blog_spent(tmp_path):
    data, private, work = _data(tmp_path), tmp_path / "private", tmp_path / "work"
    draft = private / "weeks" / "2026-11-01" / "blog" / "draft.json"
    draft.parent.mkdir(parents=True)
    draft.write_text(json.dumps({"cost_usd": 2.95}), encoding="utf-8")
    p = cards.plan(W, data=data, work=work, private=private)
    assert p["targets"] == 2 and p["calls"]["tavily_credits"] == 6 and p["llm"]["remaining_usd"] == 0.05
    assert p["reasons"]["org/lib"] == ["관점 A(조용한 강자)"]


def _png() -> bytes:
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (640, 320), "white").save(buf, "PNG")
    return buf.getvalue()


def test_cards_pick_repo_image_with_source_and_rights(tmp_path):
    from radar.clients.transport import HttpResponse

    data, private, work = _data(tmp_path), tmp_path / "private", tmp_path / "work"
    readme = "# Tool\n![arch](docs/arch.png)\n"
    gql = {
        "data": {
            "r0": {
                "nameWithOwner": "org/tool",
                "usesCustomOpenGraphImage": False,
                "openGraphImageUrl": "",
                "homepageUrl": "",
                "licenseInfo": {"spdxId": "MIT"},
            },
            "r1": {
                "nameWithOwner": "org/lib",
                "usesCustomOpenGraphImage": True,
                "openGraphImageUrl": "https://repository-images.githubusercontent.com/2/x",
                "homepageUrl": "",
                "licenseInfo": {"spdxId": "AGPL-3.0"},
            },
        }
    }
    import base64

    t = _transport()
    t.routes[:0] = [
        ("api.github.com/graphql", ok(gql)),
        ("/readme", ok({"content": base64.b64encode(readme.encode()).decode(), "encoding": "base64"})),
        (
            "raw.githubusercontent.com/org/tool/HEAD/docs/arch.png",
            HttpResponse(200, {"Content-Type": "image/png"}, _png()),
        ),
        (
            "repository-images.githubusercontent.com/2/x",
            HttpResponse(200, {"Content-Type": "image/png"}, _png()),
        ),
    ]
    client, _ = _client(t)
    cards.write_cards(
        W,
        MockLLM(lambda r: _answer()),
        client=client,
        token="tok",
        tavily_key="tv",
        data=data,
        private=private,
        work=work,
        log=lambda s: None,
    )
    folder = private / "weeks" / "2026-11-01" / "blog" / "images"
    man = json.loads((folder / "images.json").read_text(encoding="utf-8"))
    assert man["org__tool"]["kind"] == "readme" and man["org__tool"]["rights"] == "라이선스 MIT"
    assert man["org__tool"]["file"] == "org__tool.png" and (folder / "org__tool.png").exists()
    # AGPL 이라 README 그림은 후보가 아니고, 주인이 올린 소셜 미리보기를 쓴다
    assert man["org__lib"]["kind"] == "social" and man["org__lib"]["rights"] == "공개용(소셜 미리보기)"
    # 다시 돌리면 받아 둔 그림을 쓴다 — 그림 주소는 다시 부르지 않는다
    t2 = _transport()
    t2.routes[:0] = [("api.github.com/graphql", ok(gql))]
    c2, _ = _client(t2)
    cards.write_cards(
        W,
        MockLLM(lambda r: _answer()),
        client=c2,
        token="tok",
        tavily_key="tv",
        data=data,
        private=private,
        work=work,
        log=lambda s: None,
    )
    assert not [u for u in t2.urls() if "raw.githubusercontent" in u or "repository-images" in u]
