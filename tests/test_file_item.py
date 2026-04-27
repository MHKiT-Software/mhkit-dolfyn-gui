"""Tests for FileItem dataclass."""

from pathlib import Path

from mhkit_dolfyn_gui.models.file_item import FileItem, FileStatus


class TestFileItem:
    def test_default_status(self) -> None:
        item = FileItem(path=Path("/tmp/test.ad2cp"))
        assert item.status == FileStatus.PENDING
        assert item.dataset is None
        assert item.error is None

    def test_filename_and_extension(self) -> None:
        item = FileItem(path=Path("/data/RDI_test01.000"))
        assert item.filename == "RDI_test01"
        assert item.extension == ".000"

    def test_extension_lowercase(self) -> None:
        item = FileItem(path=Path("/data/vector.VEC"))
        assert item.extension == ".vec"

    def test_summary_without_dataset(self) -> None:
        item = FileItem(path=Path("/tmp/test.ad2cp"))
        assert item.summary == {}

    def test_summary_with_dataset(self, sample_adcp_dataset) -> None:
        item = FileItem(path=Path("/tmp/test.ad2cp"))
        item.dataset = sample_adcp_dataset
        item.status = FileStatus.READY
        summary = item.summary
        assert summary["Instrument"] == "Nortek Signature1000"
        assert summary["Serial"] == "12345"
        assert summary["Coord System"] == "beam"
        assert "1.0" in summary["Sampling Freq"]
        assert summary["Ensembles"] == "100"

    def test_start_end_time(self, sample_adcp_dataset) -> None:
        item = FileItem(path=Path("/tmp/test.ad2cp"))
        item.dataset = sample_adcp_dataset
        assert item.start_time is not None
        assert item.end_time is not None
        assert item.start_time < item.end_time

    def test_times_none_without_dataset(self) -> None:
        item = FileItem(path=Path("/tmp/test.ad2cp"))
        assert item.start_time is None
        assert item.end_time is None

    def test_all_datasets_empty(self) -> None:
        item = FileItem(path=Path("/tmp/test.ad2cp"))
        assert item.all_datasets == ()

    def test_all_datasets_single(self, sample_adcp_dataset) -> None:
        item = FileItem(path=Path("/tmp/test.ad2cp"))
        item.dataset = sample_adcp_dataset
        assert item.all_datasets == (sample_adcp_dataset,)

    def test_all_datasets_dual_profile(self, sample_adcp_dataset, sample_adv_dataset) -> None:
        item = FileItem(path=Path("/tmp/test.ad2cp"))
        item.dataset = sample_adcp_dataset
        item.extra_datasets = (sample_adv_dataset,)
        assert item.all_datasets == (sample_adcp_dataset, sample_adv_dataset)

    def test_format_for_list(self) -> None:
        item = FileItem(path=Path("/tmp/test.ad2cp"))
        assert item.format_for_list() == "[ ] test.ad2cp"

        item.status = FileStatus.READING
        assert "[...]" in item.format_for_list()

        item.status = FileStatus.READY
        assert "[ok]" in item.format_for_list()

        item.status = FileStatus.ERROR
        assert "[X]" in item.format_for_list()
