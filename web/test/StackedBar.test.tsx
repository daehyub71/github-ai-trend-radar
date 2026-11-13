import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StackedBar } from "@/components/StackedBar";
import { TrendChart } from "@/components/TrendChart";

describe("StackedBar", () => {
  it("빠진 신호는 그리지 않고, 읽을 수 있는 이름을 붙인다", () => {
    const { container, getByRole } = render(
      <StackedBar row={{ pct: { s1: 50, s2: null, s3: 80, s4: null, s5: 10 }, contrib: { s1: 13.6, s2: 0, s3: 36.4, s4: 0, s5: 2.7 } }} />,
    );
    const spans = container.querySelectorAll("span[data-sig]");
    expect([...spans].map((s) => s.getAttribute("data-sig"))).toEqual(["s1", "s3", "s5"]);
    expect(getByRole("img").getAttribute("aria-label")).toContain("기여 36.4");
  });
});

describe("TrendChart", () => {
  it("소급 주는 빈 점으로, 주 이름에 * 를 붙인다", () => {
    const h = [
      { week: "2026-10-25", backfilled: true, rank: 3, index: 70, contrib: { s1: 20, s2: 0, s3: 40, s4: 0, s5: 10 } },
      { week: "2026-11-01", backfilled: false, rank: 1, index: 90, contrib: { s1: 30, s2: 0, s3: 50, s4: 0, s5: 10 } },
    ];
    const { container } = render(<TrendChart history={h} />);
    const circles = container.querySelectorAll("circle");
    expect(circles[0].getAttribute("fill")).toBe("#FFFFFF");
    expect(circles[1].getAttribute("fill")).toBe("#1F5BD8");
    expect(container.textContent).toContain("10-25*");
  });
});
