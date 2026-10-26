"""Was the machine quiet while the bench measured? Read from the kernel, never assumed.

A bench number is only the product's when nothing else slowed the call. On bench-server other jobs share `work.slice`; when
the slice hits its `memory.high` or its cpu quota the kernel throttles every job in it, and a call that took 200 ms takes
20 s (13 such stalls sat in the first committed run's p95 with nothing to say so). The kernel counts those events:
`memory.events` `high` and `cpu.stat` `nr_throttled`, cumulative, per cgroup. A counter that is the same before and after a
call proves no throttle event fell inside it, whatever the sample spacing.

    Sampler        a thread: reads the counters of the job's cgroup chain every 250 ms, keeps the rows that matter
    preflight      the numbers that decide whether a run may start at all
    levels         the job's cgroup and every parent up to the root (also what `run.machine()` reads the job cap from)

Stdlib only, so the gate can load it. Rows: {"suite": "machine", "run_id", "t_ms" (epoch ms, the clock of the runner's
start_ms/end_ms), "mem_high", "cpu_throttled", "mem_psi_us", "cpu_psi_us", "io_psi_us", "load1"}; the first six counters are
sums over the chain, cumulative since boot.
"""
import os
import threading
import time

CGROUP = "/sys/fs/cgroup"
EVERY_S = 0.25
HEARTBEAT = 10  # a row is kept every 10th sample (2.5 s) even when nothing changed: it carries the pressure and load figures
MAX_PSI_AVG10 = 1.0  # memory pressure ("some", % of the last 10 s) above which a run does not start
MAX_CPU_PSI_AVG10 = 5.0  # the same for cpu: a saturated slice leaves tasks waiting for a quota that load average does not show
SETTLE_S = 2.0  # the door reads the throttle counters twice this far apart: a counter that moves means a neighbour is being throttled now
COUNTERS = ("mem_high", "cpu_throttled", "mem_psi_us", "cpu_psi_us", "io_psi_us")
EDGE = ("mem_high", "cpu_throttled")  # the two counters a throttled call is decided on


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def levels(root=CGROUP, proc_cgroup="/proc/self/cgroup"):
    """The folders of this process's cgroup and of every parent below `root` (the job cap sits on a parent slice, not on the job's unit)."""
    cg = (_read(proc_cgroup) or "").splitlines()
    d = (root + cg[0].split(":", 2)[2]).rstrip("/") if cg and cg[0].startswith("0::") else None
    out = []
    while d and d != root and len(d) > len(root):
        out.append(d)
        d = os.path.dirname(d)
    return out


def labels(dirs, root=CGROUP):
    """The level names for env.json. The job's own unit is not named: work-run puts the task name in it, and a task name can carry the
    product name into a committed file (the name gate); its parents (work.slice) are named."""
    return ["(the job's own unit)" if i == 0 else os.path.relpath(d, root) for i, d in enumerate(dirs)]


def peaks(dirs, root=CGROUP):
    """memory.peak in MB of the job's own unit (level 0), where the kernel has it: how near the job came to the slice's memory.high (a job
    that fills the cap throttles itself, and the run is refused for it). The parents' peak counts since the slice was created, so it
    says nothing about this run and is not read."""
    out = {}
    for name, d in list(zip(labels(dirs, root), dirs))[:1]:
        v = (_read(f"{d}/memory.peak") or "").strip()
        if v.isdigit():
            out[name] = round(int(v) / 1048576)
    return out


def _kv(text, key):
    for ln in (text or "").splitlines():
        parts = ln.split()
        if len(parts) == 2 and parts[0] == key:
            return int(parts[1])
    return None


def _psi(text):
    """('some avg10=0.00 avg60=.. avg300=.. total=N') -> (avg10, total in microseconds); (None, None) when the file is missing."""
    for ln in (text or "").splitlines():
        if ln.startswith("some "):
            f = dict(p.split("=") for p in ln.split()[1:])
            return float(f["avg10"]), int(f["total"])
    return None, None


