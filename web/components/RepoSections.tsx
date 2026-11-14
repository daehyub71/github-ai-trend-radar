// 저장소 화면 v2 절 01~05·07 (DESIGN §2-2b). 보라(AI 해설)와 남색(코드 계산) 표시로 출처를 나눈다.
// 해설 글은 모두 글자로만 그린다 — HTML 로 넣지 않고, 링크는 http·https 만(ExtLink).
import { ClaimBasis, ClaimBlock } from "@/components/ClaimBasis";
import { ExtLink } from "@/components/ExtLink";
import { NATURE_STYLE, modelLabel } from "@/lib/card";
import { SIGNAL_COLOR, int, shortDate, weekSpan } from "@/lib/format";
import type { Card, Claim, Insight, Mentions, RepoDoc } from "@/lib/types";

type Ev = ReadonlySet<string>;

function SecHead({ no, id, title, color, ai = false }: { no: string | null; id: string; title: string; color: string; ai?: boolean }) {
  return (
    <div className="sec-head">
      {no ? <span className="sec-no" style={{ color }}>{no}</span> : null}
      <h2 id={id}>{title}</h2>
      {ai ? <span className="tag-ai">AI 해설</span> : null}
    </div>
  );
}

const SUMMARY_ROWS = [
  ["what", "무엇인지"],
  ["why_now", "이번 주 왜 올랐나"],
  ["watch", "무엇을 볼까"],
] as const;

export function hasSummary(card: Card): boolean {
  return SUMMARY_ROWS.some(([k]) => card.summary[k] != null);
}

// 01 3줄 요약 — 게이트가 뺀 줄(null)은 그리지 않는다
export function SummarySection({ card, ev }: { card: Card; ev: Ev }) {
  return (
    <section id="summary" aria-labelledby="h-summary" className="panel sec ai-top">
      <SecHead no="01" id="h-summary" title="3줄 요약" color="#6D28D9" ai />
      {SUMMARY_ROWS.map(([k, label]) => {
        const c = card.summary[k];
        return c ? (
          <div key={k} className="claim-row">
            <b>{label}</b>
            <ClaimBlock claim={c} evidence={ev} large />
          </div>
        ) : null;
      })}
    </section>
  );
}

