"""The agent suite of the bench door (A1-lite): a fixed 40-task subset of WebVoyager, one Claude Haiku agent driving a scratch brain.

    python3 benchmarks/agent.py select --data DIR      print the task ids the published seed picks from the pinned data in DIR
    python3 benchmarks/run.py --scratch DIR --suites agent [--agent-limit N]      run it (bench-server only, see harness/README.md)

Not a command of its own: `run.py` calls `run_suite`. What is fixed, in `benchmarks/agent_tasks.json` (its sha256 is in env.json):
the source commit and the sha256 of each source file, the seed and the 40 ids it picks, the agent's prompt, the judge's rubric,
the model aliases and every cap. The suite refuses to start when the data it downloads, or the ids the seed picks from it, differ.

One attempt = a fresh scratch brain + one `claude -p` run with only the brain's tools (tests/bench/agent_driver). An attempt that
failed for a model or infra reason (agent_rules.classify) is run again, at most 3 times; a task the agent completed wrong never is.
A completed attempt is read by a deterministic check where the reference is a short exact fact, otherwise by three Haiku judge votes
(two SUCCESS pass) that see the page text the agent read and its last screenshots; every verdict is saved with its reason. A question that
names a date already past is moved ahead (`agent_rules.redate`). A captcha is never solved: the task is marked blocked.
The subscription token comes from the environment or a reader command (claude_token) and is handed to the claude child only; it is never printed or written.

`--agent-head <device>.<mode>` with `--agent-brain-url` (target_of) runs the same tasks on a named head of a brain that is already running, for
example a person's Chrome extension (`.a`) or desktop app (`.c`): no scratch brain, the brain's key from the reader command BENCH_MCP_TOKEN_CMD,
only tabs the bench opened (and closes), a task that waits for a person ends `held` and counts like blocked. The result names the head.
"""
import base64
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(CORE, "tests", "bench", "agent_driver"))
import agent_rules as rules  # noqa: E402
import head_guard  # noqa: E402  the head labels and the guard's own-tab file

TASKS_FILE = os.path.join(HERE, "agent_tasks.json")
AGENT_MODELS = ("haiku", "sonnet")  # the aliases a run may use as the agent; the judge is always the Haiku of agent_tasks.json
BACKOFF_S = {"rate_limit": 180, "api_error": 30, "cli_crash": 15, "timeout_before_first_call": 15, "brain_start": 10}
RATE_STREAK = 3  # this many rate limits in a row mean the subscription's window is spent: the run stops instead of asking again


class Stop(RuntimeError):
    """The run cannot go on and must not be counted: a token that does not work, a spent subscription window, a spent cap."""


def load_spec(path=TASKS_FILE):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def fetch_source(spec, cache):
    """The three source files at the pinned commit, each checked against its recorded sha256 (a moved file is a different bench)."""
    src, parsed = spec["source"], {}
    os.makedirs(cache, exist_ok=True)
    for name, want in src["sha256"].items():
        path = os.path.join(cache, os.path.basename(name))
        if not os.path.exists(path):
            with urllib.request.urlopen(f"https://raw.githubusercontent.com/{src['repo']}/{src['commit']}/{name}", timeout=60) as r:
                with open(path, "wb") as f:
                    f.write(r.read())
        with open(path, "rb") as f:
            raw = f.read()
        if _sha(raw) != want:
            raise Stop(f"{name} at {src['commit'][:7]} has sha256 {_sha(raw)[:12]}, the spec says {want[:12]}: another file than the one the ids were picked from")
        parsed[os.path.basename(name)] = raw.decode("utf-8")
    rows = [json.loads(x) for x in parsed["WebVoyager_data.jsonl"].splitlines() if x.strip()]
    return rows, json.loads(parsed["WebVoyagerImpossibleTasks.json"]), json.loads(parsed["reference_answer.json"])


