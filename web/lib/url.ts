// 링크로 그려도 되는 주소만 남긴다 — 해설·근거 URL 은 바깥 자료에서 왔으므로 http·https 외에는 글자로만 보인다.
const ALLOWED = new Set(["http:", "https:"]);

/** http/https 주소면 정규화한 href, 아니면 null (javascript:·data:·상대 경로 등). */
export function safeHref(url: unknown): string | null {
  if (typeof url !== "string" || url.trim() === "") return null;
  try {
    const u = new URL(url.trim());
    return ALLOWED.has(u.protocol) ? u.href : null;
  } catch {
    return null;
  }
}
