import math
class Controller:
    def __init__(self, m): pass
    def step(self, obs):
        t = obs["t"] / 20.0
        return (10 * math.cos(t), 10 * math.sin(t))
