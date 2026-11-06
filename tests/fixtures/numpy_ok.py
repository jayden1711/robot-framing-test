import numpy as np
class Controller:
    def __init__(self, m): self.v = np.array([0.0, 0.0])
    def step(self, obs): return tuple(self.v)
