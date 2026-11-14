"""글 그림 그리기 (SPEC F11 · D20 · TASKS T8-4) — matplotlib 은 이 파일에서만 import 한다(층 규칙).

차트 C1~C4 와 저장소 카드 R1 을 PNG(1600×900)로 그린다. 숫자는 `core/charts_data.py` 가 정한 것만 쓴다.
색은 사이트 시각 체계(DESIGN §3)를 따른다.
한글 글꼴은 이름으로 찾고(Noto Sans CJK KR → Apple SD Gothic Neo …),
없으면 기본 글꼴로 그린다(한글이 네모로 나온다 — 워크플로가 글꼴을 설치한다).
"""

import math
import textwrap
from collections.abc import Mapping, Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from matplotlib import font_manager  # noqa: E402 — 백엔드를 정한 뒤에 불러온다
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402
from PIL import Image, UnidentifiedImageError  # noqa: E402

from radar.core.charts_data import Bar, MapPoint, Series, Share, quadrant  # noqa: E402

W, H, DPI = 16, 9, 100  # 1600×900
SIGNALS = ("s1", "s2", "s3", "s4", "s5")
COLORS = {"s1": "#F59E0B", "s2": "#38BDF8", "s3": "#4F46E5", "s4": "#059669", "s5": "#DB2777"}
NAMES = {"s1": "스타", "s2": "포크", "s3": "기여", "s4": "사용", "s5": "언급"}
ANGLE_COLORS = {"A": "#059669", "B": "#DB2777", "C": "#1F5BD8", "D": "#8B5CF6"}
ANGLE_NAMES = {"A": "조용한 강자", "B": "반짝 관심", "C": "꾸준한 상승", "D": "신호 전환"}
LINES = (
    "#1F5BD8",
    "#F59E0B",
    "#059669",
    "#DB2777",
    "#8B5CF6",
    "#0EA5E9",
    "#DC2626",
    "#111827",
    "#A16207",
    "#9CA3AF",
)  # 서로 다른 색상 10개 — 같은 계열 두 개를 쓰지 않는다
CATS = ("#4F46E5", "#059669", "#F59E0B", "#DB2777", "#0EA5E9", "#8B5CF6", "#9CA3AF")
INK, MUTED, GRID, BG, ACCENT, SHADE = "#111827", "#4B5563", "#E5E7EB", "#FFFFFF", "#1F5BD8", "#F3F4F8"
TOP_COLOR = INK  # 신호 지도의 TOP 점 — 관점 C(파랑)와 겹치지 않게
FONT_CANDIDATES = ("Noto Sans CJK KR", "Noto Sans KR", "Apple SD Gothic Neo", "AppleGothic", "NanumGothic")
RANK_TICKS = (1, 2, 3, 5, 10, 20, 50, 100, 200)


IMAGE_FORMATS = {"PNG": "png", "JPEG": "jpg", "GIF": "gif", "WEBP": "webp"}
MIN_W, MIN_H = 200, 100


def inspect_image(data: bytes) -> tuple[str, int, int] | None:
    """받은 내용이 그림인지 — (확장자, 폭, 높이). 형식이 다르거나 너무 작으면 None."""
    from io import BytesIO

    try:
        with Image.open(BytesIO(data)) as im:
            fmt, (w, h) = im.format or "", im.size
            im.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None
    if fmt not in IMAGE_FORMATS or w < MIN_W or h < MIN_H:
        return None
    return IMAGE_FORMATS[fmt], w, h


def pick_font() -> str | None:
    names = {f.name for f in font_manager.fontManager.ttflist}
    return next((n for n in FONT_CANDIDATES if n in names), None)


def _setup() -> None:
    font = pick_font()
    plt.rcParams.update(
        {
            "font.family": [font, "DejaVu Sans"] if font else ["DejaVu Sans"],
            "axes.unicode_minus": False,
            "axes.edgecolor": GRID,
            "axes.labelcolor": MUTED,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "font.size": 13,
        }
    )


def _figure() -> Figure:
    _setup()
    return plt.figure(figsize=(W, H), dpi=DPI, facecolor=BG)


def _head(fig: Figure, title: str, subtitle: str, footer: str) -> None:
    fig.text(0.04, 0.95, title, fontsize=26, fontweight="bold", color=INK, va="top")
    fig.text(0.04, 0.895, subtitle, fontsize=14, color=MUTED, va="top")
    fig.text(0.04, 0.025, footer, fontsize=11, color=MUTED)


def _save(fig: Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, facecolor=BG)
    plt.close(fig)
    return path


def _short(full_name: str) -> str:
    return full_name.split("/", 1)[-1]


