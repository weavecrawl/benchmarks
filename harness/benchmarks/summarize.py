"""The only writer of a bench summary: env.json + raw.json in, summary.json + summary.md out.

Why it is its own file: a summary must be something a reader can re-make. The gate
(tests/gates/test_bench_door_gate.py) calls `check` on every committed run and fails when the committed
summary differs by one byte from what `render` makes of the raw rows, so a hand-edited number cannot land.
Pure: no clock, no machine, no network. Stdlib only, so the gate needs no bench dependency.

    python3 summarize.py <results/run_id>      re-write the summary of one run from its raw rows
"""
import bisect
import collections
import datetime
import json
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_rules as rules  # noqa: E402  pure and stdlib only, like this file
import browsecomp as bc  # noqa: E402  its rules (cause, the keys a row may hold) are pure; agent.py only imports agent_rules at the top

FILES = ("env.json", "raw.json", "summary.json", "summary.md")
LEDGER = "RUNS.tsv"  # beside the run folders: one line for every run the door ever made, kept or dropped, so a try cannot vanish
LEDGER_HEAD = "run_id\tcommit\tverdicts\tstatus\twhy"
LOOPBACK = "Own loopback site, hand-made pages: latency and token numbers do not transfer to real sites."
LIVE_AGENT = ("Live third-party sites, one small model as agent and the same model family as judge: a task passes or fails with the site of the day, "
              "so this is not a repeatable number and not the paper's; no time is measured in this run.")
LIVE_BROWSECOMP = ("Live web, one small model as agent and the same model family as grader: a problem passes or fails with the web of the day, so this is not a repeatable "
                    "number and not OpenAI's; no time is measured in this run.")
CORPUS = "Public data (saved pages, pinned by commit) served from loopback: no network is in the timings, and the pages are saved copies, not the live sites."
LIVE = "The replay suite reaches two third-party public sandbox sites over the network: its timings there include the network and the site, and change with both."
LIVE_DELEGATE = ("The delegate suite reaches public practice sites over the network: a goal is reached or not on the site of the day, and its timings include "
                 "the network and the site.")
SITE_SUITES = ("startup", "tools", "payload")


def stats(values):
    """n, median, p95, min, max and the spread (p75 - p25) of a list of milliseconds; linear interpolation."""
    v = sorted(x for x in values if x is not None)
    if not v:
        return {"n": 0, "median": None, "p95": None, "min": None, "max": None, "iqr": None}
    q = statistics.quantiles(v, n=100, method="inclusive") if len(v) > 1 else [v[0]] * 99
    return {"n": len(v), "median": round(statistics.median(v), 1), "p95": round(q[94], 1), "min": round(v[0], 1),
            "max": round(v[-1], 1), "iqr": round(q[74] - q[24], 1)}


class Meter:
    """Throttle events (memory.events `high` + cpu.stat `nr_throttled`, both cumulative) around one measured call, from the
    `machine` rows of the same run: the count at the first sample at or after the call's end minus the count at the last sample at
    or before its start. 0: the machine did not throttle the job during the call. None: the call has no sample on one side, or no
    start/end time, so nothing shows the machine quiet. Pure: the rows are all it reads."""

    def __init__(self, machine_rows):
        rows = sorted(machine_rows, key=lambda r: r["t_ms"])
        self.t = [r["t_ms"] for r in rows]
        self.n = [r["mem_high"] + r["cpu_throttled"] for r in rows]

    def around(self, r):
        start, end = r.get("start_ms"), r.get("end_ms")
        if start is None or end is None or not self.t:
            return None
        i, j = bisect.bisect_right(self.t, start) - 1, bisect.bisect_left(self.t, end)
        return None if i < 0 or j >= len(self.t) else self.n[j] - self.n[i]


class Quiet:
    """The quiet verdict over a set of calls: all their times, the times of those the machine did not throttle, the counts."""

    def __init__(self, meter):
        self.meter, self.all, self.quiet, self.throttled, self.unobserved = meter, [], [], 0, 0

    def add(self, row, ms):
        self.all.append(ms)
        over = self.meter.around(row)
        if over is None:
            self.unobserved += 1
        elif over:
            self.throttled += 1
        else:
            self.quiet.append(ms)

    def out(self):
        return {"ms": stats(self.all), "ms_quiet": stats(self.quiet), "throttled": self.throttled, "unobserved": self.unobserved}


def _startup(rows, meter):
    q = {k: Quiet(meter) for k in ("health_ms", "first_goto_ms")}
    for r in rows:
        for k in q:
            q[k].add(r, r[k])
    return {**{k: q[k].out()["ms"] for k in q}, "quiet": {k: q[k].out()["ms_quiet"] for k in q},
            "throttled": q["health_ms"].throttled, "unobserved": q["health_ms"].unobserved,
            "first_goto_ok": sum(1 for r in rows if r["first_goto_ok"]), "reps": len(rows)}


def _tools(rows, meter):
    tools, cases, by_check = {}, {}, {}
    for r in rows:
        t = tools.setdefault(r["tool"], {"tool": r["tool"], "pass": 0, "fail": 0, "skip": 0, "_q": Quiet(meter), "_cold": [], "_warm": []})
        t[r["verdict"]] += 1
        if r["verdict"] == "pass":
            kind = r.get("check") or "unknown"
            by_check[kind] = by_check.get(kind, 0) + 1
            t["by_check"] = {**t.get("by_check", {}), kind: t.get("by_check", {}).get(kind, 0) + 1}
        c = cases.setdefault(r["case_id"], {"case_id": r["case_id"], "tool": r["tool"], "verdicts": [], "_q": Quiet(meter), "reasons": []})
        c["verdicts"].append(r["verdict"])
        if r["verdict"] == "skip":
            c["reasons"] = [r.get("why", "")]
            continue
        t["_q"].add(r, r["wall_ms"])
        (t["_cold"] if r["rep"] == 0 else t["_warm"]).append(r["wall_ms"])
        c["_q"].add(r, r["wall_ms"])
        for why in r.get("failed") or []:
            if why not in c["reasons"]:
                c["reasons"].append(why)
    per_tool = []
    for t in sorted(tools.values(), key=lambda x: x["tool"]):
        per_tool.append({"tool": t["tool"], "pass": t["pass"], "fail": t["fail"], "skip": t["skip"], "pass_by_check": t.get("by_check", {}), **t["_q"].out(),
                         "rep0_median": stats(t["_cold"])["median"], "later_median": stats(t["_warm"])["median"]})
    per_case = []
    for c in cases.values():
        v = c["verdicts"]
        per_case.append({"case_id": c["case_id"], "tool": c["tool"], "pass": v.count("pass"), "fail": v.count("fail"),
                         "skip": v.count("skip"), **c["_q"].out(), "reasons": c["reasons"]})
    per_case.sort(key=lambda c: (-(c["ms"]["p95"] or 0), c["case_id"]))
    return {"pass": sum(t["pass"] for t in per_tool), "fail": sum(t["fail"] for t in per_tool),
            "skip": sum(t["skip"] for t in per_tool), "pass_by_check": by_check, "ref_lookups": sum(r.get("ref_lookups") or 0 for r in rows),
            "per_tool": per_tool, "per_case": per_case}


def _payload(rows, meter):
    pages = {}
    for r in rows:
        p = pages.setdefault(r["page"], {})
        p.setdefault(r["call"], []).append(r)
    out = []
    for page, calls in pages.items():
        html, text = calls.get("http_get", []), calls.get("http_text", [])
        html_tokens = statistics.median([r["tokens"] for r in html]) if html else None
        text_tokens = statistics.median([r["tokens"] for r in text]) if text else None
        row = {"page": page, "html_tokens": html_tokens, "text_tokens": text_tokens, "calls": {}}
        for name, rs in calls.items():
            toks = [r["tokens"] for r in rs]
            q = Quiet(meter)
            for r in rs:
                q.add(r, r["wall_ms"])
            covers = rs[0].get("covers")
            # a ratio is a claim "this look costs X of the page": only a look that returns the whole page, in every rep, makes it. A navigation
            # receipt, an outline and a list of controls skip the prose by design, so their small token counts are not savings
            whole = covers == "page" and all(r["ok"] and r.get("complete") for r in rs)
            row["calls"][name] = {**q.out(), "covers": covers, "parts": max(r.get("parts") or 1 for r in rs), "tokens": statistics.median(toks),
                                  "tokens_min": min(toks), "tokens_max": max(toks), "ok": sum(1 for r in rs if r["ok"]), "n": len(rs),
                                  "vs_html": round(statistics.median(toks) / html_tokens, 3) if html_tokens and whole else None,
                                  "vs_text": round(statistics.median(toks) / text_tokens, 3) if text_tokens and whole else None}
        out.append(row)
    return out

def _pct(k, n):
    return None if not n else round(100 * k / n, 1)


def _agent(env, rows):
    """The agent suite: one line per task (its attempts and its final verdict) and the totals. First-attempt success counts a task whose
    first attempt was a completed, passing one; the final count adds the tasks that passed after a rerun of an attempt that failed for
    a model or infra reason. A blocked task (a bot wall a person must solve) is in neither and is listed apart."""
    by_task = collections.defaultdict(list)
    for r in rows:
        by_task[r["task"]].append(r)
    per_task, finals = [], {}
    for tid in env["agent"]["tasks"]:
        rs = sorted(by_task.get(tid, []), key=lambda r: r["attempt"])
        if not rs:
            continue
        first, last = rs[0], rs[-1]
        finals[tid] = last
        per_task.append({"task": tid, "site": last["site"], "ref_type": last["ref_type"], "attempts": len(rs), "first_pass": bool(first.get("final") and first.get("verdict") == "pass"),
                         "verdict": last.get("verdict"), "by": last.get("verdict_by"), "reason": last.get("reason"), "reruns": [r["infra_kind"] or "unrecorded" for r in rs[:-1]],
                         "turns": sum(r.get("turns") or 0 for r in rs), "wall_ms": sum(r.get("wall_ms") or 0 for r in rs), "brain_down": any(r.get("brain_down") for r in rs),
                         "held": sum(1 for r in rs for c in r["calls"] if c.get("held")), "walls": sorted({c["wall"] for r in rs for c in r["calls"] if c.get("wall")})})
    n = len(per_task)
    count = lambda v: sum(1 for t in per_task if t["verdict"] == v)  # noqa: E731
    first, final = sum(t["first_pass"] for t in per_task), count("pass")
    blocked, held = count("blocked"), count("held")
    unblocked = n - blocked - held  # a held task waits for a person like a blocked one does
    sites = collections.defaultdict(lambda: {"tasks": 0, "first": 0, "final": 0, "blocked": 0})
    for t in per_task:
        x = sites[t["site"]]
        x["tasks"] += 1
        x["first"] += t["first_pass"]
        x["final"] += t["verdict"] == "pass"
        x["blocked"] += t["verdict"] in ("blocked", "held")
    usage = collections.Counter()
    for r in rows:
        for k, v in (r.get("usage") or {}).items():
            if isinstance(v, (int, float)):
                usage[k] += v
    reruns = collections.Counter(r["infra_kind"] for r in rows if not r.get("final"))
    out = {"tasks": n, "first_pass": first, "first_pct": _pct(first, n), "first_ci": rules.wilson(first, n),
            "final_pass": final, "final_pct": _pct(final, n), "final_ci": rules.wilson(final, n),
            "final_pass_unblocked_pct": _pct(final, unblocked), "blocked": blocked, "fail": count("fail"), "infra_failed": count("infra_failed"),
            "attempts": len(rows), "reruns": sum(reruns.values()), "rerun_reasons": dict(sorted(reruns.items())),
            "reruns_that_passed": sum(1 for t in per_task if t["attempts"] > 1 and t["verdict"] == "pass"),
            "decided_by": dict(sorted(collections.Counter(t["by"] for t in per_task if t["verdict"] in ("pass", "fail")).items())),
            "pass_by": dict(sorted(collections.Counter(t["by"] for t in per_task if t["verdict"] == "pass").items())),
            "agent_runs": sum(1 for r in rows if r.get("agent_run")), "judge_runs": sum(((r.get("judge") or {}).get("runs") or 0) for r in rows),
            "turns": sum(t["turns"] for t in per_task), "wall_ms": sum(t["wall_ms"] for t in per_task),
            "cost_usd": round(sum(r.get("cost_usd") or 0 for r in rows), 4), "usage": dict(sorted(usage.items())),
            "tasks_with_held_call": sum(1 for t in per_task if t["held"]), "brain_down": [t["task"] for t in per_task if t["brain_down"]],
            "per_site": [{"site": k, **v} for k, v in sorted(sites.items())], "per_task": per_task}
    if env["agent"].get("judge_votes"):  # a run of the honest suite: the three numbers and the cause of every task that did not pass
        out["numbers"] = _numbers(env["agent"], per_task, finals)
    if env["agent"].get("head"):  # a run on a named head of a brain that was already running: what a person's device adds
        out.update(held=held, own_tabs=sum(r.get("own_tabs") or 0 for r in rows), tabs_left=sorted(i for r in rows for i in r.get("tabs_left") or []),
                   person_tab_calls=sum(1 for r in rows for c in r["calls"] if c.get("person_tab")))
    return out


def _numbers(e, per_task, finals):
    """Raw, doable today (without the tasks fixed before the run as not doable), unblocked (also without the bot-walled ones): each with its
    95% interval; the cause of every final attempt; what was re-dated or had a broken reference; how many judged tasks had a split vote."""
    done = {t["task"] for t in per_task if t["verdict"] == "pass"}
    walled = {t["task"] for t in per_task if t["verdict"] in ("blocked", "held", "site_fault")}  # a site that did not serve its page keeps a task out like a bot wall
    every = {t["task"] for t in per_task}
    doable = every - (set(e.get("not_doable", {})) - done)  # a task that passed is doable: the subsets never score below the raw passes
    unblocked = doable - walled
    share = lambda keep: {"pass": len(done & keep), "of": len(keep), "pct": _pct(len(done & keep), len(keep)), "ci": rules.wilson(len(done & keep), len(keep))}  # noqa: E731
    return {"raw": share(every), "doable": share(doable), "unblocked": share(unblocked), "not_doable": sorted(set(e.get("not_doable", {})) & every),
            "causes": dict(sorted(collections.Counter(rules.cause(r) for r in finals.values()).items())),
            "site_fault": sorted(t["task"] for t in per_task if t["verdict"] == "site_fault"),
            "redated": {t: r["redated_years"] for t, r in finals.items() if r.get("redated_years")},
            "broken_reference": sorted(t for t, r in finals.items() if r.get("reference_broken")),
            "reference_stale": sorted(t for t, r in finals.items() if r.get("reference_stale")),
            "split_votes": sum(1 for r in finals.values() if (r.get("judge") or {}).get("agree") not in (None, f"{e['judge_votes']}/{e['judge_votes']}"))}


def _browsecomp(env, rows):
    """The browsecomp suite: per problem its attempts and final verdict, the pass rate with its 95% interval, the cause of every problem that
    did not pass, the reruns, the model calls, and the tokens, tool calls and seconds each problem took."""
    by_task = collections.defaultdict(list)
    for r in rows:
        by_task[r["task"]].append(r)
    per_task, finals = [], []
    for tid in env["browsecomp"]["tasks"]:
        rs = sorted(by_task.get(tid, []), key=lambda r: r["attempt"])
        if not rs:
            continue
        finals.append(rs[-1])
        per_task.append({"task": tid, "attempts": len(rs), "verdict": rs[-1].get("verdict"), "cause": bc.cause(rs[-1]), "agree": (rs[-1].get("judge") or {}).get("agree"),
                         "turns": sum(r.get("turns") or 0 for r in rs), "tool_calls": sum(len(r["calls"]) for r in rs), "wall_ms": sum(r.get("wall_ms") or 0 for r in rs),
                         "tokens": sum((r.get("usage") or {}).get(k) or 0 for r in rs for k in ("input_tokens", "output_tokens"))})
    n = len(per_task)
    passed = sum(1 for t in per_task if t["verdict"] == "pass")
    usage = collections.Counter()
    for r in rows:
        for k, v in (r.get("usage") or {}).items():
            if isinstance(v, (int, float)):
                usage[k] += v
    reruns = collections.Counter(r["infra_kind"] for r in rows if not r.get("final"))
    med = lambda k: statistics.median(t[k] for t in per_task) if per_task else None  # noqa: E731
    return {"tasks": n, "passed": passed, "pct": _pct(passed, n), "ci": rules.wilson(passed, n),
            "causes": dict(sorted(collections.Counter(t["cause"] for t in per_task).items())),
            "attempts": len(rows), "reruns": sum(reruns.values()), "rerun_reasons": dict(sorted(reruns.items())),
            "split_votes": sum(1 for t in per_task if t["agree"] not in (None, f"{env['browsecomp']['judge_votes']}/{env['browsecomp']['judge_votes']}")),
            "agent_runs": sum(1 for r in rows if r.get("agent_run")), "judge_runs": sum(((r.get("judge") or {}).get("runs") or 0) for r in rows),
            "turns": sum(t["turns"] for t in per_task), "tool_calls": sum(t["tool_calls"] for t in per_task), "wall_ms": sum(t["wall_ms"] for t in per_task),
            "median_tool_calls": med("tool_calls"), "median_wall_ms": med("wall_ms"), "median_tokens": med("tokens"),
            "cost_usd": round(sum(r.get("cost_usd") or 0 for r in rows), 4), "usage": dict(sorted(usage.items())), "per_task": per_task}


def judge_field(r, mp, silent):
    """(scope, result, dangerous) of one Chrome field row. scope: in (Chrome's type has a slot of this product), out (it has none), silent
    (Chrome says nothing), excluded (the field could not be joined to a control and a product field: counted, never scored), unmapped
    (a Chrome type the vocabulary has no line for: the run is refused). result: agree / no_slot / wrong for `in`; none / named for `out`
    and `silent`; not_listed for any scope when the product listed no field for the control (Chrome lists hidden controls too, so this is
    counted apart and never scored as the product's miss). dangerous: the product named an identity-policy slot (the fill policy would fill it with no person) where the
    vocabulary says that slot is not the field's, or where Chrome's type has no slot at all."""
    t = r["chrome"]
    if r["join"] in ("no_control", "unverified", "no_view"):
        return "excluded", r["join"], False
    if t == silent:
        scope = "silent"
    elif t in mp:
        scope = "in" if mp[t] else "out"
    else:
        return "unmapped", None, False
    if r["join"] == "not_listed":
        return scope, "not_listed", False  # the control is on the page and the product listed no field for it (often a hidden one): not an answer
    slot = r.get("slot")
    if scope == "in":
        res = "agree" if slot in mp[t] else ("no_slot" if slot is None else "wrong")
    else:
        res = "none" if slot is None else "named"
    return scope, res, bool(slot) and scope != "silent" and res in ("wrong", "named") and r.get("policy") == "identity"


def _share(n, d):
    return round(n / d, 4) if d else None


def _forms_arm(rows, groups, mp, silent):
    out = {"fields": len(rows), "join": {}, "in": {"n": 0, "agree": 0, "no_slot": 0, "wrong": 0, "not_listed": 0}, "out": {"n": 0, "none": 0, "named": 0, "not_listed": 0},
           "silent": {"n": 0, "named": 0, "named_identity": 0, "not_listed": 0}, "dangerous": 0, "unmapped": 0, "learned": 0, "listed": 0,
           "by_conf": {}, "by_type": {}, "by_group": {}, "token": {"with": {"n": 0, "agree": 0}, "without": {"n": 0, "agree": 0}}, "named_where_none": {}}
    accepted = []
    for r in rows:
        out["join"][r["join"]] = out["join"].get(r["join"], 0) + 1
        out["listed"] += r["join"] == "ok"
        out["learned"] += bool(r.get("learned"))
        scope, res, danger = judge_field(r, mp, silent)
        if scope == "excluded":
            continue
        if scope == "unmapped":
            out["unmapped"] += 1
            continue
        out["dangerous"] += danger
        if res == "not_listed":
            out[scope]["not_listed"] += 1
            if scope != "silent":
                out["by_type"].setdefault(r["chrome"], {"scope": scope, "n": 0, "agree": 0, "no_slot": 0, "wrong": 0, "none": 0, "named": 0, "not_listed": 0})["not_listed"] += 1
            continue
        if scope == "silent":
            out["silent"]["n"] += 1
            out["silent"]["named"] += res == "named"
            out["silent"]["named_identity"] += res == "named" and r.get("policy") == "identity"
            continue
        out[scope]["n"] += 1
        out[scope][res] += 1
        t = out["by_type"].setdefault(r["chrome"], {"scope": scope, "n": 0, "agree": 0, "no_slot": 0, "wrong": 0, "none": 0, "named": 0, "not_listed": 0})
        t["n"] += 1
        t[res] += 1
        if scope == "out" and res == "named":
            out["named_where_none"][r["chrome"]] = out["named_where_none"].get(r["chrome"], 0) + 1
        if scope == "in":
            accepted.append(set(mp[r["chrome"]]))
            g = out["by_group"].setdefault(groups.get(r["page"], "?"), {"n": 0, "agree": 0})
            g["n"] += 1
            g["agree"] += res == "agree"
            if r.get("slot") is not None:
                c = out["by_conf"].setdefault(r.get("conf") or "none", {"n": 0, "agree": 0, "wrong": 0})
                c["n"] += 1
                c["agree"] += res == "agree"
                c["wrong"] += res == "wrong"
            if r.get("token") is not None:
                k = out["token"]["with" if r["token"] else "without"]
                k["n"] += 1
                k["agree"] += res == "agree"
    slots = sorted({x for a in accepted for x in a})
    best = max(((sum(1 for a in accepted if x in a), x) for x in slots), default=(0, None))  # answering one slot for every field: the stub to beat
    out["stub"] = {"slot": best[1], "agree": best[0], "n": len(accepted)}
    out["scored"] = out["in"]["n"] + out["out"]["n"]
    out["in"]["agree_share"] = _share(out["in"]["agree"], out["in"]["n"])
    out["in"]["wrong_share"] = _share(out["in"]["wrong"], out["in"]["n"])
    out["in"]["no_slot_share"] = _share(out["in"]["no_slot"], out["in"]["n"])
    out["out"]["none_share"] = _share(out["out"]["none"], out["out"]["n"])
    out["dangerous_share"] = _share(out["dangerous"], out["scored"])
    out["stub"]["agree_share"] = _share(best[0], len(accepted))
    return out


def _forms(rows, env, meter):
    """The forms suite from its rows: calls (timed), one row per Chrome field and arm, one per page and arm. Everything is counted from
    the rows and the vocabulary copied into env.json, so changing what counts as right changes the summary."""
    vocab = env["forms"]["vocabulary"]
    calls = [r for r in rows if r["kind"] == "call"]
    q = {}
    for r in calls:
        q.setdefault(r["call"], Quiet(meter)).add(r, r["wall_ms"])
    groups = {r["page"]: r["group"] for r in rows if r["kind"] == "page"}
    arms = {}
    for arm in sorted({r["arm"] for r in rows if r["kind"] == "field"}):
        arms[arm] = _forms_arm([r for r in rows if r["kind"] == "field" and r["arm"] == arm], groups, vocab["map"], vocab["silent"])
        arms[arm]["extra_fields"] = sum(len(r["extra"]) for r in rows if r["kind"] == "page" and r["arm"] == arm)
        arms[arm]["pages_by_group"] = {g: sum(1 for v in groups.values() if v == g) for g in sorted(set(groups.values()))}
    return {"pages": len(groups), "calls": {k: v.out() for k, v in sorted(q.items())}, "calls_failed": sum(1 for r in calls if not r["ok"]),
            "calls_n": len(calls), "arms": arms}


PAGES_BASELINES = ("html_text", "title")
PAGES_ARMS = ("read_url", "read_full")
BOOTSTRAP = 1000


def _prf(tfs):
    """Precision, recall and F1 of a list of (tp, fp, fn): the arithmetic of `metrics_from_tp_fp_fns` in the benchmark's evaluate.py
    (its precision_score and recall_score, averaged over the pages that have a prediction or a truth). The run records the benchmark's
    own numbers for the same predictions and `check` refuses a difference, so a copy that drifted is caught."""
    def p(tp, fp, fn):
        return 1.0 if fp == fn == 0 else (0.0 if tp == fp == 0 else tp / (tp + fp))

    def r(tp, fp, fn):
        return 1.0 if fp == fn == 0 else (0.0 if tp == fn == 0 else tp / (tp + fn))
    ps = [p(*t) for t in tfs if t[0] + t[1] > 0]
    rs = [r(*t) for t in tfs if t[0] + t[2] > 0]
    if not ps or not rs:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    pm, rm = statistics.mean(ps), statistics.mean(rs)
    return {"precision": pm, "recall": rm, "f1": 2 * pm * rm / (pm + rm) if pm + rm else 0.0}


