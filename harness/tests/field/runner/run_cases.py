"""Run field cases through the brain's MCP door, one connection, in file order, and save everything.

    python3 run_cases.py [--tools goto,read] [--skip-slow] [--out DIR] [--mode b-headless] [--repeat N]

Env: <NS>_MCP_TOKEN (NS from brand.json) or FIELD_TOKEN_FILE (a file holding it; never printed), MC_URL (default the scratch
brain, http://127.0.0.1:47870/mcp),
FIELD_SITE (default http://127.0.0.1:8791), FIELD_SITE_ALT (the same site under another host name, default localhost: the
brain cools a host after a challenge, so challenge and hang reads go to {ALT} and leave {SITE} readable), FIELD_HEAD (default bench-server.b),
FIELD_NOTIFY_LOG (a file the notify capture writes; enables `person` cases), FIELD_PERSON_KEY_FILE + FIELD_HEADS_URL (the key of
the capture head and the brain's /heads address: the runner then starts the capture head itself, see notify_head.py),
FIELD_PERSON (the capture head's name, default fieldperson.b). Scratch brain only.
FIELD_BRAIN_HEAD (the brain's own browser head, default bench-server.b: a case marked `brain_only` is skipped on any other head), FIELD_SKIP (case ids to leave out, comma list; a skip is reported, never a pass).
FIELD_OWN_TAB=1 (open the agent's own tab on the head first: a device head's only tab is the person's and the first act on it is refused `tab_named`).

Writes under DIR (default field/results/<date>/<run_id>/):
  raw.jsonl    one line per call: run_id, case_id, tool, mode, head, args, start/end epoch ms, wall_ms,
               is_error, bytes, failed, verdict, and the FULL answer text. Stays local: never committed.
  summary.json / summary.md  verdicts per case, site POST count before and after, timing.
Exit 0 when no case failed and the site's POST count stayed 0; 1 when a case failed or the site saw a POST; 70 when the runner itself died
(an exception: a plain Python crash would also exit 1, which reads as a failed case, and the bench door must tell the two apart).
"""
import argparse
import asyncio
import datetime
import glob
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
import urllib.request
import uuid

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brand  # noqa: E402
import checks  # noqa: E402
import person  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, "..", "cases")
NO_HEAD = {"session", "scraper", "scrape", "web_search", "rename_device"}  # the tools that take no `head` (session uses `on`)
ORDER = ["manage_head", "session", "goto", "read", "web_search", "view", "maps", "click", "fill", "scroll", "tabs",
         "wait", "script", "delegate_task", "scraper", "scrape", "rename_device", "ask_human"]
PERSON = os.environ.get("FIELD_PERSON", "fieldperson.b")
CAPTURE = None  # the notify capture head of this run, when there is one
REF = re.compile(r"\{REF:([^}]+)\}")
LOOKUPS = [0]  # untimed `view` calls made to find a ref before a case: a row says how many it cost, so no timing hides them


def token():
    var = brand.setting("MCP_TOKEN")
    if os.environ.get(var):
        return os.environ[var]
    with open(os.path.expanduser(os.environ["FIELD_TOKEN_FILE"])) as f:
        return f.read().strip()


def site_count(site):
    with urllib.request.urlopen(site + "/count", timeout=5) as r:
        return json.loads(r.read())


def canary_count(site):
    """Hits on the SSRF canary: a second copy of the site on 127.0.0.2 (same port), which no allowlist names. Nothing the brain
    does may ever reach it. None when no canary site is running."""
    try:
        return site_count(site.replace("127.0.0.1", "127.0.0.2"))["canary"]
    except (OSError, KeyError, ValueError):
        return None


def load_weakness(skip_slow, allow_notify, has_person, device_head=False, skip_ids=(), files=()):
    """The weakness suite (`cases/weakness/*.jsonl`, files in name order, cases in file order). Every case names its `tool`
    and is judged also on "the brain answered" (`answered`): a client timeout never passes a refusal case."""
    cases = []
    for path in sorted(glob.glob(os.path.join(CASES, "weakness", "*.jsonl"))):
        if files and not any(os.path.basename(path).startswith(x) for x in files):
            continue
        with open(path) as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    c = json.loads(line)
                    c["expect"] = {**c.get("expect", {}), "answered": True}
                    c["_skip"] = None
                    if skip_slow and c.get("slow"):
                        c["_skip"] = "slow"
                    if c.get("may_notify") and not (allow_notify or has_person):
                        c["_skip"] = "may_notify: set FIELD_ALLOW_NOTIFY=1 or FIELD_NOTIFY_LOG"
                    if c.get("brain_only") and device_head:
                        c["_skip"] = "brain_only: the case is about the brain's own browser, not a device head"
                    if c["id"] in skip_ids:
                        c["_skip"] = "FIELD_SKIP"
                    cases.append(c)
    return [c for c in cases if not c.get("late")] + [c for c in cases if c.get("late")]


