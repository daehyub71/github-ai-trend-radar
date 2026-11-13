"""블로그 초안 (SPEC F7·F9, TASKS T5-5·T5-8) — TOP 10 글과 관점 노트.

표·숫자·고정 안내문은 코드가 쓰고, LLM 문단은 게이트를 통과한 것만 넣는다.
걸리거나 빠진 문단은 사유를 적은 자리 표시로 남긴다 — 사람이 검토할 때 보이게.
"""

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from radar.publish.facts import SIGNAL_NAMES
from radar.publish.gate import allowed_numbers, check

DATA_REPO = "https://github.com/daehyub71/github-ai-trend-radar"
WEEKDAYS = "월화수목금토일"
ANGLE_RULE_TEXT = {
    "A": "스타 백분위는 {a_star_max:g} 아래인데 사용·기여(기여·사용, 사용이 없으면 포크·기여) 평균 백분위가 "
         "{a_use_min:g} 이상인 저장소입니다. 화제는 적지만 실제로 쓰이고 관리되는 도구를 찾습니다.",
    "B": "스타나 언급 백분위가 {b_attention_min:g} 이상인데 포크·기여·사용 평균 백분위가 {b_use_max:g} 이하인 "
         "저장소입니다. 관심은 큰데 사용·기여 신호는 아직 보이지 않는 곳입니다.",
    "C": "종합 지수가 {c_rises}주 연속 오른 저장소입니다. 한 주 반짝이 아니라 자리를 잡아 가는 중인 곳입니다.",
    "D": "{lookback}주 전보다 관심(스타·언급) 비중이 줄고 사용·기여(기여·사용) 비중이 {d_shift_min:g}%p 이상 "
         "늘어난 저장소입니다. 데모에서 실제 도구로 넘어가는 순간을 찾습니다.",
}


def gate_texts(texts: Mapping[str, str], wanted: Sequence[str],
               facts: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, list[str]]]:
    """(쓸 글, 걸린 사유). 빠졌거나 걸린 target 은 자리 표시로 바꾼다."""
    allowed = allowed_numbers(facts)
    out: dict[str, str] = {}
    report: dict[str, list[str]] = {}
    for t in wanted:
        text = texts.get(t, "").strip()
        problems = ["빠짐"] if not text else check(text, allowed)
        if problems:
            report[t] = problems
            out[t] = f"〔초안 없음 — {', '.join(problems)}. 직접 써 주세요〕"
        else:
            out[t] = text
    return out, report


def _kdate(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.year}년 {d.month}월 {d.day}일({WEEKDAYS[d.weekday()]})"


def _period(f: Mapping[str, Any]) -> str:
    end = date.fromisoformat(f["week_end"])
    return f"{_kdate(f['week'])} ~ {end.month}월 {end.day}일({WEEKDAYS[end.weekday()]}), UTC 기준"


def _v(x: float | None) -> str:
    return "—" if x is None else f"{x:.1f}"


def _weights(f: Mapping[str, Any]) -> str:
    w = f["weights"]
    return " · ".join(f"{SIGNAL_NAMES[k]} {w[k]}" for k in SIGNAL_NAMES)


def _contrib_line(r: Mapping[str, Any]) -> str:
    parts = []
    for k, name in SIGNAL_NAMES.items():
        parts.append(f"{name} —" if r["pct"][k] is None else f"{name} {r['contrib'][k]:.1f}")
    return " · ".join(parts)


def _move(r: Mapping[str, Any]) -> str:
    return "새로 진입" if r["prev_rank"] is None else f"지난주 {r['prev_rank']}위"