def tasks_of(spec, cache, run_date):
    """The spec's tasks in run order, with questions and references; refuses when the seed picks other ids from this data, or when the
    dates in the questions are not the ones the spec lists. A listed question is moved ahead of `run_date` (its reference becomes `possible`,
    the old question is kept as `ques_original`); a task with a broken reference carries `reference_broken`."""
    rows, impossible, reference = fetch_source(spec, cache)
    tasks = rules.pool(rows, impossible, reference)
    picked = rules.select(tasks, spec["seed"], spec["n_tasks"])
    if picked != spec["tasks"]:
        raise Stop("the published seed picks other ids from the pinned data than benchmarks/agent_tasks.json lists")
    by_id = {t["id"]: t for t in tasks}
    out = [by_id[i] for i in spec["tasks"]]
    found = {t["id"]: rules.dates_in(t["ques"]) for t in out if rules.dates_in(t["ques"])}
    if found != spec["redate"]["tasks"]:
        raise Stop(f"the questions hold other dates than benchmarks/agent_tasks.json lists (found {found})")
    for t in out:
        if t["id"] in found:
            t["ques_original"] = t["ques"]
            t["ques"], t["redated_years"] = rules.redate(t["ques"], run_date)
            t["ref_type"] = "possible"
        if t["id"] in spec["references"]["broken"]:
            t["reference_broken"] = spec["references"]["broken"][t["id"]]
    return out, len(tasks)


def _from_reader(cmd_text, hint):
    """The first line of what a reader command prints, run without a shell. The output is never put in a message."""
    cmd = shlex.split(cmd_text)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Stop(f"the token reader {cmd[0]} did not run ({type(e).__name__})")
    tok = r.stdout.strip()
    if r.returncode or not tok:
        raise Stop(f"the token reader {cmd[0]} gave no token (exit {r.returncode}); {hint}")
    return tok


def claude_token():
    """{"CLAUDE_CODE_OAUTH_TOKEN": token} for the claude child only: the environment's value if set, else the output of the reader
    command (BENCH_TOKEN_CMD), run without a shell. The token is never printed or put in an argument."""
    tok = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if not tok:
        if not os.environ.get("BENCH_TOKEN_CMD"):
            raise Stop("set CLAUDE_CODE_OAUTH_TOKEN or BENCH_TOKEN_CMD (a command that prints the token)")
        tok = _from_reader(os.environ["BENCH_TOKEN_CMD"], "set CLAUDE_CODE_OAUTH_TOKEN or BENCH_TOKEN_CMD")
    return {"CLAUDE_CODE_OAUTH_TOKEN": tok}


def brain_token():
    """The MCP agent key of the brain a named head belongs to, from the reader command BENCH_MCP_TOKEN_CMD (no default: the key is the person's)."""
    if not os.environ.get("BENCH_MCP_TOKEN_CMD"):
        raise Stop("--agent-brain-url needs BENCH_MCP_TOKEN_CMD, a command that prints that brain's MCP agent key")
    return _from_reader(os.environ["BENCH_MCP_TOKEN_CMD"], "BENCH_MCP_TOKEN_CMD must print the brain's MCP agent key")


