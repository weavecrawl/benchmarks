<img src="docs/banner.svg" alt="WeaveCrawl published benchmark results" width="100%" />

# WeaveCrawl Benchmarks

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Published results for [WeaveCrawl](https://weavecrawl.com).** Every number here links to the run report it came from.

## In plain words

WeaveCrawl lets an AI assistant use a real web browser the way a person does: open a site, read it, click, search, and report back. We tested it on **40 everyday tasks on real, live websites** (find a flight price, check a GitHub issue, look up a recipe or a course). The tasks are a fixed sample of a well-known public test called WebVoyager.

**Latest results: 2026-10-25** (after two fixes, see below)

| | Cheapest AI model (Haiku) | Stronger AI model (Sonnet) |
| :-- | :--: | :--: |
| **Tasks finished correctly** | **26 of 40 (65%)** | **32 of 40 (80%)** |
| Same, ignoring sites that blocked us with a "prove you are human" wall | 76.5% (26 of 34) | 88.9% (32 of 36) |
| Agent working time for all 40 tasks | 22 min | 15 min |
| Average time per task | about 33 s | about 22 s |
| Cost for all 40 tasks | $0.29 | $3.06 |
| Average cost per task | about $0.01 | about $0.08 |
| Report | [Haiku run](results/2026-10-25/webvoyager-haiku-summary.md) | [Sonnet run](results/2026-10-25/webvoyager-sonnet-summary.md) |

**What this means:** with WeaveCrawl, the stronger model finishes 4 in 5 real web tasks on its own, and about 9 in 10 on sites that let a program in. It takes about 22 seconds and under 10 cents per task. The cheaper model finishes about 2 in 3 for about a cent each, so it is already usable. Cost is the price the AI vendor's tool reports for the model use; it was not billed (run on a subscription).

**What changed since the first run (2026-10-24):** WeaveCrawl now waits properly for a page to finish loading its content, and Amazon's "automated access" page now counts as a bot wall instead of an ordinary failure. Same 40 tasks, same setup.

| History | Haiku | Sonnet | Reports |
| :-- | :--: | :--: | :-- |
| 2026-10-25 (latest) | 26 of 40 (65%) | 32 of 40 (80%) | [Haiku](results/2026-10-25/webvoyager-haiku-summary.md), [Sonnet](results/2026-10-25/webvoyager-sonnet-summary.md) |
| 2026-10-24 (first run) | 26 of 40 (65%) | 29 of 40 (72.5%) | [Haiku](results/2026-10-24/webvoyager-haiku-summary.md), [Sonnet](results/2026-10-24/webvoyager-sonnet-summary.md) |

Sonnet went from 72.5% to 80% on the same tasks. Haiku's raw score stayed at 65%; more of its tasks were recognised as bot walls (6, was 4), so its score without blocked sites rose from 72.2% to 76.5%.

## In your own Chrome

We also ran the same 40 tasks with the stronger model (Sonnet) inside a person's own Chrome, through the WeaveCrawl Chrome extension, on 2026-10-25 (after the release that day).

- **Tasks finished correctly: 32 of 40 (80%)**, range 65.2–89.5%. On the server browser the same tasks also scored 80%.
- Ignoring sites we could not do (2 tasks) and the one task held for a person (Amazon add to cart, held on purpose): **32 of 37 (86.5%)**, range 72.0–94.1%.
- 7 tasks were marked wrong by the judge. The run's own validity check passed.
- Working time for all 40 tasks: 27 min (about 41 s per task).
- Cost: $3.62 equivalent (run on a subscription, not billed).

One run only. The numbers are not directly comparable with the server-browser table above (a real browser with its own sign-ins). Report: [Sonnet in Chrome](results/2026-10-25/webvoyager-sonnet-chrome-summary.md).

## In the desktop app

We also ran the same 40 tasks with the stronger model (Sonnet) in the WeaveCrawl desktop app, on a person's own Mac, on 2026-10-26 (same release as the 2026-10-25 runs).

- **Tasks finished correctly: 33 of 40 (82.5%)**, range 68.0–91.3%.
- Ignoring the one task held for a person (Amazon add to cart, held on purpose): **33 of 39 (84.6%)**, range 70.3–92.8%.
- 5 tasks were marked wrong by the judge. 1 task (Coursera) gave no final answer before the time limit. The run's own validity check passed.
- Working time for all 40 tasks: 29 min (about 44 s per task).
- Cost: $3.42 equivalent (run on a subscription, not billed).

One run only. The numbers are not directly comparable with the server-browser table above (a real Mac with its own sign-ins). Report: [Sonnet in the desktop app](results/2026-10-26/webvoyager-sonnet-desktop-summary.md).

### Latest desktop run (newer release)

Same 40 tasks, same model, same Mac, later on 2026-10-26, with a newer release where opening a page also returns its outline in the same step.

- **Tasks finished correctly: 33 of 40 (82.5%)**, range 68.0–91.3%.
- Without the tasks blocked by a bot wall or a site fault: **33 of 38 (86.8%)**, range 72.7–94.2%.
- 6 tasks were marked wrong by the judge. 1 task (Amazon add to cart) was held for a person, on purpose. The run's own validity check passed.
- What changed: same score, about 8% fewer steps (302 instead of 328) and about 15% less time.
- Working time for all 40 tasks: 25 min (about 37 s per task).
- Cost: $3.34 equivalent (run on a subscription, not billed).

One run only, not directly comparable with the server-browser table above. Report: [Sonnet in the desktop app, latest run](results/2026-10-26/webvoyager-sonnet-desktop-2-summary.md).

## How to read this

| Term | Meaning |
| :-- | :-- |
| **Raw score** | All 40 tasks, counted as run. The honest headline. |
| **Without blocked sites** | Some sites show a "prove you are human" check. A person can pass it; our test never tries to. Those tasks are counted as misses in the raw score and left out here. On 2026-10-25 Haiku hit 6 such walls, Sonnet 4 (two of them are the Allrecipes tasks we marked as not doable from our server address). |
| **Range (95%)** | With only 40 tasks, a score is not exact. Raw: Haiku 49.5–77.9%, Sonnet 65.2–89.5%. The two ranges still overlap, so we do not claim one model is clearly better. |
| **Live sites** | Websites change daily. A re-run next week can score differently. |
| **Judge** | A second AI checks each answer against the live page, not against old answers. See [methodology](docs/methodology.md). |

## What we did not test

- **One run each per day.** Each agent did the 40 tasks once on 2026-10-24 and once on 2026-10-25. No averaging over repeats.
- **40 of 588 tasks.** A small, fixed sample, chosen by a published random seed.
- **No head-to-head with other products.** We did not run any competitor ourselves. See [competitor matrix](docs/competitor_matrix.md).
- **WebVoyager is close to "solved" across the industry.** Published scores for leading products run from about 86% to 99% (self-reported; see [Steel leaderboard](https://leaderboard.steel.dev/leaderboards/webvoyager)), so it separates leaders poorly. Those scores use other setups and other judges, so they are **not directly comparable** with ours.
- **Speed tests (startup, payload size, replaying a saved route) are not in this release.** Earlier figures for those could not be re-run, so they were removed.

## Files

[Methodology](docs/methodology.md) · [Competitor matrix](docs/competitor_matrix.md) · [Data](data/official_benchmarks.json) · [Full per-task reports](results/2026-10-25/) · [desktop app run](results/2026-10-26/) · [first run](results/2026-10-24/) · [Print the numbers](scripts/reproduce_benchmarks.py)

`python3 scripts/reproduce_benchmarks.py` prints the published numbers offline. It does not re-run the benchmark.

## License

MIT, see [LICENSE](LICENSE). More at [weavecrawl.com](https://weavecrawl.com).