def load_cases(tools, skip_slow, allow_notify, has_person, device_head=False, skip_ids=(), only_slow=False):
    cases = []
    for tool in ORDER:
        if tools and tool not in tools:
            continue
        path = os.path.join(CASES, f"{tool}.jsonl")
        with open(path) as f:
            for n, line in enumerate(f, 1):
                if line.strip() and not line.startswith("#"):
                    c = json.loads(line)
                    c.setdefault("tool", tool)
                    c["expect"] = {**c.get("expect", {}), "answered": True}  # a timeout or a dead brain is never the refusal a case waits for
                    c["_skip"] = None
                    if skip_slow and c.get("slow"):
                        c["_skip"] = "slow"
                    if only_slow and not c.get("slow"):
                        c["_skip"] = "not slow"
                    if c.get("may_notify") and not (allow_notify or has_person):
                        c["_skip"] = "may_notify: set FIELD_ALLOW_NOTIFY=1 or FIELD_NOTIFY_LOG"
                    if c.get("brain_only") and device_head:
                        c["_skip"] = "brain_only: the case is about the brain's own browser, not a device head"
                    if c["id"] in skip_ids:
                        c["_skip"] = "FIELD_SKIP"
                    if c.get("person") and not has_person:
                        c["_skip"] = "person: needs FIELD_NOTIFY_LOG"
                    cases.append(c)
    return [c for c in cases if not c.get("late")] + [c for c in cases if c.get("late")]


BIG = re.compile(r"\{BIG:(\d+)(?::([^}]*))?\}")
SAVED = {}  # name -> the ref `save_ref` took on an earlier page (a stale ref is one the page it came from no longer has)


def fill_site(value, site, alt):
    if isinstance(value, str):
        value = BIG.sub(lambda m: (m.group(2) or "A") * int(m.group(1)), value)  # {BIG:n} or {BIG:n:xy}: a string of n repeats
        value = re.sub(r"\{SAVED:([^}]+)\}", lambda m: SAVED.get(m.group(1), "n0-unsaved"), value)
        port = int(site.rsplit(":", 1)[1].split("/")[0]) if site.rsplit(":", 1)[-1].isdigit() else 80  # {PORT}: the own site's port; {OTHERPORT}: the next one, where nothing is allowed
        return (value.replace("{SITE}", site).replace("{ALT}", alt).replace("{PERSON}", PERSON)
                .replace("{OTHERPORT}", str(port + 1)).replace("{PORT}", str(port)))
    if isinstance(value, dict):
        return {fill_site(k, site, alt): fill_site(v, site, alt) for k, v in value.items()}
    if isinstance(value, list):
        return [fill_site(v, site, alt) for v in value]
    return value


async def resolve_refs(sess, args, head):
    """`{REF:Full name}` in an argument becomes the ref `view` gives that label on the current page."""
    wanted = {m for v in args.values() if isinstance(v, str) for m in REF.findall(v)}
    if not wanted:
        return args
    LOOKUPS[0] += 1
    _, _, _, text = await call(sess, "view", {"head": head}, 30)
    nodes = [checks.node(n) for n in (checks.parse(text) or {}).get("nodes", [])]
    refs = {n.get("label"): n.get("ref") for n in nodes}
    return {k: REF.sub(lambda m: refs.get(m.group(1), "n0-missing"), v) if isinstance(v, str) else v for k, v in args.items()}


def notices(path):
    """The notices the capture head has written so far (kind, reason, link, ref ...)."""
    try:
        with open(path) as f:
            return [json.loads(x) for x in f if x.strip()]
    except OSError:
        return []


