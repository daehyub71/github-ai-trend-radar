"""블로그 초안 (SPEC F7·F9, TASKS T5-5·T5-8) — TOP 10 글과 관점 노트.

표·숫자·고정 안내문은 코드가 쓰고, LLM 문단은 게이트를 통과한 것만 넣는다.
걸리거나 빠진 문단은 사유를 적은 자리 표시로 남긴다 — 사람이 검토할 때 보이게.
"""

import re
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


# 글 그림 (F11) — 차트 alt 는 Notion 캡션이 된다. art 는 그림 단계의 charts.json (없으면 그림 자리 없이 쓴다, P7)
CHART_ALT = {
    "c1": "TOP 10 12주 종합 순위 추이",
    "c2": "신호 기여 — 지수를 무엇이 채웠나",
    "c3": "신호 지도 — 관심과 실사용",
    "c4": "12주 트렌드 — 신호 비중과 카테고리",
}


def _chart(art: Mapping[str, Any] | None, key: str) -> list[str]:
    if not art or not (art.get("files") or {}).get(key):
        return []
    return [f"![{CHART_ALT[key]}](charts/{art['files'][key]})", ""]


def _key(full_name: str) -> str:
    return full_name.replace("/", "__")


def _repo_picture(art: Mapping[str, Any] | None, full_name: str) -> list[str]:
    for it in (art or {}).get("intros") or []:
        pic = it.get("picture")
        if it.get("full_name") == full_name and pic and pic.get("file"):
            return [f"![{it.get('caption') or ''}]({pic['file']})", ""]
    return []


def _trend(f: Mapping[str, Any], t: Mapping[str, str], art: Mapping[str, Any] | None) -> list[str]:
    # 예전 사실 묶음(트렌드 관찰 없음)이면 그림 단계가 쓴 같은 관찰 문장을 쓴다
    obs = (f.get("trend") or {}).get("observations") or (art or {}).get("observations") or []
    lines = ["### 트렌드 분석", "", *_chart(art, "c4")]
    lines += [f"- {o}" for o in obs] + ([""] if obs else [])
    return lines + [t["trend"], ""]


# 관점 노트 일러스트 색 (D27) — 유형마다 강조색(관점 카드 차트의 유형 색 계열), 같은 유형 안에서는 바탕 4종을 차례로.
# 유형마다 시작 바탕을 하나씩 밀어 네 섹션의 첫 그림 바탕이 모두 다르다.
# 해설 LLM 은 D24 첫 문장(다크 블루프린트)을 그대로 쓰고, 여기서 그 문장만 바꿔 끼운다(LLM 0).
GROUNDS = (("dark", "deep navy", "#0B1220"), ("light", "light drafting paper", "#F7F8FA"),
           ("dark", "graphite", "#16181D"), ("light", "warm vellum drafting sheet", "#F4EFE3"))
ACCENTS: dict[str, dict[str, tuple[tuple[str, str], tuple[str, str]]]] = {
    "A": {"dark": (("emerald", "#10B981"), ("teal", "#2DD4BF")),
          "light": (("deep emerald", "#047857"), ("slate", "#334155"))},
    "B": {"dark": (("magenta", "#F472B6"), ("amber", "#FBBF24")),
          "light": (("crimson", "#BE185D"), ("burnt orange", "#C2410C"))},
    "C": {"dark": (("cyan", "#22D3EE"), ("blue", "#60A5FA")),
          "light": (("cobalt blue", "#1D4ED8"), ("steel teal", "#0E7490"))},
    "D": {"dark": (("violet", "#A78BFA"), ("coral", "#FB7185")),
          "light": (("deep violet", "#6D28D9"), ("rose", "#BE123C"))},
}
STYLE_SENTENCE = re.compile(r"16:9[^.]*?(?:#0B1220|navy background)[^.]*\.", re.I)


def restyle(prompt: str, angle: str, order: int) -> str:
    """D27 — 다크 블루프린트 첫 문장을 관점 유형 강조색 × 바탕 문장으로 바꾼다. 문장을 못 찾으면 그대로."""
    m = STYLE_SENTENCE.search(prompt)
    if not m or angle not in ACCENTS:
        return prompt
    tone, ground, hexa = GROUNDS[("ABCD".index(angle) + order) % len(GROUNDS)]
    (c1, h1), (c2, h2) = ACCENTS[angle][tone]
    view = "orthographic" if "orthographic" in m.group(0).lower() else "isometric"
    lines = f"thin {c1} ({h1}) and {c2} ({h2}) line art, {view} engineering-drawing precision."
    if tone == "dark":
        new = f"16:9 dark technical schematic on a {ground} background ({hexa}) with a faint engineering grid, {lines}"
    else:
        new = f"16:9 precise engineering drawing on {ground} ({hexa}) with a faint gray engineering grid, {lines}"
    return prompt[:m.start()] + new + prompt[m.end():]


