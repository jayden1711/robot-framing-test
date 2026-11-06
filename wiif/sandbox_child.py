"""Runs inside the sandbox. Loads the untrusted controller and answers
step requests over a private pipe (the original stdout fd). The controller's
own print() output goes to stderr, which the parent discards.

Protocol (one JSON object per line):
  parent -> child: {"mission": {...}}            child -> {"ok": true} | {"error": "..."}
  parent -> child: {"obs": {...}}                child -> {"cmd": [vx, vy]} | {"error": "..."}
"""
import json
import os
import sys
import traceback


def main() -> None:
    proto = os.fdopen(os.dup(1), "w", buffering=1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    path = sys.argv[1]

    def send(obj):
        proto.write(json.dumps(obj) + "\n")
        proto.flush()

    def err(stage):
        send({"error": stage, "trace": traceback.format_exc()[-2000:]})

    msg = json.loads(sys.stdin.readline())
    try:
        ns = {"__name__": "controller"}
        with open(path) as f:
            src = f.read()
        exec(compile(src, "controller.py", "exec"), ns)
        ctrl = ns["Controller"](msg["mission"])
    except BaseException:  # noqa: BLE001
        err("load_error")
        return
    send({"ok": True})
    for line in sys.stdin:
        obs = json.loads(line)["obs"]
        try:
            cmd = ctrl.step(obs)
            try:
                cmd = [float(c) for c in cmd] if not isinstance(cmd, dict) else cmd
            except Exception:  # noqa: BLE001
                cmd = repr(cmd)[:200]
            send({"cmd": cmd})
        except BaseException:  # noqa: BLE001
            err("exception")
            return


if __name__ == "__main__":
    main()
