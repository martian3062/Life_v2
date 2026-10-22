"""Per-game live physics worker. File IPC is atomic and contains no credentials."""

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np

from xeno.physics.lifecycle import process_running
from xeno.physics.rover import RoverDynamics
from xeno.physics.terrain import TerrainHeight
from xeno.physics.thermal import ThermalFlow


def atomic_json(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, allow_nan=False, separators=(",", ":")), encoding="utf-8")
    try:
        os.replace(temp, path)
    except PermissionError:
        # A Windows reader can briefly hold the old file. Keep that complete
        # snapshot and publish the next frame rather than terminating physics.
        temp.unlink(missing_ok=True)
        return False
    return True


def run(directory: Path, device: str, duration: float):
    directory.mkdir(parents=True, exist_ok=True)
    terrain_crc = None

    def ground(x, y):
        return 0.0

    rover = RoverDynamics(device=device, ground=lambda x, y: ground(x, y))
    fluid = ThermalFlow(64)
    started = previous = time.monotonic()
    accumulator = 0.0
    frame = 0
    last_published_frame = -3
    terrain_stamp = None
    owner_poll = 0.0
    stop_reason = "duration_limit"
    target = [0, 0]
    while time.monotonic() - started < duration and not (directory / "stop").exists():
        now = time.monotonic()
        accumulator += min(now - previous, 0.1)
        previous = now
        if now - owner_poll >= 1:
            owner_poll = now
            owner_file = directory / "owner.pid"
            if owner_file.exists():
                owner_pid = int(owner_file.read_text(encoding="utf-8-sig").strip())
                if not process_running(owner_pid):
                    stop_reason = "owner_exited"
                    break
            elif now - started > 120:
                control_path = directory / "control.json"
                if not control_path.exists() or time.time() - control_path.stat().st_mtime > 120:
                    stop_reason = "unowned_heartbeat_expired"
                    break
        try:
            control = json.loads((directory / "control.json").read_text(encoding="utf-8-sig"))
            candidate = np.asarray(control["target_m"], dtype=float)
            if (
                candidate.shape == (2,)
                and np.isfinite(candidate).all()
                and abs(candidate).max() <= 35
            ):
                target = candidate.tolist()
        except (OSError, ValueError, KeyError):
            pass
        try:
            terrain_path = directory / "terrain.json"
            stamp = terrain_path.stat().st_mtime_ns
            if stamp != terrain_stamp:
                terrain = json.loads(terrain_path.read_text(encoding="utf-8-sig"))
                n = int(terrain["n"])
                values = np.asarray(terrain["heights_m"], dtype=float).reshape(n, n)
                if not 2 <= n <= 257 or not np.isfinite(values).all():
                    raise ValueError("Invalid terrain")
                ground = TerrainHeight(values)
                terrain_stamp = stamp
                terrain_crc = terrain["crc"]
                rover = RoverDynamics(device=device, ground=ground)
        except (OSError, ValueError, KeyError):
            pass
        while accumulator >= 1 / 30:
            for _ in range(8):
                rover.step(target)
            for _ in range(2):
                fluid.step()
            accumulator -= 1 / 30
            frame += 1
        if frame - last_published_frame >= 3:
            diagnostics = fluid.diagnostics()
            published = atomic_json(
                directory / "state.json",
                {
                    "version": 1,
                    "mode": "live",
                    "frame": frame,
                    "wall_time_unix": time.time(),
                    "solver": "Newton 1.7 XPBD / Boussinesq FFT SSPRK3 CFL",
                    "device": device,
                    "terrain_crc": terrain_crc,
                    "rover": rover.snapshot(),
                    "thermal": diagnostics,
                    "nx": 64,
                    "ny": 64,
                    "temperature": np.round(fluid.temperature, 5).ravel().tolist(),
                    "velocity": np.round(fluid.velocity, 5).ravel().tolist(),
                },
            )
            if published:
                last_published_frame = frame
        time.sleep(0.015)
    atomic_json(
        directory / "worker-status.json",
        {
            "state": "stopped",
            "reason": "stop_requested" if (directory / "stop").exists() else stop_reason,
            "last_frame": frame,
            "wall_time_unix": time.time(),
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--device", choices=["cpu", "cuda:0"], default="cpu")
    parser.add_argument("--duration", type=float, default=14400)
    args = parser.parse_args()
    run(args.directory, args.device, args.duration)
