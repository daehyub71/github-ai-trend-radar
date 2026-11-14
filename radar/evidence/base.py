"""근거 수집 공통 — 출처 실패 예외와 GitHub 요청 머리말."""

GH_API = "https://api.github.com"


class SourceError(Exception):
    """한 출처를 받지 못했다. 해설 단계는 그 출처만 빼고 이어 간다(실패 출처는 기록에 남긴다)."""


def gh_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}
