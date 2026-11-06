class Controller:
    def __init__(self, m): self.n = 0
    def step(self, obs):
        self.n += 1
        if self.n > 10: raise ValueError("boom")
        return (5.0, 5.0)
