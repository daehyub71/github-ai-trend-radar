# PLAN.md — github-ai-trend-radar

> **상태: v0.7.10** (2026-11-16). 기준 문서는 `docs/SPEC.md` v0.7.10.
> PLAN 결정 P1~P6 확정(P5·P6은 2026-11-14 시안 합의 때 이의 없음). 숫자 근거는 `docs/MEASURE.md` §1(M0 실측).

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
    insights.py          (M7) 코드 관찰 I1~I7 (F10-1)
    evidence.py          (M7) 근거 모델·URL 정규화·중복 제거·번호 E1… (star-trend 이식)
    charts_data.py       (M8) 차트 데이터 — 12주 순위 시리즈·기여 막대·신호 지도 점·주별 신호 비중·카테고리 (F11)
  inputs/startrend.py  입력 계약 읽기·검증
  clients/transport.py 네트워크는 여기서만 (재시도·한도·녹화 재생)
  collectors/          신호별 수집기 — 서로 import 하지 않는다
    forks.py  (S2)     activity.py (S3)   packages.py (S4)   mentions.py (S5)
  evidence/            (M7) 해설 근거 — 서로 import 하지 않는다
    github.py (README·릴리스)  hn.py (글·큰 댓글 타래)  geeknews.py  web.py (Tavily 검색)
  store.py             평문 파일 읽기·쓰기 (§3)
  pipeline.py          주간 실행 순서 (F1)
  backfill.py          12주 소급 (F5)
  publish/             (M5) llm.py · gate.py · drafts.py · notion.py · budget.py
                       (M7) card.py (요청·JSON 스키마·파싱·렌더) · prompt_card.md · gate 근거 번호 검사
  cards.py             (M7) 해설 단계: 대상(TOP 10 + 관점) → 근거 → 해설 → 비공개 저장 → site-private 사본
                       (M8) publish/charts.py — matplotlib 으로 C1~C4·저장소 카드 PNG (matplotlib 은 이 파일에서만)
  cli.py               python -m radar <weekly|backfill|contract|notion|evidence|cards> [--dry-run]
web/                   (M4) Next.js 정적 사이트 — data/site 를 읽는다
  scripts/prepare-data.mjs (M7) 빌드 때 비공개 저장소의 site-private/ 만 받는다(읽기 전용 토큰, star-trend 이식)
  components/CardView·AiNote (M7) 해설 6절 · AI 작성 안내 · TOP 10 표 한 줄
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

- **M1 구현 세부 (2026-11-13)**
  - S2: 저장소를 ID(`/repositories/{id}`)로 조회해 이름이 바뀌어도 따라간다. 주간 증가는 **두 스냅샷 사이가 6~8일일 때만** 인정하고 아니면 결측(첫 실행·불규칙 실행 보호).
  - S4: 연결 확인은 레지스트리에서 직접 한다 — PyPI JSON(`project_urls`·`home_page`)·npm `/<name>/latest`(`repository`·`homepage`·`bugs`). 설명이 자리표시·이전 안내이거나 폐기된 패키지는 빼고, 설명이 가리키는 npm 패키지를 한 번 따라가 같은 확인을 한다(v0.7.2). 연결 결과는 `data/meta/packages.json`에 4주 캐시. 패키지가 없으면 상태 `none`(실패와 구분). 의존 수는 ecosyste.ms.
  - S5: GeekNews 날짜는 KST 라 UTC 주 끝을 덮도록 하루 더 읽고, 글 ID 로 중복을 뺀다.
  - 요청 간격: Search 2.1초 · GeekNews 2초 · pypistats 1초 · ecosyste.ms 0.2초. 429·5xx·연결 실패는 지수 대기 재시도, GitHub 한도는 reset 까지 대기(최대 15분).
