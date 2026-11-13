import { segments } from "@/lib/format";
import type { Row } from "@/lib/types";

export function StackedBar({ row, height = 14 }: { row: Pick<Row, "pct" | "contrib">; height?: number }) {
  const segs = segments(row);
  const label = segs.length ? segs.map((s) => s.label).join(", ") : "값 없음";
  return (
    <div role="img" aria-label={`신호 기여: ${label}`} className="stack" style={{ height }}>
      {segs.map((s) => (
        <span key={s.sig} data-sig={s.sig} style={{ width: `${s.width}%`, background: s.color }} />
      ))}
    </div>
  );
}
