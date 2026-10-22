"""Pure state transitions; persistence admits the entire transition atomically."""

import copy
import uuid

import numpy as np

from xeno import MODEL_VERSION
from xeno.laboratory.experiments import paired_experiment
from xeno.observations.sensors import derived_seed, measure
from xeno.service.schemas import ActionRequest, EpisodeConfig
from xeno.simulation.core import TARGET_FAMILIES, NumericalError, compartment_transport, react

CELL_VOLUME = 1e-6
CELL_WIDTH = 0.01
MIN_VOLUME = 1e-12


class DomainError(ValueError):
    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code, self.status = code, status


def opaque(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def new_state(config: EpisodeConfig, episode_id: str) -> dict:
    cfg = config.model_dump()
    n = cfg["grid_size"]
    rng = np.random.default_rng(derived_seed(cfg["seed"], "environment"))
    concentrations = np.zeros((n, n, 3))
    concentrations[..., 0] = rng.uniform(7, 9, (n, n))
    concentrations[..., 1] = rng.uniform(1.8, 2.2, (n, n))
    appearance = np.random.default_rng(derived_seed(cfg["seed"], "appearance"))
    state = {
        "episode_id": episode_id,
        "model_version": MODEL_VERSION,
        "config": cfg,
        "revision": 0,
        "simulation_time_s": 0.0,
        "sensor_sequence": 0,
        "grid": (concentrations * CELL_VOLUME).tolist(),
        "volumes": np.full((n, n), CELL_VOLUME).tolist(),
        "rate_scale": float(
            np.random.default_rng(derived_seed(cfg["seed"], "mechanism")).uniform(0.85, 1.15)
        ),
        "sites": [
            {
                "site_id": opaque("site"),
                "cell": [x, y],
                "position_m": [x * CELL_WIDTH, y * CELL_WIDTH],
                "appearance": {
                    "hue": float(appearance.uniform()),
                    "roughness": float(appearance.uniform(0.2, 0.9)),
                },
            }
            for x, y in ((0, 0), (n - 1, 0), (n - 1, n - 1), (0, n - 1))
        ],
        "position_m": [0.0, 0.0],
        "samples": {},
        "experiments": [],
        "budget": {
            "mission_time_s": cfg["duration_s"],
            "battery_j": cfg["battery_j"],
            "lab_actions": cfg["lab_actions"],
            "instrument_readings": cfg["instrument_readings"],
        },
        "costs": {
            "mission_time_s": 0.0,
            "battery_j": 0.0,
            "lab_actions": 0,
            "instrument_readings": 0,
            "sample_volume_m3": 0.0,
        },
        "ledger": {"external_in_token": 0.0, "external_out_token": 0.0},
        "diagnostics": {
            "max_solver_residual_token": 0.0,
            "solver_substeps": 0,
            "floating_point_correction_token": 0.0,
        },
        "conclusion": None,
        "evidence_ids": [],
        "last_result": None,
    }
    state["initial_inventory_token"] = inventory(state)
    return state


def inventory(state: dict) -> float:
    return float(np.sum(state["grid"])) + sum(
        float(np.sum(s["amounts"])) for s in state["samples"].values()
    )


def reconcile(state: dict) -> float:
    expected = (
        state["initial_inventory_token"]
        + state["ledger"]["external_in_token"]
        - state["ledger"]["external_out_token"]
    )
    actual = inventory(state)
    residual = abs(expected - actual)
    if not np.isfinite(actual) or residual > max(abs(expected) * 1e-9, 1e-20):
        raise NumericalError("World, sample and reagent ledgers do not reconcile")
    state["diagnostics"]["global_inventory_residual_token"] = residual
    return residual


def observation(state: dict) -> dict:
    # Explicit allowlist. Never serialize state/config and then remove private keys.
    return {
        "schema_version": "1.0",
        "episode_id": state["episode_id"],
        "observation_id": f"observation_{state['revision']}",
        "state_revision": state["revision"],
        "event_sequence": state["revision"],
        "simulation_time_s": state["simulation_time_s"],
        "status": "concluded" if state["conclusion"] else "active",
        "position_m": state["position_m"],
        "sites": [
            {k: s[k] for k in ("site_id", "position_m", "appearance")} for s in state["sites"]
        ],
        "samples": [
            {
                "sample_id": key,
                **{
                    k: s[k] for k in ("volume_m3", "source_site_id", "parent_id", "pair_id", "used")
                },
            }
            for key, s in state["samples"].items()
            if s["volume_m3"] > 0
        ],
        "remaining_budget": state["budget"],
        "sample_capacity": state["config"]["max_containers"],
        "cumulative_costs": state["costs"],
        "result": state["last_result"],
        "conclusion": state["conclusion"],
        "quality_flags": [
            "synthetic_F0_tokens",
            "ideal_sample_preservation",
            "no_camera_connected",
            "aggregate_maintenance_no_individual_replication",
        ],
    }


def charge(state: dict, seconds=0.0, battery=0.0, lab=0, readings=0):
    requested = {
        "mission_time_s": seconds,
        "battery_j": battery,
        "lab_actions": lab,
        "instrument_readings": readings,
    }
    for name, value in requested.items():
        if state["budget"][name] + 1e-12 < value:
            raise DomainError("insufficient_budget", f"Insufficient {name}")
    for name, value in requested.items():
        state["budget"][name] -= value
        state["costs"][name] += value


def advance_world(state: dict, seconds: float):
    cfg = state["config"]
    grid = np.asarray(state["grid"])
    volumes = np.asarray(state["volumes"])
    steps = max(1, int(np.ceil(seconds / cfg["solver_step_s"])))
    dt = seconds / steps
    if dt > 0:
        transport = compartment_transport(volumes, 1e-7, CELL_WIDTH, dt)
        for _ in range(steps):
            grid = transport(grid)
            grid, diagnostic = react(
                grid,
                np.where(volumes > 0, volumes, CELL_VOLUME),
                cfg["family"],
                dt,
                temperature_K=cfg["temperature_K"],
                rate_scale=state["rate_scale"],
                max_step_s=dt,
            )
            state["diagnostics"]["solver_substeps"] += diagnostic["substeps"]
            state["diagnostics"]["max_solver_residual_token"] = max(
                state["diagnostics"]["max_solver_residual_token"],
                diagnostic["inventory_residual_token"],
            )
    state["grid"] = grid.tolist()
    state["simulation_time_s"] += seconds


def at_site(state: dict, site_id: str) -> dict:
    site = next((s for s in state["sites"] if s["site_id"] == site_id), None)
    if site is None:
        raise DomainError("unknown_site", "Site was not disclosed by this episode", 404)
    return site


def reachable(state: dict, site: dict):
    if np.linalg.norm(np.array(state["position_m"]) - site["position_m"]) > 1e-9:
        raise DomainError("out_of_range", "Move to the site before using the instrument or sampler")


def sensor(state: dict, concentrations):
    seq = state["sensor_sequence"]
    state["sensor_sequence"] += 1
    return measure(concentrations, state["config"]["seed"], seq)


def read_site(state: dict, site: dict) -> dict:
    x, y = site["cell"]
    volume = state["volumes"][x][y]
    if volume <= 0:
        raise DomainError("empty_site", "No sample material remains")
    return {
        "site_id": site["site_id"],
        "instrument_id": "synthetic_concentration_v1",
        "temperature_K": state["config"]["temperature_K"],
        "measurements": sensor(state, np.asarray(state["grid"][x][y]) / volume),
    }


def _sample(state: dict, sample_id: str) -> dict:
    sample = state["samples"].get(sample_id)
    if sample is None or sample["volume_m3"] <= 0:
        raise DomainError("unknown_sample", "No usable sample with this identifier", 404)
    return sample


def apply_action(original: dict, request: ActionRequest) -> tuple[dict, dict]:
    if request.episode_id != original["episode_id"]:
        raise DomainError("episode_mismatch", "Body and route episode identifiers differ", 422)
    if request.expected_state_revision != original["revision"]:
        raise DomainError("stale_revision", "Refresh observation before submitting a new action")
    if original["conclusion"] is not None:
        raise DomainError("episode_closed", "The conclusion is already frozen")
    state = copy.deepcopy(original)
    kind, p = request.action_type, request.parameters
    seconds = 0.0
    result = {}
    if kind in ("move", "observe_site", "collect_sample", "wait_and_measure"):
        site = at_site(state, p["site_id"])
        if kind != "move":
            reachable(state, site)
        if kind == "move":
            distance = float(np.linalg.norm(np.array(state["position_m"]) - site["position_m"]))
            seconds = distance / 0.01
            charge(state, seconds, distance * 100)
            state["position_m"] = site["position_m"].copy()
            result = {"distance_m": distance}
        elif kind in ("observe_site", "wait_and_measure"):
            seconds = 1.0 if kind == "observe_site" else p["duration_s"]
            charge(state, seconds, 1.0, readings=1)
        else:
            volume = p["volume_m3"]
            if volume < MIN_VOLUME:
                raise DomainError("sample_too_small", "Minimum sample volume is 1e-12 m3", 422)
            active = sum(s["volume_m3"] > 0 for s in state["samples"].values())
            if active >= state["config"]["max_containers"]:
                raise DomainError("container_capacity", "No empty container remains")
            x, y = site["cell"]
            remaining = state["volumes"][x][y]
            if volume > remaining:
                raise DomainError(
                    "insufficient_material", "Requested volume exceeds site inventory"
                )
            charge(state, 2.0, 2.0)
            amounts = np.array(state["grid"][x][y]) * (volume / remaining)
            state["grid"][x][y] = (np.array(state["grid"][x][y]) - amounts).tolist()
            state["volumes"][x][y] -= volume
            sample_id = opaque("sample")
            state["samples"][sample_id] = {
                "amounts": amounts.tolist(),
                "volume_m3": volume,
                "source_site_id": p["site_id"],
                "parent_id": None,
                "pair_id": None,
                "used": False,
            }
            state["costs"]["sample_volume_m3"] += volume
            seconds, result = 2.0, {"sample_id": sample_id, "volume_m3": volume}
        advance_world(state, seconds)
        if kind in ("observe_site", "wait_and_measure"):
            result = read_site(state, site)
    elif kind == "split_sample":
        sample = _sample(state, p["sample_id"])
        if sample["used"] or sample["pair_id"]:
            raise DomainError("invalid_split", "Split an unused original sample")
        active = sum(s["volume_m3"] > 0 for s in state["samples"].values())
        if active + 1 > state["config"]["max_containers"]:
            raise DomainError(
                "container_capacity", "Splitting needs one additional empty container"
            )
        charge(state, 1.0, 1.0)
        pair_id = opaque("pair")
        children = []
        for _ in range(2):
            key = opaque("sample")
            state["samples"][key] = {
                **copy.deepcopy(sample),
                "amounts": (np.array(sample["amounts"]) / 2).tolist(),
                "volume_m3": sample["volume_m3"] / 2,
                "parent_id": p["sample_id"],
                "pair_id": pair_id,
            }
            children.append(key)
        sample["amounts"], sample["volume_m3"], sample["used"] = [0.0] * 3, 0.0, True
        advance_world(state, 1.0)
        result = {"control_id": children[0], "treatment_id": children[1], "pair_id": pair_id}
    elif kind == "run_intervention":
        control, treatment = _sample(state, p["control_id"]), _sample(state, p["treatment_id"])
        if (
            control is treatment
            or control["used"]
            or treatment["used"]
            or not control["pair_id"]
            or control["pair_id"] != treatment["pair_id"]
        ):
            raise DomainError("unmatched_control", "Use two unused siblings from the same split")
        seconds = p["duration_s"]
        charge(state, seconds, 5.0, lab=1, readings=18)
        trace, added, diagnostics = paired_experiment(
            control,
            treatment,
            p["intervention"],
            seconds,
            state["config"],
            state["rate_scale"],
        )
        state["ledger"]["external_in_token"] += added
        experiment_id = opaque("experiment")
        public_trace = [
            {
                "elapsed_s": t["elapsed_s"],
                "control": sensor(state, np.array(t["control"]) / control["volume_m3"]),
                "treatment": sensor(state, np.array(t["treatment"]) / treatment["volume_m3"]),
            }
            for t in trace
        ]
        result = {
            "experiment_id": experiment_id,
            "intervention": p["intervention"],
            "control_id": p["control_id"],
            "treatment_id": p["treatment_id"],
            "trace": public_trace,
            "validity_status": "completed",
            "applied_conditions": {
                "control_temperature_K": state["config"]["temperature_K"],
                "treatment_temperature_K": diagnostics["actual_temperature_K"],
                "resource_pulse_token_m3": 2.0 if added else 0.0,
            },
        }
        state["experiments"].append(
            {"public": copy.deepcopy(result), "diagnostics": diagnostics, "raw_trace": trace}
        )
        advance_world(state, seconds)
    elif kind == "submit_conclusion":
        if not set(p["evidence_ids"]).issubset(state["evidence_ids"]):
            raise DomainError("unknown_evidence", "Conclusion references unobserved evidence", 422)
        if p["outcome"] != "inconclusive" and not p["evidence_ids"]:
            raise DomainError(
                "missing_evidence", "A categorical claim needs observed evidence", 422
            )
        state["conclusion"] = copy.deepcopy(p)
        result = {"frozen": True}
    state["revision"] += 1
    state["last_result"] = result
    if kind in ("observe_site", "wait_and_measure", "run_intervention"):
        state["evidence_ids"].append(f"observation_{state['revision']}")
    reconcile(state)
    return state, {
        "schema_version": "1.0",
        "action_id": request.action_id,
        "job_id": request.action_id,
        "status": "completed",
        "observation": observation(state),
    }


def evaluation(state: dict) -> dict:
    if state["conclusion"] is None:
        raise DomainError("episode_active", "Submit a conclusion before evaluating")
    target = state["config"]["family"] in TARGET_FAMILIES
    conclusion = state["conclusion"]
    return {
        "episode_id": state["episode_id"],
        "model_version": MODEL_VERSION,
        "target_definition": "implemented_aggregate_maintenance_rule_present",
        "private_family": state["config"]["family"],
        "target": target,
        "target_score": conclusion["target_score"],
        "brier_score": (conclusion["target_score"] - int(target)) ** 2,
        "abstained": conclusion["outcome"] == "inconclusive",
        "costs": state["costs"],
        "numerical_diagnostics": state["diagnostics"],
        "global_inventory_residual_token": reconcile(state),
        "evidence_class": "hypothetical",
        "research_release": False,
    }
