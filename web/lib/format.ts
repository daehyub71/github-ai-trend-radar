import type { Row, Sig, SigMap } from "./types";

export const SIGNALS: Sig[] = ["s1", "s2", "s3", "s4", "s5"];
export const SIGNAL_NAME: SigMap<string> = { s1: "스타", s2: "포크", s3: "기여", s4: "사용", s5: "언급" };
// DESIGN §3 — 명도도 서로 다르다
export const SIGNAL_COLOR: SigMap<string> = { s1: "#F59E0B", s2: "#38BDF8", s3: "#4F46E5", s4: "#059669", s5: "#DB2777" };
export const SIGNAL_WHAT: SigMap<string> = {
  s1: "스타 증가",
  s2: "포크 증가",
  s3: "PR·작성자·이슈",
  s4: "다운로드·의존",
  s5: "HN·GeekNews",
};
export const ANGLE_NAME = { A: "조용한 강자", B: "반짝 관심", C: "꾸준한 상승", D: "신호 전환" } as const;
export const ANGLE_RULE = {
  A: "스타 백분위 50 미만 · 사용·기여 평균 80 이상",
  B: "스타·언급 90 이상 · 포크·기여·사용 평균 30 이하",
  C: "종합 지수 4주 연속 상승",
  D: "4주 전보다 사용·기여 비중 20%p 이상 상승",
} as const;

const WD = "일월화수목금토";

export function fmt(v: number | null | undefined, digits = 1): string {
  return v == null ? "—" : v.toFixed(digits);
}

export function int(v: number | string | null | undefined): string {
  return typeof v === "number" ? v.toLocaleString("ko-KR") : v == null ? "—" : String(v);
}

/** 2026-11-01 → "2026년 11월 1일(일) ~ 11월 7일(토)" (UTC) */
export function weekRange(week: string): string {
  const s = new Date(`${week}T00:00:00Z`);
  const e = new Date(s.getTime() + 6 * 86400000);
  const d = (x: Date) => `${x.getUTCMonth() + 1}월 ${x.getUTCDate()}일(${WD[x.getUTCDay()]})`;
  return `${s.getUTCFullYear()}년 ${d(s)} ~ ${d(e)}`;
}

/** 쌓은 막대 조각 — 값이 있는 신호만, 폭은 기여분(지수 최대 100 이므로 %로 그대로). */
export function segments(r: Pick<Row, "pct" | "contrib">): { sig: Sig; width: number; color: string; label: string }[] {
  return SIGNALS.filter((s) => r.pct[s] != null && r.contrib[s] > 0).map((s) => ({
    sig: s,
    width: r.contrib[s],
    color: SIGNAL_COLOR[s],
    label: `${SIGNAL_NAME[s]} ${fmt(r.contrib[s])}`,
  }));
}

export function move(r: Pick<Row, "prev_rank" | "rank">): string {
  if (r.prev_rank == null) return "새로 진입";
  const d = r.prev_rank - r.rank;
  return d === 0 ? "그대로" : d > 0 ? `▲${d}` : `▼${-d}`;
}

export function repoPath(fullName: string): string {
  const [o, n] = fullName.split("/");
  return `/repo/${encodeURIComponent(o)}/${encodeURIComponent(n)}`;
}
