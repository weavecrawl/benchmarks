"""The forms suite: what the product says each field of Chromium's saved real-site forms is, against what Chrome's own heuristics say.

Data: Chromium's autofill heuristics corpus at a pinned commit (corpora.json): 184 saved forms and, per form, the field type Chrome
gives each control. Path: each page is served from loopback and opened with `goto`, then `view(kind="form")` through the MCP, the
same door an agent uses (form_read + field_slots.classify), not a unit call.

The product's field list does not name a control's `name` or `id`, and Chrome's output names nothing else, so a field is joined to
Chrome's line in two steps that guess nothing:
  1. Chrome's line -> a control of the saved HTML. Chrome writes the control's name (or id); the page is parsed here and the k-th
     line of a name is paired with the k-th control of that name, in document order. A name Chrome lists and the page does not have
     is counted (`no_control`), not paired with the nearest.
  2. A control -> the product's field. A second copy of the page (variant `b`) carries a marker as the value of every control that
     is not a choice list (`wcb-<k>`, the type of a number, date or password box turned to text so its value shows; an extra last
     selected option in a select), and `view` reports each field's `filled` value, so the marker names the field's place in the
     list. (A ref is not stable between two loads of a page: the session counts them on.) The copy is used only for this; the answer is
     read from the page as saved (variant `a`) at that place, and counted only when the copy has a field with the same label at the
     same place, else the field is `unverified`.
A third copy (`c`) has the attributes in which the page tells its own field type (`autocomplete`) taken out, so the classifier cannot
read the answer; it is measured in the same way.

Nothing is expected here but what Chrome's files say; `forms_vocabulary.json` says which of the product's slot names mean the same
as each Chrome type (reviewed before the first run). The scoring is in summarize.py (pure, from the rows).
"""
import asyncio
import collections
import html
import html.parser
import json
import os
import re

import corpus
import corpus_site

NAME = "chromium_autofill"
SKIP_TYPES = {"hidden", "submit", "button", "image", "reset", "checkbox", "radio", "file"}  # Chrome writes none of these (checked: see forms_vocabulary.json why)
SANITIZED = {"number", "date", "datetime-local", "month", "week", "time", "range", "color", "password"}  # a browser empties a value that is not of the type's form; `view` never shows a password's value
DECLARES = ("autocomplete", "x-autocompletetype", "autocompletetype")  # the attributes a page uses to say what a field is
MARK = re.compile(r"^wcb-(\d+)$")
ARMS = {"a": "as_saved", "c": "no_declared_type"}  # the two measured copies; `b` only names the fields


class Controls(html.parser.HTMLParser):
    """Every input, select and textarea start tag of a page with where it sits in the text, and the eligible ones (the controls Chrome
    can list) numbered in document order. The text is the file decoded with surrogateescape, so any byte survives the round trip."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.text, self.tags, self.eligible = text, [], []
        self.starts = [0]
        for line in text.split("\n"):
            self.starts.append(self.starts[-1] + len(line) + 1)
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag not in ("input", "select", "textarea"):
            return
        line, col = self.getpos()
        start = self.starts[line - 1] + col
        raw = self.get_starttag_text()
        a = {}
        for k, v in attrs:
            a.setdefault(k, v if v is not None else "")
        kind = (a.get("type") or "text").strip().lower() if tag == "input" else tag
        eligible = kind not in SKIP_TYPES
        t = {"tag": tag, "attrs": attrs, "start": start, "end": start + len(raw), "type": kind, "name": a.get("name") or a.get("id") or "",
             "autocomplete": a.get("autocomplete"), "k": len(self.eligible) if eligible else None}
        self.tags.append(t)
        if eligible:
            self.eligible.append(t)


def _tag(tag, attrs):
    return "<" + tag + "".join(f" {k}" if v is None else f' {k}="{html.escape(v, quote=True)}"' for k, v in attrs) + ">"


def _apply(text, edits):
    """edits: (start, end, replacement) that do not overlap; applied from the end so positions stay true."""
    for start, end, new in sorted(edits, reverse=True):
        text = text[:start] + new + text[end:]
    return text


def variant_b(text, controls):
    """The page with a marker in every eligible control, to learn which product field is which control."""
    edits = []
    for t in controls.eligible:
        mark = f"wcb-{t['k']}"
        if t["tag"] == "input":
            attrs = [(k, v) for k, v in t["attrs"] if k != "value"]
            if t["type"] in SANITIZED:
                attrs = [(k, "text" if k == "type" else v) for k, v in attrs if k not in ("min", "max", "step")]
            edits.append((t["start"], t["end"], _tag("input", attrs + [("value", mark)])))
        else:
            close = re.compile(rf"</{t['tag']}\s*>", re.I).search(text, t["end"])
            if not close:
                continue  # an unclosed control cannot carry a marker: its field is joined as `unverified`
            if t["tag"] == "textarea":
                edits.append((t["end"], close.start(), mark))
            else:
                edits.append((close.start(), close.start(), f'<option selected value="{mark}">{mark}</option>'))
    return _apply(text, edits)


def variant_c(text, controls):
    """The page without the attributes in which it says what each control is."""
    edits = []
    for t in controls.tags:
        if any(k in DECLARES for k, _ in t["attrs"]):
            edits.append((t["start"], t["end"], _tag(t["tag"], [(k, v) for k, v in t["attrs"] if k not in DECLARES])))
    return _apply(text, edits)


def chrome_fields(out_text):
    """The lines of one Chrome output file: type | name | label | placeholder | form. A blank line ends a form."""
    out = []
    for line in out_text.split("\n"):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split("|")]
        out.append({"type": parts[0], "name": parts[1], "label": parts[2] if len(parts) > 2 else ""})
    return out


def pair(chrome, controls):
    """Chrome's k-th line of a name -> the k-th eligible control of that name (None when the page has fewer)."""
    by_name = collections.defaultdict(list)
    for c in controls.eligible:
        by_name[c["name"]].append(c)
    seen = collections.Counter()
    out = []
    for f in chrome:
        mine = by_name.get(f["name"], [])
        n = seen[f["name"]]
        seen[f["name"]] += 1
        out.append(mine[n] if n < len(mine) else None)
    return out


