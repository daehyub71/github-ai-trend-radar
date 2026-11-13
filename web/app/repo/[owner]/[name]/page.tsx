import { notFound } from "next/navigation";

import { SiteFooter, SiteHeader } from "@/components/Chrome";
import { StackedBar } from "@/components/StackedBar";
import { TrendChart } from "@/components/TrendChart";
import { findRepo, loadRepos } from "@/lib/data";
import { SIGNALS, SIGNAL_COLOR, SIGNAL_NAME, fmt, int, weekRange } from "@/lib/format";
import type { RepoDoc } from "@/lib/types";

export const dynamicParams = false;

export function generateStaticParams() {
  return loadRepos().map((r) => {
    const [owner, name] = r.full_name.split("/");
    return { owner, name };
  });
}

function rawLine(r: RepoDoc, s: (typeof SIGNALS)[number]): string {
  const v = r.latest.raw;
  if (s === "s1") return `이번 주 스타 +${int(v.s1_stars_gain)}`;
  if (s === "s2") return v.s2_fork_delta == null ? `포크 ${int(v.s2_forks)} — 주간 증가 없음` : `포크 +${int(v.s2_fork_delta)} (전체 ${int(v.s2_forks)})`;
  if (s === "s3") return `머지 PR ${int(v.s3_merged_prs)} · 작성자 ${int(v.s3_pr_authors)} · 닫힌 이슈 ${int(v.s3_closed_issues)}`;
  if (s === "s4") return v.s4_packages ? `${v.s4_packages} · 주간 다운로드 ${int(v.s4_downloads)} · 의존 ${int(v.s4_dependents)}` : "PyPI·npm 패키지가 확인되지 않음";
  return `Hacker News 글 ${int(v.s5_hn_stories)} (${int(v.s5_hn_points)}점) · GeekNews 글 ${int(v.s5_gn_topics)} (${int(v.s5_gn_points)}점)`;
}

export default async function RepoPage({ params }: { params: Promise<{ owner: string; name: string }> }) {
  const { owner, name } = await params;
  const r = findRepo(decodeURIComponent(owner), decodeURIComponent(name));
  if (!r) notFound();
  const L = r.latest;
  return (
    <>
      <SiteHeader active="repo" />
      <section className="hero">
        <div className="wrap hero-repo">
          <div className="hero-head grow">
            <div className="chips">
              {r.category ? <span className="chip-d">{r.category}</span> : null}
              {r.language ? <span className="chip-d">{r.language}</span> : null}
              {L.backfilled ? <span className="chip-d">소급</span> : null}
            </div>
            <h1 className="wrapname">{r.full_name}</h1>
            <p>{r.description ?? "저장소 설명이 없습니다."}</p>
            <a href={`https://github.com/${r.full_name}`} className="hero-link">깃허브에서 보기</a>
          </div>
          <div className="stats3">
            <div className="stat"><span className="k">종합 순위</span><span className="v">{L.rank}위</span></div>
            <div className="stat"><span className="k">지수</span><span className="v">{fmt(L.index)}</span></div>
            <div className="stat"><span className="k">스타 순위</span><span className="v">{L.star_rank == null ? "—" : `${L.star_rank}위`}</span></div>
          </div>
        </div>
      </section>
      <main className="wrap main two">
        <section aria-labelledby="pct" className="panel">
          <h2 id="pct">신호별 백분위 — {weekRange(L.week)}</h2>
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
        </section>
        <section aria-labelledby="contrib" className="panel">
          <h2 id="contrib">지수 {fmt(L.index)} 는 이렇게 모였다</h2>
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
        </section>
        <section aria-labelledby="trend" className="panel full">
          <h2 id="trend">주별 추이 — 지수와 신호 기여</h2>
          <TrendChart history={r.history} />
          <p className="muted">* 표시와 옅은 막대는 소급 주입니다. 후보에 들지 않은 주는 빠져 있습니다.</p>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
