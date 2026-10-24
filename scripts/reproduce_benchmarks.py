"""
reproduce_benchmarks.py - print the published WeaveCrawl benchmark numbers.

Reads data/official_benchmarks.json offline and prints it. It does not rerun
the benchmark; the full per-task results are in results/2026-10-24/.
"""

import json
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "official_benchmarks.json"


def main() -> None:
    data = json.loads(DATA_FILE.read_text())
    print(data["metadata"]["title"])
    print(f"{'agent':<20} {'raw':<18} {'doable':<18} {'unblocked':<18} {'minutes':<8} {'USD'}")
    for r in data["runs"]:
        cells = [f"{r[k]['passed']}/{r[k]['of']} = {r[k]['pct']}%" for k in ("raw", "doable_today", "unblocked")]
        print(f"{r['agent_model']:<20} {cells[0]:<18} {cells[1]:<18} {cells[2]:<18} "
              f"{r['wall_seconds'] / 60:<8.0f} {r['equivalent_cost_usd']}")
        print(f"  source: {r['source']}")


if __name__ == "__main__":
    main()
