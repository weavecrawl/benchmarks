"""The delegate suite: does one `delegate_task` call reach a simple multi-step goal on a public practice site, and does it say ok only then?

Field finding (2026-10-11, footage run on the live brain): 0 of 11 simple goals reached ("open books.toscrape.com then open the
Travel category then open the first book" ended blocked or goal_not_reached after wandering), and one answered ok after opening only the
start page. The goals of delegate_goals.json were fixed before any change to delegate_task.

For each goal and each rep, in a session of its own (`session(open)` ... `session(close)`):
  run     `delegate_task(goal, session_id, max_steps)`: timed; the product's answer kept (ok, reason, steps, the url it names).
  verify  `read(level="outline")` of the same session: the address the page is really on. The goal REACHED only when that address is one
          of the goal's `reach` addresses (compared without fragment and trailing slash). PASS = the product said ok AND it reached.
          ok on any other page is a FALSE SUCCESS (the bug this suite exists for), counted apart and never a pass.
  site    when a goal was not reached, the first `reach` address is fetched plainly: a site that does not answer 200 is `site_failed`
          (the site was down or changed), not a fault of the product.

What this does NOT do: judge any goal that needs a page to be read and answered (a question), a form filled or a search typed; it does
not run a decision model (the scratch brain has no `<NS>_DECISION_BASE_URL`, the same as every installed brain).
"""
import asyncio
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
GOALS = os.path.join(HERE, "delegate_goals.json")


def load():
    with open(GOALS, encoding="utf-8") as f:
        return json.load(f)


def expected(spec):
    """Rows a whole run leaves: one per goal and rep."""
    return len(spec["goals"]) * spec["reps"]


def norm(address):
    """An address without its fragment and trailing slash (a site may redirect /a to /a/); the query is kept."""
    parts = urllib.parse.urlsplit(address or "")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), parts.query, ""))


def reached(seen, reach):
    """Whether the address an independent read reported is one of the goal's addresses."""
    return bool(seen) and norm(seen) in {norm(r) for r in reach}


def site_status(url, timeout=15):
    """The HTTP status a plain GET of `url` gets (with a browser-like agent string: some practice sites refuse Python's), or 0 when it does not answer."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) bench"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except (OSError, ValueError):
        return 0


def run(ctx, run_id, scratch):
    """Run every goal of delegate_goals.json `reps` times through one scratch brain. Answers (rows, info). `ctx` is run.py's Ctx."""
    spec = load()
    brain = ctx.new_brain(os.path.join(scratch, "delegate-brain"), 0)
    brain.start()
    rows = []
    on = ctx.head.replace(".", "/")  # `bench-server.b` names the scratch brain's own browser; session(open) takes device/mode

    async def go(sess):
        async def call(tool, args, timeout=90):
            t0, t1, is_err, text = await ctx.call(sess, tool, args, timeout)
            return {"ms": round((t1 - t0) * 1000, 1), "start_ms": int(t0 * 1000), "end_ms": int(t1 * 1000), "err": bool(is_err), "text": text}

        for rep in range(spec["reps"]):
            for g in spec["goals"]:
                await asyncio.sleep(spec["pause_s"])
                opened = await call("session", {"action": "open", "on": on})
                sid = (ctx.parse(opened["text"]) or {}).get("session_id")
                d = await call("delegate_task", {"goal": g["goal"], "session_id": sid, "max_steps": spec["max_steps"]}, 240)
                answer = ctx.parse(d["text"]) or {}
                v = await call("read", {"level": "outline", "session_id": sid})
                seen = (ctx.parse(v["text"]) or {}).get("url")
                await call("session", {"action": "close", "session_id": sid})
                arrived = reached(seen, g["reach"])
                said_ok = not d["err"] and answer.get("ok") is True
                status = None if arrived else site_status(g["reach"][0])
                rows.append({"suite": "delegate", "kind": "goal", "run_id": run_id, "goal": g["id"], "rep": rep,
                             "ms": d["ms"], "start_ms": d["start_ms"], "end_ms": d["end_ms"],
                             "session": sid is not None, "err": d["err"], "said_ok": said_ok, "reason": answer.get("reason") or (answer.get("error") or "")[:120] or None,
                             "steps": answer.get("steps_taken"), "said_url": answer.get("url"), "seen": seen, "arrived": arrived,
                             "passed": said_ok and arrived, "false_success": said_ok and not arrived,
                             "decision_model": answer.get("decision_model") is not None, "verify_ok": not v["err"],
                             "site_status": status, "site_failed": status is not None and status != 200,
                             "answer": d["text"][:400]})

    try:
        asyncio.run(ctx.connect(brain, go))
        observed = ctx.observe(brain)
    finally:
        brain.stop()
    info = {"delegate": {"goals": [{"id": g["id"], "goal": g["goal"], "reach": g["reach"]} for g in spec["goals"]],
                         "reps": spec["reps"], "max_steps": spec["max_steps"]},
            "brain": observed[0], "models": observed[1]}
    return rows, info