def target_of(suites, head, brain_url):
    """None for the old suite (a scratch brain, head bench-server.b); else the named head of a brain that is already running:
    {"head", "device", "mode", "person_device", "mcp_url"}. The head and the brain's address go together and only with the agent suite alone."""
    if not head and not brain_url:
        return None
    if not head or not brain_url:
        raise Stop("--agent-head and --agent-brain-url go together: the head is on that brain")
    if suites != ["agent"]:
        raise Stop("--agent-head belongs to the agent suite, which runs alone")
    info = head_guard.head_info(head)
    if not info:
        raise Stop(f"--agent-head {head!r} is not a head label of the shape device.mode (mode a, b or c)")
    u = urllib.parse.urlsplit(brain_url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise Stop("--agent-brain-url must be an http(s) address")
    if u.username or u.password or u.query or u.fragment:
        raise Stop("--agent-brain-url must hold no credentials, query or fragment: the key comes from BENCH_MCP_TOKEN_CMD")
    return {**info, "head": head, "mcp_url": brain_url.rstrip("/") + ("" if u.path.rstrip("/").endswith("/mcp") else "/mcp")}


def target_record(target):
    """What env.json says about a named head: which one, its mode, that it is a person's device, and that it is not a mode b run."""
    return {"name": target["head"], "mode": target["mode"], "person_device": target["person_device"], "brain_url": target["mcp_url"],
            "scratch_brain": False, "comparable_with_mode_b": False}


def brain_health(mcp_url):
    """(health, deps) of a running brain from its open /health routes, or None when they do not answer; the person's brain is theirs, so this is only recorded."""
    base = mcp_url[: -len("/mcp")]
    try:
        get = lambda path: json.loads(urllib.request.urlopen(base + path, timeout=10).read())  # noqa: E731
        return get("/health"), get("/health/deps").get("deps", [])
    except (OSError, ValueError):
        return None


def _ids_in(work, name):
    try:
        with open(os.path.join(work, name)) as f:
            return list(dict.fromkeys(f.read().split()))
    except OSError:
        return []


def own_tabs(work):
    """The tab ids the guard saw the bench open in this attempt's folder."""
    return _ids_in(work, head_guard.OWN_TABS_FILE)


def own_sessions(work):
    """The brain session ids the guard saw this attempt's calls name."""
    return _ids_in(work, head_guard.OWN_SESSIONS_FILE)


def close_own_tabs(url, token, head, ids):
    """Close the tabs the bench opened; returns the ids that stayed open. A tab already gone (`not_found`) is closed."""
    return _close_each(url, token, ids, lambda i: ("tabs", {"action": "close", "tab_id": i, "head": head}), "not_found")


def close_own_sessions(url, token, ids):
    """Close the brain sessions an attempt opened; returns the ids that stayed open. A session already gone (`session_gone`) is closed."""
    return _close_each(url, token, ids, lambda i: ("session", {"action": "close", "session_id": i}), "session_gone")


def _close_each(url, token, ids, call, gone):
    import asyncio

    async def go():
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
        left = []
        async with streamablehttp_client(url, headers={"Authorization": "Bearer " + token}) as (r, w, _):
            async with ClientSession(r, w) as sess:
                await sess.initialize()
                for i in ids:
                    try:
                        res = await asyncio.wait_for(sess.call_tool(*call(i)), 30)
                    except Exception:  # noqa: BLE001 - any failure leaves it open, and the row says so
                        left.append(i)
                        continue
                    if res.isError and gone not in " ".join(getattr(c, "text", "") or "" for c in res.content):
                        left.append(i)
        return left
    try:
        return asyncio.run(go()) if ids else []
    except Exception:  # noqa: BLE001
        return list(ids)


def scrub(text, secrets):
    for s in secrets:
        if s and len(s) > 8:
            text = (text or "").replace(s, "<secret>")
    return text


def agent_prompt(spec, t):
    return spec["agent"]["prompt"].format(web=t["web"], ques=t["ques"])


def judge_prompt(spec, t, answer, pages, evidence):
    kind = spec["judge"]["kinds"][t["ref_type"]]
    shown = "\n".join(f"[{p['tool']} {p['url'] or ''}] {p['text']}" for p in evidence["passages"]) or "none"
    reference = f"none: {t['reference_broken']}" if t.get("reference_broken") else t["reference"]
    return spec["judge"]["prompt"].format(ques=t["ques"], kind=kind, reference=reference, answer=answer, pages=", ".join(pages) or "none", page_text=shown)


STOP_WORDS = frozenset("about after also because been before being between both could does each from have into just more most much only other over same "
                       "should some such than that their them then there these they this those very were what when where which while will with would your".split())


def _words(text):
    """The distinct words of a text that can tell one page from another: a number, or four letters or more and not a common word."""
    return {w for w in rules.norm(text).split() if any(ch.isdigit() for ch in w) or (len(w) >= 4 and w not in STOP_WORDS)}


CITED_URL = re.compile(r"https?://[^\s)\]>,\"']+")
CITED_ID = re.compile(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b")  # an arXiv id; the one kind of bare id the questions ask for


def _site_of(url):
    return re.sub(r"^https?://(www\.)?", "", url or "").rstrip("/.,;")


def _cited_first(pages, answer):
    """(cited, rest): the pages whose address or id the answer cites, those whose address holds it first, and every other page, each in call order.
    A page is cited when its address is (or starts with, or is started by) an address in the answer, or holds an id of the answer, or its text holds one."""
    urls = [_site_of(u) for u in CITED_URL.findall(answer)]
    ids = CITED_ID.findall(answer)
    by_address, by_text, rest = [], [], []
    for p in pages:
        site = _site_of(p["url"])
        if site and (any(site.startswith(u) or u.startswith(site) for u in urls) or any(i in site for i in ids)):
            by_address.append(p)
        elif any(i in p["text"] for i in ids):
            by_text.append(p)
        else:
            rest.append(p)
    return by_address + by_text, rest


def _strings(v):
    return [v] if isinstance(v, str) else [s for x in (v.values() if isinstance(v, dict) else v) for s in _strings(x)] if isinstance(v, (dict, list)) else []


def _unwrapped(text):
    """A tool result is one line of JSON whose page text carries its newlines as escapes; the page as the agent read it is the strings, a line each
    (its `situation` block, the other heads' tabs, is not the page)."""
    try:
        return "\n".join(_strings(head_guard.without_situation(json.loads(text)))) or text
    except ValueError:
        return text


def _has_page(text):
    """True for a `goto` answer that carries the page outline as `page`."""
    try:
        return bool(isinstance(answer := json.loads(text), dict) and answer.get("page"))
    except ValueError:
        return False


def evidence_of(spec, calls, answer, secrets):
    """(passages, images) the judge checks the answer against, kept in memory. The text of the worked calls that show a page (not `fill` or
    `script`: that text is the agent's own input), a JSON result unwrapped to its strings one to a line, the call's own address taken out of its result (a `goto` echoes it). First, in full up to
    `chars`, the pages whose address or id the answer cites (the paper it names, the link it gives); then, in the room left: all of the rest when it fits; else the lines (cut to `line_chars`, with the line before and after) that hold a number or a word of the answer, the lines with
    most distinct ones first, up to `chars`, then the last `pages` read, view or goto-with-a-page pages as far as room is left. The last `screenshots` images."""
    cfg = spec["judge"]["evidence"]
    pages, paged = [], set()  # paged: the goto answers that carry a page, read like a `read`
    for c in calls:
        if c["tool"] in cfg["tools"] and c["allowed"] and not c["error"] and c.get("text"):
            url = (c["args"] or {}).get("url")
            text = _unwrapped(scrub(c["text"], secrets))
            pages.append({"tool": c["tool"], "url": url, "text": text.replace(url, "") if url else text})
            if c["tool"] == "goto" and _has_page(c["text"]):
                paged.add(id(pages[-1]))
    images = [i for c in calls if c["allowed"] and not c["error"] for i in c.get("images") or []][-cfg["screenshots"]:]
    cited, pages = _cited_first(pages, answer)
    head, room = [], cfg["chars"]
    for p in cited:
        head.append({**p, "text": p["text"][:room]})
        room -= len(head[-1]["text"])
    if room <= 0:
        return head, images
    cfg = {**cfg, "chars": room}
    if sum(len(p["text"]) for p in pages) <= cfg["chars"]:
        return head + pages, images
    want = _words(answer)
    lines = [[x[: cfg["line_chars"]] for x in p["text"].split("\n")] for p in pages]
    hits = sorted(((-len(want & _words(x)), pi, li) for pi, ls in enumerate(lines) for li, x in enumerate(ls)))
    keep, used = set(), 0
    for score, pi, li in hits:
        if not score:
            break
        near = {(pi, j) for j in (li - 1, li, li + 1) if 0 <= j < len(lines[pi])} - keep
        if used + sum(len(lines[a][b]) + 1 for a, b in near) <= cfg["chars"]:
            keep |= near
            used += sum(len(lines[a][b]) + 1 for a, b in near)
    passages = []
    for pi, p in enumerate(pages):
        run = []
        for li in range(len(lines[pi]) + 1):
            if li < len(lines[pi]) and (pi, li) in keep:
                run.append(lines[pi][li])
            elif run:
                passages.append({"tool": p["tool"], "url": p["url"], "text": "\n".join(run)})
                run = []
    for p in [q for q in pages if q["tool"] in ("read", "view") or id(q) in paged][-cfg["pages"]:]:
        if used + cfg["page_chars"] <= cfg["chars"]:
            passages.append({**p, "text": p["text"][: cfg["page_chars"]]})
            used += cfg["page_chars"]
    return head + passages, images


def evidence_row(passages, images):
    """What the attempt's row keeps of the evidence: the passages, and the sha256 of each screenshot (never its bytes)."""
    return {"passages": passages, "screenshots": [hashlib.sha256(base64.b64decode(i["data"])).hexdigest() for i in images]}


def _tool_row(c):
    args = {k: (v[:200] if isinstance(v, str) else v) for k, v in (c["args"] or {}).items()}
    return {"tool": c["tool"], "args": args, "allowed": c["allowed"], "ms": None if c["ms"] is None else round(c["ms"], 1),
            "held": c.get("held"), "wall": c.get("wall"), "error": bool(c.get("error")),
            **({"person_tab": True} if c.get("person_tab") else {}), **({"fault": c["fault"]} if c.get("fault") else {})}


def pages_of(calls):
    seen = []
    for c in calls:
        u = (c["args"] or {}).get("url")
        if u and u not in seen:
            seen.append(u)
    return seen[:8]


REFUSAL = re.compile(r"\bthis request\b|\bjudg(?:e)?ment only\b|\bfile or tool change\b", re.I)  # a model that answers the wrapper, not the grading


def parse_verdict(text):
    m = re.match(r"\W*(NOT_SUCCESS|SUCCESS_STALE|SUCCESS)\b\W*(.*)", text or "", re.S)
    if m and not REFUSAL.search(m.group(2)):
        return m.group(1) != "NOT_SUCCESS", m.group(2).strip()[:300]
    return None, (text or "").strip()[:300]


def _result_event(stdout):
    """The CLI's last `result` event of a stream-json output, or {}."""
    res = {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            res = event
    return res


def _vote(spec, prompt, images, env_extra, state, work, parse=parse_verdict):
    """One judge vote: a Haiku run with the fixed rubric, the evidence text and the screenshots as image blocks. A run that hit an API error or
    gave no verdict is run again, at most 3 times (each counts against the judge cap); `parse` reads the reply as (ok|None, reason). Returns {"ok": bool|None, "stale": the vote said SUCCESS_STALE, "reason", "text", "runs", "model"}."""
    message = json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": prompt}] +
                                                      [{"type": "image", "source": {"type": "base64", **i}} for i in images]}}) + "\n"
    out = {"ok": None, "stale": False, "reason": "", "text": "", "runs": 0, "model": None}
    for k in range(rules.MAX_ATTEMPTS):
        if state["judge_runs"] >= spec["caps"]["judge_runs"]:
            raise Stop("the judge cap is spent")
        state["judge_runs"] += 1
        out["runs"] += 1
        p = subprocess.run(["claude", "-p", "--model", spec["judge"]["model"], "--tools", "", "--no-session-persistence", "--input-format", "stream-json",
                            "--output-format", "stream-json", "--verbose", "--max-turns", "1", "--setting-sources", "project"],
                           input=message, capture_output=True, text=True, timeout=180, cwd=work, env=dict(os.environ, **env_extra))
        res = _result_event(p.stdout)
        text = scrub(res.get("result") or "", state["secrets"])
        out["model"] = next(iter(res.get("modelUsage") or {}), out["model"])
        out["text"] = text[:600]
        if not res or res.get("is_error"):
            kind = rules.classify({"ok": False, "subtype": res.get("subtype"), "is_error": True, "text": text + scrub(p.stderr[-300:], state["secrets"])})
            _after_infra(kind, state, k + 1)
            time.sleep(BACKOFF_S.get(kind, 15) * (k + 1) if state["sleep"] else 0)
            continue
        state["rate_streak"] = 0
        ok, reason = parse(text)
        out["ok"], out["reason"], out["stale"] = ok, reason, bool(re.match(r"\W*SUCCESS_STALE\b", text))
        if ok is not None:
            return out
    out["reason"] = f"the judge gave no usable verdict in {out['runs']} runs ({out['reason'] or out['text'] or 'no answer'})"[:300]
    return out


