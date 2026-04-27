"""Tests for ME Data Pipeline filename builder (pure transformations)."""

from datetime import datetime

import numpy as np
import pytest

from mhkit_dolfyn_gui.models.me_filename import (
    MENamingFields,
    TemporalResolution,
    build_me_filename,
    check_utc,
    format_temporal,
    resolve_fs,
    validate_me_fields,
    warn_me_fields,
)


class TestFormatTemporal:
    """format_temporal: Hz → ME temporal string with ~3 sig figs."""

    def test_250hz(self) -> None:
        assert format_temporal(250) == "250hz"

    def test_10hz(self) -> None:
        assert format_temporal(10) == "10hz"

    def test_1hz(self) -> None:
        assert format_temporal(1) == "1hz"

    def test_1_25hz(self) -> None:
        assert format_temporal(1.25) == "1.25hz"

    def test_half_hz_gives_2s(self) -> None:
        assert format_temporal(0.5) == "2s"

    def test_one_per_minute(self) -> None:
        assert format_temporal(1 / 60) == "1m"

    def test_one_per_hour(self) -> None:
        assert format_temporal(1 / 3600) == "1h"

    def test_one_per_day(self) -> None:
        assert format_temporal(1 / 86400) == "1d"

    def test_30s(self) -> None:
        assert format_temporal(1 / 30) == "30s"

    def test_5m(self) -> None:
        assert format_temporal(1 / 300) == "5m"

    def test_fractional_hz(self) -> None:
        # 2.56 Hz → "2.56hz"
        assert format_temporal(2.56) == "2.56hz"

    def test_fractional_seconds(self) -> None:
        # fs=0.4 → T=2.5s → "2.5s"
        assert format_temporal(0.4) == "2.5s"

    def test_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            format_temporal(0)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            format_temporal(-1)

    def test_inf_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            format_temporal(float("inf"))


class TestBuildMeFilename:
    """build_me_filename: golden-string tests for assembled filenames."""

    _default_fields = MENamingFields(
        location_id="axys1",
        dataset_name="adcp_vel",
        data_level="a1",
    )

    def test_full_format(self) -> None:
        result = build_me_filename(
            self._default_fields,
            temporal="10hz",
            start_dt=datetime(2021, 3, 19, 14, 47, 50),
        )
        assert result == "axys1.adcp_vel-10hz.a1.20210319.144750.nc"

    def test_with_qualifier(self) -> None:
        fields = MENamingFields(
            location_id="axys1",
            dataset_name="adcp_vel",
            qualifier="raw",
            data_level="a1",
        )
        result = build_me_filename(
            fields,
            temporal="10hz",
            start_dt=datetime(2021, 3, 19, 14, 47, 50),
        )
        assert result == "axys1.adcp_vel-raw-10hz.a1.20210319.144750.nc"

    def test_no_temporal(self) -> None:
        fields = MENamingFields(
            location_id="axys1",
            dataset_name="adcp_vel",
            data_level="a1",
            include_temporal=False,
        )
        result = build_me_filename(
            fields,
            temporal="10hz",
            start_dt=datetime(2021, 3, 19, 14, 47, 50),
        )
        assert result == "axys1.adcp_vel.a1.20210319.144750.nc"

    def test_no_data_level(self) -> None:
        fields = MENamingFields(
            location_id="axys1",
            dataset_name="adcp_vel",
            data_level="",
        )
        result = build_me_filename(
            fields,
            temporal="10hz",
            start_dt=datetime(2021, 3, 19, 14, 47, 50),
        )
        assert result == "axys1.adcp_vel-10hz.20210319.144750.nc"

    def test_profile_suffix_with_qualifier(self) -> None:
        fields = MENamingFields(
            location_id="axys1",
            dataset_name="adcp_vel",
            qualifier="main",
            data_level="a1",
        )
        result = build_me_filename(
            fields,
            temporal="1hz",
            start_dt=datetime(2021, 3, 19, 14, 47, 50),
            profile_suffix="profile_2",
        )
        assert result == "axys1.adcp_vel-main_profile_2-1hz.a1.20210319.144750.nc"

    def test_profile_suffix_no_qualifier(self) -> None:
        result = build_me_filename(
            self._default_fields,
            temporal="1hz",
            start_dt=datetime(2021, 3, 19, 14, 47, 50),
            profile_suffix="profile_2",
        )
        assert result == "axys1.adcp_vel-profile_2-1hz.a1.20210319.144750.nc"

    def test_raw_data_level(self) -> None:
        fields = MENamingFields(
            location_id="site_a",
            dataset_name="waves",
            data_level="00",
        )
        result = build_me_filename(
            fields,
            temporal="30s",
            start_dt=datetime(2024, 7, 4, 0, 0, 0),
        )
        assert result == "site_a.waves-30s.00.20240704.000000.nc"

    def test_temporal_override_used_verbatim(self) -> None:
        fields = MENamingFields(
            location_id="loc",
            dataset_name="ds",
            temporal_override="custom_rate",
        )
        # When override is set, the caller passes it through as ``temporal``.
        result = build_me_filename(
            fields,
            temporal="custom_rate",
            start_dt=datetime(2024, 1, 1, 0, 0, 0),
        )
        assert result == "loc.ds-custom_rate.a1.20240101.000000.nc"


