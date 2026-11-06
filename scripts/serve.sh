#!/usr/bin/env bash
# Start llama-server for ONE model (never two at once), after checking free GPU memory.
# usage: scripts/serve.sh qwen|deepseek|gptoss      (override expert offload with N_CPU_MOE=k)
set -euo pipefail
OPT=${OPT:-$HOME/opt/wiif}; MODELS=${MODELS:-$HOME/models}
case "$1" in
  qwen)     GGUF=Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf; NEED_MIB=11500; EXTRA="--n-cpu-moe ${N_CPU_MOE:-28}" ;;
  deepseek) GGUF=DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf; NEED_MIB=11500; EXTRA="--n-cpu-moe ${N_CPU_MOE:-6}" ;;
  gptoss)   GGUF=gpt-oss-20b-MXFP4.gguf; NEED_MIB=11500
            EXTRA="--n-cpu-moe ${N_CPU_MOE:-4} --chat-template-kwargs {\"reasoning_effort\":\"medium\"}" ;;
  *) echo "unknown model"; exit 1 ;;
esac
if pgrep -u "$USER" -x llama-server >/dev/null; then
  echo "A llama-server is already running; stop it first (one model on the GPU at a time)."; exit 3
fi
FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
echo "GPU free: ${FREE} MiB, need ~${NEED_MIB} MiB"
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader
if [ "$FREE" -lt "$NEED_MIB" ]; then echo "Not enough free GPU memory; not loading."; exit 2; fi
exec systemd-run --user --scope -q -p CPUQuota=800% nice -n 10 "$OPT/llama.cpp/build/bin/llama-server" \
  -m "$MODELS/$GGUF" --host 127.0.0.1 --port 8080 --jinja --no-webui \
  -ngl 99 $EXTRA -c 20480 --parallel 2 --threads 8 --threads-batch 8
