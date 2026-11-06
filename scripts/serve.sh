#!/usr/bin/env bash
# Start llama-server for one model, after checking there is enough free GPU memory.
# usage: scripts/serve.sh qwen|deepseek
set -euo pipefail
OPT=${OPT:-$HOME/opt/wiif}; MODELS=${MODELS:-$HOME/models}
case "$1" in
  qwen)     GGUF=Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf; NEED_MIB=11000; EXTRA="--n-cpu-moe ${N_CPU_MOE:-24}" ;;
  deepseek) GGUF=DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf; NEED_MIB=12000; EXTRA="" ;;
  *) echo "unknown model"; exit 1 ;;
esac
FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
echo "GPU free: ${FREE} MiB, need ~${NEED_MIB} MiB"
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader
if [ "$FREE" -lt "$NEED_MIB" ]; then echo "Not enough free GPU memory; not loading."; exit 2; fi
exec nice -n 10 "$OPT/llama.cpp/build/bin/llama-server" -m "$MODELS/$GGUF" \
  --host 127.0.0.1 --port 8080 --jinja --no-webui \
  -ngl 99 $EXTRA -c 16384 --parallel 2 --threads 8 --threads-batch 8