class TestValidation:
    """validate_me_fields: hard errors that block export."""

    def test_valid_fields(self) -> None:
        fields = MENamingFields(location_id="loc1", dataset_name="data")
        assert validate_me_fields(fields) == []

    def test_empty_location_id(self) -> None:
        fields = MENamingFields(location_id="", dataset_name="data")
        errors = validate_me_fields(fields)
        assert any("location_id" in e and "required" in e for e in errors)

    def test_empty_dataset_name(self) -> None:
        fields = MENamingFields(location_id="loc", dataset_name="")
        errors = validate_me_fields(fields)
        assert any("dataset_name" in e and "required" in e for e in errors)

    def test_reserved_char_in_location(self) -> None:
        fields = MENamingFields(location_id="loc.1", dataset_name="data")
        assert any("'.'" in e or "'-'" in e for e in validate_me_fields(fields))

    def test_reserved_char_dash_in_name(self) -> None:
        fields = MENamingFields(location_id="loc", dataset_name="my-data")
        assert any("'.'" in e or "'-'" in e for e in validate_me_fields(fields))

    def test_invalid_data_level(self) -> None:
        fields = MENamingFields(location_id="loc", dataset_name="ds", data_level="c2")
        assert any("data_level" in e for e in validate_me_fields(fields))

    def test_empty_data_level_is_ok(self) -> None:
        fields = MENamingFields(location_id="loc", dataset_name="ds", data_level="")
        assert validate_me_fields(fields) == []

    def test_reserved_char_in_temporal_override(self) -> None:
        fields = MENamingFields(
            location_id="loc",
            dataset_name="ds",
            temporal_override="10.5hz",
        )
        errors = validate_me_fields(fields)
        assert any("temporal" in e for e in errors)


class TestWarnings:
    """warn_me_fields: soft warnings (allow but highlight)."""

    def test_name_ending_digit(self) -> None:
        fields = MENamingFields(location_id="loc", dataset_name="data3")
        warnings = warn_me_fields(fields)
        assert any("dataset_name" in w and "digit" in w for w in warnings)

    def test_qualifier_ending_digit(self) -> None:
        fields = MENamingFields(location_id="loc", dataset_name="data", qualifier="v2")
        warnings = warn_me_fields(fields)
        assert any("qualifier" in w and "digit" in w for w in warnings)

    def test_no_warning_for_good_names(self) -> None:
        fields = MENamingFields(location_id="loc", dataset_name="data", qualifier="raw")
        assert warn_me_fields(fields) == []


class TestResolveFs:
    """resolve_fs: fs from attrs or median Δt fallback."""

    def test_attrs_fs_primary(self) -> None:
        result = resolve_fs(attrs_fs=10.0, time_values=None)
        assert result == TemporalResolution(fs_hz=10.0, source="attrs")

    def test_median_dt_fallback(self) -> None:
        # 10 evenly-spaced timestamps at 1-second intervals → 1 Hz
        base = np.datetime64("2024-01-01T00:00:00", "ns")
        times = np.array([base + np.timedelta64(i, "s") for i in range(10)])
        result = resolve_fs(attrs_fs=None, time_values=times)
        assert result.source == "median_dt"
        assert result.fs_hz == pytest.approx(1.0)
        assert result.warning is None

    def test_median_dt_with_variance(self) -> None:
        base = np.datetime64("2024-01-01T00:00:00", "ns")
        # Alternating 1s and 3s gaps — high variance
        offsets = [0, 1, 4, 5, 8, 9, 12, 13, 16, 17]
        times = np.array([base + np.timedelta64(s, "s") for s in offsets])
        result = resolve_fs(attrs_fs=None, time_values=times)
        assert result.source == "median_dt"
        assert result.warning is not None
        assert "varies" in result.warning

    def test_no_data_returns_none(self) -> None:
        result = resolve_fs(attrs_fs=None, time_values=None)
        assert result.fs_hz is None
        assert result.source == "none"

    def test_single_timestamp(self) -> None:
        times = np.array([np.datetime64("2024-01-01T00:00:00", "ns")])
        result = resolve_fs(attrs_fs=None, time_values=times)
        assert result.fs_hz is None
        assert result.source == "none"


class TestCheckUtc:
    """check_utc: best-effort tz detection from dataset attrs."""

    def test_utc_attribute(self) -> None:
        is_utc, msg = check_utc({"time_zone": "UTC"})
        assert is_utc is True
        assert msg is None

    def test_gmt_attribute(self) -> None:
        is_utc, _msg = check_utc({"timezone": "GMT"})
        assert is_utc is True

    def test_non_utc_attribute(self) -> None:
        is_utc, msg = check_utc({"time_zone": "US/Pacific"})
        assert is_utc is False
        assert "US/Pacific" in (msg or "")

    def test_no_attribute(self) -> None:
        is_utc, msg = check_utc({})
        assert is_utc is False
        assert "No time zone" in (msg or "")