def carries_token(control, tokens):
    value = (control.get("autocomplete") or "").strip().lower().split()
    return bool(value) and value[-1] in tokens


def decode(data):
    return data.decode("utf-8", "surrogateescape")


def encode(text):
    return text.encode("utf-8", "surrogateescape")


def pages(dest):
    """[(stem, html bytes, chrome output text)] in file order; a page without an output file stops the run."""
    names = sorted(n for n in os.listdir(os.path.join(dest, "input")) if n.endswith(".html"))
    out = []
    for n in names:
        stem = n[:-5]
        out.append((stem, corpus.read(dest, f"input/{n}"), decode(corpus.read(dest, f"output/{stem}.out"))))
    return out


def group(stem):
    """The kind of page, from its file name: i18n / autocomplete / misc are Chromium's own test pages, the rest are saved real sites."""
    word = stem.split("_", 1)[1] if "_" in stem else stem
    for g in ("i18n", "autocomplete", "misc"):
        if word.startswith(g):
            return "chromium test page"
    return "saved real site"


def expected(dest):
    """Rows a whole run leaves: three copies of every page opened and read (a goto and a view each), a row per Chrome field and arm, a row per page and arm."""
    ps = pages(dest)
    return {"calls": len(ps) * 3 * 2, "fields": sum(len(chrome_fields(o)) for _, _, o in ps) * len(ARMS), "pages": len(ps) * len(ARMS)}


def _view(text):
    try:
        answer = json.loads(text)
        fields, ours = answer.get("fields"), answer.get("ours") or {}
    except (ValueError, AttributeError):
        return None
    return [{**f, **ours.get(f.get("ref"), {})} for f in fields] if isinstance(fields, list) else None


def marker_places(fields):
    """{eligible control k: place in the product's field list} from the `filled` values of the marked copy."""
    out = {}
    for j, f in enumerate(fields or []):
        filled = f.get("filled")
        m = MARK.match(filled) if isinstance(filled, str) else None
        if m:
            out[int(m.group(1))] = j
    return out


def same_field(a, b):
    """Whether the product's field `a` (page as saved) is the field `b` of the marked copy: the same label. A control with no label of
    its own takes its value as its label, so when the marked copy's label IS its marker the saved page's label (none, or the page's own
    value) cannot be compared and the place is trusted."""
    label = b.get("label")
    return a.get("label") == label or (isinstance(label, str) and label == b.get("filled") and bool(MARK.match(label)))


