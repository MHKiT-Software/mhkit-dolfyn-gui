"""Tests for velds extraction in export_pipeline (pure dolfyn velds properties).

Importing mhkit.dolfyn registers the velds xarray accessor on all datasets.
It must be imported here (even if not called directly) so the accessor is
available when tests call ds.velds.
"""

from __future__ import annotations

import mhkit.dolfyn  # noqa: F401 — registers ds.velds accessor
import numpy as np
import xarray as xr

from mhkit_dolfyn_gui.services.export_pipeline import (
    VELDS_PROP_NAMES,
    derived_velocity_pairs,
    inject_derived_velocity,
)

# ---------------------------------------------------------------------------
# derived_velocity_pairs
# ---------------------------------------------------------------------------


def test_pairs_all_properties(sample_adcp_dataset: xr.Dataset) -> None:
    """All 7 always-available properties are returned for a well-formed dataset."""
    pairs = derived_velocity_pairs(sample_adcp_dataset)
    names = [name for name, _ in pairs]
    assert set(names) == set(VELDS_PROP_NAMES), f"Missing or extra names: {names}"
    assert len(names) == len(VELDS_PROP_NAMES)


def test_pairs_all_float32(sample_adcp_dataset: xr.Dataset) -> None:
    """Every returned DataArray has dtype float32 regardless of source dtype."""
    pairs = derived_velocity_pairs(sample_adcp_dataset)
    for name, da in pairs:
        assert da.dtype == np.float32, f"{name} has dtype {da.dtype}, expected float32"


def test_pairs_no_vel() -> None:
    """Returns an empty list when the dataset has no 'vel' variable — no exception."""
    ds = xr.Dataset(
        {"pressure": (["time"], np.random.randn(50))},
        coords={"time": np.arange(50)},
        attrs={"inst_type": "ADCP", "coord_sys": "beam"},
    )
    result = derived_velocity_pairs(ds)
    assert result == []


def test_pairs_never_raises() -> None:
    """Returns an empty list (never raises) for a completely empty dataset."""
    ds = xr.Dataset()
    result = derived_velocity_pairs(ds)
    assert result == []


# ---------------------------------------------------------------------------
# inject_derived_velocity
# ---------------------------------------------------------------------------


def test_inject_does_not_mutate(sample_adcp_dataset: xr.Dataset) -> None:
    """inject_derived_velocity never modifies the input dataset."""
    original_vars = set(sample_adcp_dataset.data_vars)
    _ = inject_derived_velocity(sample_adcp_dataset)
    assert set(sample_adcp_dataset.data_vars) == original_vars


def test_inject_returns_new_object(sample_adcp_dataset: xr.Dataset) -> None:
    """inject_derived_velocity returns a distinct Dataset object."""
    result = inject_derived_velocity(sample_adcp_dataset)
    assert result is not sample_adcp_dataset


def test_inject_returns_all_velds_vars(sample_adcp_dataset: xr.Dataset) -> None:
    """The returned dataset contains all 7 velds names as data variables."""
    result = inject_derived_velocity(sample_adcp_dataset)
    for name in VELDS_PROP_NAMES:
        assert name in result.data_vars, f"Expected '{name}' in result.data_vars"


def test_inject_velds_vars_are_float32(sample_adcp_dataset: xr.Dataset) -> None:
    """All injected velds variables in the result are float32."""
    result = inject_derived_velocity(sample_adcp_dataset)
    for name in VELDS_PROP_NAMES:
        if name in result.data_vars:
            dtype = result[name].dtype
            assert dtype == np.float32, f"{name} has dtype {dtype}, expected float32"


def test_inject_raw_var_wins() -> None:
    """If a variable with the same name already exists, the raw value is preserved."""
    n_time, n_range = 50, 10
    times = np.arange(
        np.datetime64("2024-01-01T00:00:00"),
        np.datetime64("2024-01-01T00:00:00") + np.timedelta64(n_time, "s"),
        np.timedelta64(1, "s"),
    )
    sentinel = np.ones((n_range, n_time), dtype=np.float32) * 999.0
    ds = xr.Dataset(
        {
            "vel": (["dir", "range", "time"], np.random.randn(3, n_range, n_time)),
            # Pre-existing 'u' variable — should survive injection unchanged
            "u": (["range", "time"], sentinel),
        },
        coords={
            "time": times,
            "range": np.arange(n_range, dtype=float),
            "dir": np.array([1, 2, 3], dtype=np.int32),
        },
        attrs={"inst_type": "ADCP", "coord_sys": "beam", "fs": 1.0},
    )
    result = inject_derived_velocity(ds)
    np.testing.assert_array_equal(
        result["u"].values,
        sentinel,
        err_msg="Raw 'u' variable was overwritten by velds injection",
    )


# ---------------------------------------------------------------------------
# frame-aware metadata
# ---------------------------------------------------------------------------


def test_earth_frame_u_has_eastward_long_name() -> None:
    """In the earth (geographic) frame, u/v/w get CF-correct directional names."""
    n_time, n_range = 20, 5
    times = np.arange(
        np.datetime64("2024-01-01T00:00:00"),
        np.datetime64("2024-01-01T00:00:00") + np.timedelta64(n_time, "s"),
        np.timedelta64(1, "s"),
    )
    ds = xr.Dataset(
        {
            "vel": (["dir", "range", "time"], np.random.randn(3, n_range, n_time)),
        },
        coords={
            "time": times,
            "range": np.arange(n_range, dtype=float),
            "dir": np.array(["E", "N", "U"]),
        },
        attrs={"inst_type": "ADCP", "coord_sys": "earth", "fs": 1.0},
    )
    pairs = dict(derived_velocity_pairs(ds))
    assert pairs["u"].attrs["long_name"] == "Eastward Velocity"
    assert pairs["u"].attrs["standard_name"] == "eastward_sea_water_velocity"
    assert pairs["v"].attrs["long_name"] == "Northward Velocity"
    assert pairs["w"].attrs["long_name"] == "Upward Velocity"


def test_beam_frame_u_long_name_mentions_beam(sample_adcp_dataset: xr.Dataset) -> None:
    """sample_adcp_dataset is coord_sys='beam' — u should be labeled 'Beam 1'."""
    pairs = dict(derived_velocity_pairs(sample_adcp_dataset))
    assert "Beam 1" in pairs["u"].attrs["long_name"]


def test_u_real_and_u_imag_have_complex_storage_comment(
    sample_adcp_dataset: xr.Dataset,
) -> None:
    """U_real/U_imag carry a comment explaining the complex-storage workaround."""
    pairs = dict(derived_velocity_pairs(sample_adcp_dataset))
    assert "complex" in pairs["U_real"].attrs["comment"].lower()
    assert "complex" in pairs["U_imag"].attrs["comment"].lower()


def test_all_properties_have_derived_provenance_comment(
    sample_adcp_dataset: xr.Dataset,
) -> None:
    """Every extracted property carries a comment noting it's not in the raw file."""
    pairs = dict(derived_velocity_pairs(sample_adcp_dataset))
    for name in VELDS_PROP_NAMES:
        assert "comment" in pairs[name].attrs, f"{name} missing comment attr"


def test_inject_no_vel_returns_copy() -> None:
    """inject_derived_velocity returns a copy even when no properties can be computed."""
    ds = xr.Dataset(
        {"pressure": (["time"], np.random.randn(30))},
        coords={"time": np.arange(30)},
    )
    result = inject_derived_velocity(ds)
    assert result is not ds
    # No velds vars should have been added
    for name in VELDS_PROP_NAMES:
        assert name not in result.data_vars
