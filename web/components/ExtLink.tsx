import type { ReactNode } from "react";

import { safeHref } from "@/lib/url";

// 바깥 주소 링크 — http·https 만 링크로, 나머지(javascript: 등)는 글자로만 보인다.
export function ExtLink({ href, children }: { href: string | null | undefined; children: ReactNode }) {
  const safe = safeHref(href);
  return safe ? (
    <a href={safe} rel="noreferrer">
      {children}
    </a>
  ) : (
    <span>{children}</span>
  );
}