def run_judge(spec, t, answer, calls, evidence, env_extra, state, work):
    """The judge's verdict: `votes` Haiku votes on the same prompt, a pass when enough are SUCCESS (a vote with no verdict is not one).
    "stale" is true when the verdict is a pass and most of the SUCCESS votes said SUCCESS_STALE (the pages support the answer, the reference is out of date).
    Returns {"ok": bool, "stale": bool, "votes": [True|False|None], "vote_reasons", "agree": "2/3", "reason": a vote on the verdict's side, "text", "runs", "model"}."""
    prompt = judge_prompt(spec, t, answer, pages_of(calls), evidence)
    cast = [_vote(spec, prompt, evidence["images"], env_extra, state, work) for _ in range(spec["judge"]["votes"])]
    votes = [v["ok"] for v in cast]
    ok = rules.majority(votes)
    side = next(v for v in cast if (v["ok"] is True) == ok)
    passing = [v for v in cast if v["ok"] is True]
    stale = ok and 2 * sum(v["stale"] for v in passing) > len(passing)
    return {"ok": ok, "stale": stale, "votes": votes, "vote_reasons": [v["reason"] for v in cast], "agree": rules.agree(votes), "reason": side["reason"], "text": side["text"],
            "runs": sum(v["runs"] for v in cast), "model": next((v["model"] for v in cast if v["model"]), None)}


