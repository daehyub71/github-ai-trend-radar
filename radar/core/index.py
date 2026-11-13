"""종합 트렌드 지수 — 가중 평균·결측 재분배·기여분 (SPEC §4-1 ②③, D1 · TASKS T2-2)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from radar.core.normalize import combine, percentiles


@dataclass(frozen=True)
class IndexRow:
    repo_id: int
    index: float | None
    contrib: dict[str, float]  # 신호별 기여분 — 합이 지수와 같다
    missing: tuple[str, ...]   # 값이 없어 빠진 신호 (가중치 순서)


def compute(pcts: Mapping[str, Mapping[int, float | None]],
            weights: Mapping[str, int]) -> dict[int, IndexRow]:
    """신호별 백분위로 저장소마다 지수를 낸다.

    값이 없는 신호(None 이거나 그 신호에 저장소가 없음)는 빼고 남은 가중치로 다시 나눈다.
    기여분은 다시 나눈 가중치 × 백분위라서 합이 곧 지수다.

    Args:
        pcts: 신호 키(s1~s5) → 저장소 ID → 백분위.
        weights: 신호 키 → 가중치(합 100).

    Returns:
        저장소 ID → IndexRow.
    """
    ids = {rid for p in pcts.values() for rid in p}
    out: dict[int, IndexRow] = {}
    for rid in ids:
        have = {k: v for k in weights if (v := pcts.get(k, {}).get(rid)) is not None}
        total = sum(weights[k] for k in have)
        contrib = {k: (weights[k] * have[k] / total if k in have else 0.0) for k in weights}
        missing = tuple(k for k in weights if k not in have)
        out[rid] = IndexRow(rid, sum(contrib.values()) if total else None, contrib, missing)
    return out


def rank(rows: Mapping[int, IndexRow], tiebreak: Mapping[int, int]) -> list[int]:
    """지수 큰 순. 같으면 tiebreak(스타 증가 순위) 작은 순, 그다음 ID. 지수 없음은 맨 뒤.

    Args:
        rows: compute 결과.
        tiebreak: 저장소 ID → 동점 시 앞설수록 작은 값.

    Returns:
        저장소 ID 순서.
    """
    def key(rid: int) -> tuple[int, float, int, int]:
        idx = rows[rid].index
        return (idx is None, -(idx or 0.0), tiebreak.get(rid, 10**9), rid)

    return sorted(rows, key=key)


def _num(v: str | None) -> float | None:
    return float(v) if v not in (None, "") else None


def _add(*vals: float | None) -> float | None:
    got = [v for v in vals if v is not None]
    return sum(got) if got else None


def signal_percentiles(rows: Sequence[Mapping[str, str]]) -> dict[str, dict[int, float | None]]:
    """signals/<주>.csv 행 → 신호별 백분위 (SPEC §3·§4-1, D5).

    - S1 스타 증가, S2 포크 증가(실패·결측은 None)
    - S3 머지 PR·고유 작성자·닫힌 이슈 백분위 1:1:1 평균(실패는 None)
    - S4 다운로드·의존 수 백분위 평균 — 패키지 없음(none)·실패는 None
    - S5 HN+GeekNews 글 수 합·점수 합 백분위 평균(실패는 None)

    Args:
        rows: signals CSV 의 행들(문자열 값).

    Returns:
        신호 키 → 저장소 ID → 백분위.
    """
    def col(field: str, sig: str, skip: tuple[str, ...] = ("failed",)) -> dict[int, float | None]:
        return {int(r["repo_id"]): (None if r[f"{sig}_status"] in skip else _num(r[field])) for r in rows}

    def summed(a: str, b: str) -> dict[int, float | None]:
        return {int(r["repo_id"]): (None if r["s5_status"] == "failed" else _add(_num(r[a]), _num(r[b])))
                for r in rows}

    s4_skip = ("failed", "none")
    s3_fields = ("s3_merged_prs", "s3_pr_authors", "s3_closed_issues")
    return {
        "s1": percentiles({int(r["repo_id"]): _num(r["s1_stars_gain"]) for r in rows}),
        "s2": percentiles(col("s2_fork_delta", "s2")),
        "s3": combine([percentiles(col(f, "s3")) for f in s3_fields]),
        "s4": combine([percentiles(col(f, "s4", s4_skip)) for f in ("s4_downloads", "s4_dependents")]),
        "s5": combine([percentiles(summed("s5_hn_stories", "s5_gn_topics")),
                       percentiles(summed("s5_hn_points", "s5_gn_points"))]),
    }
