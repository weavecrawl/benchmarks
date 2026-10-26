"""The one door of the bench: start the own site and a scratch brain of THIS checkout, run the suites, write one run folder.

    python3 benchmarks/run.py --scratch DIR [--suites startup,tools,payload] [--reps N]
    python3 benchmarks/run.py --scratch DIR --suites agent [--agent-limit N]       the agent suite, alone (A1-lite, benchmarks/agent.py)
    python3 benchmarks/run.py --scratch DIR --suites browsecomp [--browsecomp-limit N]       the browsecomp suite, alone (benchmarks/browsecomp.py)
    python3 benchmarks/run.py --scratch DIR --suites forms        (or pages, replay or delegate: each is a whole run of its own, see cases.json)

Why one door: the 2026-09 bench wrote numbers nobody could re-make (hand-typed hardware and models, results with no
raw rows, one pass, a live third-party page). Here
every number in a summary comes from a row this invocation measured, and the gate re-makes the summary from those rows.

Run it on a quiet machine of its own, with a python that has `mcp`,
`playwright` and `tiktoken`. DIR is scratch outside the checkout: the brain's state, the site log, the field runner's full
answers. Nothing here touches an installed brain, its state or its heads; nothing calls a model or an embedder.
Output: benchmarks/results/<run_id>/ {env.json, raw.json, summary.json, summary.md}, written by summarize.write only.

The door refuses a busy machine (exit 75, before anything starts) and records, beside every measured call, the cgroup throttle
counters around it (quiet.py); the gate refuses a run with a throttled call, or with fewer rows than cases x reps.
"""
import argparse
import asyncio
import datetime
import hashlib
import html.parser
import importlib.metadata
import json
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.dirname(HERE)
FIELD = os.path.join(CORE, "tests", "field")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(FIELD, "runner"))
import quiet  # noqa: E402  the machine counters: was the machine quiet while a call was timed
import agent  # noqa: E402  the agent suite: opt-in, drives a model, never part of a default run
import browsecomp  # noqa: E402  the browsecomp suite: the same, on the live web
import summarize  # noqa: E402
import run_cases  # noqa: E402  the field runner: one MCP call, the token, the case files (reused, not copied)
import corpus  # noqa: E402  the public data of the corpus suites, pinned and checked against a lock
import suite_forms  # noqa: E402
import suite_pages  # noqa: E402
import suite_replay  # noqa: E402
import suite_delegate  # noqa: E402

SITE_SUITES = ("startup", "tools", "payload")  # on the own loopback site; one run
CORPUS_SUITES = ("forms", "pages", "replay", "delegate")  # on public data (corpora.json) or public practice sites; each is a whole run of its own
SUITES = SITE_SUITES + CORPUS_SUITES  # a whole run is one of these; the agent suite is asked for by name and runs alone (it spends subscription quota)
HEAD = os.environ.get("FIELD_HEAD", "bench-server.b")  # the scratch brain's own browser; never a person's head


