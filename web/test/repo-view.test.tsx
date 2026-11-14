import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RepoView } from "@/components/RepoView";
import { parseCard } from "@/lib/card";
import type { Card, RepoDoc } from "@/lib/types";

import rawCard from "./fixtures/site-private/cards/274495425.json";
import rawRepo from "./fixtures/repo_274495425.json";

afterEach(cleanup);

const repo = rawRepo as unknown as RepoDoc;
const card = (patch: (o: Record<string, unknown>) => void = () => {}): Card => {
  const o = JSON.parse(JSON.stringify(rawCard)) as Record<string, unknown>;
  patch(o);
  return parseCard(o, 274495425);
};

const section = (c: HTMLElement, id: string) => c.querySelector<HTMLElement>(`section#${id}`);

describe("저장소 화면 v2 — 해설이 있을 때 (DESIGN §2-2b)", () => {
  it("shows the AI notice, the chip and every section in order", () => {
    const { container } = render(<RepoView repo={repo} card={card()} />);
    const note = screen.getByRole("note", { name: "AI 작성 안내" });
    expect(note.textContent).toContain("사람이 검토하지 않았");
    expect(note.textContent).toContain("숫자는 모두 코드가 계산");
    expect(container.querySelector(".chip-ai")?.textContent).toBe("AI 해설 · 2026-11-01 주");
    const ids = [...container.querySelectorAll("main section[id]")].map((s) => s.id);
    expect(ids).toEqual(["summary", "trend", "what", "buzz", "insight", "signals", "sources"]);
    const toc = screen.getByRole("navigation", { name: "이 화면의 절" });
    expect([...toc.querySelectorAll("a")].map((a) => a.getAttribute("href"))).toEqual(ids.map((i) => `#${i}`));
  });

  it("puts the previous week under the hero numbers", () => {
    const { container } = render(<RepoView repo={repo} card={card()} />);
    const subs = [...container.querySelectorAll(".stat .d")].map((d) => d.textContent);
    expect(subs).toEqual(["지난주 10위 · 4계단 위", "지난주 77.0", "스타만 보면 TOP 10 밖"]);
    expect(container.querySelector(".stat .d.up")).not.toBeNull();
  });

  it("renders 01 summary with sources and 확인·추정", () => {
    const { container } = render(<RepoView repo={repo} card={card()} />);
    const s = section(container, "summary")!;
    const rows = [...s.querySelectorAll(".claim-row")];
    expect(rows.map((r) => r.querySelector("b")?.textContent)).toEqual(["무엇인지", "이번 주 왜 올랐나", "무엇을 볼까"]);
    const bases = [...s.querySelectorAll(".basis")];
    expect(bases.map((b) => b.textContent)).toEqual(["E1 · 확인", "코드 값 · 확인", "코드 값·E4 · 추정"]);
    expect(bases[0].getAttribute("style")).toContain("rgb(6, 95, 70)"); // #065F46
    expect(bases[2].getAttribute("style")).toContain("rgb(146, 64, 14)"); // #92400E
    expect(bases[0].querySelector("a")?.getAttribute("href")).toBe("#ev-E1");
  });

  it("renders 02 from the public trend table, the card releases and notes", () => {
    const { container } = render(<RepoView repo={repo} card={card()} />);
    const s = section(container, "trend")!;
    expect(s.textContent).toContain("코드 계산 — 11-01 주(11-01~11-07)");
    const rows = [...s.querySelectorAll("tbody tr")].map((r) => [...r.children].map((c) => c.textContent));
    expect(rows[0]).toEqual(["종합 순위", "10위", "6위", "16위"]);
    expect(rows).toHaveLength(9);
    expect(s.querySelector(".rel")?.textContent).toBe("이번 주 릴리스: v4.0.540 (11-02) · v4.0.541 (11-05)");
    expect(s.querySelectorAll(".notes li")).toHaveLength(2);
    expect(s.textContent).toContain("E2·E3 · 추정");
  });

  it("renders 03, 04 counts and posts, 05 insights and watch, 07 evidence", () => {
    const { container } = render(<RepoView repo={repo} card={card()} />);
    expect([...section(container, "what")!.querySelectorAll(".claim-row b")].map((b) => b.textContent)).toEqual(["푸는 문제", "대안과 비교한 자리"]);

    const buzz = section(container, "buzz")!;
    expect([...buzz.querySelectorAll(".count .v")].map((v) => v.textContent)).toEqual(["0건", "0건", "1건 · 1점"]);
    expect([...buzz.querySelectorAll(".count .k")].map((k) => k.textContent)).toEqual(["이번 주 Hacker News", "이번 주 GeekNews", "12주 Hacker News"]);
    const post = within(buzz).getByRole("link", { name: "Example post title" });
    expect(post.getAttribute("href")).toBe("https://news.ycombinator.com/item?id=1");
    expect(buzz.textContent).toContain("읽는 법");
    expect(buzz.querySelector(".nature")).toBeNull(); // nature null → 칩 없음

    const ins = section(container, "insight")!;
    expect([...ins.querySelectorAll("[data-insight]")].map((i) => i.getAttribute("data-insight"))).toEqual(["I1", "I2", "I3", "I4", "I5", "I6", "I7"]);
    expect(ins.querySelectorAll(".watch li")).toHaveLength(2);

    const src = section(container, "sources")!;
    expect([...src.querySelectorAll("tbody tr")].map((r) => r.id)).toEqual(["ev-E1", "ev-E2", "ev-E3", "ev-E4"]);
    expect(src.textContent).toContain("지난 해설: 없음(첫 해설)");
    expect(src.textContent).toContain("해설 기준: Sonnet 5.5 · 게이트에서 빠진 항목 0개");
  });

  it("shows the nature chip, trigger and reactions when the card has them", () => {
    const c = card((o) => {
      o.buzz = {
        posts: [{ site: "GeekNews", title: "글", url: "https://news.hada.io/topic?id=1", points: 2, comments: null, date: "2026-11-03", target: "저장소 이슈 #107757" }],
        nature: "논란",
        trigger: { text: "이슈 하나가 화제가 됐습니다.", sources: ["E1"], basis: "확인" },
        reactions: [{ text: "반응 하나", sources: ["E1"], basis: "확인" }],
        reading: null,
      };
    });
    const { container } = render(<RepoView repo={repo} card={c} />);
    const buzz = section(container, "buzz")!;
    const chip = buzz.querySelector(".nature")!;
    expect(chip.textContent).toBe("화제의 성격: 논란");
    expect(chip.getAttribute("style")).toContain("rgb(254, 226, 226)"); // #FEE2E2
    expect(buzz.textContent).toContain("계기");
    expect(buzz.textContent).toContain("반응의 요지");
    expect(buzz.textContent).not.toContain("읽는 법");
    const cells = [...buzz.querySelectorAll("tbody td")].map((td) => td.textContent);
    expect(cells).toContain("—"); // GeekNews 댓글 수 없음
    expect(cells).toContain("저장소 이슈 #107757");
    expect(buzz.querySelector(".obs")?.textContent).toContain("I5");
  });

  it("hides null summary lines and empty sub-blocks without crashing", () => {
    const c = card((o) => {
      o.summary = { what: null, why_now: { text: "한 줄", sources: ["F"], basis: "확인" }, watch: null };
      o.trend_notes = [];
      o.what = [];
      o.watch = [];
      o.releases = [];
      o.evidence = [];
      o.buzz = { posts: [], nature: null, trigger: null, reactions: [], reading: null };
    });
    const { container } = render(<RepoView repo={repo} card={c} />);
    expect(section(container, "summary")!.querySelectorAll(".claim-row")).toHaveLength(1);
    expect(section(container, "what")).toBeNull();
    expect(section(container, "trend")!.querySelector(".rel")).toBeNull();
    expect(section(container, "trend")!.querySelector(".notes")).toBeNull();
    expect(section(container, "buzz")!.querySelector(".buzz-ai")).toBeNull();
    expect(section(container, "insight")!.querySelector(".watch")).toBeNull();
    expect(section(container, "sources")!.querySelector("table")).toBeNull();
  });

  it("links only http(s) addresses and never injects HTML", () => {
    const c = card((o) => {
      o.evidence = [{ id: "E1", title: "<img src=x onerror=alert(1)>", site: "github.com", date: null, url: "javascript:alert(1)" }];
    });
    const { container } = render(<RepoView repo={repo} card={c} />);
    const src = section(container, "sources")!;
    expect(src.querySelector("img")).toBeNull();
    expect(src.textContent).toContain("<img src=x onerror=alert(1)>");
    expect(src.querySelector("a")).toBeNull();
    expect(container.innerHTML).not.toContain("javascript:");
  });

  it("says which week the commentary is for when it is older than the numbers", () => {
    const old = card((o) => {
      o.week = "2026-10-25";
    });
    const { container } = render(<RepoView repo={repo} card={old} cardWeekHref="/week/2026-10-25" />);
    const status = screen.getByRole("status");
    expect(status.textContent).toContain("이번 주에는 해설 대상이 아니었습니다");
    expect(status.textContent).toContain("마지막 해설: 2026-10-25 주");
    expect(within(status).getByRole("link").getAttribute("href")).toBe("/week/2026-10-25");
    expect(container.querySelector(".chip-ai")?.textContent).toBe("AI 해설 · 2026-10-25 주");
  });
});

