"""The pages suite: how well the product reads 181 saved real article pages, scored by the benchmark's own public scorer.

Data: Scrapinghub's article-extraction-benchmark at a pinned commit (corpora.json): 181 saved pages (html/<id>.html.gz), the true article
body of each (ground-truth.json) and `evaluate.py`, the scorer its published table was made with. The scorer is not copied: the file is
fetched with the data, checked against the lock and imported, so the arithmetic is theirs. Each page is served from loopback and
looked at through the MCP: `read(url)` (what an agent gets for an address), `goto` then `read(level="full")` (the whole page, every
part) and the cheap looks (`read` outline, `view`) for their cost.

What is scored, and what is not: before an earlier change `read` kept all the visible text of a page, so its rows were those of the whole-page text
dumps (html-text) and precision was what fell. Since then `read` answers an article's main text, and its rows are next to readability and
trafilatura; a page that is not an article is still read whole. The text is scored as the benchmark's human labelled it: a byline or a caption
that `read` keeps is a miss in precision. `scripts/bench/main_text_score.py` is the quick score of the picker alone, on a split fixed before tuning.
Next to the product the summary prints, scored by the same function on the same pages: the page's own text with the markup removed, the page title
alone (the stubs), and the published output of five other extractors, whose scores must come out as the
repository's README table says (checked in this run, or the run is refused).

Tokens are counted with the door's tokenizer on the answer, on the page's HTML and on the true text. Latency is the client wall time of
one call on the loopback server: no network is in it.
"""
import asyncio
import gzip
import importlib.util
import json
import os
import pathlib
import re
import statistics
import sys

import corpus
import corpus_site

NAME = "article_extraction"
LOOKS = ("read_url", "goto", "read_outline", "read_full", "view")
SCORED = ("read_url", "read_full")
BASELINES = ("html_text", "title")  # the stubs, scored by the same function: the page's text without markup, and its title alone (an empty answer cannot be scored by the benchmark: no page has a word to count)
REFERENCE = ("html-text", "readability", "readability_js", "go_trafilatura", "dragnet")  # published outputs of other extractors, scored again here as a check of the scorer; chosen because the README table at the pinned commit gives exactly the numbers their files score (its trafilatura and inscriptis rows are older than their output files)
PART_CAP = 60  # a look that covers the whole page follows its parts; a page of more than this many is not read whole


