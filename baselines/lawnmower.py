"""Hand-written reference controller: boustrophedon sweep, visibility-graph
routing around no-fly zones, battery-aware return to home. Uses only the
documented API (it sees exactly what a model-written controller sees).
Tuned on DEV seeds only."""
import heapq
import math

MARGIN = 7.0       # metres kept clear of no-fly zones
POLY_N = 16        # vertices per inflated zone polygon
EDGE = 2.0         # metres kept inside the field edge


def _seg_clear(p, q, circles):
    for cx, cy, r in circles:
        dx, dy = q[0] - p[0], q[1] - p[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((cx - p[0]) * dx + (cy - p[1]) * dy) / L2))
        if math.hypot(p[0] + t * dx - cx, p[1] + t * dy - cy) < r:
            return False
    return True


class Controller:
    def __init__(self, mission):
        self.m = mission
        self.W, self.H = mission["field"]["width"], mission["field"]["height"]
        self.home = tuple(mission["home"])
        self.vmax, self.amax = mission["max_speed"], mission["max_accel"]
        bm = mission["battery_model"]
        self.drain_fast = bm["idle_drain_per_s"] + bm["drain_per_s_per_mps"] * self.vmax
        zones = [(z["center"][0], z["center"][1], z["radius"]) for z in mission["no_fly_zones"]]
        # collision check uses zone + (margin - 1); polygon vertices sit outside zone + margin
        self.check = [(cx, cy, r + MARGIN - 1.0) for cx, cy, r in zones]
        self.nodes = []
        for cx, cy, r in zones:
            R = (r + MARGIN) / math.cos(math.pi / POLY_N) + 0.5
            for k in range(POLY_N):
                a = 2 * math.pi * k / POLY_N
                p = (cx + R * math.cos(a), cy + R * math.sin(a))
                if self._free(p):
                    self.nodes.append(p)
        n = len(self.nodes)
        self.adj = [[] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                if _seg_clear(self.nodes[i], self.nodes[j], self.check):
                    d = math.dist(self.nodes[i], self.nodes[j])
                    self.adj[i].append((j, d))
                    self.adj[j].append((i, d))
        # sweep waypoints
        sr = mission["sensor_radius"]
        spacing = 2 * sr * 0.95
        raw, y, left = [], sr * 0.9, True
        while y < self.H:
            xs = [sr * 0.9, self.W - sr * 0.9]
            if not left:
                xs.reverse()
            raw += [(xs[0], y), (xs[1], y)]
            left, y = not left, y + spacing
        self.sweep = []
        for k, p in enumerate(raw):
            q = self._push_out(p)
            if not self._free(q):
                # zone overlaps the field edge: slide along the lane toward its other end
                other = raw[k + 1] if k % 2 == 0 else raw[k - 1]
                step = 2.0 if other[0] > p[0] else -2.0
                x = p[0]
                while (min(p[0], other[0]) <= x <= max(p[0], other[0])
                       and not self._free((x, p[1]))):
                    x += step
                q = (x, p[1]) if self._free((x, p[1])) else None
            if q is not None:
                self.sweep.append(q)
        self.si = 0
        self.returning = False
        self.path = []
        self.path_goal = None

    def _free(self, p):
        return (EDGE <= p[0] <= self.W - EDGE and EDGE <= p[1] <= self.H - EDGE
                and all(math.hypot(p[0] - cx, p[1] - cy) >= r + 0.5 for cx, cy, r in self.check))

    def _push_out(self, p):
        x, y = p
        for cx, cy, r in self.check:
            d = math.hypot(x - cx, y - cy)
            need = r + 3.0
            if d < need:
                ux, uy = ((x - cx) / d, (y - cy) / d) if d > 1e-6 else (0.0, 1.0)
                x, y = cx + ux * need, cy + uy * need
        return (min(max(x, EDGE + 1), self.W - EDGE - 1), min(max(y, EDGE + 1), self.H - EDGE - 1))

    def _plan(self, a, b):
        """Shortest path a->b over the visibility graph. Returns list of points after a."""
        # if we have drifted into a safety margin, shrink that circle so we can plan out of it
        check = [(cx, cy, min(r, math.hypot(a[0] - cx, a[1] - cy) - 0.1)) for cx, cy, r in self.check]
        if _seg_clear(a, b, check):
            return [b], math.dist(a, b)
        n = len(self.nodes)
        A, B = n, n + 1
        dist = {A: 0.0}
        prev = {}
        pq = [(0.0, A)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == B:
                break
            if d > dist.get(u, 1e18):
                continue
            up = a if u == A else self.nodes[u]
            nbrs = list(self.adj[u]) if u < n else [
                (j, math.dist(a, self.nodes[j])) for j in range(n)
                if _seg_clear(a, self.nodes[j], check)]
            if _seg_clear(up, b, check):
                nbrs.append((B, math.dist(up, b)))
            for v, w in nbrs:
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v], prev[v] = nd, u
                    heapq.heappush(pq, (nd, v))
        if B not in dist:          # no route found: go straight (should not happen)
            return [b], math.dist(a, b) * 1.5
        out, u = [], B
        while u != A:
            out.append(b if u == B else self.nodes[u])
            u = prev[u]
        return out[::-1], dist[B]

    def _go(self, pos, goal):
        if self.path_goal != goal or not self.path:
            self.path, _ = self._plan(tuple(pos), goal)
            self.path_goal = goal
        while len(self.path) > 1 and math.dist(pos, self.path[0]) < 3.0:
            self.path.pop(0)
        wp = self.path[0]
        d = math.dist(pos, wp)
        if d < 1e-6:
            return (0.0, 0.0), 0.0
        ux, uy = (wp[0] - pos[0]) / d, (wp[1] - pos[1]) / d
        if len(self.path) == 1:
            v_end = 0.0
        else:   # slow for the corner so the accel limit doesn't swing us into the margin
            nx, ny = self.path[1][0] - wp[0], self.path[1][1] - wp[1]
            nn = math.hypot(nx, ny) or 1.0
            cos_t = (ux * nx + uy * ny) / nn
            v_end = self.vmax * max(0.3, cos_t)
        speed = min(self.vmax, math.sqrt(v_end ** 2 + 2 * self.amax * 0.7 * d))
        return (ux * speed, uy * speed), d

    def _need_home(self, pos):
        _, d = self._plan(tuple(pos), self.home)
        return self.drain_fast * (d / self.vmax + 10.0)

    def step(self, obs):
        pos = obs["pos"]
        if self.returning and obs["landed"]:
            return (0.0, 0.0)
        if not self.returning:
            t_left = self.m["time_limit"] - obs["t"]
            need = self._need_home(pos)
            if (obs["n_found"] >= self.m["n_targets"] or obs["battery"] < need * 1.15 + 0.03
                    or t_left < need / self.drain_fast + 20):
                self.returning = True
        if not self.returning:
            while self.si < len(self.sweep) and math.dist(pos, self.sweep[self.si]) < 4.0:
                self.si += 1
            if self.si >= len(self.sweep):
                self.returning = True
        goal = self.home if self.returning else self.sweep[self.si]
        cmd, d = self._go(pos, goal)
        if self.returning and len(self.path) == 1 and d < 1.0:
            return (0.0, 0.0)
        return cmd
