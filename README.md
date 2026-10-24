<img src="docs/banner.svg" alt="WeaveCrawl published benchmark results" width="100%" />

# WeaveCrawl Benchmarks

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Published results for [WeaveCrawl](https://weavecrawl.com).** Every number here links to the run report it came from.

## In plain words

WeaveCrawl lets an AI assistant use a real web browser the way a person does: open a site, read it, click, search, and report back. We tested it on **40 everyday tasks on real, live websites** (find a flight price, check a GitHub issue, look up a recipe or a course). The tasks are a fixed sample of a well-known public test called WebVoyager.

| | Cheapest AI model (Haiku) | Stronger AI model (Sonnet) |
| :-- | :--: | :--: |
| **Tasks finished correctly** | **26 of 40 (65%)** | **29 of 40 (72.5%)** |
| Same, ignoring sites that blocked us with a "prove you are human" wall | 72% | 78% |
| Agent working time for all 40 tasks | 25 min | 16 min |
| Average time per task | about 38 s | about 24 s |
| Cost for all 40 tasks | $0.35 | $3.05 |
| Average cost per task | about $0.01 | about $0.08 |
| Report | [Haiku run](results/2026-10-24/webvoyager-haiku-summary.md) | [Sonnet run](results/2026-10-24/webvoyager-sonnet-summary.md) |

**What this means:** with WeaveCrawl, roughly 3 in 4 real web tasks get done on their own, in about half a minute each and for a cent or a few cents. The cheaper model is already usable; the stronger one finishes more tasks and runs faster. Cost is the price the AI vendor's tool reports for the model use; it was not billed (run on a subscription).

## How to read this

| Term | Meaning |
| :-- | :-- |
| **Raw score** | All 40 tasks, counted as run. The honest headline. |
| **Without blocked sites** | Some sites show a "prove you are human" check. A person can pass it; our test never tries to. Those tasks are counted as misses in the raw score and left out here. Haiku hit 4 such walls, Sonnet 3. |
| **Range (95%)** | With only 40 tasks, a score is not exact. Raw: Haiku 49.5–77.9%, Sonnet 57.2–83.9%. The two scores overlap, so we do not claim one model is clearly better. |
| **Live sites** | Websites change daily. A re-run next week can score differently. |
| **Judge** | A second AI checks each answer against the live page, not against old answers. See [methodology](docs/methodology.md). |

## What we did not test

- **Only the server browser** (WeaveCrawl running its own Chrome on our server). Not the Chrome extension or the desktop app.
- **One run each.** Each agent did the 40 tasks once. No averaging over repeats.
- **40 of 588 tasks.** A small, fixed sample, chosen by a published random seed.
- **No head-to-head with other products.** We did not run any competitor ourselves. See [competitor matrix](docs/competitor_matrix.md).
- **WebVoyager is close to "solved" across the industry.** Published scores for leading products run from about 86% to 99% (self-reported; see [Steel leaderboard](https://leaderboard.steel.dev/leaderboards/webvoyager)), so it separates leaders poorly. Those scores use other setups and other judges, so they are **not directly comparable** with ours.
- **Speed tests (startup, payload size, replaying a saved route) are not in this release.** Earlier figures for those could not be re-run, so they were removed.

## Files

[Methodology](docs/methodology.md) · [Competitor matrix](docs/competitor_matrix.md) · [Data](data/official_benchmarks.json) · [Full per-task reports](results/2026-10-24/) · [Print the numbers](scripts/reproduce_benchmarks.py)

`python3 scripts/reproduce_benchmarks.py` prints the published numbers offline. It does not re-run the benchmark.

## License

MIT, see [LICENSE](LICENSE). More at [weavecrawl.com](https://weavecrawl.com).
