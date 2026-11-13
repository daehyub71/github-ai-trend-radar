"""워크플로 보안 규칙 (SPEC N4·N5, T3-4) — 권한 최소·SHA 고정·시크릿은 env 로만·토큰을 .git 에 안 남김."""

import re
from pathlib import Path

WF = Path(__file__).resolve().parents[1] / ".github" / "workflows"
ALLOWED_PERMS = {"ci.yml": {"contents: read"}, "weekly.yml": {"contents: write"}}


def problems(name: str, text: str) -> list[str]:
    out: list[str] = []
    lines = text.splitlines()
    for ln in lines:
        m = re.match(r"\s*(?:-\s*)?uses:\s*(\S+)", ln)
        if m and not re.search(r"@[0-9a-f]{40}$", m.group(1)):
            out.append(f"SHA 고정 아님: {m.group(1)}")
    perm = re.search(r"^permissions:\n((?:  .+\n)+)", text, re.M)
    got = {p.strip() for p in perm.group(1).splitlines()} if perm else set()
    if got != ALLOWED_PERMS.get(name, {"contents: read"}):
        out.append(f"권한: {sorted(got)}")
    for ln in lines:
        if re.search(r"\$\{\{\s*(secrets|inputs|github\.event)\.", ln) \
                and not re.match(r"\s+(?:[A-Z_]+|token|repository):\s*\$\{\{", ln):
            out.append(f"env 밖에서 시크릿·입력 사용: {ln.strip()}")
    checkouts = len(re.findall(r"uses:\s*actions/checkout@", text))
    if checkouts != len(re.findall(r"persist-credentials:\s*false", text)):
        out.append("checkout 에 persist-credentials: false 가 없다")
    return out


def test_workflow_files_follow_rules():
    files = sorted(WF.glob("*.yml"))
    assert {f.name for f in files} == set(ALLOWED_PERMS)
    for f in files:
        assert problems(f.name, f.read_text(encoding="utf-8")) == [], f.name


def test_workflow_checker_catches_violations():
    bad = """name: x
permissions:
  contents: write
  actions: write
jobs:
  a:
    steps:
      - uses: actions/checkout@v4
      - run: echo ${{ secrets.RADAR_GH_TOKEN }}
"""
    found = problems("weekly.yml", bad)
    assert any("SHA" in p for p in found)
    assert any("권한" in p for p in found)
    assert any("env 밖" in p for p in found)
    assert any("persist-credentials" in p for p in found)
