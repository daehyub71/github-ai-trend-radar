import { SIGNALS, SIGNAL_COLOR, SIGNAL_NAME, fmt } from "@/lib/format";
import type { HistoryPoint } from "@/lib/types";

// 12주 추이 — 위: 지수 선, 아래: 주별 신호 기여 쌓은 막대. 소급 주는 옅게(DESIGN §2-2).
export function TrendChart({ history }: { history: HistoryPoint[] }) {
  const pts = history.slice(-13);
  if (pts.length === 0) return <p className="muted">이력이 없습니다.</p>;
  const W = 760;
  const H = 280;
  const pad = { l: 36, r: 12, t: 12, b: 28 };
  const lineH = 110;
  const barTop = pad.t + lineH + 24;
  const barH = H - barTop - pad.b;
  const step = (W - pad.l - pad.r) / pts.length;
  const x = (i: number) => pad.l + step * i + step / 2;
  const y = (v: number) => pad.t + lineH - (v / 100) * lineH;
  const line = pts
    .map((p, i) => (p.index == null ? null : `${x(i)},${y(p.index)}`))
    .filter(Boolean)
    .join(" ");
  const label = pts.map((p) => `${p.week.slice(5)} ${p.rank}위 지수 ${fmt(p.index)}${p.backfilled ? "(소급)" : ""}`).join(", ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`주별 지수: ${label}`} className="trend">
      {[0, 50, 100].map((v) => (
        <g key={v}>
          <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke="#E5E7EB" />
          <text x={pad.l - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill="#4B5563">{v}</text>
        </g>
      ))}
      <polyline points={line} fill="none" stroke="#1F5BD8" strokeWidth="2.5" />
      {pts.map((p, i) =>
        p.index == null ? null : (
          <g key={p.week}>
            <circle cx={x(i)} cy={y(p.index)} r="4" fill={p.backfilled ? "#FFFFFF" : "#1F5BD8"} stroke="#1F5BD8" strokeWidth="2" />
            <text x={x(i)} y={y(p.index) - 9} textAnchor="middle" fontSize="10" fill="#374151">{p.rank}위</text>
          </g>
        ),
      )}
      {pts.map((p, i) => {
        let acc = 0;
        return (
          <g key={`b${p.week}`} opacity={p.backfilled ? 0.55 : 1}>
            {SIGNALS.map((s) => {
              const v = p.contrib[s] ?? 0;
              if (v <= 0) return null;
              const h = (v / 100) * barH;
              const top = barTop + barH - acc - h;
              acc += h;
              return <rect key={s} x={x(i) - step * 0.3} y={top} width={step * 0.6} height={h} fill={SIGNAL_COLOR[s]}><title>{`${SIGNAL_NAME[s]} ${fmt(v)}`}</title></rect>;
            })}
            <text x={x(i)} y={H - 10} textAnchor="middle" fontSize="10" fill="#4B5563">{p.week.slice(5)}{p.backfilled ? "*" : ""}</text>
          </g>
        );
      })}
    </svg>
  );
}
