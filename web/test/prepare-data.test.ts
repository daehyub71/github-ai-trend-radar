import { describe, expect, it } from "vitest";

import { fetchCommands, gitAuthEnv, gitFailureHint, gitFailureKind, planPrepare } from "../scripts/prepare-data.mjs";

const TOKEN = "github_pat_" + "x".repeat(70); // 형식만 맞춘 가짜 값
const PUBLIC = (p: string) => p === "../data/site/weeks.json";

describe("prepare-data — Vercel 빌드 준비 (D13, PLAN PK5)", () => {
  it("reads the public data in place and never fetches it", () => {
    expect(planPrepare({}, PUBLIC).site).toEqual({ action: "use", from: "../data/site" });
    expect(planPrepare({}, () => false).site.action).toBe("fail");
  });

  it("fetches only site-private with both the repo and the read token", () => {
    const env = { RADAR_PRIVATE_REPO: "o/p", RADAR_PRIVATE_READ_TOKEN: TOKEN };
    expect(planPrepare(env, PUBLIC).priv).toEqual({ action: "fetch", repo: "o/p", ref: "HEAD", folder: "site-private", required: false });
    expect(planPrepare({ ...env, VERCEL_ENV: "production" }, PUBLIC).priv).toMatchObject({ action: "fetch", required: true });
  });

  it("refuses a production build without the private copy settings", () => {
    // 해설이 말없이 빠지지 않게 — 둘 중 하나만 있어도 멈춘다
    for (const env of [
      { VERCEL_ENV: "production" },
      { VERCEL_ENV: "production", RADAR_PRIVATE_REPO: "o/p" },
      { VERCEL_ENV: "production", RADAR_PRIVATE_READ_TOKEN: TOKEN },
    ]) {
      const priv = planPrepare(env, PUBLIC).priv;
      expect(priv.action).toBe("fail");
      expect(JSON.stringify(priv)).not.toContain(TOKEN);
    }
    const priv = planPrepare({ VERCEL_ENV: "production", RADAR_PRIVATE_REPO: "o/p" }, PUBLIC).priv;
    expect(priv).toMatchObject({ reason: expect.stringContaining("RADAR_PRIVATE_READ_TOKEN") });
  });

  it("skips the private copy on preview and local builds", () => {
    expect(planPrepare({}, PUBLIC).priv.action).toBe("skip");
    expect(planPrepare({ VERCEL_ENV: "preview" }, PUBLIC).priv.action).toBe("skip");
    expect(planPrepare({ VERCEL_ENV: "preview", RADAR_PRIVATE_REPO: "o/p" }, PUBLIC).priv.action).toBe("skip");
  });

  it("rejects a repo name that is not owner/name", () => {
    const env = { RADAR_PRIVATE_REPO: "o/p.git --upload-pack=x", RADAR_PRIVATE_READ_TOKEN: TOKEN };
    expect(planPrepare(env, PUBLIC).priv.action).toBe("fail");
  });

  it("passes the token through git's environment, never on the command line", () => {
    const env = gitAuthEnv(TOKEN, {});
    expect(env.GIT_CONFIG_KEY_0).toBe("http.https://github.com/.extraheader");
    expect(env.GIT_CONFIG_VALUE_0).toBe(`AUTHORIZATION: basic ${Buffer.from(`x-access-token:${TOKEN}`).toString("base64")}`);
    expect(env.GIT_TERMINAL_PROMPT).toBe("0");
    const cmds = fetchCommands("o/p", "HEAD", "site-private", ".tmp");
    expect(cmds.flat().join(" ")).not.toContain(TOKEN);
    expect(cmds.flat().join(" ")).not.toContain(env.GIT_CONFIG_VALUE_0);
    expect(cmds.map((c) => c[0])).toEqual(["clone", "-C", "-C", "-C"]);
    expect(cmds[0]).toContain("https://github.com/o/p.git");
    expect(cmds[1]).toEqual(["-C", ".tmp", "sparse-checkout", "set", "site-private"]);
  });
});

describe("gitFailureKind", () => {
  it("git 오류를 원인 종류로만 바꾼다 — 원문은 옮기지 않는다", () => {
    expect(gitFailureKind(Buffer.from("remote: Repository not found.\nfatal: repository 'https://github.com/o/p.git/' not found"))).toContain("저장소를 찾지 못했다");
    expect(gitFailureKind("fatal: Authentication failed for 'https://github.com/o/p.git/'")).toContain("인증 실패");
    expect(gitFailureKind("The requested URL returned error: 403")).toContain("권한 없음");
    // 자격 증명 도우미가 없는 Vercel 에서 틀린 토큰은 이렇게 끝난다 (2026-11-14 실제 빌드)
    expect(gitFailureKind("fatal: could not read Username for 'https://github.com': terminal prompts disabled")).toContain("인증 실패");
    expect(gitFailureKind(undefined)).toContain("원인 불명");
    expect(gitFailureKind("fatal: Authentication failed for 'https://github.com/o/p.git/'")).not.toContain("github.com");
  });
});

describe("gitFailureHint", () => {
  it("마지막 오류 줄만, 토큰·긴 base64·인증 머리말은 가린다", () => {
    const fake = "github_pat_" + "x".repeat(40);
    expect(gitFailureHint(`trace\nAUTHORIZATION: basic abc\nfatal: bad token ${fake}`)).toBe("fatal: bad token github_pat_[가림]");
    expect(gitFailureHint("fatal: x " + "A".repeat(60))).toBe("fatal: x [가림]");
    expect(gitFailureHint(undefined)).toBe("");
  });
});