// 02 이번 주 동향 — 왼쪽 코드 표(공개 trend) · 오른쪽 AI 항목
export function TrendSection({ repo, card, ev }: { repo: RepoDoc; card: Card; ev: Ev }) {
  const rows = repo.trend ?? [];
  const releases = [...card.releases].sort((a, b) => (a.date ?? "9999").localeCompare(b.date ?? "9999"));
  return (
    <section id="trend" aria-labelledby="h-trend" className="panel sec">
      <SecHead no="02" id="h-trend" title="이번 주 동향" color="#1F5BD8" />
      <div className="split">
        <div className="col">
          <span className="tag-code">코드 계산 — {weekSpan(repo.latest.week)}</span>
          {rows.length ? (
            <div className="scroll">
              <table className="table compact">
                <thead>
                  <tr>
                    <th scope="col">항목</th>
                    <th scope="col" className="r">지난주</th>
                    <th scope="col" className="r">이번 주</th>
                    <th scope="col" className="r">지난 4주 평균</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((t) => (
                    <tr key={t.key}>
                      <th scope="row" className="rowh">{t.key}</th>
                      <td className="r num soft">{t.prev}</td>
                      <td className="r num"><b>{t.now}</b></td>
                      <td className="r num soft">{t.avg}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">이번 주 값이 없습니다.</p>
          )}
          {releases.length ? (
            <p className="rel">
              이번 주 릴리스:{" "}
              {releases.map((r, i) => (
                <span key={`${r.tag}-${i}`}>
                  {i > 0 ? " · " : null}
                  <strong><ExtLink href={r.url}>{r.tag}</ExtLink></strong>
                  {r.date ? ` (${shortDate(r.date)})` : null}
                </span>
              ))}
            </p>
          ) : null}
        </div>
        {card.trend_notes.length ? (
          <div className="col">
            <span className="tag-ai">AI 해설 — 무엇이 달라졌나</span>
            <ul className="notes">
              {card.trend_notes.map((n, i) => (
                <li key={i}>
                  <span className="claim-text">{n.text}</span>
                  <ClaimBasis claim={n} evidence={ev} />
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  );
}

// 03 무엇인가 · 어떤 역할을 하나
export function WhatSection({ card, ev }: { card: Card; ev: Ev }) {
  return (
    <section id="what" aria-labelledby="h-what" className="panel sec">
      <SecHead no="03" id="h-what" title="무엇인가 · 어떤 역할을 하나" color="#6D28D9" ai />
      {card.what.map((w, i) => (
        <div key={`${w.label}-${i}`} className="claim-row">
          <b>{w.label}</b>
          <ClaimBlock claim={w} evidence={ev} />
        </div>
      ))}
    </section>
  );
}

function count(stories: number, points: number): string {
  return stories === 0 ? "0건" : `${int(stories)}건 · ${int(points)}점`;
}

function MentionCounts({ m }: { m: Mentions | undefined }) {
  if (!m) return <p className="muted">이번 주 언급 값이 없습니다.</p>;
  return (
    <div className="counts">
      <div className="count"><span className="k">이번 주 Hacker News</span><span className="v">{count(m.week.hn_stories, m.week.hn_points)}</span></div>
      <div className="count"><span className="k">이번 주 GeekNews</span><span className="v">{count(m.week.gn_topics, m.week.gn_points)}</span></div>
      <div className="count"><span className="k">{m.window.weeks}주 Hacker News</span><span className="v">{count(m.window.hn_stories, m.window.hn_points)}</span></div>
    </div>
  );
}

function siteClass(site: string): string {
  return site === "HN" ? "site hn" : site === "GeekNews" ? "site gn" : "site";
}

function BuzzRow({ label, claim, ev }: { label: string; claim: Claim; ev: Ev }) {
  return (
    <>
      <b>{label}</b>
      <ClaimBlock claim={claim} evidence={ev} />
    </>
  );
}

// 04 어디서 어떻게 화제가 됐나 — 숫자 상자(공개 mentions) · 글 목록 · I5 · AI 계기/반응/읽는 법
export function BuzzSection({ repo, card, ev }: { repo: RepoDoc; card: Card; ev: Ev }) {
  const { posts, nature, trigger, reactions, reading } = card.buzz;
  const i5 = (repo.insights ?? []).find((i) => i.id === "I5");
  const hasAi = nature != null || trigger != null || reactions.length > 0 || reading != null;
  return (
    <section id="buzz" aria-labelledby="h-buzz" className="panel sec">
      <SecHead no="04" id="h-buzz" title="어디서 어떻게 화제가 됐나" color="#DB2777" />
      <MentionCounts m={repo.mentions} />
      {posts.length ? (
        <div className="col">
          <span className="tag-code">코드 계산 — 글 목록</span>
          <div className="scroll">
            <table className="table posts">
              <thead>
                <tr>
                  <th scope="col">곳</th>
                  <th scope="col">글</th>
                  <th scope="col" className="r">점수</th>
                  <th scope="col" className="r">댓글</th>
                  <th scope="col">날짜</th>
                  <th scope="col">글이 가리킨 곳</th>
                </tr>
              </thead>
              <tbody>
                {posts.map((p, i) => (
                  <tr key={`${p.url}-${i}`}>
                    <td><span className={siteClass(p.site)}>{p.site}</span></td>
                    <td><ExtLink href={p.url}>{p.title}</ExtLink></td>
                    <td className="r num"><b>{int(p.points)}</b></td>
                    <td className="r num">{int(p.comments)}</td>
                    <td className="soft">{shortDate(p.date)}</td>
                    <td className="soft">{p.target ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      {posts.length && i5 ? (
        <div className="obs">
          <span className="obs-k">{i5.id} · {i5.title} (코드)</span>
          <span className="obs-v">{i5.big}</span>
          <span className="obs-t">{i5.text}</span>
        </div>
      ) : null}
      {hasAi ? (
        <div className="buzz-ai">
          <div className="tags">
            <span className="tag-ai">AI 해설</span>
            {nature ? <span className="nature" style={NATURE_STYLE[nature]}>화제의 성격: {nature}</span> : null}
          </div>
          {trigger || reactions.length || reading ? (
            <div className="buzz-grid">
              {trigger ? <BuzzRow label="계기" claim={trigger} ev={ev} /> : null}
              {reactions.length ? (
                <>
                  <b>반응의 요지</b>
                  <ul className="reactions">
                    {reactions.map((r, i) => (
                      <li key={i}>
                        {r.text} <ClaimBasis claim={r} evidence={ev} />
                      </li>
                    ))}
                  </ul>
                </>
              ) : null}
              {reading ? <BuzzRow label="읽는 법" claim={reading} ev={ev} /> : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function insightColor(i: Insight): string {
  return i.signal === "index" ? "#1F5BD8" : (SIGNAL_COLOR[i.signal] ?? "#9CA3AF");
}

// 05 신호 인사이트 — 코드 관찰(모든 저장소) + AI 지켜볼 점(해설이 있을 때)
export function InsightSection({ repo, card, ev, no }: { repo: RepoDoc; card: Card | null; ev: Ev; no: string | null }) {
  const ins = repo.insights ?? [];
  return (
    <section id="insight" aria-labelledby="h-insight" className="panel sec">
      <SecHead no={no} id="h-insight" title="신호 인사이트 — 포크·다운로드·언급으로 볼 것" color="#059669" />
      <span className="tag-code">코드 관찰 — 규칙 v{repo.insights_version ?? 1}, 모든 저장소에 나온다</span>
      {ins.length ? (
        <div className="ins-grid">
          {ins.map((i) => (
            <div key={i.id} className="ins" data-insight={i.id}>
              <div className="ins-head"><i style={{ background: insightColor(i) }} />{i.id} · {i.title}</div>
              <span className="ins-big">{i.big}</span>
              <p>{i.text}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted">이번 주에는 관찰할 값이 없습니다.</p>
      )}
      {card && card.watch.length ? (
        <div className="watch">
          <div className="sec-head"><h3>지켜볼 점</h3><span className="tag-ai">AI 해설</span></div>
          <ol>
            {card.watch.map((w, i) => (
              <li key={i}>
                {w.text} <ClaimBasis claim={w} evidence={ev} />
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}

// 07 근거 — 번호 · 제목 · 사이트 · 날짜, 지난 해설 주, 해설 기준
export function SourcesSection({ card }: { card: Card }) {
  const past = card.history.filter((h) => h.week !== card.week).sort((a, b) => b.week.localeCompare(a.week));
  return (
    <section id="sources" aria-labelledby="h-sources" className="panel sec">
      <SecHead no="07" id="h-sources" title="근거" color="#4B5563" />
      {card.evidence.length ? (
        <div className="scroll">
          <table className="table ev">
            <thead>
              <tr>
                <th scope="col" className="evn">번호</th>
                <th scope="col">제목</th>
                <th scope="col">사이트</th>
                <th scope="col">날짜</th>
              </tr>
            </thead>
            <tbody>
              {card.evidence.map((e) => (
                <tr key={e.id} id={`ev-${e.id}`} className="ev-row">
                  <td className="num"><b>{e.id}</b></td>
                  <td><ExtLink href={e.url}>{e.title}</ExtLink></td>
                  <td className="soft">{e.site}</td>
                  <td className="soft">{e.date ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {past.length ? (
        <div className="col">
          <span className="muted">지난 해설</span>
          <ul className="ul">
            {past.map((h) => (
              <li key={h.week}><b>{h.week} 주</b>{h.why_now ? ` — ${h.why_now}` : null}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="muted">지난 해설: 없음(첫 해설).</p>
      )}
      <p className="muted">
        해설 기준: {modelLabel(card.model)} · 게이트에서 빠진 항목 {card.gate.excluded}개.
      </p>
    </section>
  );
}
