"""Cross-model comparison (PLAN.md, "Cross-model comparison"): does a framing gap
in a Chinese-developed model differ from the same gap in the control model?

  python -m wiif.compare --control results/main_gptoss \
      --model results/main_qwen30b --model results/main_dsv2lite

For each model M and each primary contrast c: DiD = gap_M(c) - gap_control(c).
95% percentile bootstrap CI (10,000 resamples, each model x framing arm resampled
independently); two-sided bootstrap p; Holm across all (model, contrast) pairs.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from .analyze import CONFIRMATORY, NOISE, B, group, holm, load


def _arms(key, zero_fill):
    arms = {}
    for f, g in CONFIRMATORY + [NOISE]:
        for x in (f, g):
            arms[x] = group(key, x, zero_fill=zero_fill)
    return arms


def _boot_gap(arms, f, g, rng):
    x, y = arms[f], arms[g]
    return rng.choice(x, (B, len(x))).mean(1) - rng.choice(y, (B, len(y))).mean(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", required=True)
    ap.add_argument("--model", action="append", required=True)
    ap.add_argument("--zero-fill", action="store_true", help="sensitivity: refusals/non-code = 0")
    ap.add_argument("--out")
    a = ap.parse_args()
    rng = np.random.default_rng(54321)
    ctrl = _arms(load(Path(a.control)), a.zero_fill)
    rows = []
    for m in a.model:
        arms = _arms(load(Path(m)), a.zero_fill)
        for f, g in CONFIRMATORY + [NOISE]:
            d_m = arms[f].mean() - arms[g].mean()
            d_c = ctrl[f].mean() - ctrl[g].mean()
            boot = _boot_gap(arms, f, g, rng) - _boot_gap(ctrl, f, g, rng)
            lo, hi = np.percentile(boot, [2.5, 97.5])
            p = min(1.0, 2 * min((boot <= 0).mean(), (boot >= 0).mean()) + 1 / B)
            rows.append([Path(m).name, f"{f} − {g}", d_m, d_c, d_m - d_c, lo, hi, p,
                         (f, g) != NOISE])
    conf = [i for i, r in enumerate(rows) if r[8]]
    adj = holm([rows[i][7] for i in conf])
    hp = {i: adj[k] for k, i in enumerate(conf)}
    L = [f"# Cross-model comparison vs control `{Path(a.control).name}`"
         + (" (refusals/non-code scored 0)" if a.zero_fill else "") + "\n",
         "| model | contrast | gap (model) | gap (control) | difference | 95% CI | p | Holm p |",
         "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows):
        L.append(f"| {r[0]} | {r[1]} | {r[2]:+.3f} | {r[3]:+.3f} | {r[4]:+.3f} | "
                 f"[{r[5]:+.3f}, {r[6]:+.3f}] | {r[7]:.3f} | "
                 + (f"{hp[i]:.3f}" if i in hp else "(noise floor)") + " |")
    text = "\n".join(L) + "\n"
    if a.out:
        Path(a.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
