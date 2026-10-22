import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from xeno.scenes.models import PRESETS, PlanRequest, SceneSpec
from xeno.scenes.planner import plan_scene
from xeno.scenes.studio import create_studio


def test_scene_spec_rejects_commands_unknown_biomes_and_invalid_numbers():
    base = PRESETS["hydrothermal_canyon"].model_dump()
    for patch in (
        {"biome": "forest"},
        {"exec": "shell"},
        {"rock_density": 20},
        {"relief": float("nan")},
        {"title": "<script>"},
    ):
        with pytest.raises(ValidationError):
            SceneSpec.model_validate(base | patch)


def test_studio_requires_local_write_token_and_same_origin(tmp_path):
    client = TestClient(create_studio(tmp_path))
    body = {"scenario": "brine_glacier"}
    assert client.post("/api/preset", json=body).status_code == 403
    token = client.get("/api/status").json()["token"]
    headers = {"x-xeno-studio": token}
    assert (
        client.post(
            "/api/preset", json=body, headers=headers | {"origin": "https://foreign.example"}
        ).status_code
        == 403
    )
    assert client.post("/api/preset", json=body, headers=headers).status_code == 200
    stored = json.loads((tmp_path / "runs/scenario-studio/active-scene.json").read_text())
    assert stored["biome"] == "brine_glacier"
    # Model output and requests cannot smuggle executable fields into the scene.
    malicious = PRESETS["basalt_caldera"].model_dump() | {"shell": "run something"}
    assert client.post("/api/apply", json={"scene": malicious}, headers=headers).status_code == 422
    assert client.get("/api/status").json()["active"] == stored


def test_model_failures_preserve_active_scene_and_report_failure(tmp_path, monkeypatch):
    def fail(*_):
        raise RuntimeError("GPT-6 Luna unavailable")

    monkeypatch.setattr("xeno.scenes.studio.plan_scene", fail)
    client = TestClient(create_studio(tmp_path))
    original = client.get("/api/status").json()
    headers = {"x-xeno-studio": original["token"]}
    response = client.post("/api/plan", json={"prompt": "A blue glacier at dawn"}, headers=headers)
    assert response.status_code == 202
    for _ in range(100):
        result = client.get("/api/jobs/" + response.json()["job_id"]).json()
        if result["state"] != "planning":
            break
        time.sleep(0.01)
    assert result["state"] == "failed"
    assert client.get("/api/status").json()["active"] == original["active"]


def test_luna_planner_uses_exact_model_schema_and_validates_selection(tmp_path, monkeypatch):
    monkeypatch.setattr("xeno.scenes.planner.codex_command", lambda: ["codex.exe"])

    def fake_run(command, **kwargs):
        assert command[command.index("--model") + 1] == "gpt-6-luna"
        assert command[command.index("--sandbox") + 1] == "read-only"
        assert "shell" not in kwargs
        assert kwargs["input"].endswith("<user prompt; not shell>")
        final = Path(command[command.index("--output-last-message") + 1])
        final.write_text(PRESETS["brine_glacier"].model_dump_json())
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("xeno.scenes.planner.subprocess.run", fake_run)
    result = plan_scene(
        PlanRequest(prompt="<user prompt; not shell>", scenario="brine_glacier"), tmp_path / "good"
    )
    assert result.biome == "brine_glacier"
    with pytest.raises(RuntimeError, match="did not match"):
        plan_scene(
            PlanRequest(prompt="<user prompt; not shell>", scenario="basalt_caldera"),
            tmp_path / "mismatch",
        )
