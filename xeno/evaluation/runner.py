import hashlib
import importlib.metadata
import json
import platform
import secrets
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
from fastapi.testclient import TestClient

from xeno import MODEL_VERSION, __version__
from xeno.investigator.policies import EpisodeClient, run_policy
from xeno.service.app import create_app
from xeno.service.schemas import EpisodeConfig
from xeno.simulation.core import FAMILIES


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def provenance() -> dict:
    root = Path(__file__).resolve().parents[1]
    hashes = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*.py"))
    }
    registry = root / "data" / "f0_registry.json"
    hashes["data/f0_registry.json"] = hashlib.sha256(registry.read_bytes()).hexdigest()
    return {
        "xeno_version": __version__,
        "model_version": MODEL_VERSION,
        "python": sys.version,
        "platform": platform.platform(),
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "scipy", "fastapi", "pydantic", "httpx", "httpx2", "uvicorn")
        },
        "source_sha256": hashes,
        "replay_mode": "recorded_observations",
        "evidence_class": "hypothetical",
        "dataset_split": "development_smoke_only",
    }


def execute_episode(
    transport, admin_token: str, config: EpisodeConfig, policy: str, output: Path | None = None
) -> dict:
    started = perf_counter()
    admin = {"Authorization": f"Bearer {admin_token}"}
    created_response = transport.post("/v1/admin/episodes", headers=admin, json=config.model_dump())
    created_response.raise_for_status()
    created = created_response.json()
    episode_id = created["episode_id"]
    client = EpisodeClient(transport, episode_id, created["investigator_token"])
    report = run_policy(client, policy)
    evaluated = transport.get(f"/v1/admin/episodes/{episode_id}/evaluation", headers=admin)
    evaluated.raise_for_status()
    evaluation = evaluated.json()
    evaluation["wall_clock_s"] = perf_counter() - started
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        events = client.get("/events")["events"]
        with (output / "observations.jsonl").open("w", encoding="utf-8") as stream:
            for event in events:
                stream.write(json.dumps(event, allow_nan=False) + "\n")
        checkpoint_response = transport.get(
            f"/v1/admin/episodes/{episode_id}/checkpoint", headers=admin
        )
        checkpoint_response.raise_for_status()
        checkpoint = checkpoint_response.json()
        write_json(output / "checkpoint.private.json", checkpoint)
        write_json(output / "evaluation.private.json", evaluation)
        write_json(output / "report.json", report)
        write_json(output / "metadata.json", provenance())
        np.savez_compressed(
            output / "fields.private.npz",
            amounts_token=checkpoint["grid"],
            volume_m3=checkpoint["volumes"],
        )
    return {**report, "evaluation": evaluation}


def demo(output: Path, config: EpisodeConfig, policy: str) -> dict:
    if output.exists():
        raise ValueError("Output directory already exists; choose a new run name")
    admin_token = secrets.token_urlsafe(32)
    with TestClient(create_app(output / "xeno.private.sqlite3", admin_token)) as client:
        return execute_episode(client, admin_token, config, policy, output)


def summarize(records: list[dict]) -> dict:
    targets = [int(r["evaluation"]["target"]) for r in records]
    predictions = [r["score"] >= 0.5 for r in records]
    positives, negatives = sum(targets), len(targets) - sum(targets)
    return {
        "episodes": len(records),
        "tpr_at_0_5": sum(p and y for p, y in zip(predictions, targets, strict=True)) / positives
        if positives
        else None,
        "fpr_at_0_5": sum(p and not y for p, y in zip(predictions, targets, strict=True))
        / negatives
        if negatives
        else None,
        "brier_uncalibrated": float(np.mean([r["evaluation"]["brier_score"] for r in records])),
        "coverage": float(np.mean([r["outcome"] != "inconclusive" for r in records])),
        "mean_mission_time_s": float(
            np.mean([r["evaluation"]["costs"]["mission_time_s"] for r in records])
        ),
        "mean_lab_actions": float(
            np.mean([r["evaluation"]["costs"]["lab_actions"] for r in records])
        ),
        "max_inventory_residual_token": max(
            r["evaluation"]["global_inventory_residual_token"] for r in records
        ),
    }


def benchmark(output: Path, seeds: int) -> dict:
    if output.exists():
        raise ValueError("Output directory already exists; choose a new run name")
    if not 1 <= seeds <= 100:
        raise ValueError("Seeds per family must be between 1 and 100")
    admin_token = secrets.token_urlsafe(32)
    records = []
    with TestClient(create_app(output / "xeno.private.sqlite3", admin_token)) as client:
        for family in FAMILIES:
            for seed in range(seeds):
                for policy in ("passive", "random", "fixed", "adaptive"):
                    result = execute_episode(
                        client,
                        admin_token,
                        EpisodeConfig(family=family, seed=1042 + seed),
                        policy,
                        output / f"{family}-{seed}-{policy}",
                    )
                    records.append(result)
    summary = {
        "scope": "development smoke comparison; no held-out mechanisms or fitted thresholds",
        "threshold": 0.5,
        "seeds_per_family": seeds,
        "mechanism_families": len(FAMILIES),
        "budget_setting": EpisodeConfig().model_dump(exclude={"family", "seed"}),
        "paired_worlds": True,
        "policies": {
            p: summarize([r for r in records if r["policy"] == p])
            for p in ("passive", "random", "fixed", "adaptive")
        },
        "per_family": {
            f: {
                p: summarize(
                    [
                        r
                        for r in records
                        if r["policy"] == p and r["evaluation"]["private_family"] == f
                    ]
                )
                for p in ("passive", "random", "fixed", "adaptive")
            }
            for f in FAMILIES
        },
    }
    write_json(output / "summary.private.json", summary)
    return summary


def replay(path: Path) -> dict:
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not events:
        raise ValueError("Empty replay")
    if [e["event_sequence"] for e in events] != list(range(len(events))):
        raise ValueError("Replay has missing or reordered events")
    if len({e["episode_id"] for e in events}) != 1:
        raise ValueError("Replay mixes episodes")
    return {
        "mode": "recorded_observations",
        "events": len(events),
        "episode_id": events[-1]["episode_id"],
        "final_status": events[-1]["status"],
        "simulation_time_s": events[-1]["simulation_time_s"],
        "conclusion": events[-1]["conclusion"],
    }
