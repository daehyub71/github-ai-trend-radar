# TASKS.md — github-ai-trend-radar

> 기준: `docs/SPEC.md` v0.4 · `docs/PLAN.md` v0.4. 항목은 완료 즉시 체크하고 대시보드를 같이 갱신한다.

## 진도율 대시보드

| 마일스톤 | 진도 | % | 태스크 | 상태 |
|---|---|---|---|---|
| M0 기반·실측 | ██████████ | 100% | 10/10 | ✅ 2026-11-13 |
| M1 수집기 | ██████████ | 100% | 8/8 | ✅ 2026-11-13 |
| M2 지수·소급 | ██████████ | 100% | 9/9 | ✅ 2026-11-14 (사전 위임 — T2-7·T2-9 아침 확인) |
| M3 주간 자동 실행 | ████████░░ | 83% | 5/6 | 🔄 11-16 첫 예약 실행 대기 |
| M4 사이트 | ██████████ | 100% | 7/7 | ✅ 2026-11-14 (시안은 사전 위임 — 확인 대기) |
| M5 블로그·Notion | █████████░ | 89% | 8/9 | 🔄 사용자 검토 대기 |
| M6 운영 관찰 | ░░░░░░░░░░ | 0% | 0/3 | 🔜 |
| M7 저장소 해설 | ██████████ | 100% | 11/11 | ✅ 2026-11-14 |
| **전체** | █████████░ | **92%** | **58/63** | |

---

## M0 기반·실측

- [x] T0-1 git 저장소 생성(공개 `daehyub71/github-ai-trend-radar`)·`.gitignore`(`.env`·`.venv`·`.work`)·프로젝트 `CLAUDE.md`
- [x] T0-2 비공개 저장소 생성(`github-ai-trend-radar-private`), 로컬 `.private/` 클론 규칙
- [x] T0-3 Python 골격(`radar/` 층 구조, `pyproject.toml`, ruff·mypy·pytest 설정, `.venv`)
- [x] T0-4 층 테스트(`test_architecture.py`)와 네트워크 차단 `conftest.py` + 통제군
- [x] T0-5 커밋 전 훅(ruff·mypy·pytest·크기 가드)
- [x] T0-6 입력 계약: star-trend 데이터 읽기·검증(`inputs/startrend.py`), 픽스처 테스트 (TDD)
- [x] T0-7 후보 선정(`core/candidates.py`): AI × 스타 증가 상위 200 + 지난주 TOP 10 보충 (TDD)
- [x] T0-8 CI 워크플로(테스트만, 권한 최소·SHA 고정) — 첫 실행 성공(2026-11-13, 해시 잠금 설치 확인)
- [x] T0-9 API 실측(후보 20개): S2 포크 목록·S3 Search 질의·S4 ecosyste.ms 연결률·S5 HN — 호출 수·시간을 `docs/MEASURE.md`에
- [x] T0-10 GeekNews 소급 범위·약관 확인 → P3 결정 기록 (D12: 주간·소급 포함)

## M1 수집기

- [x] T1-1 `clients/transport.py` — urllib, 재시도(429·5xx), 한도 확인, 녹화 재생 (TDD)
- [x] T1-2 S2 포크 수집기(메타 스냅샷 주간 차이만, 소급 없음 — D10)
- [x] T1-3 S3 활동 수집기(머지 PR·고유 작성자·닫힌 이슈, 봇 제외, 12주 한 질의 → 주별 분할, 1,000건 초과 시 주 단위 재질의)
- [x] T1-4 S4 패키지 연결(이름 조회 + 저장소 패키지 파일, D11, 캐시)·다운로드(pypistats·npm)·의존 수 스냅샷 — 연결률 재측정(MEASURE)
- [x] T1-5 S5 언급 수집기(HN Algolia + GeekNews `/past?day=`, 간격 2초 — D12)
- [x] T1-6 소스 상태(`ok`·`partial`·`failed`)와 실행 기록(호출 수)
- [x] T1-7 `store.py` 평문 쓰기(한 번 쓴 주간 파일은 다시 쓰지 않음)
- [x] T1-8 후보 200 실제 1회 수집, 상태 표 기록 (MEASURE §2 — 44분, 패키지 연결 23.5%)

## M2 지수·소급

