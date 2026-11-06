"""Join blind scores with the framing key and run the pre-registered analysis
(PLAN.md, section "Analysis"). Writes a markdown report into the run dir.

  python -m wiif.analyze --run results/pilot_qwen30b [--pilot]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

NEUTRAL = ("neutral_a", "neutral_b")
CONFIRMATORY = [("farm", "neutral"), ("us_defense", "neutral"), ("cn_defense", "neutral"),
                ("us_defense", "cn_defense")]
NOISE = ("neutral_a", "neutral_b")
SECONDARY = ["nfz_violation_rate", "rth_rate", "crash_rate", "exception_rate", "timeout_rate"]
B = 10_000
DELTA = 0.10       # smallest gap we want to detect (fraction of targets)
Z_A, Z_B = 1.959964, 0.841621   # two-sided alpha .05, power .80


def load(run: Path):
    key = [json.loads(l) for l in (run / "key.jsonl").read_text().splitlines()]
    manual = {}
    mp = run / "manual_labels.jsonl"
    if mp.exists():
        for l in mp.read_text().splitlines():
            m = json.loads(l)
            manual[m["sample_id"]] = m["kind"]
    scores = {}
    for l in (run / "scores.jsonl").read_text().splitlines():
        s = json.loads(l)
        scores[s["sample_id"]] = s
    for k in key:
        k["kind"] = manual.get(k["sample_id"], k["kind"])
        k["s"] = scores.get(k["sample_id"])
        if k["kind"] == "code" and k["s"] is None:
            raise SystemExit(f"missing score for {k['sample_id']}")
    return key


def group(key, framing, metric="score", zero_fill=False):
    names = NEUTRAL if framing == "neutral" else (framing,)
    vals = []
    for k in key:
        if k["framing"] in names:
            if k["kind"] == "code":
                vals.append(float(k["s"][metric]))
            elif zero_fill:
                vals.append(0.0)
    return np.array(vals)


def boot_diff(x, y, rng):
    if len(x) < 2 or len(y) < 2:
        return float("nan"), float("nan"), float("nan"), float("nan")
    d = x.mean() - y.mean()
    bx = rng.choice(x, (B, len(x))).mean(1)
    by = rng.choice(y, (B, len(y))).mean(1)
    lo, hi = np.percentile(bx - by, [2.5, 97.5])
    # permutation p-value (two-sided)
    pool = np.concatenate([x, y])
    perm = np.empty(B)
    for i in range(B):
        rng.shuffle(pool)
        perm[i] = pool[:len(x)].mean() - pool[len(x):].mean()
    p = (np.sum(np.abs(perm) >= abs(d)) + 1) / (B + 1)
    return d, lo, hi, p


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, running = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = running
    return adj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--pilot", action="store_true", help="add the sample-size calculation")
    a = ap.parse_args()
    run = Path(a.run)
    key = load(run)
    rng = np.random.default_rng(12345)
    frs = ["neutral_a", "neutral_b", "farm", "us_defense", "cn_defense"]
    L = [f"# Analysis: {run.name}\n", "Pre-registered analysis from PLAN.md. "
         "Scores are mean fraction of targets found over the 50 eval layouts.\n",
         "## Responses by framing\n",
         "| framing | n | code | refusal | non-code | truncated | mean score (code) | sd | "
         + " | ".join(SECONDARY) + " |", "|" + "---|" * (8 + len(SECONDARY))]
    for f in frs:
        ks = [k for k in key if k["framing"] == f]
        x = group(key, f)
        sec = [f"{group(key, f, m).mean():.2f}" if len(x) else "-" for m in SECONDARY]
        L.append(f"| {f} | {len(ks)} | {sum(k['kind'] == 'code' for k in ks)} | "
                 f"{sum(k['kind'] == 'refusal' for k in ks)} | "
                 f"{sum(k['kind'] == 'non_code' for k in ks)} | "
                 f"{sum(k['finish_reason'] == 'length' for k in ks)} | "
                 f"{x.mean():.3f} | {x.std(ddof=1) if len(x) > 1 else float('nan'):.3f} | "
                 + " | ".join(sec) + " |")

    for title, zf in [("Primary contrasts (code answers only)", False),
                      ("Sensitivity: refusals and non-code answers scored 0", True)]:
        L += [f"\n## {title}\n",
              "| contrast | diff | 95% bootstrap CI | perm p | Holm p |", "|---|---|---|---|---|"]
        rows = []
        for f, g in CONFIRMATORY:
            rows.append((f"{f} − {g}", *boot_diff(group(key, f, zero_fill=zf),
                                                 group(key, g, zero_fill=zf), rng)))
        adj = holm([r[4] for r in rows])
        for r, h in zip(rows, adj):
            L.append(f"| {r[0]} | {r[1]:+.3f} | [{r[2]:+.3f}, {r[3]:+.3f}] | {r[4]:.3f} | {h:.3f} |")
        d, lo, hi, p = boot_diff(group(key, NOISE[0], zero_fill=zf), group(key, NOISE[1], zero_fill=zf), rng)
        L.append(f"| noise floor: neutral_a − neutral_b | {d:+.3f} | [{lo:+.3f}, {hi:+.3f}] | {p:.3f} | (not corrected) |")

    L += ["\n## Secondary outcomes vs pooled neutral (code answers only, uncorrected)\n",
          "| metric | " + " | ".join(f"{f} − neutral" for f in ("farm", "us_defense", "cn_defense")) + " |",
          "|---|---|---|---|"]
    for m in SECONDARY:
        cells = []
        for f in ("farm", "us_defense", "cn_defense"):
            d, lo, hi, _ = boot_diff(group(key, f, m), group(key, "neutral", m), rng)
            cells.append(f"{d:+.2f} [{lo:+.2f}, {hi:+.2f}]")
        L.append(f"| {m} | " + " | ".join(cells) + " |")

    if a.pilot:
        resid = np.concatenate([group(key, f) - group(key, f).mean() for f in frs if len(group(key, f)) > 1])
        dof = len(resid) - sum(1 for f in frs if len(group(key, f)) > 1)
        sd = math.sqrt((resid ** 2).sum() / dof)
        # bootstrap the pooled within-framing SD for an upper bound
        sds = []
        for _ in range(2000):
            r = rng.choice(resid, len(resid))
            sds.append(math.sqrt((r ** 2).sum() / dof))
        sd_hi = float(np.percentile(sds, 80))
        n_code_frac = sum(k["kind"] == "code" for k in key) / len(key)
        def need(s, pairwise):
            k = 2.0 if pairwise else 1.5   # var factor: x vs y (n each) or x vs pooled neutral (2n)
            return math.ceil(k * (Z_A + Z_B) ** 2 * s ** 2 / DELTA ** 2)
        L += ["\n## Pilot: sample-size calculation\n",
              f"- pooled within-framing SD of per-sample score: {sd:.3f} "
              f"(80th percentile of bootstrap: {sd_hi:.3f}); df = {dof}",
              f"- code-answer rate: {n_code_frac:.2f}",
              f"- n per framing to detect a {DELTA:.2f} gap, alpha .05 two-sided, power .80:",
              f"  - framing vs pooled neutral: {need(sd, False)} (SD point est.), {need(sd_hi, False)} (SD 80th pct)",
              f"  - pairwise (us vs cn, neutral_a vs neutral_b): {need(sd, True)} (SD point est.), {need(sd_hi, True)} (SD 80th pct)",
              f"  - divided by code-answer rate: {math.ceil(need(sd_hi, True) / max(n_code_frac, 1e-9))}"]
    out = run / ("pilot_report.md" if a.pilot else "report.md")
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
