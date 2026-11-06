# HANDOFF: robot-framing-test (2026-11-06)
Status: Sim, sandbox and blind scorer done; Qwen3-Coder weights downloaded; pilot not started
Next: Serve Qwen through gpu-run, run the 50-generation pilot, stop for approval
Updated: 2026-11-06

Repo: `jayden1711/robot-framing-test` (public). Clones: Mac `~/Downloads/projects/robot-framing-test`,
NUC `~/projects/robot-framing-test` (user `jayden`, via `ssh nuc-admin`).

## Done

- Sim, sandbox, blind scorer, analysis and cross-model comparison are all built. Tests pass on the NUC under
  bubblewrap (16 of 16), including network, filesystem, hang, exception, bad-return and numpy-in-sandbox checks.
  - sim: `wiif/sim.py`
  - API doc: `prompts/api_doc.md`
  - framings: `wiif/prompts.py`
  - sandbox: `wiif/sandbox.py`
  - scorer: `wiif/score.py`
  - analysis: `wiif/analyze.py`
  - cross-model comparison: `wiif/compare.py`
  - tests: `tests/`
- **Baseline.** `baselines/lawnmower.py`, tuned on dev seeds only, scores 0.797 on the 50 eval seeds: 100% return
  to home, a no-fly-zone entry on 1 of 50 layouts. Identical on the Mac and on the NUC.
- **Model-facing wording.** Says "survey markers" (API key `n_markers`) instead of "targets". A test checks that no
  prompt contains "target".
- **PLAN.md.** Pre-registered analysis, plus gpt-oss-20b as the non-Chinese control model and the cross-model
  difference-in-gaps analysis. The deviations log has 3 entries, all made before any model output existed.
- **NUC setup.**
  - llama.cpp b12144 built with CUDA at `~/opt/wiif/llama.cpp/build/bin/llama-server`
  - venv `.venv` with numpy 2.5.4, pytest 9.2.0, huggingface_hub 2.4.0

## In progress / not done

- **Qwen weights download.** `scripts/setup_nuc.sh qwen` was still running when this session stopped. It was
  started by you, not by Claude, so it was left running. It was downloading
  `Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf` (18.6 GB) into `~/models`, about 134 MB done at 01:07.
  - The download resumes if re-run.
  - To stop it: `ssh nuc-admin 'pkill -u jayden -f scripts/setup_nuc.sh; pkill -u jayden -f "hf download"'`
- **Pilot.** Not started. No model output exists anywhere; `results/` does not exist yet.
- **Other weights.** DeepSeek and gpt-oss weights are not downloaded.

## Next steps (in order)

```bash
ssh nuc-admin
cd ~/projects/robot-framing-test && git pull

# 1. finish the download (no-op if already complete) and record its SHA-256
scripts/setup_nuc.sh qwen

# 2. start the server: one model at a time; it checks free GPU memory and refuses
#    if a llama-server is already running
nvidia-smi
scripts/serve.sh qwen        # in tmux, or nohup ... > serve_qwen.log 2>&1 &
#    If it runs out of GPU memory, raise expert offload, e.g. N_CPU_MOE=32 scripts/serve.sh qwen

# 3. pilot: 10 per framing, 50 generations
#    generate -> blind score -> analyze --pilot; writes results/pilot_qwen30b/pilot_report.md
#    resumable: re-running skips (framing, rep) pairs already in key.jsonl
scripts/pilot.sh

# 4. read the pilot report, hand-label any non-code replies, propose N, then STOP for approval
#    hand labels go in results/pilot_qwen30b/manual_labels.jsonl, blind to framing

# 5. stop the server
pkill -u jayden -x llama-server
nvidia-smi
```

Later, each after approval:

```bash
scripts/setup_nuc.sh deepseek
scripts/setup_nuc.sh gptoss
```

Then run the main runs per model with `serve.sh <model>` and `pilot.sh`, using `RUN=results/main_<model>`,
`TAG=...-main`, `N=<approved N>` and a new `--order-seed`. Finally:

```bash
python -m wiif.compare --control results/main_gptoss \
    --model results/main_qwen30b --model results/main_dsv2lite
```

## Open decisions waiting on you

1. **N per framing.** Proposed after the pilot. Note: N sized for a 10-point within-model gap only detects about a
   14-point cross-model difference-in-gaps. Detecting 10 points across models needs about 2× N. This is your call
   at the pilot stop.
2. **Sampling for gpt-oss.** The plan uses the same sampling for all models: Qwen card settings, temperature 0.7,
   top_p 0.8, reasoning effort medium. The alternative is each model's own recommended settings, which would mean
   temperature 1.0 for gpt-oss.
3. **Untuned offload settings.** The `--n-cpu-moe` defaults in `scripts/serve.sh` (qwen 28, deepseek 6, gptoss 4)
   have not been tested. Free GPU memory varies with edge-vla-bench, and was 15.8 GB at the end of this session.

## Uncommitted

Nothing. Everything is committed and pushed. Results never go in git: `results/` is gitignored, and nothing is
posted without approval.
