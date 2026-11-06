import math
class Controller:
    def __init__(self, m): pass
    def step(self, obs):
        t = obs["t"] / 2.0   # 20 m circle near home: stays in the field until the battery dies
        return (10 * math.cos(t), 10 * math.sin(t))
