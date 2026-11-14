// Vercel 빌드 준비 (SPEC F10-2 · D13, PLAN §4-1) — 비공개 저장소의 해설 사본만 web/.data/site-private 로 받는다.
//
//   공개 데이터  ../data/site 를 그대로 읽는다(레이더 Vercel 프로젝트는 루트 밖 파일을 포함한다). 받지 않고 있는지만 본다.
//   비공개 사본  RADAR_PRIVATE_REPO(owner/name) 의 site-private/ 한 폴더만 얕게 받는다(읽기 전용 토큰 RADAR_PRIVATE_READ_TOKEN).
//
// 토큰은 명령줄에 넣지 않고 git 환경변수 설정(GIT_CONFIG_*)으로만 넘긴다 — 실패해도 빌드 로그에 남지 않게.
// 프로덕션 빌드는 비공개 사본 없이 진행하지 않는다(해설이 말없이 빠지지 않게). 미리보기·로컬은 해설 없이 빌드한다(PLAN PK5).
// 사용: node scripts/prepare-data.mjs   (web/vercel.json 의 buildCommand)
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const OUT = ".data";
const PRIV_DIR = path.join(OUT, "site-private");
const PUBLIC_MARK = "../data/site/weeks.json";
const REPO = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;

/** 무엇을 할지 — 환경변수와 파일 존재만 보고 정한다(부작용 없음) */
export function planPrepare(env, exists) {
  const site = exists(PUBLIC_MARK)
    ? { action: "use", from: "../data/site" }
    : { action: "fail", reason: "../data/site 가 보이지 않는다 — Vercel 프로젝트 설정의 '루트 밖 파일 포함'을 확인한다" };

  const production = env.VERCEL_ENV === "production";
  const repo = env.RADAR_PRIVATE_REPO;
  const token = env.RADAR_PRIVATE_READ_TOKEN;
  let priv;
  if (repo && token) {
    priv = REPO.test(repo)
      ? { action: "fetch", repo, ref: "HEAD", folder: "site-private", required: production }
      : { action: "fail", reason: "RADAR_PRIVATE_REPO 는 owner/name 모양이어야 한다" };
  } else {
    const missing = [repo ? null : "RADAR_PRIVATE_REPO", token ? null : "RADAR_PRIVATE_READ_TOKEN"].filter(Boolean).join("·");
    priv = production
      ? { action: "fail", reason: `프로덕션 빌드에 해설 사본 설정(${missing})이 없다 — 해설이 말없이 빠지지 않도록 빌드를 멈춘다` }
      : { action: "skip", reason: `해설 사본 설정(${missing})이 없다 — 해설 없이 빌드한다` };
  }
  return { site, priv };
}

/** 토큰을 git 환경변수 설정으로 — 명령줄·오류 메시지에 나오지 않는다 */
export function gitAuthEnv(token, base = process.env) {
  const basic = Buffer.from(`x-access-token:${token}`).toString("base64");
  return {
    ...base,
    GIT_TERMINAL_PROMPT: "0",
    GIT_CONFIG_COUNT: "1",
    GIT_CONFIG_KEY_0: "http.https://github.com/.extraheader",
    GIT_CONFIG_VALUE_0: `AUTHORIZATION: basic ${basic}`,
  };
}

/** git 오류 출력을 원인 종류로 — 출력 원문(주소·머리말이 섞일 수 있다)은 옮기지 않는다 */
export function gitFailureKind(stderr) {
  const s = String(stderr ?? "").toLowerCase();
  if (s.includes("repository not found") || s.includes("not found")) {
    return "저장소를 찾지 못했다 — 토큰의 Repository access 에 이 비공개 저장소가 있는지 본다";
  }
  if (s.includes("authentication failed") || s.includes("401") || s.includes("invalid username or password")) {
    return "인증 실패 — 토큰 값·만료를 본다";
  }
  if (s.includes("403") || s.includes("permission") || s.includes("denied")) {
    return "권한 없음 — 토큰의 Contents 권한(Read)을 본다";
  }
  return "원인 불명 — 네트워크 또는 git 오류";
}

/** 한 폴더만 얕게 받는 git 명령들(인자 배열) */
export function fetchCommands(repo, ref, folder, dir) {
  return [
    ["clone", "--quiet", "--filter=blob:none", "--no-checkout", "--depth", "1", `https://github.com/${repo}.git`, dir],
    ["-C", dir, "sparse-checkout", "set", folder],
    ["-C", dir, "fetch", "--quiet", "--depth", "1", "--filter=blob:none", "origin", ref],
    ["-C", dir, "checkout", "--quiet", "FETCH_HEAD"],
  ];
}

function fetchFolder({ repo, ref, folder }, dest, env) {
  const tmp = fs.mkdtempSync(path.join(OUT, ".fetch-"));
  const dir = path.join(tmp, "repo");
  try {
    for (const args of fetchCommands(repo, ref, folder, dir)) {
      try {
        execFileSync("git", args, { env, stdio: ["ignore", "ignore", "pipe"] });
      } catch (e) {
        // 인자에는 토큰이 없지만, 혹시 모를 git 출력은 그대로 옮기지 않는다 — 원인 종류만 알린다
        const kind = gitFailureKind(e && typeof e === "object" && "stderr" in e ? e.stderr : "");
        throw new Error(`git ${args[0] === "-C" ? args[2] : args[0]} 실패 — ${repo} 의 ${folder}: ${kind}`);
      }
    }
    const src = path.join(dir, folder);
    if (!fs.existsSync(path.join(src, "cards"))) throw new Error(`${repo} 에 ${folder}/cards 가 없다`);
    fs.cpSync(src, dest, { recursive: true });
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
}

function count(dir) {
  return fs.existsSync(dir) ? fs.readdirSync(dir, { recursive: true }).length : 0;
}

export function main(env = process.env) {
  const plan = planPrepare(env, (p) => fs.existsSync(p));
  if (plan.site.action === "fail") throw new Error(plan.site.reason);
  console.log(`[prepare-data] 공개 데이터: ${plan.site.from} 를 그대로 읽는다`);

  // 지난 빌드의 사본이 남아 새 설정 없이 쓰이지 않게 먼저 지운다
  fs.rmSync(PRIV_DIR, { recursive: true, force: true });
  if (plan.priv.action === "fail") throw new Error(plan.priv.reason);
  if (plan.priv.action === "skip") {
    console.log(`[prepare-data] 해설 사본: 건너뜀 — ${plan.priv.reason}`);
    return;
  }
  fs.mkdirSync(OUT, { recursive: true });
  try {
    fetchFolder(plan.priv, PRIV_DIR, gitAuthEnv(env.RADAR_PRIVATE_READ_TOKEN, env));
  } catch (e) {
    fs.rmSync(PRIV_DIR, { recursive: true, force: true });
    if (plan.priv.required) throw e;
    console.warn(`[prepare-data] 해설 사본: 받지 못해 해설 없이 빌드한다(미리보기) — ${e instanceof Error ? e.message : String(e)}`);
    return;
  }
  console.log(`[prepare-data] 해설 사본: ${plan.priv.repo} → ${PRIV_DIR} (${count(PRIV_DIR)}개)`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    main();
  } catch (e) {
    console.error(`[prepare-data] ${e instanceof Error ? e.message : String(e)}`);
    process.exit(1);
  }
}
