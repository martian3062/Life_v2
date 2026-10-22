"""Bounded import of a recorded The Well trajectory for Unreal field visualization."""

import hashlib
import json
from pathlib import Path

import h5py
import httpx
import numpy as np


def prepare_reference(workspace: Path) -> dict:
    config = json.loads((workspace / "configs/well_sources.json").read_text())
    output = workspace / "runs/well"
    output.mkdir(parents=True, exist_ok=True)
    source = output / config["file"]
    if not source.exists():
        temp = source.with_suffix(".part")
        with httpx.stream("GET", config["url"], follow_redirects=True, timeout=60) as response:
            response.raise_for_status()
            length = int(response.headers.get("content-length", "0"))
            if not 0 < length <= config["max_download_bytes"]:
                raise ValueError("The Well sample exceeds the configured download limit.")
            size = 0
            with temp.open("wb") as file:
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > config["max_download_bytes"]:
                        raise ValueError("The Well download exceeded its bound.")
                    file.write(chunk)
            if size != length:
                raise ValueError("Incomplete The Well sample download.")
        temp.replace(source)
    with source.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    if digest != config["sha256"]:
        raise ValueError("The Well source checksum changed. Refusing to import unverified data.")
    return export_reference(source, output / "reference-field.json", config)


def export_reference(source: Path, output: Path, provenance: dict) -> dict:
    """Import only supported Cartesian 2D, sample/time-varying density and velocity fields."""
    with h5py.File(source, "r") as file:
        if file.attrs.get("grid_type") != "cartesian" or file.attrs.get("n_spatial_dims") != 2:
            raise ValueError("Only Cartesian 2D reference fields are supported.")
        density = file["t0_fields/density"]
        velocity = file["t1_fields/velocity"]
        for field in (density, velocity):
            if not field.attrs.get("sample_varying") or not field.attrs.get("time_varying"):
                raise ValueError("Expected sample- and time-varying fields.")
            if not np.array_equal(field.attrs.get("dim_varying"), [True, True]):
                raise ValueError("Expected two spatially varying axes.")
        if density.ndim != 4 or velocity.shape != (*density.shape, 2):
            raise ValueError("Unexpected density/velocity layout.")
        if density.shape[1] > 2000 or max(density.shape[2:]) > 4096:
            raise ValueError("Reference grid exceeds the import limit.")
        step_x = max(1, int(np.ceil(density.shape[2] / 64)))
        step_y = max(1, int(np.ceil(density.shape[3] / 64)))
        step_t = max(1, int(np.ceil(density.shape[1] / 51)))
        # Read one bounded trajectory with strided HDF5 selection, never the whole dataset.
        values = density[0, ::step_t, ::step_x, ::step_y].astype(np.float64)
        flow = velocity[0, ::step_t, ::step_x, ::step_y, :].astype(np.float64)
        times = file["dimensions/time"][::step_t].astype(np.float64)
        x = file["dimensions/x"][::step_x].astype(np.float64)
        y = file["dimensions/y"][::step_y].astype(np.float64)
        dataset = str(file.attrs["dataset_name"])
    if not all(np.isfinite(array).all() for array in (values, flow, times, x, y)):
        raise ValueError("Reference contains non-finite values.")
    if len(times) != len(values) or len(times) < 2 or not (np.diff(times) > 0).all():
        raise ValueError("Reference times must be strictly increasing and match the fields.")
    if not (np.diff(x) > 0).all() or not (np.diff(y) > 0).all():
        raise ValueError("Expected increasing grid coordinates.")
    low, high = float(values.min()), float(values.max())
    velocity_bound = float(np.abs(flow).max())
    normalized = np.rint((values - low) / max(high - low, 1e-20) * 255).astype(np.uint8)
    quantized_flow = np.rint(flow / max(velocity_bound, 1e-20) * 32767).astype(np.int16)
    payload = {
        "version": 1,
        "mode": "recorded_reference",
        "dataset": dataset,
        "source_sha256": provenance["sha256"],
        "source_url": provenance["url"],
        "repository_commit": provenance["commit"],
        "license": provenance["dataset_license"],
        "citation": provenance["citation"],
        "time_units": provenance["time_units"],
        "field": "density",
        "trajectory": 0,
        "nx": len(x),
        "ny": len(y),
        "x": x.tolist(),
        "y": y.tolist(),
        "times": times.tolist(),
        "density_range": [low, high],
        "velocity_bound": velocity_bound,
        "selection_stride": [step_t, step_x, step_y],
        "density": normalized.reshape(len(times), -1).tolist(),
        "velocity": quantized_flow.reshape(len(times), -1).tolist(),
        "display_note": (
            "Normalized density height/color and velocity arrows. Recorded gas dynamics; "
            "display time and spatial scales are artistic, independent of mission time."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    manifest = {key: value for key, value in payload.items() if key not in ("density", "velocity")}
    manifest["output_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest
