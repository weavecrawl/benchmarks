"""The browsecomp suite of the bench door: 100 fixed problems of OpenAI's BrowseComp, one Claude agent driving a scratch brain on the live web.

    python3 benchmarks/browsecomp.py pick --data DIR      print the row ids the published seed picks from the pinned file in DIR
    python3 benchmarks/run.py --scratch DIR --suites browsecomp [--browsecomp-limit N]      run it (bench-server only, see harness/README.md)

Not a command of its own: `run.py` calls `run_suite`. What is fixed, in `benchmarks/browsecomp_tasks.json`: the source url, its byte size
and sha256 (taken from the raw bytes), the seed and the 100 row ids it picks, the agent's prompt, the grader template and every cap. The
suite refuses to start when the file it downloads, or the ids the seed picks from it, differ.

The file holds each problem and answer XOR-encrypted with a per-row canary (an anti-crawl measure, not a secret). The suite decrypts in
memory for the run and writes neither: a row keeps the sha256 of the reference and of the agent's answer, the votes and the counts, never
a question, an answer, a call's arguments or a grader's reasoning (the reasoning quotes the reference). The verdict is parsed here: the
published `browsecomp_eval.py` returns the matched text (`correct: yes`) and compares it to `yes`, so every answer scores wrong there.

One attempt = a fresh scratch brain + one `claude -p` run with only the brain's tools (tests/bench/agent_driver). An attempt that failed
for a model or infra reason (agent_rules.classify) is run again, at most 3 times; a task the agent completed wrong never is. A completed
attempt is graded by three Haiku votes (two `correct: yes` pass). The pieces that do not depend on the task (token, vote, infra stop) are agent.py's.
"""
import base64
import csv
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agent  # noqa: E402
import agent_rules as rules  # noqa: E402

TASKS_FILE = os.path.join(HERE, "browsecomp_tasks.json")
VERDICT = re.compile(r"^[\s*_`>-]*correct[\s*_`]*:[\s*_`]*(yes|no)\b", re.I | re.M)
ALLOWED_KEYS = frozenset("""suite run_id task attempt brain_started agent_run ok subtype is_error timed_out returncode n_calls text turns wall_ms agent_ms cost_usd
usage model calls brain_down start_ms end_ms infra_kind final verdict verdict_by reason judge answer_chars answer_sha256 reference_sha256""".split())
CALL_KEYS = frozenset(("tool", "allowed", "ms", "wall", "error"))


