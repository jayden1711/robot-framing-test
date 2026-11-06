"""Parent side: runs the sim and talks to the sandboxed controller process.

On Linux we use bubblewrap (no network, read-only filesystem, private /tmp,
new PID namespace) plus rlimits (CPU seconds, address space, file size).
Without bwrap we only apply rlimits; that mode is refused for model-generated
code unless explicitly allowed (it is meant for hand-written baselines on a
dev laptop).
"""
from __future__ import annotations

import json
import os
import resource
import select
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import sim

CHILD = Path(__file__).with_name("sandbox_child.py").resolve()

INIT_TIMEOUT_S = 5.0      # wall time for import + Controller.__init__
STEP_TIMEOUT_S = 0.5      # wall time per step() call (generous: machine is shared)
EPISODE_CPU_S = 60        # RLIMIT_CPU for the whole child process
MEM_BYTES = 2 * 1024**3   # RLIMIT_AS
FSIZE_BYTES = 1024**2     # RLIMIT_FSIZE


def have_bwrap() -> bool:
    return sys.platform.startswith("linux") and shutil.which("bwrap") is not None


def _limits():
    resource.setrlimit(resource.RLIMIT_CPU, (EPISODE_CPU_S, EPISODE_CPU_S + 5))
    if sys.platform.startswith("linux"):
        resource.setrlimit(resource.RLIMIT_AS, (MEM_BYTES, MEM_BYTES))
    resource.setrlimit(resource.RLIMIT_FSIZE, (FSIZE_BYTES, FSIZE_BYTES))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.nice(0)  # inherit caller's niceness (pipeline is launched at nice 10)


def _cmd(code_path: Path, sandbox: bool) -> list[str]:
    py = sys.executable
    if not sandbox:
        return [py, "-I", str(CHILD), str(code_path)]
    prefix = Path(sys.prefix).resolve()
    base_prefix = Path(sys.base_prefix).resolve()
    args = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session",
            "--clearenv", "--setenv", "PATH", "/usr/bin", "--setenv", "HOME", "/tmp",
            "--ro-bind", "/usr", "/usr",
            "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
            "--symlink", "usr/bin", "/bin",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    if not str(base_prefix).startswith("/usr"):
        raise RuntimeError(f"sandbox expects the system Python under /usr, got {base_prefix}")
    if prefix != base_prefix:
        # venv: mount it at a neutral path so nothing under /home is visible
        args += ["--ro-bind", str(prefix), "/opt/venv"]
        py = "/opt/venv/bin/python"
    else:
        py = str(Path(sys.executable).resolve())
    args += ["--ro-bind", str(CHILD), "/sandbox/child.py",
             "--ro-bind", str(code_path.resolve()), "/sandbox/controller.py",
             "--chdir", "/tmp",
             py, "-I", "/sandbox/child.py", "/sandbox/controller.py"]
    return args


class _Proc:
    def __init__(self, argv):
        self.p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, preexec_fn=_limits,
                                  text=True, bufsize=1)
        self.buf = ""

    def send(self, obj) -> bool:
        try:
            self.p.stdin.write(json.dumps(obj) + "\n")
            self.p.stdin.flush()
            return True
        except (BrokenPipeError, OSError):
            return False

    def recv(self, timeout: float):
        """Returns parsed dict, 'timeout', or 'eof'."""
        deadline = time.monotonic() + timeout
        fd = self.p.stdout.fileno()
        while "\n" not in self.buf:
            rem = deadline - time.monotonic()
            if rem <= 0:
                return "timeout"
            r, _, _ = select.select([fd], [], [], rem)
            if not r:
                return "timeout"
            chunk = os.read(fd, 65536).decode(errors="replace")
            if not chunk:
                return "eof"
            self.buf += chunk
            if len(self.buf) > 1_000_000:
                return "eof"
        line, self.buf = self.buf.split("\n", 1)
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return {"error": "exception", "trace": "unparseable reply"}

    def kill(self):
        try:
            self.p.kill()
        except Exception:  # noqa: BLE001
            pass
        self.p.wait()


def _died_reason(proc: _Proc) -> str:
    proc.p.wait(timeout=2)
    rc = proc.p.returncode
    # SIGXCPU (-24) or SIGKILL after hard CPU limit -> cpu_limit
    return "cpu_limit" if rc in (-24, -9) else "exception"


def run_episode(code_path: Path, seed: int, sandbox: bool = True) -> dict:
    layout = sim.make_layout(seed)
    ep = sim.Episode(layout)
    proc = _Proc(_cmd(code_path, sandbox))
    detail = ""
    try:
        proc.send({"mission": sim.mission_info(layout)})
        r = proc.recv(INIT_TIMEOUT_S)
        if r == "timeout":
            ep._end("init_timeout")
        elif r == "eof":
            reason = _died_reason(proc)
            ep._end("cpu_limit" if reason == "cpu_limit" else "load_error")
        elif "error" in r:
            ep._end("load_error")
            detail = r.get("trace", "")
        while not ep.done:
            if not proc.send({"obs": ep.observation()}):
                ep._end(_died_reason(proc))
                break
            r = proc.recv(STEP_TIMEOUT_S)
            if r == "timeout":
                ep._end("step_timeout")
            elif r == "eof":
                ep._end(_died_reason(proc))
            elif "error" in r:
                ep._end(r["error"])
                detail = r.get("trace", "")
            else:
                try:
                    vx, vy = sim.parse_command(r.get("cmd"))
                except sim.BadCommand as e:
                    ep._end("bad_command")
                    detail = str(e)
                    break
                ep.step(vx, vy)
    finally:
        proc.kill()
    res = ep.result()
    if detail:
        res["detail"] = detail[-500:]
    return res
