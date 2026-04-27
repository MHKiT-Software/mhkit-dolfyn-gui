"""Tests for FilenamePattern template rendering."""

from datetime import datetime

from mhkit_dolfyn_gui.models.filename_pattern import FilenamePattern


class TestFilenamePattern:
    def test_default_pattern(self) -> None:
        pat = FilenamePattern.default()
        result = pat.render(
            filename="RDI_test01",
            start_date=datetime(2024, 1, 15),
            index=1,
        )
        assert result == "RDI_test01_20240115.nc"

    def test_start_and_end_date(self) -> None:
        pat = FilenamePattern("{start_date:%Y%m%d}_{end_date:%Y%m%d}.nc")
        result = pat.render(
            filename="test",
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 16),
            index=1,
        )
        assert result == "20240115_20240116.nc"

    def test_profile_token(self) -> None:
        pat = FilenamePattern("{filename}_p{profile}.nc")
        assert pat.render(filename="data", profile=2) == "data_p2.nc"
        assert pat.validate() == []

    def test_index_formatting(self) -> None:
        pat = FilenamePattern("{filename}_{index:03d}.nc")
        result = pat.render(filename="data", index=7)
        assert result == "data_007.nc"

    def test_custom_date_format(self) -> None:
        pat = FilenamePattern("{start_date:%Y-%m-%d_%H%M}.nc")
        result = pat.render(
            filename="test",
            start_date=datetime(2024, 1, 15, 8, 30),
        )
        assert result == "2024-01-15_0830.nc"

    def test_no_date_fallback(self) -> None:
        pat = FilenamePattern("{start_date:%Y%m%d}.nc")
        result = pat.render(filename="test", start_date=None)
        assert result == "no-date.nc"

    def test_filename_only(self) -> None:
        pat = FilenamePattern("{filename}.nc")
        result = pat.render(filename="my_adcp_file")
        assert result == "my_adcp_file.nc"

    def test_all_tokens(self) -> None:
        pat = FilenamePattern("{filename}_{start_date:%Y%m%d}_{end_date:%Y%m%d}_{index:02d}.nc")
        result = pat.render(
            filename="sig1000",
            start_date=datetime(2024, 6, 1),
            end_date=datetime(2024, 6, 2),
            index=3,
        )
        assert result == "sig1000_20240601_20240602_03.nc"

    def test_validate_valid_pattern(self) -> None:
        pat = FilenamePattern.default()
        errors = pat.validate()
        assert errors == []

    def test_validate_unknown_token(self) -> None:
        pat = FilenamePattern("{bogus_token}.nc")
        errors = pat.validate()
        assert any("Unknown token" in e for e in errors)

    def test_validate_missing_nc_extension(self) -> None:
        pat = FilenamePattern("{filename}.csv")
        errors = pat.validate()
        assert any(".nc" in e for e in errors)

    def test_validate_bad_format_spec(self) -> None:
        pat = FilenamePattern("{index:zzz}.nc")
        errors = pat.validate()
        assert any("INVALID_PATTERN" in e for e in errors)
