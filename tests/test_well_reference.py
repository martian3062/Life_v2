import json

import h5py
import numpy as np
import pytest

from xeno.scenes.well import export_reference


def make_source(path):
    values = np.arange(3 * 4 * 5, dtype=np.float32).reshape(1, 3, 4, 5) + 1
    flow = np.stack((values * 0.01, -values * 0.02), axis=-1)
    with h5py.File(path, "w") as file:
        file.attrs.update(grid_type="cartesian", n_spatial_dims=2, dataset_name="test_fixture")
        file.create_dataset("dimensions/time", data=[0.0, 2.0, 4.0])
        file.create_dataset("dimensions/x", data=np.linspace(-1, 1, 4))
        file.create_dataset("dimensions/y", data=np.linspace(0, 3, 5))
        for name, data in (("t0_fields/density", values), ("t1_fields/velocity", flow)):
            ds = file.create_dataset(name, data=data)
            ds.attrs.update(sample_varying=True, time_varying=True, dim_varying=[True, True])
    return values, flow


def test_well_import_preserves_axes_time_and_quantization_bounds(tmp_path):
    source = tmp_path / "source.h5"
    values, flow = make_source(source)
    before = source.read_bytes()
    metadata = {
        "sha256": "a" * 64,
        "url": "https://example.test/fixture",
        "commit": "test",
        "dataset_license": "test",
        "citation": "test",
        "time_units": "simulation units",
    }
    output = tmp_path / "reference.json"
    manifest = export_reference(source, output, metadata)
    data = json.loads(output.read_text())
    lo, hi = data["density_range"]
    reconstructed = np.array(data["density"]).reshape(values.shape) / 255 * (hi - lo) + lo
    assert np.max(np.abs(reconstructed - values)) <= (hi - lo) / 510 + 1e-6
    reconstructed_flow = (
        np.array(data["velocity"]).reshape(flow.shape) / 32767 * data["velocity_bound"]
    )
    assert np.max(np.abs(reconstructed_flow - flow)) <= data["velocity_bound"] / 65534 + 1e-6
    assert data["times"] == [0, 2, 4]
    assert data["nx"] == 4 and data["ny"] == 5
    assert source.read_bytes() == before
    assert manifest["mode"] == "recorded_reference"


def test_well_import_rejects_unsupported_coordinates_and_nonfinite_data(tmp_path):
    source = tmp_path / "source.h5"
    make_source(source)
    with h5py.File(source, "a") as file:
        file.attrs["grid_type"] = "spherical"
    with pytest.raises(ValueError, match="Cartesian"):
        export_reference(source, tmp_path / "output.json", {})
    with h5py.File(source, "a") as file:
        file.attrs["grid_type"] = "cartesian"
        file["t0_fields/density"][0, 0, 0, 0] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        export_reference(source, tmp_path / "output.json", {})
