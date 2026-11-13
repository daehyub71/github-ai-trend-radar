import { notFound } from "next/navigation";

import { SiteFooter, SiteHeader } from "@/components/Chrome";
import { WeekView } from "@/components/WeekView";
import { loadWeek, loadWeeks } from "@/lib/data";

export const dynamicParams = false;

export function generateStaticParams() {
  return loadWeeks().map((w) => ({ week: w.week }));
}

export default async function WeekPage({ params }: { params: Promise<{ week: string }> }) {
  const { week } = await params;
  const weeks = loadWeeks();
  if (!weeks.some((w) => w.week === week)) notFound();
  return (
    <>
      <SiteHeader active="week" />
      <WeekView doc={loadWeek(week)} weeks={weeks} />
      <SiteFooter />
    </>
  );
}
