"""T8-10 — 저장소 설명 그림 후보 (SPEC F11 · D21).

순수 함수 — README 그림 · og:image · 라이선스 · 우선순위.
"""

from radar.core.repo_images import (
    Candidate,
    explanatory,
    og_image,
    permissive,
    rank_candidates,
    readme_images,
)

README = """
# Tool
[![CI](https://github.com/org/tool/actions/workflows/ci.yml/badge.svg)](x)
![Downloads](https://img.shields.io/npm/dm/tool.svg)
![architecture](docs/arch.png "구조")
<p align="center"><img src="./assets/demo.gif" width="600"></p>
![blob](https://github.com/org/tool/blob/main/docs/flow.jpg?raw=true)
![logo](https://example.com/icon.svg)
<img alt="shot" src='https://user-images.githubusercontent.com/1/abc.png'>
![arch again](docs/arch.png)
"""


def test_readme_images_skip_badges_svg_and_resolve_paths():
    assert readme_images(README, "org/tool") == [
        "https://raw.githubusercontent.com/org/tool/HEAD/docs/arch.png",
        "https://raw.githubusercontent.com/org/tool/HEAD/assets/demo.gif",
        "https://raw.githubusercontent.com/org/tool/main/docs/flow.jpg",
        "https://user-images.githubusercontent.com/1/abc.png",
    ]
    assert readme_images("", "org/tool") == []
    assert readme_images("![x](javascript:alert(1))", "org/tool") == []


def test_og_image_reads_meta_in_any_order_and_resolves():
    html = (
        '<head><meta content="/img/hero.png" property="og:image">'
        '<meta name="twitter:image" content="t.png"></head>'
    )
    assert og_image(html, "https://tool.dev/docs/") == "https://tool.dev/img/hero.png"
    assert (
        og_image("<meta name='twitter:image' content='https://cdn.x/t.png'>", "https://tool.dev")
        == "https://cdn.x/t.png"
    )
    assert og_image("<html></html>", "https://tool.dev") is None


def test_permissive_licenses():
    assert permissive("MIT") and permissive("Apache-2.0") and permissive("BSD-3-Clause")
    assert not permissive("AGPL-3.0") and not permissive("NOASSERTION") and not permissive(None)


def test_rank_candidates_priority_and_rights():
    cands = rank_candidates(
        readme=["https://raw.githubusercontent.com/o/r/HEAD/a.png"],
        license_id="MIT",
        social="https://repository-images.githubusercontent.com/1/x",
        homepage_og="https://tool.dev/og.png",
        homepage="https://tool.dev",
        web=[{"url": "https://blog.x/i.png", "description": "Tool diagram"}],
        full_name="o/r",
    )
    assert [c.kind for c in cands] == ["readme", "social", "homepage", "web"]
    assert cands[0] == Candidate(
        "https://raw.githubusercontent.com/o/r/HEAD/a.png", "readme", "https://github.com/o/r", "라이선스 MIT"
    )
    assert cands[1].rights == "공개용(소셜 미리보기)" and cands[2].source == "https://tool.dev"
    assert cands[3].rights == "확인 필요(웹 검색)" and cands[3].source == "blog.x"
    # 허용형이 아니면 README 그림은 후보가 아니다
    no = rank_candidates(
        readme=["https://raw.githubusercontent.com/o/r/HEAD/a.png"],
        license_id="AGPL-3.0",
        social=None,
        homepage_og=None,
        homepage=None,
        web=[],
        full_name="o/r",
    )
    assert no == []


def test_explanatory_skips_icons_and_thin_banners():
    assert explanatory(2037, 1075) and explanatory(1200, 630) and explanatory(1024, 1024)
    assert not explanatory(256, 256)  # 앱 아이콘
    assert not explanatory(1145, 196)  # 가는 배너
    assert not explanatory(500, 500)  # 작은 정사각형
