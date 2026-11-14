// data/site/ 파일 모양 — radar/site.py 와 같게 유지한다(T4-3).
export type Sig = "s1" | "s2" | "s3" | "s4" | "s5";
export type SigMap<T> = Record<Sig, T>;

export type WeekListItem = { week: string; backfilled: boolean; issue: number | null; candidates: number; top1: string | null };

export type Row = {
  rank: number;
  repo_id: number;
  full_name: string;
  category: string | null;
  index: number | null;
  pct: SigMap<number | null>;
  contrib: SigMap<number>;
  missing: Sig[];
  star_rank: number | null;
  prev_rank: number | null;
};

export type AngleItem = { repo_id: number; full_name: string; evidence: Record<string, unknown> };
export type Angle = { status: "ok" | "insufficient"; items: AngleItem[] };

export type WeekDoc = {
  week: string;
  backfilled: boolean;
  issue: number | null;
  weights: SigMap<number>;
  weights_version: number;
  stats: { candidates: number; star_top_in_index_top: number; with_packages: number };
  top10: Row[];
  by_signal: SigMap<{ repo_id: number; full_name: string; pct: number }[]>;
  angles: Record<"A" | "B" | "C" | "D", Angle>;
};

export type HistoryPoint = { week: string; backfilled: boolean; rank: number; index: number | null; contrib: SigMap<number> };

export type RepoDoc = {
  repo_id: number;
  full_name: string;
  category: string | null;
  description: string | null;
  topics: string[];
  language: string | null;
  latest: Row & { week: string; backfilled: boolean; raw: Record<string, number | string | null>; status: Record<string, string | null> };
  history: HistoryPoint[];
  // v2 (F10-1) — 오래된 데이터 폴더에는 없을 수 있다
  insights?: Insight[];
  insights_version?: number;
  trend?: TrendRow[];
  mentions?: Mentions;
};

// ── 저장소 화면 v2 공개 필드 (radar/site.py · core/insights.py) ──
// 05절 코드 관찰 I1~I7 — 숫자에서 나온 문장이라 공개 데이터다(SPEC F10-1)
export type Insight = { id: string; title: string; big: string; text: string; signal: Sig | "index" };
// 02절 동향 표 — 값은 코드가 미리 문자열로 만든다(없으면 "—")
export type TrendRow = { key: string; prev: string; now: string; avg: string };
export type MentionCounts = { hn_stories: number; hn_points: number; gn_topics: number; gn_points: number };
// 04절 숫자 상자 — 이번 주 언급 값이 없으면 null
export type Mentions = { week: MentionCounts; window: MentionCounts & { weeks: number } } | null;

// ── 저장소 해설 사본 형식 v1 (PLAN §4-1, 비공개 site-private/) ──
export type Basis = "확인" | "추정";
// sources = 근거 번호(E1…)와 코드 값("F")
export type Claim = { text: string; sources: string[]; basis: Basis };
export type LabeledClaim = Claim & { label: string };
export type Nature = "소개" | "호평" | "논란" | "질문";
export type BuzzPost = {
  site: string; // "HN" | "GeekNews"
  title: string;
  url: string;
  points: number | null;
  comments: number | null; // GeekNews 는 댓글 수가 없다
  date: string | null;
  target: string | null; // "저장소" · "저장소 이슈 #107757" · "릴리스" …
};
export type Release = { tag: string; date: string | null; url: string };
export type Evidence = { id: string; title: string; site: string; date: string | null; url: string };

export type Card = {
  version: 1;
  repo_id: number;
  full_name: string;
  week: string;
  generated: string;
  model: string;
  gate: { checked: number; excluded: number };
  // 게이트가 뺀 줄은 null
  summary: { what: Claim | null; why_now: Claim | null; watch: Claim | null };
  trend_notes: Claim[];
  what: LabeledClaim[];
  buzz: { posts: BuzzPost[]; nature: Nature | null; trigger: Claim | null; reactions: Claim[]; reading: Claim | null };
  watch: Claim[];
  releases: Release[];
  evidence: Evidence[];
  history: { week: string; why_now: string }[];
};

// 홈 TOP 10 한 줄 — repo_id(문자열) → "이번 주 왜 올랐나" 한 줄
export type WeekLines = Record<string, string>;
