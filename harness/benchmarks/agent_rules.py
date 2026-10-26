"""The rules of the A1-lite agent suite that a reader must be able to re-make from the raw rows: which tasks, what an answer is,
the deterministic check, and which failed attempt may be run again. Pure and stdlib only: `summarize.check` (and so the gate) calls
these on every committed row, and `agent.py` calls the same functions to decide while it runs, so the two cannot drift.
"""
import datetime
import hashlib
import re
import unicodedata
import urllib.parse

MAX_ATTEMPTS = 4  # the first run and at most 3 reruns, and only for the kinds below
RERUN = ("brain_start", "timeout_before_first_call", "rate_limit", "api_error", "cli_crash")  # a model or infra reason, never the agent's answer
ABORT = ("auth",)  # a token that does not work: no rerun can help, and the run stops

REDATE_MIN_DAYS = 30  # a re-dated question's earliest date is at least this many days after the run date
VOTES_NEEDED = 2  # of the judge's votes, this many SUCCESS make a pass

BROWSER_TOOLS = ("goto", "read", "view", "click", "fill", "scroll", "tabs", "script", "maps")  # a call to one that worked is evidence a page was opened

RATE = re.compile(r"rate.?limit|usage limit|limit reached|too many requests|\b429\b|quota", re.I)
API = re.compile(r"api error|overloaded|\b(500|502|503|504|529)\b|ECONNRESET|ETIMEDOUT|ENOTFOUND|socket hang up|fetch failed|network error|"
                 r"request timed out|internal server error|service unavailable|connection (error|refused|reset)", re.I)
AUTH = re.compile(r"\b401\b|invalid (api key|token|bearer)|authentication|oauth token|not logged in|please run /login|unauthorized", re.I)


# ---- which tasks -----------------------------------------------------------------------------------------------------------

def rank(seed, key):
    """A fixed order that needs no random generator: sha256 of the published seed and the key."""
    return hashlib.sha256(f"{seed}|{key}".encode()).hexdigest()


def pool(rows, impossible, reference):
    """The tasks browser-use scored: the data rows minus the impossible ids, each with its reference answer and its kind
    (`golden`: a stable fact; `possible`: true on the day it was written, the live page may differ now)."""
    ref = {f"{site}--{a['id']}": a for site, v in reference.items() for a in v["answers"]}
    skip = set(impossible)
    return [{"id": t["id"], "site": t["web_name"], "ques": t["ques"], "web": t["web"], "ref_type": ref[t["id"]]["type"], "reference": ref[t["id"]]["ans"]}
            for t in rows if t["id"] not in skip]


