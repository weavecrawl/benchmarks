"""The replay suite: what walking a saved path costs, and what the product's stored route is worth through the tools an agent has.

Old claim (the 2026-09 public repository): "0.223 ms replay, 7,415x faster". a later check found that number was a path lookup on a made-up map, not a
replay (a real hop costs 337 to 409 ms). This suite measures the real thing on sites built for automated access, routes fixed in
replay_routes.json before any run.

For each route (a list of addresses) and each run k = 1, 2, ... up to the site's last count:
  walk    open the first address with `goto`, then for each next address find its link on the page (`read(shape="full")`, the controls with
          their href), `click` it. Each hop is a timed row: ms, tokens of the answer, the address the product says it reached, and the address
          an independent `read` of the page then reports (the next find, or one extra `read` after the last hop). A hop ARRIVED only when
          that independent address is the hop's address (compared without a trailing slash: a site may redirect /a to /a/): an answer of `ok` from a call that did not move the page fails here (ADR 0333's bug).
  at runs 1, 5, 20 (and 100 on the own site), after the walk:
          open the first address again, ask the stored route to the last address (`goto(url=last, plan=true)`, the route lookup alone: this is
          what "0.2 ms" measured, now timed through the MCP) and record the product's answer as it is, then load the last address by
          address (`goto(url=last)`) and check arrival the same way.

What this does NOT do, and why: it does not call the stored route a replay. In this product `goto` replays stored steps only for a page
id that is not an address; the pages the brain maps from a visit have their address as id, and `goto` of an address loads the
address. So there is no tool call that replays a walked route of such a page, and the summary says what `plan` answered at each run count
(a move must earn trust before it is priced) instead of timing something that did not happen.
"""
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.dirname(HERE)
ROUTES = os.path.join(HERE, "replay_routes.json")


def load():
    with open(ROUTES, encoding="utf-8") as f:
        return json.load(f)


def addresses(site, base):
    """The routes of a site with every hop as a full address (the own site's hops are paths)."""
    return [(r["id"], [urllib.parse.urljoin(base + "/", h) if h.startswith("/") else h for h in r["hops"]]) for r in site["routes"]]


def expected(spec):
    """Rows a whole run leaves: per route and run: the first goto, then per hop a find and a click, and one verify; per checkpoint: a goto, a plan, an address load and its verify."""
    out = 0
    for site in spec["sites"]:
        for route in site["routes"]:
            hops = len(route["hops"]) - 1
            out += max(site["runs"]) * (1 + 2 * hops + 1) + len(site["runs"]) * 4
    return out


def norm(address):
    """An address without its fragment and trailing slash: a site may answer /author/x with a redirect to /author/x/ (quotes.toscrape.com does), and the
    page it lands on is the page asked for. The query is kept (the own site's pagination lives in it)."""
    parts = urllib.parse.urlsplit(address or "")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), parts.query, ""))


def node_for(graph_text, target):
    """The id the stored graph gives the page of `target` (ids are normalised addresses), else None."""
    try:
        nodes = json.loads(graph_text).get("nodes") or []
    except (ValueError, AttributeError):
        return None
    return next((n["id"] for n in nodes if norm(n.get("id")) == norm(target)), None)


def find_link(read_text, target):
    """(page address, ref) of the link to `target` in a `read(shape="full")` answer, else (page address, None). hrefs are resolved against the page's address."""
    try:
        page = json.loads(read_text)
    except ValueError:
        return None, None
    base = page.get("url") or ""
    for block in page.get("blocks") or []:
        if block.get("kind") == "control" and block.get("role") == "link" and block.get("href") and block.get("ref"):
            if norm(urllib.parse.urljoin(base, block["href"])) == norm(target):
                return base, block["ref"]
    return base, None


def plan_outcome(is_err, text):
    """What `goto(plan)` answered, as one word and the route length: route (a stored route), not_trusted (a move has not earned trust), no_route, other."""
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    if not is_err and isinstance(parsed, dict):
        if parsed.get("ok") is False:
            return parsed.get("reason") or "no_route", 0
        return "route", len(parsed.get("route") or [])
    low = text.lower()
    return ("not_trusted" if "not_trusted" in low else "no_route" if "no_route" in low else "not_a_node" if "bad_url" in low else "other"), 0


def seen_url(text):
    try:
        return json.loads(text).get("url")
    except (ValueError, AttributeError):
        return None