def _arm_metrics(rows, with_std):
    """f1, precision, recall, accuracy (and the bootstrap spread, seeded) of rows that carry tp, fp, fn, acc."""
    tfs = [(r["tp"], r["fp"], r["fn"]) for r in rows]
    out = {**_prf(tfs), "accuracy": statistics.mean(r["acc"] for r in rows) if rows else 0.0, "n": len(rows)}
    if with_std and len(rows) > 1:
        rng, draws = random.Random(0), {"f1": [], "precision": [], "recall": [], "accuracy": []}
        for _ in range(BOOTSTRAP):
            pick = [rng.randint(0, len(rows) - 1) for _ in rows]
            m = _prf([tfs[i] for i in pick])
            for k in ("f1", "precision", "recall"):
                draws[k].append(m[k])
            draws["accuracy"].append(statistics.mean(rows[i]["acc"] for i in pick))
        out["std"] = {k: round(statistics.stdev(v), 6) for k, v in draws.items()}  # rounded: stdev differs in the last digit between Python 3.10 and 3.12, and the gate re-makes the summary on any machine
    return out


def _pages(rows, env, meter):
    """The pages suite from its rows: per-page tp/fp/fn of the product's looks (first repeat) and of the stubs, scored with the benchmark's arithmetic;
    tokens against the page's HTML, its text and the true article; time of every call; whether repeats gave the same words."""
    looks = [r for r in rows if r["kind"] == "look"]
    meta = {r["page"]: r for r in rows if r["kind"] == "page"}
    refused = sorted({r["page"] for r in looks if r.get("refused")})
    metrics = {}
    for arm in PAGES_ARMS:
        metrics[arm] = _arm_metrics([r for r in looks if r["look"] == arm and r["rep"] == 0 and not r.get("refused")], True)
    for arm in PAGES_BASELINES:
        metrics[arm] = _arm_metrics([r for r in rows if r["kind"] == "base" and r["arm"] == arm], True)
    tokens, latency, stable = {}, {}, {}
    for name in dict.fromkeys(r["look"] for r in looks):
        mine = [r for r in looks if r["look"] == name]
        first = [r for r in mine if r["rep"] == 0 and not r.get("refused")]
        q = Quiet(meter)
        for r in mine:
            q.add(r, r["wall_ms"])
        latency[name] = q.out()
        whole = first[0]["covers"] == "page" and all(r["ok"] for r in first)
        ratio = lambda key: round(statistics.median(r["tokens"] / meta[r["page"]][key] for r in first if meta[r["page"]][key]), 3) if whole else None  # noqa: E731
        tokens[name] = {"covers": first[0]["covers"], "median": statistics.median(r["tokens"] for r in first), "vs_html": ratio("html_tokens"),
                        "vs_text": ratio("text_tokens"), "vs_truth": ratio("truth_tokens"), "parts_max": max(r["parts"] for r in mine)}
        if name in PAGES_ARMS and len({r["rep"] for r in mine}) > 1:  # a look taken once says nothing about repeats
            by_page = {}
            for r in mine:
                by_page.setdefault(r["page"], set()).add(r.get("text_sha"))
            stable[name] = {"same": sum(1 for v in by_page.values() if len(v) == 1), "pages": len(by_page)}
    return {"pages": len(meta), "reps": max((r["rep"] for r in looks if r["look"] != "read_url"), default=-1) + 1,
            "url_reps": max((r["rep"] for r in looks if r["look"] == "read_url"), default=-1) + 1, "metrics": metrics, "tokens": tokens, "latency": latency, "stable": stable,
            "refused": len(refused), "looks_failed": sum(1 for r in looks if not r["ok"] and not r.get("refused") and not (r["look"] == "goto" and r.get("reason") == "url_blocked")), "looks_n": len(looks),
            "html_tokens_median": statistics.median(m["html_tokens"] for m in meta.values()) if meta else None,
            "truth_tokens_median": statistics.median(m["truth_tokens"] for m in meta.values()) if meta else None}


ARRIVAL_MIN = 0.8  # of the hops walked, at least this share must be verified arrived, or the product is not walking pages and nothing here is a result


def _replay(rows, env, meter):
    """The replay suite from its rows: per route the cost of a click hop (first walk against later ones), the arrival of every hop checked by an independent read
    (and what the product itself claimed), the stored-route lookup at each checkpoint with the product's answer, and the load by address."""
    q = {}
    for r in rows:
        if r.get("ms") is not None:
            kind = "checkpoint goto" if r["kind"] == "hop" and r.get("phase") == "checkpoint" else ("goto" if r["kind"] == "hop" and r["via"] == "goto" else "click" if r["kind"] == "hop" else r["kind"])
            q.setdefault(kind, Quiet(meter)).add(r, r["ms"])
    routes = []
    for site in env["replay"]["sites"]:
        for route in site["routes"]:
            mine = [r for r in rows if r["site"] == site["id"] and r["route"] == route["id"]]
            walk = [r for r in mine if r["kind"] == "hop" and r.get("phase") is None]
            clicks = [r for r in walk if r["via"] == "click" and r["ms"] is not None]
            counted = [r for r in walk if not r["site_failed"]]
            med = lambda xs: stats([r["ms"] for r in xs])  # noqa: E731
            routes.append({
                "site": site["id"], "own": site["own"], "route": route["id"], "hops": route["hops"], "runs": site["runs"],
                "walk_hops": len(counted), "arrived": sum(1 for r in counted if r["arrived"]), "claimed": sum(1 for r in counted if r["claimed"]),
                "site_failed": sum(1 for r in walk if r["site_failed"]), "hops_failed": sum(1 for r in walk if not r["ok"]),
                "click_first": med([r for r in clicks if r["run"] == 1]), "click_later": med([r for r in clicks if r["run"] > 1]),
                "goto_start": med([r for r in walk if r["via"] == "goto" and r["ms"] is not None]),
                "find": med([r for r in mine if r["kind"] == "find" and r["ms"] is not None]),
                "tokens_click": statistics.median([r["tokens"] for r in clicks]) if clicks else None,
                "tokens_find": statistics.median([r["tokens"] for r in mine if r["kind"] == "find" and r["ms"] is not None] or [0]),
                "plan": [{"run": r["run"], "outcome": r["outcome"], "route_len": r["route_len"], "ms": r["ms"], "node": r.get("node") is not None} for r in mine if r["kind"] == "plan"],
                "address": [{"run": r["run"], "ms": r["ms"], "arrived": r["arrived"], "claimed": r["claimed"]} for r in mine if r["kind"] == "address"]})
    walked = sum(r["walk_hops"] for r in routes)
    return {"routes": routes, "latency": {k: v.out() for k, v in sorted(q.items())}, "posts_after": env["replay"].get("posts_after"),
            "walk_hops": walked, "arrived": sum(r["arrived"] for r in routes), "claimed": sum(r["claimed"] for r in routes), "site_failed": sum(r["site_failed"] for r in routes),
            "calls_failed": sum(1 for r in rows if r["kind"] != "plan" and r.get("ok") is False and not r.get("site_failed"))}


def _delegate(rows, env, meter):
    """The delegate suite from its rows: per goal, how many reps passed (the product said ok AND an independent read found the page on one of the
    goal's addresses), how many it said ok, how many reached, the false successes (ok on another page), the time and steps of a run, its reasons."""
    q = Quiet(meter)
    goals = []
    for g in env["delegate"]["goals"]:
        mine = sorted((r for r in rows if r["goal"] == g["id"]), key=lambda r: r["rep"])
        for r in mine:
            q.add(r, r["ms"])
        goals.append({"goal": g["id"], "reps": len(mine), "passed": sum(1 for r in mine if r["passed"]), "said_ok": sum(1 for r in mine if r["said_ok"]),
                      "arrived": sum(1 for r in mine if r["arrived"]), "false_success": sum(1 for r in mine if r["false_success"]),
                      "ms": stats([r["ms"] for r in mine]), "steps": [r["steps"] for r in mine],
                      "reasons": sorted({r["reason"] for r in mine if r["reason"] and not r["passed"]}),
                      "seen": sorted({r["seen"] or "-" for r in mine if not r["arrived"]})})
    return {"goals": goals, "latency": q.out(), "runs": len(rows), "passed": sum(1 for r in rows if r["passed"]),
            "goals_reached_every_rep": sum(1 for g in goals if g["reps"] and g["passed"] == g["reps"]),
            "said_ok": sum(1 for r in rows if r["said_ok"]), "arrived": sum(1 for r in rows if r["arrived"]),
            "false_success": sum(1 for r in rows if r["false_success"]), "no_model_note": sum(1 for r in rows if r["decision_model"]),
            "site_failed": sum(1 for r in rows if r["site_failed"]),
            "calls_failed": sum(1 for r in rows if r["err"] or not r["verify_ok"] or not r["session"])}


def render(env, raw):
    """summary (a dict) and its markdown, made from the raw rows and the environment only."""
    by = {}
    for r in raw:
        by.setdefault(r["suite"], []).append(r)
    meter = Meter(by.get("machine", []))
    s = {"run_id": env["run_id"], "suites": env["suites"]}
    if "startup" in by:
        s["startup"] = _startup(by["startup"], meter)
    if "tools" in by:
        s["tools"] = _tools(by["tools"], meter)
    if "payload" in by:
        s["payload"] = _payload(by["payload"], meter)
    if "agent" in by:
        s["agent"] = _agent(env, by["agent"])
    if "browsecomp" in by:
        s["browsecomp"] = _browsecomp(env, by["browsecomp"])
    if "forms" in by:
        s["forms"] = _forms(by["forms"], env, meter)
    if "pages" in by:
        s["pages"] = _pages(by["pages"], env, meter)
    if "replay" in by:
        s["replay"] = _replay(by["replay"], env, meter)
    if "delegate" in by:
        s["delegate"] = _delegate(by["delegate"], env, meter)
    s["machine"] = _machine(by.get("machine", []))
    s["quiet"] = _quiet(s)
    s["rows"] = _rows(env, by)
    return s, markdown(env, s)


def _machine(rows):
    """What the kernel counted over the whole run (last sample minus first): the throttle events and the stall time."""
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: r["t_ms"])
    a, z = rows[0], rows[-1]
    d = lambda k: z[k] - a[k]  # noqa: E731
    return {"samples_kept": len(rows), "span_s": round((z["t_ms"] - a["t_ms"]) / 1000), "mem_high_events": d("mem_high"),
            "cpu_throttled_periods": d("cpu_throttled"), "mem_stall_ms": round(d("mem_psi_us") / 1000), "cpu_stall_ms": round(d("cpu_psi_us") / 1000),
            "io_stall_ms": round(d("io_psi_us") / 1000), "load1_max": max(r["load1"] for r in rows)}


def _quiet(s):
    """Measured calls over every suite, how many the machine throttled, how many have no sample on both sides."""
    parts = [{"n": s["startup"]["reps"], "throttled": s["startup"]["throttled"], "unobserved": s["startup"]["unobserved"]}] if "startup" in s else []
    parts += [{"n": t["ms"]["n"], "throttled": t["throttled"], "unobserved": t["unobserved"]} for t in s.get("tools", {}).get("per_tool", [])]
    parts += [c for p in s.get("payload", []) for c in p["calls"].values()]
    parts += [{"n": c["ms"]["n"], "throttled": c["throttled"], "unobserved": c["unobserved"]} for c in s.get("forms", {}).get("calls", {}).values()]
    parts += [{"n": c["ms"]["n"], "throttled": c["throttled"], "unobserved": c["unobserved"]} for c in s.get("pages", {}).get("latency", {}).values()]
    parts += [{"n": c["ms"]["n"], "throttled": c["throttled"], "unobserved": c["unobserved"]} for c in s.get("replay", {}).get("latency", {}).values()]
    parts += [{"n": c["ms"]["n"], "throttled": c["throttled"], "unobserved": c["unobserved"]} for c in ([s["delegate"]["latency"]] if "delegate" in s else [])]
    return {"measured": sum(x["n"] for x in parts), "throttled": sum(x["throttled"] for x in parts), "unobserved": sum(x["unobserved"] for x in parts)}


