"""수집기 공통 — 상태 값과 GitHub 요청 머리말 (SPEC F3)."""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

OK, PARTIAL, FAILED = "ok", "partial", "failed"
GH_API = "https://api.github.com"


@dataclass(frozen=True)
class RepoRef:
    id: int
    full_name: str


def gh_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def utc_day(stamp: str | None) -> date | None:
    """ISO 시각 → UTC 날짜. 읽지 못하면 None."""
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(UTC).date()
    except ValueError:
        return None


def is_bot(user: object) -> bool:
    if not isinstance(user, dict):
        return False
    return user.get("type") == "Bot" or str(user.get("login", "")).endswith("[bot]")


def same_repo(url: object, full_name: str) -> bool:
    """URL 이 github.com/<full_name> 이거나 그 아래 경로인가 (대소문자·.git·git+ 무시)."""
    if not isinstance(url, str):
        return False
    pat = r"github\.com[/:]" + re.escape(full_name.lower()) + r"(?:\.git)?(?:$|[/#?])"
    return re.search(pat, url.lower().strip()) is not None
