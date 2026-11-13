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
