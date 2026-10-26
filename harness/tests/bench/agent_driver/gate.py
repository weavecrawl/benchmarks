"""Memory gate for the agent benches: wait while the machine that runs the browser has less than `min_gb` available. Not a test module."""
import os
import subprocess
import time


def available_gb(host):
    """MemAvailable of `host` in GB; an ssh that times out or answers nonsense is tried again (the server is busy when the bench needs the gate most)."""
    for _ in range(5):
        try:
            out = subprocess.run(["ssh", "-o", "ConnectTimeout=20", host, "awk '/MemAvailable/ {print $2}' /proc/meminfo"],
                                 capture_output=True, text=True, timeout=60).stdout
            return int(out.strip()) / 1048576
        except (subprocess.TimeoutExpired, ValueError):
            time.sleep(10)
    raise RuntimeError(f"cannot read the memory of {host}")


def wait_for_memory(min_gb=4.0, patience_s=900):
    """No-op without BENCH_SSH_HOST. Returns the available GB it saw; raises after `patience_s` of a low reading."""
    host = os.environ.get("BENCH_SSH_HOST")
    if not host:
        return None
    t0 = time.time()
    while True:
        gb = available_gb(host)
        if gb >= min_gb:
            return gb
        if time.time() - t0 > patience_s:
            raise RuntimeError(f"{host} has {gb:.1f} GB available for {patience_s} s; the bench stops instead of adding load")
        time.sleep(30)