def select(tasks, seed, n):
    """n task ids spread over every site: n // sites each, and the n % sites left over go to the sites that rank first for the seed;
    inside a site the tasks that rank first. Returned in run order (ranked too, so one site is not hit many times in a row)."""
    sites = sorted({t["site"] for t in tasks})
    if n < len(sites):
        raise ValueError(f"{n} tasks cannot cover {len(sites)} sites")
    extra = set(sorted(sites, key=lambda s: rank(seed, "site|" + s))[: n % len(sites)])
    chosen = []
    for site in sites:
        mine = sorted((t for t in tasks if t["site"] == site), key=lambda t: rank(seed, "task|" + t["id"]))
        chosen += [t["id"] for t in mine[: n // len(sites) + (site in extra)]]
    return sorted(chosen, key=lambda i: rank(seed, "order|" + i))


# ---- dates: a question that names a date the site no longer offers --------------------------------------------------------------

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
DATE = re.compile(rf"\b({'|'.join(MONTHS)}) (\d{{1,2}})(?:-(\d{{1,2}}))?, (\d{{4}})\b")  # 'March 20, 2025' and the range 'March 1-7, 2025'


def dates_in(ques):
    """The date strings of a question, exactly as written."""
    return [m.group(0) for m in DATE.finditer(ques)]


def redate(ques, run_date):
    """(question, years): every date of the question moved ahead by the same whole number of years, the smallest for which the earliest
    date is at least REDATE_MIN_DAYS after `run_date` (a datetime.date, UTC); a question with no date, or already far enough ahead, is
    returned as it is with 0 years."""
    found = list(DATE.finditer(ques))
    if not found:
        return ques, 0
    first = min(datetime.date(int(m.group(4)), MONTHS.index(m.group(1)) + 1, int(m.group(2))) for m in found)
    years = max(0, run_date.year - first.year)
    while first.replace(year=first.year + years) < run_date + datetime.timedelta(days=REDATE_MIN_DAYS):
        years += 1
    return DATE.sub(lambda m: m.group(0)[:-4] + str(int(m.group(4)) + years), ques), years


# ---- what an answer is, and the deterministic check ------------------------------------------------------------------------

def answer_of(final):
    """(answer, found): the text after the last `ANSWER:` of the final message; the whole message's last 600 chars when there is none."""
    hits = list(re.finditer(r"ANSWER:\s*", final or ""))
    if hits:
        return final[hits[-1].end():].strip()[:1500], True
    return (final or "").strip()[-600:], False


def norm(text):
    """Lower case, no accents, every run of non-letters-or-digits one space; a decimal point and a thousands comma stay inside a number."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    return " ".join(re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text).split())


def det_check(reference, answer, max_words=4):
    """True when the reference is short enough to be an exact fact (at most `max_words` words after norm) and the answer holds it as
    whole words; None when the reference is too long for an exact check (a judge decides); False when it is short and not found.
    A False is not a failure: the judge still reads it, because '$5' and 'five dollars' are one answer."""
    ref, ans = norm(reference), norm(answer)
    if not ref or len(ref.split()) > max_words:
        return None
    return re.search(r"(?<![a-z0-9.])" + re.escape(ref) + r"(?![a-z0-9]|\.\d)", ans) is not None


# ---- which failed attempt may run again ------------------------------------------------------------------------------------

def classify(row):
    """Why an attempt failed for a reason that is not the agent's work, or None. From the row's own fields only:
    ok, subtype, timed_out, returncode, n_calls, text (the result text and the CLI's stderr), brain_started.
    None means the attempt is final: it completed (right or wrong), or it was the agent's own failure (turn cap, a wall cap after it began)."""
    if row.get("brain_started") is False:
        return "brain_start"
    if row.get("ok"):
        return None
    if row.get("subtype") == "error_max_turns":
        return None
    if row.get("timed_out"):
        return "timeout_before_first_call" if not row.get("n_calls") else None
    text = row.get("text") or ""
    if AUTH.search(text):
        return "auth"
    if RATE.search(text):
        return "rate_limit"
    if API.search(text):
        return "api_error"
    if row.get("subtype") in (None, "error_during_execution"):
        return "cli_crash"
    return "api_error" if row.get("is_error") else None


def may_rerun(kind, attempt):
    return kind in RERUN and attempt < MAX_ATTEMPTS


def evidence(calls):
    """True when the agent made at least one browser call that was allowed and did not fail: a pass needs the browser."""
    return any(c["tool"] in BROWSER_TOOLS and c["allowed"] and not c["error"] for c in calls)


def _host(url):
    """The host of an address without a leading `www.`, or None."""
    host = urllib.parse.urlsplit(url or "").hostname
    return host[4:] if host and host.startswith("www.") else host


def site_fault(calls, web):
    """The fault the task's own site showed, as '<fault> on <host>', or None: the last call that names a page of the site `web` (the host or a subdomain of it)
    was answered with a fault (driver._fault_word). A later good page of the site, a fault of another host (an ad, a CDN), a call that never
    answered (ours) and a call with no address all leave it to the agent's verdict."""
    site = _host(web)
    last = None
    for i, c in enumerate(calls):
        host = _host((c["args"] or {}).get("url"))
        if host and site and (host == site or host.endswith("." + site)):
            last = c, host, i
    if not last or not last[0].get("fault"):
        return None
    url = last[0]["args"]["url"].rstrip("/")
    if last[0]["fault"] in ("http_404", "http_410") and url != web.rstrip("/") and not any(url in (p.get("text") or "") for p in calls[:last[2]]):
        return None  # a not-found address neither the task nor a page the agent read gave: the agent made it up
    return f"{last[0]['fault']} on {last[1]}"


def majority(votes):
    """True when enough of the judge's votes are SUCCESS; a vote with no verdict (None) is not one."""
    return sum(v is True for v in votes) >= VOTES_NEEDED


def agree(votes):
    """How many of the votes say the verdict, as '2/3'; a vote with no verdict (None) says nothing, so it is on neither side."""
    ok = majority(votes)
    return f"{sum(v is ok for v in votes)}/{len(votes)}"


def cause(row):
    """Why a final attempt is not a pass, or 'pass', from its own fields: pass, blocked:<wall>, held:<word>, site_fault:<fault>, infra_failed, fail:no_answer,
    fail:no_page, fail:judge, fail:not_judged."""
    v = row["verdict"]
    if v == "blocked":
        return "blocked:" + "+".join(sorted({c["wall"] for c in row["calls"] if c.get("wall")}))
    if v == "held":
        return "held:" + "+".join(sorted({c["held"] for c in row["calls"] if c.get("held")}))
    if v == "site_fault":
        return "site_fault:" + "+".join(sorted({c["fault"] for c in row["calls"] if c.get("fault")}))
    if v != "fail":
        return v
    if not (row.get("final_text") or "").strip():
        return "fail:no_answer"
    if not evidence(row["calls"]):
        return "fail:no_page"
    return "fail:judge" if row.get("verdict_by") == "judge" else "fail:not_judged"


def wilson(k, n, z=1.96):
    """The 95% Wilson score interval of k successes in n, in percent (low, high); n = 0 gives (None, None)."""
    if not n:
        return None, None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return round(100 * (centre - half), 1), round(100 * (centre + half), 1)