def _after_infra(kind, state, attempt):
    """Stop the whole run on a token that does not work or a spent window; otherwise count the failure."""
    if kind in rules.ABORT:
        raise Stop("the subscription token was refused (auth error): no rerun can help")
    state["rate_streak"] = state["rate_streak"] + 1 if kind == "rate_limit" else 0
    if state["rate_streak"] >= RATE_STREAK:
        raise Stop(f"{RATE_STREAK} rate limits in a row: the subscription window is spent, the run stops instead of asking again")


def judge_task(spec, t, r, env_extra, state, work, person_device=False):
    """The verdict of a completed attempt: (verdict, by, reason, det, judge). Order: no answer, no page opened, a short reference found
    word for word, else the judge. A task that met a bot wall and did not pass is blocked (never auto-solved); on a person's device a task
    that did not pass and had a call the product held for a person (a submit, a purchase, a login) is held, counted like blocked and never forced."""
    answer, found = rules.answer_of(r["final"])
    walls = sorted({c["wall"] for c in r["calls"] if c.get("wall")})
    det = rules.det_check(t["reference"], answer) if found and not t.get("reference_broken") else None
    if not r["final"].strip():
        verdict, by, reason, jd = "fail", "rule", f"no final answer after {r['turns']} turns" if r["turns"] else "no final answer", None
    elif not rules.evidence(r["calls"]):
        verdict, by, reason, jd = "fail", "rule", "no page was opened or read: an answer from memory is not a result", None
    elif walls and not found:
        verdict, by, reason, jd = "fail", "rule", "met a bot wall and gave no ANSWER line", None
    elif det is True:
        verdict, by, reason, jd = "pass", "deterministic", f"the reference '{t['reference']}' is in the answer", None
    else:
        jd = run_judge(spec, t, answer, r["calls"], r["evidence"], env_extra, state, work)
        verdict = "pass" if jd["ok"] else "fail"
        by, reason = "judge", jd["reason"] or "no reason given"
    helds = sorted({c["held"] for c in r["calls"] if c.get("held")})
    fault = rules.site_fault(r["calls"], t["web"])
    if verdict == "fail" and walls:
        verdict, by, reason = "blocked", "rule", f"bot wall ({', '.join(walls)}) and no passing answer; a person solves it, the bench does not" + (f"; judge: {jd['reason']}" if jd else "")
    elif verdict == "fail" and person_device and helds:
        verdict, by, reason = "held", "rule", f"the product held an act for the person ({', '.join(helds)}) and no passing answer; the bench never does it" + (f"; judge: {jd['reason']}" if jd else "")
    elif verdict == "fail" and fault:
        verdict, by, reason = "site_fault", "rule", f"the site did not serve its page ({fault}) and no passing answer; not the product's fault" + (f"; judge: {jd['reason']}" if jd else "")
    return verdict, by, reason, det, jd


