#!/usr/bin/env bash
# Pilot: N per framing, one model. Expects scripts/serve.sh running.
set -euo pipefail
# re-exec inside a CPU-capped scope (shared machine)
if [ -z "${WIIF_SCOPED:-}" ]; then exec systemd-run --user --scope -q -p CPUQuota=600% env WIIF_SCOPED=1 "$0" "$@"; fi
cd "$(dirname "$0")/.."
RUN=${RUN:-results/pilot_qwen30b}; N=${N:-10}; TAG=${TAG:-qwen3-coder-30b-a3b-instruct-q4km}
nice -n 10 .venv/bin/python -m wiif.generate --run "$RUN" --model-tag "$TAG" --n "$N"
.venv/bin/python -c 'import sys; from pathlib import Path; from wiif.prompts import FRAMINGS
run, n = Path(sys.argv[1]), int(sys.argv[2]); want = n * len(FRAMINGS)
got = len((run / "key.jsonl").read_text().splitlines()) if (run / "key.jsonl").exists() else 0
sys.exit(f"incomplete generation: {got}/{want} rows in {run}/key.jsonl") if got < want else None' "$RUN" "$N"
nice -n 10 .venv/bin/python -m wiif.score --code "$RUN/code" --out "$RUN/scores.jsonl" \
    --episodes-out "$RUN/episodes.jsonl" --workers 4
[ -s "$RUN/scores.jsonl" ] && [ -s "$RUN/episodes.jsonl" ] || { echo "scoring produced no output in $RUN" >&2; exit 1; }
nice -n 10 .venv/bin/python -m wiif.analyze --run "$RUN" --pilot
