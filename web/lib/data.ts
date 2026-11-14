// 빌드 때 서버 컴포넌트에서만 읽는다 — 클라이언트 컴포넌트에서 import 하지 않는다.
import fs from "node:fs";
import path from "node:path";

import { parseCard, parseWeekLines } from "./card";
import type { Card, RepoDoc, WeekDoc, WeekLines, WeekListItem } from "./types";

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

// ── 비공개 해설 사본(site-private, PLAN §4-1) — 없으면 해설 없이 그린다 ──

/**
 * 해설 사본 폴더. RADAR_PRIVATE_DIR → 빌드 때 받은 web/.data/site-private → 로컬 ../.private/site-private 순.
 * 어느 것도 없으면 null(미리보기·로컬 — 해설 없이 빌드).
 */
export function privateDir(): string | null {
  const env = process.env.RADAR_PRIVATE_DIR;
  if (env) return path.resolve(env);
  const candidates = [
    path.resolve(process.cwd(), ".data", "site-private"),
    path.resolve(process.cwd(), "..", ".private", "site-private"),
  ];
  return candidates.find((d) => fs.existsSync(d)) ?? null;
}

/** cards/<repo_id>.json — 없으면 null. 형식이 계약과 다르면 빌드를 멈춘다(parseCard). */
export function loadCard(repoId: number, dir: string | null = privateDir()): Card | null {
  if (!dir || !Number.isSafeInteger(repoId) || repoId <= 0) return null;
  const file = path.join(dir, "cards", `${repoId}.json`);
  return fs.existsSync(file) ? parseCard(readJson<unknown>(file), repoId) : null;
}

/** weeks/<주>.json 의 TOP 10 한 줄 — 없으면 빈 표 */
export function loadWeekLines(week: string, dir: string | null = privateDir()): WeekLines {
  if (!dir || !WEEK.test(week)) return {};
  const file = path.join(dir, "weeks", `${week}.json`);
  return fs.existsSync(file) ? parseWeekLines(readJson<unknown>(file), week) : {};
}
