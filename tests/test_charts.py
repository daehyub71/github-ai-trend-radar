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


def test_charts_font_pick_rescans_fonts_installed_after_the_cache(monkeypatch):
    # 11-16 실행: 해설 단계가 matplotlib 을 먼저 불러 글꼴 목록이 캐시된 뒤 CI 가 fonts-noto-cjk 를 설치했다 →
    # 목록에 없어 그림 단계가 멈췄다. 후보가 없으면 시스템 글꼴을 다시 읽는다.
    # Ubuntu 의 NotoSansCJK-*.ttc 는 matplotlib 이 첫 글꼴만 읽는다
    # — 이름이 "Noto Sans CJK JP"(한글 글자는 같다)
    from types import SimpleNamespace

    from matplotlib import font_manager

    fm = SimpleNamespace(ttflist=[SimpleNamespace(name="DejaVu Sans", fname="/f/DejaVuSans.ttf")])

    def addfont(path):
        fm.ttflist.append(SimpleNamespace(name="Noto Sans CJK JP", fname=path))

    fm.addfont = addfont
    monkeypatch.setattr(font_manager, "fontManager", fm)
    ttc = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    monkeypatch.setattr(font_manager, "findSystemFonts", lambda: ["/f/DejaVuSans.ttf", ttc])
    assert charts.pick_font() == "Noto Sans CJK JP"
    assert [f.fname for f in fm.ttflist].count("/f/DejaVuSans.ttf") == 1  # 아는 파일은 다시 넣지 않는다


def test_charts_font_pick_prefers_the_korean_face(monkeypatch):
    from types import SimpleNamespace

    from matplotlib import font_manager

    faces = ("Noto Sans CJK JP", "Noto Sans CJK KR")
    fm = SimpleNamespace(ttflist=[SimpleNamespace(name=n, fname=n) for n in faces])
    monkeypatch.setattr(font_manager, "fontManager", fm)
    assert charts.pick_font() == "Noto Sans CJK KR"


def test_charts_inspect_image_accepts_real_pictures_only():
    from io import BytesIO

    from PIL import Image

    def png(w: int, h: int) -> bytes:
        buf = BytesIO()
        Image.new("RGB", (w, h), "white").save(buf, "PNG")
        return buf.getvalue()

    assert charts.inspect_image(png(640, 320)) == ("png", 640, 320)
    assert charts.inspect_image(png(64, 64)) is None  # 아이콘 크기
    assert charts.inspect_image(b"<html>not an image</html>") is None


def test_charts_diagram_and_card_with_picture(tmp_path):
    _quiet()
    from PIL import Image

    nodes = [
        {"id": "a", "label": "React 컴포넌트"},
        {"id": "b", "label": "렌더러"},
        {"id": "c", "label": "MP4"},
        {"id": "d", "label": "클라우드 렌더"},
    ]
    edges = [
        {"from": "a", "to": "b", "label": "프레임마다"},
        {"from": "b", "to": "c", "label": "인코딩"},
        {"from": "a", "to": "d", "label": ""},
    ]
    d = charts.draw_diagram(nodes, edges, tmp_path / "d.png", full_name="o/tool", week="2026-11-01")
    assert _size(d) == (1600, 900)
    assert charts._layers(nodes, edges) == {"a": 0, "b": 1, "c": 2, "d": 1}
    pic = tmp_path / "p.png"
    Image.new("RGB", (800, 400), "#DDEEFF").save(pic)
    card = charts.draw_repo_card(
        full_name="o/tool",
        category="MCP",
        angle="B",
        pct={"s1": 90.0, "s2": None, "s3": 10.0, "s4": None, "s5": 95.0},
        ranks=[(w, 50) for w in WEEKS],
        lines=["무엇", "왜", "볼 것"],
        path=tmp_path / "c.png",
        week="2026-11-01",
        picture=pic,
        caption="그림: o/tool · 공개용(소셜 미리보기)",
    )
    assert _size(card) == (1600, 900)


def test_charts_flow_layout_leaves_room_for_arrows():
    nodes = [{"id": str(i), "label": f"상자 {i}"} for i in range(1, 6)]
    edges = [{"from": str(i), "to": str(i + 1), "label": "다음"} for i in range(1, 5)]
    pos, bw, bh = charts._flow_layout(nodes, edges)
    xs = sorted(x for x, _ in pos.values())
    gaps = [b - a - bw for a, b in zip(xs, xs[1:], strict=False)]
    assert min(gaps) >= 0.6 * bw  # 화살표와 라벨이 들어갈 틈 (11-01 시안: 틈이 거의 없어 화살표가 안 보였다)
    assert all(0 <= x - bw / 2 and x + bw / 2 <= 100 for x, _ in pos.values())
    # 한 단에 상자가 여럿이면 위아래로 겹치지 않는다
    branch = [{"from": "1", "to": "2", "label": ""}, {"from": "1", "to": "3", "label": ""}]
    pos2, _, bh2 = charts._flow_layout(nodes[:3], branch)
    assert abs(pos2["2"][1] - pos2["3"][1]) > bh2


def test_charts_card_draws_diagram_in_panel(tmp_path):
    _quiet()
    card = charts.draw_repo_card(
        full_name="o/tool",
        category="MCP",
        angle="B",
        pct={s: 50.0 for s in SIG},
        ranks=[(w, 50) for w in WEEKS],
        lines=["무엇", "왜", "볼 것"],
        path=tmp_path / "c.png",
        week="2026-11-01",
        diagram={
            "nodes": [
                {"id": "1", "label": "입력"},
                {"id": "2", "label": "처리 엔진"},
                {"id": "3", "label": "출력"},
            ],
            "edges": [{"from": "1", "to": "2", "label": "읽기"}, {"from": "2", "to": "3", "label": ""}],
        },
        caption="그림: README 를 바탕으로 AI 가 정리 · 자동 생성",
    )
    assert _size(card) == (1600, 900)


def test_charts_wrap_label_breaks_at_spaces_and_dots():
    # 폭은 한글 한 글자 = 1, 로마자 = 0.6
    assert charts._wrap_label("GitHub·Feishu 요청", 5) == ["GitHub·", "Feishu", "요청"]
    assert charts._wrap_label("독립 에이전트 세션", 8) == ["독립 에이전트", "세션"]
    assert charts._wrap_label("짧음", 8) == ["짧음"]
    # 한 줄보다 긴 낱말만 자른다
    assert charts._wrap_label("Supercalifragilistic", 5) == ["Supercal", "ifragili", "stic"]


def test_charts_fit_shrinks_font_instead_of_chopping_words():
    font, lines = charts._fit("먼저 동작시키기", 80, 12)
    assert font < 12 and lines == ["먼저", "동작시키기"]
    assert charts._fit("입력", 200, 12) == (12, ["입력"])


def test_charts_render_stops_without_korean_font(monkeypatch, tmp_path):
    # P7 — 한글 글꼴이 없으면 네모 글자 그림을 만들지 않고 그림 단계만 실패한다(초안은 그림 자리 없이)
    from datetime import date
    from typing import cast

    import pytest

    from radar import images
    from radar.config import Config

    monkeypatch.setattr(charts, "pick_font", lambda: None)
    with pytest.raises(ValueError, match="한글 글꼴"):
        images.render_images(cast(Config, None), date(2026, 11, 1), data=tmp_path, private=tmp_path)
