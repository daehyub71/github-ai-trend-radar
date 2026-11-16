# github-ai-trend-radar

English | [한국어](README_KO.md)

> A weekly **composite trend index** for AI repositories on GitHub — read from five signals instead of stars alone.
> A personal, work-in-progress project built with Claude Code. Project documents (`docs/`) are written in Korean.

**Live site: <https://github-ai-trend-radar.vercel.app>** — this week's composite TOP 10, top 5 per signal, angle notes, and a page per repository.
Repository commentaries on the site are AI-written summaries that no person has reviewed; every claim carries an evidence number and a "confirmed / inferred" mark, and every number is computed by code.

## Why

Stars show attention, not use. A demo can collect thousands of stars in a week while a library that millions of developers install keeps a quiet star count. This project reads every AI repository through five weekly signals:

| Signal | Weekly value | Source | Weight v1 |
|---|---|---|---|
| Stars | star gain | [github-ai-star-trend](https://github.com/daehyub71/github-ai-star-trend) public data | 15 |
| Forks | fork gain (snapshots 6–8 days apart) | GitHub repository metadata | 15 |
| Contributions | merged PRs · unique PR authors · closed issues (bots excluded) | GitHub Search API | 25 |
| Usage | weekly package downloads · dependent packages | pypistats · npm · ecosyste.ms | 30 |
| Mentions | posts linking the repository · their points | Hacker News (Algolia) · GeekNews | 15 |

For example, in the week of 2026-11-01 `remotion-dev/remotion` ranked 70th by stars but 6th on the composite index, carried by about 3.5 million weekly downloads and a growing number of PR authors.

## Status (2026-11-14)

| Milestone | State |
|---|---|
| M0 · Foundation and API measurement | ✅ done |
| M1 · Signal collectors | ✅ done |
| M2 · Index and 12-week backfill (577 repositories, 13 weeks of index) | ✅ done |
| M3 · Weekly GitHub Actions run | 🔄 first scheduled run on 2026-11-16 |
| M4 · Website (Next.js on Vercel) | ✅ deployed |
| M5 · Blog drafts and Notion pages | 🔄 waiting for human review |
| M6 · Three weeks of observation | planned |
| M7 · Repository commentary | ✅ deployed |
| M8 · Post pictures (charts, repository pictures, diagrams) | 🔄 in drafts and Notion; first scheduled run on 2026-11-16 |

The live progress dashboard is at the top of [`docs/TASKS.md`](docs/TASKS.md).

## How it works

```
star-trend public data ──► candidates (AI repos: top 200 by weekly star gain + last week's TOP 10)
                             │
                             ▼
     collectors: forks · contributions · usage · mentions   (urllib, retries, rate limits)
                             │
                             ▼
     index: percentile within the week's candidates → weighted mean → contribution per signal
                             │
          ┌──────────────────┼──────────────────────────┐
          ▼                  ▼                          ▼
   site data (public)   angle notes A–D           repository commentary (AI)
   data/site/           (code picks repos)        evidence → Claude → gate → private repo
          │                                             │
          └────────────► Next.js site ◄─── fetched at build time (read-only token)
```

- **Index.** Each signal becomes a percentile rank among that week's candidates (ties take the middle rank). The index is the weighted mean. A signal with no value (no package, no fork snapshot yet) is **left out and its weight is redistributed** — it is never counted as zero. The contribution bar shows which signal made the rank.
- **Angle notes.** Code picks up to five repositories for each of four angles — A quiet strength (low stars, high use and contribution), B flash of attention (high stars or mentions, low use), C steady rise (index up four weeks in a row), D signal shift (attention share falls while use and contribution rise).
- **Code observations.** Every repository page shows observations computed from numbers only, such as downloads per star, the download trend against the 4-week average, the growth in PR authors, and whether one post made the whole mention signal.
- **Repository commentary.** For the week's TOP 10 and angle-note repositories, our code collects evidence: the README, releases, Hacker News posts with their largest comment threads, GeekNews posts, and web search results (Tavily). Claude Sonnet 5.5 writes a 3-line summary, the week's trend, what the repository is, where and why it drew attention, and what to watch, all as schema-constrained JSON. A code gate drops any claim without an evidence number, with a link, with a number that is not in the computed facts, or with banned wording.
- **Post pictures.** matplotlib draws four charts from computed numbers only: the TOP 10 rank trend over 12 weeks, signal contributions, a signal map (attention × real use) and a 12-week trend of signal shares and categories. Each commentary repository gets one explanatory picture with its source and rights: a README image (permissive licenses only), the owner's social preview, the homepage image, a web image search result, or, when none exists, a "how it works" diagram that Claude outlines from the README and code draws. Pictures go into the blog drafts and are uploaded to the Notion draft pages. When the commentary exists, each repository's "what is it" in the post and in the angle notes comes from it (README and web evidence), replacing the draft's "check the repository" sentence, and a hand-made cover image in `gen/cover.png` goes under the title.
- **Weekly run.** When star-trend's weekly run succeeds, its last step starts this repository's weekly run, so the radar begins as soon as its input is published. A Monday 05:00 UTC (14:00 KST) schedule stays as a fallback: it checks for star-trend's data every 5 minutes for up to 2 hours. If the week is already done, every later step is skipped, so the paid steps run once a week even when both runs happen.

## Engineering rules

- **Numbers come from code; text comes from the LLM.** Ranks, percentiles, the index, angle picks and observations are computed. The LLM only explains, and the gate enforces it.
- **Public repository, private writing.** Code and computed data are public. LLM-written drafts, commentaries and the Notion mapping live in a separate private repository; the site fetches the commentary copy at build time with a read-only token. A size guard blocks drafts from entering this repository.
- **Tests first, no network.** The default test run needs no network, no keys and no money; a fixture blocks sockets. Collectors are tested with recorded responses.
- **Rules are enforced by code.** A layer checker (core → clients → inputs / collectors / evidence → publish → app → cli; collectors never import each other; only `clients/transport.py` touches the network; only `clients/claude.py` imports the Anthropic SDK), control tests that prove each checker catches a violation, and a pre-commit hook: `ruff → mypy → pytest → size guard`.
- **Money has guards.** Every paid step has a `--dry-run`. A budget meter blocks an LLM call *before* it could exceed the per-run cap ($3).
- **External content is data.** README files, comments and web pages are wrapped as untrusted data and never treated as instructions.

## Getting started

Requirements: Python 3.12+ and a local clone of [github-ai-star-trend](https://github.com/daehyub71/github-ai-star-trend) next to this repository (or set `RADAR_STARTREND_DIR`).

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
git config core.hooksPath scripts/hooks
```

Environment variables — pass them to the command that needs them, **never commit them**:

| Variable | Used for |
|---|---|
| `GITHUB_TOKEN` | collectors, backfill, commentary evidence (read-only token) |
| `STARTREND_ANTHROPIC_API_KEY` | blog drafts and commentary (shared with star-trend on purpose) |
| `STARTREND_TAVILY_API_KEY` | web search for commentary evidence |
| `NOTION_TOKEN` | Notion draft pages |
| `RADAR_STARTREND_DIR` | optional — path to star-trend data |

```bash
python -m radar contract              # check the star-trend input contract (no network)
python -m radar weekly --dry-run      # expected calls for the last completed week
python -m radar weekly                # collect signals and compute the index
python -m radar site                  # site data under data/site/ (no network)
python -m radar blog --dry-run        # TOP 10 and angle-note drafts: worst-case cost only
python -m radar cards --dry-run       # repository commentary: targets, calls and cost only
python -m radar images               # post charts, repository cards and commentary merged into the drafts (no network, no LLM)
```

```bash
python -m pytest            # default gate: no network, no keys, no cost
python -m pytest -m live    # real API calls
cd web && npm ci && npm run dev   # site; reads ../data/site and, if present, ../.private/site-private
```

## Repository layout

```
radar/      core/ (weeks, normalize, index, angles, insights, evidence, charts_data, repo_images) · clients/ (transport, http, claude)
            inputs/ (star-trend contract) · collectors/ (forks, activity, packages, mentions)
            evidence/ (github, hn, geeknews, web, images) · publish/ (drafts, card, gate, notion, budget, charts)
            pipeline.py · backfill.py · site.py · blog.py · cards.py · images.py · cli.py
data/       candidates · signals · index · meta · site (public, computed)
web/        Next.js site (static generation)
docs/       SPEC · PLAN · DESIGN · TASKS · MEASURE (Korean)
scripts/    size guard, measurement scripts, git hooks
tests/      unit tests with recorded responses and synthetic fixtures
```

`.work/` (gitignored) holds caches. `.private/` (gitignored) is a clone of the private repository.

## Data notes

- Percentiles are **relative to that week's candidates**, not absolute scores.
- Weeks marked "backfilled" were collected later. Fork gains and dependent counts cannot be recovered for past weeks, so those signals are empty there.
- The usage signal exists only when a PyPI or npm package matches the repository. Many agent skills and apps have no package.
- AI classification and categories come from github-ai-star-trend (Claude). Past weeks are filtered with today's classification.
- Dependent counts use [ecosyste.ms](https://ecosyste.ms) data (CC BY-SA 4.0). Mentions use the Hacker News Algolia API and GeekNews listings.
- This project is not affiliated with GitHub, Anthropic, Tavily, Hacker News, GeekNews, ecosyste.ms, or Notion.

## License

Not decided yet.
