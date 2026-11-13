from scripts.size_guard import MB, Entry, check


def test_size_guard_blocks_large_file():
    v = check([Entry("data/signals/2026-11-01.csv", 0, 2 * MB)])
    assert len(v) == 1 and "1MB" in v[0]


def test_size_guard_blocks_non_ascii_name():
    v = check([Entry("data/한글.csv", 0, 10)])
    assert len(v) == 1 and "ASCII" in v[0]


def test_size_guard_blocks_llm_text_in_public_repo():
    for path in ("data/blog/2026-11-01.md", "data/notion/index.json", "data/drafts/x.md",
                 "data/commentary/2026-11-01.json"):
        v = check([Entry(path, 0, 10)])
        assert len(v) == 1 and "비공개 저장소" in v[0], path


def test_size_guard_blocks_large_data_growth():
    v = check([Entry(f"data/signals/{i}.csv", 0, MB - 1) for i in range(6)])
    assert any("늘어난다" in x for x in v)


def test_size_guard_allows_normal_commit():
    assert check([Entry("data/signals/2026-11-01.csv", 0, 200_000), Entry("radar/core/x.py", 10, 20)]) == []
