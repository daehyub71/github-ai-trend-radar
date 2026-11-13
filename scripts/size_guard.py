"""크기 가드 — 커밋 전 훅과 CI 가 부른다 (PLAN §4, SPEC D7·N4).

막는 것:
- 1MB 를 넘는 파일, 한 커밋에 data/ 가 5MB 넘게 늘어나는 것
- ASCII 가 아닌 파일명 (워크스페이스 규칙)
- data/ 아래 LLM 글(블로그·Notion·초안·해설) — 비공개 저장소에만 둔다(D7)
- 시크릿 — 토큰 모양과 환경변수의 실제 키 값. 보고에 값은 쓰지 않는다

    .venv/bin/python scripts/size_guard.py --staged
"""

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from radar.core.secrets import scan_text, secret_values  # noqa: E402

MB = 1_048_576
MAX_FILE = MB
MAX_DATA_GROWTH = 5 * MB
_LLM_TEXT = re.compile(r"^data/(?:blog|notion|drafts|commentary|angles)/")
BINARY = (".webp", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".gz", ".zip", ".pdf", ".woff", ".woff2")


@dataclass(frozen=True)
class Entry:
    path: str  # 저장소 기준 POSIX 경로
    old_size: int  # HEAD 의 크기. 새 파일이면 0
    new_size: int  # 스테이징된 크기


def check(entries: list[Entry], max_file: int = MAX_FILE,
          max_data_growth: int = MAX_DATA_GROWTH) -> list[str]:
    violations = []
    for e in entries:
        if not e.path.isascii():
            violations.append(f"{e.path}: 파일명은 ASCII 만 쓴다")
        if _LLM_TEXT.match(e.path):
            violations.append(f"{e.path}: LLM 글은 비공개 저장소에만 둔다 (D7)")
        if e.new_size > max_file:
            violations.append(f"{e.path}: {e.new_size / MB:.2f}MB — "
                              f"{max_file / MB:g}MB 를 넘는 파일은 커밋하지 않는다")
    growth = sum(e.new_size - e.old_size for e in entries if e.path.startswith("data/"))
    if growth > max_data_growth:
        violations.append(f"data/ 가 이번 커밋에서 {growth / MB:.2f}MB 늘어난다 — "
                          f"기준 {max_data_growth / MB:.0f}MB 초과")
    return violations


def _git(repo: Path, *args: str, stdin: str | None = None) -> str:
    r = subprocess.run(["git", *args], cwd=repo, input=stdin, capture_output=True, text=True,
                       encoding="utf-8", check=True)
    return r.stdout


def _sizes(repo: Path, objects: list[str]) -> list[int]:
    out = _git(repo, "cat-file", "--batch-check=%(objectsize)", stdin="\n".join(objects) + "\n")
    return [0 if line.endswith(" missing") else int(line) for line in out.splitlines()]


def staged_entries(repo: Path) -> list[Entry]:
    out = _git(repo, "diff", "--cached", "--name-only", "--no-renames", "--diff-filter=AM", "-z")
    paths = [p for p in out.split("\0") if p]
    if not paths:
        return []
    has_head = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=repo,
                              capture_output=True).returncode == 0
    new = _sizes(repo, [f":{p}" for p in paths])
    old = _sizes(repo, [f"HEAD:{p}" for p in paths]) if has_head else [0] * len(paths)
    return [Entry(p, o, n) for p, o, n in zip(paths, old, new, strict=True)]


def staged_secret_hits(repo: Path, paths: list[str], secrets: list[str]) -> list[str]:
    """스테이징된 내용에서 시크릿을 찾는다 — "파일:줄 (종류)"만."""
    hits: list[str] = []
    for p in paths:
        if p.lower().endswith(BINARY):
            continue
        blob = subprocess.run(["git", "show", f":{p}"], cwd=repo, capture_output=True, check=True).stdout
        for no, line in enumerate(blob.decode("utf-8", errors="ignore").splitlines(), 1):
            for kind in scan_text(line, secrets=secrets):
                hits.append(f"{p}:{no} ({kind})")
    return hits


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="size_guard")
    ap.add_argument("--staged", action="store_true", help="스테이징된 변경을 검사한다")
    ap.add_argument("--repo", default=".")
    args = ap.parse_args(argv)
    if not args.staged:
        ap.error("지금은 --staged 만 지원한다")
    repo = Path(args.repo)
    entries = staged_entries(repo)
    violations = check(entries)
    for hit in staged_secret_hits(repo, [e.path for e in entries], secret_values(os.environ)):
        violations.append(f"{hit}: 시크릿으로 보인다 — 커밋하지 않는다")
    for v in violations:
        print(f"[size_guard] {v}", file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