def attempt_row(run_id, t, n, r, brain_started, brain_down, tabs=None, sessions=None):
    """One raw row from the driver's result of one attempt. Every field `agent_rules.classify` reads is stored."""
    return {"suite": "agent", "run_id": run_id, "task": t["id"], "site": t["site"], "attempt": n, "ref_type": t["ref_type"],
            "brain_started": brain_started, "agent_run": r is not None,
            "ok": bool(r and r["ok"]), "subtype": r and r["subtype"], "is_error": bool(r and r["is_error"]),
            "timed_out": bool(r and r["timed_out"]), "returncode": r and r["returncode"], "n_calls": len(r["calls"]) if r else 0,
            "text": "", "turns": r and r["turns"], "wall_ms": round(r["wall_ms"]) if r else 0, "agent_ms": r and r["agent_ms"],
            "cost_usd": r and r["cost_usd"], "usage": r and r["usage"], "model": r and r["model"],
            "calls": [_tool_row(c) for c in r["calls"]] if r else [], "brain_down": brain_down,
            **({"own_tabs": len(tabs[0]), "tabs_left": list(tabs[1])} if tabs else {}),
            **({"own_sessions": len(sessions[0]), "sessions_left": list(sessions[1])} if sessions else {})}


def _task(run_id, scratch, spec, t, door, driver, env_extra, state, info, sleep, log, rows, target=None):
    """All attempts of one task: appends every attempt's row to `rows` (a Stop raised after an attempt leaves its row there) and
    returns None; the last row is the task's final one. `target` (target_of, plus `close` and `close_sessions`: the functions that close the bench's tabs and
    the attempt's brain sessions and answer the ones left) runs the attempt on a named head of a brain that is already running, with no scratch brain."""
    secrets = state["secrets"]
    for n in range(1, rules.MAX_ATTEMPTS + 1):
        if state["agent_runs"] >= spec["caps"]["agent_runs"]:
            raise Stop(f"the agent cap of {spec['caps']['agent_runs']} runs is spent before {t['id']} attempt {n}")
        t0 = time.time()
        work = os.path.join(scratch, "agent", t["id"].replace(" ", "_"), str(n))
        os.makedirs(work, exist_ok=True)
        brain = None if target else door.Brain(os.path.join(work, "brain"), door.free_port(), door.free_port())
        r, started, down, tabs, sessions = None, True, False, None, None
        try:
            try:
                if brain:
                    brain.start()
            except RuntimeError as e:
                started = False
                log(f"{t['id']} attempt {n}: brain did not start: {str(e)[:120]}")
            if started:
                if brain:
                    info["health"] = info["health"] or brain.health()
                    info["launch"] = info["launch"] or door.launch(brain.work)
                    os.environ["BENCH_MCP_URL"] = brain.url + "/mcp"
                    os.environ["BENCH_MCP_TOKEN_FILE"] = os.path.join(brain.work, "token")
                state["agent_runs"] += 1
                r = driver.run_task(agent_prompt(spec, t), model=spec["agent"]["model"], max_turns=spec["agent"]["max_turns"],
                                    wall_s=spec["agent"]["wall_s"], workdir=work, env_extra=env_extra, evidence=True, **({"head": target["head"]} if target else {}))
                if brain:
                    try:
                        brain.health()
                        if not info["browser"] or info["browser"].startswith("unknown"):  # the browser starts at the first goto: ask after the agent ran
                            info["browser"] = door.browser(brain.work)
                    except OSError:
                        down = True
        finally:
            if brain:
                brain.stop()
            else:
                ids = own_tabs(work)
                tabs = (ids, target["close"](ids))
                sids = own_sessions(work)
                sessions = (sids, target["close_sessions"](sids))
        row = attempt_row(run_id, t, n, r, started, down, tabs, sessions)
        if r:
            r["final"] = scrub(r["final"], secrets)
            row["text"] = scrub((r["final"] if not r["ok"] else "")[-600:] + " " + r["stderr"], secrets).strip()
            row["final_text"] = r["final"][-1500:]
            passages, images = evidence_of(spec, r["calls"], rules.answer_of(r["final"])[0], secrets)
            r["evidence"], row["evidence"] = {"passages": passages, "images": images}, evidence_row(passages, images)
            info["agent_resolved"] = info["agent_resolved"] or r["model"]
        row["start_ms"], row["end_ms"] = int(t0 * 1000), int(time.time() * 1000)
        kind = row["infra_kind"] = rules.classify(row)
        row["final"] = not (kind and rules.may_rerun(kind, n))
        rows.append(row)
        if kind:
            _after_infra(kind, state, n)
        else:
            state["rate_streak"] = 0
        if not row["final"]:
            log(f"{t['id']} attempt {n}: {kind}; run again")
            if sleep:
                time.sleep(BACKOFF_S.get(kind, 15) * n)
            continue
        if kind:
            row.update(verdict="infra_failed", verdict_by="rule", reason=f"{kind} on every one of {n} attempts" if n > 1 else kind, det=None, judge=None)
        else:
            answer, found = rules.answer_of(r["final"])
            row.update(ques=t["ques"], reference=t["reference"], answer=answer, answer_line=found)
            row.update({k: t[k] for k in ("ques_original", "redated_years", "reference_broken") if k in t})
            try:
                v, by, reason, det, jd = judge_task(spec, t, r, env_extra, state, work, bool(target and target["person_device"]))
            except Stop as e:
                row.update(verdict="fail", verdict_by="rule", reason=f"not judged: {e}", det=None, judge=None)
                raise
            row.update(verdict=v, verdict_by=by, reason=reason, det=det, judge=jd, reference_stale=bool(v == "pass" and jd and jd.get("stale")))
            info["judge_resolved"] = info["judge_resolved"] or (jd or {}).get("model")
        log(f"{t['id']:26s} {row['verdict'].upper():11s} by {row['verdict_by']:13s} attempts {n} turns {row['turns']} "
            f"wall {row['wall_ms'] / 1000:.0f}s  {row['reason'][:70]}")
        return None
    return None


