"""관점 글 유형 선정 A~D (SPEC F9, D9 · TASKS T2-8). 숫자로만 고른다 — LLM 은 설명만 쓴다.

- A 조용한 강자: 스타 백분위 < a_star_max 이고 사용·기여(S3·S4, S4 없으면 S2·S3) 평균 ≥ a_use_min
- B 반짝 관심: 스타 또는 언급 백분위 ≥ b_attention_min 이고 포크·기여·사용 평균 ≤ b_use_max
- C 꾸준한 상승: 이번 주까지 지수가 c_rises 번 연속 올랐다 (이번 주 포함 c_rises+1 주 이력)
- D 신호 전환: lookback 주 전보다 관심(S1+S5) 비중이 내려가고
  사용·기여(S3+S4) 비중이 d_shift_min %p 이상 올랐다

거리가 먼 순(조건을 넘은 여유의 합)으로 유형마다 cap 개. 한 저장소는 D → C → A → B 순으로 한 유형에만.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

ORDER = ("D", "C", "A", "B")
OK = "ok"
INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class AngleRules:
    a_star_max: float = 50.0
    a_use_min: float = 80.0
    b_attention_min: float = 90.0
    b_use_max: float = 30.0
    c_rises: int = 4
    lookback: int = 4
    d_shift_min: float = 20.0
    cap: int = 5
    version: int = 1


RULES_V1 = AngleRules()


def _mean(vals: Sequence[float | None]) -> float | None:
    got = [v for v in vals if v is not None]
    return sum(got) / len(got) if got else None


def _shares(row: Mapping[str, Any]) -> tuple[float, float] | None:
    idx = row.get("index")
    if not idx:
        return None
    c = row["contrib"]
    return 100.0 * (c["s1"] + c["s5"]) / idx, 100.0 * (c["s3"] + c["s4"]) / idx


def _a(row: Mapping[str, Any], r: AngleRules) -> tuple[float, dict[str, Any]] | None:
    p = row["pct"]
    s1 = p["s1"]
    use = _mean([p["s3"], p["s4"]]) if p["s4"] is not None else _mean([p["s2"], p["s3"]])
    if s1 is None or use is None or not (s1 < r.a_star_max and use >= r.a_use_min):
        return None
    basis = "s3·s4" if p["s4"] is not None else "s2·s3"
    return (r.a_star_max - s1) + (use - r.a_use_min), {"s1": s1, "use": round(use, 2), "use_basis": basis}


def _b(row: Mapping[str, Any], r: AngleRules) -> tuple[float, dict[str, Any]] | None:
    p = row["pct"]
    att = max((v for v in (p["s1"], p["s5"]) if v is not None), default=None)
    use = _mean([p["s2"], p["s3"], p["s4"]])
    if att is None or use is None or not (att >= r.b_attention_min and use <= r.b_use_max):
        return None
    ev = {"s1": p["s1"], "s5": p["s5"], "use": round(use, 2)}
    return (att - r.b_attention_min) + (r.b_use_max - use), ev


def select_angles(weeks: Sequence[Mapping[str, Any]], rules: AngleRules = RULES_V1) -> dict[str, Any]:
    """weeks: index/<주>.json 들 (오래된 순, 마지막이 이번 주). 유형별 {status, items} 를 돌려준다."""
    cur = {r["repo_id"]: r for r in weeks[-1]["rows"]}
    hist = [{r["repo_id"]: r for r in w["rows"]} for w in weeks]
    need = max(rules.c_rises, rules.lookback) + 1
    enough = len(weeks) >= need
    found: dict[str, list[tuple[float, int, dict[str, Any]]]] = {k: [] for k in ORDER}

    for rid, row in cur.items():
        if enough:
            series = [h.get(rid, {}).get("index") for h in hist[-(rules.c_rises + 1):]]
            if all(v is not None for v in series):
                vals = [float(v) for v in series if v is not None]
                if all(b > a for a, b in zip(vals, vals[1:], strict=False)):
                    found["C"].append((vals[-1] - vals[0], rid, {"index": series}))
            old = hist[-(rules.lookback + 1)].get(rid)
            then, now = (_shares(old) if old else None), _shares(row)
            if then and now and now[0] < then[0] and now[1] - then[1] >= rules.d_shift_min:
                ev = {"attention_share": [round(then[0], 1), round(now[0], 1)],
                      "use_share": [round(then[1], 1), round(now[1], 1)]}
                found["D"].append((now[1] - then[1], rid, ev))
        for key, fn in (("A", _a), ("B", _b)):
            hit = fn(row, rules)
            if hit:
                found[key].append((hit[0], rid, hit[1]))

    taken: set[int] = set()
    out: dict[str, Any] = {"rules_version": rules.version}
    for key in ORDER:
        status = INSUFFICIENT if key in ("C", "D") and not enough else OK
        items: list[dict[str, Any]] = []
        for score, rid, ev in sorted(found[key], key=lambda t: (-t[0], t[1])):
            if rid in taken or len(items) >= rules.cap:
                continue
            taken.add(rid)
            items.append({"repo_id": rid, "full_name": cur[rid]["full_name"], "score": round(score, 2),
                          "evidence": ev})
        out[key] = {"status": status, "items": items}
    return out
