"""평문 저장 (TASKS T1-7, PLAN §4·P1) — 정본은 data/ 의 CSV·JSON.

주간 파일은 한 번 쓰면 다시 쓰지 않는다(write_once). 내용이 같으면 넘어가고, 다르면 WriteOnceError.
매주 갱신하는 메타 캐시(패키지 연결)만 write_mutable 로 쓴다.
"""

import csv
import io
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from radar.config import PROJECT_ROOT

DATA = PROJECT_ROOT / "data"


class WriteOnceError(Exception):
    """이미 있는 주간 파일을 다른 내용으로 덮어쓰려 했다."""


def write_once(path: Path, text: str) -> bool:
    """썼으면 True, 같은 내용이 이미 있으면 False."""
    if path.exists():
        if path.read_text(encoding="utf-8") == text:
            return False
        raise WriteOnceError(f"{path.name} 은 이미 있고 내용이 다르다 — 주간 파일은 다시 쓰지 않는다")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def write_mutable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def csv_text(fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> str:
    """None 은 빈 칸(결측)으로 쓴다. 줄바꿈은 \\n."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(fieldnames), lineterminator="\n", extrasaction="raise")
    w.writeheader()
    for r in rows:
        w.writerow({k: "" if v is None else v for k, v in r.items()})
    return buf.getvalue()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def json_text(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def week_path(kind: str, week: date, suffix: str, data: Path = DATA) -> Path:
    return data / kind / f"{week.isoformat()}.{suffix}"