def run(ctx, run_id, scratch):
    """Walk every route of replay_routes.json through one brain. Answers (rows, info). `ctx` is run.py's Ctx (brain, MCP connection, call)."""
    import tiktoken
    enc = tiktoken.get_encoding(ctx.tokenizer)
    spec = load()
    field_port = ctx.free_port()
    server = subprocess.Popen([sys.executable, os.path.join(CORE, "tests", "field", "site", "server.py"), "--port", str(field_port)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    for _ in range(100):
        try:
            ctx.get(f"http://127.0.0.1:{field_port}/count", 1)
            break
        except OSError:
            time.sleep(0.1)
    brain = ctx.new_brain(os.path.join(scratch, "replay-brain"), field_port)
    brain.start()
    rows = []

    async def go(sess):
        async def call(tool, args):
            t0, t1, is_err, text = await ctx.call(sess, tool, {**args, "head": ctx.head}, 90)
            return {"ms": round((t1 - t0) * 1000, 1), "start_ms": int(t0 * 1000), "end_ms": int(t1 * 1000), "tokens": len(enc.encode(text)), "err": bool(is_err), "text": text}

        def row(kind, site, route, **kw):
            r = {"suite": "replay", "kind": kind, "run_id": run_id, "site": site["id"], "route": route, **kw}
            rows.append(r)
            return r

        def timed(c):
            return {"ms": c["ms"], "start_ms": c["start_ms"], "end_ms": c["end_ms"], "tokens": c["tokens"]}

        for site in spec["sites"]:
            base = f"http://127.0.0.1:{field_port}" if site["own"] else ""
            for rid, hops in addresses(site, base):
                for k in range(1, max(site["runs"]) + 1):
                    await walk(call, row, timed, site, rid, hops, k)
                    if k in site["runs"]:
                        await checkpoint(call, row, timed, site, rid, hops, k)

    async def pause(site):
        if site["pause_s"]:
            await asyncio.sleep(site["pause_s"])

    async def walk(call, row, timed, site, rid, hops, k):
        await pause(site)
        c = await call("goto", {"url": hops[0]})
        status = (ctx.parse(c["text"]) or {}).get("status")
        pending = row("hop", site, rid, run=k, hop=0, via="goto", target=hops[0], claimed=norm(seen_url(c["text"])) == norm(hops[0]), status=status,
                      ok=not c["err"] and (ctx.parse(c["text"]) or {}).get("loaded") is True, site_failed=status not in (None, 200), **timed(c))
        for i in range(1, len(hops)):
            await pause(site)
            f = await call("read", {"shape": "full"})
            page, ref = find_link(f["text"], hops[i])
            pending["seen"], pending["arrived"] = page, norm(page) == norm(hops[i - 1])
            row("find", site, rid, run=k, hop=i, found=ref is not None, ok=not f["err"], **timed(f))
            if ref is None:
                for j in range(i, len(hops)):  # the page has no link to the next address: the site changed; the rest of the route cannot be walked
                    pending = row("hop", site, rid, run=k, hop=j, via="click", target=hops[j], claimed=False, status=None, ok=False, site_failed=True, ms=None, start_ms=None, end_ms=None, tokens=0, seen=None, arrived=False)
                    if j > i:
                        row("find", site, rid, run=k, hop=j, found=False, ok=False, site_failed=True, ms=None, start_ms=None, end_ms=None, tokens=0)
                row("verify", site, rid, run=k, ok=False, ms=None, start_ms=None, end_ms=None, tokens=0, seen=None)
                return
            c = await call("click", {"ref": ref})
            pending = row("hop", site, rid, run=k, hop=i, via="click", target=hops[i], claimed=norm(seen_url(c["text"])) == norm(hops[i]), status=None, ok=not c["err"], site_failed=False, **timed(c))
        v = await call("read", {"level": "outline"})
        pending["seen"], pending["arrived"] = seen_url(v["text"]), norm(seen_url(v["text"])) == norm(hops[-1])
        row("verify", site, rid, run=k, ok=not v["err"], **timed(v))

    async def checkpoint(call, row, timed, site, rid, hops, k):
        await pause(site)
        c = await call("goto", {"url": hops[0]})
        row("hop", site, rid, run=k, hop=0, via="goto", phase="checkpoint", target=hops[0], claimed=norm(seen_url(c["text"])) == norm(hops[0]), status=(ctx.parse(c["text"]) or {}).get("status"),
            ok=not c["err"], site_failed=False, **timed(c))
        node = node_for((await call("maps", {"action": "graph"}))["text"], hops[-1])
        p = await call("goto", {"url": node or hops[-1], "plan": True})
        outcome, length = plan_outcome(p["err"], p["text"])
        row("plan", site, rid, run=k, target=hops[-1], node=node, outcome=outcome, route_len=length, answer=p["text"][:240], **timed(p))
        await pause(site)
        a = await call("goto", {"url": hops[-1]})
        v = await call("read", {"level": "outline"})
        row("address", site, rid, run=k, target=hops[-1], claimed=norm(seen_url(a["text"])) == norm(hops[-1]), seen=seen_url(v["text"]), arrived=norm(seen_url(v["text"])) == norm(hops[-1]),
            ok=not a["err"], **timed(a))
        row("verify", site, rid, run=k, phase="checkpoint", ok=not v["err"], **timed(v))

    try:
        asyncio.run(ctx.connect(brain, go))
        observed = ctx.observe(brain)
        posts = json.loads(ctx.get(f"http://127.0.0.1:{field_port}/count"))["posts"]
    finally:
        brain.stop()
        server.terminate()
    return rows, {"replay": {"sites": [{"id": s["id"], "own": s["own"], "runs": s["runs"], "routes": [{"id": r["id"], "hops": len(r["hops"]) - 1} for r in s["routes"]]} for s in spec["sites"]],
                             "posts_after": posts}, "brain": observed[0], "models": observed[1]}
