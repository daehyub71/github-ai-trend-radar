"""테스트 하네스 — 규칙을 사람 대신 코드가 지키게 한다 (PLAN §2).

- 네트워크 차단: conftest 의 autouse 픽스처가 쓴다 (`live` 표시 테스트만 예외).
- 층 규칙 검사기: test_architecture 가 쓴다. 검사기가 위반을 잡는지 통제군 테스트로 먼저 확인한다.
"""

import ast
from collections.abc import Mapping
from pathlib import Path

PACKAGE = "radar"

# 층마다 import 해도 되는 radar 층 (위가 아래를 쓴다, 순환 없음)
ALLOWED: dict[str, set[str]] = {
    "core": {"core"},
    "clients": {"core", "clients"},
    "inputs": {"core", "inputs"},
    "collectors": {"core", "clients", "collectors"},  # 수집기끼리는 아래에서 따로 막는다
    "evidence": {"core", "clients", "evidence"},  # M7 해설 근거 — 수집기처럼 서로 import 하지 않는다
    "publish": {"core", "clients", "publish"},  # M5 글·Notion — 수집기·입력을 모른다(사실 묶음만 받는다)
    "app": {"core", "clients", "inputs", "collectors", "evidence", "publish", "app"},
    "cli": {"core", "clients", "inputs", "collectors", "evidence", "publish", "app", "cli"},
    "package": set(),
}
APP_MODULES = {"config", "store", "pipeline", "backfill", "blog", "site", "cards", "images"}
NETWORK_MODULES = {"socket", "ssl", "http.client", "urllib.request", "ftplib", "smtplib"}
NETWORK_ALLOWED_FILES = {"radar/clients/transport.py"}
LLM_SDK_MODULES = {"anthropic"}
LLM_SDK_ALLOWED_FILES = {"radar/clients/claude.py"}
CHART_MODULES = {"matplotlib"}
CHART_ALLOWED_FILES = {"radar/publish/charts.py"}  # M8 — 그림 도구는 한 파일에서만 (SPEC D20)


class NetworkBlocked(RuntimeError):
    """기본 테스트 게이트에서 네트워크에 접속하려 했다 (SPEC N2)."""


def layer_of(relpath: str) -> str:
    parts = relpath.split("/")
    if parts == ["radar", "__init__.py"]:
        return "package"
    if parts in (["radar", "__main__.py"], ["radar", "cli.py"]):
        return "cli"
    if len(parts) == 2 and Path(parts[1]).stem in APP_MODULES:
        return "app"
    if len(parts) > 2 and parts[1] in ("core", "clients", "inputs", "collectors", "evidence", "publish"):
        return parts[1]
    raise ValueError(f"층을 알 수 없는 모듈: {relpath}")


def _target_layer(mod: str) -> str:
    head = mod.split(".")[1]
    if head in ("__main__", "cli"):
        return "cli"
    if head in APP_MODULES:
        return "app"
    return head


def _imports(tree: ast.AST) -> list[tuple[int, str, list[str]]]:
    out: list[tuple[int, str, list[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append((node.lineno, a.name, []))
        elif isinstance(node, ast.ImportFrom):
            mod = "." * node.level + (node.module or "")
            out.append((node.lineno, mod, [a.name for a in node.names]))
    return out


def check_sources(sources: Mapping[str, str]) -> list[str]:
    """{상대경로: 소스} → 위반 목록. 비어 있으면 통과."""
    violations: list[str] = []
    for relpath, src in sorted(sources.items()):
        layer = layer_of(relpath)
        own = Path(relpath).stem if layer in ("collectors", "evidence") else None
        for lineno, mod, names in _imports(ast.parse(src, filename=relpath)):
            where = f"{relpath}:{lineno}"
            if mod.startswith("."):
                violations.append(f"{where} 상대 import 금지 — 절대 경로로 쓴다 ({mod})")
                continue
            full = {mod} | {f"{mod}.{n}" for n in names}
            if full & NETWORK_MODULES and relpath not in NETWORK_ALLOWED_FILES:
                violations.append(f"{where} 네트워크 모듈은 clients/transport.py 에서만 ({mod})")
            if mod.split(".")[0] in LLM_SDK_MODULES and relpath not in LLM_SDK_ALLOWED_FILES:
                violations.append(f"{where} LLM SDK 는 clients/claude.py 에서만 ({mod})")
            if mod.split(".")[0] in CHART_MODULES and relpath not in CHART_ALLOWED_FILES:
                violations.append(f"{where} matplotlib 은 publish/charts.py 에서만 ({mod})")
            if mod != PACKAGE and not mod.startswith(PACKAGE + "."):
                continue
            # `from radar import config` 는 이름마다 층을 본다
            targets = [_target_layer(f"{mod}.{n}") for n in names] if mod == PACKAGE else [_target_layer(mod)]
            for target in dict.fromkeys(targets):
                if target not in ALLOWED[layer]:
                    violations.append(f"{where} {layer} 층은 {target} 층을 import 할 수 없다 ({mod})")
            if layer in ("collectors", "evidence") and layer in targets:
                others = names if mod == f"{PACKAGE}.{layer}" else [mod.split(".")[2]]
                for other in others:
                    if other not in (own, "base"):
                        violations.append(f"{where} 수집기끼리 import 금지 ({other})")
    return violations


def project_sources(root: Path) -> dict[str, str]:
    pkg = root / PACKAGE
    return {
        f.relative_to(root).as_posix(): f.read_text(encoding="utf-8")
        for f in sorted(pkg.rglob("*.py"))
        if "__pycache__" not in f.parts
    }
