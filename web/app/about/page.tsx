import { SiteFooter, SiteHeader } from "@/components/Chrome";
import { loadWeek, loadWeeks } from "@/lib/data";
import { SIGNALS, SIGNAL_COLOR, SIGNAL_NAME } from "@/lib/format";

const WHAT = {
  s1: ["스타 증가", "github-ai-star-trend 공개 데이터"],
  s2: ["포크 수 주간 증가(스냅샷 6~8일 간격일 때만)", "GitHub 저장소 메타"],
  s3: ["머지 PR · 고유 작성자 · 닫힌 이슈 백분위 평균(봇 제외)", "GitHub Search API"],
  s4: ["패키지 주간 다운로드 · 의존 패키지 수", "pypistats · npm · ecosyste.ms"],
  s5: ["저장소 링크 글 수 · 점수 합", "Hacker News Algolia · GeekNews"],
} as const;

export default function About() {
  const doc = loadWeek(loadWeeks()[0].week);
  return (
    <>
      <SiteHeader active="about" />
      <main className="wrap narrow main">
        <div className="stackcol">
          <h1 className="h1">지수는 이렇게 만든다</h1>
          <p className="lead">스타는 관심을 보여 주지만, 실제로 쓰이고 관리되는지는 다른 신호에 있습니다. 레이더는 다섯 신호를 같은 눈금으로 바꿔 한 숫자로 모읍니다. 숫자는 모두 코드가 계산합니다.</p>
        </div>
        <section aria-labelledby="steps" className="panel">
          <h2 id="steps">세 단계</h2>
          <ol className="steps">
            <li><b>1 · 후보 안 순위 백분위</b><span>신호마다 그 주 후보 안에서 순위를 매겨 0~100으로 바꿉니다. 같은 값은 가운데 순위를 받습니다. 큰 저장소가 모든 신호를 압도하지 않습니다.</span></li>
            <li><b>2 · 가중 평균, 빠진 신호는 재분배</b><span>값이 없는 신호(예: 패키지 없음)는 0점이 아니라 계산에서 빼고, 남은 가중치로 다시 나눕니다. 빠진 신호는 화면에 표시합니다.</span></li>
            <li><b>3 · 기여분 막대</b><span>신호마다 다시 나눈 가중치 × 백분위가 기여분이고, 기여분의 합이 지수입니다.</span></li>
          </ol>
        </section>
        <section aria-labelledby="sig" className="panel">
          <h2 id="sig">다섯 신호와 가중치 v{doc.weights_version}</h2>
          <div className="scroll">
            <table className="table">
              <thead><tr><th scope="col">신호</th><th scope="col">주간 값</th><th scope="col">출처</th><th scope="col">가중치</th></tr></thead>
              <tbody>
                {SIGNALS.map((s) => (
                  <tr key={s}>
                    <td><span className="legend-i"><i style={{ background: SIGNAL_COLOR[s] }} />{SIGNAL_NAME[s]}</span></td>
                    <td>{WHAT[s][0]}</td>
                    <td className="muted">{WHAT[s][1]}</td>
                    <td className="num big">{doc.weights[s]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>관심(스타)보다 실제로 쓰이고 관리되는지를 더 봅니다. 가중치를 바꾸면 버전을 올리고, 지난 지수는 그때의 가중치로 남깁니다.</p>
        </section>
        <section aria-labelledby="lim" className="panel">
          <h2 id="lim">알고 보면 좋은 한계</h2>
          <ul className="ul">
            <li>AI 저장소 판정과 카테고리는 github-ai-star-trend 의 판정(Claude)을 그대로 씁니다. 지난 주를 소급할 때도 지금의 판정으로 거릅니다.</li>
            <li>&quot;소급&quot; 표시 주는 나중에 거꾸로 모은 값입니다. 포크 증가와 의존 패키지 수는 과거 값을 얻을 수 없어 비어 있습니다.</li>
            <li>사용 신호는 PyPI·npm 패키지가 저장소와 일치할 때만 있습니다. 에이전트 스킬·앱처럼 패키지가 없는 저장소가 많습니다.</li>
            <li>언급은 대부분 0이라 같은 순위가 많습니다. 목록형 저장소는 목록 추가 PR 때문에 기여가 크게 보일 수 있습니다 — 표시만 하고 빼지 않습니다.</li>
            <li>의존 패키지 수는 <a href="https://ecosyste.ms">ecosyste.ms</a> 데이터를 씁니다(CC BY-SA 4.0).</li>
          </ul>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