def load_spec(path=TASKS_FILE):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def derive_key(password, length):
    """sha256 of the password, repeated to `length` bytes."""
    key = hashlib.sha256(password.encode()).digest()
    return key * (length // len(key)) + key[: length % len(key)]


def decrypt(ciphertext, password):
    """The text of a base64 `ciphertext` XOR-ed with the key of `password`; raises UnicodeDecodeError for a key that does not fit."""
    data = base64.b64decode(ciphertext)
    return bytes(a ^ b for a, b in zip(data, derive_key(password, len(data)))).decode()


def pick(n_rows, seed, n):
    """n row ids out of range(n_rows): the ones that rank first for the seed, returned in run order (ranked too)."""
    first = sorted(range(n_rows), key=lambda i: rules.rank(seed, f"row|{i}"))[:n]
    return sorted(first, key=lambda i: rules.rank(seed, f"order|{i}"))


def fetch_source(spec, cache):
    """The rows of the pinned file, checked against the recorded size and sha256 first (a moved file is a different bench)."""
    src = spec["source"]
    path = os.path.join(cache, "browse_comp_test_set.csv")
    os.makedirs(cache, exist_ok=True)
    if not os.path.exists(path):
        with urllib.request.urlopen(src["url"], timeout=60) as r:
            with open(path, "wb") as f:
                f.write(r.read())
    with open(path, "rb") as f:
        raw = f.read()
    if len(raw) != src["bytes"]:
        raise agent.Stop(f"the file has {len(raw)} bytes, the spec says {src['bytes']}: another file than the one the ids were picked from")
    if hashlib.sha256(raw).hexdigest() != src["sha256"]:
        raise agent.Stop(f"the file has sha256 {hashlib.sha256(raw).hexdigest()[:12]}, the spec says {src['sha256'][:12]}: another file than the one the ids were picked from")
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8"), newline="")))


def tasks_of(spec, cache):
    """The spec's tasks in run order as {"id", "ques", "answer"}, decrypted in memory; refuses another row count or other ids for the seed."""
    rows = fetch_source(spec, cache)
    if len(rows) != spec["n_rows"]:
        raise agent.Stop(f"the file has {len(rows)} rows, the spec says {spec['n_rows']}")
    if pick(len(rows), spec["seed"], spec["n_tasks"]) != spec["rows"]:
        raise agent.Stop("the published seed picks other ids from the pinned file than benchmarks/browsecomp_tasks.json lists")
    return [{"id": i, "ques": decrypt(rows[i]["problem"], rows[i]["canary"]), "answer": decrypt(rows[i]["answer"], rows[i]["canary"])} for i in spec["rows"]]


def parse_verdict(text):
    """(True|False|None, ""): the last line of the grader's reply that starts with `correct:` and says yes or no; None when there is none.
    The pair shape is what agent._vote expects of a parse."""
    hits = VERDICT.findall(text or "")
    return (hits[-1].lower() == "yes" if hits else None), ""


def judge_prompt(spec, t, response):
    return spec["judge"]["prompt"].format(question=t["ques"], response=response, correct_answer=t["answer"])


def run_judge(spec, t, response, env_extra, state, work):
    """{"ok", "votes", "agree", "runs", "model"}: `votes` Haiku votes on the same prompt, a pass when enough say `correct: yes`. The votes' text is dropped."""
    prompt = judge_prompt(spec, t, response)
    cast = [agent._vote(spec, prompt, [], env_extra, state, work, parse=parse_verdict) for _ in range(spec["judge"]["votes"])]
    votes = [v["ok"] for v in cast]
    return {"ok": rules.majority(votes), "votes": votes, "agree": rules.agree(votes), "runs": sum(v["runs"] for v in cast), "model": next((v["model"] for v in cast if v["model"]), None)}


def cause(row):
    """Why a final attempt is not a pass, or 'pass', from its own fields: blocked:<wall>, infra_failed, fail:no_answer, fail:no_page, fail:wrong."""
    v = row["verdict"]
    if v == "blocked":
        return "blocked:" + "+".join(sorted({c["wall"] for c in row["calls"] if c.get("wall")}))
    if v != "fail":
        return v
    if not row.get("answer_chars"):
        return "fail:no_answer"
    if not rules.evidence(row["calls"]):
        return "fail:no_page"
    return "fail:wrong" if row.get("verdict_by") == "judge" else "fail:not_judged"


def agent_prompt(spec, t):
    return spec["agent"]["prompt"].format(ques=t["ques"])


def _row(run_id, t, n, r, brain_started, brain_down, secrets):
    """One raw row of one attempt: agent.attempt_row without the task text, the call arguments and (for a completed attempt) any text."""
    row = agent.attempt_row(run_id, {"id": t["id"], "site": "", "ref_type": ""}, n, r, brain_started, brain_down)
    for k in ("site", "ref_type"):
        del row[k]
    row["suite"] = "browsecomp"
    row["calls"] = [{k: c[k] for k in CALL_KEYS} for c in row["calls"]]
    row["text"] = agent.scrub((r["final"] if not r["ok"] else "")[-300:] + " " + r["stderr"][-300:], secrets + [t["answer"], t["ques"]]).strip() if r and not r["ok"] else ""
    return row


def _task(run_id, scratch, spec, t, door, driver, env_extra, state, info, sleep, log, rows):
    """All attempts of one task: appends every attempt's row to `rows` (a Stop raised after an attempt leaves its row there)."""
    secrets = state["secrets"]
    for n in range(1, rules.MAX_ATTEMPTS + 1):
        if state["agent_runs"] >= spec["caps"]["agent_runs"]:
            raise agent.Stop(f"the agent cap of {spec['caps']['agent_runs']} runs is spent before row {t['id']} attempt {n}")
        t0 = time.time()
        work = os.path.join(scratch, "browsecomp", str(t["id"]), str(n))
        os.makedirs(work, exist_ok=True)
        brain = door.Brain(os.path.join(work, "brain"), door.free_port(), door.free_port())
        r, started, down = None, True, False
        try:
            try:
                brain.start()
            except RuntimeError as e:
                started = False
                log(f"row {t['id']} attempt {n}: brain did not start: {str(e)[:120]}")
            if started:
                info["health"] = info["health"] or brain.health()
                info["launch"] = info["launch"] or door.launch(brain.work)
                os.environ["BENCH_MCP_URL"] = brain.url + "/mcp"
                os.environ["BENCH_MCP_TOKEN_FILE"] = os.path.join(brain.work, "token")
                state["agent_runs"] += 1
                r = driver.run_task(agent_prompt(spec, t), model=spec["agent"]["model"], max_turns=spec["agent"]["max_turns"],
                                    wall_s=spec["agent"]["wall_s"], workdir=work, env_extra=env_extra, evidence=False)
                try:
                    brain.health()
                    if not info["browser"] or info["browser"].startswith("unknown"):
                        info["browser"] = door.browser(brain.work)
                except OSError:
                    down = True
        finally:
            brain.stop()
        if r:
            r["final"] = agent.scrub(r["final"], secrets)
            info["agent_resolved"] = info["agent_resolved"] or r["model"]
        row = _row(run_id, t, n, r, started, down, secrets)
        row["start_ms"], row["end_ms"] = int(t0 * 1000), int(time.time() * 1000)
        kind = row["infra_kind"] = rules.classify(row)
        row["final"] = not (kind and rules.may_rerun(kind, n))
        rows.append(row)
        if kind:
            agent._after_infra(kind, state, n)
        else:
            state["rate_streak"] = 0
        if not row["final"]:
            log(f"row {t['id']} attempt {n}: {kind}; run again")
            if sleep:
                time.sleep(agent.BACKOFF_S.get(kind, 15) * n)
            continue
        if kind:
            row.update(verdict="infra_failed", verdict_by="rule", reason=f"{kind} on every one of {n} attempts" if n > 1 else kind, judge=None)
        else:
            answer = rules.answer_of(r["final"])[0]
            row.update(answer_chars=len(answer), answer_sha256=hashlib.sha256(answer.encode()).hexdigest(), reference_sha256=hashlib.sha256(t["answer"].encode()).hexdigest())
            walls = sorted({c["wall"] for c in r["calls"] if c.get("wall")})
            jd = None
            if not r["final"].strip():
                verdict, by, reason = "fail", "rule", "no final answer"
            elif not rules.evidence(r["calls"]):
                verdict, by, reason = "fail", "rule", "no page was opened or read: an answer from memory is not a result"
            else:
                try:
                    jd = run_judge(spec, t, r["final"], env_extra, state, work)
                except agent.Stop as e:
                    row.update(verdict="fail", verdict_by="rule", reason=f"not judged: {e}", judge=None)
                    raise
                verdict, by, reason = ("pass" if jd["ok"] else "fail"), "judge", f"{jd['agree']} votes say {'correct' if jd['ok'] else 'not correct'}"
            if verdict == "fail" and walls:
                verdict, by, reason = "blocked", "rule", f"bot wall ({', '.join(walls)}) and no passing answer; a person solves it, the bench does not"
            row.update(verdict=verdict, verdict_by=by, reason=reason, judge=jd)
            info["judge_resolved"] = info["judge_resolved"] or (jd or {}).get("model")
        log(f"row {t['id']:5d} {row['verdict'].upper():11s} by {row['verdict_by']:6s} attempts {n} turns {row['turns']} wall {row['wall_ms'] / 1000:.0f}s")
        return None
    return None


def run_suite(run_id, scratch, spec, tasks, door, limit=0, sleep=True, log=print):
    """Run every task (the first `limit` for a try). Returns (rows, info); info is what env.json records about the agent side."""
    import driver  # tests/bench/agent_driver
    env_extra, secrets, version = agent.cli_env(scratch)
    state = {"agent_runs": 0, "judge_runs": 0, "rate_streak": 0, "secrets": secrets, "sleep": sleep}
    info = {"claude_cli": version, "agent_model": spec["agent"]["model"], "judge_model": spec["judge"]["model"], "agent_resolved": None,
            "judge_resolved": None, "health": None, "launch": None, "browser": None, "stopped": None, "agent_runs": 0, "judge_runs": 0}
    rows = []
    try:
        for t in tasks[: limit or None]:
            _task(run_id, scratch, spec, t, door, driver, env_extra, state, info, sleep, log, rows)
    except agent.Stop as e:
        info["stopped"] = str(e)
    info["agent_runs"], info["judge_runs"] = state["agent_runs"], state["judge_runs"]
    return rows, info


def main(argv):
    if len(argv) >= 3 and argv[0] == "pick" and argv[1] == "--data":
        spec = load_spec()
        print(json.dumps(pick(len(fetch_source(spec, argv[2])), spec["seed"], spec["n_tasks"])))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
