import Link from "next/link";

import { AiNotice } from "@/components/AiNotice";
import { BuzzSection, InsightSection, SourcesSection, SummarySection, TrendSection, WhatSection, hasSummary } from "@/components/RepoSections";
import { StackedBar } from "@/components/StackedBar";
import { TrendChart } from "@/components/TrendChart";
import { SIGNALS, SIGNAL_COLOR, SIGNAL_NAME, fmt, int, rankLine, starRankLine, weekRange } from "@/lib/format";
import type { Card, RepoDoc } from "@/lib/types";

// 저장소 화면 (DESIGN §2-2 · §2-2b 시안 v2).
// 해설이 있으면 히어로 · 목차 · AI 안내 · 01~07, 없으면 히어로 · 05 코드 관찰 · 06 만 그린다.

function rawLine(r: RepoDoc, s: (typeof SIGNALS)[number]): string {
  const v = r.latest.raw;
  if (s === "s1") return `이번 주 스타 +${int(v.s1_stars_gain)}`;
  if (s === "s2") return v.s2_fork_delta == null ? `포크 ${int(v.s2_forks)} — 주간 증가 없음` : `포크 +${int(v.s2_fork_delta)} (전체 ${int(v.s2_forks)})`;
  if (s === "s3") return `머지 PR ${int(v.s3_merged_prs)} · 작성자 ${int(v.s3_pr_authors)} · 닫힌 이슈 ${int(v.s3_closed_issues)}`;
  if (s === "s4") return v.s4_packages ? `${v.s4_packages} · 주간 다운로드 ${int(v.s4_downloads)} · 의존 ${int(v.s4_dependents)}` : "PyPI·npm 패키지가 확인되지 않음";
  return `Hacker News 글 ${int(v.s5_hn_stories)} (${int(v.s5_hn_points)}점) · GeekNews 글 ${int(v.s5_gn_topics)} (${int(v.s5_gn_points)}점)`;
}

function Hero({ r, card }: { r: RepoDoc; card: Card | null }) {
  const L = r.latest;
  const rank = rankLine(L);
  const prevIndex = r.trend?.find((t) => t.key === "지수")?.prev;
  return (
    <section className="hero">
      <div className="wrap hero-repo">
        <div className="hero-head grow">
          <div className="chips">
            {r.category ? <span className="chip-d">{r.category}</span> : null}
            {r.language ? <span className="chip-d">{r.language}</span> : null}
            {L.backfilled ? <span className="chip-d">소급</span> : null}
            {card ? <span className="chip-ai">AI 해설 · {card.week} 주</span> : null}
          </div>
          <h1 className="wrapname">{r.full_name}</h1>
          <p>{r.description ?? "저장소 설명이 없습니다."}</p>
          <a href={`https://github.com/${r.full_name}`} className="hero-link">깃허브에서 보기</a>
        </div>
        <div className="stats3">
          <div className="stat">
            <span className="k">종합 순위</span><span className="v">{L.rank}위</span>
            <span className={`d ${rank.tone}`}>{rank.text}</span>
          </div>
          <div className="stat">
            <span className="k">지수</span><span className="v">{fmt(L.index)}</span>
            <span className="d">{prevIndex && prevIndex !== "—" ? `지난주 ${prevIndex}` : "지난주 값 없음"}</span>
          </div>
          <div className="stat">
            <span className="k">스타 순위</span><span className="v">{L.star_rank == null ? "—" : `${L.star_rank}위`}</span>
            <span className="d">{starRankLine(L.star_rank)}</span>
          </div>
        </div>
      </div>
    </section>
  );
}

