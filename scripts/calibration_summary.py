"""Pooled (framing-blind) mean score per model for a calibration batch.
usage: python scripts/calibration_summary.py results/calibration_v2 > results/calibration_v2/summary.md"""
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1])
print(f"# Calibration summary: {root.name}\n")
print("Pooled over all framings; mean and median of per-sample score (mean over the eval layouts).\n")
print("| model | n | mean | median | sd | min | max | nfz_violation_rate | rth_rate |")
print("|---|---|---|---|---|---|---|---|---|")
for d in sorted(p for p in root.iterdir() if (p / "scores.jsonl").exists()):
    rows = [json.loads(line) for line in (d / "scores.jsonl").read_text().splitlines()]
    s = [r["score"] for r in rows]
    m = lambda k: statistics.mean(r[k] for r in rows)  # noqa: E731
    print(f"| {d.name} | {len(s)} | {statistics.mean(s):.3f} | {statistics.median(s):.3f} | "
          f"{statistics.pstdev(s):.3f} | {min(s):.3f} | {max(s):.3f} | "
          f"{m('nfz_violation_rate'):.2f} | {m('rth_rate'):.2f} |")
