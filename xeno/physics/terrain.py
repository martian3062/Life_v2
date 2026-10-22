"""Scalar bilinear sampling across the Unreal-to-Newton reflected Y axis."""

import numpy as np


class TerrainHeight:
    def __init__(self, heights, half_extent=40.0):
        self.heights = np.asarray(heights, dtype=float)
        n = len(self.heights)
        if self.heights.shape != (n, n) or not 2 <= n <= 257:
            raise ValueError("Square bounded terrain grid required")
        if not np.isfinite(self.heights).all():
            raise ValueError("Finite terrain heights required")
        self.n, self.half_extent = n, half_extent
        self.scale = (n - 1) / (2 * half_extent)

    def __call__(self, x, y):
        gx = (x + self.half_extent) * self.scale
        gy = (-y + self.half_extent) * self.scale
        if not 0 <= gx <= self.n - 1 or not 0 <= gy <= self.n - 1:
            return 0.0
        i, j = min(int(gx), self.n - 2), min(int(gy), self.n - 2)
        a, b = gx - i, gy - j
        h = self.heights
        return float(
            (1 - a) * ((1 - b) * h[i, j] + b * h[i, j + 1])
            + a * ((1 - b) * h[i + 1, j] + b * h[i + 1, j + 1])
        )
