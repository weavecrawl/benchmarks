"""Drive one task with a Claude-subscription agent (claude CLI, no API key) through the brain's MCP.

Not a test module. `run_task(prompt, ...)` starts `claude -p` with only the brain's tools, a hook that refuses any call not on
head bench-server.b (head_guard.py), and returns the final text, every tool call with its client-side time, turns, cost and wall.
The claude CLI is a client only: the browser, the brain and every tool run on bench-server.
"""
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time

from head_guard import HEAD, OWN_SESSIONS_FILE, OWN_TABS_FILE, head_info

HERE = os.path.dirname(os.path.abspath(__file__))
# the product name is read from brand.json never typed here
with open(os.path.join(HERE, "..", "..", "..", "brand.json")) as _brand:
    SERVER = f"{json.load(_brand)['namespace']}-local"
PREFIX = f"mcp__{SERVER}__"
TOOLS = ",".join(PREFIX + t for t in ("goto", "read", "view", "click", "fill", "scroll", "tabs", "wait", "script", "maps", "session", "manage_head"))
_SYSTEM = ("You drive a browser only through the browser tools of the MCP server. Pass head=\"{head}\" on EVERY call to it "
          "(the default head is somebody's own Chrome and must never be touched). Never submit a final form, pay, post, "
          "send, delete or upload. When done, answer with the final line exactly as the task asks.")
SYSTEM = _SYSTEM.format(head=HEAD)
PERSON_DEVICE = (" This head is a person's own browser. Start with tabs action=\"open\" and then tabs action=\"focus\" on the tab_id it answers; work only in tabs you "
                 "opened, never list, read or touch the person's tabs, and close your tabs when done. Never log in, never type a password, an email address or any "
                 "detail the task did not give you; when the product says a person must act, stop and say so in your answer.")


def tools_for(head):
    """The tools the agent may use on `head`: all, except `manage_head` on a person's device (it restarts or changes their browser app)."""
    return TOOLS if not (head_info(head) or {}).get("person_device") else ",".join(t for t in TOOLS.split(",") if not t.endswith("manage_head"))


def system_for(head):
    return _SYSTEM.format(head=head) + (PERSON_DEVICE if (head_info(head) or {}).get("person_device") else "")


def workdir_for(out, name):
    """A task's own folder under the run's output (events.jsonl, guard.jsonl, mcp.json stay there; the folder is git-ignored)."""
    path = os.path.join(out, "tasks", name.replace("/", "_"))
    os.makedirs(path, exist_ok=True)
    return path