def _md(week: str) -> str:
    return week[5:].replace("-", ".")


def _rank_axis(ax: Axes, worst: int, ticks_from: Sequence[int] = RANK_TICKS) -> None:
    ax.set_yscale("log")
    top = max(20, min(250, worst * 1.3))
    ax.set_ylim(top, 0.8)
    ticks = [t for t in ticks_from if t <= top]
    ax.set_yticks(ticks, [f"{t}위" for t in ticks])
    ax.minorticks_off()
    ax.grid(axis="y", color=GRID, linewidth=1)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def _shade_backfill(ax: Axes, flags: Sequence[bool]) -> None:
    for i, bf in enumerate(flags):
        if bf:
            ax.axvspan(i - 0.5, i + 0.5, color=SHADE, zorder=0, linewidth=0)
    if any(flags):
        last = max(i for i, bf in enumerate(flags) if bf)
        ax.text(
            last / 2,
            0.98,
            "소급 주",
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=11,
            color=MUTED,
        )


def draw_rank_trend(series: Sequence[Series], path: Path, *, week: str, top_n: int = 10) -> Path:
    """C1 — 이번 주 TOP n 의 12주 순위 (위가 1위). 후보 밖 주는 끊는다."""
    fig = _figure()
    _head(
        fig,
        f"이번 주 TOP {top_n}, 12주 동안의 순위",
        "위가 1위 · 옅은 칸은 소급 주 · 끊긴 곳은 후보 밖 · 이름 앞 숫자는 이번 주 순위",
        f"깃허브 AI 트렌드 레이더 · {week} 주 · 숫자는 코드 계산",
    )
    ax = fig.add_axes((0.07, 0.10, 0.66, 0.74))
    weeks = [p[0] for p in series[0].points] if series else []
    xs = list(range(len(weeks)))
    worst = 1
    for i, s in enumerate(series):
        ys = [float(r) if r is not None else math.nan for _, r, _ in s.points]
        worst = max([worst] + [int(r) for _, r, _ in s.points if r is not None])
        first = all(r is None for _, r, _ in s.points[:-1])  # 창 안에서 이번 주에 처음 후보가 됐다
        label = f"{s.rank_now}  {_short(s.full_name)}" + ("  · 이번 주 첫 등장" if first else "")
        ax.plot(xs, ys, color=LINES[i % len(LINES)], linewidth=2.6, marker="o", markersize=5, label=label)
    _rank_axis(ax, worst)
    if series:
        _shade_backfill(ax, [p[2] for p in series[0].points])
    ax.set_xticks(xs, [_md(w) for w in weeks])
    ax.set_xlim(-0.5, len(xs) - 0.5)
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        frameon=False,
        fontsize=13,
        labelcolor=INK,
        handlelength=1.6,
    )
    return _save(fig, path)


def draw_contribution(bars: Sequence[Bar], path: Path, *, week: str, weights: Mapping[str, int]) -> Path:
    """C2 — 이번 주 TOP n 의 신호별 기여분(합 = 지수)."""
    fig = _figure()
    _head(
        fig,
        "TOP 10 은 어떤 신호로 올랐나",
        "막대 길이 = 종합 지수, 색 = 신호별 기여분 · 빠진 신호는 계산에서 빼고 가중치를 다시 나눴다",
        f"깃허브 AI 트렌드 레이더 · {week} 주 · 가중치 v1 "
        + " · ".join(f"{NAMES[s]} {weights[s]}" for s in SIGNALS),
    )
    ax = fig.add_axes((0.27, 0.10, 0.62, 0.72))
    ys = list(range(len(bars)))
    for s in SIGNALS:
        left = [sum(b.contrib[t] for t in SIGNALS[: SIGNALS.index(s)]) for b in bars]
        ax.barh(ys, [b.contrib[s] for b in bars], left=left, color=COLORS[s], height=0.62, label=NAMES[s])
    for y, b in zip(ys, bars, strict=True):
        miss = " · 빠짐: " + "·".join(NAMES[m] for m in b.missing) if b.missing else ""
        ax.text(b.index + 1, y, f"{b.index:.1f}{miss}", va="center", fontsize=12, color=INK)
    ax.set_yticks(ys, [f"{b.rank}  {_short(b.full_name)}" for b in bars], fontsize=13, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, 125)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.grid(axis="x", color=GRID)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(loc="lower right", ncol=5, frameon=False, bbox_to_anchor=(1.0, 1.0), fontsize=12)
    return _save(fig, path)


