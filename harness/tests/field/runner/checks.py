"""What a case expects of one tool answer. Pure functions: no network, no brain.

expect keys (all optional; a case with none only proves the call did not crash the brain):
  ok         true  -> the call is not an error and the answer does not say ok:false
  not_ok     true  -> the call is an error, or the answer says ok:false / loaded:false / all_ok:false
  error      code  -> the answer text carries that error code, e.g. bad_argument
  contains   [s]   -> every string is in the answer text (case-insensitive)
  any_of     [s]   -> at least one string is in the answer text (case-insensitive)
  not_contains [s] -> none of the strings is in the answer text (case-insensitive)
  json       {p:v} -> dotted path p of the parsed answer equals v
  max_ms     n     -> the call took at most n ms
  max_bytes  n     -> the answer is at most n bytes (a 5 MB page must not come back as a 5 MB answer)
  answered   true  -> the brain answered: not a client timeout or a transport failure (the weakness suite sets it on every case)
  clean      true  -> the answer leaks no internals: no Python traceback, no exception class name, no file path of the brain

A case may also carry `"setup": true` (outside `expect`): it only prepares the page for the cases after it (a goto, a first fill).
The bench counts its pass beside the others and says how many passes are setup steps (`strength`).
"""
import json
import re

LEAK = re.compile(r"Traceback \(most recent|\b(KeyError|AttributeError|TypeError|ValueError|IndexError|NameError|ZeroDivisionError|"
                  r"RuntimeError|AssertionError|UnicodeError|UnicodeEncodeError|RecursionError|MemoryError|NotImplementedError|"
                  r"JSONDecodeError|ValidationError)\b|\.py\", line \d+|/(home|Users)/[^ \"']*\.py")


def parse(text):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def node(item):
    """A `view` node as a dict: a node that is a line (`ref role[ @href] label`, `core.view.for_agent`) is split back into
    `ref`, `role`, `href` (a link) and `label`; a node that is an object is returned as it is."""
    if not isinstance(item, str):
        return item
    ref, role, rest = (item.split(" ", 2) + ["", ""])[:3]
    out = {"ref": ref, "role": role}
    if role == "link":
        href, _, rest = rest.partition(" ")
        out["href"] = href[1:]
    if rest:
        out["label"] = rest
    return out


def _path(obj, dotted):
    for part in dotted.split("."):
        if isinstance(obj, dict) and part in obj:
            obj = obj[part]
        elif isinstance(obj, list) and part.isdigit() and int(part) < len(obj):
            obj = obj[int(part)]
        else:
            return None
    return obj


def strength(expect):
    """How much of an answer a case's expectation looks at, for the bench to report beside its pass count:
    content (contains / any_of / json: the answer must carry something), refusal (not_ok or an error code), ok (only that the call
    worked), weak (only negatives, limits, or nothing: a stub answer can pass it)."""
    if any(k in expect for k in ("contains", "any_of", "json")):
        return "content"
    if expect.get("not_ok") or "error" in expect:
        return "refusal"
    return "ok" if expect.get("ok") else "weak"


def says_not_ok(is_error, parsed):
    if is_error:
        return True
    return isinstance(parsed, dict) and (parsed.get("ok") is False or parsed.get("loaded") is False
                                  or parsed.get("all_ok") is False)


def evaluate(expect, text, is_error, wall_ms):
    """Return the list of failed expectations (empty = pass)."""
    failed = []
    parsed = parse(text)
    low = (text or "").lower()
    bad = says_not_ok(is_error, parsed)
    if expect.get("ok") and bad:
        failed.append("expected ok, got an error or ok:false")
    if expect.get("not_ok") and not bad:
        failed.append("expected a refusal or failure, got ok")
    if "error" in expect and expect["error"].lower() not in low:
        failed.append(f"error code {expect['error']!r} not in answer")
    for s in expect.get("contains", []):
        if s.lower() not in low:
            failed.append(f"missing {s!r}")
    if expect.get("any_of") and not any(s.lower() in low for s in expect["any_of"]):
        failed.append(f"none of {expect['any_of']!r} in answer")
    for s in expect.get("not_contains", []):
        if s.lower() in low:
            failed.append(f"unexpected {s!r}")
    for p, v in expect.get("json", {}).items():
        got = _path(parsed, p)
        if got != v:
            failed.append(f"json {p} = {got!r}, wanted {v!r}")
    if "max_ms" in expect and wall_ms > expect["max_ms"]:
        failed.append(f"took {wall_ms:.0f} ms, limit {expect['max_ms']}")
    if "max_bytes" in expect and len((text or "").encode()) > expect["max_bytes"]:
        failed.append(f"answer is {len((text or '').encode())} bytes, limit {expect['max_bytes']}")
    if expect.get("clean"):
        leak = LEAK.search(text or "")
        if leak:
            failed.append(f"answer leaks internals: {leak.group(0)!r}")
    if expect.get("answered") and ("[client_timeout]" in (text or "") or "[client_exception]" in (text or "")):
        failed.append("no answer from the brain (client timeout or transport failure)")
    return failed
