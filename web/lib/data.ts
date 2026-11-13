// 빌드 때 서버 컴포넌트에서만 읽는다 — 클라이언트 컴포넌트에서 import 하지 않는다.
import fs from "node:fs";
import path from "node:path";

import type { RepoDoc, WeekDoc, WeekListItem } from "./types";

const WEEK = /^\d{4}-\d{2}-\d{2}$/;

export function siteDir(): string {
  return process.env.RADAR_SITE_DIR ?? path.resolve(process.cwd(), "..", "data", "site");
}

function readJson<T>(file: string): T {
  return JSON.parse(fs.readFileSync(file, "utf8")) as T;
}

export function loadWeeks(dir: string = siteDir()): WeekListItem[] {
  return readJson<WeekListItem[]>(path.join(dir, "weeks.json"));
}

export function loadWeek(week: string, dir: string = siteDir()): WeekDoc {
  if (!WEEK.test(week)) throw new Error(`주 이름이 아니다: ${week}`);
  return readJson<WeekDoc>(path.join(dir, "week", `${week}.json`));
}

export function loadRepos(dir: string = siteDir()): RepoDoc[] {
  const d = path.join(dir, "repo");
  return fs
    .readdirSync(d)
    .filter((f) => /^\d+\.json$/.test(f))
    .map((f) => readJson<RepoDoc>(path.join(d, f)));
}

export function findRepo(owner: string, name: string, dir: string = siteDir()): RepoDoc | null {
  const want = `${owner}/${name}`.toLowerCase();
  return loadRepos(dir).find((r) => r.full_name.toLowerCase() === want) ?? null;
}
