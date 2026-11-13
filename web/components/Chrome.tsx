import Link from "next/link";

export function Logo() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
      <circle cx="14" cy="14" r="12" fill="none" stroke="#1F5BD8" strokeWidth="2" />
      <circle cx="14" cy="14" r="6.5" fill="none" stroke="#1F5BD8" strokeWidth="2" opacity="0.55" />
      <path d="M14 14 L23 7" stroke="#8B5CF6" strokeWidth="2.4" strokeLinecap="round" />
      <circle cx="20" cy="9" r="2" fill="#8B5CF6" />
    </svg>
  );
}

export function SiteHeader({ active }: { active: "week" | "repo" | "about" }) {
  const items: [string, string, "week" | "repo" | "about"][] = [
    ["/", "이번 주", "week"],
    ["/repo", "저장소", "repo"],
    ["/about", "지수는 이렇게", "about"],
  ];
  return (
    <header className="topbar">
      <div className="wrap topbar-in">
        <Link href="/" className="brand">
          <Logo />
          <span>깃허브 AI 트렌드 레이더</span>
        </Link>
        <nav aria-label="주 메뉴" className="nav">
          {items.map(([href, label, key]) => (
            <Link key={key} href={href} className={key === active ? "pill on" : "pill"} aria-current={key === active ? "page" : undefined}>
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="footer">
      <div className="wrap footer-in">
        <span>
          AI 저장소 판정·카테고리·스타는 <a href="https://github.com/daehyub71/github-ai-star-trend">github-ai-star-trend</a> 공개
          데이터 · 포크·PR·이슈는 GitHub API · 다운로드는 pypistats·npm · 의존 패키지 수는{" "}
          <a href="https://ecosyste.ms">ecosyste.ms</a>(CC BY-SA 4.0) · 언급은 Hacker News·GeekNews
        </span>
        <span>
          &quot;소급&quot; 표시가 붙은 주는 나중에 거꾸로 모은 값입니다(포크·의존 수 없음). 숫자는 모두 코드가 계산합니다. 데이터·코드:{" "}
          <a href="https://github.com/daehyub71/github-ai-trend-radar">github-ai-trend-radar</a>
        </span>
      </div>
    </footer>
  );
}