def _out(cmd, cwd=CORE):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _read(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return default


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


class _Text(html.parser.HTMLParser):
    """The words of a page and nothing else (no tags, scripts or styles): what a plain html-to-text gives an agent."""

    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        self.skip += tag in ("script", "style")

    def handle_endtag(self, tag):
        self.skip -= tag in ("script", "style") and self.skip > 0

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def plain_text(html_text):
    p = _Text()
    p.feed(html_text)
    return "\n".join(p.parts)


def machine():
    """What this run ran on, read from the machine now, never typed."""
    cpu = next((ln.split(":", 1)[1].strip() for ln in (_read("/proc/cpuinfo", "") or "").splitlines() if ln.startswith("model name")),
               platform.processor() or platform.machine())
    mem = next((int(ln.split()[1]) // 1024 for ln in (_read("/proc/meminfo", "") or "").splitlines() if ln.startswith("MemTotal")), None)
    cap = {"memory.max": None, "memory.high": None, "cpu.max": None}
    chain = quiet.levels()
    for d in chain:  # the job cap (work-run) sits on a parent slice, not on the job's own unit
        for k in cap:
            v = _read(f"{d}/{k}")
            if cap[k] is None and v and not v.startswith("max"):
                cap[k] = v
    return {"hostname": socket.gethostname(), "os": f"{platform.system()} {platform.release()}", "cpu": cpu, "cpus": os.cpu_count(),
            "mem_total_mb": mem, "python": platform.python_version(), "load_start": _load(), "load_end": None,
            "cap_memory": " / ".join(f"{k} {cap[k]}" for k in ("memory.high", "memory.max") if cap[k]) or None, "cap_cpu": cap["cpu.max"],
            "cgroups": quiet.labels(chain), "isolation": quiet.isolation(chain)}


def _load():
    return [round(x, 2) for x in os.getloadavg()]


def git():
    status = _out(["git", "status", "--porcelain"])  # an untracked file in the checkout (a source file, a case) makes the run dirty too
    return {"commit": _out(["git", "rev-parse", "HEAD"]), "dirty": bool(status) if status is not None else True}


def pushed(cwd=CORE):
    """True when HEAD is on a remote branch. A run of a commit that exists only here (a mutation proof, a scratch edit committed to be
    clean) is not a try at the branch's numbers and leaves no ledger line; every run of a pushed commit does."""
    return bool(_out(["git", "branch", "-r", "--contains", "HEAD"], cwd=cwd))


def packages():
    out = {}
    for name in ("mcp", "playwright", "tiktoken"):
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = None
    return out


class Brain:
    """A scratch brain of this checkout on loopback (tests/field/runner/field_brain.sh), its own state dir and token."""

    def __init__(self, work, port, site_port):
        self.work, self.port = work, port
        self.env = {**os.environ, "FIELD_BRAIN_PORT": str(port), "FIELD_SITE_PORT": str(site_port), "BRAIN_PY": sys.executable}
        self.url = f"http://127.0.0.1:{port}"

    def start(self):
        """Start it; answer the ms from the start command to the first /health 200."""
        t0 = time.time()
        p = subprocess.Popen([os.path.join(FIELD, "runner", "field_brain.sh"), "start", self.work], env=self.env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        while time.time() - t0 < 60:
            try:
                _get(self.url + "/health", 1)
                ms = (time.time() - t0) * 1000
                p.wait(30)
                return ms
            except OSError:
                time.sleep(0.05)
        p.kill()
        raise RuntimeError(f"brain on :{self.port} did not answer /health in 60 s; see {self.work}/brain.log")

    def stop(self):
        subprocess.run([os.path.join(FIELD, "runner", "field_brain.sh"), "stop", self.work], env=self.env, capture_output=True)
        time.sleep(2)

    def health(self):
        h = json.loads(_get(self.url + "/health"))
        deps = json.loads(_get(self.url + "/health/deps")).get("deps", [])
        return h, deps

    def mcp_env(self):
        return {**os.environ, "FIELD_TOKEN_FILE": os.path.join(self.work, "token"), "MC_URL": self.url + "/mcp"}


def _descendants(pid):
    """Every process below `pid`, from /proc (Linux)."""
    kids = {}
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                kids.setdefault(int((_read(f"/proc/{d}/stat") or "").rsplit(")", 1)[1].split()[1]), []).append(int(d))
            except (IndexError, ValueError):
                continue
    out, todo = [], [pid]
    while todo:
        for k in kids.get(todo.pop(), []):
            out.append(k)
            todo.append(k)
    return out


def browser(work):
    """The browser the brain launched, and its version: the main browser process below the brain's pid (not a `--type=` helper) is
    asked for `--version`, so it is the binary that ran, not whatever `google-chrome` is first on PATH. The brain's own log line says
    whether it is real Chrome or the bundled Chromium. 'unknown' when no browser process is running."""
    log = _read(os.path.join(work, "brain.log"), "") or ""
    kind = "real Chrome" if "launched REAL Chrome" in log else "bundled Chromium (playwright)"
    for pid in _descendants(int(_read(os.path.join(work, "brain.pid"), "0") or 0)):
        try:
            exe, cmd = os.readlink(f"/proc/{pid}/exe"), _read(f"/proc/{pid}/cmdline", "") or ""
        except OSError:
            continue
        if "chrom" in os.path.basename(exe).lower() and "--type=" not in cmd:
            return f"{_out([exe, '--version']) or 'version unknown'} ({kind}, {exe})"
    return f"unknown ({kind}; no browser process found below the brain)"


def launch(work):
    """How the scratch brain was started and how that differs from an installed one: the file field_brain.sh wrote from the values it set."""
    try:
        with open(os.path.join(work, "launch.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


async def _calls(brain, fn):
    """Open one MCP connection to the brain and run fn(session) on it."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    with open(os.path.join(brain.work, "token")) as f:
        tok = f.read().strip()
    async with streamablehttp_client(brain.url + "/mcp", headers={"Authorization": "Bearer " + tok}) as (r, w, _):
        async with ClientSession(r, w) as sess:
            await sess.initialize()
            return await fn(sess)


def suite_startup(run_id, scratch, site, site_port, reps):
    """Cold start: a fresh brain (empty state dir) to /health, then its first goto (the browser starts here)."""
    rows, health = [], None
    for rep in range(reps):
        b = Brain(os.path.join(scratch, f"startup-{rep}"), _free_port(), site_port)
        began = time.time()
        try:
            health_ms = b.start()
            health = health or b.health()

            async def first(sess):
                return await run_cases.call(sess, "goto", {"url": site + "/about", "head": HEAD}, 90)
            t0, t1, is_err, text = asyncio.run(_calls(b, first))
            rows.append({"suite": "startup", "run_id": run_id, "rep": rep, "health_ms": round(health_ms, 1),
                         "first_goto_ms": round((t1 - t0) * 1000, 1), "start_ms": int(began * 1000), "end_ms": int(t1 * 1000),
                         "first_goto_ok": not is_err and (run_cases.checks.parse(text) or {}).get("loaded") is True})
        finally:
            b.stop()
    return rows, health


def suite_tools(run_id, scratch, brain, site, reps, spec):
    """The field cases of every tool, through the field runner (one connection, file order), `reps` times."""
    out = os.path.join(scratch, "tools")
    cmd = [sys.executable, os.path.join(FIELD, "runner", "run_cases.py"), "--repeat", str(reps), "--mode", "b-headless", "--out", out]
    if spec["skip_slow"]:
        cmd.append("--skip-slow")
    env = {**brain.mcp_env(), "FIELD_SITE": site, "FIELD_HEAD": HEAD, "FIELD_SKIP": ",".join(spec["skip_ids"])}
    for var in ("FIELD_NOTIFY_LOG", "FIELD_ALLOW_NOTIFY", "FIELD_PERSON_KEY_FILE"):
        env.pop(var, None)  # no person and no notice in a bench: those cases skip and say why
    rc = subprocess.run(cmd, env=env, check=False).returncode  # 0 all passed, 1 a case failed or the site saw a POST; anything else: it died
    kinds = {c["id"]: "setup" if c.get("setup") else run_cases.checks.strength(c["expect"]) for c in tools_cases(spec)}  # what each case's check looks at
    rows = []
    with open(os.path.join(out, "raw.jsonl"), encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("step", 0):
                continue  # a person case's later calls: none run in a bench, kept out of the timing anyway
            why = r.get("why", "")
            if r["case_id"] in spec["skip_ids"]:
                why = "skipped by benchmarks/cases.json: " + spec["skip_ids"][r["case_id"]]
            rows.append({"suite": "tools", "run_id": run_id, "rep": r["rep"], "case_id": r["case_id"], "tool": r["tool"],
                         "verdict": r["verdict"], "wall_ms": r.get("wall_ms"), "bytes": r.get("bytes"), "is_error": r.get("is_error"),
                         "start_ms": r.get("start_ms"), "end_ms": r.get("end_ms"), "check": kinds.get(r["case_id"]),
                         "ref_lookups": r.get("ref_lookups", 0),
                         "failed": r.get("failed", []), "why": why})
    return rows, rc


PART_CAP = 20  # a look that covers the whole page follows its parts; a page of more than this many is not a look, and is not ok


def body(text):
    """An answer without its top-level `url` and `title`: those are the page's own address and name, which a stub that echoes the
    request gives back, so a `must` word that is only in them proves nothing."""
    try:
        parsed = json.loads(text)
    except ValueError:
        return text
    # compact, as the brain writes it: the goto receipt's `"loaded":true` is a must word and would not match `"loaded": true`
    return json.dumps({k: v for k, v in parsed.items() if k not in ("url", "title")}, ensure_ascii=False, separators=(",", ":")) if isinstance(parsed, dict) else text


def parts_of(text):
    """(part, parts) an answer says it is; (1, 1) when it says nothing."""
    try:
        parsed = json.loads(text)
        return int(parsed.get("part") or 1), int(parsed.get("parts") or 1)
    except (ValueError, AttributeError, TypeError):
        return 1, 1


async def look(sess, c, args, enc):
    """One look at a page: one call, or for a call that covers the whole page (`covers` page) every part of its answer, one call each,
    tokens, bytes and time summed. `complete` is false when a part was refused or the cap was hit: that look is not the page."""
    texts, ms, tokens, size, first, last, errs = [], 0.0, 0, 0, None, None, False
    part, complete = 1, True
    for _ in range(PART_CAP):
        t0, t1, is_err, text = await run_cases.call(sess, c["tool"], args if part == 1 else {**args, "part": part}, 90)
        texts.append((part, is_err, text))
        ms, tokens, size, errs = ms + (t1 - t0) * 1000, tokens + len(enc.encode(text)), size + len(text.encode()), errs or is_err
        first, last = first or t0, t1
        here, total = parts_of(text)
        if c.get("covers") != "page" or is_err or here >= total:
            complete = c.get("covers") != "page" or (not is_err and here >= total)
            break
        part = here + 1
    else:
        complete = False
    return {"ms": round(ms, 1), "tokens": tokens, "bytes": size, "start": first, "end": last, "is_error": errs, "complete": complete,
            "parts": len(texts), "texts": texts}


def suite_payload(run_id, scratch, brain, site, reps, spec):
    """Tokens and time of one look at each page, beside the page's own HTML fetched plainly. A look counts only when its answer
    carries the page's own words (`must` in cases.json); every answer is kept whole in scratch/payload.jsonl."""
    import tiktoken
    enc = tiktoken.get_encoding(spec["tokenizer"])
    rows = []
    keep = open(os.path.join(scratch, "payload.jsonl"), "w", encoding="utf-8")

    async def go(sess):
        for rep in range(reps):
            for spec_page in spec["pages"]:
                page, must = spec_page["path"], spec_page["must"]
                url = site + page
                t0 = time.time()
                html = _get(url).decode("utf-8", "replace")
                t1 = time.time()
                rows.append({"suite": "payload", "run_id": run_id, "rep": rep, "page": page, "call": "http_get", "tool": None,
                             "wall_ms": round((t1 - t0) * 1000, 1), "start_ms": int(t0 * 1000), "end_ms": int(t1 * 1000),
                             "bytes": len(html.encode()), "tokens": len(enc.encode(html)), "ok": True, "covers": "page", "complete": True, "parts": 1})
                t0 = time.time()
                text = plain_text(html)  # the fairer baseline: the page's words without its markup
                t1 = time.time()
                rows.append({"suite": "payload", "run_id": run_id, "rep": rep, "page": page, "call": "http_text", "tool": None,
                             "wall_ms": round((t1 - t0) * 1000, 1), "start_ms": int(t0 * 1000), "end_ms": int(t1 * 1000),
                             "bytes": len(text.encode()), "tokens": len(enc.encode(text)), "ok": bool(text), "covers": "page", "complete": True, "parts": 1})
                for c in spec["calls"]:
                    args = {k: (v.replace("{PAGE}", url) if isinstance(v, str) else v) for k, v in c["args"].items()}
                    args["head"] = HEAD
                    got = await look(sess, c, args, enc)
                    answer = "\n".join(body(t) for _, _, t in got["texts"])
                    missing = [m for m in must[c["name"]] if m.lower() not in answer.lower()]
                    for part, is_err, text in got["texts"]:
                        keep.write(json.dumps({"run_id": run_id, "rep": rep, "page": page, "call": c["name"], "part": part, "is_error": is_err, "text": text}) + "\n")
                    rows.append({"suite": "payload", "run_id": run_id, "rep": rep, "page": page, "call": c["name"], "tool": c["tool"], "covers": c.get("covers"),
                                 "wall_ms": got["ms"], "start_ms": int(got["start"] * 1000), "end_ms": int(got["end"] * 1000), "bytes": got["bytes"],
                                 "tokens": got["tokens"], "parts": got["parts"], "complete": got["complete"],
                                 "ok": not got["is_error"] and not missing and got["complete"], "missing": missing})
    try:
        asyncio.run(_calls(brain, go))
    finally:
        keep.close()
    return rows


class Ctx:
    """What a corpus suite file needs of this door: the brain, the MCP connection and the call. Handed over, so the suite imports nothing of run.py."""
    head = HEAD
    call = staticmethod(run_cases.call)
    parse = staticmethod(run_cases.checks.parse)
    connect = staticmethod(_calls)
    look = staticmethod(look)  # one look at a page: every part of an answer that covers the whole page, tokens and time summed
    plain_text = staticmethod(plain_text)
    tokenizer = None  # set by main from cases.json
    free_port = staticmethod(_free_port)
    get = staticmethod(_get)

    @staticmethod
    def new_brain(work, site_port):
        return Brain(work, _free_port(), site_port)

    @staticmethod
    def observe(brain):
        """What the running brain says it is: (its sha, dirty flag, browser and how it was started; its registered dependencies as text)."""
        h, deps = brain.health()
        return ({"sha": h.get("sha"), "dirty": h.get("dirty"), "browser": browser(brain.work), "launch": launch(brain.work)},
                ", ".join(f"{d.get('name')} (alive {d.get('alive')})" for d in deps) or None)


def tools_cases(spec):
    """The cases the field runner will list for this bench (skips included: each is a row per rep), by the runner's own loader."""
    device = HEAD != os.environ.get("FIELD_BRAIN_HEAD", "bench-server.b")
    return run_cases.load_cases([], spec["skip_slow"], False, False, device, list(spec["skip_ids"]))


def whole_run(spec, suites):
    """The suites this run is when they are exactly one of the whole runs `cases.json` defines; None for anything else (a try)."""
    return next((w for w in spec["whole_runs"] if sorted(w) == sorted(suites)), None)


def default_reps(spec, suites):
    """Repeats of a whole run: the corpus suite's own when it runs alone, else the site suites' (`cases.json`)."""
    return spec[suites[0]]["reps"] if len(suites) == 1 and suites[0] in CORPUS_SUITES else spec["reps"]


def expected(spec, suites, reps, corpora=None, agent_tasks=0, browsecomp_tasks=0):
    """How many rows each suite must leave: a run with fewer died partway and is not a result."""
    out = {}
    if "agent" in suites:
        out["agent"] = agent_tasks  # tasks with a final verdict; a task's attempts are counted by summarize._rows
    if "browsecomp" in suites:
        out["browsecomp"] = browsecomp_tasks  # problems with a final verdict; a problem's attempts are counted by summarize._rows
    if "forms" in suites:
        out["forms"] = sum(suite_forms.expected(corpora["chromium_autofill"]["dir"]).values())
    if "replay" in suites:
        out["replay"] = suite_replay.expected(suite_replay.load())
    if "delegate" in suites:
        out["delegate"] = suite_delegate.expected(suite_delegate.load())
    if "pages" in suites:
        out["pages"] = sum(suite_pages.expected(corpora["article_extraction"]["dir"], reps, spec["pages"]["url_reps"]).values())
    if "startup" in suites:
        out["startup"] = spec["startup"]["reps"]
    if "tools" in suites:
        out["tools"] = {c["id"]: reps for c in tools_cases(spec["tools"])}
    if "payload" in suites:
        out["payload"] = len(spec["payload"]["pages"]) * (2 + len(spec["payload"]["calls"])) * reps  # http_get, http_text, then the calls
    return out


def not_run(suites=()):
    """What the door does not run, said in the summary so a reader does not assume it: counted from the files now."""
    if "agent" in suites:
        return [{"what": "the other 546 WebVoyager tasks and BU Bench V1", "why": "A1-lite is a 40-task subset on purpose: the subscription is a limit"},
                {"what": "a same-model control arm and any other agent or model", "why": "one agent model per run (Haiku or Sonnet) and one Haiku judge; no comparison with another tool layer is made"},
                {"what": "the timing suites (startup, tools, payload)", "why": "they need a quiet machine and no model; they run in their own door run"},
                {"what": "a screenshot judge or a human review of the verdicts", "why": "the judge reads text only; every verdict and reason is in raw.json for a person to check"}]
    if "browsecomp" in suites:
        return [{"what": "the other 1166 BrowseComp problems", "why": "a 100-problem subset on purpose: the subscription is a limit; about plus or minus 10 points at 95%"},
                {"what": "clicking, forms and every page task", "why": "BrowseComp tests searching and reading; it does not stand in for a form or navigation benchmark"},
                {"what": "OpenAI's setup (its tools, its model, its grader model)", "why": "our agent, our brain's tools, a Haiku grader on OpenAI's template: the number is not comparable with a vendor row"},
                {"what": "the timing suites (startup, tools, payload)", "why": "they need a quiet machine and no model; they run in their own door run"}]
    weak = sum(1 for n in os.listdir(os.path.join(FIELD, "cases", "weakness")) if n.endswith(".jsonl")
               for ln in open(os.path.join(FIELD, "cases", "weakness", n), encoding="utf-8") if ln.strip() and not ln.startswith("#"))
    out = [{"what": f"the weakness suite ({weak} cases, tests/field/cases/weakness/)", "why": "hostile arguments, odd pages and safety checks; run by tests/field/runner/weakness_run.sh, not by this door"},
           {"what": "the agent benches (tests/bench/webgames, tests/bench/webvoyager)", "why": "they drive the `claude` CLI, which is on the Mac only; they commit no results"},
           {"what": "headed browsers and device heads (Mode B headed, Mode C)", "why": "the scratch brain runs headless on its own browser; tests/field/runner/device_heads_run.sh covers the others"}]
    if set(suites) & set(SITE_SUITES):
        out.append({"what": "any real site", "why": "only the own loopback site is used (a live page changes between runs)"})
    if "forms" in suites:
        out.append({"what": "the forms of the live sites", "why": "the pages are Chromium's saved copies, years old; the live pages changed since"})
    if "replay" in suites:
        out.append({"what": "a replay of a walked route", "why": "no tool call replays the stored route of a page whose id is an address (goto loads the address); the suite times the walk, the route lookup and the address load, and says what the lookup answered"})
    if "delegate" in suites:
        out.append({"what": "a goal that asks a page to be read and answered, a form filled or a search typed", "why": "the 11 goals only open a site and then a named link or the first item; delegate_goals.json says why"})
        out.append({"what": "a decision model", "why": "the scratch brain has no decision host, like every installed brain; the brain's registered dependencies above say so"})
    if "pages" in suites:
        out.append({"what": "the live article pages", "why": "the pages are the benchmark's saved copies; a live page changed since, and may now refuse a server address"})
    return out


class Door:
    """The door's own helpers, handed to the agent suite so that benchmarks/agent.py does not import this file."""
    Brain = Brain
    free_port = staticmethod(_free_port)
    browser = staticmethod(lambda work: browser(work))
    launch = staticmethod(lambda work: launch(work))
    head = HEAD


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", required=True, help="a folder outside the checkout for brain state, logs, full answers and the downloaded public data")
    ap.add_argument("--suites", default=",".join(SITE_SUITES))
    ap.add_argument("--reps", type=int, default=0, help="repeats of the suites (default: benchmarks/cases.json)")
    ap.add_argument("--agent-limit", type=int, default=0, help="agent suite only: run the first N tasks (a try; the gate refuses it as a result)")
    ap.add_argument("--agent-model", choices=agent.AGENT_MODELS, default="haiku", help="agent and browsecomp suites only: the model alias of the agent (the judge is always Haiku)")
    ap.add_argument("--agent-head", help="agent suite only: run on this head (`<device>.<mode>`, for example a person's Chrome `d1.a` or desktop app `d1.c`) of a brain that is already running, with --agent-brain-url; "
                    "results are not comparable with the mode b runs")
    ap.add_argument("--agent-brain-url", help="agent suite only: the running brain's address; its MCP agent key is printed by the command in BENCH_MCP_TOKEN_CMD")
    ap.add_argument("--browsecomp-limit", type=int, default=0, help="browsecomp suite only: run the first N problems (a try; the gate refuses it as a result)")
    ap.add_argument("--allow-busy", action="store_true", help="start on a busy machine anyway; the run is recorded as such and the gate refuses it")
    a = ap.parse_args()
    suites = [s for s in a.suites.split(",") if s]
    unknown = set(suites) - set(SUITES) - {"agent", "browsecomp"}
    if unknown:
        sys.exit(f"unknown suite(s) {sorted(unknown)}; known: {', '.join(SUITES)}, agent, browsecomp")
    if "browsecomp" in suites and suites != ["browsecomp"]:
        sys.exit("the browsecomp suite runs alone: a model run beside the timed suites would void their quiet-machine proof")
    if "agent" in suites and suites != ["agent"]:
        sys.exit("the agent suite runs alone: a model run beside the timed suites would void their quiet-machine proof")
    try:
        target = agent.target_of(suites, a.agent_head, a.agent_brain_url)
    except agent.Stop as e:
        sys.exit(str(e))
    with open(os.path.join(HERE, "cases.json"), encoding="utf-8") as f:
        spec = json.load(f)
    reps = a.reps or default_reps(spec, suites)
    aspec = agent.load_spec() if "agent" in suites else None
    bspec = browsecomp.load_spec() if "browsecomp" in suites else None
    for x in (aspec, bspec):
        if x:
            x["agent"]["model"] = a.agent_model
    Ctx.tokenizer = spec["payload"]["tokenizer"]
    scratch_root = os.path.abspath(os.path.expanduser(a.scratch))
    corpora = {}  # the public data this run reads, downloaded and checked against the lock before the machine is looked at
    for suite in suites:
        if suite in CORPUS_SUITES and spec[suite].get("corpus"):
            name = spec[suite]["corpus"]
            dest = os.path.join(scratch_root, "corpus", name)
            corpora[name] = {"dir": dest, "entry": corpus.fetch(name, dest)}
    pre = quiet.preflight()
    if pre["busy"]:
        print("the machine is not quiet:\n  " + "\n  ".join(pre["busy"]) + ("\nstarting anyway (--allow-busy)" if a.allow_busy else "\nnot started"), file=sys.stderr)
        if not a.allow_busy:
            return 75
    run_id = "bench-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:4]
    scratch = os.path.join(scratch_root, run_id)
    os.makedirs(scratch)
    case_files = [os.path.join(HERE, "cases.json"), agent.TASKS_FILE] if aspec else [os.path.join(HERE, "cases.json"), browsecomp.TASKS_FILE] if bspec else [os.path.join(HERE, n) for n in ("cases.json", "corpora.json", "corpora.lock.json", "forms_vocabulary.json", "replay_routes.json", "delegate_goals.json")] + sorted(
        os.path.join(FIELD, "cases", n) for n in os.listdir(os.path.join(FIELD, "cases")) if n.endswith(".jsonl"))
    run_day = datetime.datetime.now(datetime.timezone.utc).date()
    tasks = agent.tasks_of(aspec, os.path.join(scratch, "source"), run_day)[0][: a.agent_limit or None] if aspec else []
    btasks = browsecomp.tasks_of(bspec, os.path.join(scratch, "source"))[: a.browsecomp_limit or None] if bspec else []  # decrypted in memory, never written
    whole = whole_run(spec, suites)
    on_site = bool(set(suites) & set(SITE_SUITES))
    env = {"run_id": run_id, "suites": suites, "reps": reps, "head": target["head"] if target else HEAD, "tokenizer": spec["payload"]["tokenizer"],
           "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "ended_at": None,
           "git": git(), "machine": machine(), "packages": packages(), "preflight": {**pre, "allowed_busy": bool(pre["busy"])},
           "expected": expected(spec, suites, reps, corpora, len(tasks), len(btasks)), "not_run": not_run(suites),
           # what a whole run is: a run of less is a try, and check says so
           "door": ({"reps": spec["reps"], "suites": ["agent"], "tasks": aspec["n_tasks"]} if aspec else
                    {"reps": spec["reps"], "suites": ["browsecomp"], "tasks": bspec["n_tasks"]} if bspec else
                    {"reps": default_reps(spec, whole or list(SITE_SUITES)), "suites": whole or list(SITE_SUITES),
                     **({"url_reps": spec["pages"]["url_reps"]} if whole == ["pages"] else {})}),
           "cases": {os.path.relpath(p, CORE): _sha(p) for p in case_files},
           "corpora": {name: {"commit": c["entry"]["commit"], "licence": c["entry"]["licence"], "files": len(c["entry"]["files"]), "digest": corpus.digest(c["entry"])}
                       for name, c in corpora.items()},
           "models": {"brain": None, "agent": None, "agent_why": "no suite drives an agent: the brain's tools are timed directly"}}
    if aspec:
        env["agent"] = {"tasks": [t["id"] for t in tasks], "seed": aspec["seed"], "pool": aspec["pool"], "spread": aspec["method"].split(":")[0], "caps": aspec["caps"],
                        "source_commit": aspec["source"]["commit"], "license": aspec["source"]["license"], "max_turns": aspec["agent"]["max_turns"],
                        "wall_s": aspec["agent"]["wall_s"], "max_attempts": agent.rules.MAX_ATTEMPTS,
                        "judge_votes": aspec["judge"]["votes"], "not_doable": aspec["not_doable"], "run_date": run_day.isoformat(),
                        **({"head": agent.target_record(target)} if target else {})}
    if bspec:
        env["browsecomp"] = {"tasks": [t["id"] for t in btasks], "seed": bspec["seed"], "n_rows": bspec["n_rows"], "source_sha256": bspec["source"]["sha256"], "caps": bspec["caps"],
                             "max_turns": bspec["agent"]["max_turns"], "wall_s": bspec["agent"]["wall_s"], "max_attempts": agent.rules.MAX_ATTEMPTS,
                             "judge_votes": bspec["judge"]["votes"]}
    if env["git"]["dirty"]:
        print("warning: the checkout has uncommitted changes; the gate refuses a dirty run's results", file=sys.stderr)
    site_proc = site_log = None
    site_port = site = None
    raw = []
    sampler = quiet.Sampler(run_id)
    brain = None
    try:
        if on_site:
            site_port = _free_port()
            site = f"http://127.0.0.1:{site_port}"
            site_log = open(os.path.join(scratch, "site.log"), "w")
            site_proc = subprocess.Popen([sys.executable, os.path.join(FIELD, "site", "server.py"), "--port", str(site_port)],
                                         stdout=site_log, stderr=subprocess.STDOUT)
            brain = Brain(os.path.join(scratch, "brain"), _free_port(), site_port)
        sampler.start()
        if on_site:
            for _ in range(100):
                try:
                    _get(site + "/count", 1)
                    break
                except OSError:
                    time.sleep(0.1)
        health = None
        if aspec or bspec:
            name, mod, spec_of, todo = ("agent", agent, aspec, tasks) if aspec else ("browsecomp", browsecomp, bspec, btasks)
            rows, info = mod.run_suite(run_id, scratch, spec_of, todo, Door, limit=0, **({"target": target} if target else {}))
            raw += rows
            health = info["health"]
            env["brain"] = {"sha": health and health[0].get("sha"), "dirty": health and health[0].get("dirty"), "browser": info["browser"], "launch": info["launch"]}
            env["models"] = {"brain": ", ".join(f"{d.get('name')} (alive {d.get('alive')})" for d in (health[1] if health else [])) or None,
                             "agent": f"agent {info['agent_resolved']}, judge {info['judge_resolved']}, claude CLI {info['claude_cli']}",
                             "agent_why": f"the aliases in {name}_tasks.json resolve to these model ids at run time; the subscription token is never recorded"}
            env[name].update(claude_cli=info["claude_cli"], agent_model=info["agent_model"], judge_model=info["judge_model"],
                             agent_resolved=info["agent_resolved"], judge_resolved=info["judge_resolved"], stopped=info["stopped"])
            health = None
        if "startup" in suites:
            rows, health = suite_startup(run_id, scratch, site, site_port, spec["startup"]["reps"])
            raw += rows
        if "tools" in suites or "payload" in suites:
            brain.start()
            health = brain.health()
        if health:
            h, deps = health
            env["brain"] = {"sha": h.get("sha"), "dirty": h.get("dirty"), "browser": None}
            env["brain"]["launch"] = launch(brain.work if "tools" in suites or "payload" in suites else os.path.join(scratch, "startup-0"))
            env["models"]["brain"] = ", ".join(f"{d.get('name')} (alive {d.get('alive')})" for d in deps) or None
        if "tools" in suites or "payload" in suites:
            if "tools" in suites:
                rows, env["runner_exit"] = suite_tools(run_id, scratch, brain, site, reps, spec["tools"])
                raw += rows
            if "payload" in suites:
                raw += suite_payload(run_id, scratch, brain, site, reps, spec["payload"])
            env["brain"]["browser"] = browser(brain.work)
        if "pages" in suites:
            rows, info = suite_pages.run(Ctx, run_id, scratch, corpora["article_extraction"]["dir"], reps, spec["pages"]["url_reps"])
            raw += rows
            env["pages"] = info["pages"]
            env["brain"], env["models"]["brain"] = info["brain"], info["models"]
        if "replay" in suites:
            rows, info = suite_replay.run(Ctx, run_id, scratch)
            raw += rows
            env["replay"] = info["replay"]
            env["brain"], env["models"]["brain"] = info["brain"], info["models"]
        if "delegate" in suites:
            rows, info = suite_delegate.run(Ctx, run_id, scratch)
            raw += rows
            env["delegate"] = info["delegate"]
            env["brain"], env["models"]["brain"] = info["brain"], info["models"]
        if "forms" in suites:
            rows, info = suite_forms.run(Ctx, run_id, scratch, corpora["chromium_autofill"]["dir"])
            raw += rows
            env["forms"] = info["forms"]
            env["brain"], env["models"]["brain"] = info["brain"], info["models"]
        if on_site:
            env["posts_after"] = json.loads(_get(site + "/count"))["posts"]
    finally:
        env["machine"]["peak_mb"] = quiet.peaks(quiet.levels())
        raw += sampler.stop()
        if brain:
            brain.stop()
        if site_proc:
            site_proc.terminate()
            site_log.close()
    env.setdefault("brain", {"sha": None, "dirty": None, "browser": None})
    env["machine"]["load_end"] = _load()
    if env["machine"].get("isolation"):
        env["machine"]["other_units_end"] = (quiet.isolation(quiet.levels()) or {}).get("other_units")
    env["ended_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    folder = os.path.join(HERE, "results", run_id)
    os.makedirs(folder)
    summarize.write(folder, env, raw)
    problems = summarize.check(folder)
    results = os.path.dirname(folder)
    ledger = os.path.join(results, summarize.LEDGER)
    print(f"wrote {folder}")
    print("\n".join(problems) or "check: ok")
    if pushed():
        fresh = not os.path.exists(ledger)
        with open(ledger, "a", encoding="utf-8") as f:  # every run of a pushed commit leaves a line, kept or dropped (self-reported: the repo cannot see a run that did not)
            if fresh:
                f.write(summarize.LEDGER_HEAD + "\n")
            f.write(summarize.ledger_row(env, summarize.render(env, raw)[0], problems))
        print(f"a line for this run is in {ledger}: if you do not commit the folder, change its status to dropped and say why")
    else:
        print("HEAD is on no remote branch: no ledger line (push the commit first; this run cannot be committed as a result)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