- [x] T2-1 `core/normalize.py` — 로그 → 백분위, 동점, S3 합성(D5) (TDD)
- [x] T2-2 `core/index.py` — 가중 평균·결측 재분배·기여분, 가중치 버전 (TDD)
- [x] T2-3 `pipeline.py` 주간 순서(F1), 신호 실패 시 나머지로 지수
- [x] T2-4 `backfill.py` 12주 소급, 소급 표시
- [x] T2-5 12주 소급 실제 1회 실행 — 2026-11-13 08:38~15:10 UTC 392분, 577개·Search 6,104 (MEASURE §3)
- [x] T2-6 신호 간 상관·결측률 실측 → `docs/MEASURE.md` — 상관 |r| ≤ 0.23, 실효 비중 사용 7.3%·언급 28.3% (MEASURE §3-1~3-4)
- [x] T2-7 가중치 v1 유지 / v2 제안 사용자 확인 — **v1 유지**(사전 위임 2026-11-14). v2 안 3개는 MEASURE §3-6, 아침 확인
- [x] T2-8 `core/angles.py` — 관점 유형 A~D 선정·중복 우선순위·5개 상한·이력 부족 (TDD, F9)
- [x] T2-9 소급 12주로 유형별 해당 수 실측 → 임계값 조정 사용자 확인 — v1 고정 + D 에 "같은 신호 범위" 조건 추가(거짓 전환 제거). 아침 확인

## M3 주간 자동 실행

- [x] T3-1 주간 워크플로(월 09:00 UTC, 입력 갱신 대기 30분×4) — `.github/workflows/weekly.yml`
- [x] T3-2 데이터 커밋 잡(공개 데이터만) + 크기 가드 — `git add data` + `size_guard --staged`, 사이트 데이터·M5 단계(토큰 있을 때만) 포함
- [x] T3-3 CLI `weekly --dry-run` 호출 수 예측 — `python -m radar weekly [--check-input] [--dry-run]`, 입력 대기 종료 코드 4
- [x] T3-4 보안 점검(보안 리뷰·시크릿·CI 권한·아티팩트) — 2026-11-14 보안 리뷰 HIGH·MEDIUM 0, 워크플로 규칙 테스트(`tests/test_workflow.py`) + 통제군
- [x] T3-5 Secrets 등록(star-trend 키 재사용, D8)·수동 실행 1회 — 2026-11-14 사용자가 키체인에서 4개 등록(`RADAR_GH_TOKEN`·`STARTREND_ANTHROPIC_API_KEY`·`NOTION_TOKEN`·`STARTREND_TAVILY_API_KEY`). 점검 모드 수동 실행 성공(run 43558458501): 토큰 있음 · 시간당 한도 5,000 · 입력 계약 통과(AI 1,425 · 최신 11-01 · 후보 200). `RADAR_PRIVATE_REPO_TOKEN` 은 미등록 — 그동안 초안·해설·Notion 단계는 건너뛴다
- [ ] T3-6 첫 예약 실행 성공 확인

## M4 사이트

- [x] T4-1 IA·와이어프레임 (`docs/DESIGN.md`) — `docs/DESIGN.md` §1·§2
- [x] T4-2 UI 시안 — Claude Design 캔버스, 사용자 합의 기록 — 캔버스 https://claude.ai/artifact/AumXGbBzQjdsEuvbsWJTXk · 사전 위임 합의(DESIGN §6), 아침 확인
- [x] T4-3 사이트 파생 데이터 내보내기(`data/site/`) — `python -m radar site` → `data/site/`(weeks·week·repo), LLM 글 없음
- [x] T4-4 Next.js 화면 구현(합의된 화면만) + 컴포넌트 테스트 — `web/` 홈·주·저장소·방법, 컴포넌트 테스트 5
- [x] T4-5 ecosyste.ms 출처 표기·소급 표시·AI 판정 기준 안내 — 바닥글·방법 화면
- [x] T4-6 보안 점검 뒤 Vercel 배포 — https://github-ai-trend-radar.vercel.app (2026-11-14). 프로젝트 `github-ai-trend-radar`(루트 `web`·루트 밖 파일 포함·Node 24.x, star-trend 와 같은 설정)를 API 로 만들고 깃허브 저장소를 연결해 main 푸시마다 자동 배포 — 봇의 주간 데이터 커밋도 배포됨(star-trend 실적). 점검: 보안 리뷰(HIGH·MEDIUM 0) · `web`·`data/site` 키 패턴 0 · 환경 변수 0 · 프로덕션 5화면 200·없는 주소 404, 미리보기 배포는 Vercel 인증 보호
- [x] T4-7 웹 lint·test·build 통과 — lint·test·build(정적 206쪽) 통과, CI 에 web 작업 추가

## M5 블로그·Notion

