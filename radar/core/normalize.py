"""신호 값 → 후보 안 순위 백분위 (SPEC §4-1 ①, D5 · TASKS T2-1).

SPEC 은 "로그를 취한 뒤 비교"라고 쓴다. 순위 백분위는 단조 변환에 바뀌지 않으므로
로그를 취한 값과 원래 값의 결과가 같다 — 여기서는 원래 값으로 순위를 매긴다.
"""

from collections.abc import Mapping, Sequence


def percentiles(values: Mapping[int, float | None]) -> dict[int, float | None]:
    """값이 있는 저장소끼리 순위를 매겨 0~100 으로 바꾼다.

    동점은 가운데 순위를 받는다. 값이 없으면(None) 순위에서 빠지고 None 으로 남는다.
    값이 하나뿐이면 100 이다.

    Args:
        values: 저장소 ID → 주간 값.

    Returns:
        저장소 ID → 백분위(또는 None).
    """
    present = sorted((v, rid) for rid, v in values.items() if v is not None)
    out: dict[int, float | None] = {rid: None for rid, v in values.items() if v is None}
    n = len(present)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and present[j + 1][0] == present[i][0]:
            j += 1
        mid = (i + j) / 2  # 0 부터 센 가운데 순위
        pct = 100.0 if n == 1 else 100.0 * mid / (n - 1)
        for k in range(i, j + 1):
            out[present[k][1]] = pct
        i = j + 1
    return out


def combine(parts: Sequence[Mapping[int, float | None]]) -> dict[int, float | None]:
    """하위 값 백분위를 1:1 평균한다(D5). 값이 있는 것만 평균하고, 모두 없으면 None.

    Args:
        parts: 하위 값별 백분위 사전들.

    Returns:
        저장소 ID → 합성 백분위(또는 None).
    """
    ids = {rid for p in parts for rid in p}
    out: dict[int, float | None] = {}
    for rid in ids:
        got = [v for p in parts if (v := p.get(rid)) is not None]
        out[rid] = sum(got) / len(got) if got else None
    return out
