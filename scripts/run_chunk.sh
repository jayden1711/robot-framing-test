#!/usr/bin/env bash
# One resumable generation chunk for ONE model: start llama-server, generate until MAXS seconds have passed
# (in-flight requests finish), stop the server. Re-run until generate reports 0 left.
# Run it under the GPU lock, in the foreground:
#   ~/projects/bin/gpu-run --need-mib 12500 --wait 540 --label robot-framing-test -- \
#       scripts/run_chunk.sh <qwen|gptoss|deepseek>
# env: RUN (results dir), TAG (model tag, also seeds the request seeds), N (per framing), ORDER_SEED,
#      WIIF_VARIANT (v1|v2_easy), MAXS (seconds before no new request starts; default 200)
set -uo pipefail
cd "$(dirname "$0")/.."
MODEL=$1; : "${RUN:?}" "${TAG:?}" "${N:?}"
ORDER_SEED=${ORDER_SEED:-0}; MAXS=${MAXS:-200}
mkdir -p "$RUN"
scripts/serve.sh "$MODEL" > "$RUN/serve_$(date +%s).log" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null; wait $SRV 2>/dev/null' EXIT
for _ in $(seq 1 240); do
  curl -sf http://127.0.0.1:8080/health >/dev/null && break
  kill -0 $SRV 2>/dev/null || { echo "server exited early"; exit 5; }
  sleep 2
done
curl -sf http://127.0.0.1:8080/health >/dev/null || { echo "server not healthy"; exit 6; }
nice -n 10 .venv/bin/python -m wiif.generate --run "$RUN" --model-tag "$TAG" --n "$N" \
    --order-seed "$ORDER_SEED" --max-seconds "$MAXS"
