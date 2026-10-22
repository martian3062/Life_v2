"""Transparent demonstration heuristics; scores are explicitly uncalibrated.

No simulator imports, hidden parameters, family identifiers or evaluator calls are
available here. This is a baseline, not the proposed research EIG algorithm.
"""

import math
import random
import uuid

POLICIES = ("passive", "random", "fixed", "adaptive")


class EpisodeClient:
    def __init__(self, transport, episode_id: str, token: str):
        self.transport = transport
        self.base = f"/v1/episodes/{episode_id}"
        self.episode_id = episode_id
        self.headers = {"Authorization": f"Bearer {token}"}
        self.history = []
        self.obs = self.get("/observation")

    def get(self, suffix: str):
        response = self.transport.get(self.base + suffix, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def act(self, kind: str, **parameters):
        response = self.transport.post(
            self.base + "/actions",
            headers=self.headers,
            json={
                "schema_version": "1.0",
                "episode_id": self.episode_id,
                "action_id": uuid.uuid4().hex,
                "expected_state_revision": self.obs["state_revision"],
                "action_type": kind,
                "parameters": parameters,
            },
        )
        response.raise_for_status()
        self.obs = response.json()["observation"]
        self.history.append(self.obs)
        return self.obs["result"]


def channel(measurements: list, name="structure") -> float | None:
    return next(m["value"] for m in measurements if m["channel_id"] == name)


def experiment_score(result: dict) -> tuple[float, bool]:
    trace = result["trace"]
    # Early response reduces confounding from late substrate exhaustion.
    start, early = trace[0], trace[2]
    values = [channel(t[arm]) for t in (start, early) for arm in ("control", "treatment")]
    if any(v is None for v in values):
        return 0.5, True
    c0, t0, c1, t1 = values
    dc, dt = c1 - c0, t1 - t0
    if abs(dc) < 0.15:
        return 0.5, True
    if result["intervention"] == "temperature_shift":
        acceleration = dt / dc
        mismatch = acceleration < 0 or acceleration > 4
        # Weak thermal acceleration is compatible with the maintained-compartment prior.
        logit = (1.5 - acceleration) * 4
    else:
        enhancement = dt - dc
        mismatch = abs(enhancement) > 3
        # Resource dependence is weak evidence, since abiotic growth can share it.
        logit = (enhancement - 0.1) * 0.8
    score = 1 / (1 + math.exp(-max(-20, min(20, logit))))
    return float(score), mismatch


def run_policy(client: EpisodeClient, policy: str, policy_seed: int = 17) -> dict:
    if policy not in POLICIES:
        raise ValueError(f"Unknown policy: {policy}")
    rng = random.Random(policy_seed)
    site = client.obs["sites"][0]["site_id"]
    client.act("observe_site", site_id=site)
    evidence = [client.obs["observation_id"]]
    score, mismatch = 0.5, False
    choices, rationales = [], []
    for index in range(2):
        budget = client.obs["remaining_budget"]
        if budget["mission_time_s"] < 64 or budget["battery_j"] < 8:
            break
        if policy == "passive":
            client.act("wait_and_measure", site_id=site, duration_s=60)
            evidence.append(client.obs["observation_id"])
            # A temporal growth observation alone is deliberately weak evidence.
            observed = channel(client.obs["result"]["measurements"])
            score = 0.5 if observed is None else 0.5 + 0.1 * math.tanh((observed - 2) / 2)
            continue
        if budget["lab_actions"] < 1 or budget["instrument_readings"] < 18:
            break
        if len(client.obs["samples"]) + 2 > client.obs["sample_capacity"]:
            break
        if policy == "random":
            choice = rng.choice(["resource_pulse", "temperature_shift"])
            rationale = "Uniform random choice from the supported intervention catalogue."
        elif policy == "fixed":
            choice = ["resource_pulse", "temperature_shift"][index]
            rationale = "Predefined resource-dependence then temperature-response sequence."
        else:
            choice = "temperature_shift" if abs(score - 0.5) < 0.3 else "resource_pulse"
            rationale = (
                "Uncertain score: test differential thermal response."
                if choice == "temperature_shift"
                else "Check resource dependence as a second view."
            )
        sample = client.act("collect_sample", site_id=site, volume_m3=2e-7)
        pair = client.act("split_sample", sample_id=sample["sample_id"])
        result = client.act(
            "run_intervention",
            control_id=pair["control_id"],
            treatment_id=pair["treatment_id"],
            intervention=choice,
            duration_s=60,
        )
        estimate, bad_fit = experiment_score(result)
        mismatch |= bad_fit
        # Thermal evidence has higher heuristic weight; no calibrated posterior is claimed.
        weight = 0.85 if choice == "temperature_shift" else 0.3
        score = weight * estimate + (1 - weight) * score
        evidence.append(client.obs["observation_id"])
        choices.append(choice)
        rationales.append(rationale)
    if mismatch or 0.25 < score < 0.75:
        outcome = "inconclusive"
    elif score >= 0.75:
        outcome = "candidate_mechanism_supported"
    else:
        outcome = "abiotic_explanation_supported"
    client.act(
        "submit_conclusion",
        outcome=outcome,
        target_score=score,
        evidence_ids=evidence,
        interpretation=f"{policy} policy; uncalibrated maintenance-mechanism score {score:.3f}.",
        alternatives=[
            "Maintained aggregate compartment",
            "Abiotic driven growth",
            "Unknown mechanism",
        ],
        limitations=[
            "F0 hypothetical resource tokens; no molecular chemistry or life claim.",
            "Qualitative heuristic score has no probability calibration.",
            "Four development fixtures do not establish transfer to unseen mechanisms.",
        ],
        next_experiment="Repeat a matched temperature experiment with independent sample material.",
    )
    return {
        "policy": policy,
        "policy_seed": policy_seed,
        "score": score,
        "outcome": outcome,
        "interventions": choices,
        "rationales": rationales,
        "predictive_mismatch": mismatch,
    }
