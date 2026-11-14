import { describe, expect, it } from "vitest";

import { basisText, modelLabel, parseCard, parseClaim, parseWeekLines, sourceLabel } from "@/lib/card";

import raw from "./fixtures/site-private/cards/274495425.json";

const clone = (): Record<string, unknown> => JSON.parse(JSON.stringify(raw)) as Record<string, unknown>;

describe("parseCard — 해설 사본 형식 v1 (PLAN §4-1)", () => {
  it("reads the canonical fixture", () => {
    const c = parseCard(raw, 274495425);
    expect(c.week).toBe("2026-11-01");
    expect(c.summary.why_now?.sources).toEqual(["F"]);
    expect(c.trend_notes).toHaveLength(2);
    expect(c.what.map((w) => w.label)).toEqual(["푸는 문제", "대안과 비교한 자리"]);
    expect(c.buzz.posts[0]).toMatchObject({ site: "HN", points: 1, comments: 0, target: "저장소" });
    expect(c.buzz.nature).toBeNull();
    expect(c.buzz.trigger).toBeNull();
    expect(c.evidence.map((e) => e.id)).toEqual(["E1", "E2", "E3", "E4"]);
    expect(c.gate).toEqual({ checked: 14, excluded: 0 });
  });

  it("keeps null summary lines and empty arrays without crashing", () => {
    const o = clone();
    o.summary = { what: null, why_now: null, watch: null };
    o.trend_notes = [];
    o.what = [];
    o.buzz = { posts: [], nature: null, trigger: null, reactions: [], reading: null };
    o.watch = [];
    o.releases = [];
    o.evidence = [];
    o.history = [];
    const c = parseCard(o, 274495425);
    expect(c.summary).toEqual({ what: null, why_now: null, watch: null });
    expect(c.buzz.posts).toEqual([]);
    expect(c.evidence).toEqual([]);
  });

  it("keeps a null comment count (GeekNews) and drops claims without a basis", () => {
    const o = clone();
    o.buzz = { ...(o.buzz as object), posts: [{ site: "GeekNews", title: "t", url: "https://news.hada.io/topic?id=1", points: 2, comments: null, date: "2026-11-03", target: "저장소" }] };
    o.trend_notes = [{ text: "x", sources: ["F"], basis: "단정" }, { text: "", sources: ["F"], basis: "확인" }, { text: "ok", sources: ["F"], basis: "확인" }];
    const c = parseCard(o, 274495425);
    expect(c.buzz.posts[0].comments).toBeNull();
    expect(c.trend_notes.map((n) => n.text)).toEqual(["ok"]);
  });

  it("stops the build on another format version or a card filed under another repo", () => {
    expect(() => parseCard({ ...clone(), version: 2 }, 274495425)).toThrow(/v1/);
    expect(() => parseCard(raw, 1)).toThrow(/repo_id/);
    expect(() => parseCard({ ...clone(), week: "11-01" }, 274495425)).toThrow(/주/);
  });
});

describe("근거 표시", () => {
  it("reads the code value F as 코드 값", () => {
    expect(sourceLabel("F")).toBe("코드 값");
    expect(sourceLabel("E3")).toBe("E3");
    expect(basisText({ sources: ["F"], basis: "확인" })).toBe("코드 값 · 확인");
    expect(basisText({ sources: ["E1", "E2"], basis: "확인" })).toBe("E1·E2 · 확인");
    expect(basisText({ sources: ["F", "E4"], basis: "추정" })).toBe("코드 값·E4 · 추정");
    expect(basisText({ sources: [], basis: "추정" })).toBe("추정");
  });

  it("keeps only evidence ids and F as sources", () => {
    expect(parseClaim({ text: "a", sources: ["E1", "F", "javascript:x", 3, "E"], basis: "확인" })?.sources).toEqual(["E1", "F"]);
  });

  it("names the model briefly", () => {
    expect(modelLabel("claude-sonnet-5-5")).toBe("Sonnet 5.5");
    expect(modelLabel("something-else")).toBe("something-else");
    expect(modelLabel("")).toBe("—");
  });
});

describe("parseWeekLines — TOP 10 한 줄", () => {
  it("keeps string lines of the same week only", () => {
    expect(parseWeekLines({ week: "2026-11-01", lines: { "1": " 한 줄 ", "2": 3, x: "no", "4": "" } }, "2026-11-01")).toEqual({ "1": "한 줄" });
    expect(parseWeekLines({ week: "2026-10-25", lines: { "1": "a" } }, "2026-11-01")).toEqual({});
    expect(parseWeekLines(null, "2026-11-01")).toEqual({});
  });
});
