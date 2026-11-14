import { describe, expect, it } from "vitest";

import { safeHref } from "@/lib/url";

// 해설·근거 URL 은 바깥 자료에서 온다 — http·https 만 링크가 된다
describe("safeHref", () => {
  it("keeps http and https addresses", () => {
    expect(safeHref("https://github.com/remotion-dev/remotion")).toBe("https://github.com/remotion-dev/remotion");
    expect(safeHref("http://example.com/a?b=1")).toBe("http://example.com/a?b=1");
    expect(safeHref("  https://news.ycombinator.com/item?id=1 ")).toBe("https://news.ycombinator.com/item?id=1");
  });

  it("drops script, data, relative and malformed addresses", () => {
    for (const bad of [
      "javascript:alert(1)",
      "JavaScript:alert(1)",
      "java\tscript:alert(1)",
      "data:text/html,<script>alert(1)</script>",
      "vbscript:msgbox",
      "file:///etc/passwd",
      "//evil.example.com",
      "/repo/a/b",
      "not a url",
      "",
    ]) {
      expect(safeHref(bad), bad).toBeNull();
    }
    expect(safeHref(null)).toBeNull();
    expect(safeHref(undefined)).toBeNull();
    expect(safeHref(42)).toBeNull();
  });
});
