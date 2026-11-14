// AI 작성 안내 — SPEC F10-2 화면 안내(D13). 해설은 사람이 검토하지 않은 AI 글이라는 것을 읽는 사람에게 먼저 밝힌다.
// 문구는 시안 v2(RepoV2) 그대로.
export function AiNotice() {
  return (
    <aside aria-label="AI 작성 안내" role="note" className="ai-notice">
      <span className="ai-badge">AI 작성</span>
      <p>
        보라 표시 글은 AI(Claude)가 공개 자료(README·릴리스·Hacker News·GeekNews·웹 글)로 쓴 해설입니다. 사람이 검토하지 않았고, 항목마다 근거
        번호와 <strong>확인</strong>(근거가 직접 말함)·<strong>추정</strong>(해석) 표시를 붙였습니다. 숫자는 모두 코드가 계산합니다.
      </p>
      <div className="tags">
        <span className="tag-ai">AI 해설</span>
        <span className="tag-code">코드 계산</span>
      </div>
    </aside>
  );
}
