"""T2-6 — 신호 간 상관·결측률·동점·실효 가중치 실측 (SPEC §4-1, MEASURE §3). 네트워크 없음.

data/index/*.json 을 읽어 집계만 출력한다(저장소 이름은 상위 사례만).
"""

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

SIGS = ("s1", "s2", "s3", "s4", "s5")
NAMES = {"s1": "스타", "s2": "포크", "s3": "기여", "s4": "사용", "s5": "언급"}


def main(data: Path) -> None:
    files = sorted((data / "index").glob("*.json"))
    weeks = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    rows = [r for w in weeks for r in w["rows"]]
    print(f"주 {len(weeks)}개 ({weeks[0]['week']}~{weeks[-1]['week']}) · 행 {len(rows)}")

    print("\n## 결측률·최빈값 비율 (전체 행)")
    for s in SIGS:
        vals = [r["pct"][s] for r in rows]
        have = [v for v in vals if v is not None]
        mode = Counter(have).most_common(1)
        tie = mode[0][1] / len(have) if have else 0
        miss = 1 - len(have) / len(vals)
        print(f"{NAMES[s]} 결측 {miss:.1%} · 값 있음 {len(have)} · 최빈값 비율 {tie:.1%}")

    print("\n## 신호 간 상관 (백분위 피어슨 = 순위 상관, 둘 다 있는 행)")
    for i, a in enumerate(SIGS):
        for b in SIGS[i + 1:]:
            pairs = [(r["pct"][a], r["pct"][b]) for r in rows
                     if r["pct"][a] is not None and r["pct"][b] is not None]
            if len(pairs) < 10:
                print(f"{NAMES[a]}-{NAMES[b]} 표본 {len(pairs)} (부족)")
                continue
            x, y = zip(*pairs, strict=True)
            print(f"{NAMES[a]}-{NAMES[b]} r={statistics.correlation(x, y):+.2f} (n={len(pairs)})")

    print("\n## 실효 가중치 (지수에서 신호별 기여분 평균 비중)")
    for s in SIGS:
        shares = [r["contrib"][s] / r["index"] for r in rows if r["index"]]
        print(f"{NAMES[s]} {statistics.mean(shares):.1%}")

    print("\n## 주별 — 스타 TOP10 과 지수 TOP10 겹침 · 지난주 지수 TOP10 유지")
    prev: set[int] = set()
    for w in weeks:
        top = {r["repo_id"] for r in w["rows"][:10]}
        star = {r["repo_id"] for r in w["rows"] if r["gain_rank"] is not None and r["gain_rank"] <= 10}
        keep = len(top & prev) if prev else "-"
        print(f"{w['week']} 겹침 {len(top & star)}/10 · 유지 {keep} · 후보 {w['candidates']}")
        prev = top

    print("\n## S4 있음/없음 저장소의 지수 TOP10 비율")
    for label, want in (("있음", True), ("없음", False)):
        sub = [r for r in rows if (r["pct"]["s4"] is not None) == want]
        print(f"S4 {label} {len(sub)}행 · TOP10 {sum(r['rank'] <= 10 for r in sub)} "
              f"({sum(r['rank'] <= 10 for r in sub) / max(len(sub), 1):.1%})")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "data")