def load_scorer(dest):
    """The benchmark's own evaluate.py, imported from the checked file."""
    spec = importlib.util.spec_from_file_location("article_extraction_evaluate", os.path.join(dest, "evaluate.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def published_table(readme):
    """{extractor: {f1, precision, recall, accuracy}} from the README's results block, read as text (`name version F1 ± e P ± e R ± e A ± e`)."""
    out = {}
    pat = re.compile(r"^\s{2,}(\S+)\s+(\S+)\s+([\d.]+) ± [\d.]+\s+([\d.]+) ± [\d.]+\s+([\d.]+) ± [\d.]+\s+([\d.]+) ± [\d.]+\s*$")
    for line in readme.split("\n"):
        m = pat.match(line)
        if m:
            out[m.group(1)] = {"version": m.group(2), "f1": float(m.group(3)), "precision": float(m.group(4)), "recall": float(m.group(5)), "accuracy": float(m.group(6))}
    return out


def pages(dest):
    """[(id, html text, true article body, url)] in the order of ground-truth.json sorted by id; a page without its truth stops the run."""
    truth = json.loads(corpus.read(dest, "ground-truth.json"))
    out = []
    for pid in sorted(truth):
        html = gzip.decompress(corpus.read(dest, f"html/{pid}.html.gz")).decode("utf-8", "surrogateescape")
        out.append((pid, html, truth[pid].get("articleBody", ""), truth[pid].get("url")))
    return out


def repeats(look, reps, url_reps):
    """How many times a look is taken: `read(url)` is a plain fetch and is repeated; the browser looks wait for the page to settle (1.6 to 1.7 s each) and are taken `reps` times."""
    return url_reps if look == "read_url" else reps


def expected(dest, reps, url_reps):
    n = len(json.loads(corpus.read(dest, "ground-truth.json")))
    return {"looks": n * sum(repeats(look, reps, url_reps) for look in LOOKS), "base": n * len(BASELINES), "pages": n}


def answer_text(text):
    """The words of a `read` answer, without the envelope (url, title, part numbers): the `content` of an address read, the `markdown` of an open page.
    Anything that is not such an answer is scored as it is, so a broken tool cannot hide behind a field that is not there."""
    try:
        parsed = json.loads(text)
    except ValueError:
        return text
    if isinstance(parsed, dict):
        for key in ("content", "markdown", "text"):
            if isinstance(parsed.get(key), str):
                return parsed[key]
    return text


REF = re.compile(r"\[n\d+\]")


def title_of(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def score(scorer, true, pred):
    tp, fp, fn = scorer.string_shingle_matching(true=true, pred=pred)
    return {"tp": tp, "fp": fp, "fn": fn, "acc": scorer.get_accuracy(true=true, pred=pred)}


def public_metrics(scorer, truth, preds):
    """The benchmark's own `evaluate` over {page id: article body} for the pages in `preds`: f1, precision, recall, accuracy (no bootstrap: that is for the +- and uses chance)."""
    try:
        m = scorer.evaluate({k: {"articleBody": truth[k]} for k in preds}, {k: {"articleBody": v} for k, v in preds.items()}, 0)
    except ZeroDivisionError:  # precision and recall are both 0 (an answer that shares no four words with any article): the benchmark's F1 is 0 / 0
        return {"f1": 0.0, "precision": 0.0, "recall": 0.0, "accuracy": statistics.mean(scorer.get_accuracy(true=truth[k], pred=v) for k, v in preds.items())}
    return {k: m[k] for k in ("f1", "precision", "recall", "accuracy")}


def reference(scorer, dest, truth):
    """The published outputs of other extractors scored by this run's copy of the scorer, next to the README table they came from."""
    out = {}
    for name in REFERENCE:
        pred, version = scorer.load_prediction(pathlib.Path(dest, "output", f"{name}.json"))
        out[name] = {"version": version, **public_metrics(scorer, truth, {k: v.get("articleBody", "") for k, v in pred.items()})}
    return out


def run(ctx, run_id, scratch, dest, reps, url_reps):
    """The whole suite: every page served from loopback and looked at through one brain (`read(url)` `url_reps` times, the browser looks `reps` times); the stubs scored beside it.
    Answers (rows, info)."""
    import tiktoken
    enc = tiktoken.get_encoding(ctx.tokenizer)
    scorer = load_scorer(dest)
    plan = pages(dest)
    truth = {pid: body for pid, _, body, _ in plan}
    refused = set()
    rows, preds, keep = [], {"read_url": {}, "read_full": {}, "html_text": {}, "title": {}}, open(os.path.join(scratch, "pages.jsonl"), "w", encoding="utf-8")
    for pid, html, body, _ in plan:
        text = ctx.plain_text(html)
        rows.append({"suite": "pages", "kind": "page", "run_id": run_id, "page": pid, "html_bytes": len(html.encode("utf-8", "surrogateescape")),
                     "html_tokens": len(enc.encode(html, disallowed_special=())), "text_tokens": len(enc.encode(text, disallowed_special=())),
                     "truth_tokens": len(enc.encode(body, disallowed_special=()))})
        for arm, pred in (("html_text", text), ("title", title_of(html))):
            preds[arm][pid] = pred
            rows.append({"suite": "pages", "kind": "base", "run_id": run_id, "page": pid, "arm": arm, **score(scorer, body, pred)})
    site = corpus_site.Site({f"/p/{pid}.html": (html.encode("utf-8", "surrogateescape"), "text/html; charset=utf-8") for pid, html, _, _ in plan})
    brain = ctx.new_brain(os.path.join(scratch, "pages-brain"), site.port)
    brain.start()
    calls = {"read_url": {"tool": "read", "covers": "page"}, "goto": {"tool": "goto", "covers": "receipt"}, "read_outline": {"tool": "read", "covers": "outline"},
             "read_full": {"tool": "read", "covers": "page", "args": {"level": "full"}}, "view": {"tool": "view", "covers": "controls"}}

    async def go(sess):
        for rep in range(max(reps, url_reps)):
            for pid, _, body, _ in plan:
                url = f"{site.url}/p/{pid}.html"
                refused.discard(pid)
                for name in LOOKS:
                    if rep >= repeats(name, reps, url_reps):
                        continue
                    c = calls[name]
                    args = {"url": url} if name in ("read_url", "goto") else {}
                    args.update(c.get("args", {}))
                    args["head"] = ctx.head
                    got = await ctx.look(sess, {"tool": c["tool"], "covers": c["covers"]}, args, enc)
                    row = {"suite": "pages", "kind": "look", "run_id": run_id, "rep": rep, "page": pid, "look": name, "covers": c["covers"], "wall_ms": got["ms"],
                           "start_ms": int(got["start"] * 1000), "end_ms": int(got["end"] * 1000), "tokens": got["tokens"], "bytes": got["bytes"], "parts": got["parts"],
                           "complete": got["complete"], "ok": not got["is_error"] and got["complete"]}
                    if name == "goto":
                        shown = ctx.parse(got["texts"][0][2]) or {}
                        row["ok"] = row["ok"] and shown.get("loaded") is True
                        row["reason"] = shown.get("reason")
                        if shown.get("loaded") is not True and shown.get("reason") == "url_blocked":
                            refused.add(pid)  # the page's own script sent the tab away from the saved page; what `read` and `view` then show is not the page
                    if pid in refused and name != "goto":
                        row["refused"] = True  # counted and printed, never scored: the tab is not on the page
                    if name in SCORED:
                        answer = "\n".join(answer_text(t) for _, _, t in got["texts"])
                        row["ok"] = row["ok"] and bool(answer.strip())
                        row["text_sha"] = corpus.sha256(REF.sub("", answer).encode("utf-8", "surrogateescape"))  # the `[n12]` ref numbers count up on every load of a page; the words must be the same
                        row.update(score(scorer, body, answer))
                        if rep == 0 and not row.get("refused"):
                            preds[name][pid] = answer
                        keep.write(json.dumps({"rep": rep, "page": pid, "look": name, "text": answer}) + "\n")
                    rows.append(row)
    try:
        asyncio.run(ctx.connect(brain, go))
        observed = ctx.observe(brain)
    finally:
        brain.stop()
        site.stop()
        keep.close()
    published = published_table(corpus.read(dest, "README.rst").decode("utf-8"))
    info = {"pages": {"count": len(plan), "reps": reps, "url_reps": url_reps, "public_scorer": {arm: public_metrics(scorer, truth, p) for arm, p in preds.items()},
                      "reference": reference(scorer, dest, truth), "published": {k: v for k, v in published.items() if k in REFERENCE}, "served": len(site.served)},
            "brain": observed[0], "models": observed[1]}
    return rows, info
