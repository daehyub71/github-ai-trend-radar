"""글 그림 단계 (SPEC F11 · TASKS T8-4) — 차트 C1~C4 와 관점 저장소 카드 R1 을
비공개 저장소 초안 폴더에 그린다.

네트워크·LLM 0. 입력은 공개 지수(data/index/)·사이트 데이터(data/site/repo/)와,
있으면 저장소 해설(.private/cards/).
출력: `.private/weeks/<주>/blog/charts/` 의 PNG 와 `charts.json`(파일 목록 · 트렌드 관찰 문장 · 카드 목록).
"""

import json
from datetime import date
from pathlib import Path
from typing import Any

from radar.config import PROJECT_ROOT, Config
from radar.core import charts_data as cd
from radar.core.angles import select_angles
from radar.inputs.startrend import load_categories
from radar.publish import charts
from radar.store import DATA, json_text, write_mutable

PRIVATE = PROJECT_ROOT / ".private"
TOP_N = 10
N_WEEKS = 12
FILES = {
    "c1": "c1-rank-trend.png",
    "c2": "c2-contribution.png",
    "c3": "c3-signal-map.png",
    "c4": "c4-trend.png",
}


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _weeks(data: Path, week: date) -> list[dict[str, Any]]:
    return [_read(f) for f in sorted((data / "index").glob("*.json")) if f.stem <= week.isoformat()]


def render_images(cfg: Config, week: date, *, data: Path = DATA, private: Path = PRIVATE) -> dict[str, Any]:
    weeks = _weeks(data, week)
    if not weeks or weeks[-1]["week"] != week.isoformat():
        raise ValueError(f"{week} 주 지수가 없다")
    wk = week.isoformat()
    out = private / "weeks" / wk / "blog" / "charts"
    names = load_categories(cfg.startrend_dir)
    cur = weeks[-1]
    angles = select_angles(weeks, cfg.angles)
    series = cd.rank_series(weeks, top_n=TOP_N, n_weeks=N_WEEKS)
    shares = cd.signal_shares(weeks, top_n=TOP_N, n_weeks=N_WEEKS)
    cats, mix = cd.category_mix(weeks, names, top_n=TOP_N, n_weeks=N_WEEKS)
    charts.draw_rank_trend(series, out / FILES["c1"], week=wk, top_n=TOP_N)
    charts.draw_contribution(
        cd.contribution_bars(cur, top_n=TOP_N), out / FILES["c2"], week=wk, weights=cur["weights"]
    )
    charts.draw_signal_map(cd.signal_map(cur, angles, top_n=TOP_N), out / FILES["c3"], week=wk)
    charts.draw_trend_analysis(shares, cats, mix, out / FILES["c4"], week=wk, top_n=TOP_N)
    rows = {r["repo_id"]: r for r in cur["rows"]}
    made = []
    for k in ("A", "B", "C", "D"):
        for it in (angles.get(k) or {}).get("items", []):
            rid = it["repo_id"]
            r = rows[rid]
            card_path = private / "cards" / f"{rid}.json"
            card = _read(card_path) if card_path.exists() else None
            if card and card.get("week") != wk:
                card = None
            repo_path = data / "site" / "repo" / f"{rid}.json"
            insights = _read(repo_path).get("insights", []) if repo_path.exists() else []
            name = f"card-{r['full_name'].replace('/', '__')}.png"
            charts.draw_repo_card(
                full_name=r["full_name"],
                category=names.get(r["category"] or "", r["category"] or ""),
                angle=k,
                pct=r["pct"],
                ranks=cd.repo_ranks(weeks, rid, n_weeks=N_WEEKS),
                lines=cd.repo_card_lines(card, insights),
                path=out / name,
                week=wk,
            )
            made.append(
                {
                    "repo_id": rid,
                    "full_name": r["full_name"],
                    "angle": k,
                    "file": name,
                    "from_commentary": card is not None,
                }
            )
    manifest = {
        "week": wk,
        "files": FILES,
        "cards": made,
        "observations": cd.trend_observations(shares, mix, series, top_n=TOP_N),
    }
    write_mutable(out / "charts.json", json_text(manifest))
    return manifest
