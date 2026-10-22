from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class EpisodeConfig(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    seed: int = Field(default=1042, ge=0, le=2**32 - 1)
    family: Literal[
        "maintenance_fast", "maintenance_buffered", "mineral_growth", "abiotic_catalyst"
    ] = "maintenance_fast"
    grid_size: int = Field(default=8, ge=2, le=32)
    temperature_K: float = Field(default=298.15, ge=285, le=305)
    solvent_profile: Literal["aqueous_demo_v1"] = "aqueous_demo_v1"
    pressure_Pa: Literal[101325] = 101325
    duration_s: float = Field(default=1200, ge=60, le=7200)
    battery_j: float = Field(default=1000, gt=0, le=100000)
    lab_actions: int = Field(default=4, ge=0, le=20)
    instrument_readings: int = Field(default=200, ge=1, le=1000)
    max_containers: int = Field(default=8, ge=3, le=32)
    solver_step_s: float = Field(default=0.25, ge=0.05, le=1)


class Empty(StrictModel):
    pass


class Site(StrictModel):
    site_id: str = Field(min_length=1, max_length=100)


class Collect(Site):
    volume_m3: float = Field(gt=0, le=1e-6)


class Split(StrictModel):
    sample_id: str = Field(min_length=1, max_length=100)


class Intervention(StrictModel):
    control_id: str = Field(min_length=1, max_length=100)
    treatment_id: str = Field(min_length=1, max_length=100)
    intervention: Literal["resource_pulse", "temperature_shift"]
    duration_s: float = Field(default=60, ge=10, le=120)


class Wait(Site):
    duration_s: float = Field(default=60, ge=1, le=120)


class Conclusion(StrictModel):
    outcome: Literal[
        "candidate_mechanism_supported", "abiotic_explanation_supported", "inconclusive"
    ]
    target_score: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(max_length=200)
    interpretation: str = Field(min_length=1, max_length=4000)
    alternatives: list[str] = Field(min_length=1, max_length=10)
    limitations: list[str] = Field(min_length=1, max_length=10)
    next_experiment: str = Field(min_length=1, max_length=500)


PARAMETERS = {
    "move": Site,
    "observe_site": Site,
    "collect_sample": Collect,
    "split_sample": Split,
    "run_intervention": Intervention,
    "wait_and_measure": Wait,
    "submit_conclusion": Conclusion,
}


class ActionRequest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    episode_id: str = Field(min_length=1, max_length=100)
    action_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    expected_state_revision: int = Field(ge=0)
    action_type: Literal[
        "move",
        "observe_site",
        "collect_sample",
        "split_sample",
        "run_intervention",
        "wait_and_measure",
        "submit_conclusion",
    ]
    parameters: dict

    @model_validator(mode="after")
    def validate_parameters(self):
        self.parameters = PARAMETERS[self.action_type].model_validate(self.parameters).model_dump()
        return self


class ConclusionRequest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    episode_id: str = Field(min_length=1, max_length=100)
    action_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    expected_state_revision: int = Field(ge=0)
    parameters: Conclusion
