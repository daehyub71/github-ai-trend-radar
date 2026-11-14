import { Fragment } from "react";

import { BASIS_COLOR, sourceLabel } from "@/lib/card";
import type { Claim } from "@/lib/types";

// 해설 항목 아래 작은 줄 — "E1·E2 · 확인". 근거 번호는 07절 표의 그 줄로 이어진다. 코드 값(F)은 "코드 값".
export function ClaimBasis({ claim, evidence }: { claim: Pick<Claim, "sources" | "basis">; evidence: ReadonlySet<string> }) {
  return (
    <span className="basis" data-basis={claim.basis} style={{ color: BASIS_COLOR[claim.basis] }}>
      {claim.sources.map((s, i) => (
        <Fragment key={`${s}-${i}`}>
          {i > 0 ? "·" : null}
          {evidence.has(s) ? <a href={`#ev-${s}`}>{s}</a> : sourceLabel(s)}
        </Fragment>
      ))}
      {claim.sources.length ? " · " : null}
      {claim.basis}
    </span>
  );
}

// 글 + 근거 줄을 위아래로
export function ClaimBlock({ claim, evidence, large = false }: { claim: Claim; evidence: ReadonlySet<string>; large?: boolean }) {
  return (
    <div className="claim">
      <span className={large ? "claim-text lg" : "claim-text"}>{claim.text}</span>
      <ClaimBasis claim={claim} evidence={evidence} />
    </div>
  );
}