def _free_spot(
    placed: Sequence[tuple[float, float]], x: float, y: float, gap: float = 4.2
) -> tuple[float, float]:
    """이미 찍은 표시와 gap 보다 가까우면 옆(오른쪽, 끝이면 위)으로 비킨다 — 데이터 좌표 0~100."""
    cx, cy = x, y
    for _ in range(12):
        if all(math.hypot(cx - px, cy - py) >= gap for px, py in placed):
            break
        if cx + gap <= 99:
            cx += gap
        else:
            cx, cy = x, cy + gap
    return cx, cy


def draw_signal_map(points: Sequence[MapPoint], path: Path, *, week: str) -> Path:
    """C3 — 관심 × 실사용. 회색은 후보 전체, 숫자는 TOP 순위, A1·B2 같은 기호는 관점 유형.

    이름은 오른쪽 목록에 둔다.
    """
    fig = _figure()
    _head(
        fig,
        "신호 지도 — 관심과 실사용",
        f"후보 {len(points)}개 · 가로 = 스타·언급 백분위 평균, 세로 = 기여·사용 백분위 평균"
        " · 이름은 오른쪽 목록",
        f"깃허브 AI 트렌드 레이더 · {week} 주 · 백분위는 그 주 후보 안 순위",
    )
    ax = fig.add_axes((0.06, 0.10, 0.56, 0.74))
    ax.scatter(
        [p.attention for p in points],
        [p.usage for p in points],
        s=22,
        color="#9CA3AF",
        alpha=0.45,
        linewidths=0,
    )
    groups: dict[str, list[tuple[str, str]]] = {"TOP": [], "A": [], "B": [], "C": [], "D": []}
    seen = {k: 0 for k in ("A", "B", "C", "D")}
    placed: list[tuple[float, float]] = []
    for p in sorted((p for p in points if p.mark), key=lambda p: (p.mark or "").isdigit() is False):
        mark = p.mark or ""
        if mark.isdigit():
            code, color, key = mark, TOP_COLOR, "TOP"
        else:
            seen[mark] += 1
            code, color, key = f"{mark}{seen[mark]}", ANGLE_COLORS[mark], mark
        groups[key].append((code, _short(p.full_name)))
        x, y = _free_spot(placed, p.attention, p.usage)
        placed.append((x, y))
        if (x, y) != (p.attention, p.usage):  # 겹치면 옆으로 비켜 놓고 원래 점까지 선을 긋는다
            ax.plot([p.attention, x], [p.usage, y], color=color, linewidth=1.2, zorder=2)
            ax.scatter([p.attention], [p.usage], s=30, color=color, zorder=3)
        ax.scatter([x], [y], s=520, color=color, zorder=3, edgecolors=BG, linewidths=1.5)
        ax.text(x, y, code, ha="center", va="center", fontsize=10, color=BG, fontweight="bold", zorder=4)
    ax.axhline(50, color=GRID, linewidth=1.5)
    ax.axvline(50, color=GRID, linewidth=1.5)
    for x, y, ha, va in (
        (98, 98, "right", "top"),
        (2, 98, "left", "top"),
        (98, 2, "right", "bottom"),
        (2, 2, "left", "bottom"),
    ):
        ax.text(x, y, quadrant(x, y), ha=ha, va=va, fontsize=15, color=MUTED, fontweight="bold")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_xlabel("관심 →")
    ax.set_ylabel("실사용 →")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    y = 0.84
    titles = {"TOP": ("이번 주 TOP 10", TOP_COLOR)} | {
        k: (f"관점 {k} · {ANGLE_NAMES[k]}", ANGLE_COLORS[k]) for k in ("A", "B", "C", "D")
    }
    for key, items in groups.items():
        if not items:
            continue
        title, color = titles[key]
        fig.text(0.66, y, "●", fontsize=15, color=color, va="top")
        fig.text(0.68, y, title, fontsize=14, color=INK, fontweight="bold", va="top")
        y -= 0.042
        text = " · ".join(f"{code} {name}" for code, name in sorted(items, key=lambda t: (len(t[0]), t[0])))
        for line in textwrap.wrap(text, width=48):
            fig.text(0.68, y, line, fontsize=11.5, color=INK, va="top")
            y -= 0.033
        y -= 0.02
    return _save(fig, path)


