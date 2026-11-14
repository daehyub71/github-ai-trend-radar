"""글 그림 단계 (SPEC F11 · TASKS T8-4·T8-12) — 차트 C1~C4, 관점 저장소 카드 R1, TOP 10 저장소 설명 그림.

네트워크·LLM 0. 입력은 공개 지수(data/index/)·사이트 데이터(data/site/repo/)와, 있으면
저장소 해설(.private/cards/)·해설 단계가 고른 그림(blog/images/images.json)·사람이 만든 일러스트(blog/gen/).
출력: `.private/weeks/<주>/blog/charts/` 의 PNG 와 `charts.json`
(파일 · 트렌드 관찰 · 카드 · TOP 10 소개 그림).
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
GEN_EXT = ("png", "jpg", "jpeg", "webp")


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _weeks(data: Path, week: date) -> list[dict[str, Any]]:
    return [_read(f) for f in sorted((data / "index").glob("*.json")) if f.stem <= week.isoformat()]


def _key(full_name: str) -> str:
    return full_name.replace("/", "__")


def picture_for(
    blog: Path, full_name: str, card: dict[str, Any] | None, picked: dict[str, Any] | None, wk: str
) -> dict[str, Any] | None:
    """저장소 설명 그림 (D21·D22) — 사람이 만든 일러스트 → 해설 단계가 웹에서 고른 그림 → 구조도 자동 생성.

    경로(file)는 blog/ 기준. 출처(source)와 저작권 상태(rights)를 함께 돌려준다.
    """
    key = _key(full_name)
    for ext in GEN_EXT:
        if (blog / "gen" / f"{key}.{ext}").exists():
            return {
                "file": f"gen/{key}.{ext}",
                "kind": "illustration",
                "source": "사람이 만든 일러스트",
                "rights": "직접 제작",
            }
    if picked and (blog / "images" / picked["file"]).exists():
        return {
            "file": f"images/{picked['file']}",
            "kind": picked["kind"],
            "source": picked["source"],
            "rights": picked["rights"],
            "url": picked.get("url"),
        }
    diagram = (card or {}).get("diagram")
    if diagram:
        name = f"diagram-{key}.png"
        charts.draw_diagram(
            diagram["nodes"], diagram["edges"], blog / "charts" / name, full_name=full_name, week=wk
        )
        return {
            "file": f"charts/{name}",
            "kind": "diagram",
            "source": "README 를 바탕으로 AI 가 정리",
            "rights": "자동 생성",
        }
    return None


def caption(p: dict[str, Any]) -> str:
    return f"그림: {p['source']} · {p['rights']}"


def render_images(cfg: Config, week: date, *, data: Path = DATA, private: Path = PRIVATE) -> dict[str, Any]:
    if charts.pick_font() is None:  # P7 — 네모 글자 그림을 만들지 않는다
        fonts = ", ".join(charts.FONT_CANDIDATES)
        raise ValueError(f"한글 글꼴이 없다({fonts}) — CI 는 fonts-noto-cjk 를 설치한다")
    weeks = _weeks(data, week)
    if not weeks or weeks[-1]["week"] != week.isoformat():
        raise ValueError(f"{week} 주 지수가 없다")
    wk = week.isoformat()
    blog = private / "weeks" / wk / "blog"
    out = blog / "charts"
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
    index_path = blog / "images" / "images.json"
    picked_all: dict[str, Any] = _read(index_path) if index_path.exists() else {}

    def card_of(rid: int) -> dict[str, Any] | None:
        path = private / "cards" / f"{rid}.json"
        c = _read(path) if path.exists() else None
        return c if c and c.get("week") == wk else None

    intros = []
    for r in sorted(
        (r for r in cur["rows"] if r["rank"] is not None and r["rank"] <= TOP_N), key=lambda r: r["rank"]
    ):
        pic = picture_for(
            blog, r["full_name"], card_of(r["repo_id"]), picked_all.get(_key(r["full_name"])), wk
        )
        intros.append(
            {
                "repo_id": r["repo_id"],
                "full_name": r["full_name"],
                "rank": r["rank"],
                "picture": pic,
                "caption": caption(pic) if pic else None,
            }
        )
    made = []
    for k in ("A", "B", "C", "D"):
        for it in (angles.get(k) or {}).get("items", []):
            rid = it["repo_id"]
            r = rows[rid]
            card = card_of(rid)
            pic = picture_for(blog, r["full_name"], card, picked_all.get(_key(r["full_name"])), wk)
            repo_path = data / "site" / "repo" / f"{rid}.json"
            insights = _read(repo_path).get("insights", []) if repo_path.exists() else []
            name = f"card-{_key(r['full_name'])}.png"
            charts.draw_repo_card(
                full_name=r["full_name"],
                category=names.get(r["category"] or "", r["category"] or ""),
                angle=k,
                pct=r["pct"],
                ranks=cd.repo_ranks(weeks, rid, n_weeks=N_WEEKS),
                lines=cd.repo_card_lines(card, insights),
                path=out / name,
                week=wk,
                picture=blog / pic["file"] if pic and pic["kind"] != "diagram" else None,
                diagram=card["diagram"] if pic and pic["kind"] == "diagram" and card else None,
                caption=caption(pic) if pic else "",
            )
            made.append(
                {
                    "repo_id": rid,
                    "full_name": r["full_name"],
                    "angle": k,
                    "file": name,
                    "from_commentary": card is not None,
                    "picture": pic,
                    "illustration": (card or {}).get("illustration"),
                }
            )
    manifest = {
        "week": wk,
        "files": FILES,
        "cards": made,
        "intros": intros,
        "observations": cd.trend_observations(shares, mix, series, top_n=TOP_N),
    }
    write_mutable(out / "charts.json", json_text(manifest))
    return manifest
