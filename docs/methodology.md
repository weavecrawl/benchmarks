# How it works

## In short
An AI model gets a plain-language task about a real, live website ("find the cheapest flight...", "what does this GitHub issue say..."). It can only use WeaveCrawl's browser tools. A second AI checks its answer. Nothing is tuned per site. We ran the same 40 tasks several times, with two models (Haiku, the cheaper one, and Sonnet, the stronger one) and in three places (a server browser, a person's own Chrome, the WeaveCrawl desktop app).

- Every task and its reference answer: [tasks/](../tasks/README.md)
- The result of every task in every run, with the reason: [results/per-task-results.md](../results/per-task-results.md)
- The code that ran it: [harness/](../harness/README.md)

## The benchmark we used
**WebVoyager** is a public set of tasks on live websites, made for testing AI web agents. We use the copy kept by `browser-use/eval` (commit `0ee7ae0`, Apache-2.0): 588 tasks after it drops the ones that cannot be done, on 15 sites. Many published products report a WebVoyager score, which is why we used it. We run a fixed sample of 40 (we call it A1-lite), because every run uses a paid model subscription.

## How a run works

| Step | What happens |
| :-- | :-- |
| **Fixed tasks** | 40 of the 588 tasks, picked by a published seed (`a1-lite-2026-10-11`): 2 per site, and the 10 left over go to the 10 sites that rank first by a hash of the seed. The code refuses to start if the downloaded data picks different tasks. Same 40 in every run. |
| **The agent** | The `claude` command-line agent, with only WeaveCrawl's tools (no other web access). Fresh start for every task. It is told to answer from what it reads on the web, not to log in, buy, post or submit anything, and to end with one line, `ANSWER: ...`. At most **25 steps and 5 minutes per task**. |
| **Live sites** | Real websites, on the day. No saved copies. Results move with the sites. |
| **The judge** | A second AI (Haiku) reads the task, the reference answer, the agent's answer, the page text the agent read and the last screenshots it saw. **Three votes; two "success" votes pass.** Where the reference is a short exact fact, plain matching decides instead of the judge. |
| **What counts as a pass** | The answer does what the task asks and meets every condition in it, and the agent really used the browser. An answer from memory fails. |
| **Reruns** | A task is run again (at most 3 times) only when the attempt broke for a reason of the model or the machine: an API error, a rate limit, a crash, no tool call before the time limit. A task the agent finished with a wrong answer is never run again. |

## What we changed from WebVoyager

WebVoyager was written in 2024 and its tasks and answers age. These are all the changes, so a result can be repeated:

1. **A sample of 40, not all tasks.** Chosen by the published seed above, not by us.
2. **Dates moved forward.** Five tasks name a date that is already past (flights and hotels, for example "March 20, 2025"). We move every date in the question forward by the same whole number of years, the smallest number that puts the earliest date at least 30 days after the run. All five moved forward two years. The reference answer for such a task is treated as possibly out of date.
3. **The live page wins over an old reference answer.** Where the reference answer is marked as true only on the day it was written, the judge goes by what the live page shows now, and the report flags each task that passed this way. Where the reference is a stable fact, the answer must match it.
4. **One broken reference.** Allrecipes--5 asks for a recipe with more than 1,000 reviews, but its reference answer has 818. The judge is shown no reference for that task.
5. **A different judge.** The original paper used a screenshot-reading GPT-4V judge, and browser-use used a hand-corrected one. Ours is Haiku with three votes, reading page text plus the last screenshots. Our scores are not comparable with scores from other setups.
6. **A different agent.** Claude with WeaveCrawl's tools, not the paper's screenshot-clicking agent.
7. **Bot walls counted apart.** If a site shows a "prove you are human" check, the task is marked *blocked*; the test never solves it. It counts as a miss in the raw score and is shown separately.
8. **Broken sites counted apart.** If a task's own site answers with a server error or an error page, is unreachable, or never finishes loading, and no answer passed, it is a *site fault*. It counts as a miss in the raw score and is left out of the headline score. (No task was marked this way in any published run.)
9. **Held for a person, by design.** On a person's own device, if the product stops to ask a person (a submit, a purchase, an add to cart, a login), the task is *held*. The test never forces it. It counts as a miss in the raw score and is left out of the headline score. One task (Amazon--15) is held in every run on a person's device.
10. **Two tasks fixed as not doable.** Before the first run, two Allrecipes tasks (Allrecipes--32 and Allrecipes--5) showed an IP block on every page from our server's address (HTTP 402). They are named in the reports. A not-doable task that passed anyway stays in the score; one that did not pass is left out of the headline score.
11. **One run per setup.** No averaging over repeats.

## Scores

Every report prints these three, and each task left out is named with its reason in [the per-task results](../results/per-task-results.md).

- **Headline score ("Unblocked" in the reports):** tasks passed ÷ tasks, **without** the tasks a bot wall blocked, a broken site stopped, or that were held for a person by design, and without the not-doable Allrecipes task that did not pass. Nothing else is left out.
- **Raw:** passed ÷ 40. Every task, as run.
- **Doable today:** raw, without the not-doable tasks only.

Ranges are 95% intervals; with 40 tasks they are wide (roughly ±12 points).

## Limits
Live sites change; the judge is an AI (it reads text and screenshots, not a human); the judge and the agent differ from the original WebVoyager; the summaries cut long judge reasons short; each setup was run once. Treat a score as a solid snapshot, not an exact constant. Runs on a person's own device are not directly comparable with the server-browser runs (a real browser with its own sign-ins).

## How to run it yourself
See [harness/README.md](../harness/README.md): what you need (a running WeaveCrawl, the `claude` agent and a token, Python with `mcp`, `playwright`, `tiktoken`) and the exact command. Timing: about 25 to 35 minutes for 40 tasks, on a machine that is not busy.

## Machine
The server-browser runs: one shared server (AMD Ryzen 7 3700X), 6 CPU cores and 3 GB memory reserved per run, real Chrome 150. The Chrome-extension and desktop-app runs: a person's Mac, driven through that person's own browser or app. Times are the agent's working time added up over the 40 tasks (includes site load time). No single call was timed.
