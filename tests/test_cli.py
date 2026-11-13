from radar.cli import main
from tests.startrend_fixture import meta, write_tree


def test_cli_contract_reports_counts(tmp_path, capsys, monkeypatch):
    root = write_tree(tmp_path, [meta(1, "a/a"), meta(2, "b/b"), meta(3, "c/c", is_ai=False)],
                      {"2026-11-01": [(1, "a/a", 50), (2, "b/b", 70), (3, "c/c", 900)]})
    monkeypatch.setenv("RADAR_STARTREND_DIR", str(root))
    assert main(["contract"]) == 0
    out = capsys.readouterr().out
    assert "AI 저장소 2" in out and "2026-11-01" in out and "후보 2" in out


def test_cli_contract_fails_on_broken_input(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("RADAR_STARTREND_DIR", str(tmp_path / "missing"))
    assert main(["contract"]) == 1
    assert "계약" in capsys.readouterr().err


def test_cli_collect_dry_run_makes_no_calls(tmp_path, capsys, monkeypatch):
    root = write_tree(tmp_path, [meta(1, "a/a"), meta(2, "b/b")],
                      {"2026-11-01": [(1, "a/a", 50), (2, "b/b", 70)]})
    monkeypatch.setenv("RADAR_STARTREND_DIR", str(root))
    assert main(["collect", "--dry-run"]) == 0  # 네트워크는 conftest 가 막는다 — 호출하면 실패한다
    assert '"candidates": 2' in capsys.readouterr().out


def test_cli_collect_needs_token(tmp_path, capsys, monkeypatch):
    root = write_tree(tmp_path, [meta(1, "a/a")], {"2026-11-01": [(1, "a/a", 50)]})
    monkeypatch.setenv("RADAR_STARTREND_DIR", str(root))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert main(["collect"]) == 1
    assert "GITHUB_TOKEN" in capsys.readouterr().err
