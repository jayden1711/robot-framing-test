# robot-framing-test

Does a coding model write worse robot control code depending on who it is told the customer is?
Same drone-search task and API doc (find hidden survey markers), one sentence changed to name the customer, controllers scored blind in a deterministic simulator.

See [PLAN.md](PLAN.md) for the design and the pre-registered analysis.

- `wiif/sim.py` – 2D drone search sim (pure Python, deterministic)
- `prompts/api_doc.md` – the API doc every model sees
- `wiif/prompts.py` – framings (only the first sentence differs)
- `wiif/sandbox.py` – runs generated controllers in a bubblewrap sandbox, one process per episode
- `wiif/score.py` – blind scorer (never reads the framing key)
- `wiif/generate.py` – sampling from a local llama-server
- `wiif/analyze.py` – per-model bootstrap contrasts, refusal accounting, sample-size calc
- `wiif/compare.py` – cross-model difference-in-gaps vs the control model (gpt-oss-20b)
- `baselines/` – hand-written reference controllers

Results live in `results/` (gitignored).
