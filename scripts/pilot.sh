#!/usr/bin/env bash
# Pilot: N per framing, one model. Expects scripts/serve.sh running.
set -euo pipefail
# re-exec inside a CPU-capped scope (shared machine)
if [ -z "${WIIF_SCOPED:-}" ]; then exec systemd-run --user --scope -q -p CPUQuota=600% env WIIF_SCOPED=1 "$0" "$@"; fi
cd "$(dirname "$0")/.."
RUN=${RUN:-results/pilot_qwen30b}; N=${N:-10}; TAG=${TAG:-qwen3-coder-30b-a3b-instruct-q4km}
nice -n 10 .venv/bin/python -m wiif.generate --run "$RUN" --model-tag "$TAG" --n "$N"
nice -n 10 .venv/bin/python -m wiif.score --code "$RUN/code" --out "$RUN/scores.jsonl" \
    --episodes-out "$RUN/episodes.jsonl" --workers 4
nice -n 10 .venv/bin/python -m wiif.analyze --run "$RUN" --pilot
