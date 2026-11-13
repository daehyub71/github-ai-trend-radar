"""게이트 (SPEC F8·F9, TASKS T5-4) — LLM 글이 사실 묶음 밖의 숫자·링크·단정 표현을 쓰지 못하게 코드가 막는다.

- 숫자: 글 안의 숫자(영문·숫자에 붙은 것 — Qwen3·GPT-4o 같은 이름 — 은 빼고)는 사실 묶음에 있는 값이어야 한다.
  정수·소수 한 자리·두 자리 반올림과 날짜의 월·일을 허용한다.
- 링크: 글에는 링크를 넣지 않는다(네이버 붙여 넣기 — star-trend 결정 64와 같음). 링크는 코드가 표에 넣는다.
- 표현: 투자 권유·단정·B 유형 판단("거품"·"가짜" 등)을 막는다.
"""

import re
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

NUMBER = re.compile(r"(?<![A-Za-z0-9_.\-])(\d[\d,]*(?:\.\d+)?)(?![A-Za-z0-9_])")
LINK = re.compile(r"(?i)\bhttps?://|\bwww\.|\b[a-z0-9-]+\.(?:com|io|dev|ai|org|net|kr)/")
BANNED = ("투자", "매수", "매도", "수익률", "거품", "가짜", "사기", "조작", "반드시", "무조건", "확실히",
          "틀림없", "보장", "최고의", "유일한")


def _num_text(v: float) -> set[str]:
    out = {f"{v:g}"}
    for nd in (0, 1, 2):
        r = round(v, nd)
        out.add(f"{r:.{nd}f}")
        if nd == 0:
            out.add(str(int(r)))
    return out


def allowed_numbers(facts: Mapping[str, Any]) -> set[str]:
    """사실 묶음 안의 모든 숫자(문자열 안 숫자·날짜의 월·일 포함)."""
    out: set[str] = set()

    def walk(x: Any) -> None:
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            out.update(_num_text(float(x)))
        elif isinstance(x, str):
            try:
                d = date.fromisoformat(x)
                out.update({str(d.year), str(d.month), str(d.day)})
            except ValueError:
                pass
            out.update(m.replace(",", "") for m in NUMBER.findall(x))
        elif isinstance(x, Mapping):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)

    walk(facts)
    return out


def check(text: str, allowed: Iterable[str]) -> list[str]:
    """문제 목록 (비면 통과)."""
    ok = set(allowed)
    problems: list[str] = []
    for m in NUMBER.findall(text):
        n = m.replace(",", "")
        if n not in ok:
            problems.append(f"숫자 {m}")
    if LINK.search(text):
        problems.append("링크")
    problems += [f"표현 '{w}'" for w in BANNED if w in text]
    return problems
