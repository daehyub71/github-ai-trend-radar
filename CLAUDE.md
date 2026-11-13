# CLAUDE.md — github-ai-trend-radar

> 워크스페이스 공통 규칙(SDD/TDD, 언어, Git, 보안 점검)은 `../CLAUDE.md` 에 있다.
> 이 파일은 그 위에 이 프로젝트에만 해당하는 것을 더한다.

## Project Overview

깃허브 AI 저장소의 주간 트렌드를 스타 하나가 아니라 **스타·포크·기여(PR·이슈)·패키지 사용·커뮤니티 언급** 다섯 신호로 읽는다.
신호별 순위와 **종합 트렌드 지수**(백분위 가중 평균, 결측은 재분배)를 만들고, 웹 사이트와 블로그 초안(TOP 10 글 + 관점 글)·Notion 으로 낸다.
AI 판정과 스타는 `github-ai-star-trend` 공개 데이터를 **입력으로 읽고** 다시 수집하지 않는다.

읽는 순서: `docs/SPEC.md` → `docs/PLAN.md` → `docs/TASKS.md`(진도율 대시보드). 실측 숫자는 `docs/MEASURE.md` 에서만 가져온다.

## 이 프로젝트에서 지키는 규칙

### 숫자는 코드가, 글은 LLM 이
신호 값·백분위·지수·순위·유형 선정은 코드가 계산한다. LLM 은 설명만 쓰고, 없는 숫자·출처 없는 링크·단정 표현은 코드 게이트가 막는다.

### 공개 저장소다 (D7)
이 저장소는 **공개**다 — 커밋하는 모든 것이 바로 공개된다. LLM 해설·블로그 초안·Notion 대응표는 비공개 저장소
`daehyub71/github-ai-trend-radar-private`(로컬 `.private/`, gitignore)에만 둔다. 크기 가드가 `data/blog|notion|drafts|commentary|angles/` 를 막는다.

### 입력 계약
star-trend 데이터는 `RADAR_STARTREND_DIR`(없으면 `config/settings.toml` 의 상대 경로 — 맥 클론 `../github-ai-star-trend`)에서 읽는다.
`python -m radar contract` 로 네트워크 없이 점검한다. 계약이 깨지면 그 주 실행을 멈춘다(SPEC K1).

### 키 (D8 — star-trend 키 재사용)
- `GITHUB_TOKEN`(읽기 전용)·`NOTION_TOKEN`·`STARTREND_ANTHROPIC_API_KEY` 는 맥 키체인에 있다(`security find-generic-password -a "$USER" -s <이름> -w`).
  **필요한 명령에만 그 자리에서 넘긴다.** `GITHUB_TOKEN` 을 셸 전역에 export 하지 않는다(gh 쓰기가 깨진다).
- `ANTHROPIC_API_KEY` 라는 이름은 쓰지 않는다. 키 값을 출력·기록·커밋하지 않는다(이름과 길이만 확인).
- 로컬 실제 호출에는 `SSL_CERT_FILE=/etc/ssl/cert.pem` 이 필요하다.

### 규칙은 코드가 지킨다
- 기본 테스트 중 네트워크 접속은 `tests/conftest.py` 가 막는다. 실제 호출은 `@pytest.mark.live`.
- 층 규칙(`tests/test_architecture.py`): core 는 다른 층을 모르고, inputs 는 core 만, 수집기끼리 서로 import 하지 않고,
  네트워크 모듈은 `radar/clients/transport.py` 에서만, LLM SDK 는 `radar/clients/claude.py` 에서만.
- 커밋 전 훅(`scripts/hooks/pre-commit`): ruff·mypy·pytest·크기 가드. 클론마다 `git config core.hooksPath scripts/hooks`. 훅을 건너뛰지 않는다.
- 검사기를 바꾸면 통제군 테스트도 같이 고친다.

### 의존성
런타임 의존성 0(표준 라이브러리 urllib, PLAN P4). 개발 도구는 `requirements-dev.txt`, CI 는 해시 고정 `requirements-lock.txt`
(리눅스·3.12 용 — 맥에서는 바이너리 휠 해시가 달라 설치되지 않는 것이 정상). 새 패키지는 사용자 확인 뒤.

## 검증 명령

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy radar tests scripts
.venv/bin/python -m pytest              # 기본 게이트 (외부 의존 0)
.venv/bin/python -m pytest -m live      # 실제 외부 호출
.venv/bin/python -m radar contract      # star-trend 입력 계약 점검
```

## Working Rules

- 마일스톤 종료 시 사용자 확인 후 다음으로. 화면은 `docs/DESIGN.md` 시안(Claude Design) 합의 뒤에만.
- 과금·장시간 작업(소급·LLM)은 `--dry-run` 결과를 제시한 뒤 실행한다.