def rows_for_page(run_id, stem, chrome, controls, tokens, views):
    """The field and page rows of one page: `views` = {"a": fields, "b": fields, "c": fields} as the product listed them (None = the call failed)."""
    places = marker_places(views["b"])
    paired = pair(chrome, controls)
    rows = []
    for arm, letter in (("as_saved", "a"), ("no_declared_type", "c")):
        listed, base = views[letter] or [], views["b"] or []
        used = set()
        for i, (cf, ctrl) in enumerate(zip(chrome, paired)):
            row = {"suite": "forms", "kind": "field", "run_id": run_id, "page": stem, "arm": arm, "i": i, "chrome": cf["type"], "name": cf["name"],
                   "token": carries_token(ctrl, tokens) if ctrl else None, "join": None}
            if views[letter] is None or views["b"] is None:
                row["join"] = "no_view"
            elif ctrl is None:
                row["join"] = "no_control"
            elif ctrl["k"] not in places:
                row["join"] = "not_listed"
            else:
                j = places[ctrl["k"]]
                if j >= len(listed) or not same_field(listed[j], base[j]):
                    row["join"] = "unverified"
                else:
                    f = listed[j]
                    used.add(j)
                    row.update(join="ok", pos=j, label=f.get("label"), slot=f.get("slot"), conf=f.get("confidence"), policy=f.get("policy"),
                               src=f.get("slot_source"), learned=bool(f.get("learned")), widget=f.get("widget_class"))
            rows.append(row)
        rows.append({"suite": "forms", "kind": "page", "run_id": run_id, "page": stem, "arm": arm, "group": group(stem),
                     "listed": len(listed), "extra": [{"pos": j, "label": f.get("label"), "slot": f.get("slot"), "conf": f.get("confidence"), "policy": f.get("policy")}
                                                        for j, f in enumerate(listed) if j not in used]})
    return rows


async def _pass(ctx, brain, site, plan, letters, out):
    """One brain's pass: for each page, each copy in `letters`: goto then view. Fills out[(stem, letter)] with the field list (None on a failed call)."""
    rows = []

    async def go(sess):
        for stem, _, _ in plan:
            for letter in letters:
                url = f"{site.url}/{letter}/{stem}.html"
                got = {}
                for tool, args in (("goto", {"url": url}), ("view", {"kind": "form"})):
                    t0, t1, is_err, text = await ctx.call(sess, tool, {**args, "head": ctx.head}, 90)
                    got[tool] = (t0, t1, is_err, text)
                    ok = not is_err and ((ctx.parse(text) or {}).get("loaded") is True if tool == "goto" else _view(text) is not None)
                    rows.append({"suite": "forms", "kind": "call", "page": stem, "variant": letter, "call": tool, "wall_ms": round((t1 - t0) * 1000, 1),
                                 "start_ms": int(t0 * 1000), "end_ms": int(t1 * 1000), "bytes": len(text.encode()), "ok": ok})
                out[(stem, letter)] = _view(got["view"][3]) if rows[-1]["ok"] and rows[-2]["ok"] else None
    await ctx.connect(brain, go)
    return rows


def run(ctx, run_id, scratch, dest):
    """The whole suite: serve the three copies of every page, read them with two fresh brains (a and b; then c), build the rows.
    Answers (rows, info). `dest` holds the checked data (run.py fetched it); `ctx` carries the door's brain, MCP connection and call,
    so this file imports nothing of run.py."""
    vocab = corpus.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "forms_vocabulary.json"))
    plan = pages(dest)
    routes, parsed = {}, {}
    for stem, data, out in plan:
        text = decode(data)
        controls = Controls(text)
        parsed[stem] = (controls, chrome_fields(out))
        routes[f"/a/{stem}.html"] = data
        routes[f"/b/{stem}.html"] = encode(variant_b(text, controls))
        routes[f"/c/{stem}.html"] = encode(variant_c(text, controls))
    site = corpus_site.Site(routes)
    views, calls, seen = {}, [], []
    try:
        for letters in (("a", "b"), ("c",)):  # a fresh brain for the third copy: nothing it learned from the first can answer for it
            brain = ctx.new_brain(os.path.join(scratch, f"forms-{''.join(letters)}"), site.port)
            brain.start()
            try:
                calls += asyncio.run(_pass(ctx, brain, site, plan, letters, views))
                seen.append(ctx.observe(brain))
            finally:
                brain.stop()
    finally:
        site.stop()
    rows = [dict(r, run_id=run_id) for r in calls]
    for stem, _, _ in plan:
        controls, chrome = parsed[stem]
        rows += rows_for_page(run_id, stem, chrome, controls, set(vocab["autocomplete_tokens"]),
                              {"a": views.get((stem, "a")), "b": views.get((stem, "b")), "c": views.get((stem, "c"))})
    info = {"forms": {"vocabulary": {"map": vocab["map"], "silent": vocab["silent"]}, "served": len(site.served), "pages": len(plan),
                      "brains": [b["sha"] for b, _ in seen]},
            "brain": seen[0][0], "models": seen[0][1]}
    return rows, info
