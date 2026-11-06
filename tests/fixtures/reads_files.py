import os
class Controller:
    def __init__(self, m):
        # must not be able to see the repo / sim source / home dir
        for p in ["/home", os.path.expanduser("~"), "/root"]:
            if os.path.exists(p) and os.listdir(p):
                raise RuntimeError("can see " + p)
    def step(self, obs): return (0.0, 0.0)
