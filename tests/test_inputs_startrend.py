from datetime import date

import pytest

from radar.inputs.startrend import (
    ContractError,
    available_weeks,
    load_ai_repos,
    load_categories,
    load_week_stars,
)
from tests.startrend_fixture import meta, write_tree


def _tree(tmp_path):
    return write_tree(
        tmp_path,
        [meta(101, "o/ai-one"), meta(202, "o/plain", is_ai=False), meta(303, "p/ai-two", category="rag")],
        {"2026-10-25": [(101, "o/ai-one", 40)], "2026-11-01": [(101, "o/ai-one", 70), (202, "o/plain", 12)]},
    )


def test_inputs_loads_only_ai_repos(tmp_path):
    ai = load_ai_repos(_tree(tmp_path))
    assert set(ai) == {101, 303}
    assert ai[303].category == "rag" and ai[303].full_name == "p/ai-two"


def test_inputs_weeks_and_stars(tmp_path):
    root = _tree(tmp_path)
    assert available_weeks(root) == [date(2026, 10, 25), date(2026, 11, 1)]
    rows = load_week_stars(root, date(2026, 11, 1))
    assert [(r.id, r.gain) for r in rows] == [(101, 70), (202, 12)]


def test_inputs_categories(tmp_path):
    assert load_categories(_tree(tmp_path))["mcp-tools"] == "MCP 서버·도구"


def test_inputs_missing_week_is_contract_error(tmp_path):
    with pytest.raises(ContractError):
        load_week_stars(_tree(tmp_path), date(2026, 11, 8))


def test_inputs_missing_column_is_contract_error(tmp_path):
    root = _tree(tmp_path)
    f = root / "data" / "stars" / "2026" / "2026-11-01.csv"
    f.write_text("id,full_name,stars_end\n1,a/b,3\n", encoding="utf-8")
    with pytest.raises(ContractError, match="gain"):
        load_week_stars(root, date(2026, 11, 1))


def test_inputs_meta_without_classify_is_contract_error(tmp_path):
    root = write_tree(tmp_path, [{"id": 1, "full_name": "a/b"}], {})
    with pytest.raises(ContractError, match="classify"):
        load_ai_repos(root)


def test_inputs_missing_root_is_contract_error(tmp_path):
    with pytest.raises(ContractError):
        load_ai_repos(tmp_path / "nope")