// 06 신호와 추이 — v1 절 그대로(백분위 막대 · 지수 구성 · 12주 추이)
function SignalsSection({ r, no }: { r: RepoDoc; no: string | null }) {
  const L = r.latest;
  return (
    <section id="signals" aria-labelledby="h-signals" className="grid-sig sec">
      <h2 id="h-signals">{no ? <span className="sec-no" style={{ color: "#1F5BD8" }}>{no} </span> : null}신호와 추이</h2>
      <div className="panel">
        <h3 id="pct">신호별 백분위 — {weekRange(L.week)}</h3>
        {SIGNALS.map((s) => {
          const p = L.pct[s];
          return (
            <div key={s} className="pbar">
              <div className="between"><b>{SIGNAL_NAME[s]}</b><span className="num">{p == null ? "빠짐" : fmt(p)}</span></div>
              <div role="img" aria-label={`${SIGNAL_NAME[s]} ${p == null ? "값 없음" : `백분위 ${fmt(p)}`}`} className="track"><span style={{ width: `${p ?? 0}%`, background: SIGNAL_COLOR[s] }} /></div>
              <span className="muted">{rawLine(r, s)}</span>
            </div>
          );
        })}
      </div>
      <div className="panel">
        <h3 id="contrib">지수 {fmt(L.index)} 는 이렇게 모였다</h3>
        <StackedBar row={L} height={40} />
        <div className="grid-c">
          {SIGNALS.filter((s) => L.pct[s] != null).map((s) => (
            <div key={s} className="kv"><span className="muted">{SIGNAL_NAME[s]}</span><span className="num big">{fmt(L.contrib[s])}</span></div>
          ))}
        </div>
        {L.missing.length ? (
          <p>
            {L.missing.map((m) => SIGNAL_NAME[m]).join("·")} 신호가 이번 주 값이 없어, 남은 신호의 가중치로 다시 나눴습니다. 빠진 신호는 0점이 아니라 계산에서 뺀 것입니다.
          </p>
        ) : null}
      </div>
      <div className="panel full">
        <h3 id="history">주별 추이 — 지수와 신호 기여</h3>
        <TrendChart history={r.history} />
        <p className="muted">* 표시와 옅은 막대는 소급 주입니다. 후보에 들지 않은 주는 빠져 있습니다.</p>
      </div>
    </section>
  );
}

// 해설 기준 주가 숫자의 주와 다를 때 — "마지막 해설: <주>"
function CardWeekNote({ card, week, href }: { card: Card; week: string; href: string | null }) {
  const label = `${card.week} 주`;
  return (
    <p className="card-week" role="status">
      {card.week < week ? "이번 주에는 해설 대상이 아니었습니다. " : null}
      마지막 해설: {href ? <Link href={href}>{label}</Link> : <b>{label}</b>} — 아래 AI 해설은 이 주 기준이고, 숫자(코드 계산)는 {week} 주 값입니다.
    </p>
  );
}

export function RepoView({ repo, card, cardWeekHref = null }: { repo: RepoDoc; card: Card | null; cardWeekHref?: string | null }) {
  const ev: ReadonlySet<string> = new Set(card?.evidence.map((e) => e.id) ?? []);
  const showSummary = card != null && hasSummary(card);
  const showWhat = card != null && card.what.length > 0;
  const toc: [string, string][] = card
    ? [
        ...(showSummary ? [["#summary", "3줄 요약"] as [string, string]] : []),
        ["#trend", "이번 주 동향"],
        ...(showWhat ? [["#what", "무엇인가"] as [string, string]] : []),
        ["#buzz", "화제"],
        ["#insight", "신호 인사이트"],
        ["#signals", "신호와 추이"],
        ["#sources", "근거"],
      ]
    : [];
  return (
    <>
      <Hero r={repo} card={card} />
      {toc.length ? (
        <div className="toc-bar">
          <nav aria-label="이 화면의 절" className="wrap toc">
            {toc.map(([href, label]) => <a key={href} href={href}>{label}</a>)}
          </nav>
        </div>
      ) : null}
      <main className="wrap main repo-main">
        {card ? <AiNotice /> : null}
        {card && card.week !== repo.latest.week ? <CardWeekNote card={card} week={repo.latest.week} href={cardWeekHref} /> : null}
        {card && showSummary ? <SummarySection card={card} ev={ev} /> : null}
        {card ? <TrendSection repo={repo} card={card} ev={ev} /> : null}
        {card && showWhat ? <WhatSection card={card} ev={ev} /> : null}
        {card ? <BuzzSection repo={repo} card={card} ev={ev} /> : null}
        <InsightSection repo={repo} card={card} ev={ev} no={card ? "05" : null} />
        <SignalsSection r={repo} no={card ? "06" : null} />
        {card ? <SourcesSection card={card} /> : null}
      </main>
    </>
  );
}
