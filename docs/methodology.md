# How the test works

## In short
Two AI models each tried the same 40 tasks on real websites. A separate AI checked every answer. Nothing was tuned per site. Full details and every task result: [Haiku report](results/2026-10-24/webvoyager-haiku-summary.md), [Sonnet report](results/2026-10-24/webvoyager-sonnet-summary.md).

| Step | What happens |
| :-- | :-- |
| **Fixed tasks** | 40 tasks from WebVoyager (the public `browser-use/eval` set, commit `0ee7ae0`), picked from 588 by a published seed (`a1-lite-2026-10-11`). Same 40 for both runs. 15 sites. |
| **Live sites** | Real websites, on the day. No saved copies. Results move with the sites. |
| **The agent** | An AI model (Haiku, then Sonnet) that can only use WeaveCrawl's browser tools. Fresh start for every task. Up to 25 steps and 5 minutes per task. |
| **Bot walls** | If a site shows a "prove you are human" check, the task is marked **blocked**. The test never solves it. Blocked tasks count as misses in the raw score and are shown separately. |
| **The judge** | A second AI (Haiku) reads the agent's answer and what the agent saw. Three votes; two "success" votes pass. Short exact facts are checked by simple matching instead. |
| **Live page wins** | The judge goes by what the live page shows. Where the old reference answer is out of date, the live page decides, and the task is flagged. Both reports list these tasks. |
| **No guessing** | A pass needs real browser use. An answer from memory fails. |
| **Re-dated tasks** | Five tasks with past dates (flights, hotels) were moved forward two years. Listed in the reports. |
| **No reruns** | Zero reruns happened. A task the agent completed wrongly is never run again. |

## Scores
- **Raw:** passed ÷ 40.
- **Doable today:** leaves out 2 Allrecipes tasks marked, before the run, as not doable from our server address.
- **Unblocked:** also leaves out tasks a bot wall stopped.

## Limits
Live sites change, the judge is an AI (it reads text and screenshots, not a human), and the judge is not the one used in the original WebVoyager paper or by other published scores. Treat the score as a solid snapshot, not an exact constant. Each run was one pass; ranges are in the reports.

## Machine
One shared server (AMD Ryzen 7 3700X), 6 CPU cores and 3 GB memory reserved per run, real Chrome 150. Times are the agents' working time added up over the 40 tasks (includes site load time); the whole Haiku run, with judging, took about 35 min. Neither run timed individual calls.
