"""star-trend 공개 데이터 읽기 — 입력 계약 (PLAN §1, SPEC K1).

필드가 없거나 형식이 바뀌면 조용히 넘어가지 않고 ContractError 를 낸다. 그 주 실행은 멈춘다.
"""

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

from radar.core.models import RepoMeta, StarRow
from radar.core.weeks import parse_week

STAR_COLUMNS = ("id", "full_name", "gain", "stars_end", "exact")


class ContractError(Exception):
    """star-trend 데이터가 계약과 다르다."""


def _data(root: Path) -> Path:
    data = root / "data"
    if not data.is_dir():
        raise ContractError(f"star-trend 데이터 폴더가 없다: {data}")
    return data


def load_ai_repos(root: Path) -> dict[int, RepoMeta]:
    """AI 로 판정된 저장소 {id: RepoMeta}. 읽는 시점의 판정이다(PLAN §1)."""
    files = sorted(_data(root).glob("repos/*/*/meta.json"))
    if not files:
        raise ContractError("data/repos 아래 meta.json 이 없다")
    out: dict[int, RepoMeta] = {}
    for f in files:
        d: Any = json.loads(f.read_text(encoding="utf-8"))
        c = d.get("classify") if isinstance(d, dict) else None
        if not isinstance(c, dict) or "is_ai" not in c:
            raise ContractError(f"{f}: classify.is_ai 가 없다")
        if not isinstance(d.get("id"), int) or not isinstance(d.get("full_name"), str):
            raise ContractError(f"{f}: id·full_name 이 없다")
        if c["is_ai"] is True:
            topics = d.get("topics") if isinstance(d.get("topics"), list) else []
            desc = d.get("description") if isinstance(d.get("description"), str) else None
            lang = d.get("language") if isinstance(d.get("language"), str) else None
            out[d["id"]] = RepoMeta(d["id"], d["full_name"], d.get("created"), c.get("category"),
                                    c.get("secondary"), c.get("type"), desc,
                                    tuple(str(t) for t in topics), lang)
    return out


def available_weeks(root: Path) -> list[date]:
    """주간 스타 파일이 있는 주, 오래된 순."""
    return sorted(parse_week(f.stem) for f in _data(root).glob("stars/*/*.csv"))


def load_week_stars(root: Path, week: date) -> list[StarRow]:
    f = _data(root) / "stars" / f"{week.year}" / f"{week.isoformat()}.csv"
    if not f.is_file():
        raise ContractError(f"그 주 스타 파일이 없다: {week.isoformat()}")
    with f.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in STAR_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ContractError(f"{f.name}: 열이 없다 — {', '.join(missing)}")
        try:
            return [StarRow(int(r["id"]), r["full_name"], int(r["gain"]), int(r["stars_end"]),
                            r["exact"] == "1") for r in reader]
        except (TypeError, ValueError) as e:
            raise ContractError(f"{f.name}: 값 형식이 다르다 ({e})") from e


def load_categories(root: Path) -> dict[str, str]:
    """카테고리 키 → 한국어 이름."""
    f = _data(root) / "site" / "categories.json"
    try:
        names = json.loads(f.read_text(encoding="utf-8"))["names"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ContractError(f"categories.json 을 읽지 못했다 ({e})") from e
    if not isinstance(names, dict):
        raise ContractError("categories.json 의 names 가 사전이 아니다")
    return {str(k): str(v) for k, v in names.items()}