def _illustration(card: Mapping[str, Any], style: tuple[str, int] | None = None) -> list[str]:
    """R2 — 사람이 이미지 AI 로 만들 프롬프트. 이미 만든 일러스트가 있으면 뺀다. style = (관점 유형, 유형 안 순번)."""
    ill = card.get("illustration")
    if not ill or (card.get("picture") or {}).get("kind") == "illustration":
        return []
    prompt = restyle(ill["prompt"], *style) if style else ill["prompt"]
    labels = " · ".join(ill.get("labels") or [])
    return [f"> 🎨 일러스트 프롬프트 — {ill.get('teach') or ''}".rstrip(" —"),
            f"> 이미지 AI 로 만들어 `gen/{_key(card['full_name'])}.png` 로 두면 카드와 글에 들어갑니다."
            + (f" 얹을 한글 라벨: {labels}" if labels else ""),
            ">", f"> {prompt}", ""]


def _cover(cover: str | None) -> list[str]:
    """대표 이미지 (D25) — 사람이 만든 blog/gen/cover*.* 가 있으면 제목 바로 아래."""
    return [f"![대표 이미지]({cover})", ""] if cover else []


def _tag(c: Mapping[str, Any]) -> str:
    return " (추정)" if c.get("basis") == "추정" else ""


UNKNOWN_MARK = "확인이 필요"  # 초안 LLM 이 설명·토픽이 비었을 때 쓰는 문장 — 해설이 있으면 뺀다 (D25 보강)


def _drop_unknown(text: str) -> str:
    """'…저장소에서 확인이 필요합니다' 같은 문장을 뺀다. 해설이 그 자리를 채울 때만 부른다."""
    keep = [x for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x and UNKNOWN_MARK not in x]
    return " ".join(keep)


def _has_what(note: Mapping[str, Any] | None) -> bool:
    head = ((note or {}).get("summary") or {}).get("what") or {}
    return bool(head.get("text")) or any(w.get("text") for w in (note or {}).get("what") or [])


def _what(note: Mapping[str, Any] | None, fallback: str) -> list[str]:
    """무엇인가 (D25) — 그 주 저장소 해설(F10, README·웹 근거·게이트 통과)이 있으면 그것을,
    없으면 초안 LLM 문단(설명·토픽·언어 근거)을 쓴다. 해설에 요약 문장이 없으면 초안 문단에서
    "확인이 필요" 문장을 뺀 나머지를 첫 줄로 쓰고 해설 항목을 붙인다."""
    head = ((note or {}).get("summary") or {}).get("what") or {}
    items = [w for w in (note or {}).get("what") or [] if w.get("text")]
    if not head.get("text") and not items:
        return [f"**무엇인가** {fallback}", ""] if fallback else []
    first = f"{_tag(head)} {head['text']}" if head.get("text") else (f" {_drop_unknown(fallback)}".rstrip())
    lines = [f"**무엇인가**{first}", ""]
    lines += [f"- **{w['label']}**{_tag(w)} {w['text']}" for w in items]
    return lines + ([""] if items else [])


