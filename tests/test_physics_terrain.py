import numpy as np

from xeno.physics.terrain import TerrainHeight


def test_native_height_grid_preserves_planar_heights_and_reflects_y():
    axis = np.linspace(-40, 40, 129)
    x, y = np.meshgrid(axis, axis, indexing="ij")
    terrain = TerrainHeight(0.1 * x + 0.2 * y + 3)
    for nx, ny in [(0.333, 2.2), (-39.9, 39.2), (40, -40), (0, 0)]:
        assert abs(terrain(nx, ny) - (0.1 * nx - 0.2 * ny + 3)) < 1e-12
    assert terrain(41, 0) == 0