- PR 작성자 고유 수는 Search API가 바로 주지 않는다. 머지 PR 목록(주당 최대 100건씩)을 받아 `user.login`에서 `[bot]`을 빼고 센다. 100건을 넘는 저장소는 페이지를 더 읽는다(상한을 둔다).
- 모든 응답은 녹화 파일로 테스트하고, 형식이 바뀌면 `partial`로 기록한다(F3).
- GitHub 토큰은 star-trend의 읽기 전용 토큰을 재사용한다(D8). 한 실행의 REST·Search 호출 수를 실행 기록에 남긴다.
- **M2 지수 구현 세부 (2026-11-13)**
  - 백분위 = 값이 있는 저장소끼리의 순위, 동점은 가운데 순위, `100 × (순위−1)/(n−1)`(하나뿐이면 100). 순위 백분위는 로그 같은 단조 변환에 바뀌지 않으므로 SPEC §4-1 ①의 "로그 뒤 비교"와 결과가 같다.
  - 합성 신호: S3 = 머지 PR·고유 작성자·닫힌 이슈 백분위 평균(D5), S4 = 다운로드·의존 수 백분위 평균, S5 = HN+GeekNews 글 수 합·점수 합 백분위 평균. 상태 `failed`(S4는 `none`도)는 결측.
  - 기여분 = 다시 나눈 가중치 × 백분위 — 합이 지수다. 순위는 지수 큰 순, 동점은 스타 증가 순위·ID.
  - `index/<주>.json` 은 쓰기 한 번 — 같은 입력이면 같은 파일, 가중치가 바뀌면 덮어쓰지 않아 지난 지수는 그때의 가중치로 남는다(§4-1 ④).
- **M2 소급 구현 세부 (2026-11-13)** — `python -m radar backfill [--anchor 주] [--weeks 12] [--dry-run]`
  - 소급 주 = 기준 주(첫 정기 수집 주 `2026-11-01`) 바로 앞 12주. 12주 동안 한 번이라도 후보였던 저장소(합집합 577개)를
    **처음 후보가 된 주부터 끝 주까지 창 하나로** 받는다(S3·S4 다운로드·HN). GeekNews 는 전체 기간 한 번.
  - 저장소마다 `.work/backfill/<기준주>-<주수>/` 에 바로 저장 — 끊겨도 다시 실행하면 이어 한다. 이미 쓴 주는 건너뛴다.
  - 주별 쓰기는 오래된 주부터: 후보 선정(지난주 TOP 보충은 앞 주 지수 필요) → signals(`backfilled=1`) → runs(`backfill: true`) → 지수.
    S2 는 상태 `none`(D10), 의존 수는 비운다(소급 불가) → 소급 주 S4 = 다운로드만.
  - 기준 주 `2026-11-01` 은 소급 전에 모아 지난주 TOP 보충 없이 후보가 정해졌다(소급 뒤 다시 쓰지 않는다).

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
| 비공개 저장소 `cards/<repo_id>.json` · `weeks/<주>/cards/` | 저장소 해설(최신 · 주별) | **비공개**(D13) |
| 비공개 저장소 `site-private/` | 사이트용 해설 사본 — Vercel 빌드가 받는다 | **비공개**, 화면에만 보인다(D13) |
| `.work/evidence/<주>/` | 근거 원문·검색 결과 캐시 | 커밋 안 함(gitignore) |

- 주간 파일은 한 번 쓰면 다시 쓰지 않는다. 다시 계산하면 가중치 버전을 올린다.

### 4-1. 해설 사본 형식 v1 (M7 — 웹과 해설 단계의 계약, 2026-11-14)

비공개 저장소 `site-private/` (웹은 빌드 때 받아 `web/.data/site-private/`, 로컬은 `../.private/site-private/`):

| 파일 | 내용 |
|---|---|
| `cards/<repo_id>.json` | 저장소의 **가장 최근** 해설 — 아래 형식 |
| `cards/index.json` | `[{repo_id, full_name, week}]` |
| `weeks/<주>.json` | `{week, lines: {"<repo_id>": "이번 주 왜 올랐나 한 줄"}}` — 홈 TOP 10 한 줄(D16) |

