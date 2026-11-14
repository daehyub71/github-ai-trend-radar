import { SiteFooter, SiteHeader } from "@/components/Chrome";
import { WeekView } from "@/components/WeekView";
import { loadWeek, loadWeekLines, loadWeeks } from "@/lib/data";

export default function Home() {
  const weeks = loadWeeks();
  const doc = loadWeek(weeks[0].week);
  return (
    <>
      <SiteHeader active="week" />
      <WeekView doc={doc} weeks={weeks} lines={loadWeekLines(doc.week)} />
      <SiteFooter />
    </>
  );
}
