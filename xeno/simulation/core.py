"""Conservative F0 token kinetics and no-flux finite-volume transport.

R -> B -> W are resource, structured material and waste TOKEN pools, not molecules.
All coefficients are hypothetical. No quantitative chemistry is claimed.
"""

import json
from dataclasses import dataclass
from importlib.resources import files

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import solve_ivp
from scipy.sparse import coo_matrix, eye
from scipy.sparse.linalg import factorized

FAMILIES = ("maintenance_fast", "maintenance_buffered", "mineral_growth", "abiotic_catalyst")
TARGET_FAMILIES = frozenset(FAMILIES[:2])


class NumericalError(ValueError):
    """An update cannot be admitted as valid evidence."""


@dataclass(frozen=True)
class Kinetics:
    growth_s: float
    loss_s: float
    thermal_coefficient_K: float
    saturating: bool


# Effective compartment models, not individual organisms or calibrated reaction laws.
REGISTRY = json.loads(files("xeno").joinpath("data/f0_registry.json").read_text(encoding="utf-8"))
KINETICS = {name: Kinetics(**parameters) for name, parameters in REGISTRY["families"].items()}


def check_inventory(before: NDArray, after: NDArray) -> float:
    if not np.all(np.isfinite(after)) or np.any(after < 0):
        raise NumericalError("Nonfinite or negative token inventory; no clipping applied")
    initial, final = float(np.sum(before)), float(np.sum(after))
    residual = abs(final - initial)
    if residual > max(abs(initial) * 1e-10, 1e-20):
        raise NumericalError("Conserved token inventory exceeded its scale-aware tolerance")
    return residual


def react(
    amounts: NDArray,
    volume_m3: float,
    family: str,
    duration_s: float,
    *,
    temperature_K: float = 298.15,
    rate_scale: float = 1.0,
    max_step_s: float = 0.25,
) -> tuple[NDArray, dict]:
    """Lie splitting: analytic resource transfer, then analytic structure decay.

    Inputs may be a single chamber or (..., 3) grid. Transfer extents cannot exceed
    their donor pools. Step refinement is required because growth is nonlinear.
    """
    if family not in KINETICS:
        raise ValueError("Unsupported mechanism family")
    volume_m3 = np.asarray(volume_m3)
    scalars = (duration_s, temperature_K, rate_scale, max_step_s)
    if not np.isfinite(scalars).all():
        raise ValueError("Nonfinite solver input")
    if (
        not np.isfinite(volume_m3).all()
        or np.any(volume_m3 <= 0)
        or duration_s < 0
        or rate_scale <= 0
        or max_step_s <= 0
    ):
        raise ValueError("Invalid solver scale")
    if not 285 <= temperature_K <= 315:
        raise ValueError("Outside aqueous_demo_v1 temperature domain")
    initial = np.array(amounts, dtype=float, copy=True)
    if initial.shape[-1] != 3:
        raise ValueError("Expected resource, structure, waste channels")
    check_inventory(initial, initial)
    result = initial.copy()
    k = KINETICS[family]
    thermal = np.exp(k.thermal_coefficient_K * (temperature_K - 298.15))
    steps = max(1, int(np.ceil(duration_s / max_step_s)))
    dt = duration_s / steps
    for _ in range(steps):
        structure = result[..., 1] / volume_m3
        catalyst = structure / (structure + 0.5) if k.saturating else 1.0
        growth = result[..., 0] * (-np.expm1(-k.growth_s * rate_scale * thermal * catalyst * dt))
        result[..., 0] -= growth
        result[..., 1] += growth
        loss = result[..., 1] * (-np.expm1(-k.loss_s * rate_scale * thermal * dt))
        result[..., 1] -= loss
        result[..., 2] += loss
    residual = check_inventory(initial, result)
    return result, {
        "substeps": steps,
        "inventory_residual_token": residual,
        "floating_point_correction_token": 0.0,
        "max_step_s": max_step_s,
    }


