"""Tests for the field resolver DSL."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from mhkit_dolfyn_gui.models.field_resolver import list_available_fields, resolve_field


class _FakeFileItem:
    """Minimal stand-in for FileItem to avoid importing PySide6 in pure tests."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()


class TestResolveField:
    # -- attr --

    def test_attr_existing(self, sample_adcp_dataset) -> None:
        assert resolve_field(sample_adcp_dataset, "attr.inst_type") == "ADCP"

    def test_attr_missing(self, sample_adcp_dataset) -> None:
        assert resolve_field(sample_adcp_dataset, "attr.nonexistent") == "N/A"

    # -- var stats --

    def test_var_mean(self, sample_adcp_dataset) -> None:
        result = resolve_field(sample_adcp_dataset, "var.heading.mean")
        # heading is uniform(0, 360) — result should be a number string
        assert result != "N/A"
        float(result)  # should not raise

    def test_var_stat_with_units(self) -> None:
        """When a variable has a units attr, it should be appended."""
        ds = xr.Dataset({"temp": (["x"], [1.0, 2.0, 3.0], {"units": "degC"})})
        result = resolve_field(ds, "var.temp.mean")
        assert "[degC]" in result

    def test_var_stat_without_units(self, sample_adcp_dataset) -> None:
        result = resolve_field(sample_adcp_dataset, "var.heading.max")
        assert "[" not in result  # no units on test fixtures

    def test_var_min_max(self, sample_adcp_dataset) -> None:
        mn = resolve_field(sample_adcp_dataset, "var.heading.min")
        mx = resolve_field(sample_adcp_dataset, "var.heading.max")
        assert float(mn) <= float(mx)

    def test_var_std(self, sample_adcp_dataset) -> None:
        result = resolve_field(sample_adcp_dataset, "var.heading.std")
        assert float(result) > 0

    # -- var nan info --

    def test_var_nan_count_no_nans(self, sample_adcp_dataset) -> None:
        result = resolve_field(sample_adcp_dataset, "var.heading.nan_count")
        assert result == "0"

    def test_var_nan_pct_no_nans(self, sample_adcp_dataset) -> None:
        result = resolve_field(sample_adcp_dataset, "var.heading.nan_pct")
        assert result == "0.0%"

    def test_var_nan_count_with_nans(self) -> None:
        ds = xr.Dataset({"x": (["t"], [1.0, np.nan, 3.0, np.nan])})
        assert resolve_field(ds, "var.x.nan_count") == "2"

    def test_var_nan_pct_with_nans(self) -> None:
        ds = xr.Dataset({"x": (["t"], [1.0, np.nan, 3.0, np.nan])})
        assert resolve_field(ds, "var.x.nan_pct") == "50.0%"

    # -- var metadata --

    def test_var_shape(self, sample_adcp_dataset) -> None:
        result = resolve_field(sample_adcp_dataset, "var.heading.shape")
        assert result == "(100,)"

    def test_var_size(self, sample_adcp_dataset) -> None:
        assert resolve_field(sample_adcp_dataset, "var.heading.size") == "100"

    def test_var_dtype(self, sample_adcp_dataset) -> None:
        result = resolve_field(sample_adcp_dataset, "var.heading.dtype")
        assert "float" in result

    # -- var attr --

    def test_var_attr(self) -> None:
        ds = xr.Dataset({"temp": (["x"], [1.0], {"units": "degC"})})
        assert resolve_field(ds, "var.temp.attr.units") == "degC"

    def test_var_attr_missing(self, sample_adcp_dataset) -> None:
        assert resolve_field(sample_adcp_dataset, "var.heading.attr.missing") == "N/A"

    # -- var values --

    def test_var_values_slice(self) -> None:
        ds = xr.Dataset({"x": (["t"], [10.0, 20.0, 30.0, 40.0, 50.0])})
        result = resolve_field(ds, "var.x.values.1.3")
        assert "20.0" in result
        assert "30.0" in result
        assert "40.0" in result

    # -- var nonexistent --

    def test_var_nonexistent(self, sample_adcp_dataset) -> None:
        assert resolve_field(sample_adcp_dataset, "var.nonexistent.mean") == "N/A"

    # -- dim --

    def test_dim(self, sample_adcp_dataset) -> None:
        assert resolve_field(sample_adcp_dataset, "dim.time") == "100"

    def test_dim_missing(self, sample_adcp_dataset) -> None:
        assert resolve_field(sample_adcp_dataset, "dim.nonexistent") == "N/A"

    # -- coord --

    def test_coord_first(self, sample_adcp_dataset) -> None:
        result = resolve_field(sample_adcp_dataset, "coord.time.first")
        assert "2024-01-15" in result

    def test_coord_last(self, sample_adcp_dataset) -> None:
        result = resolve_field(sample_adcp_dataset, "coord.time.last")
        assert "2024-01-15" in result

    def test_coord_non_time(self, sample_adcp_dataset) -> None:
        result = resolve_field(sample_adcp_dataset, "coord.range.first")
        assert result == "0.0"

    def test_coord_missing(self, sample_adcp_dataset) -> None:
        assert resolve_field(sample_adcp_dataset, "coord.nonexistent.first") == "N/A"

    # -- computed --

    def test_computed_instrument(self, sample_adcp_dataset) -> None:
        assert resolve_field(sample_adcp_dataset, "computed.instrument") == "Nortek Signature1000"

    def test_computed_duration(self, sample_adcp_dataset) -> None:
        result = resolve_field(sample_adcp_dataset, "computed.duration")
        assert "m" in result

    def test_computed_missing(self, sample_adcp_dataset) -> None:
        assert resolve_field(sample_adcp_dataset, "computed.nonexistent") == "N/A"

    # -- file --

    def test_file_name(self, sample_adcp_dataset) -> None:
        fi = _FakeFileItem(Path("/data/test_file.ad2cp"))
        assert resolve_field(sample_adcp_dataset, "file.name", fi) == "test_file.ad2cp"

    def test_file_path(self, sample_adcp_dataset) -> None:
        fi = _FakeFileItem(Path("/data/test_file.ad2cp"))
        assert resolve_field(sample_adcp_dataset, "file.path", fi) == "/data/test_file.ad2cp"

    def test_file_extension(self, sample_adcp_dataset) -> None:
        fi = _FakeFileItem(Path("/data/test_file.ad2cp"))
        assert resolve_field(sample_adcp_dataset, "file.extension", fi) == ".ad2cp"

    def test_file_no_item(self, sample_adcp_dataset) -> None:
        assert resolve_field(sample_adcp_dataset, "file.name") == "N/A"

    # -- error handling --

    def test_garbage_path(self, sample_adcp_dataset) -> None:
        assert resolve_field(sample_adcp_dataset, "garbage") == "N/A"

    def test_empty_path(self, sample_adcp_dataset) -> None:
        assert resolve_field(sample_adcp_dataset, "") == "N/A"

    def test_empty_dataset(self) -> None:
        ds = xr.Dataset()
        assert resolve_field(ds, "attr.anything") == "N/A"


class TestListAvailableFields:
    def test_returns_all_categories(self, sample_adcp_dataset) -> None:
        fields = list_available_fields(sample_adcp_dataset)
        assert set(fields.keys()) == {"attr", "var", "dim", "coord", "computed", "file"}

    def test_attr_paths(self, sample_adcp_dataset) -> None:
        fields = list_available_fields(sample_adcp_dataset)
        assert "attr.inst_type" in fields["attr"]
        assert "attr.fs" in fields["attr"]

    def test_var_paths_include_stats(self, sample_adcp_dataset) -> None:
        fields = list_available_fields(sample_adcp_dataset)
        var_paths = fields["var"]
        assert "var.heading.mean" in var_paths
        assert "var.heading.nan_count" in var_paths
        assert "var.heading.dtype" in var_paths

    def test_computed_paths(self, sample_adcp_dataset) -> None:
        fields = list_available_fields(sample_adcp_dataset)
        assert "computed.instrument" in fields["computed"]
        assert "computed.duration" in fields["computed"]

    def test_file_paths(self, sample_adcp_dataset) -> None:
        fields = list_available_fields(sample_adcp_dataset)
        assert fields["file"] == ["file.name", "file.path", "file.extension"]