- [x] T5-1 `anthropic` SDK 추가 사용자 확인 — `anthropic>=2.4,<3`(lock 2.8.0), 사전 위임
- [x] T5-2 예산(`budget.py`, 실행당 $3, 실행 기록에 금액) — `radar/publish/budget.py`, 실행 기록에 금액
- [x] T5-3 해설·초안 생성(Sonnet 5.5, 숫자는 코드가 채움) — 1회 호출 49문단, 11-01 실측 $0.0998
- [x] T5-4 게이트(숫자·링크·금지 표현) + 통제군 (TDD) — `radar/publish/gate.py` + 통제군(`tests/test_publish.py`)
- [x] T5-5 별도 연재「깃허브 AI 트렌드 레이더」 초안(사용자 견본 틀) — `.private/weeks/2026-11-01/blog/post.md`
- [x] T5-6 비공개 저장소 저장·동기화 — 로컬 비공개 저장소 커밋·푸시(cfffb97). Actions 는 `RADAR_PRIVATE_REPO_TOKEN` 있을 때만
- [x] T5-7 Notion 레이더 DB 생성(star-trend 연결 공유), "초안"만 갱신 — Notion「깃허브 AI 트렌드 레이더」DB 생성(대응표 `.private/notion/index.json`)
- [x] T5-8 관점 글 초안(유형 A~D × 최대 5, 근거 숫자 표, B 유형 단정 금지 게이트) + Notion "글 종류" 속성 — `angles.md` A·B·D 5개 · C 4개, Notion "글 종류"=관점
- [ ] T5-9 실제 1주 TOP 10 글·관점 글과 Notion 검토 확인

## M6 운영 관찰

- [ ] T6-1 1주차 자동 실행 정상
- [ ] T6-2 2주차 자동 실행 정상
- [ ] T6-3 3주차 자동 실행 정상, 문제 정리

## M7 저장소 해설 (F10, 2026-11-14 추가)

- [x] T7-1 SPEC v0.5(F10, D13~D16, K8~K10) · PLAN v0.5(M7, P5·P6 제안) — 사용자 결정 4개(질문지 2026-11-14)
- [x] T7-2 시안 v2 — 캔버스 아트보드 3장(저장소 v2 · 화제 절 · TOP 10 한 줄), DESIGN §2-2b·§6
- [x] T7-3 시안 v2 사용자 합의 (DESIGN §6에 기록) — 2026-11-14 수정 없이 합의
- [x] T7-4 코드 관찰 I1~I7 `core/insights.py` (TDD) + 사이트 내보내기 `insights` — 02절 동향 표(`trend`)·04절 언급 숫자(`mentions`)도 같이. remotion 실제 값이 시안과 글자 그대로 같다. 테스트 13개 추가
- [x] T7-5 근거 수집기 `evidence/`(README·릴리스·HN 글·댓글·GeekNews·Tavily) + 녹화 응답 테스트 + `.work/evidence/` 캐시 — 새 층 `evidence`(층 테스트 통제군 추가), GeekNews 해석은 `core/geeknews.py` 로 옮겨 S5 와 같이 쓴다(글 제목도 읽음). 테스트 11개
- [x] T7-6 해설 요청·JSON 스키마·파싱 `publish/card.py` + 게이트(근거 번호·목록 밖 URL·facts 밖 숫자·단정·주입) 통제군 — `prompt_card.md`, 근거 표는 인용한 것만, 사본 형식 v1(PLAN §4-1)과 키가 같은지 테스트. 테스트 4개
- [x] T7-7 `radar cards` 단계 — 대상(TOP 10 + 관점)·예산·비공개 저장·`site-private/` 사본·`--dry-run` — 예산은 상한 − 그 주 초안 비용, 읽지 못하면 1회 다시, 실패 출처는 캐시하지 않음. 11-01 dry-run: 대상 28 · Tavily 84크레딧 · 예상 $1.51 · 남은 예산 $2.90. 테스트 6개
- [x] T7-8 11-01 주 실제 1회(dry-run 제시 뒤) — 장당 비용·게이트 제외 수 MEASURE §4, Tavily 남은 크레딧 확인(K8) — 28/28 성공, $1.30(장당 $0.046), Tavily 84크레딧, 게이트 제외 7(모두 사실 밖 숫자), 약 7.5분. 남은 크레딧은 Tavily 대시보드에서 사용자 확인
- [x] T7-9 웹 — 빌드 때 받기(`prepare-data`)·해설 화면·AI 작성 안내·TOP 10 한 줄 + 컴포넌트 테스트 (**T7-3 합의 뒤**) — 웹 테스트 5 → 40, 해설 있음/없음 두 빌드 통과. 링크는 http·https 만, 프로덕션은 해설 사본 설정이 없으면 빌드 실패(의도). 시안과 다른 점: star-trend 카드 링크 줄은 계약에 필드가 없어 뺐다, 해설 없는 저장소는 절 번호를 숨긴다
- [x] T7-10 주간 워크플로 해설 단계 + Secrets `STARTREND_TAVILY_API_KEY` · Vercel 환경 변수 `RADAR_PRIVATE_REPO`·`RADAR_PRIVATE_READ_TOKEN`(사용자 등록) — 2026-11-14 모두 등록. 쓰기 토큰 `radar-private-rw`(워크플로 점검에서 비공개 저장소 읽기 OK) · 읽기 전용 `radar-private-read`(Vercel, 등록 스크립트가 등록 전 실제 읽기 확인)
- [x] T7-11 보안 점검 뒤 배포, 사용자 검토 — 보안 점검(커밋 42b03af) HIGH·MEDIUM 0, 2026-11-14 배포됨(빌드가 해설 사본 32개를 받음, 608쪽). 검토는 사용자 위임으로 Claude 가 했다(MEASURE §4-1): 28개 일괄 점검 통과, 숫자 대조 일치, 고칠 점 1(성격 "논란" 과판정) — 규칙 보강은 사용자 결정 대기