describe("저장소 화면 v2 — 해설이 없을 때", () => {
  it("shows only the hero, 05 code observations and 06", () => {
    const { container } = render(<RepoView repo={repo} card={null} />);
    expect(screen.queryByRole("note")).toBeNull();
    expect(screen.queryByRole("navigation", { name: "이 화면의 절" })).toBeNull();
    expect(container.querySelector(".chip-ai")).toBeNull();
    expect(container.querySelector(".tag-ai")).toBeNull();
    expect([...container.querySelectorAll("main section[id]")].map((s) => s.id)).toEqual(["insight", "signals"]);
    expect(section(container, "insight")!.querySelectorAll("[data-insight]")).toHaveLength(7);
    expect(container.querySelector(".sec-no")).toBeNull();
    // 06 — v1 절 그대로
    expect(container.querySelector("#pct")).not.toBeNull();
    expect(container.querySelector("#contrib")).not.toBeNull();
    expect(container.querySelector("svg.trend")).not.toBeNull();
  });

  it("still renders when the data folder predates the v2 fields", () => {
    const old: RepoDoc = { ...repo, insights: undefined, insights_version: undefined, trend: undefined, mentions: undefined };
    const { container } = render(<RepoView repo={old} card={null} />);
    expect(section(container, "insight")!.textContent).toContain("관찰할 값이 없습니다");
    expect(container.querySelector(".stat .d")?.textContent).toBe("지난주 10위 · 4계단 위");
  });
});
