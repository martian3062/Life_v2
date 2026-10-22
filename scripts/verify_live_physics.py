"""Run in the isolated physics environment; write measured CPU/CUDA fixtures."""

import argparse
import json
from pathlib import Path

import numpy as np

from xeno.physics.rover import RoverDynamics
from xeno.physics.thermal import ThermalFlow


def verify(device):
    rover = RoverDynamics(device)
    for _ in range(480):
        rover.step()
    resting = rover.snapshot()
    load_error = abs(sum(resting["normal_loads_n"]) - 120 * 9.81) / (120 * 9.81)
    assert load_error < 0.005, f"Static force balance failed: {load_error}"
    assert abs(resting["velocity_m_s"][2]) < 0.001
    for _ in range(720):
        rover.step((2, 0))
    driven = rover.snapshot()
    assert 1.6 < driven["position_m"][0] < 2.1
    assert driven["traction_ratio_max"] <= 1.000001
    no_traction = RoverDynamics(device)
    for _ in range(480):
        no_traction.step((2, 0), friction=0)
    assert abs(no_traction.snapshot()["position_m"][0]) < 1e-5
    return {
        "resting": resting,
        "driven": driven,
        "relative_static_load_error": load_error,
        "zero_friction_x_m": no_traction.snapshot()["position_m"][0],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("runs/physics/validation.json"))
    args = parser.parse_args()
    result = {"newton_cpu": verify("cpu"), "newton_cuda": verify("cuda:0")}
    thermal = ThermalFlow()
    for _ in range(600):
        thermal.step()
    result["thermal"] = thermal.diagnostics()
    assert result["thermal"]["divergence_linf"] < 1e-11
    assert np.isfinite(thermal.temperature).all()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    print("CPU, CUDA, static balance, traction and live thermal checks passed.")
