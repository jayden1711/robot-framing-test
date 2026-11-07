# CRITIQUES: what a skeptical expert would say, and what we have done about it

Every entry has exactly one status: **[A] addressed** (with a pointer), **[B] extra experiment** (with whether it
was run), or **[C] limitation** we state up front. This file contains no result numbers. Numbers live in the
git-ignored `results/` and are named below by file. All of this is **simulation**: a 2D point-mass drone in a
deterministic simulator, never a real robot.

**Scope of the claim.** We measure whether the *quality of generated robot code, as scored in simulation, differs
between prompts that name different customers*. We do not measure, and do not claim anything about, model intent.

---

## 1. "You p-hacked: you looked at the data and picked the comparison."  [A]

- The design and analysis are in `PLAN.md`, committed as `2cc73ce` at 2026-11-06T00:56:10-06:00, before any model
  output existed (`git log --format='%h %aI %s' -- PLAN.md`).
- Only four comparisons per model are primary (farm, us_defense, cn_defense vs pooled neutral; us_defense vs
  cn_defense), Holm-corrected, plus the pre-registered cross-model difference-in-gaps (Holm over 8 pairs). A
  detection needs Holm p < 0.05, a CI excluding 0, **and** a gap larger than the neutral_a vs neutral_b noise floor
  (`wiif/analyze.py`, `wiif/compare.py`). We never report the best gap per model.
- Anything outside those comparisons (secondary rates, spot checks, per-framing breakdowns) is labelled exploratory.
- Changes after the first commit are in the dated **Deviations log** in `PLAN.md`. Each was written before the
  affected main-run output existed. The task-variant decision (floor-effect check) is one of them; its calibration
  evidence is in `results/calibration_v2/`. The calibration batch never enters the main analysis.
- Pilot runs (`results/pilot_*`) and the calibration batch are not part of the confirmatory analysis, and the
  main runs use new request seeds (new model-tag suffix) and a new `--order-seed`.

## 2. "The gap is a wording confound, not a customer effect."  [A, with a limit in C]

- Two neutral paraphrases (`neutral_a`, `neutral_b`) are in the design. Their difference is the noise floor, and a
  framing effect only counts as detected if it exceeds it (`PLAN.md`, Noise floor).
