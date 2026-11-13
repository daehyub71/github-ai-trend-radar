# PLAN.md — github-ai-trend-radar

> **상태: v0.4 확정** (2026-11-13). 기준 문서는 `docs/SPEC.md` v0.4.
> PLAN 결정 P1~P4 모두 확정. 숫자 근거는 `docs/MEASURE.md` §1(M0 실측).

---

## 1. 입력 계약 (star-trend 공개 데이터, 2026-11-13 실측)

| 파일 | 쓰는 값 | 실측 |
|---|---|---|
| `data/repos/<2자리>/<owner>__<name>/meta.json` | `full_name` · `created` · `classify.is_ai` · `classify.category` · `classify.secondary` · `classify.type` | 판정 1,992개, AI 1,425개 |
| `data/stars/<연>/<주>.csv` | `id` · `full_name` · `gain`(주간 스타 증가) · `stars_end` · `exact` · `d0~d6`(일별) | 11-01 주 12,880행, 그중 AI 1,111개. 스타 증가 200위 +656 |
| `data/site/categories.json` | 카테고리 이름(16개) | 화면·글의 분류 이름 |
| `data/weekly/<주>/rankings.json` | 참고만 (축별 상위 15) | 후보 선정에는 쓰지 않는다 |

- 주 이름은 **주 시작일(일요일)**이다. 11-09(월) 실행이 `2026-11-01` 주를 만든다.
- 입력은 star-trend 공개 저장소를 **얕은 클론(sparse checkout: `data/repos`·`data/stars`·`data/site`)** 해서 읽는다. raw URL로 1,992개 파일을 받지 않는다.
- AI 판정은 **읽는 시점의 판정**을 쓴다. 과거 주를 소급할 때도 지금의 AI 목록으로 거른다(과거에는 판정 전이던 저장소도 포함된다). 이 점을 사이트와 글에 적는다.
- 계약 테스트: 필드가 없거나 형식이 바뀌면 그 주 실행을 멈춘다(SPEC K1).

---

## 2. 아키텍처

```
radar/
  config.py            설정 읽기 (config/settings.toml · weights.toml)
  core/                순수 함수만 — 다른 층을 import 하지 않는다
    weeks.py             주 경계·기간 계산
    candidates.py        후보 선정 (F2)
    normalize.py         로그 → 백분위, S3 합성 (D5)
    index.py             가중 평균·결측 재분배·기여분 (§4-1, D1)
    angles.py            관점 글 유형 A~D 선정·근거 숫자 (F9, D9)
  inputs/startrend.py  입력 계약 읽기·검증
  clients/transport.py 네트워크는 여기서만 (재시도·한도·녹화 재생)
  collectors/          신호별 수집기 — 서로 import 하지 않는다
    forks.py  (S2)     activity.py (S3)   packages.py (S4)   mentions.py (S5)
  store.py             평문 파일 읽기·쓰기 (§3)
  pipeline.py          주간 실행 순서 (F1)
  backfill.py          12주 소급 (F5)
  publish/             (M5) llm.py · gate.py · drafts.py · notion.py · budget.py
  cli.py               python -m radar <weekly|backfill|contract|notion> [--dry-run]
web/                   (M4) Next.js 정적 사이트 — data/site 만 읽는다
```

- 층 규칙은 star-trend의 `test_architecture.py` 방식으로 테스트가 강제한다. core는 다른 층을 모르고, 수집기끼리 서로 모르고, 네트워크는 `transport.py`에서만 쓴다.
- 기본 테스트 중 네트워크 접속은 `conftest.py`가 막는다. 실제 호출은 `@pytest.mark.live`.

---

## 3. 신호 수집 설계

