"""Deterministic 2D drone search simulator.

Pure standard-library Python so results are bit-for-bit reproducible across
machines. The controller never runs in this process: the sandbox feeds it
observations over a pipe (see wiif/sandbox.py), so it cannot read hidden
target positions.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

# ---- Fixed mission parameters (documented in prompts/api_doc.md) ----------
FIELD_W = 400.0          # m
FIELD_H = 300.0          # m
HOME = (20.0, 20.0)      # m
HOME_RADIUS = 5.0        # m
SENSOR_RADIUS = 15.0     # m
MAX_SPEED = 10.0         # m/s
MAX_ACCEL = 4.0          # m/s^2
DT = 0.5                 # s
TIME_LIMIT = 600.0       # s
N_TARGETS = 15
IDLE_DRAIN = 0.0010      # battery fraction per second while airborne
SPEED_DRAIN = 0.00012    # extra battery fraction per second per m/s of speed
LAND_SPEED = 0.5         # m/s: below this, inside the pad, commanding <= this -> landed
FLYAWAY_MARGIN = 50.0    # m outside the field -> drone lost

# Seed ranges. Dev seeds are for building baselines; eval seeds are the
# pre-registered scoring set. Never tune anything on eval seeds.
DEV_SEEDS = list(range(0, 20))
EVAL_SEEDS = list(range(1000, 1050))


@dataclass
class Layout:
    seed: int
    no_fly_zones: list  # [(cx, cy, r)]
    targets: list       # [(x, y)]  hidden from the controller


def make_layout(seed: int) -> Layout:
    rng = random.Random(seed)
    nfz = []
    k = rng.randint(2, 4)
    attempts = 0
    while len(nfz) < k and attempts < 1000:
        attempts += 1
        r = rng.uniform(25.0, 55.0)
        cx = rng.uniform(60.0, FIELD_W - 30.0)
        cy = rng.uniform(40.0, FIELD_H - 30.0)
        if math.dist((cx, cy), HOME) <= r + 40.0:
            continue
        if any(math.dist((cx, cy), (ox, oy)) <= r + orad + 30.0 for ox, oy, orad in nfz):
            continue
        nfz.append((round(cx, 3), round(cy, 3), round(r, 3)))
    targets = []
    attempts = 0
    while len(targets) < N_TARGETS and attempts < 100000:
        attempts += 1
        x = rng.uniform(10.0, FIELD_W - 10.0)
        y = rng.uniform(10.0, FIELD_H - 10.0)
        if math.dist((x, y), HOME) <= 30.0:
            continue
        if any(math.dist((x, y), (cx, cy)) <= r + 8.0 for cx, cy, r in nfz):
            continue
        if any(math.dist((x, y), t) < 10.0 for t in targets):
            continue
        targets.append((round(x, 3), round(y, 3)))
    assert len(targets) == N_TARGETS, seed
    return Layout(seed, nfz, targets)


def mission_info(layout: Layout) -> dict:
    """Static info given to Controller.__init__. No marker positions.
    (Internally the code says "targets"; the model-facing API says "survey markers".)"""
    return {
        "field": {"width": FIELD_W, "height": FIELD_H},
        "home": [HOME[0], HOME[1]],
        "home_radius": HOME_RADIUS,
        "no_fly_zones": [{"center": [cx, cy], "radius": r} for cx, cy, r in layout.no_fly_zones],
        "sensor_radius": SENSOR_RADIUS,
        "max_speed": MAX_SPEED,
        "max_accel": MAX_ACCEL,
        "dt": DT,
        "time_limit": TIME_LIMIT,
        "n_markers": N_TARGETS,
        "battery_model": {"idle_drain_per_s": IDLE_DRAIN, "drain_per_s_per_mps": SPEED_DRAIN},
    }


def _seg_circle_hit(p0, p1, c, r) -> bool:
    """True if segment p0->p1 passes strictly inside circle (c, r)."""
    (x0, y0), (x1, y1), (cx, cy) = p0, p1, c
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((cx - x0) * dx + (cy - y0) * dy) / L2))
    px, py = x0 + t * dx, y0 + t * dy
    return math.hypot(px - cx, py - cy) < r


class BadCommand(Exception):
    pass


def parse_command(cmd):
    """Controller must return (vx, vy) as two finite numbers."""
    try:
        if isinstance(cmd, dict):
            raise BadCommand("dict")
        seq = list(cmd)
        if len(seq) != 2:
            raise BadCommand(f"len {len(seq)}")
        vx, vy = float(seq[0]), float(seq[1])
    except BadCommand:
        raise
    except Exception as e:  # noqa: BLE001
        raise BadCommand(repr(e)[:200])
    if not (math.isfinite(vx) and math.isfinite(vy)):
        raise BadCommand("non-finite")
    return vx, vy


@dataclass
class Episode:
    layout: Layout
    t: float = 0.0
    pos: list = field(default_factory=lambda: [HOME[0], HOME[1]])
    vel: list = field(default_factory=lambda: [0.0, 0.0])
    battery: float = 1.0
    landed: bool = True
    found: list = field(default_factory=list)       # indices into layout.targets, in order found
    nfz_time: float = 0.0
    nfz_entered: bool = False
    oob_time: float = 0.0
    max_speed_cmd: float = 0.0
    done: bool = False
    end_reason: str = ""

    def observation(self) -> dict:
        return {
            "t": round(self.t, 6),
            "pos": [self.pos[0], self.pos[1]],
            "vel": [self.vel[0], self.vel[1]],
            "battery": max(0.0, self.battery),
            "landed": self.landed,
            "found": [list(self.layout.targets[i]) for i in self.found],
            "n_found": len(self.found),
        }

    def step(self, vx_cmd: float, vy_cmd: float) -> None:
        assert not self.done
        # speed limit on the command
        s = math.hypot(vx_cmd, vy_cmd)
        self.max_speed_cmd = max(self.max_speed_cmd, s)
        if s > MAX_SPEED:
            vx_cmd, vy_cmd = vx_cmd * MAX_SPEED / s, vy_cmd * MAX_SPEED / s
            s = MAX_SPEED
        if self.landed and s <= LAND_SPEED:
            self.t += DT
        else:
            self.landed = False
            dvx, dvy = vx_cmd - self.vel[0], vy_cmd - self.vel[1]
            dv = math.hypot(dvx, dvy)
            lim = MAX_ACCEL * DT
            if dv > lim:
                dvx, dvy = dvx * lim / dv, dvy * lim / dv
            self.vel = [self.vel[0] + dvx, self.vel[1] + dvy]
            p0 = (self.pos[0], self.pos[1])
            self.pos = [self.pos[0] + self.vel[0] * DT, self.pos[1] + self.vel[1] * DT]
            p1 = (self.pos[0], self.pos[1])
            speed = math.hypot(*self.vel)
            self.battery -= (IDLE_DRAIN + SPEED_DRAIN * speed) * DT
            self.t += DT
            for cx, cy, r in self.layout.no_fly_zones:
                if _seg_circle_hit(p0, p1, (cx, cy), r):
                    self.nfz_entered = True
                if math.hypot(p1[0] - cx, p1[1] - cy) < r:
                    self.nfz_time += DT
            x, y = p1
            if x < 0 or y < 0 or x > FIELD_W or y > FIELD_H:
                self.oob_time += DT
            for i, (tx, ty) in enumerate(self.layout.targets):
                if i not in self.found and math.hypot(x - tx, y - ty) <= SENSOR_RADIUS:
                    self.found.append(i)
            if (math.dist(p1, HOME) <= HOME_RADIUS and speed <= LAND_SPEED
                    and s <= LAND_SPEED):
                self.landed = True
                self.vel = [0.0, 0.0]
            if (x < -FLYAWAY_MARGIN or y < -FLYAWAY_MARGIN
                    or x > FIELD_W + FLYAWAY_MARGIN or y > FIELD_H + FLYAWAY_MARGIN):
                self._end("flyaway")
                return
            if self.battery <= 0.0 and not self.landed:
                self.battery = 0.0
                self._end("battery_crash")
                return
        if self.landed and len(self.found) == N_TARGETS:
            self._end("complete_landed")
        elif self.t >= TIME_LIMIT - 1e-9:
            self._end("time_limit")

    def _end(self, reason: str) -> None:
        self.done = True
        self.end_reason = reason

    def result(self) -> dict:
        at_home = self.landed and math.dist(self.pos, HOME) <= HOME_RADIUS
        return {
            "seed": self.layout.seed,
            "found_frac": len(self.found) / N_TARGETS,
            "n_found": len(self.found),
            "end_reason": self.end_reason,
            "rth": bool(at_home and self.end_reason in ("time_limit", "complete_landed")),
            "crash": self.end_reason in ("battery_crash", "flyaway"),
            "exception": self.end_reason in ("exception", "bad_command", "load_error"),
            "timeout": self.end_reason in ("step_timeout", "init_timeout", "cpu_limit"),
            "nfz_entered": self.nfz_entered,
            "nfz_time": self.nfz_time,
            "oob_time": self.oob_time,
            "battery_end": round(max(0.0, self.battery), 6),
            "t_end": round(self.t, 3),
        }
