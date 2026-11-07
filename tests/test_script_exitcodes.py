import os
import shutil
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sandbox(tmp_path, py_body):
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "pilot.sh", tmp_path / "scripts" / "pilot.sh")
    py = tmp_path / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text("#!/bin/sh\n" + py_body + "\n")
    py.chmod(py.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "WIIF_SCOPED": "1", "RUN": str(tmp_path / "run"), "N": "1"}
    return subprocess.run(["bash", str(tmp_path / "scripts" / "pilot.sh")], env=env, capture_output=True, text=True)


def test_pilot_fails_when_inner_job_crashes(tmp_path):
    assert _sandbox(tmp_path, "exit 3").returncode != 0


def test_pilot_fails_when_outputs_missing(tmp_path):
    # every python step "succeeds" but writes nothing: must not report success
    assert _sandbox(tmp_path, "exit 0").returncode != 0
