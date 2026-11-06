# robot-framing-test: Claude rules

**Read `~/projects/NUC_RULES.md` first.** It covers Quatern priority, sim-run/gpu-run, the results policy and publishing.

Does a coding model write worse robot code depending on the stated customer? Plan (pre-registered): PLAN.md. State: HANDOFF.md.

- **Public repo, Apache-2.0. Results never go in git until the owner approves.** `results/` (generations, scores,
  key files, pilot reports, manual labels) is git-ignored. No result numbers in README/PLAN/HANDOFF (the
  lawnmower baseline in HANDOFF is an approved exception).
- **Pre-registration:** PLAN.md's design and analysis can't change after model output exists, except through
  a dated entry in the deviations log, written before looking at the affected outputs.
- **Blinding:** scoring stays blind to framing. Hand labels are made without seeing the framing.
- **One model served at a time:** `~/projects/bin/gpu-run --need-mib <N> --label robot-framing-test -- scripts/serve.sh <model>`.
  Run it in the foreground under nohup so it holds the lock, and stop it when done.
- **Sandbox:** model-written code only runs in the bubblewrap sandbox (`wiif/sandbox.py`). Never run it outside.
- New model downloads (DeepSeek, gpt-oss) and the main runs each need the owner's go. Weights live in
  `~/models` and are never committed.
