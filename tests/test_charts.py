"""T8-4 — 글 그림 그리기 (SPEC F11). 파일이 생기는지, PNG 1600×900 인지, 값이 빠져도 그려지는지만 본다."""

import struct
import warnings
from pathlib import Path

from radar.core.charts_data import Bar, MapPoint, Series, Share
from radar.publish import charts

SIG = ("s1", "s2", "s3", "s4", "s5")
WEEKS = [
    f"2026-{m:02d}-{d:02d}"
    for m, d in (
        (8, 16),
        (8, 23),
        (8, 30),
        (9, 6),
        (9, 13),
        (9, 20),
        (9, 27),
        (10, 4),
        (10, 11),
        (10, 18),
        (10, 25),
        (11, 1),
    )
]


def _size(p: Path) -> tuple[int, int]:
    head = p.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n"
    w, h = struct.unpack(">II", head[16:24])
    return int(w), int(h)


def _quiet() -> None:
    warnings.filterwarnings("ignore", message="Glyph .* missing")  # CI 에 한글 글꼴이 없을 때


def test_charts_render_all_four_and_card(tmp_path):
    _quiet()
    series = [
        Series(
            i,
            f"o/repo-{i}",
            i,
            tuple((w, (i if k > 3 else None), k < 11) for k, w in enumerate(WEEKS)),
            i == 1,
        )
        for i in range(1, 11)
    ]
    bars = [
        Bar(
            i,
            i,
            f"o/repo-{i}",
            90.0 - i,
            {"s1": 20.0, "s2": 0.0, "s3": 40.0 - i, "s4": 0.0, "s5": 30.0},
            ("s2", "s4"),
        )
        for i in range(1, 11)
    ]
    points = [MapPoint(i, f"o/r{i}", (i * 7) % 100, (i * 13) % 100, None) for i in range(200)]
    points += [MapPoint(900, "o/top", 80.0, 75.0, "1"), MapPoint(901, "o/quiet", 15.0, 92.0, "A")]
    shares = [Share(w, k < 11, {s: 20.0 for s in SIG}) for k, w in enumerate(WEEKS)]
    mix = [(w, {"에이전트": 6, "MCP": 3, "기타": 1}) for w in WEEKS]
    out = [
        charts.draw_rank_trend(series, tmp_path / "c1.png", week="2026-11-01"),
        charts.draw_contribution(
            bars,
            tmp_path / "c2.png",
            week="2026-11-01",
            weights={"s1": 15, "s2": 15, "s3": 25, "s4": 30, "s5": 15},
        ),
        charts.draw_signal_map(points, tmp_path / "c3.png", week="2026-11-01"),
        charts.draw_trend_analysis(
            shares, ["에이전트", "MCP", "기타"], mix, tmp_path / "c4.png", week="2026-11-01"
        ),
        charts.draw_repo_card(
            full_name="o/quiet",
            category="MCP 서버·도구",
            angle="A",
            pct={"s1": 20.0, "s2": None, "s3": 90.0, "s4": 95.0, "s5": 10.0},
            ranks=[(w, None if k < 3 else 40 - k) for k, w in enumerate(WEEKS)],
            lines=["무엇인지 한 문장입니다. " * 4, "왜 올랐나", "무엇을 볼까"],
            path=tmp_path / "card.png",
            week="2026-11-01",
        ),
    ]
    for p in out:
        assert p.exists() and _size(p) == (1600, 900)


def test_charts_font_pick_is_known_or_none():
    assert charts.pick_font() in (*charts.FONT_CANDIDATES, None)
