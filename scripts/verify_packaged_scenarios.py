"""Visible packaged integration checks; leave the final canyon open for review.

Requires the local trusted service and Scenario Studio. Private evaluator output
stays under ignored runs. This script never prints credentials.
"""

import hashlib
import json
import re
import shutil
import struct
import subprocess
import time
from pathlib import Path

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/canyon-final-verification"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    studio = httpx.Client(base_url="http://127.0.0.1:8770", timeout=15)
    credential = read(ROOT / "runs/local/credentials.private.json")["admin_token"]
    admin = httpx.Client(
        base_url="http://127.0.0.1:8766",
        timeout=15,
        headers={"Authorization": "Bearer " + credential},
    )
    status = studio.get("/api/status").json()
    headers = {"X-Xeno-Studio": status["token"]}
    original = status["active"]
    assert original["biome"] == "hydrothermal_canyon", "Select the reviewed canyon first"
    cases = {}
    for biome in ["brine_glacier", "basalt_caldera", "hydrothermal_canyon"]:
        if biome == "hydrothermal_canyon":
            response = studio.post("/api/apply", headers=headers, json={"scene": original})
        else:
            response = studio.post("/api/preset", headers=headers, json={"scenario": biome})
        response.raise_for_status()
        launched = studio.post("/api/launch", headers=headers, json={})
        launched.raise_for_status()
        assert launched.json()["state"] == "launching", "An existing game must be closed first"
        deadline = time.monotonic() + 150
        run = None
        while time.monotonic() < deadline:
            log = (ROOT / "runs/scenario-studio/launch.log").read_text(
                encoding="utf-8-sig", errors="replace"
            )
            match = re.search(r"Run artifacts: (.+)", log)
            if match:
                candidate = Path(match.group(1).strip())
                if (candidate / "preview.png").exists() and (
                    candidate / "runtime-check.json"
                ).exists():
                    run = candidate
                    break
            time.sleep(0.5)
        assert run is not None, f"No packaged capture for {biome}"
        runtime = read(run / "runtime-check.json")
        assert runtime["success"] and runtime["requires_cooked_data"]
        assert runtime["scene_biome"] == biome
        assert runtime["final_revision"] == 6 and runtime["stream_events"] == 7
        evaluation = admin.get(f"/v1/admin/episodes/{runtime['episode_id']}/evaluation").json()
        assert evaluation["costs"]["lab_actions"] == 1
        assert abs(evaluation["costs"]["sample_volume_m3"] - 2e-7) < 1e-18
        assert evaluation["global_inventory_residual_token"] < 1e-15
        native = read(run / "physics/native-status.json")
        first = read(run / "physics/state.json")
        time.sleep(2)
        second = read(run / "physics/state.json")
        assert native["live_physics"] and second["frame"] > first["frame"]
        assert np.isfinite(second["temperature"]).all()
        assert second["thermal"]["divergence_linf"] < 1e-9
        assert np.isfinite(second["rover"]["position_m"]).all()
        assert second["rover"]["traction_ratio_max"] <= 1.00001
        log = (run / "unreal.log").read_text(errors="replace")
        assert "LogD3D12RHI" in log and "SM6" in log
        assert "Fatal error" not in log and "Assertion failed" not in log
        screenshot = ROOT / "runs/scenario-studio/previews" / f"{biome}.png"
        shutil.copyfile(run / "preview.png", screenshot)
        dimensions = struct.unpack(">II", screenshot.read_bytes()[16:24])
        assert dimensions == (1280, 800)
        cases[biome] = {
            "run": str(run),
            "runtime": runtime,
            "evaluation": evaluation,
            "native": native,
            "physics": second["thermal"],
            "rover": second["rover"],
            "preview": str(screenshot),
            "preview_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
        }
        print(f"Packaged {biome}: mission, DX12/SM6, live physics and capture passed", flush=True)
        (OUT / "verification.private.json").write_text(json.dumps({"cases": cases}, indent=2))
        if biome != "hydrothermal_canyon":
            subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-File",
                    str(ROOT / "scripts/Close-XenoGame.ps1"),
                    (run / "launcher.pid").read_text().strip(),
                ],
                check=True,
            )
            time.sleep(0.5)
    print("Final canyon left open for review.", flush=True)


if __name__ == "__main__":
    main()