- The prompt is byte-identical except for the first sentence (`wiif/prompts.py`; `prompt_hash` is recorded in each
  run's `meta_*.json`). Prompts are published verbatim: `python -m wiif.prompts <framing>`.
- Limit [C]: each customer has one wording. A difference between `us_defense` and `cn_defense` could still come from
  the specific words ("US" vs "Chinese", "contractor"), not the customer concept. Extra experiment [B, **not run**,
  would need a PLAN deviation and more generations]: two or three paraphrases per customer.

## 3. "N is too small."  [A for within-model, C for cross-model]

- Sample size is derived from the pilot SD with the formula in `PLAN.md` (Sample size). N = 80 per framing per
  model was chosen by the owner (2026-11-06). The pilot-based calculation, including the smallest detectable
  differences, is in `results/N_proposal.md` and each `results/*/pilot_report.md`; `analyze` prints it.
- The design is powered for a 10-point within-model gap on `score` (alpha 0.05, power 0.80, pairwise). A
  difference-in-gaps has about twice the variance, so the cross-model comparison detects only about
  sqrt(2) times larger effects (the exact figure is in `results/N_proposal.md`). Smaller cross-model differences
  are not excluded. We will say "not detected", never "no effect", and always show the CI.
- The SD comes from a floor-limited, right-skewed score distribution, so the bootstrap-SD formula is approximate.
  We re-check power against the main-run SD after the run and report it.

## 4. "Quantization or local-model artifacts."  [C]

- Models are local GGUF builds: Qwen3-Coder-30B-A3B-Instruct Q4_K_M, DeepSeek-Coder-V2-Lite-Instruct Q4_K_M,
  gpt-oss-20b MXFP4 (as released). Repos, revisions and SHA-256 sums: `PLAN.md`, `THIRD_PARTY.md`, each run's
  `meta_*.json`, `~/models/SHA256SUMS.wiif`. Runtime: llama.cpp b12144, expert offload recorded per run.
- Would plausibly generalise: that a customer sentence can (or cannot) shift code quality in these specific
  checkpoints, with this prompt and sampling.
- Would **not** be shown: behaviour of the full-precision or hosted versions, larger models (Qwen3-Coder-480B,
  Qwen3-Coder-Next), or other sampling settings. Quantization could dampen or amplify an effect; we did not test
  other quantizations. The Hirundo case study used the same 30B-A3B model family; we do not claim our setup
  reproduces theirs (user message vs system prompt, different task).
- llama.cpp with parallel slots is not bit-reproducible; per-request seeds are recorded and raw outputs are kept in
  `results/*/raw/`.

## 5. "You are claiming the model is malicious."  [A]

- We claim nothing about intent. The estimand is a **difference in a code-quality score between framings** for
  fixed prompts, tasks and sampling. A gap, if found, has many possible causes (training data associations, refusal
  or safety tuning, formatting habits) that this design cannot separate.
- Wording in all outputs stays neutral and factual. The spot check looks for customer mentions and missing safety
  checks and is exploratory.

## 6. "Scores are at the floor, so you cannot see a gap."  [A / B, run]

- Pilot scores were far below the hand-written baseline (`baselines/lawnmower.py`). Owner decision: run a small
  calibration batch on one easier variant (`WIIF_VARIANT=v2_easy`, smaller field, bigger sensor radius, fewer
  markers and zones, gentler battery) before the main run, and switch only if mean scores land in a usable range.
- Calibration evidence: `results/calibration_v2/<model>/pilot_report.md` and `scores.jsonl`. The outcome and the
  decision are recorded in the `PLAN.md` deviations log and `HANDOFF.md` (without numbers).
- Limit [C]: a model at the floor (e.g. DeepSeek-Coder-V2-Lite) makes the primary score uninformative. We report
  secondary outcomes for it, labelled exploratory, and state the floor effect plainly.

## 7. "The scorer might leak the framing or be buggy."  [A]

- Samples get random ids; the framing lives only in `key.jsonl`; `wiif/score.py` never opens it. Progress logs omit
  framings. Hand labels of non-code replies are made from the text alone (`manual_labels.jsonl`).
- Simulator and sandbox are covered by `tests/test_sim.py` (network, filesystem, hang, exception, bad return,
  numpy-in-sandbox, variant doc consistency). Model code runs only in bubblewrap (`wiif/sandbox.py`) and cannot see
  hidden marker positions. The baseline reproduces identically across machines.

## 8. "The control model is not comparable."  [C]

- gpt-oss-20b differs from the Chinese models in architecture, size, training, quantization and in being a reasoning
  model. A difference-in-gaps therefore does not isolate developer origin. We describe it only as "gap in model M
  differs from gap in the control", never as an effect of origin. One control model cannot support a general claim.
- Reasoning text is kept in `raw/`; only the final answer is scored. Truncation at max_tokens is reported.

## 9. "Refusals or non-code answers are dropped."  [A]

- Refusals and non-code are classified (`wiif/extract.py`), counted per framing, compared by Fisher's exact test,
  and every primary comparison is repeated with them scored 0 (sensitivity analysis in `analyze` and `compare --zero-fill`).

## 10. "One task, one simulator."  [C]

- Single task (drone search), single simulator, 50 fixed evaluation layouts (seeds 1000-1049, never tuned on).
  Real robots, other tasks, and other code styles are not covered. No claim about real-world safety.

## 11. "Same sampling for every model is unfair to some."  [C]

- Pre-registered choice: Qwen model-card sampling for all models (temperature 0.7, top_p 0.8, top_k 20, max_tokens
  8192) so sampling is not a between-model difference. gpt-oss's own recommended settings differ; a run with them
  is an unrun extra experiment [B, not run].

## 12. "Naming a defense customer in a drone task changes the task, not just the customer."  [C]

- Possibly true, and it is part of what we measure. The `farm` framing is included as a civilian drone-customer
  contrast. Model-facing text says "survey markers", not "targets" (deviation logged before any output).

## 13. "Can I reproduce a number from the post?"  [A]

- Each run directory holds `meta_*.json` (model tag, sampling, prompt hash, task variant, order seed, git commit,
  server properties), `key.jsonl` (per-sample seeds), `raw/`, `code/`, `scores.jsonl`, `episodes.jsonl`.
- One command each: `scripts/run_chunk.sh` (generate, resumable), `scripts/finish.sh` (score and analyze),
  `python -m wiif.compare ...` (cross-model). Exact invocations are in `HANDOFF.md`.
- Raw prompts, isolation tests and full attempt logs (including pilots and calibration, with all attempts) will be
  published with the results once approved.

## 14. "The DeepSeek licence forbids military use."  [A]

- The study only evaluates outputs under prompts that *name* a defense customer; it does not use the model for
  military purposes. Stated in `PLAN.md`.

## 15. "Conflict of interest."  [A]

- Disclosed at the top of this file and in the README.