def run_task(prompt, model="haiku", max_turns=30, wall_s=420, workdir=None, env_extra=None, brain=None, evidence=False, head=HEAD):
    """`env_extra` is added to the CLI's environment only (the A1-lite bench passes the subscription token this way: the caller's own
    environment, and so every child of the caller, never holds it). `brain` = (url, token file) names the brain of this run (the paired
    bench runs two of them); without it the environment names one, as before. `evidence` keeps each call's whole result text and screenshots
    in the returned calls (for a judge); without it a call keeps the first 4000 characters and no screenshot, which is what the benches that save
    the calls to disk want. `head` is the one head the agent may use (see head_guard.py); on a person's device the tabs it opens are written to
    `own_tabs.txt` in `workdir` and the caller closes them."""
    work = workdir or tempfile.mkdtemp(prefix="bench-agent-")
    guard_log = os.path.join(work, "guard.jsonl")
    open(guard_log, "w").close()
    hook = {"type": "command", "command": f"{sys.executable} {os.path.join(HERE, 'head_guard.py')}"}
    settings = {"hooks": {ev: [{"matcher": PREFIX + ".*", "hooks": [hook]}] for ev in ("PreToolUse", "PostToolUse")}}
    settings_path = os.path.join(work, "settings.json")
    with open(settings_path, "w") as f:
        json.dump(settings, f)
    mcp_path = os.path.join(work, "mcp.json")
    with open(os.open(mcp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump({"mcpServers": {SERVER: _brain_server(brain)}}, f)
    cmd = ["claude", "-p", "--mcp-config", mcp_path, "--strict-mcp-config", "--model", model, "--output-format", "stream-json", "--verbose", "--tools", "",
           "--allowedTools", tools_for(head), "--permission-mode", "dontAsk", "--no-session-persistence", "--max-turns", str(max_turns),
           "--setting-sources", "project", "--settings", settings_path, "--append-system-prompt", system_for(head), prompt]
    env = dict(os.environ, **(env_extra or {}), BENCH_GUARD_LOG=guard_log, BENCH_HEAD=head, BENCH_OWN_TABS=os.path.join(work, OWN_TABS_FILE),
               BENCH_OWN_SESSIONS=os.path.join(work, OWN_SESSIONS_FILE))
    t0 = time.time()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True, env=env, cwd=work, start_new_session=True)
    events, timed_out = [], False
    events_log = open(os.path.join(work, "events.jsonl"), "w")
    import threading
    killer = threading.Timer(wall_s, lambda: os.killpg(p.pid, signal.SIGKILL))
    killer.start()
    try:
        for line in p.stdout:
            events_log.write(line)
            events_log.flush()
            try:
                events.append((time.time() - t0, json.loads(line)))
            except ValueError:
                pass
    finally:
        killer.cancel()
    p.wait()
    events_log.close()
    wall = time.time() - t0
    timed_out = p.returncode is not None and p.returncode < 0
    result = next((e for _, e in reversed(events) if e.get("type") == "result"), {})
    init = next((e for _, e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    calls = _calls(events, guard_log, evidence)
    return {"final": result.get("result") or "", "ok": result.get("subtype") == "success" and not result.get("is_error"),
            "subtype": result.get("subtype"), "is_error": bool(result.get("is_error")), "turns": result.get("num_turns"), "cost_usd": result.get("total_cost_usd"),
            "agent_ms": result.get("duration_ms"), "wall_ms": wall * 1000, "timed_out": timed_out, "calls": calls,
            "refused": [c for c in calls if not c["allowed"]], "stderr": (p.stderr.read() or "")[-300:],
            "returncode": p.returncode, "usage": result.get("usage"), "model": init.get("model") or next(iter(result.get("modelUsage") or {}), None)}


def _brain_server(brain=None):
    """The brain the agent talks to. `brain` = (url, token file) names it; else `BENCH_MCP_URL` + `BENCH_MCP_TOKEN_FILE` name a brain of
    their own (a scratch brain reached by an ssh tunnel); otherwise the person's own claude MCP entry (URL and headers helper, no key inside),
    so the agent sees that server only."""
    if brain:
        url, token_file = brain
        with open(token_file) as f:
            return {"type": "http", "url": url, "headers": {"Authorization": "Bearer " + f.read().strip()}}
    url = os.environ.get("BENCH_MCP_URL")
    if url:
        with open(os.environ["BENCH_MCP_TOKEN_FILE"]) as f:
            return {"type": "http", "url": url, "headers": {"Authorization": "Bearer " + f.read().strip()}}
    with open(os.path.expanduser("~/.claude.json")) as f:
        return json.load(f)["mcpServers"][SERVER]


# The product holding an act for a person, as the answer says it: a tool error `[code]` (a fill with a judgement field raises `[needs_human]`).
# Not the bare word: a read carries `"needs_human": false` in its bot-wall block on every call.
HELD = re.compile(r'\[(submit_guarded|needs_human|no_head_alive|awaiting_approval)\]')


def _results(events):
    """tool_use_id -> (the text of its result, its screenshots as {media_type, data})."""
    out = {}
    for _, e in events:
        if e.get("type") == "user" and isinstance(e["message"].get("content"), list):
            for c in e["message"]["content"]:
                if c.get("type") == "tool_result":
                    body = c.get("content")
                    parts = [{"type": "text", "text": body}] if isinstance(body, str) else body or []
                    out[c["tool_use_id"]] = (" ".join(x["text"] for x in parts if x.get("type") == "text"),
                                             [{"media_type": x["source"]["media_type"], "data": x["source"]["data"]} for x in parts
                                              if x.get("type") == "image" and x.get("source", {}).get("type") == "base64"])
    return out


# A bot wall the product reports as blocking the page now (a captcha, a challenge page): one JSON object with `needs_human` true and `kind`
# `load_time`, the product's own rule (core.ask_human._wall.blocks). Not the fill reasons map, whose `needs_human` key holds a sentence, not an
# overlay (false) and not a captcha that fires at submit (`submit_time`): the page is the site's own and the agent can read it.
WALL = re.compile(r'"needs_human":\s*true')


def _json_objects(text):
    """Every JSON object in `text`, nested ones too."""
    decoder, i = json.JSONDecoder(), text.find("{")
    while i >= 0:
        try:
            yield decoder.raw_decode(text, i)[0]
        except ValueError:
            pass
        i = text.find("{", i + 1)


def _wall_word(answer):
    """The kind of bot wall an answer reports ('recaptcha', 'cloudflare_turnstile', ...), or None."""
    if not WALL.search(answer):
        return None
    return next((o.get("blocked") or "needs_human" for o in _json_objects(answer) if isinstance(o, dict) and o.get("needs_human") is True and o.get("kind") == "load_time"), None)


# Why a site's page was not served, as a goto (or the error page's note in a read) says it: the site cannot be reached or did not finish loading in the head's bound.
# Not `load_failed` (the fallback for any failure, ours too), `tab_closed` or `url_blocked`, and a 404/410 is reported too: `agent_rules.site_fault` keeps it only for an address the site gave.
SITE_DOWN = ("dns", "refused", "cert", "timeout")


def _fault_word(answer):
    """The site fault an answer reports ('http_503', 'dns', 'refused', 'cert', 'timeout', 'error_page'), or None. Only an object with a `loaded` key counts:
    a goto's answer or the error page's note, not a page's own text that happens to hold a status."""
    for o in _json_objects(answer):
        if not isinstance(o, dict) or "loaded" not in o:
            continue
        status = o.get("status")
        if isinstance(status, int) and (status >= 500 or status in (404, 410)):
            return f"http_{status}"
        if o["loaded"] is False and o.get("reason") in SITE_DOWN:
            return o["reason"]
        if o.get("error_page") is True:
            return "error_page"
    return None


def _errored(events):
    """tool_use_id -> True when its result was an error."""
    return {c["tool_use_id"]: bool(c.get("is_error")) for _, e in events if e.get("type") == "user" and isinstance(e["message"].get("content"), list)
            for c in e["message"]["content"] if c.get("type") == "tool_result"}


def _held_word(answer):
    found = HELD.search(answer)
    return found.group(1) if found else None


RESULT_CHARS = 200_000  # of one result's text kept with `evidence`; the caller keeps only what it needs in a row


def _calls(events, guard_log, evidence=False):
    """Every call to the brain: tool, args, the hook-to-hook time (the tool's own time), whether the guard allowed it, `held`:
    which human-step word its answer carries (the product held the act for a person), or None, and the result's text and screenshots."""
    uses = {}
    for _, e in events:
        if e.get("type") == "assistant":
            for c in e["message"]["content"]:
                if c["type"] == "tool_use":
                    uses[c["id"]] = {"tool": c["name"].replace(PREFIX, ""), "args": c["input"]}
    pre, post = {}, {}
    with open(guard_log) as f:
        for line in f:
            r = json.loads(line)
            (pre if r["phase"] == "PreToolUse" else post)[r["id"]] = r
    answers = _results(events)
    errors = _errored(events)
    out = []
    for i, u in uses.items():
        a, b = pre.get(i), post.get(i)
        text, images = answers.get(i, ("", []))
        out.append({"tool": u["tool"], "args": u["args"], "allowed": a["allowed"] if a else True,
                    "ms": (b["t"] - a["t"]) * 1000 if a and b else None,
                    "held": _held_word(text), "wall": _wall_word(text), "fault": _fault_word(text), "error": errors.get(i, False), "person_tab": bool(b and b.get("person_tab")),
                    "text": text[:RESULT_CHARS if evidence else 4000], "images": images if evidence else []})
    return out
