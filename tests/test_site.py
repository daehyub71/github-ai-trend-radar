"""T4-3 — 사이트 파생 데이터 (SPEC F6, DESIGN §1). 네트워크 없음. LLM 글은 넣지 않는다."""

import json
from datetime import date

from radar.config import Config
from radar.core.angles import RULES_V1
from radar.pipeline import SIGNAL_FIELDS
from radar.site import export_site
from radar.store import csv_text, json_text, week_path
from tests.startrend_fixture import meta, write_tree

W = {"s1": 15, "s2": 15, "s3": 25, "s4": 30, "s5": 15}


def _setup(tmp_path):
    root = write_tree(tmp_path / "st", [meta(1, "org/one", description="Agent tool", topics=["mcp"]),
                                         meta(2, "org/two")], {"2026-11-01": [(1, "org/one", 5)]},
                      names={"mcp-tools": "MCP 서버·도구"})
    data = tmp_path / "data"
    for wk, backfilled, rows in (("2026-10-25", True, [(1, 1, 60.0), (2, 2, 50.0)]),
                                 ("2026-11-01", False, [(2, 1, 70.0), (1, 2, 65.0)])):
        idx = {"week": wk, "weights": W, "weights_version": 1, "candidates": 2, "top": [r[0] for r in rows],
               "rows": [{"rank": rk, "repo_id": rid, "full_name": f"org/{'one' if rid == 1 else 'two'}",
                         "category": "mcp-tools", "gain_rank": rid, "index": v,
                         "pct": {"s1": 50.0, "s2": None, "s3": 80.0, "s4": None, "s5": 10.0},
                         "contrib": {"s1": 10.0, "s2": 0.0, "s3": 40.0, "s4": 0.0, "s5": 5.0},
                         "missing": ["s2", "s4"], "backfilled": backfilled} for rid, rk, v in rows]}
        f = week_path("index", date.fromisoformat(wk), "json", data)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json_text(idx), encoding="utf-8")
        sig = [{k: None for k in SIGNAL_FIELDS} | {"repo_id": rid, "full_name": "x", "s1_stars_gain": 9,
                                                       "s3_merged_prs": 3, "s4_status": "none",
                                                       "backfilled": int(backfilled)} for rid, _, _ in rows]
        sf = week_path("signals", date.fromisoformat(wk), "csv", data)
        sf.parent.mkdir(parents=True, exist_ok=True)
        sf.write_text(csv_text(SIGNAL_FIELDS, sig), encoding="utf-8")
    return Config(root, 200, 10, W, 1, RULES_V1), data


def test_site_export_weeks_week_and_repo_files(tmp_path):
    cfg, data = _setup(tmp_path)
    out = export_site(cfg, data=data)
    site = data / "site"
    weeks = json.loads((site / "weeks.json").read_text(encoding="utf-8"))
    assert [w["week"] for w in weeks] == ["2026-11-01", "2026-10-25"]
    assert weeks[1]["backfilled"] is True and weeks[0]["issue"] == 1
    wk = json.loads((site / "week" / "2026-11-01.json").read_text(encoding="utf-8"))
    assert wk["top10"][0]["full_name"] == "org/two" and wk["top10"][0]["prev_rank"] == 2
    assert wk["top10"][0]["category"] == "MCP 서버·도구"
    assert wk["by_signal"]["s3"][0]["pct"] == 80.0 and wk["by_signal"]["s2"] == []
    assert set(wk["angles"]) == {"A", "B", "C", "D"}
    repo = json.loads((site / "repo" / "1.json").read_text(encoding="utf-8"))
    assert repo["description"] == "Agent tool" and repo["topics"] == ["mcp"]
    assert [h["week"] for h in repo["history"]] == ["2026-10-25", "2026-11-01"]
    assert repo["history"][0]["backfilled"] is True
    assert repo["latest"]["raw"]["s1_stars_gain"] == 9
    assert out["repos"] == 2 and out["weeks"] == 2


def test_site_export_has_no_llm_text_or_private_paths(tmp_path):
    cfg, data = _setup(tmp_path)
    export_site(cfg, data=data)
    blob = "".join(f.read_text(encoding="utf-8") for f in (data / "site").rglob("*.json"))
    for word in ("what:", "why:", "angle:", ".private", "draft"):
        assert word not in blob
