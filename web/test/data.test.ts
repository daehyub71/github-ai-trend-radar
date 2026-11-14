import path from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { loadCard, loadWeekLines, privateDir } from "@/lib/data";

const PRIV = path.resolve(__dirname, "fixtures", "site-private");
const NONE = path.resolve(__dirname, "fixtures", "no-such-dir");

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("비공개 해설 사본 읽기", () => {
  it("reads a card and the TOP 10 lines from the private copy", () => {
    expect(loadCard(274495425, PRIV)?.full_name).toBe("remotion-dev/remotion");
    expect(loadWeekLines("2026-11-01", PRIV)["274495425"]).toContain("350만");
  });

  it("renders without commentary when the copy or the file is absent", () => {
    expect(loadCard(274495425, null)).toBeNull();
    expect(loadCard(274495425, NONE)).toBeNull();
    expect(loadCard(1, PRIV)).toBeNull();
    expect(loadWeekLines("2026-11-01", null)).toEqual({});
    expect(loadWeekLines("2026-10-25", PRIV)).toEqual({});
  });

  it("never builds a path from a malformed id or week", () => {
    expect(loadCard(Number.NaN, PRIV)).toBeNull();
    expect(loadCard(-1, PRIV)).toBeNull();
    expect(loadWeekLines("../cards/274495425", PRIV)).toEqual({});
  });

  it("takes RADAR_PRIVATE_DIR first", () => {
    vi.stubEnv("RADAR_PRIVATE_DIR", PRIV);
    expect(privateDir()).toBe(PRIV);
    expect(loadCard(274495425)?.week).toBe("2026-11-01");
  });
});