async def watch_person(path, seen, spec, own_host):
    """The person: wait for a new notice in the capture log, then open its link and press the button the case names.
    No button (`press` null) is a person who never answers. Answers what the page said, never the link."""
    for tick in range(int(spec.get("watch_s", 30) / 0.25)):
        rows = notices(path)
        new = [n for n in rows[seen:] if n.get("event") == "notify"]
        if not new and tick >= 4:  # a held act asked before this case is still one open request: its notice is the one to answer
            cleared = {n.get("ref") for n in rows if n.get("event") == "clear"}
            new = [n for n in rows[:seen] if n.get("event") == "notify" and n.get("ref") not in cleared
                   and n.get("kind") == (spec.get("notice") or {}).get("kind") and n["at"] + n.get("ttl_s", 0) > time.time()][-1:]
        if new:
            note = {"kind": new[0].get("kind"), "reason": new[0].get("reason")}
            if spec.get("answer") == "done":  # a wall: the notice shows the agent's browser; Done is the head's answer
                page = await person.act(new[0]["link"])
                await CAPTURE.done(new[0]["ref"])
                note.update(title=page.get("title"), opened=page.get("status"))
            elif spec.get("press"):
                page = await person.act(new[0]["link"], spec["press"], spec.get("value"), own_host)
                note.update(title=page.get("title"), buttons=page.get("buttons"), after=page.get("after"), refused=page.get("refused"))
            return note
        await asyncio.sleep(0.25)
    return {"kind": None, "why": "no notice reached the capture head"}


async def person_case(sess, c, args, site, notify, head, row, raw):
    """A case with a person: the call, the person answering through the capture head, then (`repeat`) the same call again until the
    answer is no longer `awaiting_approval`. Judged on the first answer (`expect`) and the last (`person.expect_after`) and on
    the site's POST count (`person.posts`), which is then reset. Every call is a line of raw.jsonl."""
    spec = c["person"]
    own_host = site.split("//")[-1].split(":")[0]
    if spec.get("prime"):  # the person is named once, so a held act that names no head finds them
        await call(sess, "ask_human", {"reason": "field: where the person is", "timeout": 1, "person_at": PERSON}, 20)
        await asyncio.sleep(1.5)
    seen = len(notices(notify))
    posts0 = site_count(site)["posts"]
    watcher = asyncio.create_task(watch_person(notify, seen, spec, own_host))
    steps, failed = [], []
    for n in range(1 + int(spec.get("repeat", 0))):
        if n:
            await asyncio.sleep(spec.get("wait_s", 0.5))
            if watcher.done() is False:
                await asyncio.wait_for(asyncio.shield(watcher), 60)
        t0, t1, is_err, text = await call(sess, c["tool"], args, c.get("timeout_s", 90))
        steps.append((t0, t1, is_err, text))
        raw.write(json.dumps({**row, "case_id": c["id"], "step": n, "args": args, "wall_ms": round((t1 - t0) * 1000, 1), "is_error": is_err,
                              "text": text}) + "\n")
        if n == 0:
            failed += checks.evaluate(c.get("expect", {}), text, is_err, (t1 - t0) * 1000)
        if "awaiting_approval" not in text:
            break  # the person's yes arrived inside the call's own wait, or the second call settled it
    heard = await asyncio.wait_for(asyncio.shield(watcher), 60)
    last = steps[-1]
    if spec.get("expect_after"):
        failed += [f"after: {f}" for f in checks.evaluate(spec["expect_after"], last[3], last[2], (last[1] - last[0]) * 1000)]
    for key, want in (spec.get("notice") or {}).items():
        if heard.get(key) != want:
            failed.append(f"notice {key} = {heard.get(key)!r}, wanted {want!r}")
    if heard.get("refused"):
        failed.append(heard["refused"])
    if "posts" in spec:
        got = site_count(site)["posts"] - posts0
        if got != spec["posts"]:
            failed.append(f"site POSTs {got}, wanted {spec['posts']}")
        urllib.request.urlopen(urllib.request.Request(site + "/reset", data=b"", method="POST"), timeout=5).read()
    return steps[0], failed, {"heard": heard, "steps": len(steps), "last_text": last[3]}


async def call(sess, tool, args, timeout):
    t0 = time.time()
    try:
        res = await asyncio.wait_for(sess.call_tool(tool, args), timeout)
        text = "\n".join(getattr(c, "text", None) or f"<{c.type}>" for c in res.content)
        return t0, time.time(), bool(res.isError), text
    except asyncio.TimeoutError:
        return t0, time.time(), True, f"[client_timeout] no answer in {timeout}s"
    except Exception as e:  # a transport failure is a result of the case, not of the runner
        return t0, time.time(), True, f"[client_exception] {type(e).__name__}: {e}"