def cpu_list(spec):
    """'2-7,10-15' -> [2, 3, ..., 7, 10, ..., 15]."""
    out = []
    for part in (spec or "").strip().split(","):
        if part.strip():
            lo, _, hi = part.partition("-")
            out += range(int(lo), int(hi or lo) + 1)
    return out


def isolation(dirs):
    """Whether the job runs in a `work-run` slot: its own unit has a cpuset narrower than its parent's and a memory cap of its own. Then the
    cores are its alone and the other units beside it cannot take its cpu or its memory. Answers {cpuset, slice_cpuset, memory_max_mb,
    other_units (how many other work units sit beside it now)}, else None. No unit name is read out: a task name can carry the product name."""
    if len(dirs) < 2:
        return None
    own, parent = (_read(f"{dirs[0]}/cpuset.cpus.effective") or "").strip(), (_read(f"{dirs[1]}/cpuset.cpus.effective") or "").strip()
    cap = (_read(f"{dirs[0]}/memory.max") or "").strip()
    if not own or not parent or own == parent or not cap.isdigit():
        return None
    try:
        units = [n for n in os.listdir(dirs[1]) if n.startswith("work-") and n.endswith(".service")]
    except OSError:
        units = []
    return {"cpuset": own, "slice_cpuset": parent, "memory_max_mb": int(cap) // 1048576, "other_units": max(0, len(units) - 1)}


def _cpu_times(cpus, stat="/proc/stat"):
    """(idle, total) jiffies summed over `cpus`, from /proc/stat."""
    idle = total = 0
    want = {f"cpu{c}" for c in cpus}
    for ln in (_read(stat) or "").splitlines():
        f = ln.split()
        if f and f[0] in want:
            v = [int(x) for x in f[1:9]]
            idle += v[3] + v[4]
            total += sum(v)
    return idle, total


def read(dirs, own_psi=False):
    """The counters summed over `dirs`, plus the highest memory pressure avg10 seen on any of them (on the job's own unit alone when `own_psi`:
    in a slot the parent's pressure is the sum of every neighbour's stalls, which cannot slow this job). `memory.events.local` is read where it
    exists: `memory.events` of a parent counts the events of every unit under it, and another unit throttling itself at its own cap is not a
    throttle of this job. None when no folder has a readable `memory.events`: then nothing can prove the machine quiet."""
    tot = dict.fromkeys(COUNTERS, 0)
    avg10 = {"memory": 0.0, "cpu": 0.0}
    seen = dict.fromkeys(("memory.events", "nr_throttled", "pressure"), False)
    for i, d in enumerate(dirs):
        local = _read(f"{d}/memory.events.local")
        high = _kv(local if local is not None else _read(f"{d}/memory.events"), "high")
        thr = _kv(_read(f"{d}/cpu.stat"), "nr_throttled")
        seen["memory.events"] |= high is not None
        seen["nr_throttled"] |= thr is not None
        tot["mem_high"] += high or 0
        tot["cpu_throttled"] += thr or 0
        for key, name in (("mem_psi_us", "memory"), ("cpu_psi_us", "cpu"), ("io_psi_us", "io")):
            a, t = _psi(_read(f"{d}/{name}.pressure"))
            tot[key] += t or 0
            if name in avg10 and a is not None and not (own_psi and i > 0):
                avg10[name] = max(avg10[name], a)
                seen["pressure"] |= name == "memory"
    # a counter nobody could read sums to 0, which is what a quiet machine looks like: so nothing readable is not a reading
    return {**tot, "mem_avg10": avg10["memory"], "cpu_avg10": avg10["cpu"]} if all(seen.values()) else None


def compact(rows, heartbeat=HEARTBEAT):
    """Keep the first and last row, every row where a throttle counter differs from its neighbour on either side, and every
    `heartbeat`-th row. Counters only grow, so two kept rows with equal throttle counters prove nothing fell between them:
    dropping the rows in between loses no event and keeps raw.json small (a 40 min run is ~10 000 samples)."""
    key = lambda r: tuple(r[k] for k in EDGE)  # noqa: E731
    last = len(rows) - 1
    return [r for i, r in enumerate(rows)
            if i in (0, last) or i % heartbeat == 0 or key(r) != key(rows[i - 1]) or key(r) != key(rows[i + 1])]


class Sampler:
    """Sample the job's cgroup chain on a thread from `start()` to `stop()`; `stop()` answers the kept rows."""

    def __init__(self, run_id, dirs=None, every=EVERY_S):
        self.run_id, self.dirs, self.every = run_id, levels() if dirs is None else dirs, every
        self.own_psi = isolation(self.dirs) is not None
        self._rows, self._halt, self._thread = [], threading.Event(), None

    def _take(self):
        c = read(self.dirs, self.own_psi)
        if c is not None:
            self._rows.append({"suite": "machine", "run_id": self.run_id, "t_ms": int(time.time() * 1000), "load1": round(os.getloadavg()[0], 2),
                               **{k: c[k] for k in COUNTERS}})

    def start(self):
        self._take()  # one before the first call, so the first call has a sample on its left
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._halt.wait(self.every):
            self._take()

    def stop(self):
        self._halt.set()
        if self._thread:
            self._thread.join()
        self._take()  # and one after the last call
        return compact(self._rows)


def cpu_quota(dirs):
    """CPUs the chain's first `cpu.max` allows (quota / period), None when none sets a quota: work.slice holds 6 of the host's 16."""
    for d in dirs:
        parts = (_read(f"{d}/cpu.max") or "").split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit() and int(parts[1]):
            return int(parts[0]) / int(parts[1])
    return None


MAX_OWN_CPU_BUSY = 25.0  # % busy of a slot's own cores during the door's look: they are the job's alone, so anything running there is not the bench


def preflight(dirs=None, cpus=None, settle=SETTLE_S, sleep=time.sleep, stat="/proc/stat"):
    """What the machine is like right now, and the reasons a run must not start on it (`busy`, empty: it may). The CPU count is the job's
    quota when the chain has one. The throttle counters are read twice, `settle` seconds apart: load average does not show a slice that is
    full (throttled tasks leave the run queue), a moving counter does."""
    dirs = levels() if dirs is None else dirs
    iso = isolation(dirs)
    quota = cpu_quota(dirs)
    cpus = cpus or min(os.cpu_count() or 1, quota or 1e9)
    cpus = int(cpus) if float(cpus).is_integer() else cpus
    c = read(dirs, iso is not None)
    load1 = round(os.getloadavg()[0], 2)
    why = []
    mine = cpu_list(iso["cpuset"]) if iso else []
    before = _cpu_times(mine, stat) if iso else None
    if c is None:
        why.append("the cgroup counters (memory.events, cpu.stat nr_throttled, memory.pressure) cannot all be read here: nothing could prove the machine quiet")
    else:
        sleep(settle)
        again = read(dirs, iso is not None)
        moved = {k: again[k] - c[k] for k in EDGE if again and again[k] != c[k]}
        if moved:
            why.append(f"the kernel throttled this slice during the last {settle:g} s ({', '.join(f'{k} +{v}' for k, v in moved.items())}): a neighbour is running")
        if c["mem_avg10"] > MAX_PSI_AVG10:
            why.append(f"memory pressure (some avg10) is {c['mem_avg10']} > {MAX_PSI_AVG10}")
        if c["cpu_avg10"] > MAX_CPU_PSI_AVG10:
            why.append(f"cpu pressure (some avg10) is {c['cpu_avg10']} > {MAX_CPU_PSI_AVG10}")
    if iso:  # the host's load average is mostly the neighbours' cores; this job's own cores are what must be idle
        idle, total = (b - a for a, b in zip(before, _cpu_times(mine, stat)))
        busy = round(100 * (1 - idle / total), 1) if total else 0.0
        if busy > MAX_OWN_CPU_BUSY:
            why.append(f"the job's own cores ({iso['cpuset']}) are {busy} % busy > {MAX_OWN_CPU_BUSY:g} % before it started")
    elif load1 > cpus / 2:
        why.append(f"load average {load1} > {cpus / 2:g} (half of {cpus:g} CPUs)")
    return {"mem_psi_avg10": None if c is None else c["mem_avg10"], "load1": load1, "cpus": cpus, "busy": why, "isolation": iso}