def _rows(env, by):
    """Rows seen against rows expected, per suite (env["expected"], written before the run started); the tools suite also names
    the cases with fewer or more rows than reps. A run that died partway leaves fewer rows than it set out to make."""
    want = env.get("expected") or {}
    out = {}
    for suite in env["suites"]:
        got = len(by.get(suite, []))
        if suite == "tools":
            seen = {}
            for r in by.get("tools", []):
                seen[r["case_id"]] = seen.get(r["case_id"], 0) + 1
            exp = want.get("tools")
            off = sorted(c for c in set(seen) | set(exp or {}) if seen.get(c, 0) != (exp or {}).get(c, 0))
            out[suite] = {"seen": got, "expected": None if exp is None else sum(exp.values()), "off": off}
        elif suite in ("agent", "browsecomp"):
            tasks = {}
            for r in by.get(suite, []):
                tasks.setdefault(r["task"], []).append(r)
            off = sorted(t for t, rs in tasks.items() if sorted(r["attempt"] for r in rs) != list(range(1, len(rs) + 1))
                         or [r.get("final") for r in sorted(rs, key=lambda r: r["attempt"])] != [False] * (len(rs) - 1) + [True]
                         or len(rs) > rules.MAX_ATTEMPTS)
            out[suite] = {"seen": len(tasks), "expected": want.get(suite), "off": off}
        else:
            out[suite] = {"seen": got, "expected": want.get(suite)}
    return out


def _f(v):
    return "-" if v is None else (f"{v:.0f}" if isinstance(v, (int, float)) and abs(v) >= 100 else f"{v}")