def markdown(s):
    """The committed face of a run: counts, the POST proof, every non-pass case with its reason, every case's time."""
    lines = [f"# Field run {s['run_id']}", "",
             f"mode `{s['mode']}`, head `{s['head']}`, site {s['site']}. Cases pass/fail/skip: {s['pass']}/{s['fail']}/{s['skip']}.",
             f"**Site POSTs before/after: {s['posts_before']}/{s['posts_after']}** (uploads {s['uploads_after']}); a safe run ends at 0.",
             f"SSRF canary hits (127.0.0.2, never allowed): {s.get('canary_after')}; a safe run ends at 0 (None: no canary site was running).", ""]
    bad = [c for c in s["cases"] if c["verdict"] != "pass"]
    if bad:
        lines += ["## Failed and skipped", "", "| case | tool | verdict | why |", "|---|---|---|---|"]
        for c in bad:
            lines.append(f"| {c['case_id']} | {c['tool']} | {c['verdict']} | {'; '.join(c.get('failed') or []) or c.get('why', '')}"
                         f"{' (finding ' + c['finding'] + ')' if c.get('finding') else ''} |")
        lines.append("")
    lines += ["## All cases", "", "| case | tool | verdict | ms |", "|---|---|---|---|"]
    lines += [f"| {c['case_id']} | {c['tool']} | {c['verdict']} | {c.get('wall_ms', '-')} |" for c in s["cases"]]
    return "\n".join(lines) + "\n"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", default="")
    ap.add_argument("--skip-slow", action="store_true")
    ap.add_argument("--only-slow", action="store_true", help="run only the slow (hang) cases")
    ap.add_argument("--files", default="", help="weakness suite: only the case files whose name starts with one of these (a1,a2,a5; a6 freezes or exhausts a brain: run it alone, last)")
    ap.add_argument("--ids", default="", help="weakness suite: only the cases whose id contains one of these words (a repro of a finding)")
    ap.add_argument("--suite", default="field", choices=["field", "weakness"], help="weakness: cases/weakness/*.jsonl, hostile arguments, odd pages, safety (ADR 0463)")
    ap.add_argument("--out", default="")
    ap.add_argument("--mode", default=os.environ.get("FIELD_MODE", "b-headless"))
    ap.add_argument("--repeat", type=int, default=1)
    a = ap.parse_args()
    site = os.environ.get("FIELD_SITE", "http://127.0.0.1:8791")
    alt = os.environ.get("FIELD_SITE_ALT", site.replace("127.0.0.1", "localhost"))  # same site, another host name
    head = os.environ.get("FIELD_HEAD", "bench-server.b")
    url = os.environ.get("MC_URL", "http://127.0.0.1:47870/mcp")
    notify = os.environ.get("FIELD_NOTIFY_LOG", "")
    head_task = None
    if os.environ.get("FIELD_PERSON_KEY_FILE") and notify:
        import notify_head  # the capture head: this runner is the person's screen for the run
        with open(os.path.expanduser(os.environ["FIELD_PERSON_KEY_FILE"])) as f:
            pkey = f.read().strip()
        from interfaces.head_config import load_identity
        mode = PERSON.split(".")[1]
        global CAPTURE
        CAPTURE = notify_head.make_client(os.environ["FIELD_HEADS_URL"], pkey, notify,
                                          load_identity(Path(os.path.expanduser(os.environ["FIELD_PERSON_KEY_FILE"])).with_suffix(".dev")), mode)
        head_task = asyncio.create_task(CAPTURE.run())
        await asyncio.sleep(3)
    run_id = "fld-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:4]
    out = a.out or os.path.join(HERE, "..", "results", datetime.date.today().isoformat(), run_id)
    os.makedirs(out, exist_ok=True)
    tools = [t for t in a.tools.split(",") if t]
    device = head != os.environ.get("FIELD_BRAIN_HEAD", "bench-server.b")
    skip_ids = [x for x in os.environ.get("FIELD_SKIP", "").split(",") if x]
    if a.suite == "weakness":
        cases = load_weakness(a.skip_slow, os.environ.get("FIELD_ALLOW_NOTIFY") == "1", bool(notify), device, skip_ids,
                              [x for x in a.files.split(",") if x])
        if tools:
            cases = [c for c in cases if c["tool"] in tools]
        if a.ids:
            cases = [c for c in cases if any(w in c["id"] for w in a.ids.split(","))]
    else:
        cases = load_cases(tools, a.skip_slow, os.environ.get("FIELD_ALLOW_NOTIFY") == "1", bool(notify), device, skip_ids, a.only_slow)
    before = site_count(site)
    canary0 = canary_count(site)
    if a.suite == "weakness" and canary0 is None:
        print("warning: no canary site on 127.0.0.2: cases that carry `canary` only prove the refusal, not the absence of a request")
    rows, raw = [], open(os.path.join(out, "raw.jsonl"), "a")
    async with streamablehttp_client(url, headers={"Authorization": "Bearer " + token()}) as (r, w, _):
        async with ClientSession(r, w) as sess:
            await sess.initialize()
            if os.environ.get("FIELD_OWN_TAB") == "1":  # a device head has the person's tab: work in one of the agent's own (`tab_named`)
                await call(sess, "tabs", {"action": "open", "url": "about:blank", "head": head}, 30)
            for rep in range(a.repeat):
                for c in cases:
                    row = {"run_id": run_id, "case_id": c["id"], "tool": c["tool"], "mode": a.mode, "head": head, "rep": rep}
                    if c.get("finding"):
                        row["finding"] = c["finding"]  # a case that fails because of a recorded product finding says which
                    if c["_skip"]:
                        row.update(verdict="skip", why=c["_skip"])
                        rows.append(row)
                        raw.write(json.dumps(row) + "\n")
                        continue
                    lookups0 = LOOKUPS[0]
                    args = fill_site(c.get("args", {}), site, alt)
                    if c["tool"] not in NO_HEAD:
                        args.setdefault("head", head)
                    for var, label in (c.get("save_ref") or {}).items():  # take the ref of `label` on this page, for a later stale use
                        SAVED[var] = (await resolve_refs(sess, {"x": "{REF:" + label + "}"}, head))["x"]
                    args = await resolve_refs(sess, args, head)
                    if c.get("person"):
                        (t0, t1, is_err, text), failed, extra = await person_case(sess, c, args, site, notify, head, row, raw)
                        row["person"] = extra["heard"]
                        row["steps"] = extra["steps"]
                    else:
                        t0, t1, is_err, text = await call(sess, c["tool"], args, c.get("timeout_s", 90))
                        failed = checks.evaluate(c.get("expect", {}), text, is_err, (t1 - t0) * 1000)
                        if "canary" in c and canary0 is not None:  # a case that sends the brain toward the canary: it must stay unreached
                            await asyncio.sleep(1.5)
                            reached = canary_count(site) - canary0
                            if reached:
                                failed.append(f"SSRF: the canary on 127.0.0.2 was reached {reached} time(s)")
                            canary0 = canary_count(site)
                    wall = (t1 - t0) * 1000
                    row.update(args=args, ref_lookups=LOOKUPS[0] - lookups0, start_ms=int(t0 * 1000), end_ms=int(t1 * 1000), wall_ms=round(wall, 1),
                               is_error=is_err, bytes=len(text.encode()), failed=failed,
                               verdict="fail" if failed else "pass", text=text)
                    raw.write(json.dumps(row) + "\n")
                    raw.flush()
                    rows.append({k: v for k, v in row.items() if k not in ("text", "args")})
                    print(f"{row['verdict']:4} {c['id']:34} {wall:8.0f} ms  {'; '.join(failed)}", flush=True)
    after = site_count(site)
    raw.close()
    if head_task:
        head_task.cancel()
    summary = {"canary_after": canary_count(site), "run_id": run_id, "mode": a.mode, "head": head, "site": site, "posts_before": before["posts"],
               "posts_after": after["posts"], "uploads_after": after["uploads"],
               "pass": sum(r["verdict"] == "pass" for r in rows), "fail": sum(r["verdict"] == "fail" for r in rows),
               "skip": sum(r["verdict"] == "skip" for r in rows), "cases": rows}
    with open(os.path.join(out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    with open(os.path.join(out, "summary.md"), "w") as f:
        f.write(markdown(summary))
    print(f"run_id={run_id} pass={summary['pass']} fail={summary['fail']} skip={summary['skip']} "
          f"posts_after={after['posts']} out={out}")
    return 0 if summary["fail"] == 0 and after["posts"] == 0 and not summary["canary_after"] else 1


if __name__ == "__main__":
    try:
        code = asyncio.run(main())
    except SystemExit:
        raise
    except BaseException:  # the MCP client wraps what its tasks raise in exception groups: catch them all, say what happened, exit 70
        traceback.print_exc()
        code = 70
    sys.exit(code)
