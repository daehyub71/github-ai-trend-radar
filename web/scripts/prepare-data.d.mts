// scripts/prepare-data.mjs 의 타입 — 테스트(test/prepare-data.test.ts)가 쓴다
type Env = Record<string, string | undefined>;
type SiteStep = { action: "use"; from: string } | { action: "fail"; reason: string };
type PrivStep =
  | { action: "fetch"; repo: string; ref: string; folder: string; required: boolean }
  | { action: "skip" | "fail"; reason: string };

export function planPrepare(env: Env, exists: (p: string) => boolean): { site: SiteStep; priv: PrivStep };
export function gitAuthEnv(token: string, base?: Env): Env;
export function fetchCommands(repo: string, ref: string, folder: string, dir: string): string[][];
export function gitFailureKind(stderr: unknown): string;
export function gitFailureHint(stderr: unknown): string;
export function main(env?: Env): void;
