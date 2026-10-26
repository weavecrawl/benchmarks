"""Claude Code hook for the bench agent: the brain's calls may name one head and nothing else (default bench-server.b).

The default head of the product is a person's own Chrome. `decide` is the rule; `handle` and `main` are the hook:
PreToolUse and PostToolUse both land here (stdin JSON), each appends one line with a clock to $BENCH_GUARD_LOG
(the per-call time the driver reads), and a refused PreToolUse exits 2 with the reason on stderr.

$BENCH_HEAD names another head (`<device>.<mode>`). On a person's device (mode a, the Chrome extension, or c, the desktop app) the bench
also touches only tabs it opened itself: `tabs open` writes the new tab's id to $BENCH_OWN_TABS, nothing acts before one exists,
a tab is focused or closed only when it is listed there, `all` and `manage_head` are refused. Every `session_id` an answer names
is appended to $BENCH_OWN_SESSIONS, so the bench closes the brain sessions its attempt opened.
"""
import json
import os
import re
import sys
import time

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "brand.json")) as _brand:
    # the product name is read from brand.json never typed here
    PREFIX = f"mcp__{json.load(_brand)['namespace']}-local__"

HEAD = "bench-server.b"
OWN_TABS_FILE = "own_tabs.txt"  # in a task's folder: one tab id per line, the tabs the bench opened
OWN_SESSIONS_FILE = "own_sessions.txt"  # in a task's folder: one brain session id per line, the sessions the attempt's calls opened or used
ACTING = ("goto", "read", "view", "click", "fill", "scroll", "wait", "script", "maps")  # the tools that act on a session's tab


def head_info(head):
    """{"name", "device", "mode", "person_device"} for a head label `device.mode` (mode a: the person's Chrome, b: a server's own browser,
    c: the desktop app; a and c are a person's device), or None for any other shape."""
    m = re.fullmatch(r"([\w-]+)\.([abc])", head or "")
    return {"name": head, "device": m[1], "mode": m[2], "person_device": m[2] in ("a", "c")} if m else None


def decide(tool_name, tool_input, head=HEAD, own_tabs=()):
    """(allowed, reason) for one tool call."""
    if not tool_name.startswith(PREFIX):
        return True, ""
    tool, args = tool_name[len(PREFIX):], tool_input or {}
    info = head_info(head) or {"device": head, "mode": "", "person_device": False}
    if tool == "ask_human":
        return False, "ask_human sends a notice to a person's devices; a bench has no person"
    if tool == "manage_head" and info["person_device"]:
        return False, "manage_head changes a person's browser app; a bench never does"
    if tool == "session":
        on = f"{info['device']}/{info['mode']}"
        if args.get("action") == "open" and args.get("on") not in (on, head):
            return False, f"session open must say on=\"{on}\""
        return True, ""
    if args.get("head") != head:
        return False, f"every call to the brain must pass head=\"{head}\" (the default head is a person's Chrome)"
    if info["person_device"]:
        if tool in ACTING and not own_tabs:
            return False, "open your own tab first: tabs action=\"open\" (this is a person's browser; the bench never acts on their tabs)"
        if tool == "tabs":
            if args.get("all"):
                return False, "tabs all=true lists the person's other tabs; a bench never looks at them"
            if args.get("action") in ("focus", "close") and args.get("tab_id") not in own_tabs:
                return False, "tabs focus and close take only a tab the bench opened (no id means the active tab, which may be the person's)"
    return True, ""


def _text(response):
    return response if isinstance(response, str) else json.dumps(response)


def opened_tab(tool_name, tool_input, response):
    """The id a `tabs open` answered, or None for any other call."""
    if tool_name != PREFIX + "tabs" or (tool_input or {}).get("action") != "open":
        return None
    m = re.search(r'tab_id\\?"?\s*:\s*\\?"?([\w.-]+)', _text(response))
    return m[1] if m else None


def session_ids(response):
    """The brain session ids an answer names (`goto` and `session open` carry one), in order."""
    return re.findall(r'session_id\\?"?\s*:\s*\\?"([\w.-]+)', _text(response))


def without_situation(value):
    """`value` (a JSON text, or parsed JSON, also inside a list of content blocks) with every `situation` key dropped at any depth: that block lists
    the other heads' tabs, not the call's own. A text that is not JSON comes back as it is."""
    if isinstance(value, str):
        try:
            return without_situation(json.loads(value)) if value.lstrip()[:1] in ("{", "[") else value
        except ValueError:
            return value
    if isinstance(value, dict):
        return {k: without_situation(v) for k, v in value.items() if k != "situation"}
    return [without_situation(v) for v in value] if isinstance(value, list) else value


def touched_person_tab(tool_name, response):
    """True when the answer of an act names the person's tab as the one it acted on (`"owner": "person"`, its `situation` block aside); a tab list is not an act."""
    return not tool_name.endswith(("__tabs", "__session")) and bool(re.search(r'owner\\?"?\s*:\s*\\?"person', _text(without_situation(response))))


def handle(event):
    """One hook event: (allowed, reason). Logs the call, and records the bench's own tab when a `tabs open` came back."""
    phase, name, inp = event.get("hook_event_name", ""), event.get("tool_name", ""), event.get("tool_input") or {}
    head, own_file = os.environ.get("BENCH_HEAD", HEAD), os.environ.get("BENCH_OWN_TABS")
    own = set(open(own_file).read().split()) if own_file and os.path.exists(own_file) else set()
    allowed, why = decide(name, inp, head, own)
    response = event.get("tool_response")
    tab = opened_tab(name, inp, response) if phase == "PostToolUse" else None
    if tab and own_file:
        with open(own_file, "a") as f:
            f.write(tab + "\n")
    sessions_file = os.environ.get("BENCH_OWN_SESSIONS")
    if sessions_file and phase == "PostToolUse" and name.startswith(PREFIX) and (ids := session_ids(response)):
        with open(sessions_file, "a") as f:
            f.write("\n".join(ids) + "\n")
    log = os.environ.get("BENCH_GUARD_LOG")
    if log and name.startswith(PREFIX):
        with open(log, "a") as f:
            f.write(json.dumps({"t": time.time(), "phase": phase, "tool": name[len(PREFIX):], "id": event.get("tool_use_id"),
                                "allowed": allowed, "why": why, "head": inp.get("head"),
                                "person_tab": phase == "PostToolUse" and touched_person_tab(name, response)}) + "\n")
    return allowed, why


def main():
    event = json.load(sys.stdin)
    allowed, why = handle(event)
    if event.get("hook_event_name") == "PreToolUse" and not allowed:
        print(why, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
