"""후보 선정 (SPEC F2·D2) — AI 저장소의 스타 증가 상위 cap 개 + 지난주 TOP 에서 빠진 저장소."""

from collections.abc import Collection, Sequence

from radar.core.models import Candidate, StarRow


def select_candidates(stars: Sequence[StarRow], ai_ids: Collection[int], previous_top: Sequence[int],
                      cap: int) -> list[Candidate]:
    """같은 입력이면 같은 결과. 동점은 이름(소문자)·ID 순."""
    ranked = sorted((r for r in stars if r.id in ai_ids), key=lambda r: (-r.gain, r.full_name.lower(), r.id))
    rank = {r.id: i for i, r in enumerate(ranked, 1)}
    out = [Candidate(r.id, r.full_name, r.gain, rank[r.id], "gain_top") for r in ranked[:cap]]
    chosen = {c.id for c in out}
    by_id = {r.id: r for r in ranked}
    for rid in previous_top:
        if rid in chosen or rid not in ai_ids:
            continue
        row = by_id.get(rid)
        out.append(Candidate(rid, row.full_name if row else "", row.gain if row else 0,
                             rank.get(rid), "prev_top"))
        chosen.add(rid)
    return out
