"""Sanity baseline: never takes off. Expected: found 0, rth True, no crashes."""


class Controller:
    def __init__(self, mission):
        pass

    def step(self, obs):
        return (0.0, 0.0)
