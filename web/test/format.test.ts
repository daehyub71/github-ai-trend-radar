import { describe, expect, it } from "vitest";

import { fmt, move, repoPath, segments, weekRange } from "@/lib/format";

describe("format", () => {
  it("weekRange 는 UTC 일~토", () => {
    expect(weekRange("2026-11-01")).toBe("2026년 11월 1일(일) ~ 11월 7일(토)");
  });
  it("segments 는 값 있는 신호만, 폭 = 기여분", () => {
    const segs = segments({
      pct: { s1: 99.5, s2: null, s3: 94.8, s4: null, s5: 99.0 },
      contrib: { s1: 27.14, s2: 0, s3: 43.09, s4: 0, s5: 27.0 },
    });
    expect(segs.map((s) => s.sig)).toEqual(["s1", "s3", "s5"]);
    expect(segs[1].width).toBe(43.09);
    expect(segs[0].label).toBe("스타 27.1");
  });
  it("move · fmt · repoPath", () => {
    expect(move({ prev_rank: null, rank: 3 })).toBe("새로 진입");
    expect(move({ prev_rank: 5, rank: 2 })).toBe("▲3");
    expect(move({ prev_rank: 1, rank: 4 })).toBe("▼3");
    expect(fmt(null)).toBe("—");
    expect(repoPath("org/a.b")).toBe("/repo/org/a.b");
  });
});

import { rankLine, shortDate, starRankLine, weekSpan } from "@/lib/format";

describe("format — 저장소 화면 v2", () => {
  it("weekSpan · shortDate", () => {
    expect(weekSpan("2026-11-01")).toBe("11-01 주(11-01~11-07)");
    expect(weekSpan("2026-12-27")).toBe("12-27 주(12-27~01-02)");
    expect(shortDate("2026-11-05")).toBe("11-05");
    expect(shortDate(null)).toBe("—");
  });
  it("rankLine · starRankLine", () => {
    expect(rankLine({ prev_rank: 10, rank: 6 })).toEqual({ text: "지난주 10위 · 4계단 위", tone: "up" });
    expect(rankLine({ prev_rank: 3, rank: 5 })).toEqual({ text: "지난주 3위 · 2계단 아래", tone: "down" });
    expect(rankLine({ prev_rank: 5, rank: 5 }).text).toBe("지난주 5위 · 그대로");
    expect(rankLine({ prev_rank: null, rank: 5 }).tone).toBe("flat");
    expect(starRankLine(70)).toBe("스타만 보면 TOP 10 밖");
    expect(starRankLine(3)).toBe("스타로도 TOP 10");
    expect(starRankLine(null)).toBe("스타 순위 없음");
  });
});
