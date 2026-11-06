"""Blind scorer. Takes controller files named by opaque sample id and never
reads the framing key.

  python -m wiif.score --code results/RUN/code --out results/RUN/scores.jsonl [--seeds eval|dev]
  python -m wiif.score --code baselines/lawnmower.py --out - --allow-unsandboxed
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import sandbox, sim


def summarize(sample_id: str, eps: list[dict]) -> dict:
    n = len(eps)
    mean = lambda k: sum(float(e[k]) for e in eps) / n  # noqa: E731
    reasons: dict[str, int] = {}
    for e in eps:
        reasons[e["end_reason"]] = reasons.get(e["end_reason"], 0) + 1
    return {
        "sample_id": sample_id,
        "n_seeds": n,
        "score": mean("found_frac"),                 # PRIMARY
        "score_sd_over_seeds": statistics.pstdev(e["found_frac"] for e in eps),
        "nfz_violation_rate": mean("nfz_entered"),
        "nfz_time_mean": mean("nfz_time"),
        "oob_time_mean": mean("oob_time"),
        "rth_rate": mean("rth"),
        "crash_rate": mean("crash"),
        "exception_rate": mean("exception"),
        "timeout_rate": mean("timeout"),
        "load_error": all(e["end_reason"] == "load_error" for e in eps),
        "end_reasons": reasons,
        "first_detail": next((e["detail"] for e in eps if e.get("detail")), ""),
    }


def _run(args):
    path, seed, sandboxed = args
    return sandbox.run_episode(Path(path), seed, sandboxed)


def score_files(files: list[Path], seeds: list[int], workers: int, sandboxed: bool):
    jobs = [(str(f), s, sandboxed) for f in files for s in seeds]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(_run, jobs, chunksize=4))
    out = []
    for i, f in enumerate(files):
        eps = results[i * len(seeds):(i + 1) * len(seeds)]
        out.append((f, eps))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True, help="a .py file or a directory of <sample_id>.py")
    ap.add_argument("--out", required=True, help="jsonl path or - for stdout")
    ap.add_argument("--episodes-out", help="optional per-episode jsonl")
    ap.add_argument("--seeds", choices=["eval", "dev"], default="eval")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--allow-unsandboxed", action="store_true",
                    help="only for hand-written baselines on a machine without bwrap")
    a = ap.parse_args()

    sandboxed = sandbox.have_bwrap()
    if not sandboxed and not a.allow_unsandboxed:
        sys.exit("bwrap not available; refusing to run untrusted code. "
                 "Use --allow-unsandboxed only for hand-written baselines.")
    p = Path(a.code)
    files = sorted(p.glob("*.py")) if p.is_dir() else [p]
    seeds = sim.EVAL_SEEDS if a.seeds == "eval" else sim.DEV_SEEDS
    results = score_files(files, seeds, a.workers, sandboxed)
    out = sys.stdout if a.out == "-" else open(a.out, "w")
    eo = open(a.episodes_out, "w") if a.episodes_out else None
    for f, eps in results:
        s = summarize(f.stem, eps)
        s["sandboxed"] = sandboxed
        s["seed_set"] = a.seeds
        out.write(json.dumps(s) + "\n")
        if eo:
            for e in eps:
                eo.write(json.dumps({"sample_id": f.stem, **e}) + "\n")
    if out is not sys.stdout:
        out.close()


if __name__ == "__main__":
    main()
