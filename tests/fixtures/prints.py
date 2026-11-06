import sys
class Controller:
    def __init__(self, m): print("hello" * 1000)
    def step(self, obs):
        print('{"cmd": [10, 10]}'); sys.stdout.write("noise\n")
        return (0.0, 0.0)
