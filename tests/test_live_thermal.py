import numpy as np

from xeno.physics.thermal import ThermalFlow


def test_heat_fourier_decay_and_mean_conservation():
    flow = ThermalFlow(32, buoyancy=0)
    x = np.arange(32) * 2 * np.pi / 32
    flow.temperature = 0.5 + 0.2 * np.cos(x)[:, None] * np.ones((1, 32))
    for _ in range(120):
        flow.step(1 / 120, heating=0)
    expected = 0.5 + 0.2 * np.exp(-flow.kappa) * np.cos(x)[:, None]
    assert abs(flow.temperature.mean() - 0.5) < 1e-12
    assert abs(flow.temperature - expected).max() < 2e-7


def test_heating_drives_flow_and_projection_is_divergence_free():
    flow = ThermalFlow(32)
    initial = flow.temperature.copy()
    for _ in range(120):
        flow.step()
    check = flow.diagnostics()
    assert check["max_speed"] > 0.05
    assert check["divergence_linf"] < 1e-12
    assert np.isfinite(flow.temperature).all()
    assert np.linalg.norm(initial - flow.temperature) > 0.1


def test_live_flow_remains_finite_beyond_the_initial_transient():
    flow = ThermalFlow(64)
    for _ in range(3600):
        flow.step()
    assert np.isfinite(flow.temperature).all()
    assert abs(flow.temperature).max() < 10
    assert flow.diagnostics()["divergence_linf"] < 1e-10
    assert abs(flow.time - 60) < 1e-8