`cards/<repo_id>.json` (예시: `tests/fixtures/card_v1.json`):
- `version`(1) · `repo_id` · `full_name` · `week` · `generated`(UTC ISO) · `model` · `gate{checked, excluded}`
- `summary{what, why_now, watch}` — 각각 **Claim**
- `trend_notes[]` Claim(2~4) · `what[]` Claim + `label`(푸는 문제·구조·쓰는 사람·대안과 비교한 자리)
- `buzz{posts[], nature, trigger, reactions[], reading}` — `posts[]{site(HN|GeekNews), title, url, points, comments, date, target}`, `nature` 소개·호평·논란·질문·null, `trigger`·`reading` Claim 또는 null
- `watch[]` Claim(2~3) · `releases[]{tag, date, url}` · `evidence[]{id, title(120자), site, date, url}` · `history[]{week, why_now}`
- (M8, 선택) `diagram{nodes[]{id,label}, edges[]{from,to,label}}` 구조도 · `illustration{teach, prompt, labels[]}` 일러스트 프롬프트 — 없으면 null. 웹은 읽지 않는다
- **Claim** = `{text, sources[], basis}` — `sources` 는 근거 번호(`E1`…)와 코드 값(`F`), `basis` 는 `확인`|`추정`
- 숫자 표(02절 동향 표·04절 언급 숫자·05절 관찰)는 공개 `data/site/repo/<id>.json` 의 `trend`·`mentions`·`insights` 에서 온다(코드 계산)
- 크기 가드(커밋 전 훅 + CI)가 공개 저장소에 초안·해설이 들어오는 것을 막는다.

---

## 5. 마일스톤

| M | 이름 | 범위 | 완료 기준 |
|---|---|---|---|
| **M0** | 기반·실측 | git 저장소(공개)·비공개 저장소 생성, 골격·층 테스트·CI(테스트만), 입력 계약 읽기, **API 실측**: 후보 20개로 S2~S5 호출 수·시간·패키지 연결률·GeekNews 소급 범위 | 테스트 통과, `docs/MEASURE.md`에 실측 기록, P3 확정 |
| **M1** | 수집기 | S2~S5 수집기, transport(재시도·한도), 녹화 응답 테스트, 상태 기록 | 후보 200 실제 1회 수집 성공, 상태 표 기록 |
| **M2** | 지수·소급 | normalize·index(결측 재분배·기여분), 관점 유형 선정(`angles.py`), 12주 소급 1회 실행, 신호 간 상관·결측률·유형별 해당 수 실측 | 12주 지수 생성, MEASURE에 상관표·유형별 해당 수, **관점 임계값 조정 확인**, **가중치 v1 유지/v2 제안을 사용자와 확인** |
| **M3** | 주간 자동 실행 | Actions 워크플로(star-trend 신호로 시작 — D26 · 대비 예약 월 05:00 UTC — 2026-11-16 변경, 입력 대기·재시도, 이미 끝낸 주 건너뜀), 실행 기록, **보안 점검** 뒤 cron 활성화 | 수동 실행 1회 + 첫 예약 실행 성공 |
| **M4** | 사이트 | **DESIGN 시안(Claude Design 캔버스) 합의 →** Next.js 정적 사이트, Vercel 배포, 보안 점검 | 시안 합의 기록, 웹 lint·test·build 통과, 배포 |
| **M5** | 블로그·Notion | Sonnet 5.5 해설($3 상한), 게이트(숫자·링크·금지 표현), 별도 연재 초안, **관점 글 초안(F9)**, 비공개 저장소 저장, Notion 레이더 DB(글 종류 속성) | 실제 1주 TOP 10 글·관점 글과 Notion 페이지 검토 확인 |
| **M6** | 운영 관찰 | 연속 3주 자동 실행 관찰, 문제 정리 | 3주 연속 정상 |
| **M8** | 글 그림 (F11, 2026-11-14 추가) | matplotlib 추가(잠금 해시·층 규칙), 차트 데이터(core, TDD)·그리기(C1~C4·R1), **11-01 주 시안 그림 합의 →** 초안 결합(그림 자리·트렌드 분석 소제목·일러스트 프롬프트 R2), Notion 파일 업로드, 워크플로(한글 글꼴·그림 단계) | 시안 합의 기록, 11-08 주 자동 실행 초안·Notion 에 그림, 사용자 검토 |
| **M7** | 저장소 해설 (F10, 2026-11-14 추가) | **DESIGN 시안 v2 합의 →** 코드 관찰 I1~I7, 근거 수집(README·릴리스·HN 글·댓글·GeekNews·Tavily), Sonnet 5.5 해설 6절(JSON 스키마)·게이트(근거 번호·URL·숫자·단정), 비공개 저장·site-private, 빌드 때 받기, 저장소 화면·TOP 10 한 줄, 주간 워크플로 단계, **보안 점검** 뒤 배포 | 시안 합의 기록, 11-01 주 실제 1회(장당 비용·게이트 제외 수 MEASURE 기록), 사용자 검토, 웹 lint·test·build, 배포 |

