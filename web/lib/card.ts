// 저장소 해설 사본(PLAN §4-1) 읽기·표시 도우미 — 파일을 읽지 않는 순수 함수만 둔다(테스트가 바로 쓴다).
import type { Basis, BuzzPost, Card, Claim, Evidence, LabeledClaim, Nature, Release, WeekLines } from "./types";

export const CARD_VERSION = 1;
const WEEK = /^\d{4}-\d{2}-\d{2}$/;
const EVIDENCE_ID = /^E\d+$/;
const NATURES: readonly Nature[] = ["소개", "호평", "논란", "질문"];

type Obj = Record<string, unknown>;

function obj(x: unknown): Obj | null {
  return typeof x === "object" && x !== null && !Array.isArray(x) ? (x as Obj) : null;
}
function arr(x: unknown): unknown[] {
  return Array.isArray(x) ? x : [];
}
function str(x: unknown): string | null {
  return typeof x === "string" && x.trim() !== "" ? x : null;
}
function num(x: unknown): number | null {
  return typeof x === "number" && Number.isFinite(x) ? x : null;
}
function notNull<T>(x: T | null): x is T {
  return x !== null;
}

/** Claim 하나 — 글이 없거나 확인·추정 표시가 아니면 그리지 않는다(null). */
export function parseClaim(x: unknown): Claim | null {
  const o = obj(x);
  const text = str(o?.text);
  const basis = o?.basis;
  if (!o || !text || (basis !== "확인" && basis !== "추정")) return null;
  const sources = arr(o.sources).filter((s): s is string => typeof s === "string" && (s === "F" || EVIDENCE_ID.test(s)));
  return { text, sources, basis };
}

function parseLabeled(x: unknown): LabeledClaim | null {
  const c = parseClaim(x);
  const label = str(obj(x)?.label);
  return c && label ? { ...c, label } : null;
}

function parsePost(x: unknown): BuzzPost | null {
  const o = obj(x);
  const title = str(o?.title);
  if (!o || !title) return null;
  return {
    site: str(o.site) ?? "—",
    title,
    url: str(o.url) ?? "",
    points: num(o.points),
    comments: num(o.comments),
    date: str(o.date),
    target: str(o.target),
  };
}

function parseRelease(x: unknown): Release | null {
  const o = obj(x);
  const tag = str(o?.tag);
  return o && tag ? { tag, date: str(o.date), url: str(o.url) ?? "" } : null;
}

function parseEvidence(x: unknown): Evidence | null {
  const o = obj(x);
  const id = str(o?.id);
  const title = str(o?.title);
  if (!o || !id || !EVIDENCE_ID.test(id) || !title) return null;
  return { id, title, site: str(o.site) ?? "—", date: str(o.date), url: str(o.url) ?? "" };
}

/**
 * cards/<repo_id>.json 을 화면이 쓰는 모양으로 바꾼다.
 * 형식 버전·저장소가 다르면 멈춘다(빌드 실패) — 계약이 깨진 해설이 말없이 빠지거나 다른 저장소에 붙지 않게.
 * 빈 배열·null 항목은 그 절의 일부만 숨기도록 그대로 둔다.
 */
export function parseCard(raw: unknown, repoId: number): Card {
  const o = obj(raw);
  if (!o) throw new Error(`해설 사본이 객체가 아니다: ${repoId}`);
  if (o.version !== CARD_VERSION) throw new Error(`해설 사본 형식이 v${CARD_VERSION} 이 아니다: ${repoId} (version=${String(o.version)})`);
  if (o.repo_id !== repoId) throw new Error(`해설 사본의 repo_id 가 파일 이름과 다르다: ${repoId}`);
  const week = str(o.week);
  if (!week || !WEEK.test(week)) throw new Error(`해설 사본의 주 이름이 아니다: ${repoId}`);
  const summary = obj(o.summary);
  const buzz = obj(o.buzz);
  const gate = obj(o.gate);
  const nature = buzz?.nature;
  return {
    version: CARD_VERSION,
    repo_id: repoId,
    full_name: str(o.full_name) ?? "",
    week,
    generated: str(o.generated) ?? "",
    model: str(o.model) ?? "",
    gate: { checked: num(gate?.checked) ?? 0, excluded: num(gate?.excluded) ?? 0 },
    summary: {
      what: parseClaim(summary?.what),
      why_now: parseClaim(summary?.why_now),
      watch: parseClaim(summary?.watch),
    },
    trend_notes: arr(o.trend_notes).map(parseClaim).filter(notNull),
    what: arr(o.what).map(parseLabeled).filter(notNull),
    buzz: {
      posts: arr(buzz?.posts).map(parsePost).filter(notNull),
      nature: NATURES.includes(nature as Nature) ? (nature as Nature) : null,
      trigger: parseClaim(buzz?.trigger),
      reactions: arr(buzz?.reactions).map(parseClaim).filter(notNull),
      reading: parseClaim(buzz?.reading),
    },
    watch: arr(o.watch).map(parseClaim).filter(notNull),
    releases: arr(o.releases).map(parseRelease).filter(notNull),
    evidence: arr(o.evidence).map(parseEvidence).filter(notNull),
    history: arr(o.history)
      .map((h) => {
        const x = obj(h);
        const w = str(x?.week);
        return w && WEEK.test(w) ? { week: w, why_now: str(x?.why_now) ?? "" } : null;
      })
      .filter(notNull),
  };
}

/** weeks/<주>.json — 다른 주의 파일이거나 모양이 다르면 빈 표. 값은 글자만 남긴다. */
export function parseWeekLines(raw: unknown, week: string): WeekLines {
  const o = obj(raw);
  const lines = obj(o?.lines);
  if (!o || o.week !== week || !lines) return {};
  const out: WeekLines = {};
  for (const [k, v] of Object.entries(lines)) {
    const t = str(v);
    if (/^\d+$/.test(k) && t) out[k] = t.trim();
  }
  return out;
}

/** 근거 번호 표시 — 코드 값("F")은 "코드 값"으로 읽는다. */
export function sourceLabel(s: string): string {
  return s === "F" ? "코드 값" : s;
}

/** "E1·E2 · 확인" · "코드 값 · 추정" · (근거 없음) "확인" */
export function basisText(c: Pick<Claim, "sources" | "basis">): string {
  const src = c.sources.map(sourceLabel).join("·");
  return src ? `${src} · ${c.basis}` : c.basis;
}

// DESIGN §3 (v2) 근거 표시 색
export const BASIS_COLOR: Record<Basis, string> = { 확인: "#065F46", 추정: "#92400E" };

// 화제의 성격 칩 — 논란은 시안 값, 나머지는 같은 명도 규칙(옅은 바탕 100 · 짙은 글자 800)
export const NATURE_STYLE: Record<Nature, { background: string; color: string }> = {
  소개: { background: "#DBEAFE", color: "#1E40AF" },
  호평: { background: "#DCFCE7", color: "#166534" },
  논란: { background: "#FEE2E2", color: "#991B1B" },
  질문: { background: "#FEF3C7", color: "#92400E" },
};

/** "claude-sonnet-5-5" → "Sonnet 5.5" (모르는 모양이면 그대로) */
export function modelLabel(model: string): string {
  const m = /^claude-([a-z]+)-(\d+)-(\d+)\b/.exec(model);
  if (!m) return model || "—";
  return `${m[1][0].toUpperCase()}${m[1].slice(1)} ${m[2]}.${m[3]}`;
}
