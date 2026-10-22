"""Live, dimensionless 2D Boussinesq flow on a periodic square.

Vorticity/streamfunction formulation; dealiased Fourier derivatives, SSPRK3 and
implicit diffusion. This is a synthetic heated fluid patch, not calibrated
hydrothermal chemistry or a replacement for The Well reference datasets.
"""

import numpy as np
from scipy.fft import fft2, ifft2


class ThermalFlow:
    def __init__(self, n=64, diffusivity=0.012, viscosity=0.018, buoyancy=0.8):
        self.n, self.kappa, self.nu, self.buoyancy = n, diffusivity, viscosity, buoyancy
        self.time = 0.0
        k = np.fft.fftfreq(n, 1 / n)
        self.kx, self.ky = np.meshgrid(k, k, indexing="ij")
        self.k2 = self.kx**2 + self.ky**2
        self.inverse = np.where(self.k2 == 0, 1, self.k2)
        self.mask = (abs(self.kx) < n / 3) & (abs(self.ky) < n / 3)
        x, y = np.meshgrid(
            np.arange(n) * 2 * np.pi / n, np.arange(n) * 2 * np.pi / n, indexing="ij"
        )
        self.heat = np.exp(-((x - np.pi) ** 2 + (y - 1.2) ** 2) / 0.22)
        self.temperature = self.heat.copy()
        self.vorticity = np.zeros((n, n))
        self.velocity = np.zeros((n, n, 2))

    def fields(self, omega):
        spectrum = fft2(omega) * self.mask
        psi = spectrum / self.inverse
        u = ifft2(1j * self.ky * psi).real
        v = ifft2(-1j * self.kx * psi).real
        return u, v

    def rhs(self, omega, temperature, heating):
        u, v = self.fields(omega)
        wh, th = fft2(omega) * self.mask, fft2(temperature) * self.mask

        def derivative(f, k):
            return ifft2(1j * k * f).real

        dw = -u * derivative(wh, self.kx) - v * derivative(wh, self.ky)
        dw += self.buoyancy * derivative(th, self.kx)
        dt = -u * derivative(th, self.kx) - v * derivative(th, self.ky)
        if heating:
            dt += heating * self.heat - 0.06 * temperature
        return dw, dt

    def step(self, dt=1 / 60, heating=0.35):
        if not 0 < dt <= 1 / 30 or not 0 <= heating <= 2:
            raise ValueError("Bounded timestep and heating required")
        speed = float(np.linalg.norm(self.velocity, axis=-1).max())
        if not np.isfinite(speed):
            raise RuntimeError("Non-finite live flow state")
        substeps = max(1, int(np.ceil(speed * dt * self.n / (2 * np.pi * 0.35))))
        if substeps > 64:
            raise RuntimeError("Live flow exceeded the supported CFL budget")
        if substeps > 1:
            for _ in range(substeps):
                self.step(dt / substeps, heating)
            return
        a, b = self.rhs(self.vorticity, self.temperature, heating)
        w1, t1 = self.vorticity + dt * a, self.temperature + dt * b
        c, d = self.rhs(w1, t1, heating)
        w2 = 0.75 * self.vorticity + 0.25 * (w1 + dt * c)
        t2 = 0.75 * self.temperature + 0.25 * (t1 + dt * d)
        e, f = self.rhs(w2, t2, heating)
        self.vorticity = ifft2(
            fft2(self.vorticity / 3 + 2 / 3 * (w2 + dt * e))
            * self.mask
            / (1 + dt * self.nu * self.k2)
        ).real
        self.temperature = ifft2(
            fft2(self.temperature / 3 + 2 / 3 * (t2 + dt * f))
            * self.mask
            / (1 + dt * self.kappa * self.k2)
        ).real
        u, v = self.fields(self.vorticity)
        self.velocity = np.stack((u, v), axis=-1)
        self.time += dt

    def diagnostics(self):
        u, v = self.velocity[..., 0], self.velocity[..., 1]
        divergence = ifft2(1j * self.kx * fft2(u) + 1j * self.ky * fft2(v)).real
        return {
            "time": self.time,
            "temperature_mean": float(self.temperature.mean()),
            "max_speed": float(np.linalg.norm(self.velocity, axis=-1).max()),
            "divergence_linf": float(abs(divergence).max()),
        }
