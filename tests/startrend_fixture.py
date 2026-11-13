"""star-trend 공개 데이터 모양의 작은 가짜 트리 (PLAN §1 입력 계약). 실제 파일과 같은 필드만 쓴다."""

import json
from pathlib import Path
from typing import Any

HEADER = "id,full_name,created,stars_end,gain,exact,d0,d1,d2,d3,d4,d5,d6"


def meta(rid: int, full_name: str, *, is_ai: bool = True, category: str = "mcp-tools",
         **extra: Any) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": rid, "full_name": full_name, "created": "2026-01-01", "language": "Python",
        "classify": {"status": "ok", "is_ai": is_ai, "category": category if is_ai else None,
                     "secondary": None, "type": "도구/라이브러리"},
    }
    d.update(extra)
    return d


def write_tree(root: Path, metas: list[dict[str, Any]], weeks: dict[str, list[tuple[int, str, int]]],
               names: dict[str, str] | None = None) -> Path:
    """root/data/... 를 만든다. weeks = {"2026-11-01": [(id, full_name, gain), ...]}."""
    data = root / "data"
    for m in metas:
        owner, name = m["full_name"].split("/")
        d = data / "repos" / f"{m['id'] % 100:02d}" / f"{owner}__{name}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "meta.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    for week, rows in weeks.items():
        f = data / "stars" / week[:4] / f"{week}.csv"
        f.parent.mkdir(parents=True, exist_ok=True)
        lines = [HEADER] + [f"{rid},{fn},2026-01-01,{1000 + g},{g},0,,,,,,," for rid, fn, g in rows]
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    site = data / "site"
    site.mkdir(parents=True, exist_ok=True)
    (site / "categories.json").write_text(
        json.dumps({"names": names or {"ALL": "ALL", "mcp-tools": "MCP 서버·도구"}}, ensure_ascii=False),
        encoding="utf-8")
    return root
