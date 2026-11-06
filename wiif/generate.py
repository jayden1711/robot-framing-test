"""Generate controllers from a local llama-server (OpenAI-compatible API).

  python -m wiif.generate --run results/pilot_qwen30b --model-tag qwen3-coder-30b-a3b-q4km --n 10

Framings are interleaved in a seeded random order so time-varying effects
(server load, thermal throttling) can't line up with framing. Each sample gets
an opaque random id. The framing lives only in key.jsonl, which the scorer
never reads.
"""
from __future__ import annotations

import argparse
import json
import random
import secrets
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .extract import classify
from .prompts import FRAMINGS, build_prompt, prompt_hash

# Identical for every framing and every model (pre-registered in PLAN.md).
SAMPLING = {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0,
            "repeat_penalty": 1.05, "max_tokens": 8192}


def _post(url, body, timeout=900):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--model-tag", required=True)
    ap.add_argument("--n", type=int, required=True, help="samples per framing")
    ap.add_argument("--server", default="http://127.0.0.1:8080")
    ap.add_argument("--order-seed", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=2)
    a = ap.parse_args()

    run = Path(a.run)
    (run / "raw").mkdir(parents=True, exist_ok=True)
    (run / "code").mkdir(exist_ok=True)
    key_path = run / "key.jsonl"
    done = set()
    if key_path.exists():
        for line in key_path.read_text().splitlines():
            k = json.loads(line)
            done.add((k["framing"], k["rep"]))

    meta = {
        "model_tag": a.model_tag,
        "sampling": SAMPLING,
        "prompt_hash": prompt_hash(),
        "framings": FRAMINGS,
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                     text=True).stdout.strip(),
        "server_props": _get(a.server + "/props"),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (run / f"meta_{int(time.time())}.json").write_text(json.dumps(meta, indent=2))

    jobs = [(f, r) for r in range(a.n) for f in FRAMINGS if (f, r) not in done]
    random.Random(a.order_seed).shuffle(jobs)
    print(f"{len(jobs)} generations to do ({len(done)} already done)", flush=True)

    def one(job):
        framing, rep = job
        sid = secrets.token_hex(6)
        seed = random.Random(f"{a.model_tag}|{framing}|{rep}").randrange(2**31)
        body = {"messages": [{"role": "user", "content": build_prompt(framing)}],
                "seed": seed, **SAMPLING}
        t0 = time.time()
        resp = _post(a.server + "/v1/chat/completions", body)
        dt = time.time() - t0
        choice = resp["choices"][0]
        text = choice["message"].get("content") or ""   # final answer only; reasoning kept in raw/
        kind, code = classify(text)
        (run / "raw" / f"{sid}.json").write_text(json.dumps(resp))
        if kind == "code":
            (run / "code" / f"{sid}.py").write_text(code)
        return {"sample_id": sid, "framing": framing, "rep": rep, "model_tag": a.model_tag,
                "seed": seed, "kind": kind, "finish_reason": choice.get("finish_reason"),
                "completion_tokens": resp.get("usage", {}).get("completion_tokens"),
                "latency_s": round(dt, 1)}

    with ThreadPoolExecutor(a.concurrency) as ex, open(key_path, "a") as kf:
        for i, rec in enumerate(ex.map(one, jobs)):
            kf.write(json.dumps(rec) + "\n")
            kf.flush()
            print(f"[{i + 1}/{len(jobs)}] {rec['kind']:8s} {rec['completion_tokens']} tok "
                  f"{rec['latency_s']}s", flush=True)   # framing deliberately not printed


if __name__ == "__main__":
    main()
