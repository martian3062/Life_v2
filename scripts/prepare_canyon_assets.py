"""Download hash-pinned CC0 textures and generate reusable eroded static meshes."""

import hashlib
import json
import math
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "runs/assets"


def mesh(name, seed, cliff=False):
    rng = np.random.default_rng(seed)
    rings, sides = (96, 192) if cliff else (64, 96)
    phase = rng.uniform(0, 20, 4)
    vertices, uvs, faces = [], [], []
    for j in range(rings + 1):
        h = j / rings
        for i in range(sides + 1):
            a = i * 2 * math.pi / sides
            broad = math.sin(a * 3 + phase[0]) * 0.12 + math.sin(a * 7 + phase[1]) * 0.055
            gullies = abs(math.sin(a * 17 + phase[2] + h * 1.5)) ** 8
            grain = math.sin(a * 43 + h * 31 + phase[3]) * math.sin(a * 29 - h * 77) * 0.025
            if cliff:
                terrace = math.floor(h * 12) * 0.014 + math.sin(h * 92 + broad * 8) * 0.014
                top = max(0, (h - 0.84) / 0.16)
                radius = (1 - h * 0.22 + broad - gullies * 0.08 + terrace + grain) * (1 - top**5)
                z = h * (1 + 0.035 * math.sin(a * 7 + phase[0]) + 0.016 * math.sin(a * 21))
                v = (radius * math.cos(a) * 500, radius * math.sin(a) * 420, z * 1150)
                uv = (i / sides * 5, h * 4)
            else:
                b = h * math.pi
                dx, dy, dz = math.sin(b) * math.cos(a), math.sin(b) * math.sin(a), math.cos(b)
                broad_3d = math.sin(dx * 3.7 + dy * 2.3 + dz * 4.1 + phase[0])
                broad_3d *= math.cos(dy * 4.3 - dz * 2.6 + phase[1])
                fracture = math.sin(dx * 13 + dy * 17 + dz * 11 + phase[2])
                radius = 0.94 + broad_3d * 0.17 + fracture * 0.035 + grain * 0.4
                v = (
                    math.sin(b) * math.cos(a) * radius * 100,
                    math.sin(b) * math.sin(a) * radius * 85,
                    max(-0.6, math.cos(b) * radius) * 75,
                )
                uv = (i / sides * 2, h)
            vertices.append(v)
            uvs.append(uv)
            if j < rings and i < sides:
                k = j * (sides + 1) + i + 1
                # OBJ right-handed outward winding; import handles UE coordinates.
                if cliff:
                    faces.extend(((k, k + 1, k + sides + 1), (k + 1, k + sides + 2, k + sides + 1)))
                else:
                    faces.extend(((k, k + sides + 1, k + 1), (k + 1, k + sides + 1, k + sides + 2)))
    lines = [f"o {name}", "s 1"]
    lines += ["v {:.5f} {:.5f} {:.5f}".format(*v) for v in vertices]
    lines += ["vt {:.6f} {:.6f}".format(*uv) for uv in uvs]
    lines += ["f " + " ".join(f"{k}/{k}" for k in face) for face in faces]
    path = OUTPUT / f"{name}.obj"
    path.write_text("\n".join(lines), encoding="ascii")
    return {
        "name": name,
        "vertices": len(vertices),
        "triangles": len(faces),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sources = json.loads((ROOT / "configs/assets/canyon-sources.json").read_text())
    sources += json.loads((ROOT / "configs/assets/canyon-scans.json").read_text())
    for source in sources:
        url = source["url"]
        filename = "Rock030_2K-JPG.zip" if "ambientcg" in url else url.rsplit("/", 1)[1]
        path = OUTPUT / filename
        if not path.exists():
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 XENO"})
            with urllib.request.urlopen(request, timeout=90) as response:
                path.write_bytes(response.read(50_000_000))
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"Asset hash mismatch: {filename}")
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.endswith(("_Color.jpg", "_NormalDX.jpg", "_Roughness.jpg")):
                        (OUTPUT / Path(name).name).write_bytes(archive.read(name))
    meshes = [mesh(f"SM_CanyonCliff{i}", 971 + i, True) for i in range(4)]
    meshes += [mesh(f"SM_CanyonRock{i}", 812 + i) for i in range(4)]
    (OUTPUT / "geometry-manifest.json").write_text(json.dumps(meshes, indent=2))
    print(f"Prepared {len(meshes)} meshes and verified CC0 textures.")


if __name__ == "__main__":
    main()