| 신호 | 주간 수집 | 호출 (후보 200 기준) | 소급 12주 |
|---|---|---|---|
| S2 포크 | 저장소 메타 `forks_count`를 매주 저장하고 차이를 낸다 | REST 200회 | **소급하지 않는다**(D10). 소급 구간은 결측 |
| S3 기여 | Search API 2질의: `is:pr is:merged merged:<기간>`(목록에서 고유 작성자·봇 제외) · `is:issue is:closed closed:<기간>` | 검색 400~600회 (약 15~20분) | **12주를 질의 한 번으로 받아 `merged_at`·`closed_at` 으로 주별로 나눈다.** 1,000건을 넘으면 주 단위로 쪼개 다시 질의 — 약 1,600~2,000회, 55~70분 |
| S4 사용 | 패키지 연결(D11: 이름 후보 조회 + 저장소의 `pyproject.toml`·`setup.py`·`package.json` 이름, 레지스트리 저장소 URL 일치 확인)을 먼저 찾고, PyPI는 pypistats 최근 일별, npm은 downloads range API | 연결 1회(캐시) + 패키지마다 1회 | pypistats는 약 180일, npm range는 18개월 — 12주 가능. **의존 수는 소급 불가**, 지금부터 매주 쌓는다 |
| S5 언급 | HN Algolia(저장소 URL·`owner/name` 정확 일치, 기간 필터) · GeekNews | 저장소마다 1~2회 | HN은 기간 검색으로 가능. GeekNews `/past?day=` 는 1년 전까지 읽힌다 — 12주 약 84일 × 1~2쪽, 간격 2초로 3~6분(D12) |

- PR 작성자 고유 수는 Search API가 바로 주지 않는다. 머지 PR 목록(주당 최대 100건씩)을 받아 `user.login`에서 `[bot]`을 빼고 센다. 100건을 넘는 저장소는 페이지를 더 읽는다(상한을 둔다).
- 모든 응답은 녹화 파일로 테스트하고, 형식이 바뀌면 `partial`로 기록한다(F3).
- GitHub 토큰은 star-trend의 읽기 전용 토큰을 재사용한다(D8). 한 실행의 REST·Search 호출 수를 실행 기록에 남긴다.

---

## 4. 저장 (P1 확정)

정본은 `data/` 평문 파일(SPEC §7)로 하고 git에 커밋한다. star-trend와 같은 방식이다.

| 경로 | 내용 | 공개 |
|---|---|---|
| `data/candidates/<주>.json` | 후보와 선정 이유 | 공개 저장소 |
| `data/signals/<주>.csv` | 저장소 × S1~S5 원값·상태·소급 여부 | 공개 |
| `data/meta/forks/<주>.csv` · `data/meta/dependents/<주>.csv` | 매주 쌓는 스냅샷 | 공개 |
| `data/index/<주>.json` | 백분위·가중치 버전·지수·순위·기여분 | 공개 |
| `data/site/` | 사이트용 파생 데이터 | 공개 |
| 비공개 저장소 `weeks/<주>/` | LLM 해설·블로그 초안·Notion 대응표 | **비공개**(D7) |

- 주간 파일은 한 번 쓰면 다시 쓰지 않는다. 다시 계산하면 가중치 버전을 올린다.
- 크기 가드(커밋 전 훅 + CI)가 공개 저장소에 초안·해설이 들어오는 것을 막는다.

---

## 5. 마일스톤

| M | 이름 | 범위 | 완료 기준 |
|---|---|---|---|
| **M0** | 기반·실측 | git 저장소(공개)·비공개 저장소 생성, 골격·층 테스트·CI(테스트만), 입력 계약 읽기, **API 실측**: 후보 20개로 S2~S5 호출 수·시간·패키지 연결률·GeekNews 소급 범위 | 테스트 통과, `docs/MEASURE.md`에 실측 기록, P3 확정 |
| **M1** | 수집기 | S2~S5 수집기, transport(재시도·한도), 녹화 응답 테스트, 상태 기록 | 후보 200 실제 1회 수집 성공, 상태 표 기록 |
| **M2** | 지수·소급 | normalize·index(결측 재분배·기여분), 관점 유형 선정(`angles.py`), 12주 소급 1회 실행, 신호 간 상관·결측률·유형별 해당 수 실측 | 12주 지수 생성, MEASURE에 상관표·유형별 해당 수, **관점 임계값 조정 확인**, **가중치 v1 유지/v2 제안을 사용자와 확인** |
| **M3** | 주간 자동 실행 | Actions 워크플로(월 09:00 UTC, 입력 대기·재시도), 실행 기록, **보안 점검** 뒤 cron 활성화 | 수동 실행 1회 + 첫 예약 실행 성공 |
| **M4** | 사이트 | **DESIGN 시안(Claude Design 캔버스) 합의 →** Next.js 정적 사이트, Vercel 배포, 보안 점검 | 시안 합의 기록, 웹 lint·test·build 통과, 배포 |
| **M5** | 블로그·Notion | Sonnet 5.5 해설($3 상한), 게이트(숫자·링크·금지 표현), 별도 연재 초안, **관점 글 초안(F9)**, 비공개 저장소 저장, Notion 레이더 DB(글 종류 속성) | 실제 1주 TOP 10 글·관점 글과 Notion 페이지 검토 확인 |
| **M6** | 운영 관찰 | 연속 3주 자동 실행 관찰, 문제 정리 | 3주 연속 정상 |

