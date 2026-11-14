import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { WeekView } from "@/components/WeekView";
import type { WeekDoc } from "@/lib/types";

import rawWeek from "./fixtures/week_2026-11-01.json";

afterEach(cleanup);

const doc = rawWeek as unknown as WeekDoc;
const weeks = [{ week: doc.week, backfilled: false, issue: 1, candidates: 200, top1: null }];

describe("홈 TOP 10 — AI 한 줄 (D16, TopRowV2)", () => {
  it("puts the AI line only under repositories that have one", () => {
    const { container } = render(<WeekView doc={doc} weeks={weeks} lines={{ "274495425": "스타는 70위 — 사용으로 오른 저장소입니다." }} />);
    const lines = container.querySelectorAll(".ai-line");
    expect(lines).toHaveLength(1);
    expect(lines[0].querySelector(".ai-tag")?.textContent).toBe("AI");
    expect(lines[0].textContent).toContain("사용으로 오른 저장소");
    const row = lines[0].closest("tr")!;
    expect(row.textContent).toContain("remotion-dev/remotion");
  });

  it("leaves the line empty without commentary", () => {
    const { container } = render(<WeekView doc={doc} weeks={weeks} />);
    expect(container.querySelectorAll(".ai-line")).toHaveLength(0);
    expect(container.querySelectorAll("tbody tr").length).toBeGreaterThan(0);
  });
});
