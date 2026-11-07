#!/usr/bin/env bash
# Score (blind, sandboxed, CPU only) and analyze one run directory. Needs no GPU.
# usage: RUN=results/main_qwen30b WIIF_VARIANT=v2_easy scripts/finish.sh [--pilot]
# --pilot adds the sample-size section (calibration/pilot runs); omit it for a main run.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${RUN:?}"
WORKERS=${WORKERS:-2}
~/projects/bin/sim-run .venv/bin/python -m wiif.score --code "$RUN/code" --out "$RUN/scores.jsonl" \
    --episodes-out "$RUN/episodes.jsonl" --workers "$WORKERS"
~/projects/bin/sim-run .venv/bin/python -m wiif.analyze --run "$RUN" "$@"
