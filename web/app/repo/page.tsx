import Link from "next/link";

import { SiteFooter, SiteHeader } from "@/components/Chrome";
import { loadRepos, loadWeeks } from "@/lib/data";
import { fmt, repoPath } from "@/lib/format";

// 저장소 목록 — 최신 주에 후보였던 저장소를 지수 순으로
export default function RepoIndex() {
  const latest = loadWeeks()[0].week;
  const repos = loadRepos()
    .filter((r) => r.latest.week === latest)
    .sort((a, b) => a.latest.rank - b.latest.rank);
  return (
    <>
      <SiteHeader active="repo" />
      <main className="wrap main">
        <section className="panel">
          <div className="panel-head"><h2>이번 주 후보 저장소 {repos.length}개</h2><span className="muted">종합 순위 순</span></div>
          <div className="scroll">
            <table className="table">
              <thead><tr><th scope="col">순위</th><th scope="col">저장소</th><th scope="col">카테고리</th><th scope="col">지수</th><th scope="col">스타 순위</th></tr></thead>
              <tbody>
                {repos.map((r) => (
                  <tr key={r.repo_id}>
                    <td className="num">{r.latest.rank}</td>
                    <td><Link href={repoPath(r.full_name)} className="wrapname">{r.full_name}</Link></td>
                    <td>{r.category ?? "—"}</td>
                    <td className="num">{fmt(r.latest.index)}</td>
                    <td>{r.latest.star_rank == null ? "—" : `${r.latest.star_rank}위`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