def _table(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"] + \
           ["| " + " | ".join(_f(c) if not isinstance(c, str) else c for c in r) + " |" for r in rows]


def _pre(env):
    p = env.get("preflight")
    if not p:
        return "not recorded"
    return f"memory pressure avg10 {p['mem_psi_avg10']}, load {p['load1']} on {p['cpus']} CPUs" + (f"; STARTED BUSY (--allow-busy): {'; '.join(p['busy'])}" if p["allowed_busy"] else "")


def _quiet_line(s):
    q = s["quiet"]
    if not q["measured"]:
        return "no call was timed in this run, so no call is called quiet; the kernel counters below say whether the job was throttled at all"
    return (f"quiet machine: {q['measured']} measured calls, {q['throttled']} overlapped throttling (memory.high or cpu quota), "
            f"{q['unobserved']} with no machine sample around them. 'quiet' columns count only the calls the machine did not throttle")


def _caveat(env):
    on_site = any(x in SITE_SUITES for x in env["suites"])
    corpus = any(x in ("forms", "pages") for x in env["suites"])
    return " ".join(([LOOPBACK] if on_site else []) + ([CORPUS] if corpus else []) + ([LIVE] if "replay" in env["suites"] else [])
                    + ([LIVE_DELEGATE] if "delegate" in env["suites"] else []))


def _launch_line(x):
    if not x:
        return "not recorded"
    return (f"license check {'on' if x.get('license_check') else 'off'}, telemetry {x.get('telemetry')}, state dir {'empty' if x.get('state_empty_at_start') else 'NOT empty'} "
            f"at start, {'headless' if x.get('headless') else 'headed'}; an installed brain differs in each of these")


def _checks_line(c):
    names = (("content", "the answer's content"), ("refusal", "a refusal or an error code"), ("ok", "only that the call worked"),
             ("weak", "nothing a stub answer could not pass"), ("setup", "setup steps (a goto or fill that only prepares a page)"),
             ("unknown", "not recorded"))
    return "; ".join(f"{c[k]} {what}" for k, what in names if c.get(k))


def _isolation_line(m):
    i = (m or {}).get("isolation")
    if not i:
        return "shared slice (the job has no cores of its own: another job in the slice can slow it)"
    return (f"a `work-run` slot: cores {i['cpuset']} of the slice's {i['slice_cpuset']} are this job's alone, memory capped at {i['memory_max_mb']} MB; "
            f"other work units beside it: {i['other_units']} at the start, {m.get('other_units_end')} at the end (they cannot take its cores or its memory; they share the host's memory bus, disk and network)")


def _machine_line(m):
    if not m:
        return "none recorded"
    return (f"memory.high events +{m['mem_high_events']}, cpu throttled periods +{m['cpu_throttled_periods']}, stalled (some) memory {m['mem_stall_ms']} ms, "
            f"cpu {m['cpu_stall_ms']} ms, io {m['io_stall_ms']} ms, load1 max {m['load1_max']}; {m['samples_kept']} samples kept over {m['span_s']} s")


def _rows_line(rows):
    return "; ".join(f"{k} {v['seen']} / {'?' if v['expected'] is None else v['expected']}" for k, v in rows.items())


def _ci(ci):
    return "-" if ci[0] is None else f"{ci[0]}-{ci[1]}%"


def _where(env):
    """Where the agent suite's attempts ran: a fresh scratch brain on the server's own browser, or a named head of a brain that was already running."""
    h = env["agent"].get("head")
    if not h:
        return f"a fresh scratch brain per attempt, mode b, head `{env['head']}`"
    return (f"the brain at {h['brain_url']} that was already running (no scratch brain), mode {h['mode']}, head `{h['name']}`"
            + (", a person's own device (their browser, their sign-ins)" if h["person_device"] else ""))


def _head_lines(e, a):
    """What a run on a named head must say beside its numbers: it is not a mode b run, the human step was on, what was held, which tabs were the bench's."""
    h = e.get("head")
    if not h:
        return []
    who = ", a person's own device" if h["person_device"] else ""
    return [f"- **Head `{h['name']}`, mode {h['mode']}{who}: these numbers are not comparable with the mode b runs** "
            "(a live browser with its own sign-ins, cookies and extensions, an existing brain, the product's human step on).",
            f"- Held for a person (a submit, a purchase, an add to cart or a login the product did not do; counted like blocked, never forced): {a['held']}. "
            f"Tabs the bench opened: {a['own_tabs']}; left open: {', '.join(a['tabs_left']) or 'none'}; calls that acted on a tab of the person: {a['person_tab_calls']}.", ""]


def _agent_markdown(env, a):
    """The agent suite's face: the two rates first, then what was rerun and why, then every task with its verdict and reason."""
    e = env["agent"]
    use = a["usage"]
    nums = a.get("numbers")
    judge = (f"Judge: `{e['judge_model']}` ({e['judge_resolved']}), {e['judge_votes']} votes on the same prompt, two SUCCESS pass, only where the reference is not a short exact "
             "fact; it sees the page text the agent read and the last screenshots it saw." if nums else
             f"Judge: `{e['judge_model']}` ({e['judge_resolved']}), text only, fixed rubric, only where the reference is not a short exact fact.")
    lines = ["## Agent (A1-lite: a fixed subset of WebVoyager, live sites)", "",
             f"{a['tasks']} tasks of the {e['pool']} browser-use scored (`browser-use/eval` `{e['source_commit'][:7]}`, {e['license']}), picked by the published seed "
             f"`{e['seed']}` ({e['spread']}). Agent: `claude -p --model {e['agent_model']}` ({e['agent_resolved']}, claude CLI {e['claude_cli']}) with only the brain's "
             f"tools, {_where(env)}, at most {e['max_turns']} turns and {e['wall_s']} s per attempt. "
             f"{judge} Not the paper's GPT-4V screenshot judge and not browser-use's hand-corrected one.", ""] + _head_lines(e, a) + (
        [f"- **Raw: {nums['raw']['pass']}/{nums['raw']['of']} = {nums['raw']['pct']}%** (95% interval {_ci(nums['raw']['ci'])}): every task, as run.",
         f"- **Doable today: {nums['doable']['pass']}/{nums['doable']['of']} = {nums['doable']['pct']}%** (95% interval {_ci(nums['doable']['ci'])}): without the tasks fixed "
         f"before the run as not doable from this address ({', '.join(nums['not_doable']) or 'none'}).",
         f"- **Unblocked: {nums['unblocked']['pass']}/{nums['unblocked']['of']} = {nums['unblocked']['pct']}%** (95% interval {_ci(nums['unblocked']['ci'])}): also without the tasks a bot wall blocked and the site faults below.",
         f"- Site faults (the task's own site answered a 5xx or an error page, was unreachable or never finished loading, and no answer passed; kept in Raw, out of Unblocked): "
         f"{', '.join(nums['site_fault']) or 'none'}.",
         f"- Every task by cause: {', '.join(f'{k} {v}' for k, v in nums['causes'].items())}. Judge votes that were not unanimous: {nums['split_votes']}.",
         f"- Re-dated (years moved ahead): {', '.join(f'{k} +{v}' for k, v in nums['redated'].items()) or 'none'}. Reference known to be wrong (judged without it): {', '.join(nums['broken_reference']) or 'none'}.",
         f"- Reference out of date (live page supports the answer, passed anyway): {', '.join(nums['reference_stale']) or 'none'}.",
         f"- First attempt: {a['first_pass']}/{a['tasks']} = {a['first_pct']}% (95% interval {_ci(a['first_ci'])})."] if nums else
        [f"- **First attempt: {a['first_pass']}/{a['tasks']} = {a['first_pct']}%** (95% interval {_ci(a['first_ci'])}).",
         f"- **Final, after reruns: {a['final_pass']}/{a['tasks']} = {a['final_pct']}%** (95% interval {_ci(a['final_ci'])}); "
         f"{a['final_pass_unblocked_pct']}% of the {a['tasks'] - a['blocked']} tasks that were not blocked."]) + [
             f"- Blocked by a bot wall (a person solves it, the bench never does): {a['blocked']}. Failed with a completed attempt: {a['fail']}. "
             f"Failed on every rerun for a model or infra reason: {a['infra_failed']}.",
             f"- Reruns: {a['reruns']} ({', '.join(f'{k} {v}' for k, v in a['rerun_reasons'].items()) or 'none'}); {a['reruns_that_passed']} task(s) passed after a rerun. "
             f"A rerun happens only for a model or infra reason (API error, rate limit, CLI crash, no tool call before the wall cap, brain did not start), "
             f"at most {e['max_attempts'] - 1} per task; a task the agent completed wrong is never run again.",
             f"- Passes decided by: {', '.join(f'{k} {v}' for k, v in a['pass_by'].items()) or 'none'}. All verdicts: {', '.join(f'{k} {v}' for k, v in a['decided_by'].items()) or 'none'} "
             "(a blocked or infra-failed task has no judged verdict). A pass needs a worked browser call: an answer from memory is a fail.",
             f"- Model calls: {a['agent_runs']} agent runs (cap {e['caps']['agent_runs']}), {a['judge_runs']} judge runs (cap {e['caps']['judge_runs']}); {a['turns']} agent turns, "
             f"wall {a['wall_ms'] / 1000:.0f} s; the CLI reports ${a['cost_usd']} as an equivalent (subscription, not billed); "
             f"tokens {', '.join(f'{k} {int(v)}' for k, v in use.items()) or 'not reported'}.",
             f"- Tasks with a call held for a person{'' if e.get('head') else ' (the bench has none)'}: {a['tasks_with_held_call']}. Brain unreachable after its attempt: {', '.join(a['brain_down']) or 'none'}.", ""]
    lines += _table(["site", "tasks", "first attempt", "final", "blocked"], [[x["site"], x["tasks"], x["first"], x["final"], x["blocked"]] for x in a["per_site"]]) + [""]
    lines += ["### Every task", ""]
    lines += _table(["task", "ref", "attempts", "result", "by", "reruns", "turns", "wall s", "reason"],
                    [[t["task"], t["ref_type"], t["attempts"], t["verdict"], t["by"], ", ".join(t["reruns"]) or "-", t["turns"], round(t["wall_ms"] / 1000),
                      (t["reason"] or "").replace("|", "/").replace("\n", " ")[:110]] for t in a["per_task"]]) + [""]
    return lines


def _browsecomp_markdown(env, b):
    """The browsecomp suite's face: the rate with its interval first, then the causes, the reruns, the cost, and every problem with its result."""
    e = env["browsecomp"]
    use = b["usage"]
    lines = ["## Browsecomp (a fixed subset of OpenAI's BrowseComp, live web)", "",
             f"{b['tasks']} problems of the {e['n_rows']} in OpenAI's `browse_comp_test_set.csv` (sha256 `{e['source_sha256'][:12]}`), picked by the published seed `{e['seed']}`. "
             f"Agent: `claude -p --model {e['agent_model']}` ({e['agent_resolved']}, claude CLI {e['claude_cli']}) with only the brain's tools, a fresh scratch brain per attempt, "
             f"mode b, head `{env['head']}`, at most {e['max_turns']} turns and {e['wall_s']} s per attempt. Grader: `{e['judge_model']}` ({e['judge_resolved']}), "
             f"{e['judge_votes']} votes on OpenAI's template, two `correct: yes` pass; the verdict is parsed by `browsecomp.parse_verdict`. "
             "No question, answer or grader reasoning is in the raw rows: the problems are decrypted in memory and a row holds hashes and counts.", "",
             f"- **Passed: {b['passed']}/{b['tasks']} = {b['pct']}%** (95% interval {_ci(b['ci'])}).",
             f"- Every problem by cause: {', '.join(f'{k} {v}' for k, v in b['causes'].items()) or 'none'}. Votes that were not unanimous: {b['split_votes']}.",
             f"- Reruns: {b['reruns']} ({', '.join(f'{k} {v}' for k, v in b['rerun_reasons'].items()) or 'none'}); a rerun happens only for a model or infra reason, "
             f"at most {e['max_attempts'] - 1} per problem; an answer the agent completed wrong is never run again. A pass needs a worked browser call.",
             f"- Model calls: {b['agent_runs']} agent runs (cap {e['caps']['agent_runs']}), {b['judge_runs']} grader runs (cap {e['caps']['judge_runs']}); {b['turns']} agent turns, "
             f"{b['tool_calls']} tool calls, wall {b['wall_ms'] / 1000:.0f} s; per problem the median is {_f(b['median_tool_calls'])} tool calls, "
             f"{_f(b['median_wall_ms'] and b['median_wall_ms'] / 1000)} s and {_f(b['median_tokens'])} tokens; the CLI reports ${b['cost_usd']} as an equivalent (subscription, not billed); "
             f"tokens {', '.join(f'{k} {int(v)}' for k, v in use.items()) or 'not reported'}.", ""]
    lines += ["### Every problem", ""]
    lines += _table(["row", "attempts", "result", "cause", "votes", "turns", "tool calls", "wall s", "tokens"],
                    [[t["task"], t["attempts"], t["verdict"], t["cause"], t["agree"] or "-", t["turns"], t["tool_calls"], round(t["wall_ms"] / 1000), t["tokens"]] for t in b["per_task"]]) + [""]
    return lines


def _pc(v):
    return "-" if v is None else f"{v * 100:.1f} %"


def _forms_md(env, f):
    """The forms section: every number is read from `f` (made from the rows) and the vocabulary in env."""
    arm_names = {"as_saved": "the page as saved", "no_declared_type": "the page without the attributes that say what a field is (autocomplete)"}
    lines = ["## Forms (Chromium's saved real-site forms against Chrome's own field types)", "",
             f"{f['pages']} saved forms ({', '.join(f'{n} {g}' for g, n in next(iter(f['arms'].values()))['pages_by_group'].items())}); "
             f"each opened with `goto` and read with `view(kind=\"form\")` through the MCP. What counts as right is the committed `benchmarks/forms_vocabulary.json` "
             "(copied into env.json): the product's slot names that mean the same as each Chrome type. **This is agreement with Chrome's autofill heuristics, "
             "not human truth**: Chrome's output gives UNKNOWN_TYPE to some fields a person would name, and those are counted apart, never scored. "
             f"The product has no slot for a card number or a part of a phone number, so for those the right answer is no slot (`out`). "
             f"Calls: {f['calls_n'] - f['calls_failed']}/{f['calls_n']} ok.", ""]
    for arm, a in f["arms"].items():
        i, o, sl = a["in"], a["out"], a["silent"]
        lines += [f"### Arm: {arm_names.get(arm, arm)}", "",
                  f"- **Chrome fields {a['fields']}; scored {a['scored']}** (listed by the product: {i['n']} `in`, the product has a slot for the type; {o['n']} `out`, it has none); "
                  f"left out because they could not be joined to a control and a product field: "
                  f"{', '.join(f'{k} {v}' for k, v in sorted(a['join'].items()) if k in ('no_control', 'unverified', 'no_view')) or 'none'}; "
                  f"controls on the page for which the product listed no field (`not_listed`; Chrome lists hidden controls too, so this is not scored as a miss): "
                  f"{a['join'].get('not_listed', 0)} ({i['not_listed']} `in`, {o['not_listed']} `out`, {sl['not_listed']} silent)",
                  f"- **`in`: agree {i['agree']}/{i['n']} = {_pc(i['agree_share'])}** of the fields the product listed; wrong slot {i['wrong']} ({_pc(i['wrong_share'])}); "
                  f"no slot {i['no_slot']} ({_pc(i['no_slot_share'])}). If every `in` control it did not list counted as a miss: {i['agree']}/{i['n'] + i['not_listed']} = {_pc(_share(i['agree'], i['n'] + i['not_listed']))}",
                  f"- stub to beat: answering `{a['stub']['slot']}` for every field agrees on {a['stub']['agree']}/{a['stub']['n']} = {_pc(a['stub']['agree_share'])}",
                  f"- `out`: no slot where none exists {o['none']}/{o['n']} = {_pc(o['none_share'])}; a slot named where none exists {o['named']}",
                  f"- **dangerous errors** (an identity-policy slot the vocabulary says is not the field's, which the fill policy would fill with no person): "
                  f"{a['dangerous']}/{a['scored']} scored fields = {_pc(a['dangerous_share'])}",
                  f"- fields where Chrome says nothing (UNKNOWN_TYPE), not scored: {sl['n']}; the product named a slot for {sl['named']} of them ({sl['named_identity']} with the identity policy)",
                  f"- answers that came from the brain's memory and not the classifier (`learned`): {a['learned']} (must be 0); product fields not paired with a Chrome line: {a['extra_fields']}", ""]
        lines += ["By the product's confidence (fields where it named a slot, type `in`):", ""]
        lines += _table(["confidence", "named", "agree", "wrong", "agree share"],
                        [[k, v["n"], v["agree"], v["wrong"], _pc(_share(v["agree"], v["n"]))] for k, v in sorted(a["by_conf"].items())]) + [""]
        t = a["token"]
        lines += [f"Fields (type `in`) whose page declares its own type in `autocomplete`: agree {t['with']['agree']}/{t['with']['n']} = {_pc(_share(t['with']['agree'], t['with']['n']))}; "
                  f"fields that do not: {t['without']['agree']}/{t['without']['n']} = {_pc(_share(t['without']['agree'], t['without']['n']))}.", ""]
        lines += ["By kind of page (type `in`):", ""]
        lines += _table(["pages", "fields", "agree", "agree share"], [[g, v["n"], v["agree"], _pc(_share(v["agree"], v["n"]))] for g, v in sorted(a["by_group"].items())]) + [""]
        lines += ["By Chrome type:", ""]
        lines += _table(["Chrome type", "scope", "fields", "agree", "wrong", "no slot", "slot named where none exists"],
                        [[k, v["scope"], v["n"], v["agree"], v["wrong"], v["no_slot"], v["named"]] for k, v in sorted(a["by_type"].items(), key=lambda kv: (-kv[1]["n"], kv[0]))]) + [""]
    lines += ["Calls (ms, client wall time):", ""]
    lines += _table(["call", "n", "median", "p95", "min", "max", "throttled", "quiet p95"],
                    [[k, *[v["ms"][x] for x in ("n", "median", "p95", "min", "max")], v["throttled"], v["ms_quiet"]["p95"]] for k, v in f["calls"].items()]) + [""]
    return lines


def _pm(m, k):
    std = (m.get("std") or {}).get(k)
    return f"{m[k]:.3f}" + (f" ± {std:.3f}" if std is not None else "")


def _pages_md(env, p):
    """The pages section: every number is read from `p` (made from the rows) and from what the run recorded of the benchmark's own scorer."""
    pub, ref = env["pages"]["published"], env["pages"]["reference"]
    lines = ["## Pages (Scrapinghub's saved article pages, scored by the benchmark's own scorer)", "",
             f"{p['pages']} saved article pages, each served from loopback and looked at through the MCP: `read(url)` {p['url_reps']} times, the browser looks {p['reps']} time(s) (they wait 1.6 to 1.7 s each for a page that runs script to settle; the content scores and token counts do not change with repeats, so one is enough, and the p50/p95 are over the pages). The score is the benchmark's `evaluate.py` (fetched with the data and "
             "checked against the lock): shingles of 4 words of the true article body against the words of the answer, precision, recall and F1 averaged over pages; `accuracy` is 1 "
             "when the words are exactly the article's. **Before an earlier change `read` kept all the visible text of a page; since then it answers an article's main text.** "
             "A run of the older code belongs beside the whole-page text dump (html-text) of the published table; a later one beside readability and trafilatura. "
             "A saved page is plain HTML, so `read(url)` here is the plain-GET tier only: the browser tier of the same call (a head, a page the GET cannot read) is not scored. ± is the benchmark's bootstrap "
             f"({BOOTSTRAP} draws, seeded here). First repeat is scored; later repeats give time and say whether the words were the same.", ""]
    rows = []
    for arm, label in (("read_url", "`read(url)` of a saved page: the plain-GET tier"), ("read_full", "`goto` then `read(level=\"full\")`, every part"),
                       ("html_text", "stub: the page's text with the markup removed"), ("title", "stub: the page's title alone")):
        m = p["metrics"][arm]
        rows.append([label, _pm(m, "f1"), _pm(m, "precision"), _pm(m, "recall"), _pm(m, "accuracy")])
    for name in sorted(ref):
        m = ref[name]
        rows.append([f"published output of `{name}` {m['version']}, scored by this run", f"{m['f1']:.3f}", f"{m['precision']:.3f}", f"{m['recall']:.3f}", f"{m['accuracy']:.3f}"])
        table = pub.get(name)
        rows.append([f"the repository's README table for `{name}`"] + ([f"{table[k]:.3f}" for k in ("f1", "precision", "recall", "accuracy")] if table else ["-"] * 4))
    lines += _table(["answer", "F1", "precision", "recall", "accuracy"], rows) + [""]
    own = ", ".join("%s F1 %.3f" % (k, v["f1"]) for k, v in sorted(env["pages"]["public_scorer"].items()))
    lines += [f"The benchmark's own function gave, for the same answers: {own}; "
              "`check` refuses a run where these differ from the numbers made here from the rows, or where the published outputs do not score as the README says.", ""]
    lines += [f"Tokens ({env['tokenizer']}) of one look, first repeat, median over pages; the median page is {_f(p['html_tokens_median'])} tokens of HTML and "
              f"{_f(p['truth_tokens_median'])} of true article. A ratio is made only for a look that returns the whole page in every page.", ""]
    lines += _table(["look", "covers", "parts (max)", "tokens", "x html", "x page text", "x true article", "calls", "median ms", "p95 ms", "throttled", "quiet p95 ms"],
                    [[n, t["covers"], t["parts_max"], t["median"], t["vs_html"], t["vs_text"], t["vs_truth"], p["latency"][n]["ms"]["n"], p["latency"][n]["ms"]["median"],
                      p["latency"][n]["ms"]["p95"], p["latency"][n]["throttled"], p["latency"][n]["ms_quiet"]["p95"]] for n, t in p["tokens"].items()]) + [""]
    lines += [f"Pages the product refused to keep open: {p['refused']} of {p['pages']}. Their own script sent the tab away from the saved page (`goto` answers `loaded: false, reason: url_blocked`); what `read(level=full)` and `view` would then show is not the page, so those looks are counted here and left out of the `read(level=full)` score and tokens. `read(url)` is a plain fetch and is scored on every page. The stubs and `read(url)` cover all {p['pages']} pages; `read(level=full)` covers {p['pages'] - p['refused']}.", ""]
    lines += ["Same words on every repeat (the `[n12]` ref numbers left out): " + ("; ".join(f"{k} {v['same']}/{v['pages']} pages" for k, v in p["stable"].items()) or "no look was repeated") + f". Not measured for the browser looks (taken {p['reps']} time(s)). Looks that failed: {p['looks_failed']}/{p['looks_n']}.", ""]
    return lines


def _replay_md(env, p):
    lines = ["## Replay (saved path: the walk, the stored route, the address)", "",
             "Routes fixed in `replay_routes.json` (the own loopback site, and two public sandbox sites built for scraping, reached over the network). Each walk opens the first address with `goto` and "
             "reaches every next address by clicking its link (found with `read(shape=\"full\")`). A hop **arrived** only when an independent `read` of the page then reports the hop's address "
             "(compared without a trailing slash); `claimed` is what the product's own answer said. **This is not a replay**: `goto` replays stored steps only for a page id that is not an address, and "
             "the pages the brain maps from a visit have their address as id, so no tool call replays a walked route of such a page. The suite times the walk, asks the stored route for the last page "
             "(`goto(url=last, plan=true)`: the route lookup alone, what the 2026-09 \"0.2 ms\" measured) and records what it answered, and loads the last page by address.", "",
             f"Hops walked {p['walk_hops']}: verified arrived {p['arrived']}, claimed by the product {p['claimed']}, failed by the site {p['site_failed']}, calls that failed {p['calls_failed']}. "
             f"The own site's POST count after the run: {p['posts_after']}.", ""]
    rows = []
    for r in p["routes"]:
        rows.append([r["site"], r["route"], r["hops"], max(r["runs"]), f"{r['arrived']}/{r['walk_hops']}", r["claimed"], r["click_first"]["median"], r["click_later"]["median"], r["click_later"]["p95"],
                     r["goto_start"]["median"], r["find"]["median"], r["tokens_click"], r["tokens_find"]])
    lines += ["Walk (ms; client wall time of one call; `click first` = the first walk, `click later` = walks 2 and on):", ""]
    lines += _table(["site", "route", "hops", "walks", "arrived", "claimed", "click first median", "click later median", "click later p95", "first goto median", "find link median", "tokens of a click answer", "tokens of a find"], rows) + [""]
    prow = []
    for r in p["routes"]:
        for pl, ad in zip(r["plan"], r["address"]):
            prow.append([r["site"], r["route"], pl["run"], pl["outcome"], pl["route_len"], pl["node"], pl["ms"], ad["ms"], f"{ad['arrived']} (claimed {ad['claimed']})"])
    lines += ["After walk k: the stored route to the last page (`plan`), and the last page loaded by address:", ""]
    lines += _table(["site", "route", "after walk", "plan answered", "route steps", "last page is a graph node", "plan ms", "address load ms", "address arrived"], prow) + [""]
    lines += ["Calls (ms):", ""]
    lines += _table(["call", "n", "median", "p95", "min", "max", "throttled", "quiet p95"], [[k, *[v["ms"][x] for x in ("n", "median", "p95", "min", "max")], v["throttled"], v["ms_quiet"]["p95"]] for k, v in p["latency"].items()]) + [""]
    return lines


def _delegate_md(env, p):
    lines = ["## Delegate (one delegate_task call per goal, public practice sites)", "",
             f"Goals fixed in `delegate_goals.json` before any change to delegate_task; each run in a fresh session, max_steps {env['delegate']['max_steps']}. "
             "A run **passed** only when delegate_task answered ok AND an independent `read(level=\"outline\")` of the session afterwards reported one of the goal's "
             "addresses (compared without fragment and trailing slash). **ok on any other page is a false success**, never a pass.", "",
             f"**Passed {p['passed']}/{p['runs']} runs; goals reached in every rep {p['goals_reached_every_rep']}/{len(p['goals'])}.** "
             f"Said ok {p['said_ok']}, reached the page {p['arrived']}, **false successes {p['false_success']}**, answers that said no decision model acted "
             f"{p['no_model_note']}, runs whose site did not answer {p['site_failed']}, calls that failed {p['calls_failed']}.", ""]
    lines += _table(["goal", "passed", "said ok", "reached", "false success", "median ms", "steps per rep", "why not (distinct)", "where it ended when not reached"],
                    [[g["goal"], f"{g['passed']}/{g['reps']}", g["said_ok"], g["arrived"], g["false_success"], g["ms"]["median"],
                      ", ".join(_f(x) for x in g["steps"]), "; ".join(g["reasons"])[:200] or "-", " ".join(g["seen"])[:200] or "-"] for g in p["goals"]]) + [""]
    c = p["latency"]
    lines += ["Calls (ms, one delegate_task call):", ""]
    lines += _table(["call", "n", "median", "p95", "min", "max", "throttled", "quiet p95"],
                    [["delegate_task", *[c["ms"][x] for x in ("n", "median", "p95", "min", "max")], c["throttled"], c["ms_quiet"]["p95"]]]) + [""]
    return lines


def markdown(env, s):
    """The human face of a run. Every number in it is read from `s` or `env`; nothing is typed here."""
    g, m, b = env["git"], env["machine"], env["brain"]
    lines = [f"# Bench run {env['run_id']}", "",
             "Generated by `benchmarks/summarize.py` from `raw.json` and `env.json` in this folder. Do not edit: the gate re-makes it.", "",
             f"**{LIVE_AGENT if env['suites'] == ['agent'] else LIVE_BROWSECOMP if env['suites'] == ['browsecomp'] else _caveat(env)}**", "",
             f"- commit `{g['commit']}` (dirty {g['dirty']}); brain under test reports sha `{b['sha']}`, dirty {b['dirty']}",
             f"- machine `{m['hostname']}`: {m['cpu']}, {m['cpus']} CPUs seen, {m['mem_total_mb']} MB RAM, job cap: memory {m['cap_memory']}, cpu {m['cap_cpu']}",
             f"- load average at start {m['load_start']}, at end {m['load_end']}; at the door: {_pre(env)}",
             *([f"- isolation: {_isolation_line(m)}"] if "isolation" in m else []),  # a run made before slots existed has no such key: its summary stays as it was made
             f"- **{_quiet_line(s)}**",
             f"- kernel counters over the run (cgroups {', '.join(m.get('cgroups') or []) or 'none'}): {_machine_line(s['machine'])}; "
             f"peak memory {', '.join(f'{k} {v} MB' for k, v in (m.get('peak_mb') or {}).items()) or 'not read'}",
             f"- rows seen / expected: {_rows_line(s['rows'])}",
             f"- browser `{b['browser']}`; head `{env['head']}`; Python {m['python']}; packages {', '.join(f'{k} {v}' for k, v in sorted(env['packages'].items()))}",
             f"- how the scratch brain was started: {_launch_line(b.get('launch'))}",
             f"- the brain's registered dependencies, read at run time (a model host would be one): {env['models']['brain'] or 'none'}; "
             f"agent model: {env['models']['agent'] or 'none'} ({env['models']['agent_why']})",
             *([f"- the own site's POST count after the run: {env.get('posts_after')} (a safe run ends at 0)"] if env.get("posts_after") is not None else []),
             *[f"- public data `{n}`: commit `{c['commit']}`, {c['files']} files checked against the lock (digest `{c['digest'][:12]}`), licence {c['licence']}" for n, c in sorted(env.get("corpora", {}).items())],
             f"- started {env['started_at']}, ended {env['ended_at']}; suites {', '.join(env['suites'])}; reps {env['reps']}",
             f"- cases: `benchmarks/cases.json` sha256 `{env['cases']['benchmarks/cases.json'][:12]}`, {len(env['cases'])} files hashed", ""]
    if "startup" in s:
        st = s["startup"]
        lines += ["## Startup (cold)", "", f"{st['reps']} brain starts; first goto ok {st['first_goto_ok']}/{st['reps']}. Milliseconds.", ""]
        lines += _table(["step", "n", "median", "p95", "min", "max", "spread (p75-p25)", "reps throttled", "quiet p95", "quiet max"],
                        [[k, *[st[k][x] for x in ("n", "median", "p95", "min", "max", "iqr")], st["throttled"], st["quiet"][k]["p95"], st["quiet"][k]["max"]]
                         for k in ("health_ms", "first_goto_ms")]) + [""]
    if "tools" in s:
        t = s["tools"]
        lines += ["## Tools (field cases through the MCP)", "",
                  f"Calls pass/fail/skip over all reps: {t['pass']}/{t['fail']}/{t['skip']}. Client wall time in ms, all cases of a tool together. "
                  "`rep 0` is the first pass (cold caches), `later` the other reps.", "",
                  f"What the {t['pass']} passes checked: {_checks_line(t['pass_by_check'])}.",
                  f"Not timed and not in a row of their own: {t['ref_lookups']} `view` lookups that find a `{{REF:...}}` before a case.", ""]
        lines += _table(["tool", "pass", "fail", "skip", "n", "median", "p95", "min", "max", "spread", "rep 0 median", "later median",
                         "calls throttled", "quiet p95", "quiet max", "passes setup or ok-only"],
                        [[r["tool"], r["pass"], r["fail"], r["skip"], *[r["ms"][x] for x in ("n", "median", "p95", "min", "max", "iqr")],
                          r["rep0_median"], r["later_median"], r["throttled"], r["ms_quiet"]["p95"], r["ms_quiet"]["max"],
                          sum(r["pass_by_check"].get(k, 0) for k in ("setup", "ok", "weak"))] for r in t["per_tool"]]) + [""]
        bad = [c for c in t["per_case"] if c["fail"]]
        lines += ["### Cases that failed in at least one rep", ""]
        lines += (_table(["case", "tool", "fail/reps", "why (distinct reasons)"],
                         [[c["case_id"], c["tool"], f"{c['fail']}/{c['pass'] + c['fail']}", "; ".join(c["reasons"])[:300]] for c in bad])
                  if bad else ["none"]) + [""]
        skipped = [c for c in t["per_case"] if c["skip"]]
        lines += ["### Cases skipped", ""]
        lines += (_table(["case", "tool", "why"], [[c["case_id"], c["tool"], "; ".join(c["reasons"])] for c in skipped]) if skipped else ["none"]) + [""]
        lines += ["### Slowest 25 cases by p95", ""]
        lines += _table(["case", "tool", "n", "median", "p95", "min", "max", "spread", "calls throttled", "quiet p95", "quiet max"],
                        [[c["case_id"], c["tool"], *[c["ms"][x] for x in ("n", "median", "p95", "min", "max", "iqr")], c["throttled"],
                          c["ms_quiet"]["p95"], c["ms_quiet"]["max"]] for c in t["per_case"] if c["ms"]["n"]][:25]) + [""]
    if "payload" in s:
        lines += ["## Payload (one look at a page, own site)", "",
                  f"Tokens by `{env['tokenizer']}` (an OpenAI tokenizer: a stand-in, not the agent model's own count). `http_get` is the page's "
                  "own HTML fetched plainly, `http_text` the same page as plain text without its markup (what a plain html-to-text gives). "
                  "`x html` is tokens of the answer / tokens of the HTML, `x text` the same against the text. A look counts only when its answer (without "
                  "its own url and title) carries the words its page must give back (`ok`). `covers` says what a look returns: `page` is the whole text "
                  "(every part of a long answer is fetched, tokens and ms are the sum, `parts` is how many) and is the only kind that gets a ratio, "
                  "and only when every rep is ok and complete; an `outline`, the `controls` of the page and a navigation `receipt` skip the prose by design, "
                  "so their small token counts are not savings. ms is the median of the reps."
                  + (" This suite runs after the tools suite on the same brain: the browser is warm (the startup suite has the cold start)."
                     if "tools" in env["suites"] else ""), ""]
        names = list(dict.fromkeys(n for p in s["payload"] for n in p["calls"]))
        rows = []
        for p in s["payload"]:
            for n in names:
                c = p["calls"].get(n)
                if c:
                    tok = c["tokens"] if c["tokens_min"] == c["tokens_max"] else f"{c['tokens']} ({c['tokens_min']}-{c['tokens_max']})"
                    rows.append([p["page"], n, c["covers"] or "-", c["parts"], tok if isinstance(tok, str) else tok, c["vs_html"], c["vs_text"],
                                 c["ms"]["median"], c["ms"]["p95"], c["throttled"], c["ms_quiet"]["p95"], f"{c['ok']}/{c['n']}"])
        lines += _table(["page", "call", "covers", "parts", "tokens", "x html", "x text", "median ms", "p95 ms", "throttled", "quiet p95 ms", "ok"], rows) + [""]
    if "agent" in s:
        lines += _agent_markdown(env, s["agent"])
    if "browsecomp" in s:
        lines += _browsecomp_markdown(env, s["browsecomp"])
    if "forms" in s:
        lines += _forms_md(env, s["forms"])
    if "pages" in s:
        lines += _pages_md(env, s["pages"])
    if "replay" in s:
        lines += _replay_md(env, s["replay"])
    if "delegate" in s:
        lines += _delegate_md(env, s["delegate"])
    lines += ["## Not run by this door", ""] + [f"- {x['what']}: {x['why']}" for x in env.get("not_run") or []] + [""]
    return "\n".join(lines)


def write(folder, env, raw):
    """Write all four files of a run. The only place a summary is written."""
    s, md = render(env, raw)
    for name, body in (("env.json", env), ("raw.json", raw), ("summary.json", s)):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
            f.write(json.dumps(body, indent=1, sort_keys=True) + "\n")
    with open(os.path.join(folder, "summary.md"), "w", encoding="utf-8") as f:
        f.write(md + "\n")


def _unproven(folder, env, s):
    """What the rows cannot prove: a machine that was quiet, and a run that finished. Each is a reason the run is not a result."""
    bad = []
    q, pre = s["quiet"], env.get("preflight")
    if q["throttled"]:
        bad.append(f"{folder}: {q['throttled']} measured calls overlapped machine throttling")
    if q["unobserved"]:
        bad.append(f"{folder}: {q['unobserved']} measured calls have no machine sample on both sides (nothing shows the machine quiet)")
    if not pre or pre["allowed_busy"]:
        bad.append(f"{folder}: the run " + ("started on a busy machine (--allow-busy): " + "; ".join(pre["busy"]) if pre else "recorded no check of the machine at its start"))
    for suite, r in s["rows"].items():
        if r["expected"] is None:
            bad.append(f"{folder}: no row count was recorded for the {suite} suite, so a partial run cannot be told from a whole one")
        elif r["seen"] != r["expected"] or r.get("off"):
            bad.append(f"{folder}: the {suite} suite left {r['seen']} rows, expected {r['expected']} (the runner died partway, or rows are missing)"
                       + (f"; cases off: {', '.join(r['off'][:8])}" if r.get("off") else ""))
    door = env.get("door")
    if not door:
        bad.append(f"{folder}: env.json does not say what a whole run is (reps and suites), so a try cannot be told from a result")
    elif env["reps"] != door["reps"] or sorted(env["suites"]) != sorted(door["suites"]):
        bad.append(f"{folder}: a try, not a result: {env['reps']} reps of {door['reps']}, suites {', '.join(env['suites'])} of {', '.join(door['suites'])}")
    st = s.get("startup")
    if st and st["first_goto_ok"] < st["reps"]:
        bad.append(f"{folder}: the first goto failed in {st['reps'] - st['first_goto_ok']} of {st['reps']} cold starts, so those times are of an error")
    broken = sum(c["n"] - c["ok"] for p in s.get("payload", []) for c in p["calls"].values())
    if broken:
        bad.append(f"{folder}: {broken} payload calls failed or lacked the words their page must give back (a token count of a broken answer is no saving)")
    bad += _unproven_forms(folder, s.get("forms"))
    bad += _unproven_pages(folder, env, s.get("pages"))
    bad += _unproven_replay(folder, s.get("replay"))
    bad += _unproven_delegate(folder, s.get("delegate"))
    if "tools" in env["suites"] and env.get("runner_exit") not in (0, 1):
        bad.append(f"{folder}: the field runner exited {env.get('runner_exit')!r} (0 and 1 are a finished run; anything else is a crash)")
    return bad


def _agent_problems(folder, env, raw):
    """What the rows of an agent run cannot support, re-made with the same pure rules the suite decided by: a rerun only for a model or infra
    reason, a final attempt that is not one, a pass with no worked browser call, a 'deterministic' pass the rule does not give, a blocked
    task with no bot wall, a model that is not Haiku, a cap overrun, a try (fewer tasks than the door defines). For a run of the honest
    suite (`judge_votes` in env.json) also: a judge verdict that is not the majority of its votes, a question not re-dated by the rule, a
    deterministic pass on a task with a broken reference."""
    bad, e, door = [], env.get("agent") or {}, env.get("door") or {}
    rows = [r for r in raw if r["suite"] == "agent"]
    if not e:
        return [f"{folder}: env.json has no agent record"]
    if door.get("tasks") != len(e.get("tasks", [])):
        bad.append(f"{folder}: a try, not a result: {len(e.get('tasks', []))} tasks of {door.get('tasks')}")
    if e.get("stopped"):
        bad.append(f"{folder}: the run stopped early: {e['stopped']}")
    for key, name, locked in (("agent_resolved", "agent", ("haiku", "sonnet")), ("judge_resolved", "judge", ("haiku",))):
        if not e.get(key) or not any(m in e[key] for m in locked):
            bad.append(f"{folder}: the {name} model that ran was {e.get(key)!r}, not a {' or '.join(m.title() for m in locked)} (the model lock of this suite)")
    if sum(1 for r in rows if r.get("agent_run")) > e["caps"]["agent_runs"] or sum(((r.get("judge") or {}).get("runs") or 0) for r in rows) > e["caps"]["judge_runs"]:
        bad.append(f"{folder}: more model runs than the caps in agent_tasks.json allow")
    votes = e.get("judge_votes")
    run_date = datetime.date.fromisoformat(e["run_date"]) if votes and e.get("run_date") else None
    if votes and not run_date:
        bad.append(f"{folder}: env.json has no run_date, so the re-dating cannot be checked")
    for r in rows:
        tag = f"{folder}: {r['task']} attempt {r['attempt']}"
        jd = r.get("judge")
        if votes and jd and len(jd.get("votes") or []) != votes:
            bad.append(f"{tag}: the judge cast {len(jd.get('votes') or [])} votes, the suite needs {votes} votes")
        elif votes and jd and (rules.majority(jd["votes"]) != jd.get("ok") or jd.get("agree") != rules.agree(jd["votes"])):
            bad.append(f"{tag}: the judge's verdict {jd.get('ok')!r} (agree {jd.get('agree')}) is not the majority of its votes {jd['votes']}")
        if run_date and r.get("ques") and (r["ques"], r.get("redated_years", 0)) != rules.redate(r.get("ques_original", r["ques"]), run_date):
            bad.append(f"{tag}: re-dating: the question is not what the rule makes of it for a run on {run_date}")
        if r.get("reference_stale") and (r.get("verdict") != "pass" or r.get("verdict_by") != "judge"):
            bad.append(f"{tag}: reference_stale is set on a row the judge did not pass")
        if r.get("reference_broken") and r.get("verdict_by") == "deterministic":
            bad.append(f"{tag}: a deterministic pass on a reference known to be wrong")
        kind = rules.classify(r)
        if kind != r.get("infra_kind"):
            bad.append(f"{tag}: recorded as {r.get('infra_kind')!r}, the rule says {kind!r}")
        if not r.get("final"):
            if not rules.may_rerun(kind, r["attempt"]):
                bad.append(f"{tag}: run again, but {kind!r} is not a reason to (only a model or infra failure is)")
            continue
        if kind and r.get("verdict") != "infra_failed":
            bad.append(f"{tag}: failed for {kind!r} but is not marked infra_failed")
        if not kind and r.get("verdict") not in ("pass", "fail", "blocked", "held", "site_fault"):
            bad.append(f"{tag}: a completed attempt with the verdict {r.get('verdict')!r}")
        if kind and rules.may_rerun(kind, r["attempt"]):
            bad.append(f"{tag}: ended on {kind!r} with reruns left")
        if r.get("verdict") in ("pass", "fail", "blocked", "held", "site_fault") and (not r.get("reason") or r.get("verdict_by") not in ("deterministic", "judge", "rule")):
            bad.append(f"{tag}: a verdict without its reason or its source")
        if r.get("verdict") == "pass":
            if not rules.evidence(r["calls"]):
                bad.append(f"{tag}: passed with no worked browser call")
            if r["verdict_by"] == "deterministic" and rules.det_check(r["reference"], r["answer"]) is not True:
                bad.append(f"{tag}: marked a deterministic pass, but the reference is not in the answer by the rule")
            if r["verdict_by"] == "judge" and not (r.get("judge") or {}).get("ok"):
                bad.append(f"{tag}: marked a judge pass, but the judge's verdict was {(r.get('judge') or {}).get('ok')!r}")
        if r.get("verdict") == "blocked" and not any(c.get("wall") for c in r["calls"]):
            bad.append(f"{tag}: blocked with no bot wall in its calls")
        if r.get("verdict") == "site_fault" and not any(c.get("fault") for c in r["calls"]):
            bad.append(f"{tag}: site_fault with no site fault in its calls")
        if r.get("verdict") == "held" and (not (e.get("head") or {}).get("person_device") or not any(c.get("held") for c in r["calls"])):
            bad.append(f"{tag}: held with no call held for a person (or not a run on a person's device)")
        if r.get("tabs_left"):
            bad.append(f"{tag}: left {len(r['tabs_left'])} tab(s) of the bench open on the person's browser: {', '.join(r['tabs_left'])}")
        if any(c.get("person_tab") for c in r["calls"]):
            bad.append(f"{tag}: a call acted on a tab of the person")
        if r.get("answer") is not None and rules.answer_of(r.get("final_text", ""))[0] != r["answer"]:
            bad.append(f"{tag}: the stored answer is not what the final message holds")
    return bad


def _browsecomp_problems(folder, env, raw):
    """What the rows of a browsecomp run cannot support, re-made with the rules the suite decided by: a rerun only for a model or infra reason, a final attempt
    that is not one, a pass that is not the majority of its votes or has no worked browser call, a key a row may not hold (no question, answer, call argument or
    grader text is ever written), a model outside the lock, a cap overrun, a try or a stopped run."""
    bad, e, door = [], env.get("browsecomp") or {}, env.get("door") or {}
    rows = [r for r in raw if r["suite"] == "browsecomp"]
    if not e:
        return [f"{folder}: env.json has no browsecomp record"]
    if door.get("tasks") != len(e.get("tasks", [])):
        bad.append(f"{folder}: a try, not a result: {len(e.get('tasks', []))} problems of {door.get('tasks')}")
    if e.get("stopped"):
        bad.append(f"{folder}: the run stopped early: {e['stopped']}")
    for key, name, locked in (("agent_resolved", "agent", ("haiku", "sonnet")), ("judge_resolved", "judge", ("haiku",))):
        if not e.get(key) or not any(m in e[key] for m in locked):
            bad.append(f"{folder}: the {name} model that ran was {e.get(key)!r}, not a {' or '.join(m.title() for m in locked)} (the model lock of this suite)")
    if sum(1 for r in rows if r.get("agent_run")) > e["caps"]["agent_runs"] or sum(((r.get("judge") or {}).get("runs") or 0) for r in rows) > e["caps"]["judge_runs"]:
        bad.append(f"{folder}: more model runs than the caps in browsecomp_tasks.json allow")
    for r in rows:
        tag = f"{folder}: row {r['task']} attempt {r['attempt']}"
        extra = sorted(set(r) - bc.ALLOWED_KEYS) + sorted({k for c in r["calls"] for k in set(c) - bc.CALL_KEYS})
        if extra:
            bad.append(f"{tag}: holds {', '.join(extra)}, which a browsecomp row never writes (it would carry the problem, the answer or the agent's input)")
        jd = r.get("judge")
        if jd and len(jd.get("votes") or []) != e["judge_votes"]:
            bad.append(f"{tag}: the grader cast {len(jd.get('votes') or [])} votes, the suite needs {e['judge_votes']}")
        elif jd and (rules.majority(jd["votes"]) != jd.get("ok") or jd.get("agree") != rules.agree(jd["votes"])):
            bad.append(f"{tag}: the grader's verdict {jd.get('ok')!r} (agree {jd.get('agree')}) is not the majority of its votes {jd['votes']}")
        kind = rules.classify(r)
        if kind != r.get("infra_kind"):
            bad.append(f"{tag}: recorded as {r.get('infra_kind')!r}, the rule says {kind!r}")
        if not r.get("final"):
            if not rules.may_rerun(kind, r["attempt"]):
                bad.append(f"{tag}: run again, but {kind!r} is not a reason to (only a model or infra failure is)")
            continue
        if kind and r.get("verdict") != "infra_failed":
            bad.append(f"{tag}: failed for {kind!r} but is not marked infra_failed")
        if not kind and r.get("verdict") not in ("pass", "fail", "blocked"):
            bad.append(f"{tag}: a completed attempt with the verdict {r.get('verdict')!r}")
        if kind and rules.may_rerun(kind, r["attempt"]):
            bad.append(f"{tag}: ended on {kind!r} with reruns left")
        if r.get("verdict") in ("pass", "fail", "blocked") and (not r.get("reason") or r.get("verdict_by") not in ("judge", "rule")):
            bad.append(f"{tag}: a verdict without its reason or its source")
        if r.get("verdict") == "pass":
            if not rules.evidence(r["calls"]):
                bad.append(f"{tag}: passed with no worked browser call")
            if r["verdict_by"] != "judge" or not (jd or {}).get("ok"):
                bad.append(f"{tag}: marked a pass, but the grader's verdict was {(jd or {}).get('ok')!r}")
        if r.get("verdict") == "blocked" and not any(c.get("wall") for c in r["calls"]):
            bad.append(f"{tag}: blocked with no bot wall in its calls")
    return bad


JOIN_MIN = 0.9  # of the Chrome fields, at least this share must be joined to a control of the page, or the score is of too few fields to be the corpus's
LIST_MIN = 0.6  # of the controls Chrome lists, at least this share must be listed by the product (measured 90 % on pages 000-099): a guard against a product that lists nothing, not a tuning knob


def _unproven_forms(folder, f):
    """What the forms rows must be able to prove: every call worked, the answers came from the classifier and not the brain's memory, the join
    reached most fields, every Chrome type has a line in the vocabulary, and the product beats answering one slot for every field."""
    if not f:
        return []
    bad = []
    if f["calls_failed"]:
        bad.append(f"{folder}: {f['calls_failed']} of {f['calls_n']} forms calls failed (a goto that did not load, or a view with no field list), so those pages say nothing")
    for arm, a in f["arms"].items():
        if a["learned"]:
            bad.append(f"{folder}: {a['learned']} {arm} fields were answered from what the brain had learned, not by the classifier alone")
        if a["unmapped"]:
            bad.append(f"{folder}: {a['unmapped']} {arm} fields have a Chrome type that forms_vocabulary.json has no line for (review it before a run)")
        reached = a["join"].get("ok", 0) + a["join"].get("not_listed", 0)
        if a["fields"] and reached / a["fields"] < JOIN_MIN:
            bad.append(f"{folder}: only {reached} of {a['fields']} {arm} Chrome fields were joined to a control of the page (the least is {JOIN_MIN:.0%}): the score would be of too few fields")
        if reached and a["join"].get("ok", 0) / reached < LIST_MIN:
            bad.append(f"{folder}: the product listed a field for only {a['join'].get('ok', 0)} of {reached} {arm} controls Chrome lists (the least is {LIST_MIN:.0%}): it is not reading these pages")
        if a["in"]["n"] and a["in"]["agree"] <= a["stub"]["agree"]:
            bad.append(f"{folder}: {arm}: the product agrees with Chrome on {a['in']['agree']} of {a['in']['n']} fields, no more than answering `{a['stub']['slot']}` for every field ({a['stub']['agree']})")
    return bad


REFUSED_MAX = 0.05  # of the pages, at most this share may be pages whose own script takes the tab away from the saved page
PUBLISHED_TOLERANCE = 0.0006  # the README prints three decimals


def _unproven_pages(folder, env, p):
    """What the pages rows must be able to prove: every look worked, the numbers made here are the benchmark's own for the same answers, its published
    outputs score as its README says (so the scorer is the scorer), and the product beats the stubs."""
    if not p:
        return []
    bad = []
    if p["looks_failed"]:
        bad.append(f"{folder}: {p['looks_failed']} of {p['looks_n']} page looks failed (an error, a part left out, or no words), so those pages say nothing")
    info = env.get("pages") or {}
    for arm, own in (info.get("public_scorer") or {}).items():
        mine = p["metrics"].get(arm)
        if mine is None or any(abs(mine[k] - own[k]) > 1e-9 for k in ("f1", "precision", "recall", "accuracy")):
            bad.append(f"{folder}: the {arm} score made from the rows differs from the benchmark's own function on the same answers")
    for name, got in (info.get("reference") or {}).items():
        want = (info.get("published") or {}).get(name)
        if not want or any(abs(got[k] - want[k]) > PUBLISHED_TOLERANCE for k in ("f1", "precision", "recall", "accuracy")):
            bad.append(f"{folder}: the published output of {name} scores {got['f1']:.3f} F1 here, the repository's README says {want['f1'] if want else 'nothing'}: this is not the benchmark's scorer")
    whole = (env.get("door") or {}).get("url_reps")
    if whole is not None and p["url_reps"] != whole:
        bad.append(f"{folder}: a try, not a result: read(url) was taken {p['url_reps']} times of {whole}")
    if p["refused"] > REFUSED_MAX * p["pages"]:
        bad.append(f"{folder}: the product refused to keep {p['refused']} of {p['pages']} pages open (the most is {REFUSED_MAX:.0%}): read(level=full) is scored on too few pages")
    for arm in PAGES_ARMS:
        if p["metrics"][arm]["f1"] <= p["metrics"]["title"]["f1"]:
            bad.append(f"{folder}: {arm} scores F1 {p['metrics'][arm]['f1']:.3f}, no more than the page's title alone ({p['metrics']['title']['f1']:.3f})")
    return bad


def _unproven_replay(folder, p):
    """What the replay rows must be able to prove: the sites still have the links of the routes, no call failed, the own site saw no POST, and the walk reached its pages."""
    if not p:
        return []
    bad = []
    if p["site_failed"]:
        bad.append(f"{folder}: {p['site_failed']} hops failed for the site (a start page that did not answer 200, or a page without the link of the route): the site changed or was down, so this is not a result")
    if p["calls_failed"]:
        bad.append(f"{folder}: {p['calls_failed']} replay calls failed")
    if p["posts_after"] not in (0, None):
        bad.append(f"{folder}: the own site saw {p['posts_after']} POSTs (a safe run ends at 0)")
    if p["walk_hops"] and p["arrived"] / p["walk_hops"] < ARRIVAL_MIN:
        bad.append(f"{folder}: only {p['arrived']} of {p['walk_hops']} hops were verified at their address (the product claimed {p['claimed']}): it is not walking pages (the least is {ARRIVAL_MIN:.0%})")
    return bad


def _unproven_delegate(folder, p):
    """What the delegate rows must be able to prove: every site answered, and every call worked (a session opened, delegate_task and the
    verifying read answered). A low pass count is the measurement, never a reason to drop the run."""
    if not p:
        return []
    bad = []
    if p["site_failed"]:
        bad.append(f"{folder}: {p['site_failed']} delegate runs missed a goal whose site did not answer 200: the site was down or changed, so this is not a result")
    if p["calls_failed"]:
        bad.append(f"{folder}: {p['calls_failed']} delegate runs had a call that failed (session open, delegate_task or the verifying read)")
    return bad


def ledger_row(env, s, problems):
    """The one line the door appends to RUNS.tsv for a run it just made. A run that fails its own check is `dropped` on the spot:
    the gate then wants its folder gone, and the line stays. Otherwise `kept`; deleting the folder later means editing the line to
    `dropped` with the reason, so a try cannot disappear without a trace (best-of-N)."""
    t, q, a, b = s.get("tools"), s["quiet"], s.get("agent"), s.get("browsecomp")
    f = (s.get("forms") or {}).get("arms", {}).get("as_saved")
    pg = (s.get("pages") or {}).get("metrics")
    verdicts = "; ".join([f"tools {t['pass']}/{t['fail']}/{t['skip']}" if t else "no tools suite"]
                         + ([f"agent first {a['first_pass']}/{a['tasks']} final {a['final_pass']}/{a['tasks']} blocked {a['blocked']}"] if a else [])
                         + ([f"browsecomp passed {b['passed']}/{b['tasks']}"] if b else [])
                         + ([f"forms agree {f['in']['agree']}/{f['in']['n']}, dangerous {f['dangerous']}/{f['scored']}"] if f else [])
                         + ([f"replay arrived {s['replay']['arrived']}/{s['replay']['walk_hops']}"] if s.get("replay") else [])
                         + ([f"delegate passed {s['delegate']['passed']}/{s['delegate']['runs']}, false successes {s['delegate']['false_success']}"] if s.get("delegate") else [])
                         + ([f"pages F1 read_url {pg['read_url']['f1']:.3f}, read_full {pg['read_full']['f1']:.3f}"] if pg else [])
                         + [f"throttled calls {q['throttled']}/{q['measured']}", f"reps {env['reps']}", f"{len(problems)} check problems"])
    why = problems[0].split(": ", 1)[-1] if problems else ""
    return "\t".join([env["run_id"], env["git"]["commit"], verdicts, "dropped" if problems else "kept", why]) + "\n"


def check_ledger(results):
    """What is wrong with RUNS.tsv and the run folders beside it: a folder with no line, a kept line with no folder or another commit,
    a dropped line whose folder is still there or that gives no reason, a repeated run id, a malformed line."""
    path = os.path.join(results, LEDGER)
    if not os.path.isfile(path):
        return [f"{results}: no {LEDGER}: every run the door made needs a line"]
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    bad = [] if lines[:1] == [LEDGER_HEAD] else [f"{path}: the first line must be {LEDGER_HEAD!r}"]
    seen = {}
    for n, ln in enumerate(lines[1:], 2):
        f = ln.split("\t")
        if len(f) != 5 or f[3] not in ("kept", "dropped") or not f[0] or not f[1] or not f[2]:
            bad.append(f"{path}:{n}: want run_id, commit, verdicts, kept|dropped, why (tab separated): {ln!r}")
            continue
        if f[0] in seen:
            bad.append(f"{path}:{n}: run {f[0]} is listed twice")
        seen[f[0]] = f
        folder = os.path.join(results, f[0])
        if f[3] == "dropped":
            if os.path.exists(folder):
                bad.append(f"{path}:{n}: run {f[0]} is dropped but its folder is still there")
            if not f[4].strip():
                bad.append(f"{path}:{n}: run {f[0]} is dropped without a reason")
        elif not os.path.isdir(folder):
            bad.append(f"{path}:{n}: run {f[0]} is kept but has no folder (edit the line to dropped, with the reason)")
        else:
            with open(os.path.join(folder, "env.json"), encoding="utf-8") as e:
                if json.load(e)["git"]["commit"] != f[1]:
                    bad.append(f"{path}:{n}: run {f[0]} was made at another commit than the line says")
    bad += [f"{path}: run folder {d} has no line" for d in sorted(os.listdir(results)) if os.path.isdir(os.path.join(results, d)) and d not in seen]
    return bad


def check(folder):
    """What is wrong with one committed run folder: missing files, rows of another run, a summary that is not what its raw makes."""
    names = sorted(os.listdir(folder))
    if names != sorted(FILES):
        return [f"{folder}: files {names}, wanted exactly {sorted(FILES)}"]
    with open(os.path.join(folder, "env.json"), encoding="utf-8") as f:
        env = json.load(f)
    with open(os.path.join(folder, "raw.json"), encoding="utf-8") as f:
        raw = json.load(f)
    bad = []
    if not raw:
        bad.append(f"{folder}: raw.json has no rows")
    if any(r.get("run_id") != env.get("run_id") for r in raw):
        bad.append(f"{folder}: a raw row belongs to another run than {env.get('run_id')}")
    own_brain = bool((env.get("agent") or {}).get("head"))  # a brain the person already runs: its commit, launch and dirt are theirs; the summary names it
    if env["git"]["dirty"] or (env["brain"]["dirty"] is not False and not own_brain) or len(env["git"]["commit"]) != 40:
        bad.append(f"{folder}: the run is not of one clean commit (commit {env['git']['commit']!r}, dirty {env['git']['dirty']}, brain dirty {env['brain']['dirty']})")
    if not own_brain and not env["brain"].get("launch"):
        bad.append(f"{folder}: env.json does not say how the scratch brain was started (license check, telemetry, state), so it cannot be compared with an installed one")
    if not own_brain and not (env["brain"]["sha"] and len(env["brain"]["sha"]) >= 7 and env["git"]["commit"].startswith(env["brain"]["sha"])):  # the brain names a short sha
        bad.append(f"{folder}: the brain ran sha {env['brain']['sha']!r}, the bench ran commit {env['git']['commit']!r}")
    s, md = render(env, raw)
    bad += _unproven(folder, env, s)
    if "agent" in env["suites"]:
        bad += _agent_problems(folder, env, raw)
    if "browsecomp" in env["suites"]:
        bad += _browsecomp_problems(folder, env, raw)
    with open(os.path.join(folder, "summary.json"), encoding="utf-8") as f:
        if f.read() != json.dumps(s, indent=1, sort_keys=True) + "\n":
            bad.append(f"{folder}: summary.json is not what raw.json makes (hand-edited or stale)")
    with open(os.path.join(folder, "summary.md"), encoding="utf-8") as f:
        if f.read() != md + "\n":
            bad.append(f"{folder}: summary.md is not what raw.json makes (hand-edited or stale)")
    return bad


if __name__ == "__main__":
    d = sys.argv[1]
    with open(os.path.join(d, "env.json"), encoding="utf-8") as f:
        e = json.load(f)
    with open(os.path.join(d, "raw.json"), encoding="utf-8") as f:
        write(d, e, json.load(f))
    print("\n".join(check(d)) or f"{d}: ok")
