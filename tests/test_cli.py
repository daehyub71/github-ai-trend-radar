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


def test_cli_backfill_dry_run_makes_no_calls(tmp_path, capsys, monkeypatch):
    root = write_tree(tmp_path, [meta(1, "a/a"), meta(2, "b/b")],
                      {"2026-10-25": [(1, "a/a", 50)], "2026-11-01": [(2, "b/b", 70)]})
    monkeypatch.setenv("RADAR_STARTREND_DIR", str(root))
    assert main(["backfill", "--anchor", "2026-11-01", "--weeks", "1", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert '"repos": 1' in out and "2026-10-25" in out


def test_cli_backfill_needs_token(tmp_path, capsys, monkeypatch):
    root = write_tree(tmp_path, [meta(1, "a/a")], {"2026-10-25": [(1, "a/a", 50)], "2026-11-01": []})
    monkeypatch.setenv("RADAR_STARTREND_DIR", str(root))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert main(["backfill", "--anchor", "2026-11-01", "--weeks", "1"]) == 1
    assert "GITHUB_TOKEN" in capsys.readouterr().err


def test_cli_weekly_waits_when_input_not_updated(tmp_path, capsys, monkeypatch):
    from datetime import date

    import radar.cli as cli

    root = write_tree(tmp_path, [meta(1, "a/a")], {"2026-11-01": [(1, "a/a", 50)]})
    monkeypatch.setenv("RADAR_STARTREND_DIR", str(root))
    monkeypatch.setattr(cli, "_today", lambda: date(2026, 11, 16))  # 기대 주 11-08 이 아직 없다
    assert main(["weekly", "--check-input"]) == cli.EXIT_NOT_READY
    assert "2026-11-08" in capsys.readouterr().err


def test_cli_weekly_check_input_ready_and_dry_run(tmp_path, capsys, monkeypatch):
    from datetime import date

    import radar.cli as cli

    root = write_tree(tmp_path, [meta(1, "a/a")], {"2026-11-08": [(1, "a/a", 50)]})
    monkeypatch.setenv("RADAR_STARTREND_DIR", str(root))
    monkeypatch.setattr(cli, "_today", lambda: date(2026, 11, 16))
    assert main(["weekly", "--check-input"]) == 0
    assert main(["weekly", "--dry-run"]) == 0
    assert '"week": "2026-11-08"' in capsys.readouterr().out


def test_cli_weekly_already_collected_is_ok(tmp_path, capsys, monkeypatch):
    from datetime import date

    import radar.cli as cli

    root = write_tree(tmp_path, [meta(1, "a/a")], {"2026-11-08": [(1, "a/a", 50)]})
    monkeypatch.setenv("RADAR_STARTREND_DIR", str(root))
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setattr(cli, "_today", lambda: date(2026, 11, 16))
    data = tmp_path / "data"
    (data / "signals").mkdir(parents=True)
    (data / "signals" / "2026-11-08.csv").write_text("repo_id\n", encoding="utf-8")
    monkeypatch.setattr(cli, "_data_dir", lambda: data)
    assert main(["weekly"]) == 0
    assert "이미" in capsys.readouterr().out