def post_markdown(f: Mapping[str, Any], t: Mapping[str, str]) -> str:
    """TOP 10 글 (F7). t 는 gate_texts 를 거친 글."""
    lines = [
        f"# 📡 {f['series']} {f['issue']}회 📡 {t['title:1']}", "",
        f"> 제목 후보: {t['title:2']} / {t['title:3']}", "",
        t["lead"], "",
        f"***{f['series']} {f['issue']}회 정보***", "",
        "⭐ 이 글의 내용 : 이번 주 흐름 · 종합 TOP 10(지수와 신호 기여) · TOP 10 저장소(무엇인가 · 어떤 신호로 떴나)"
        " · 숫자를 읽을 때 주의할 점 · 한 장 요약", "",
        f"⭐ 집계 기간 : {_period(f)}", "",
        f"⭐ 종합 지수 : 다섯 신호의 후보 내 순위 백분위를 가중 평균({_weights(f)}, 가중치 v{f['weights_version']})"
        " · 값이 없는 신호는 빼고 남은 가중치로 다시 나눕니다", "",
        f"⭐ 데이터 기준 : 그 주 AI 저장소 스타 증가 상위 {f['candidates']}개 후보 · AI 판정과 스타는 github-ai-star-trend"
        " 공개 데이터 · 포크·PR·이슈는 GitHub API · 다운로드는 pypistats·npm · 의존 수는 ecosyste.ms"
        " · 언급은 Hacker News·GeekNews", "",
        "⭐ 쓰는 방식 : 숫자는 코드가, 글 초안은 AI(Claude)가 쓰고 사람이 검토합니다", "",
        f"⭐ 데이터 저장소 : {DATA_REPO}", "",
        f"### 이번 주 흐름 — {t['flow_title']}", "", t["flow"], "",
        "### 종합 TOP 10 — 지수와 신호 기여", "",
        "| 순위 | 저장소 | 지수 | 변동 | 스타 순위 | 스타 | 포크 | 기여 | 사용 | 언급 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in f["top10"]:
        cells = [_v(None if r["pct"][k] is None else r["contrib"][k]) for k in SIGNAL_NAMES]
        star = "—" if r["star_rank"] is None else f"{r['star_rank']}위"
        lines.append(f"| {r['rank']} | {r['repo']} | {r['index']:.1f} | {_move(r)} | {star} | " + " | ".join(cells)
                     + " |")
    lines += ["", "표의 신호 칸은 지수에 더해진 기여분입니다(합이 지수). — 는 이번 주 값이 없어 빠진 신호입니다.", ""]
    if f["dropped"]:
        lines += ["### 지난주 TOP 10에서 빠진 저장소", ""]
        for d in f["dropped"]:
            now = "후보 밖" if d["now_rank"] is None else f"{d['now_rank']}위"
            lines.append(f"- {d['repo']} — 지난주 {d['prev_rank']}위 → 이번 주 {now}")
        lines.append("")
    for r in f["top10"]:
        lines += [f"### {r['rank']}위 {r['repo']} — 지수 {r['index']:.1f} ({_move(r)})", "",
                  f"신호 기여: {_contrib_line(r)}", "",
                  f"**무엇인가** {t['what:' + r['repo']]}", "",
                  f"**어떤 신호로 떴나** {t['why:' + r['repo']]}", ""]
    lines += [
        "### 숫자를 읽을 때 주의할 점", "",
        f"- 백분위는 그 주 후보 {f['candidates']}개 안에서의 상대 위치입니다. 다른 주와 지수 값을 그대로 비교하기보다 순위로 봐 주세요.",
        "- 포크 증가는 매주 쌓는 스냅샷 두 개가 있어야 나옵니다. 사용 신호는 PyPI·npm 패키지로 확인된 저장소에만 있습니다.",
        "- AI 저장소 판정과 카테고리는 github-ai-star-trend 의 판정(Claude)을 그대로 씁니다.", "",
        t["caveats"], "",
        "### 한 장 요약", "", t["summary"], "",
    ]
    return "\n".join(lines)


def _evidence(key: str, ev: Mapping[str, Any]) -> str:
    if key == "A":
        return f"스타 백분위 {ev['s1']:.1f} · 사용·기여 평균 {ev['use']:.1f}({ev['use_basis']})"
    if key == "B":
        att = " · ".join(f"{n} {ev[k]:.1f}" for k, n in (("s1", "스타"), ("s5", "언급")) if ev.get(k) is not None)
        return f"관심 백분위 {att} · 포크·기여·사용 평균 {ev['use']:.1f}"
    if key == "C":
        return "지수 추이 " + " → ".join(_v(v) for v in ev["index"])
    a, u = ev["attention_share"], ev["use_share"]
    return f"관심 비중 {a[0]:.1f}% → {a[1]:.1f}% · 사용·기여 비중 {u[0]:.1f}% → {u[1]:.1f}%"


def angles_markdown(f: Mapping[str, Any], t: Mapping[str, str]) -> str:
    """관점 노트 (F9)."""
    rules = f["rules"]["angles"]
    lines = [f"# 📡 {f['series']} 관점 노트 📡 {_period(f)}", "", t["angle_intro"], ""]
    for key in ("A", "B", "C", "D"):
        a = f["angles"][key]
        lines += [f"### {key}. {a['name']}", "", ANGLE_RULE_TEXT[key].format(**rules) if rules else "", ""]
        if a["status"] == "insufficient":
            lines += ["이력이 모자라 이번 주는 비워 둡니다.", ""]
            continue
        if not a["items"]:
            lines += ["이번 주에는 조건을 만족하는 저장소가 없습니다.", ""]
            continue
        for it in a["items"]:
            lines += [f"#### {it['repo']} — 종합 {it['rank']}위 · 지수 {it['index']:.1f}", "",
                      f"근거: {_evidence(key, it['evidence'])}", "", t["angle:" + it["repo"]], ""]
    lines += ["### 주의할 점", "",
              f"- 유형은 코드가 정한 규칙으로 고릅니다(유형마다 최대 5개, 한 저장소는 한 유형에만). 백분위는 후보 {f['candidates']}개 안의 상대값입니다.",
              "- 반짝 관심 유형은 판단이 아니라 관측입니다. 사용·기여 신호가 늦게 나타나는 저장소도 많습니다.", "",
              "### 한 장 요약", "", t["angle_summary"], ""]
    return "\n".join(lines)
