#!/usr/bin/env bash
# One-time setup on the NUC: Python venv + pinned llama.cpp CUDA build + model downloads.
# Everything runs at nice 10 with capped build parallelism (shared machine).
set -euo pipefail
cd "$(dirname "$0")/.."
LLAMA_TAG=b12144
OPT=${OPT:-$HOME/opt/wiif}
MODELS=${MODELS:-$HOME/models}
mkdir -p "$OPT" "$MODELS"

# venv
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

# llama.cpp (CUDA, sm_120 for RTX 50xx)
if [ ! -x "$OPT/llama.cpp/build/bin/llama-server" ]; then
  [ -d "$OPT/llama.cpp" ] || git clone -q https://github.com/ggml-org/llama.cpp "$OPT/llama.cpp"
  git -C "$OPT/llama.cpp" fetch -q --tags && git -C "$OPT/llama.cpp" checkout -q "$LLAMA_TAG"
  export PATH=/usr/local/cuda/bin:$PATH
  nice -n 10 cmake -S "$OPT/llama.cpp" -B "$OPT/llama.cpp/build" -DGGML_CUDA=ON \
      -DCMAKE_CUDA_ARCHITECTURES=120 -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release >/dev/null
  nice -n 10 cmake --build "$OPT/llama.cpp/build" -j 8 --target llama-server >/dev/null
fi
"$OPT/llama.cpp/build/bin/llama-server" --version 2>&1 | tail -2

# models (pinned revisions; see PLAN.md)
dl() { # repo revision file
  [ -f "$MODELS/$3" ] || nice -n 10 .venv/bin/hf download "$1" "$3" --revision "$2" --local-dir "$MODELS" >/dev/null 2>&1
  sha256sum "$MODELS/$3" | tee -a "$MODELS/SHA256SUMS.wiif"
}
case "${1:-qwen}" in
  qwen) dl unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF b17cb02dd882d5b6ab62fc777ad2995f19668350 Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf ;;
  deepseek) dl bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF main DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf ;;
esac