def draw_trend_analysis(
    shares: Sequence[Share],
    cats: Sequence[str],
    mix: Sequence[tuple[str, Mapping[str, int]]],
    path: Path,
    *,
    week: str,
    top_n: int = 10,
) -> Path:
    """C4 — 주별 TOP n 기여분의 신호 비중(왼쪽)과 카테고리 분포(오른쪽)."""
    fig = _figure()
    bf = [sh.week for sh in shares if sh.backfilled]
    note = f" · {_md(bf[-1])} 주까지는 소급 값" if bf else ""
    _head(
        fig,
        f"12주 트렌드 — TOP {top_n} 을 만든 신호와 카테고리",
        f"왼쪽: 주마다 TOP 기여분에서 각 신호의 비중 · 오른쪽: TOP 저장소의 카테고리 수{note}",
        f"깃허브 AI 트렌드 레이더 · {week} 주 · 숫자는 코드 계산",
    )
    left = fig.add_axes((0.06, 0.13, 0.42, 0.60))
    xs = list(range(len(shares)))
    left.stackplot(
        xs,
        *[[sh.shares[s] for sh in shares] for s in SIGNALS],
        colors=[COLORS[s] for s in SIGNALS],
        labels=[NAMES[s] for s in SIGNALS],
        alpha=0.92,
    )
    left.set_ylim(0, 100)
    left.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    left.set_xticks(xs, [_md(sh.week) for sh in shares], rotation=45, fontsize=11)
    left.set_xlim(0, max(len(xs) - 1, 1))
    left.legend(loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=5, frameon=False, fontsize=12)
    right = fig.add_axes((0.55, 0.13, 0.42, 0.60))
    rx = list(range(len(mix)))
    bottom = [0] * len(mix)
    for i, c in enumerate(cats):
        vals = [row[1].get(c, 0) for row in mix]
        right.bar(
            rx,
            vals,
            bottom=bottom,
            color=CATS[i % len(CATS)] if c != "기타" else "#9CA3AF",
            width=0.7,
            label=c,
        )
        bottom = [b + v for b, v in zip(bottom, vals, strict=True)]
    right.set_xticks(rx, [_md(w) for w, _ in mix], rotation=45, fontsize=11)
    right.set_ylim(0, top_n)
    right.legend(loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=4, frameon=False, fontsize=11)
    for ax in (left, right):
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    return _save(fig, path)


def _layers(nodes: Sequence[Mapping[str, str]], edges: Sequence[Mapping[str, str]]) -> dict[str, int]:
    """상자마다 단(왼쪽부터 0) — 들어오는 화살표가 없는 상자에서 가장 긴 길. 고리는 순서대로 끊는다."""
    ids = [n["id"] for n in nodes]
    layer = {i: 0 for i in ids}
    for _ in range(len(ids)):
        changed = False
        for e in edges:
            a, b = e["from"], e["to"]
            if a in layer and b in layer and ids.index(a) < ids.index(b) and layer[b] < layer[a] + 1:
                layer[b] = layer[a] + 1
                changed = True
        if not changed:
            break
    return layer


def draw_diagram(
    nodes: Sequence[Mapping[str, str]],
    edges: Sequence[Mapping[str, str]],
    path: Path,
    *,
    full_name: str,
    week: str,
) -> Path:
    """구조도(D22) — README 를 바탕으로 AI 가 정한 상자·화살표를 왼쪽 → 오른쪽 흐름으로."""
    fig = _figure()
    _head(
        fig,
        f"{_short(full_name)} — 어떻게 동작하나",
        "README 를 바탕으로 AI 가 정리한 구조도 · 자동 생성",
        f"깃허브 AI 트렌드 레이더 · {week} 주 · {full_name}",
    )
    ax = fig.add_axes((0.04, 0.08, 0.92, 0.76))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    layer = _layers(nodes, edges)
    cols = max(layer.values()) + 1 if layer else 1
    by_col: dict[int, list[str]] = {}
    for n in nodes:
        by_col.setdefault(layer[n["id"]], []).append(n["id"])
    bw, bh = min(24.0, 80.0 / cols), 16.0
    pos: dict[str, tuple[float, float]] = {}
    for c, members in by_col.items():
        x = 6 + (c + 0.5) * (88 / cols)
        for k, nid in enumerate(members):
            y = 50 + ((len(members) - 1) / 2 - k) * (bh + 10)
            pos[nid] = (x, y)
    labels = {n["id"]: n["label"] for n in nodes}
    for e in edges:
        (x1, y1), (x2, y2) = pos[e["from"]], pos[e["to"]]
        ax.annotate(
            "",
            xy=(x2 - bw / 2, y2),
            xytext=(x1 + bw / 2, y1),
            arrowprops={"arrowstyle": "-|>", "color": MUTED, "linewidth": 2, "mutation_scale": 22},
        )
        if e.get("label"):
            ax.text(
                (x1 + x2) / 2,
                (y1 + y2) / 2 + 3,
                e["label"],
                ha="center",
                va="bottom",
                fontsize=13,
                color=MUTED,
            )
    for nid, (x, y) in pos.items():
        ax.add_patch(
            FancyBboxPatch(
                (x - bw / 2, y - bh / 2),
                bw,
                bh,
                boxstyle="round,pad=0.4,rounding_size=2",
                facecolor="#EEF2FF",
                edgecolor=ACCENT,
                linewidth=2,
            )
        )
        ax.text(
            x,
            y,
            "\n".join(textwrap.wrap(labels[nid], width=10)[:3]),
            ha="center",
            va="center",
            fontsize=17,
            color=INK,
            fontweight="bold",
        )
    return _save(fig, path)