- M3까지 끝나면 사이트 없이도 매주 지수가 쌓인다. 사이트·글은 그 데이터 위에 올린다.
- 마일스톤마다 사용자 확인 뒤 다음으로 넘어간다.

---

## 6. 테스트 전략

- **core**: 관점 유형 경계값·유형 중복 우선순위(D→C→A→B)·5개 상한·이력 부족 처리, 백분위·결측 재분배·기여분 합 = 지수, 같은 입력 → 같은 결과, 동점 처리, 후보 선정 경계(200위 동점·지난주 TOP 10 보충). TDD로 먼저 쓴다.
- **inputs**: star-trend 실제 파일 일부를 픽스처로 둔 계약 테스트 + 필드 누락 통제군.
- **collectors**: 녹화 응답 재생. 429·5xx 재시도, 형식 변경 → `partial`, 봇 제외.
- **pipeline**: 한 신호 실패 시 나머지로 지수, 빠진 신호 표시.
- **publish(M5)**: 게이트가 없는 숫자·링크·금지 표현을 실제로 잡는지 통제군.
- **web(M4)**: 컴포넌트 핵심 동작(Vitest).
- 검증 명령: `ruff check .` · `mypy radar tests` · `pytest` · (웹) `npm run lint && npm test && npm run build`.

---

## 7. PLAN 결정 (2026-11-13 사용자 확정)

| ID | 항목 | 결정 |
|---|---|---|
| P1 | 저장 형식 | 평문 CSV/JSON을 git에 (star-trend와 같음) |
| P2 | 패키지 연결 | ~~ecosyste.ms 저장소→패키지 조회~~ → **이름 조회 + 저장소 패키지 파일**(D11). 저장소 URL 조회는 응답이 수십 MB이고 포크 패키지가 섞인다(star-trend MEASURE §22). 의존 수는 ecosyste.ms, CC-BY-SA 출처 표기 |
| P3 | GeekNews | 주간·소급 모두 포함(D12), 요청 간격 2초 |
| P4 | HTTP | 표준 라이브러리 `urllib` (새 패키지 0). M5의 `anthropic` SDK는 그때 사용자 확인 |

---

## 8. 리스크 (PLAN 추가분)

| ID | 리스크 | 대응 |
|---|---|---|
| PK1 | Search API 분당 30회가 주간 실행 시간을 늘린다 | 질의를 기간 OR로 묶을 수 있는지 M0에서 실측, 안 되면 실행 시간을 잡 제한(6시간) 안에서 감수 |
| PK2 | 과거 주를 지금의 AI 판정으로 걸러 소급이 실제 그때와 다르다 | 소급 값에 표시를 남기고 글에서 밝힌다 |
| PK3 | star-trend 토큰을 같이 써서 월요일 오전 한도가 겹친다 | 실행 시각을 star-trend 종료 뒤(09:00 UTC)로 두었다. 남은 한도를 시작 때 확인한다 |

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|---|---|---|
| v0.1 | 2026-11-13 | 초안. 입력 계약 실측, 아키텍처, 신호 수집 설계, 저장, M0~M6, 테스트 전략, 열린 결정 P1~P4 |
| v0.2 | 2026-11-13 | P1 평문 git · P2 ecosyste.ms · P3 M0 실측 뒤 · P4 urllib 확정 |
| v0.3 | 2026-11-13 | SPEC v0.3 F9 반영: `core/angles.py`(M2), 관점 글 초안·Notion(M5), 테스트 항목 |
| v0.4 | 2026-11-13 | M0 실측 반영: S2 소급 제외, S3 12주 한 질의 + 1,000건 초과 시 주별 분할, S4 패키지 파일 연결, P2 수정, P3 확정 |
