import json
import os
import secrets
import subprocess
import threading
import uuid
import zlib
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from starlette.middleware.trustedhost import TrustedHostMiddleware

from xeno.scenes.authoring import try_author_scene
from xeno.scenes.models import PRESETS, PlanRequest, SceneSpec
from xeno.scenes.planner import MODEL, codex_command, plan_scene


class ApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene: SceneSpec


class PresetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: Literal["hydrothermal_canyon", "brine_glacier", "basalt_caldera"]


def create_studio(workspace: Path, data_dir: Path | None = None) -> FastAPI:
    workspace = workspace.resolve()
    data_dir = (data_dir or workspace / "runs/scenario-studio").resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    active = data_dir / "active-scene.json"
    if not active.exists():
        active.write_text(
            PRESETS["hydrothermal_canyon"].model_dump_json(indent=2), encoding="utf-8"
        )
    token = secrets.token_urlsafe(32)
    app = FastAPI(title="XENO Scenario Studio", docs_url=None, redoc_url=None)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )
    jobs: dict[str, dict] = {}
    lock = threading.Lock()
    launcher: subprocess.Popen | None = None

    @app.middleware("http")
    async def local_mutations(request: Request, call_next):
        from fastapi.responses import JSONResponse

        if request.method == "POST":
            if request.headers.get("x-xeno-studio") != token:
                return JSONResponse({"detail": "Reload the local studio page."}, status_code=403)
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "Local studio requests only."}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def apply(spec: SceneSpec):
        temp = data_dir / f"{uuid.uuid4().hex}.tmp"
        temp.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temp, active)

    @app.get("/")
    def index():
        return FileResponse(Path(__file__).parent / "static/index.html")

    @app.get("/api/status")
    def status():
        rendered_path = data_dir / "scene-status.json"
        try:
            rendered = json.loads(rendered_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            rendered = None
        physics_path = workspace / "runs/well/reference-field.manifest.json"
        physics = json.loads(physics_path.read_text()) if physics_path.exists() else None
        return {
            "model": MODEL,
            "planner_available": codex_command() is not None,
            "token": token,
            "active": json.loads(active.read_text(encoding="utf-8")),
            "presets": {key: spec.model_dump() for key, spec in PRESETS.items()},
            "package_ready": (workspace / "runs/unreal-package/Windows/Xeno.exe").exists(),
            "rendered": rendered,
            "physics_reference": physics,
            "spec_crc": zlib.crc32(active.read_bytes()),
            "authoring": json.loads(
                (data_dir / "authoring-status.json").read_text(encoding="utf-8-sig")
            )
            if (data_dir / "authoring-status.json").exists()
            else None,
        }

    @app.get("/api/preview/{scenario}")
    def preview(scenario: str):
        if scenario not in PRESETS:
            raise HTTPException(404, "Unknown scene.")
        path = data_dir / "previews" / f"{scenario}.png"
        if not path.exists():
            raise HTTPException(404, "No captured preview yet.")
        return FileResponse(path)

    @app.post("/api/preset")
    def preset(body: PresetRequest):
        spec = PRESETS[body.scenario]
        apply(spec)
        return {"scene": spec.model_dump(), "source": "preset"}

    @app.post("/api/apply")
    def apply_scene(body: ApplyRequest):
        apply(body.scene)
        return {"scene": body.scene.model_dump(), "source": "edited_plan"}

    @app.post("/api/plan", status_code=202)
    def plan(body: PlanRequest):
        with lock:
            if any(job["state"] == "planning" for job in jobs.values()):
                raise HTTPException(409, "A scene is already being planned.")
            job_id = uuid.uuid4().hex
            jobs[job_id] = {"state": "planning", "model": MODEL}

        def work():
            try:
                spec = plan_scene(body, data_dir / job_id)
                apply(spec)
                value = {"state": "applied", "model": MODEL, "scene": spec.model_dump()}
                value["authoring"] = try_author_scene(active, workspace)
            except Exception as exc:
                value = {
                    "state": "failed",
                    "error": str(exc)
                    if isinstance(exc, RuntimeError)
                    else "The planner returned an invalid scene. No scene was applied.",
                }
            with lock:
                jobs[job_id] = value

        threading.Thread(target=work, daemon=True).start()
        return {"job_id": job_id}

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str):
        with lock:
            if job_id not in jobs:
                raise HTTPException(404, "Unknown planning job.")
            return jobs[job_id]

    @app.post("/api/launch")
    def launch():
        nonlocal launcher
        with lock:
            if launcher and launcher.poll() is None:
                return {"state": "running", "message": "Unreal is open; scene changes apply live."}
            if not (workspace / "runs/unreal-package/Windows/Xeno.exe").exists():
                raise HTTPException(409, "Build the Unreal package first.")
            command = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(workspace / "scripts/Run-XenoUnreal.ps1"),
                "-Mode",
                "Packaged",
                "-SceneFile",
                str(active),
                "-WaitForGame",
                "-CleanView",
            ]
            log = (data_dir / "launch.log").open("w", encoding="utf-8")
            launcher = subprocess.Popen(
                command,
                cwd=workspace,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            log.close()
        return {"state": "launching", "message": "Launching Unreal. See the game window."}

    @app.post("/api/author")
    def author():
        return try_author_scene(active, workspace)

    return app