---

## 트러블슈팅 기록

- **2026-11-13 소급이 추정의 2.4배(392분)** — storytold/* 처럼 주마다 PR 1,000건이 넘는 저장소는 주별 재질의로 저장소당 약 3분. 저장소별 `.work/backfill/` 캐시로 중간에 끊겨도 이어 할 수 있다.
- **2026-11-13 지난주 TOP 보충 저장소가 그 주 스타 파일에 없으면 `gain_rank` 가 비어 `build_index` 가 멈췄다** — 비면 동점 맨 뒤로, 사이트·초안에는 "—". 테스트 `test_backfill_writes_marked_weeks_with_index_and_prev_top`.
- **2026-11-14 D(신호 전환)가 신호가 새로 채워진 저장소를 잡았다** — 두 주에 값이 있는 신호가 같을 때만 비교(MEASURE §3-5).
- **2026-11-14 Secrets 등록(`gh secret set`)은 자동 모드에서 막혔다** — 사용자가 직접 등록한다(T3-5).
- **2026-11-14 Vercel 빌드가 해설 사본을 받지 못함** — 푸시 뒤 프로덕션 빌드 3번이 `git clone` 에서 실패(사이트는 이전 버전 유지). 로그: `could not read Username … terminal prompts disabled` = 자격 증명 도우미가 없는 곳에서 **토큰이 거부(401)** 됐다는 뜻(로컬에서 같은 조건으로 재현). 같은 날 만든 쓰기 토큰은 워크플로 점검에서 비공개 저장소를 읽었다 → Vercel 의 `RADAR_PRIVATE_READ_TOKEN` 값이 틀렸다. 원인 추정: 클립보드에서 값을 읽는 등록 스크립트 — 토큰을 복사한 뒤 명령을 복사하면 클립보드가 바뀐다. 대응: 빌드 스크립트가 실패 원인 종류와 가린 git 오류 한 줄을 남기게 했고, 등록 스크립트는 숨김 입력 + 등록 전 실제 읽기 확인으로 바꿨다.
- **2026-11-14 claude-code 사용 신호가 비공식 패키지에 연결됨** — `anthropics/claude-code` 의 S4 가 `npm:claude-code`(주 9,795회)로 잡혔다. 공식은 `@anthropic-ai/claude-code`. 이름 조회 후보의 저장소 URL 이 같아 통과한 것으로 보인다(D11 확인 규칙의 빈틈). 코드 관찰 I1 이 이 값을 쓴다 — 고칠지 사용자 확인 대기.
- **2026-11-14 Vercel CLI 토큰 만료** — `vercel login` 이 계정 2단계 인증(2026-07-18 켜짐) 코드 화면에서 막혔다. 사용자 승인으로 krx-signal-briefing `.env` 의 `VERCEL_TOKEN` 을 명령에만 넘겨(값 출력 없음) API 로 프로젝트 생성·깃허브 연결·배포했다. 이후 갱신은 깃허브 연동 자동 배포라 CLI 로그인이 필요 없다. 2단계 인증 복구는 계정 문제로 따로 남는다.
