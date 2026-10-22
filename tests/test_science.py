import numpy as np
import pytest

from xeno.observations.sensors import measure
from xeno.simulation.core import (
    FAMILIES,
    NumericalError,
    compartment_transport,
    diffuse,
    react,
    reversible_fixture,
)


def test_bdf_against_analytic_solution():
    result = reversible_fixture()
    assert result["analytic_max_error"] < 2e-9
    assert result["inventory_residual_token"] < 1e-12


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("scale", [1e-12, 1.0, 1e3])
def test_reaction_conserves_tokens_without_clipping(family, scale):
    initial = np.array([8.0, 2.0, 0.0]) * 1e-6 * scale
    final, diagnostics = react(initial, 1e-6 * scale, family, 120, rate_scale=10)
    assert np.min(final) >= 0
    np.testing.assert_allclose(final.sum(), initial.sum(), rtol=1e-12, atol=0)
    assert diagnostics["floating_point_correction_token"] == 0


def test_time_step_refinement():
    initial = np.array([8.0, 2.0, 0.0]) * 1e-6
    results = [
        react(initial, 1e-6, "maintenance_fast", 60, max_step_s=dt)[0]
        for dt in (0.5, 0.25, 0.125, 0.03125)
    ]
    assert np.linalg.norm(results[2] - results[3]) < np.linalg.norm(results[1] - results[3])
    assert np.max(np.abs(results[1] - results[3])) / initial.sum() < 0.001


def test_diffusion_closed_boundary_and_spatial_refinement():
    errors = []
    for n in (8, 16, 32):
        x = (np.arange(n) + 0.5) / n
        initial = np.ones((n, n, 3))
        initial[..., 0] += 0.5 * np.cos(np.pi * x[:, None])
        final = diffuse(initial, 0.1, 0.05, 1 / n, max_step_s=0.0001)
        exact = 1 + 0.5 * np.cos(np.pi * x[:, None]) * np.exp(-0.05 * np.pi**2 * 0.1)
        errors.append(np.max(np.abs(final[..., 0] - exact)))
        np.testing.assert_allclose(final.sum(axis=(0, 1)), initial.sum(axis=(0, 1)), rtol=1e-13)
        assert final.min() >= 0
    assert errors[2] < errors[1] < errors[0]


def test_invalid_numerical_state_is_rejected():
    with pytest.raises(NumericalError):
        react(np.array([-1e-12, 2e-12, 0]), 1e-6, "maintenance_fast", 10)
    with pytest.raises(ValueError):
        react(np.array([1, 2, 0]), 1e-6, "maintenance_fast", 10, temperature_K=400)


def test_transport_after_sampling_is_positive_and_conservative():
    volumes = np.full((3, 3), 1e-6)
    volumes[0, 0] = 1e-8
    volumes[1, 1] = 0
    amounts = np.zeros((3, 3, 3))
    amounts[0, 0] = [8e-8, 2e-8, 0]
    step = compartment_transport(volumes, 1e-7, 0.01, 0.25)
    result = amounts.copy()
    for _ in range(100):
        result = step(result)
    np.testing.assert_allclose(result.sum(axis=(0, 1)), amounts.sum(axis=(0, 1)), rtol=1e-12)
    assert result.min() >= 0
    np.testing.assert_array_equal(result[1, 1], [0, 0, 0])


def test_sensor_censoring_and_reproducibility():
    first = measure([0, 2, 3], 1042, 0)
    assert first == measure([0, 2, 3], 1042, 0)
    assert first != measure([0, 2, 3], 1042, 1)
    assert first[0]["censored"] is True
    assert first[0]["value"] is None


def test_world_reproducibility_and_appearance_independence():
    from xeno.service.engine import advance_world, new_state
    from xeno.service.schemas import EpisodeConfig

    first = new_state(EpisodeConfig(seed=123), "episode-a")
    repeated = new_state(EpisodeConfig(seed=123), "episode-b")
    other_family = new_state(EpisodeConfig(seed=123, family="mineral_growth"), "episode-c")
    assert first["grid"] == repeated["grid"]
    assert first["rate_scale"] == repeated["rate_scale"]
    assert [s["appearance"] for s in first["sites"]] == [
        s["appearance"] for s in other_family["sites"]
    ]
    advance_world(first, 10)
    advance_world(repeated, 10)
    np.testing.assert_array_equal(first["grid"], repeated["grid"])
