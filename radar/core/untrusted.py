"""외부 글을 프롬프트에 넣는 규칙 (SPEC K10) — README·HN 댓글·웹 글은 데이터다.

star-trend 에서 옮겼다(PLAN P5).

외부 글은 우리 구분 태그 안에 넣는다. 그 글이 우리 태그를 닫거나 새로 열면 데이터 칸을 빠져나가 지시처럼
보일 수 있다 — 글 안의 예약 태그는 '<' 를 '&lt;' 로 바꿔 무력화한다. 내용은 지우지 않는다.
"""

import re

RESERVED = ("facts", "evidence", "repository", "document", "doc", "system", "instructions", "untrusted")
_TAG = re.compile(rf"(?i)<(\s*/?\s*(?:{'|'.join(RESERVED)})(?![\w-]))")


def neutralize(text: str) -> str:
    return _TAG.sub(r"&lt;\1", text)


def block(tag: str, text: str) -> str:
    if tag not in RESERVED:
        raise ValueError(f"예약 태그가 아니다: {tag}")
    return f"<{tag}>\n{neutralize(text)}\n</{tag}>"
