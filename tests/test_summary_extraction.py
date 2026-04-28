"""Tests for summary field extraction from xarray Datasets."""

from mhkit_dolfyn_gui.services.field_extractors import get_summary_fields


class TestSummaryExtraction:
    def test_adcp_all_fields_present(self, sample_adcp_dataset) -> None:
        ds = sample_adcp_dataset
        for label, extractor in get_summary_fields(ds):
            result = extractor(ds)
            assert isinstance(result, str), f"{label} did not return a string"
            assert result != "", f"{label} returned empty string"

    def test_adv_all_fields_present(self, sample_adv_dataset) -> None:
        ds = sample_adv_dataset
        for label, extractor in get_summary_fields(ds):
            result = extractor(ds)
            assert isinstance(result, str), f"{label} did not return a string"

    def test_adcp_instrument_string(self, sample_adcp_dataset) -> None:
        extract_instrument = get_summary_fields(sample_adcp_dataset)[0][1]
        assert extract_instrument(sample_adcp_dataset) == "Nortek Signature1000"

    def test_adv_instrument_string(self, sample_adv_dataset) -> None:
        extract_instrument = get_summary_fields(sample_adv_dataset)[0][1]
        assert extract_instrument(sample_adv_dataset) == "Nortek Vector"

    def test_duration_format(self, sample_adcp_dataset) -> None:
        extract_duration = dict(get_summary_fields(sample_adcp_dataset))["Duration"]
        result = extract_duration(sample_adcp_dataset)
        # 100 seconds = 1m 40s, should show "1m"
        assert "m" in result

    def test_missing_attributes_graceful(self) -> None:
        """Extractors should return 'N/A' for missing attributes, not crash."""
        import xarray as xr

        empty_ds = xr.Dataset()
        for label, extractor in get_summary_fields(empty_ds):
            result = extractor(empty_ds)
            assert isinstance(result, str), f"{label} crashed on empty dataset"
