# github-ai-trend-radar

[English](README.md) | 한국어

> 깃허브 AI 저장소의 주간 흐름을 스타 하나가 아니라 **다섯 신호로 읽는 종합 트렌드 지수**입니다.
> Claude Code 로 만드는 개인 프로젝트이며 아직 진행 중입니다. 프로젝트 문서(`docs/`)는 한국어입니다.

**사이트: <https://github-ai-trend-radar.vercel.app>** — 이번 주 종합 TOP 10, 신호별 TOP 5, 관점 노트, 저장소별 화면.
사이트의 저장소 해설은 사람이 검토하지 않은 AI 요약입니다. 주장마다 근거 번호와 "확인·추정" 표시가 붙고, 숫자는 모두 코드가 계산합니다.

## 왜 만들었나

스타는 관심을 보여 줄 뿐 사용을 보여 주지 않습니다. 데모 하나가 한 주에 스타 수천 개를 모으는 동안, 수백만 명이 설치하는 라이브러리는 스타가 조용할 수 있습니다. 그래서 AI 저장소를 매주 다섯 신호로 읽습니다.

| 신호 | 주간 값 | 출처 | 가중치 v1 |
|---|---|---|---|
| 스타 | 스타 증가 | [github-ai-star-trend](https://github.com/daehyub71/github-ai-star-trend) 공개 데이터 | 15 |
| 포크 | 포크 증가(스냅샷 6~8일 간격) | GitHub 저장소 메타 | 15 |
| 기여 | 머지 PR · 고유 PR 작성자 · 닫힌 이슈(봇 제외) | GitHub Search API | 25 |
| 사용 | 패키지 주간 다운로드 · 의존 패키지 수 | pypistats · npm · ecosyste.ms | 30 |
| 언급 | 저장소를 링크한 글 수 · 점수 | Hacker News(Algolia) · GeekNews | 15 |

예를 들어 2026-11-01 주 `remotion-dev/remotion` 은 스타 순위 70위였지만, 주간 다운로드 약 350만 회와 늘어나는 PR 작성자 덕에 종합 지수 6위였습니다.

## 진행 상태 (2026-11-14)

| 마일스톤 | 상태 |
|---|---|
| M0 · 기반과 API 실측 | ✅ 완료 |
| M1 · 신호 수집기 | ✅ 완료 |
| M2 · 지수와 12주 소급(저장소 577개, 지수 13주) | ✅ 완료 |
| M3 · 깃허브 Actions 주간 실행 | 🔄 2026-11-16 첫 예약 실행 |
| M4 · 사이트(Next.js · Vercel) | ✅ 배포됨 |
| M5 · 블로그 초안과 Notion 페이지 | 🔄 사람 검토 대기 |
| M6 · 3주 운영 관찰 | 예정 |
| M7 · 저장소 해설 | ✅ 배포됨 |
| M8 · 글 그림(차트 · 저장소 그림 · 구조도) | 🔄 초안과 Notion 에 들어감, 2026-11-16 첫 예약 실행 |

진도율 대시보드는 [`docs/TASKS.md`](docs/TASKS.md) 맨 위에 있습니다.

## 동작 방식

```
star-trend 공개 데이터 ──► 후보 (AI 저장소: 주간 스타 증가 상위 200 + 지난주 TOP 10)
                             │
                             ▼
     수집기: 포크 · 기여 · 사용 · 언급   (urllib, 재시도, 요청 한도)
                             │
                             ▼
     지수: 그 주 후보 안 백분위 → 가중 평균 → 신호별 기여분
                             │
          ┌──────────────────┼──────────────────────────┐
          ▼                  ▼                          ▼
   사이트 데이터(공개)    관점 노트 A~D              저장소 해설(AI)
   data/site/            (코드가 고른다)            근거 → Claude → 게이트 → 비공개 저장소
          │                                             │
          └────────────► Next.js 사이트 ◄─── 빌드 때 받는다(읽기 전용 토큰)
```

- **지수.** 신호마다 그 주 후보 안에서 백분위 순위를 매기고(같은 값은 가운데 순위), 가중 평균을 냅니다. 값이 없는 신호(패키지 없음, 포크 스냅샷 전)는 **0점이 아니라 계산에서 빼고 가중치를 다시 나눕니다.** 기여분 막대로 어느 신호가 순위를 만들었는지 보여 줍니다.
- **관점 노트.** 코드가 유형마다 최대 5개 저장소를 고릅니다. A 조용한 강자(스타는 낮고 사용·기여는 높음), B 반짝 관심(스타·언급은 높고 사용은 낮음), C 꾸준한 상승(지수 4주 연속 상승), D 신호 전환(관심 비중이 내려가고 사용·기여 비중이 오름)입니다.
- **코드 관찰.** 모든 저장소 화면에 숫자만으로 계산한 관찰이 나옵니다. 스타 1개당 다운로드, 4주 평균 대비 다운로드 추세, PR 작성자 증가, 글 하나가 언급 신호를 다 만들었는지 같은 것입니다.
- **저장소 해설.** 그 주 TOP 10과 관점 노트 저장소에 대해 코드가 근거를 모읍니다. README, 릴리스, Hacker News 글과 큰 댓글 타래, GeekNews 글, 웹 검색(Tavily) 결과입니다. Claude Sonnet 5.5 가 3줄 요약 · 이번 주 동향 · 무엇인가 · 어디서 어떻게 화제가 됐나 · 지켜볼 점을 정해진 JSON 형식으로 씁니다. 코드 게이트가 근거 번호가 없는 주장, 링크를 쓴 주장, 계산한 사실에 없는 숫자를 쓴 주장, 금지 표현을 쓴 주장을 뺍니다.
- **글 그림.** matplotlib 이 계산한 숫자로만 차트 4종을 그립니다. TOP 10 의 12주 순위 추이, 신호 기여, 신호 지도(관심 × 실사용), 신호 비중·카테고리의 12주 트렌드입니다. 해설 대상 저장소마다 설명 그림 하나를 출처·저작권 상태와 함께 고릅니다. README 그림(허용형 라이선스만), 주인이 올린 소셜 미리보기, 홈페이지 대표 이미지, 웹 이미지 검색 순이고, 아무것도 없으면 Claude 가 README 로 정리한 "어떻게 동작하나" 구조도를 코드가 그립니다. 그림은 블로그 초안에 들어가고 Notion 초안 페이지에 올라갑니다. 해설이 있으면 초안의 저장소별 "무엇인가"는 해설(README·웹 근거)로 채우고, 사람이 만든 대표 이미지 `gen/cover.png` 는 제목 아래에 넣습니다.
- **주간 실행.** star-trend 주간 실행이 성공하면 마지막 단계가 이 저장소의 주간 실행을 시작시킵니다. 입력이 올라오자마자 레이더가 돕니다. 월요일 05:00 UTC(14:00 KST) 예약은 대비로 남아, star-trend 데이터를 5분마다 최대 2시간 다시 봅니다. 그 주를 이미 끝냈으면 뒤 단계를 모두 건너뛰므로, 두 실행이 다 돌아도 유료 단계는 한 주에 한 번만 돕니다.

## 개발 원칙

- **숫자는 코드가, 글은 LLM 이.** 순위·백분위·지수·관점 선정·관찰은 코드가 계산합니다. LLM 은 설명만 쓰고, 게이트가 그 규칙을 지킵니다.
- **공개 저장소, 비공개 글.** 코드와 계산한 데이터는 공개합니다. LLM 이 쓴 초안·해설·Notion 대응표는 별도 비공개 저장소에 두고, 사이트는 빌드 때 읽기 전용 토큰으로 해설 사본만 받습니다. 크기 가드가 초안이 이 저장소에 들어오는 것을 막습니다.
- **테스트 먼저, 네트워크 없이.** 기본 테스트는 네트워크·키·비용 없이 돕니다(소켓을 막는 픽스처). 수집기는 녹화한 응답으로 검사합니다.
- **규칙은 코드가 지킵니다.** 층 검사기(core → clients → inputs / collectors / evidence → publish → app → cli, 수집기끼리 import 금지, 네트워크는 `clients/transport.py` 에서만, Anthropic SDK 는 `clients/claude.py` 에서만), 검사기가 위반을 실제로 잡는지 보는 통제군 테스트, 커밋 전 훅 `ruff → mypy → pytest → 크기 가드`.
- **비용에는 안전장치를.** 과금 단계마다 `--dry-run` 이 있습니다. 예산 계량기가 실행당 상한($3)을 넘을 수 있는 LLM 호출을 **부르기 전에** 막습니다.
- **외부 글은 데이터.** README·댓글·웹 글은 신뢰하지 않는 데이터로 감싸고 지시로 다루지 않습니다.

## 시작하기

필요한 것: Python 3.12 이상, 그리고 이 저장소 옆에 [github-ai-star-trend](https://github.com/daehyub71/github-ai-star-trend) 클론(또는 `RADAR_STARTREND_DIR` 지정).

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
git config core.hooksPath scripts/hooks
```

환경 변수 — 필요한 명령에만 넘기고 **커밋하지 않습니다**:

| 변수 | 쓰는 곳 |
|---|---|
| `GITHUB_TOKEN` | 수집기 · 소급 · 해설 근거(읽기 전용 토큰) |
| `STARTREND_ANTHROPIC_API_KEY` | 블로그 초안 · 저장소 해설(star-trend 와 같은 키를 일부러 같이 씀) |
| `STARTREND_TAVILY_API_KEY` | 해설 근거용 웹 검색 |
| `NOTION_TOKEN` | Notion 초안 페이지 |
| `RADAR_STARTREND_DIR` | 선택 — star-trend 데이터 경로 |

```bash
python -m radar contract              # star-trend 입력 계약 점검 (네트워크 없음)
python -m radar weekly --dry-run      # 지난 완료 주의 예상 호출 수
python -m radar weekly                # 신호 수집과 지수 계산
python -m radar site                  # data/site/ 사이트 데이터 (네트워크 없음)
python -m radar blog --dry-run        # TOP 10·관점 노트 초안: 최악 비용만
python -m radar cards --dry-run       # 저장소 해설: 대상·호출 수·비용만
python -m radar images               # 글 차트·저장소 카드를 그리고 해설과 함께 초안에 넣는다 (네트워크·LLM 없음)
```

```bash
python -m pytest            # 기본 게이트: 네트워크·키·비용 없음
python -m pytest -m live    # 실제 API 호출
cd web && npm ci && npm run dev   # 사이트 — ../data/site 와 (있으면) ../.private/site-private 를 읽는다
```

## 저장소 구성

```
radar/      core/ (주 · 정규화 · 지수 · 관점 · 관찰 · 근거 · 차트 데이터 · 저장소 그림 후보) · clients/ (transport · http · claude)
            inputs/ (star-trend 계약) · collectors/ (포크 · 기여 · 패키지 · 언급)
            evidence/ (github · hn · geeknews · web · 그림) · publish/ (초안 · 해설 · 게이트 · notion · 예산 · 차트)
            pipeline.py · backfill.py · site.py · blog.py · cards.py · images.py · cli.py
data/       candidates · signals · index · meta · site (공개, 계산값)
web/        Next.js 사이트(정적 생성)
docs/       SPEC · PLAN · DESIGN · TASKS · MEASURE
scripts/    크기 가드, 실측 스크립트, git 훅
tests/      녹화 응답과 합성 픽스처로 하는 단위 테스트
```

`.work/`(gitignore)는 캐시, `.private/`(gitignore)는 비공개 저장소 클론입니다.

## 데이터 참고

- 백분위는 **그 주 후보 안에서의 상대값**이지 절대 점수가 아닙니다.
- "소급" 표시 주는 나중에 거꾸로 모은 값입니다. 포크 증가와 의존 패키지 수는 과거 값을 얻을 수 없어 그 주에는 비어 있습니다.
- 사용 신호는 PyPI·npm 패키지가 저장소와 일치할 때만 있습니다. 에이전트 스킬·앱처럼 패키지가 없는 저장소가 많습니다.
- AI 판정과 카테고리는 github-ai-star-trend 의 판정(Claude)을 씁니다. 지난 주도 지금의 판정으로 거릅니다.
- 의존 패키지 수는 [ecosyste.ms](https://ecosyste.ms) 데이터(CC BY-SA 4.0)를, 언급은 Hacker News Algolia API 와 GeekNews 목록을 씁니다.
- 이 프로젝트는 GitHub, Anthropic, Tavily, Hacker News, GeekNews, ecosyste.ms, Notion 과 관계가 없습니다.

## 라이선스

아직 정하지 않았습니다.
