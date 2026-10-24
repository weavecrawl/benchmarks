# Where others stand (published claims only)

We did **not** run any competitor. The rows below are what each vendor or leaderboard has published, with the source. Setups differ (different models, task sets, judges, and removed tasks), so **these are context, not a ranking**.

| Product | Published WebVoyager score | Source | How their setup differs |
| :-- | :--: | :-- | :-- |
| **WeaveCrawl** (this repo) | 65% (Haiku), 72.5% (Sonnet) raw; 72–78% without blocked sites | [Haiku run](../results/2026-10-24/webvoyager-haiku-summary.md), [Sonnet run](../results/2026-10-24/webvoyager-sonnet-summary.md) | 40-task sample, live sites, bot-walled tasks counted as misses, one run, AI judge on page text |
| browser-control (Fable 5) | 99.19% (self-reported) | [Steel leaderboard](https://leaderboard.steel.dev/leaderboards/webvoyager), updated 2026-10-11 | Their own harness and judge; see [their repo](https://github.com/omxyz/webvoyager) |
| Browser Use | 89.1% | [Browser Use technical report](https://browser-use.com/posts/sota-technical-report) | Their own run on 586 tasks after removing 55 they judged unsolvable or outdated. A separate team (Notte) reported it could not replicate this. |
| Skyvern | 85.85% | [Skyvern blog](https://www.skyvern.com/blog/skyvern-2-0-webvoyager-benchmark-results/) | Their own run, their own setup |
| OpenAI Operator | 87% | [Steel leaderboard](https://leaderboard.steel.dev/leaderboards/webvoyager) (self-reported by OpenAI) | Different agent and judge |
| H Company Surfer-H (with Holo1) | 92.2% | [H Company release notes](https://hub.hcompany.ai/changelog/surferhreleasenotes) | Their own agent and model |

The leaderboard itself warns that WebVoyager is not fully standardized across submissions and that small gaps can come from setup choices. Our score is lower than these headline numbers, but the setups are not the same, so the gap does not show a product difference.

Figures taken from vendors were last read on 2026-10-24 and may have changed.
