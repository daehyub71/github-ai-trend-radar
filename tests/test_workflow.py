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


def _step(text: str, name: str) -> str:
    start = text.index(f"- name: {name}")
    nxt = text.find("\n      - name:", start + 1)
    return text[start:nxt if nxt > 0 else len(text)]


def test_weekly_waits_in_short_steps_and_skips_a_week_already_done():
    # D26 — star-trend 가 끝나면 신호로 시작한다. 예약 실행은 대비용 — 5분마다 보고,
    # 이미 끝낸 주(종료 코드 5)면 뒤 단계(유료 포함)를 모두 건너뛴다.
    # 순서를 기다린 실행도 앞 실행의 커밋을 보도록 최신 main 을 받는다
    text = (WF / "weekly.yml").read_text(encoding="utf-8")
    own = _step(text, "레이더 저장소")
    assert "ref: main" in own
    wait = _step(text, "입력 갱신 대기")
    assert "sleep 300" in wait and "sleep 1800" not in wait
    assert '"5"' in wait and "GO=true" in wait and "GITHUB_ENV" in wait
    after = text[text.index("- name: 입력 갱신 대기"):].split("\n      - name:")[1:]
    assert after
    for step in after:
        cond = re.search(r"^\s+if: (.+)$", step, re.M)
        assert cond, step.splitlines()[0]
        assert "env.GO == 'true'" in cond.group(1) and "env.RUN" not in cond.group(1), step.splitlines()[0]
