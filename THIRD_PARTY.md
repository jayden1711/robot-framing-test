# Third-party models, runtimes and tools

Weights are downloaded by `scripts/setup_nuc.sh` at pinned revisions into `~/models` (outside git) and are never
committed or redistributed. PLAN.md records the same pins.

## Models
| Model | Weights (HF repo @ revision, file) | License | Notes |
|---|---|---|---|
| Qwen3-Coder-30B-A3B-Instruct | `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF` @ b17cb02dd882d5b6ab62fc777ad2995f19668350, Q4_K_M | Apache-2.0 | |
| DeepSeek-Coder-V2-Lite-Instruct | `bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF` @ 8f248fa2072348f77a8bc37754e470de1f61866e, Q4_K_M | DeepSeek Model License (use restrictions, Attachment A) | evaluated only; see PLAN.md on the military-use clause |
| gpt-oss-20b | `ggml-org/gpt-oss-20b-GGUF` @ 15dcfc7e7c608c6161507211ed43c5b590801b4b, MXFP4 | Apache-2.0 (+ OpenAI gpt-oss usage policy) | control model |

## Runtimes and tools
| Tool | Version | License | Use |
|---|---|---|---|
| llama.cpp `llama-server` | release b12144, CUDA build | MIT | model serving (built into `~/opt/wiif`) |
| numpy | 2.5.4 | BSD-3-Clause | sim, scoring |
| pytest | 9.2.0 | MIT | tests |
| huggingface_hub | 2.4.0 | Apache-2.0 | downloads |
| bubblewrap (`bwrap`) | Ubuntu 24.04 package | LGPL-2.0-or-later | sandbox; system tool, not distributed |
