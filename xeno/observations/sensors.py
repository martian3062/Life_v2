import hashlib

import numpy as np

CHANNELS = ("resource", "structure", "waste")
SIGMA = 0.04
DETECTION_LIMIT = 0.08


def derived_seed(seed: int, stream: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{seed}:{stream}".encode()).digest()[:8], "little")


def measure(concentrations, seed: int, measurement_number: int) -> list[dict]:
    rng = np.random.default_rng(derived_seed(seed, f"sensor:{measurement_number}"))
    noisy = np.asarray(concentrations) + rng.normal(0, SIGMA, 3)
    return [
        {
            "channel_id": channel,
            "value": None if value < DETECTION_LIMIT else float(value),
            "unit": "token/m3",
            "standard_uncertainty": SIGMA,
            "detection_limit": DETECTION_LIMIT,
            "censored": bool(value < DETECTION_LIMIT),
        }
        for channel, value in zip(CHANNELS, noisy, strict=True)
    ]
