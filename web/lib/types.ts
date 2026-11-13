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
};
