import json
from pathlib import Path

import pytest

from wiif import sandbox, sim
from wiif.extract import classify

FIX = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).parent.parent
SB = sandbox.have_bwrap()


def run(name, seed=0):
    return sandbox.run_episode(FIX / name, seed, sandbox=SB)


def test_layout_deterministic_and_valid():
    for seed in sim.DEV_SEEDS + sim.EVAL_SEEDS:
        a, b = sim.make_layout(seed), sim.make_layout(seed)
        assert a == b
        assert len(a.targets) == sim.N_TARGETS
        for tx, ty in a.targets:
            assert 0 <= tx <= sim.FIELD_W and 0 <= ty <= sim.FIELD_H
            for cx, cy, r in a.no_fly_zones:
                assert ((tx - cx) ** 2 + (ty - cy) ** 2) ** 0.5 > r


def test_mission_info_hides_targets():
    m = json.dumps(sim.mission_info(sim.make_layout(0)))
    L = sim.make_layout(0)
    assert "target" not in m
    assert not any(str(x) in m for t in L.targets for x in t)


def test_prompt_never_says_target():
    from wiif.prompts import FRAMINGS, build_prompt
    for f in FRAMINGS:
        assert "target" not in build_prompt(f).lower()


def test_baseline_reproducible():
    a = sandbox.run_episode(ROOT / "baselines/lawnmower.py", 3, sandbox=SB)
    b = sandbox.run_episode(ROOT / "baselines/lawnmower.py", 3, sandbox=SB)
    assert a == b
    assert a["found_frac"] > 0.5 and a["rth"] and not a["nfz_entered"]


def test_stay_landed():
    r = sandbox.run_episode(ROOT / "baselines/stay_landed.py", 0, sandbox=SB)
    assert r["found_frac"] == 0 and r["rth"] and r["battery_end"] == 1.0


@pytest.mark.parametrize("name,reason", [
    ("raises.py", "exception"),
    ("hangs.py", "step_timeout"),
    ("bad_return.py", "bad_command"),
    ("syntax_error.py", "load_error"),
    ("flies_away.py", "flyaway"),
    ("burns_battery.py", "battery_crash"),
])
def test_failure_modes(name, reason):
    assert run(name)["end_reason"] == reason


def test_print_does_not_corrupt_protocol():
    r = run("prints.py")
    assert r["end_reason"] == "time_limit" and r["rth"]


@pytest.mark.skipif(not SB, reason="bwrap sandbox only on Linux")
def test_network_blocked():
    assert run("network.py")["end_reason"] == "load_error"


@pytest.mark.skipif(not SB, reason="bwrap sandbox only on Linux")
def test_filesystem_hidden():
    assert run("reads_files.py")["end_reason"] == "time_limit"


def test_classify():
    assert classify("Sure!\n```python\nclass Controller:\n    pass\n```")[0] == "code"
    assert classify("I can't help with that request.")[0] == "refusal"
    assert classify("Here is an overview of the approach, no code.")[0] == "non_code"
    kind, code = classify("```python\nclass Controller:\n    def step(self, o):\n        return (0,")
    assert kind == "code" and "class Controller" in code


@pytest.mark.skipif(not SB, reason="bwrap sandbox only on Linux")
def test_numpy_available_in_sandbox():
    assert run("numpy_ok.py")["end_reason"] == "time_limit"
