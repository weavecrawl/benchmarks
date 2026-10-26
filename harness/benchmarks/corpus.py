"""The public data of the corpus suites: fetched from its source, pinned by commit, every file checked against a lock.

    python3 corpus.py lock [NAME ...]      download the pinned source and write benchmarks/corpora.lock.json (the only writer of the lock)
    python3 corpus.py fetch NAME DIR       make DIR hold exactly the locked files of NAME, downloading what is missing; refuses on a hash
                                           that differs from the lock

Why a lock and not a copy of the data: the pages are third-party snapshots (checkout pages of shops, news pages), so the repository
holds their sha256 only. A run downloads them from the source named in `corpora.json`, and a file whose bytes differ from the lock
(a rewritten history, a CDN that changed a byte) stops the run before any number is made. No answer is written here: the expected
values are read out of the pinned files themselves by the suites.

Stdlib only; the run and the gate read it without a bench dependency.
"""
import gzip
import hashlib
import io
import json
import os
import sys
import tarfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CORPORA = os.path.join(HERE, "corpora.json")
LOCK = os.path.join(HERE, "corpora.lock.json")
UA = "bench-corpus/1 (+public data, pinned by commit)"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(data):
    """The git object id of a file's bytes: ties a GitHub file to the commit's tree without trusting the transport."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _get(url, tries=4):
    for n in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                return r.read()
        except OSError:
            if n == tries - 1:
                raise
            time.sleep(2 * (n + 1))


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _tar_files(data):
    """{relative path: bytes} of the regular files of a tar.gz, read in memory; a path that leaves the archive is refused."""
    out = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
        for m in t.getmembers():
            if not m.isfile():
                continue
            if m.name.startswith(("/", "..")) or ".." in m.name.split("/"):
                raise ValueError(f"archive member leaves the archive: {m.name!r}")
            out[m.name] = t.extractfile(m).read()
    return out


def _wanted(path, take):
    return any(path == t or (t.endswith("/") and path.startswith(t)) for t in take)


def _download(name, spec, paths=None):
    """{path: bytes, git blob id or None} for one corpus from its source. `paths` limits a `files` corpus to those paths."""
    if spec["kind"] == "tar.gz":
        archive = _get(spec["source"].format(commit=spec["commit"]))
        return {p: (b, None) for p, b in sorted(_tar_files(archive).items())}
    tree = json.loads(_get(spec["tree"].format(repo=spec["repo"], commit=spec["commit"])))
    if tree.get("truncated"):
        raise RuntimeError(f"{name}: the tree listing of {spec['commit']} is truncated")
    listed = {e["path"]: e["sha"] for e in tree["tree"] if e["type"] == "blob" and _wanted(e["path"], spec["take"])}
    out = {}
    for p in sorted(listed if paths is None else paths):
        out[p] = (_get(spec["source"].format(repo=spec["repo"], commit=spec["commit"], path=p)), listed.get(p))
    return out


def lock(names=None):
    """Download each pinned source and write the lock: sha256 and size of every file, the git blob id where the source has one."""
    spec = load(CORPORA)
    names = names or [k for k in spec if isinstance(spec[k], dict)]
    locked = load(LOCK) if os.path.isfile(LOCK) else {}
    for name in names:
        files = {}
        for path, (data, blob) in _download(name, spec[name]).items():
            if blob and git_blob(data) != blob:
                raise RuntimeError(f"{name}: {path} does not match its git object id {blob}")
            files[path] = {"sha256": sha256(data), "bytes": len(data), **({"git_blob": blob} if blob else {})}
        locked[name] = {"commit": spec[name]["commit"], "licence": spec[name]["licence"], "files": files}
        print(f"{name}: {len(files)} files locked at {spec[name]['commit']}")
    with open(LOCK, "w", encoding="utf-8") as f:
        f.write(json.dumps(locked, indent=1, sort_keys=True) + "\n")


def digest(entry):
    """One hash for a locked corpus: its commit and every `path sha256` line, so env.json names the data without listing it."""
    lines = [entry["commit"]] + [f"{p} {v['sha256']}" for p, v in sorted(entry["files"].items())]
    return sha256("\n".join(lines).encode())


def fetch(name, dest):
    """Make `dest` hold the locked files of `name`: reuse a file whose hash is right, download the rest, refuse a wrong hash.
    Answers the lock entry (path -> hash) the run records."""
    spec, locked = load(CORPORA)[name], load(LOCK)
    entry = locked.get(name)
    if not entry or entry["commit"] != spec["commit"]:
        raise RuntimeError(f"{name}: corpora.lock.json is not of the pinned commit {spec['commit']}; run `python3 corpus.py lock {name}`")
    missing = []
    for path, want in entry["files"].items():
        target = os.path.join(dest, path)
        if os.path.isfile(target):
            with open(target, "rb") as f:
                if sha256(f.read()) == want["sha256"]:
                    continue
        missing.append(path)
    if missing:
        got = _download(name, spec, None if spec["kind"] == "tar.gz" else missing)
        for path in missing:
            data = got[path][0] if path in got else None
            if data is None or sha256(data) != entry["files"][path]["sha256"]:
                raise RuntimeError(f"{name}: {path} from the source differs from the lock (the source changed, or the download is damaged)")
            target = os.path.join(dest, path)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(data)
    return entry


def read(dest, path):
    with open(os.path.join(dest, path), "rb") as f:
        return f.read()


def gunzip(data):
    return gzip.decompress(data)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "lock":
        lock(sys.argv[2:] or None)
    elif len(sys.argv) == 4 and sys.argv[1] == "fetch":
        e = fetch(sys.argv[2], sys.argv[3])
        print(f"{sys.argv[2]}: {len(e['files'])} files ok, digest {digest(e)}")
    else:
        sys.exit(__doc__)
