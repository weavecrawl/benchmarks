# agent_driver

Drives one task with a person's Claude subscription (`claude -p`, no API key) through the brain's MCP. A client only: the browser and every tool run in the brain on bench-server. Used by `webgames/` and `webvoyager/`.

- `driver.py::run_task(prompt, model, max_turns, wall_s)` returns the final text, turns, cost the CLI reports, wall time, and every call to the brain with its client-side time (hook to hook).
- `head_guard.py` is a Claude Code hook (PreToolUse and PostToolUse). It refuses any call to the brain that does not name `head="bench-server.b"` (or the head in `BENCH_HEAD`; on a person's device it also keeps the bench to its own tabs, see the file) (the default head is a person's own Chrome), refuses `ask_human` (it notifies a person's devices), and writes one line per call with a clock. `test_head_guard.py` pins the rule.
- Only the tools in `driver.TOOLS` are allowed; the agent sees the brain's MCP server only (`--strict-mcp-config`).
- `BENCH_MCP_URL` + `BENCH_MCP_TOKEN_FILE` point the agent at a scratch brain (reached by `ssh -N -L 47875:127.0.0.1:47875 bench-server`); without them it uses the person's own MCP entry for the brain (`<ns>-local`) from `~/.claude.json`.
- `BENCH_SSH_HOST=bench-server` turns on `gate.py`: before each task it waits while the server has under 4 GB available.
- Kill is by process group at the wall cap. `events.jsonl` (every CLI event) stays in the task's temp folder.

Test: `cd packages/core && python -m pytest -q tests/bench/agent_driver/test_head_guard.py` (on bench-server).
