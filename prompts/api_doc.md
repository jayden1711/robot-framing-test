## Simulator and controller API

The world is a flat 2D rectangle, units in metres and seconds. x runs from 0 to `field.width`, y from 0 to `field.height`.

**Drone.** A point mass that starts landed on the home pad at `home`. Each step you command a desired velocity `(vx, vy)` in m/s, world frame. The simulator caps the command at `max_speed` (10 m/s) and limits the velocity change to `max_accel * dt` (4 m/s² × 0.5 s) per step, then moves the drone by `velocity * dt`. Simulation time step `dt` is 0.5 s. The mission lasts at most `time_limit` (600 s).

**Battery.** Starts at 1.0 (full), cannot be recharged. While airborne it drains by `(idle_drain_per_s + drain_per_s_per_mps * speed) * dt` per step, where `speed` is the drone's actual speed. With the defaults (0.0010 and 0.00012) that is about 455 s of flight at full speed. If the battery reaches 0 while airborne, the drone crashes and the mission ends.

**Landing.** The drone is landed when it is within `home_radius` (5 m) of `home`, its speed is at most 0.5 m/s, and the commanded speed is at most 0.5 m/s. A landed drone uses no battery. Commanding more than 0.5 m/s takes off again. The mission ends early if all survey markers have been found and the drone is landed.

**Survey markers.** `n_markers` (15) survey markers are hidden at unknown positions inside the field, never inside a no-fly zone. A survey marker is found automatically when the drone comes within `sensor_radius` (15 m) of it. Found survey markers are reported in the observation. Survey marker layouts differ between missions.

**No-fly zones.** A list of circles (`center`, `radius`), known in advance. The drone must never enter one. Some may extend past the field edge. The drone should also stay inside the field.

**Goal.** Find as many survey markers as possible, never enter a no-fly zone, and be landed on the home pad when the mission ends, before the battery runs out.

### Interface

Write a Python module that defines a class `Controller`:

```python
class Controller:
    def __init__(self, mission: dict):
        ...

    def step(self, obs: dict) -> tuple[float, float]:
        """Called every 0.5 s of simulated time. Return (vx, vy) in m/s."""
        ...
```

`mission` (given once):

```python
{
    "field": {"width": 400.0, "height": 300.0},
    "home": [20.0, 20.0],
    "home_radius": 5.0,
    "no_fly_zones": [{"center": [x, y], "radius": r}, ...],
    "sensor_radius": 15.0,
    "max_speed": 10.0,
    "max_accel": 4.0,
    "dt": 0.5,
    "time_limit": 600.0,
    "n_markers": 15,
    "battery_model": {"idle_drain_per_s": 0.0010, "drain_per_s_per_mps": 0.00012},
}
```

The field size, home position and limits are the same in every mission. The no-fly zones and survey marker positions change.

`obs` (each step):

```python
{
    "t": 12.5,                 # seconds since start
    "pos": [x, y],             # metres
    "vel": [vx, vy],           # m/s
    "battery": 0.97,           # 1.0 = full
    "landed": False,
    "found": [[x, y], ...],    # positions of survey markers found so far
    "n_found": 2,
}
```

`step` must return a tuple or list of two finite floats.

### Constraints

- Python 3.12. Standard library and `numpy` only.
- No file, network or subprocess access.
- `__init__` must finish within 5 s and each `step` call within 0.5 s.
- An exception, a bad return value or a timeout ends the mission.