- M3까지 끝나면 사이트 없이도 매주 지수가 쌓인다. 사이트·글은 그 데이터 위에 올린다.
- 마일스톤마다 사용자 확인 뒤 다음으로 넘어간다.
- M7은 M6(관찰)과 같은 기간에 진행한다. M6은 매주 실행을 지켜보는 일이라 겹쳐도 된다.

---

## 6. 테스트 전략

- **core**: 관점 유형 경계값·유형 중복 우선순위(D→C→A→B)·5개 상한·이력 부족 처리, 백분위·결측 재분배·기여분 합 = 지수, 같은 입력 → 같은 결과, 동점 처리, 후보 선정 경계(200위 동점·지난주 TOP 10 보충). TDD로 먼저 쓴다.
- **inputs**: star-trend 실제 파일 일부를 픽스처로 둔 계약 테스트 + 필드 누락 통제군.
- **collectors**: 녹화 응답 재생. 429·5xx 재시도, 형식 변경 → `partial`, 봇 제외.
- **pipeline**: 한 신호 실패 시 나머지로 지수, 빠진 신호 표시.
- **publish(M5)**: 게이트가 없는 숫자·링크·금지 표현을 실제로 잡는지 통제군.
- **web(M4)**: 컴포넌트 핵심 동작(Vitest).
- **M7**: 관찰 I1~I7 경계값(데이터 없음·0·동점·포크 증가 없음)을 TDD로 먼저. 근거 수집기는 녹화 응답(README 없음·릴리스 0·HN 댓글 없음·Tavily 실패 → 그 출처만 빠짐). 해설 게이트 통제군 — 근거 번호 없는 항목·목록 밖 URL·facts 밖 숫자·단정 표현·근거 속 지시문(주입)을 실제로 잡는지. 웹: 프로덕션에서 토큰 없으면 빌드 실패, 해설 없는 저장소는 숫자·관찰만, AI 작성 안내 렌더.
- 검증 명령: `ruff check .` · `mypy radar tests` · `pytest` · (웹) `npm run lint && npm test && npm run build`.

---

## 7. PLAN 결정 (2026-11-13 사용자 확정)

