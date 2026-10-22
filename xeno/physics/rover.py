"""Newton rigid chassis with six ray suspension/tire forces (SI units).

The tire contacts sample the terrain exported by Unreal. Coulomb-limited tire
forces drive the chassis; wheel meshes follow measured suspension travel. This
model does not simulate deformable soil, independent wheel rigid bodies or F0
sampling permissions.
"""

import newton
import numpy as np
import warp as wp
from scipy.spatial.transform import Rotation


class RoverDynamics:
    mass = 120.0
    dt = 1 / 240
    mounts = np.array([(x, y, -0.18) for y in (0.61, -0.61) for x in (-0.62, 0, 0.62)])

    def __init__(self, device="cpu", ground=lambda x, y: 0.0):
        self.ground = ground
        builder = newton.ModelBuilder()
        builder.add_body(
            xform=wp.transform((0, 0, ground(0, 0) + 0.76), wp.quat_identity()),
            mass=self.mass,
            inertia=wp.mat33(28, 0, 0, 0, 45, 0, 0, 0, 55),
            lock_inertia=True,
            label="six_ray_rover",
        )
        self.model = builder.finalize(device=device)
        self.solver = newton.solvers.SolverXPBD(self.model, iterations=2, angular_damping=0.2)
        self.current, self.next = self.model.state(), self.model.state()
        self.control = self.model.control()
        self.time = 0.0
        self.travel = np.zeros(6)
        self.normal_loads = np.zeros(6)
        self.traction_ratios = np.zeros(6)

    def step(self, target=(0, 0), friction=0.75):
        q = self.current.body_q.numpy()[0]
        vel = self.current.body_qd.numpy()[0]
        rot = Rotation.from_quat(q[3:7])
        points = rot.apply(self.mounts)
        world = points + q[:3]
        forward = rot.apply([1, 0, 0])
        lateral = rot.apply([0, 1, 0])
        desired = np.asarray(target) - q[:2]
        distance = np.linalg.norm(desired)
        heading = np.arctan2(forward[1], forward[0])
        error = np.arctan2(
            np.sin(np.arctan2(desired[1], desired[0]) - heading),
            np.cos(np.arctan2(desired[1], desired[0]) - heading),
        )
        speed = min(1.1, distance * 0.8) * max(0.1, np.cos(error)) if distance > 0.08 else 0
        yaw = np.clip(error * 1.2, -0.8, 0.8) if distance > 0.08 else 0
        total = np.zeros(3)
        torque = -vel[3:] * np.array([4.0, 4.0, 3.0])
        for i, p in enumerate(world):
            height = self.ground(p[0], p[1])
            dx = (self.ground(p[0] + 0.025, p[1]) - self.ground(p[0] - 0.025, p[1])) / 0.05
            dy = (self.ground(p[0], p[1] + 0.025) - self.ground(p[0], p[1] - 0.025)) / 0.05
            normal = np.array([-dx, -dy, 1.0])
            normal /= np.linalg.norm(normal)
            compression = np.clip(0.49 - (p[2] - height), 0, 0.35)
            point_velocity = vel[:3] + np.cross(vel[3:], points[i])
            load = (
                np.clip(4300 * compression - 280 * point_velocity[2], 0, 1800)
                if compression > 0
                else 0
            )
            drive = 100 * (speed - np.dot(point_velocity, forward) - yaw * self.mounts[i, 1])
            side = -180 * np.dot(point_velocity, lateral)
            tire = drive * forward + side * lateral
            tire -= np.dot(tire, normal) * normal
            limit = max(0, friction * load)
            tire *= min(1, limit / max(np.linalg.norm(tire), 1e-9))
            force = tire + normal * load
            total += force
            torque += np.cross(points[i], force)
            self.travel[i] = compression
            self.normal_loads[i] = load
            self.traction_ratios[i] = np.linalg.norm(tire) / max(limit, 1e-9)
        self.current.clear_forces()
        self.current.body_f.assign(np.array([np.r_[total, torque]], dtype=np.float32))
        self.solver.step(self.current, self.next, self.control, None, self.dt)
        self.current, self.next = self.next, self.current
        self.time += self.dt
        return self.current.body_q.numpy()[0]

    def snapshot(self):
        q = self.current.body_q.numpy()[0]
        v = self.current.body_qd.numpy()[0]
        return {
            "position_m": q[:3].tolist(),
            "quaternion_xyzw": q[3:].tolist(),
            "velocity_m_s": v[:3].tolist(),
            "suspension_compression_m": self.travel.tolist(),
            "normal_loads_n": self.normal_loads.tolist(),
            "traction_ratio_max": float(self.traction_ratios.max()),
        }
