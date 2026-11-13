"""S2 포크 — 저장소 메타 스냅샷 (TASKS T1-2, SPEC D10).

ID 로 조회해(`/repositories/{id}`) 이름이 바뀐 저장소도 따라간다. 주간 증가는 지난 스냅샷과의 차이로
core.signals.fork_delta 가 계산한다. 포크 목록 소급은 하지 않는다(MEASURE §1).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from radar.clients.http import HttpClient
from radar.collectors.base import FAILED, GH_API, OK, RepoRef, gh_headers


@dataclass(frozen=True)
class ForkSnapshot:
    id: int
    full_name: str  # 지금 이름 (바뀌었으면 새 이름)
    forks: int | None
    stars: int | None
    archived: bool | None
    status: str
    note: str = ""


def snapshot(client: HttpClient, token: str, repos: Sequence[RepoRef]) -> list[ForkSnapshot]:
    out: list[ForkSnapshot] = []
    for r in repos:
        st, body = client.get_json("gh_rest", f"{GH_API}/repositories/{r.id}", gh_headers(token))
        if st != 200 or not isinstance(body, dict):
            out.append(ForkSnapshot(r.id, r.full_name, None, None, None, FAILED, f"저장소 조회 {st}"))
            continue
        forks = body.get("forks_count")
        if not isinstance(forks, int):
            out.append(ForkSnapshot(r.id, r.full_name, None, None, None, FAILED,
                                    "forks_count 가 없다(형식 변경)"))
            continue
        stars = body.get("stargazers_count")
        out.append(ForkSnapshot(r.id, str(body.get("full_name") or r.full_name), forks,
                                stars if isinstance(stars, int) else None, bool(body.get("archived")), OK))
    return out