| ID | 항목 | 결정 |
|---|---|---|
| P1 | 저장 형식 | 평문 CSV/JSON을 git에 (star-trend와 같음) |
| P2 | 패키지 연결 | ~~ecosyste.ms 저장소→패키지 조회~~ → **이름 조회 + 저장소 패키지 파일**(D11). 저장소 URL 조회는 응답이 수십 MB이고 포크 패키지가 섞인다(star-trend MEASURE §22). 의존 수는 ecosyste.ms, CC-BY-SA 출처 표기 |
| P3 | GeekNews | 주간·소급 모두 포함(D12), 요청 간격 2초 |
| P4 | HTTP | 표준 라이브러리 `urllib` (새 패키지 0). M5의 `anthropic` SDK는 그때 사용자 확인 |
| P5 | 해설 코드 | star-trend의 근거·게이트·빌드 받기 코드를 **복사해 고친다**(공유 패키지로 만들지 않는다 — ai-trend-batch `budget.py` 복사 선례). 레이더 층 규칙 안으로 옮긴다 |
| P7 | 그림 (M8) | matplotlib(Agg) 로 PNG 를 그린다. 글꼴은 이름으로 찾고(Noto Sans CJK KR → Apple SD Gothic Neo), 없으면 그림 단계만 실패로 남기고 초안은 그림 자리 없이 쓴다. Notion 업로드·결합은 star-trend `notion` 업로드 방식을 옮긴다(P5) |
| P8 | 저장소 설명 그림 (M8) | 해설 단계(`radar cards`)가 근거와 함께 그림 후보를 모은다 — README 는 이미 받은 원문에서, 소셜 미리보기·홈페이지는 GraphQL 한 번, 홈페이지 og:image 는 HTML 한 번, 웹 이미지는 Tavily 같은 검색에 `include_images`(크레딧 추가 없음). 고른 그림만 받아 Pillow 로 확인한다(Pillow 도 `publish/charts.py` 에서만). 구조도·일러스트 프롬프트는 해설 JSON 스키마에 `diagram`·`illustration` 을 더한다 — 호출 수는 그대로. 구조도는 상자 라벨 목록 + `"1>2 라벨"` 문자열로 받는다(객체로 두면 구조화 출력 문법 한도 초과, v0.7.1). 스키마를 바꾸면 `pytest -m live tests/test_live_schema.py` |
| P6 | 해설 호출 | Sonnet 5.5 일반 호출(Batch 안 씀) — 25장 × 약 35초 ≈ 15분이라 주간 실행 시간 안에 든다. 실패하면 한 번 다시 묻고, 그래도 안 되면 그 저장소는 숫자·관찰만 |

---

## 8. 리스크 (PLAN 추가분)

