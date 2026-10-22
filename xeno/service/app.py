import asyncio
import os
import secrets
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from xeno import MODEL_VERSION, __version__
from xeno.service.engine import DomainError, evaluation, observation
from xeno.service.schemas import ActionRequest, ConclusionRequest, EpisodeConfig
from xeno.service.store import Store
from xeno.simulation.core import NumericalError

CATALOG = {
    "schema_version": "1.0",
    "execution_mode": "synchronous_at_decision_boundary",
    "actions": [
        {
            "action_type": "move",
            "parameters": {"site_id": "observed site"},
            "cost": {"mission_time_s": "distance_m / 0.01", "battery_j": "100 * distance_m"},
        },
        {
            "action_type": "observe_site",
            "parameters": {"site_id": "current site"},
            "cost": {"mission_time_s": 1, "battery_j": 1, "instrument_readings": 1},
        },
        {
            "action_type": "collect_sample",
            "parameters": {"site_id": "current site", "volume_m3": "[1e-12, 1e-6]"},
            "cost": {"mission_time_s": 2, "battery_j": 2, "containers": 1},
        },
        {
            "action_type": "split_sample",
            "parameters": {"sample_id": "unused original"},
            "cost": {"mission_time_s": 1, "battery_j": 1, "additional_containers": 1},
            "allocation": "equal-volume siblings; original consumed",
        },
        {
            "action_type": "run_intervention",
            "parameters": {
                "control_id": "unused sibling",
                "treatment_id": "unused sibling",
                "duration_s": "[10, 120]",
                "intervention": ["resource_pulse", "temperature_shift"],
            },
            "cost": {
                "mission_time_s": "duration_s",
                "battery_j": 5,
                "lab_actions": 1,
                "instrument_readings": 18,
            },
            "effects": {
                "resource_pulse": "+2 token/m3 resource to treatment",
                "temperature_shift": "+10 K to treatment (supported range 285–315 K)",
            },
        },
        {
            "action_type": "wait_and_measure",
            "parameters": {"site_id": "current site", "duration_s": "[1, 120]"},
            "cost": {"mission_time_s": "duration_s", "battery_j": 1, "instrument_readings": 1},
        },
        {
            "action_type": "submit_conclusion",
            "cost": {},
            "effect": "freeze evidence-linked report and terminate episode",
        },
    ],
    "instrument": {
        "id": "synthetic_concentration_v1",
        "channels": ["resource", "structure", "waste"],
        "unit": "token/m3",
        "standard_uncertainty": 0.04,
        "detection_limit": 0.08,
        "censoring": "value=null below detection limit",
        "noise": "independent Gaussian",
        "camera": "deferred until Unreal integration",
    },
    "sampling": (
        "ideal preservation; variable-volume transport; empty source cells have sealed faces"
    ),
    "errors": "invalid or numerically invalid actions roll back all costs and effects",
}


def create_app(db_path: str | Path, admin_token: str) -> FastAPI:
    if len(admin_token) < 24:
        raise ValueError("Use an admin token of at least 24 characters")
    app = FastAPI(
        title="XENO headless investigation API",
        version=__version__,
        description="Hypothetical F0 token models. Local research prototype.",
    )
    store = Store(db_path)
    app.state.store = store
    security = HTTPBearer(auto_error=False)

    def bearer(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    ) -> str:
        if credentials is None:
            raise HTTPException(401, "Bearer credential required")
        return credentials.credentials

    def admin(token: str = Depends(bearer)):
        if not secrets.compare_digest(token, admin_token):
            raise HTTPException(403, "Evaluator credential required")

    def investigator(episode_id: str, token: str = Depends(bearer)):
        if not store.authorized(episode_id, token):
            raise HTTPException(403, "Episode-scoped investigator credential required")

    @app.exception_handler(DomainError)
    async def domain_error(_request: Request, exc: DomainError):
        return JSONResponse(
            status_code=exc.status,
            content={"status": "invalid_request", "error": exc.code, "message": str(exc)},
        )

    @app.exception_handler(NumericalError)
    async def numerical_error(_request: Request, exc: NumericalError):
        return JSONResponse(
            status_code=422, content={"status": "numerically_invalid", "error": str(exc)}
        )

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__, "model_version": MODEL_VERSION}

    @app.post("/v1/admin/episodes", dependencies=[Depends(admin)], status_code=201)
    def create(config: EpisodeConfig):
        return store.create(config)

    @app.get("/v1/admin/episodes/{episode_id}/evaluation", dependencies=[Depends(admin)])
    def evaluate(episode_id: str):
        return evaluation(store.state(episode_id))

    @app.get("/v1/admin/episodes/{episode_id}/checkpoint", dependencies=[Depends(admin)])
    def checkpoint(episode_id: str):
        return store.state(episode_id)

    @app.get("/v1/episodes/{episode_id}/observation", dependencies=[Depends(investigator)])
    def observe(episode_id: str):
        return observation(store.state(episode_id))

    @app.get("/v1/episodes/{episode_id}/actions", dependencies=[Depends(investigator)])
    def actions(episode_id: str):
        state = store.state(episode_id)
        return {
            **CATALOG,
            "episode_id": episode_id,
            "state_revision": state["revision"],
            "remaining_budget": state["budget"],
            "closed": state["conclusion"] is not None,
        }

    @app.post("/v1/episodes/{episode_id}/actions", dependencies=[Depends(investigator)])
    def action(episode_id: str, request: ActionRequest):
        return store.action(episode_id, request)

    @app.post("/v1/episodes/{episode_id}/conclusion", dependencies=[Depends(investigator)])
    def conclude(episode_id: str, request: ConclusionRequest):
        return store.action(
            episode_id, ActionRequest(**request.model_dump(), action_type="submit_conclusion")
        )

    @app.get("/v1/episodes/{episode_id}/jobs/{job_id}", dependencies=[Depends(investigator)])
    def job(episode_id: str, job_id: str):
        return store.result(episode_id, job_id)

    @app.get("/v1/episodes/{episode_id}/events", dependencies=[Depends(investigator)])
    def events(episode_id: str, after: int = Query(default=-1, ge=-1)):
        return {"events": store.events(episode_id, after)}

    @app.websocket("/v1/episodes/{episode_id}/stream")
    async def stream(websocket: WebSocket, episode_id: str, after: int = -1):
        header = websocket.headers.get("authorization", "")
        token = header[7:] if header.startswith("Bearer ") else ""
        if not store.authorized(episode_id, token):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        try:
            while True:
                events = await asyncio.to_thread(store.events, episode_id, after)
                for event in events:
                    await websocket.send_json({"type": "observation", "observation": event})
                    after = event["event_sequence"]
                # Receive ping/resync commands with a bounded wait; poll committed events.
                try:
                    message = await asyncio.wait_for(websocket.receive_json(), timeout=0.2)
                    if (
                        isinstance(message, dict)
                        and message.get("type") == "resync"
                        and isinstance(message.get("after"), int)
                        and message["after"] >= -1
                    ):
                        after = message["after"]
                    else:
                        await websocket.send_json({"type": "ack", "event_sequence": after})
                except TimeoutError:
                    pass
        except (WebSocketDisconnect, RuntimeError, ValueError):
            return

    return app


def from_environment() -> FastAPI:
    token = os.environ.get("XENO_ADMIN_TOKEN", "")
    if not token:
        raise RuntimeError("Set XENO_ADMIN_TOKEN, or run 'xeno serve' to create local credentials")
    return create_app(os.environ.get("XENO_DB_PATH", "runs/local/xeno.sqlite3"), token)
