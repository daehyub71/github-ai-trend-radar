import Link from "next/link";

import { StackedBar } from "@/components/StackedBar";
import { ANGLE_NAME, ANGLE_RULE, SIGNALS, SIGNAL_COLOR, SIGNAL_NAME, SIGNAL_WHAT, fmt, move, repoPath, weekRange } from "@/lib/format";
import type { AngleItem, WeekDoc, WeekListItem } from "@/lib/types";

function evidence(key: string, ev: Record<string, unknown>): string {
  const n = (k: string) => (typeof ev[k] === "number" ? (ev[k] as number).toFixed(1) : "—");
  if (key === "A") return `스타 ${n("s1")} · 사용·기여 ${n("use")}`;
  if (key === "B") return `스타 ${n("s1")} · 언급 ${n("s5")} · 사용·기여 ${n("use")}`;
  if (key === "C") return `지수 ${((ev.index as (number | null)[]) ?? []).map((v) => fmt(v)).join(" → ")}`;
  const a = (ev.attention_share as number[]) ?? [];
  const u = (ev.use_share as number[]) ?? [];
  return `관심 ${fmt(a[0])}% → ${fmt(a[1])}% · 사용·기여 ${fmt(u[0])}% → ${fmt(u[1])}%`;
}

export function WeekView({ doc, weeks }: { doc: WeekDoc; weeks: WeekListItem[] }) {
  const w = doc.weights;
  return (
    <>
      <section className="hero">
        <div className="wrap hero-in">
          <div className="hero-head">
            <span className="eyebrow">
              {weekRange(doc.week)} · UTC{doc.issue ? ` · ${doc.issue}회` : ""}
              {doc.backfilled ? " · 소급" : ""}
            </span>
            <h1>스타 하나가 아니라 다섯 신호로 본 이번 주 AI 저장소</h1>
            <p>
              스타 증가 상위 {doc.stats.candidates}개 후보를 스타·포크·기여·사용·언급으로 다시 매겼습니다. 스타 TOP 10 가운데 종합 TOP
              10에 남은 저장소는 {doc.stats.star_top_in_index_top}곳입니다.
            </p>
          </div>
          <div className="stats">
            <div className="stat"><span className="k">후보 저장소</span><span className="v">{doc.stats.candidates}</span><span className="d">그 주 AI 저장소 스타 증가 상위</span></div>
            <div className="stat"><span className="k">스타 TOP 10 중 지수 TOP 10</span><span className="v">{doc.stats.star_top_in_index_top}<small> / 10</small></span><span className="d">나머지 자리는 다른 신호가 바꿨다</span></div>
            <div className="stat"><span className="k">패키지가 확인된 후보</span><span className="v">{doc.stats.with_packages}</span><span className="d">PyPI·npm — 사용 신호가 있는 곳</span></div>
          </div>
          <div className="legend">
            <span className="muted-l">가중치 v{doc.weights_version}</span>
            {SIGNALS.map((s) => (
              <span key={s} className="chip-d"><i style={{ background: SIGNAL_COLOR[s] }} />{SIGNAL_NAME[s]} {w[s]}</span>
            ))}
          </div>
          <nav aria-label="다른 주" className="weeks">
            {weeks.slice(0, 13).map((x) => (
              <Link key={x.week} href={`/week/${x.week}`} className={x.week === doc.week ? "wk on" : "wk"} aria-current={x.week === doc.week ? "page" : undefined}>
                {x.week.slice(5)}{x.backfilled ? " 소급" : ""}
              </Link>
            ))}
          </nav>
        </div>
      </section>

      <main className="wrap main">
        <section aria-labelledby="top10" className="panel">
          <div className="panel-head">
            <h2 id="top10">종합 TOP 10</h2>
            <span className="muted">막대 = 신호별 기여분(합이 지수) · 점선 칩 = 이번 주 값이 없어 빠진 신호</span>
          </div>
          <div className="scroll">
            <table className="table">
              <thead>
                <tr><th scope="col">순위</th><th scope="col">저장소</th><th scope="col">지수</th><th scope="col" className="wide">신호 기여</th><th scope="col">변동</th><th scope="col">스타 순위</th><th scope="col">빠진 신호</th></tr>
              </thead>
              <tbody>
                {doc.top10.map((r) => (
                  <tr key={r.repo_id}>
                    <td className="num big">{r.rank}</td>
                    <td>
                      <div className="name">
                        <Link href={repoPath(r.full_name)}>{r.full_name}</Link>
                        {r.category ? <span className="chip">{r.category}</span> : null}
                      </div>
                    </td>
                    <td className="num big">{fmt(r.index)}</td>
                    <td><StackedBar row={r} /></td>
                    <td>{move(r)}</td>
                    <td>{r.star_rank == null ? "—" : `${r.star_rank}위`}</td>
                    <td><div className="chips">{r.missing.map((m) => <span key={m} className="chip-miss">{SIGNAL_NAME[m]}</span>)}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section aria-labelledby="bysig" className="stackcol">
          <h2 id="bysig">신호별 TOP 5</h2>
          <div className="grid5">
            {(["s1", "s3", "s4", "s5", "s2"] as const).map((s) => (
              <div key={s} className="card" style={{ borderTopColor: SIGNAL_COLOR[s] }}>
                <div className="card-head"><b>{SIGNAL_NAME[s]}</b><span className="muted">{SIGNAL_WHAT[s]}</span></div>
                {doc.by_signal[s].length ? (
                  <ol className="ol">
                    {doc.by_signal[s].map((it) => (
                      <li key={it.repo_id}><span className="between"><Link href={repoPath(it.full_name)} className="wrapname">{it.full_name}</Link><span className="num">{fmt(it.pct)}</span></span></li>
                    ))}
                  </ol>
                ) : (
                  <p className="muted">이번 주는 값이 없습니다. 포크 증가는 주간 스냅샷 두 개가 쌓인 뒤 나옵니다.</p>
                )}
              </div>
            ))}
          </div>
        </section>

        <section aria-labelledby="angles" className="panel">
          <div className="panel-head">
            <h2 id="angles">관점 노트 — 스타 순위로는 안 보이는 저장소</h2>
            <span className="muted">유형마다 최대 5개 · 코드가 규칙으로 고른다</span>
          </div>
          <div className="grid4">
            {(["A", "B", "C", "D"] as const).map((k) => {
              const a = doc.angles[k];
              return (
                <div key={k} className="angle">
                  <div className="angle-head"><span className="badge">{k}</span><b>{ANGLE_NAME[k]}</b></div>
                  <p className="muted">{ANGLE_RULE[k]}</p>
                  {a.status === "insufficient" ? (
                    <p className="note">4주 이력이 쌓이면 채워집니다.</p>
                  ) : a.items.length === 0 ? (
                    <p className="note">이번 주에는 조건을 만족하는 저장소가 없습니다.</p>
                  ) : (
                    <ul className="ul">
                      {a.items.map((it: AngleItem) => (
                        <li key={it.repo_id}><Link href={repoPath(it.full_name)} className="wrapname">{it.full_name}</Link> <span className="muted">{evidence(k, it.evidence)}</span></li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      </main>
    </>
  );
}