def draw_repo_card(
    *,
    full_name: str,
    category: str,
    angle: str | None,
    pct: Mapping[str, float | None],
    ranks: Sequence[tuple[str, int | None]],
    lines: Sequence[str],
    path: Path,
    week: str,
    picture: Path | None = None,
    caption: str = "",
) -> Path:
    """R1 — 저장소 카드: 이름·카테고리·관점, 설명 그림(있으면), 해설 요약(또는 코드 관찰),
    신호 막대, 12주 순위.
    """
    fig = _figure()
    color = ANGLE_COLORS.get(angle or "", ACCENT)
    fig.patches.append(Rectangle((0, 0.965), 1, 0.035, color=color, transform=fig.transFigure, figure=fig))
    tag = f"관점 {angle} · {ANGLE_NAMES[angle]}" if angle in ANGLE_NAMES else "이번 주 TOP"
    fig.text(0.05, 0.90, tag, fontsize=16, color=color, fontweight="bold", va="top")
    fig.text(0.05, 0.84, full_name, fontsize=32, color=INK, fontweight="bold", va="top")
    fig.text(0.05, 0.765, category, fontsize=15, color=MUTED, va="top")
    y, size, width, rows, step = 0.68, 17, 40, 3, 0.05
    if picture is not None:
        pic = fig.add_axes((0.05, 0.38, 0.52, 0.33))
        with Image.open(picture) as im:
            pic.imshow(im.convert("RGB"))
        pic.axis("off")
        fig.text(0.05, 0.365, caption, fontsize=11, color=MUTED, va="top")
        y, size, width, rows, step = 0.31, 14, 52, 2, 0.04
    for line in lines[:3]:
        wrapped = textwrap.wrap(line, width=width) or [""]
        for j, part in enumerate(wrapped[:rows]):
            fig.text(0.05, y, ("· " if j == 0 else "  ") + part, fontsize=size, color=INK, va="top")
            y -= step
        y -= step / 2
    bars = fig.add_axes((0.62, 0.50, 0.33, 0.36))
    ys = list(range(len(SIGNALS)))
    vals = [pct.get(s) for s in SIGNALS]
    bars.barh(ys, [100] * len(ys), color=SHADE, height=0.55)
    bars.barh(ys, [v or 0 for v in vals], color=[COLORS[s] for s in SIGNALS], height=0.55)
    for yy, v in zip(ys, vals, strict=True):
        bars.text(
            102, yy, "빠짐" if v is None else f"{v:.0f}", va="center", fontsize=14, color=INK if v else MUTED
        )
    bars.set_yticks(ys, [NAMES[s] for s in SIGNALS], fontsize=15, color=INK)
    bars.invert_yaxis()
    bars.set_xlim(0, 115)
    bars.set_xticks([])
    bars.set_title("신호별 백분위 (후보 안)", fontsize=15, color=MUTED, loc="left")
    for side in ("top", "right", "bottom"):
        bars.spines[side].set_visible(False)
    trend = fig.add_axes((0.62, 0.12, 0.33, 0.28))
    xs = list(range(len(ranks)))
    ry = [float(r) if r is not None else math.nan for _, r in ranks]
    trend.plot(xs, ry, color=color, linewidth=3, marker="o", markersize=5)
    _rank_axis(trend, max([1] + [int(r) for _, r in ranks if r is not None]), ticks_from=(1, 10, 50, 200))
    if ranks:
        trend.set_xticks([0, len(ranks) - 1], [_md(ranks[0][0]), _md(ranks[-1][0])])
    trend.set_title("12주 종합 순위", fontsize=15, color=MUTED, loc="left")
    fig.text(
        0.05,
        0.025,
        f"깃허브 AI 트렌드 레이더 · {week} 주 · 숫자는 코드 계산, 글은 AI 해설 요약",
        fontsize=11,
        color=MUTED,
    )
    return _save(fig, path)
