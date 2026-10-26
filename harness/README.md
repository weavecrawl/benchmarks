# Benchmark harness

The code that ran the published WebVoyager results (the "agent suite"), copied from the WeaveCrawl source tree. WeaveCrawl itself (the product) is not here; the harness drives a running WeaveCrawl through its public tool interface (MCP), like any AI assistant would.

## What is in the folder

| Path | What it does |
| :-- | :-- |
| `benchmarks/run.py` | The command you start. Checks the machine, runs the suite, writes the run folder (`env.json`, `raw.json`, `summary.md`). |
| `benchmarks/agent.py` | The agent suite: loads the 40 tasks, runs one agent per task, calls the judge, decides pass / fail / blocked / held. |
| `benchmarks/agent_rules.py` | The fixed rules: re-dating a question, the exact-match check, how a failed attempt is classed (bot wall, model or infrastructure problem, wrong answer). |
| `benchmarks/agent_tasks.json` | The fixed input: which 40 tasks, the seed, the agent prompt, the judge prompt, the models and every cap. |
| `benchmarks/summarize.py` | Makes the report (`summary.md`) from `raw.json` and `env.json`, and checks a run is valid. |
| `benchmarks/quiet.py`, `cases.json` | Machine-quiet check and shared settings that `run.py` reads. |
| `benchmarks/browsecomp.py`, `corpus.py`, `corpus_site.py`, `suite_*.py` | Imported by `run.py` and `summarize.py` but **not used by the agent suite**. The other suites they belong to (page reading, forms, replay, delegate) are not supported here: they need parts of the private source tree. |
| `tests/bench/agent_driver/` | Starts the `claude` command-line agent with only the WeaveCrawl tools, and the guard that keeps it on the bench's own tabs. Its test (`test_head_guard.py`) pins that guard. |
| `tests/field/runner/` | Small helpers `run.py` imports (`run_cases.py`, `brand.py`, `checks.py`, `person.py`). |
| `brand.json` | The product name the helpers read (`weavecrawl`). |

## What you need

- A running WeaveCrawl with a browser head you may drive (a server browser, the Chrome extension, or the desktop app), its address, and a way to print its agent key.
- The `claude` command-line agent, logged in, and a token for it.
- Python 3.12 with `mcp`, `playwright` and `tiktoken`.
- Internet access: the tasks run on live sites, and the task data is downloaded from `browser-use/eval` at a pinned commit; the run stops if the downloaded files differ from the checksums in `agent_tasks.json`.

## Run it

```
export CLAUDE_CODE_OAUTH_TOKEN=...            # or BENCH_TOKEN_CMD="<command that prints it>"
export BENCH_MCP_TOKEN_CMD="<command that prints the WeaveCrawl agent key>"
python3 harness/benchmarks/run.py --scratch ~/bench-scratch --suites agent \
    --agent-model sonnet \
    --agent-head <device>.<mode> --agent-brain-url http://127.0.0.1:<port>
```

`<device>.<mode>` is the head you drive: mode `a` the Chrome extension, `b` the server browser, `c` the desktop app. `--agent-limit N` runs only the first N tasks (a try; the report marks it as not a result). `--agent-model` is `haiku` or `sonnet`; the judge is always Haiku.

The run takes about 25 to 35 minutes for 40 tasks and writes `~/bench-scratch/bench-<time>-<id>/summary.md`. Run it on a machine that is not busy: `run.py` refuses a busy machine unless you pass `--allow-busy`, and then the run is marked as such.

## Differences from the harness that produced the published runs

The published runs used the version before this copy. Changes made for this copy, none of which touch how a task is run or judged:

- Machine, device and key names of the original setup were removed. `bench-server` stands for the device name of your own server head; the product name is read from `brand.json`.
- The default for the token reader command was removed: set `CLAUDE_CODE_OAUTH_TOKEN` or `BENCH_TOKEN_CMD` (the run stops with a clear message if neither is set).
- Internal change-record numbers in comments were removed.

`agent_tasks.json` and `cases.json` are copied unchanged, so their checksums in the published reports still match.
