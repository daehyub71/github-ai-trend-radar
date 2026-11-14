import { notFound } from "next/navigation";

import { SiteFooter, SiteHeader } from "@/components/Chrome";
import { RepoView } from "@/components/RepoView";
import { findRepo, loadCard, loadRepos, loadWeeks } from "@/lib/data";

export const dynamicParams = false;

export function generateStaticParams() {
  return loadRepos().map((r) => {
    const [owner, name] = r.full_name.split("/");
    return { owner, name };
  });
}

export default async function RepoPage({ params }: { params: Promise<{ owner: string; name: string }> }) {
  const { owner, name } = await params;
  const r = findRepo(decodeURIComponent(owner), decodeURIComponent(name));
  if (!r) notFound();
  // 비공개 해설 사본 — 없으면 null(해설 없이 히어로 · 05 · 06 만)
  const card = loadCard(r.repo_id);
  const cardWeekHref = card && loadWeeks().some((w) => w.week === card.week) ? `/week/${card.week}` : null;
  return (
    <>
      <SiteHeader active="repo" />
      <RepoView repo={r} card={card} cardWeekHref={cardWeekHref} />
      <SiteFooter />
    </>
  );
}
