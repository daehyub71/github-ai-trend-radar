"""T1-7 — 평문 저장: 한 번 쓴 주간 파일은 다시 쓰지 않는다 (PLAN §4)."""

import pytest

from radar.store import WriteOnceError, csv_text, read_csv, write_mutable, write_once


def test_store_write_once_then_same_content_is_noop(tmp_path):
    f = tmp_path / "a" / "x.csv"
    assert write_once(f, "a\n1\n") is True
    assert write_once(f, "a\n1\n") is False


def test_store_write_once_refuses_different_content(tmp_path):
    f = tmp_path / "x.csv"
    write_once(f, "a\n1\n")
    with pytest.raises(WriteOnceError):
        write_once(f, "a\n2\n")
    assert f.read_text() == "a\n1\n"


def test_store_mutable_overwrites(tmp_path):
    f = tmp_path / "m.json"
    write_mutable(f, "1")
    write_mutable(f, "2")
    assert f.read_text() == "2"


def test_store_csv_roundtrip_keeps_missing_as_empty(tmp_path):
    text = csv_text(["id", "v"], [{"id": 1, "v": None}, {"id": 2, "v": 5}])
    assert text == "id,v\n1,\n2,5\n"
    f = tmp_path / "x.csv"
    write_once(f, text)
    assert read_csv(f) == [{"id": "1", "v": ""}, {"id": "2", "v": "5"}]