def diffuse(
    amounts: NDArray,
    duration_s: float,
    diffusivity_m2_s: float,
    dx_m: float,
    *,
    max_step_s: float = 1.0,
) -> NDArray:
    """Equal-volume square cells, closed boundaries, positivity-stable explicit FV."""
    scalars = (duration_s, diffusivity_m2_s, dx_m)
    if not np.isfinite(scalars).all() or duration_s < 0 or diffusivity_m2_s < 0 or dx_m <= 0:
        raise ValueError("Invalid diffusion settings")
    initial = np.array(amounts, dtype=float, copy=True)
    check_inventory(initial, initial)
    if not np.isfinite(max_step_s) or max_step_s <= 0:
        raise ValueError("Invalid transport timestep")
    steps = max(
        1,
        int(np.ceil(duration_s * diffusivity_m2_s / dx_m**2 / 0.24)),
        int(np.ceil(duration_s / max_step_s)),
    )
    alpha = duration_s * diffusivity_m2_s / dx_m**2 / steps
    result = initial.copy()
    for _ in range(steps):
        delta = np.zeros_like(result)
        flux_x = alpha * (result[1:, ...] - result[:-1, ...])
        flux_y = alpha * (result[:, 1:, ...] - result[:, :-1, ...])
        delta[1:, ...] -= flux_x
        delta[:-1, ...] += flux_x
        delta[:, 1:, ...] -= flux_y
        delta[:, :-1, ...] += flux_y
        result += delta
    check_inventory(initial, result)
    return result


def compartment_transport(volumes: NDArray, diffusivity_m2_s: float, dx_m: float, dt_s: float):
    """Conservative backward Euler transfer with variable accessible fluid volumes.

    Faces have conductance D * dx (m3/s); empty cells have sealed faces. The
    generator's columns sum to zero. Its implicit inverse preserves positivity.
    """
    volumes = np.asarray(volumes, dtype=float)
    if (
        volumes.ndim != 2
        or not np.isfinite(volumes).all()
        or np.any(volumes < 0)
        or not np.isfinite([diffusivity_m2_s, dx_m, dt_s]).all()
        or diffusivity_m2_s < 0
        or dx_m <= 0
        or dt_s <= 0
    ):
        raise ValueError("Invalid compartment transport settings")
    n, m = volumes.shape
    flat = volumes.ravel()
    rows, cols, values = [], [], []
    conductance = diffusivity_m2_s * dx_m
    for x in range(n):
        for y in range(m):
            a = x * m + y
            for nx, ny in ((x + 1, y), (x, y + 1)):
                if nx >= n or ny >= m:
                    continue
                b = nx * m + ny
                if flat[a] <= 0 or flat[b] <= 0:
                    continue
                rows.extend([a, a, b, b])
                cols.extend([a, b, a, b])
                values.extend(
                    [
                        -conductance / flat[a],
                        conductance / flat[b],
                        conductance / flat[a],
                        -conductance / flat[b],
                    ]
                )
    generator = coo_matrix((values, (rows, cols)), shape=(n * m, n * m)).tocsc()
    solve = factorized(eye(n * m, format="csc") - dt_s * generator)

    def step(amounts):
        result = solve(np.asarray(amounts).reshape(n * m, -1)).reshape(amounts.shape)
        check_inventory(amounts, result)
        return result

    return step


def reversible_fixture(duration_s: float = 10.0) -> dict:
    """Independent BDF fixture A <-> B with known equilibrium and analytic solution."""
    forward, reverse = 0.2, 0.1

    def rhs(_time, state):
        flux = forward * state[0] - reverse * state[1]
        return [-flux, flux]

    result = solve_ivp(rhs, (0, duration_s), [1.0, 0.0], method="BDF", rtol=1e-10, atol=1e-12)
    if not result.success:
        raise NumericalError(result.message)
    expected_a = reverse / (forward + reverse) + (
        forward / (forward + reverse) * np.exp(-(forward + reverse) * duration_s)
    )
    residual = check_inventory(np.array([1.0, 0.0]), result.y[:, -1])
    return {
        "solver": "BDF",
        "final": result.y[:, -1].tolist(),
        "analytic_max_error": float(abs(result.y[0, -1] - expected_a)),
        "inventory_residual_token": residual,
    }
