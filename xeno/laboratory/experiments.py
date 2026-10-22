import copy

import numpy as np

from xeno.simulation.core import react


def paired_experiment(
    control: dict,
    treatment: dict,
    intervention: str,
    duration_s: float,
    config: dict,
    rate_scale: float,
) -> tuple[list, float, dict]:
    """Mutates two already-allocated chambers; never duplicates source material."""
    added = 0.0
    temperature = config["temperature_K"]
    if intervention == "resource_pulse":
        added = 2.0 * treatment["volume_m3"]
        treatment["amounts"][0] += added
    elif intervention == "temperature_shift":
        temperature += 10.0
    else:
        raise ValueError("Unsupported intervention")
    trace = []
    residual = 0.0
    steps = 0
    for index in range(9):
        if index:
            for chamber, temp in ((control, config["temperature_K"]), (treatment, temperature)):
                amounts, diagnostic = react(
                    np.array(chamber["amounts"]),
                    chamber["volume_m3"],
                    config["family"],
                    duration_s / 8,
                    temperature_K=temp,
                    rate_scale=rate_scale,
                    max_step_s=config["solver_step_s"],
                )
                chamber["amounts"] = amounts.tolist()
                residual = max(residual, diagnostic["inventory_residual_token"])
                steps += diagnostic["substeps"]
        trace.append(
            {
                "elapsed_s": index * duration_s / 8,
                "control": copy.deepcopy(control["amounts"]),
                "treatment": copy.deepcopy(treatment["amounts"]),
            }
        )
    control["used"] = treatment["used"] = True
    return (
        trace,
        added,
        {
            "substeps": steps,
            "inventory_residual_token": residual,
            "actual_temperature_K": temperature,
            "resource_added_token": added,
        },
    )