def post_markdown(f: Mapping[str, Any], t: Mapping[str, str], art: Mapping[str, Any] | None = None, *,
                  notes: Mapping[str, Mapping[str, Any]] | None = None, cover: str | None = None) -> str:
    """TOP 10 글 (F7). t 는 gate_texts 를 거친 글, art 는 그림 단계 결과(F11 — 없으면 그림 없이),
    notes 는 그 주 저장소 해설(저장소 이름 → 카드), cover 는 대표 이미지 경로(blog/ 기준)."""
    lines = [
        f"# 📡 {f['series']} {f['issue']}회 📡 {t['title:1']}", "",
        *_cover(cover),
        f"> 제목 후보: {t['title:2']} / {t['title:3']}", "",
        t["lead"], "",
        f"***{f['series']} {f['issue']}회 정보***", "",
        "⭐ 이 글의 내용 : 이번 주 흐름 · 종합 TOP 10(지수와 신호 기여) · 트렌드 분석 · TOP 10 저장소(무엇인가 · 어떤 신호로 떴나)"
        " · 숫자를 읽을 때 주의할 점 · 한 장 요약", "",
        f"⭐ 집계 기간 : {_period(f)}", "",
        f"⭐ 종합 지수 : 다섯 신호의 후보 내 순위 백분위를 가중 평균({_weights(f)}, 가중치 v{f['weights_version']})"
        " · 값이 없는 신호는 빼고 남은 가중치로 다시 나눕니다", "",
        f"⭐ 데이터 기준 : 그 주 AI 저장소 스타 증가 상위 {f['candidates']}개 후보 · AI 판정과 스타는 github-ai-star-trend"
        " 공개 데이터 · 포크·PR·이슈는 GitHub API · 다운로드는 pypistats·npm · 의존 수는 ecosyste.ms"
        " · 언급은 Hacker News·GeekNews", "",
        "⭐ 쓰는 방식 : 숫자는 코드가, 글 초안은 AI(Claude)가 쓰고 사람이 검토합니다", "",
        f"⭐ 데이터 저장소 : {DATA_REPO}", "",
        f"### 이번 주 흐름 — {t['flow_title']}", "", t["flow"], "", *_chart(art, "c1"),
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
    lines += _chart(art, "c2")
    if f["dropped"]:
        lines += ["### 지난주 TOP 10에서 빠진 저장소", ""]
        for d in f["dropped"]:
            now = "후보 밖" if d["now_rank"] is None else f"{d['now_rank']}위"
            lines.append(f"- {d['repo']} — 지난주 {d['prev_rank']}위 → 이번 주 {now}")
        lines.append("")
    lines += _trend(f, t, art)
    for r in f["top10"]:
        lines += [f"### {r['rank']}위 {r['repo']} — 지수 {r['index']:.1f} ({_move(r)})", "",
                  *_repo_picture(art, r["repo"]),
                  f"신호 기여: {_contrib_line(r)}", "",
                  *_what((notes or {}).get(r["repo"]), t["what:" + r["repo"]]),
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


def angles_markdown(f: Mapping[str, Any], t: Mapping[str, str], art: Mapping[str, Any] | None = None, *,
                    notes: Mapping[str, Mapping[str, Any]] | None = None, cover: str | None = None) -> str:
    """관점 노트 (F9). art 가 있으면 신호 지도(C3)·관점 카드(R1)·일러스트 프롬프트(R2)를 넣는다.
    그 주 해설(notes)이 있는 저장소는 무엇인가를 넣고, 관점 문단의 "확인이 필요" 문장은 뺀다 (D25 보강)."""
    rules = f["rules"]["angles"]
    cards = {c["full_name"]: c for c in (art or {}).get("cards") or []}
    lines = [f"# 📡 {f['series']} 관점 노트 📡 {_period(f)}", "", *_cover(cover), t["angle_intro"], "",
             *_chart(art, "c3")]
    for key in ("A", "B", "C", "D"):
        a = f["angles"][key]
        lines += [f"### {key}. {a['name']}", "", ANGLE_RULE_TEXT[key].format(**rules) if rules else "", ""]
        if a["status"] == "insufficient":
            lines += ["이력이 모자라 이번 주는 비워 둡니다.", ""]
            continue
        if not a["items"]:
            lines += ["이번 주에는 조건을 만족하는 저장소가 없습니다.", ""]
            continue
        for order, it in enumerate(a["items"]):
            card = cards.get(it["repo"])
            lines += [f"#### {it['repo']} — 종합 {it['rank']}위 · 지수 {it['index']:.1f}", ""]
            if card:
                lines += [f"![관점 카드 — {it['repo']}](charts/{card['file']})", ""]
            note = (notes or {}).get(it["repo"])
            text = t["angle:" + it["repo"]]
            if _has_what(note):
                lines += _what(note, "")
                text = _drop_unknown(text)
            lines += [f"근거: {_evidence(key, it['evidence'])}", "", text, ""]
            if card:
                lines += _illustration(card, (key, order))
    lines += ["### 주의할 점", "",
              f"- 유형은 코드가 정한 규칙으로 고릅니다(유형마다 최대 5개, 한 저장소는 한 유형에만). 백분위는 후보 {f['candidates']}개 안의 상대값입니다.",
              "- 반짝 관심 유형은 판단이 아니라 관측입니다. 사용·기여 신호가 늦게 나타나는 저장소도 많습니다.", "",
              "### 한 장 요약", "", t["angle_summary"], ""]
    return "\n".join(lines)