| ID | 리스크 | 대응 |
|---|---|---|
| PK1 | Search API 분당 30회가 주간 실행 시간을 늘린다 | 질의를 기간 OR로 묶을 수 있는지 M0에서 실측, 안 되면 실행 시간을 잡 제한(6시간) 안에서 감수 |
| PK2 | 과거 주를 지금의 AI 판정으로 걸러 소급이 실제 그때와 다르다 | 소급 값에 표시를 남기고 글에서 밝힌다 |
| PK3 | star-trend 토큰을 같이 써서 월요일 오전 한도가 겹친다 | star-trend 는 실행 맨 끝에 공개 데이터를 push 한 뒤 레이더를 시작시킨다(D26) — 레이더는 그 뒤에야 수집을 시작한다. 대비 예약 실행도 입력 대기로 그 push 를 기다린다. 남은 한도를 시작 때 확인한다 |
| PK4 | 해설 단계가 주간 실행을 늘린다(근거 약 20초 + 해설 약 35초 × 25 ≈ 25분) | 잡 제한 240분 안. 해설 단계는 수집·지수·커밋 뒤에 두어 실패해도 공개 데이터는 나간다 |
| PK6 | matplotlib 이 무겁다(numpy·pillow 등) — 해시 잠금 설치 시간이 는다 | Actions 캐시 없이도 1분 안팎(실측 T8-2). 그림은 공개 데이터 수집·지수 뒤 단계라 실패해도 수집은 나간다 |
| PK5 | 빌드 때 비공개 저장소를 받지 못하면 사이트 배포가 멈춘다 | 프로덕션만 실패시키고 미리보기는 해설 없이 빌드한다. 토큰 만료일을 TASKS에 적는다 |

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|---|---|---|
| v0.1 | 2026-11-13 | 초안. 입력 계약 실측, 아키텍처, 신호 수집 설계, 저장, M0~M6, 테스트 전략, 열린 결정 P1~P4 |
| v0.2 | 2026-11-13 | P1 평문 git · P2 ecosyste.ms · P3 M0 실측 뒤 · P4 urllib 확정 |
| v0.3 | 2026-11-13 | SPEC v0.3 F9 반영: `core/angles.py`(M2), 관점 글 초안·Notion(M5), 테스트 항목 |
| v0.4 | 2026-11-13 | M0 실측 반영: S2 소급 제외, S3 12주 한 질의 + 1,000건 초과 시 주별 분할, S4 패키지 파일 연결, P2 수정, P3 확정 |
| v0.7.10 | 2026-11-16 | D28 보강 — `post_markdown(summary_image=)` 이 그림 아래에 `summary_prompt` 의 라벨 5개를 "그림 라벨(왼쪽부터)" 한 줄로 |
| v0.7.9 | 2026-11-16 | D28 — `drafts.summary_prompt(facts)` → (프롬프트, 라벨 5). `post_markdown(summary_image=)` · `blog._write` 가 `gen/summary.*` 를 찾는다. 관심 비중은 `core.charts_data.trend_observations` 문장에서 읽는다(형식 결합 테스트) |
| v0.7.8 | 2026-11-16 | D27 — `drafts.restyle(prompt, 유형, 순번)` 이 다크 블루프린트 첫 문장을 유형 강조색 × 바탕(남색·제도지·그래파이트·미색 제도지, 유형마다 시작을 민다) 문장으로 바꾼다. `angles_markdown` 이 유형 안 순번을 넘긴다 |
| v0.7.7 | 2026-11-16 | D25 보강 — `drafts.angles_markdown(notes=)` · `_what` 이 요약 없을 때 초안 문장을 `_drop_unknown` 으로 걸러 첫 줄로. `blog._write` 가 관점 글에도 해설을 넘긴다 |
| v0.7.6 | 2026-11-16 | D26 — star-trend 워크플로 맨 끝 `레이더 시작 신호` 단계(`gh workflow run weekly -f mode=run`). 레이더: `weekly --check-input` 종료 코드 5(이미 끝낸 주) → 입력 대기 단계가 `GO` 를 `GITHUB_ENV` 에 쓰고 뒤 단계는 `env.GO` 로만 돈다 · 체크아웃 `ref: main` · 대기 5분 × 24 |
| v0.7.5 | 2026-11-16 | 주간 cron 월 05:00 UTC(14:00 KST) — star-trend 보다 먼저 시작해도 입력 대기가 공개 데이터 push 를 기다린다 |
| v0.7.4 | 2026-11-15 | D25 — `blog._write` 가 그 주 해설 사본(`weeks/<주>/cards/*.json`)과 `gen/cover*.*` 를 읽어 `drafts` 에 넘긴다. 주간 순서는 그대로 — 초안(해설 전)은 LLM 문단, 그림 단계의 다시 쓰기에서 해설로 바뀐다 |
| v0.7.3 | 2026-11-14 | D24 — 해설 프롬프트의 일러스트 지시를 다크 블루프린트 기술 도해로, 게이트 `STYLE_BANNED`(금지 절 "No …" 는 검사에서 뺀다) |
| v0.7.2 | 2026-11-14 | S4 연결 보강(자리표시·폐기 패키지 제외, 가리키는 패키지 따라가기) · I2 는 같은 패키지 주끼리만 비교 |
| v0.7.1 | 2026-11-14 | P8 구조도 응답 형식(문자열 목록) · 주간 순서 초안 → 해설 → 그림(초안에 넣기) → Notion(그림 업로드) |
| v0.7 | 2026-11-14 | SPEC v0.7 D21~D23 반영: P8 저장소 설명 그림(후보 수집·확인·구조도) |
| v0.6 | 2026-11-14 | SPEC v0.6 F11 반영: M8 글 그림(차트 데이터·그리기·초안 결합·Notion 업로드), P7, PK6 |
| v0.5 | 2026-11-14 | SPEC v0.5 F10 반영: M7 저장소 해설(모듈·저장·테스트), P5·P6 제안, PK4·PK5 |
