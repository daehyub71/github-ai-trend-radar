"""T2-3 — signals → index/<주>.json (SPEC F1·F4)."""

import json
from datetime import date

import pytest

from radar.config import Config
from radar.pipeline import SIGNAL_FIELDS, build_index
from radar.store import WriteOnceError, csv_text, week_path

WEEK = date(2026, 11, 1)
CFG = Config(None, 200, 10, {"s1": 15, "s2": 15, "s3": 25, "s4": 30, "s5": 15}, 1)  # type: ignore[arg-type]


def _signals(data, n=12):
    rows = []
    for i in range(1, n + 1):
        rows.append({f: None for f in SIGNAL_FIELDS} | {
            "repo_id": i, "full_name": f"org/r{i}", "category": "앱", "gain_rank": i, "reason": "gain",
            "s1_stars_gain": 1000 - i, "s2_status": "ok",
            "s3_merged_prs": i, "s3_pr_authors": i, "s3_closed_issues": i, "s3_status": "ok",
            "s4_status": "none", "s5_hn_stories": 0, "s5_hn_points": 0, "s5_gn_topics": 0, "s5_gn_points": 0,
            "s5_status": "ok", "backfilled": 0})
    f = week_path("signals", WEEK, "csv", data)
    f.parent.mkdir(parents=True)
    f.write_text(csv_text(SIGNAL_FIELDS, rows), encoding="utf-8")


def test_pipeline_index_writes_ranked_rows_and_top10(tmp_path):
    _signals(tmp_path)
    out = build_index(CFG, WEEK, data=tmp_path)
    saved = json.loads(week_path("index", WEEK, "json", tmp_path).read_text(encoding="utf-8"))
    assert saved == out
    assert out["weights_version"] == 1 and out["weights"]["s4"] == 30
    assert len(out["top"]) == 10
    rows = out["rows"]
    assert [r["rank"] for r in rows] == list(range(1, 13))
    first = rows[0]
    assert set(first["missing"]) == {"s2", "s4"}
    assert sum(first["contrib"].values()) == pytest.approx(first["index"], abs=0.05)
    assert out["top"] == [r["repo_id"] for r in rows[:10]]


def test_pipeline_index_same_input_same_file_and_old_weights_kept(tmp_path):
    _signals(tmp_path)
    assert build_index(CFG, WEEK, data=tmp_path) == build_index(CFG, WEEK, data=tmp_path)
    v2 = Config(None, 200, 10, {"s1": 20, "s2": 10, "s3": 25, "s4": 30, "s5": 15}, 2)  # type: ignore[arg-type]
    with pytest.raises(WriteOnceError):
        build_index(v2, WEEK, data=tmp_path)


def test_pipeline_index_requires_signals(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_index(CFG, WEEK, data=tmp_path)