def cli_env(scratch):
    """(env_extra, secrets, version) for the claude child: the token and the config folder in the run's scratch (it goes to the child only),
    the CLI's folder put on PATH, and the CLI's version."""
    secrets_env = claude_token()
    env_extra = {**secrets_env, "CLAUDE_CONFIG_DIR": os.path.join(scratch, "claude-config"), "DISABLE_AUTOUPDATER": "1",
                 "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
    secrets = [v for k, v in secrets_env.items() if "TOKEN" in k or "KEY" in k]
    bin_dir = os.environ.get("BENCH_CLAUDE_BIN_DIR", os.path.expanduser("~/.local/claude-cli/bin"))
    os.environ["PATH"] = bin_dir + os.pathsep + os.environ["PATH"] if os.path.isdir(bin_dir) else os.environ["PATH"]
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True, env=dict(os.environ, **env_extra)).stdout.strip()
    return env_extra, secrets, version


def run_suite(run_id, scratch, spec, tasks, door, limit=0, sleep=True, log=print, target=None):
    """Run every task (the first `limit` for a try). Returns (rows, info); info is what env.json records about the agent side.
    `door` carries the door's own helpers (Brain, free_port, browser, launch, head) so this file does not import run.py.
    `target` (target_of) names a head of a brain that is already running: its key is read once, handed to the agent's MCP config
    and scrubbed from every text, and the bench closes the tabs it opened."""
    import driver  # tests/bench/agent_driver
    env_extra, secrets, version = cli_env(scratch)
    if target:
        key = brain_token()
        secrets.append(key)
        token_file = os.path.join(scratch, "brain-key")
        with open(os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
            f.write(key)
        os.environ["BENCH_MCP_URL"], os.environ["BENCH_MCP_TOKEN_FILE"] = target["mcp_url"], token_file
        target = {**target, "close": lambda ids: close_own_tabs(target["mcp_url"], key, target["head"], ids),
                  "close_sessions": lambda ids: close_own_sessions(target["mcp_url"], key, ids)}
    state = {"agent_runs": 0, "judge_runs": 0, "rate_streak": 0, "secrets": secrets, "sleep": sleep}
    info = {"claude_cli": version, "agent_model": spec["agent"]["model"], "judge_model": spec["judge"]["model"], "agent_resolved": None,
            "judge_resolved": None, "health": brain_health(target["mcp_url"]) if target else None, "launch": None, "browser": f"the person's {target['head']}, not recorded" if target else None, "stopped": None,
            "agent_runs": 0, "judge_runs": 0}
    rows = []
    try:
        for t in tasks[: limit or None]:
            _task(run_id, scratch, spec, t, door, driver, env_extra, state, info, sleep, log, rows, target)
    except Stop as e:
        info["stopped"] = str(e)
    info["agent_runs"], info["judge_runs"] = state["agent_runs"], state["judge_runs"]
    return rows, info


def main(argv):
    if len(argv) >= 3 and argv[0] == "select" and argv[1] == "--data":
        spec = load_spec()
        cache = argv[2]
        rows, impossible, reference = fetch_source(spec, cache)
        tasks = rules.pool(rows, impossible, reference)
        print(json.dumps(rules.select(tasks, spec["seed"], spec["n_tasks"])))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
