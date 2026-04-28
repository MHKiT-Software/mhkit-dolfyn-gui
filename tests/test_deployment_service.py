"""Tests for the pure deployment-analysis service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import xarray as xr

from mhkit_dolfyn_gui.constants import DEFAULT_TIME_GAP_THRESHOLD_SECONDS
from mhkit_dolfyn_gui.models.file_item import FileItem
from mhkit_dolfyn_gui.services.deployment_service import analyze

if TYPE_CHECKING:
    from pathlib import Path


def _make_item(
    tmp_path: Path,
    name: str,
    start: str,
    periods: int = 4,
    freq: str = "1h",
    inst_make: str = "Nortek",
    inst_model: str = "Signature1000",
    coord_sys: str = "earth",
    fs: int = 8,
) -> FileItem:
    times = pd.date_range(start, periods=periods, freq=freq)
    ds = xr.Dataset(
        data_vars={"vel": (("time",), np.zeros(periods))},
        coords={"time": times},
        attrs={
            "inst_make": inst_make,
            "inst_model": inst_model,
            "coord_sys": coord_sys,
            "fs": fs,
        },
    )
    p = tmp_path / name
    p.write_bytes(b"")
    item = FileItem(path=p)
    item.dataset = ds
    return item


class TestAnalyze:
    def test_empty_input(self) -> None:
        result = analyze([], DEFAULT_TIME_GAP_THRESHOLD_SECONDS)
        assert result.sorted_items == ()
        assert result.coverage == ()
        assert result.gaps == ()
        assert result.mismatches == ()

    def test_skips_items_without_dataset(self, tmp_path: Path) -> None:
        unloaded = FileItem(path=tmp_path / "x.ad2cp")
        loaded = _make_item(tmp_path, "a.ad2cp", "2024-01-01")
        result = analyze([unloaded, loaded], DEFAULT_TIME_GAP_THRESHOLD_SECONDS)
        assert len(result.sorted_items) == 1
        assert result.sorted_items[0] is loaded

    def test_sorts_by_start_time(self, tmp_path: Path) -> None:
        a = _make_item(tmp_path, "a.ad2cp", "2024-01-02")
        b = _make_item(tmp_path, "b.ad2cp", "2024-01-01")
        result = analyze([a, b], DEFAULT_TIME_GAP_THRESHOLD_SECONDS)
        assert [it.path.name for it in result.sorted_items] == ["b.ad2cp", "a.ad2cp"]

    def test_contiguous_files_have_no_gap(self, tmp_path: Path) -> None:
        a = _make_item(tmp_path, "a.ad2cp", "2024-01-01 00:00", periods=4, freq="1h")
        # b starts 1 second after a ends → well below threshold
        b = _make_item(tmp_path, "b.ad2cp", "2024-01-01 03:00:01", periods=4, freq="1h")
        result = analyze([a, b], DEFAULT_TIME_GAP_THRESHOLD_SECONDS)
        assert result.gaps == ()

    def test_large_gap_is_detected(self, tmp_path: Path) -> None:
        a = _make_item(tmp_path, "a.ad2cp", "2024-01-01 00:00", periods=4, freq="1h")
        # 2 hours after a ends
        b = _make_item(tmp_path, "b.ad2cp", "2024-01-01 05:00", periods=4, freq="1h")
        result = analyze([a, b], DEFAULT_TIME_GAP_THRESHOLD_SECONDS)
        assert len(result.gaps) == 1
        assert result.gaps[0].before is a
        assert result.gaps[0].after is b
        assert result.gaps[0].delta.total_seconds() > 0

    def test_overlap_is_detected(self, tmp_path: Path) -> None:
        a = _make_item(tmp_path, "a.ad2cp", "2024-01-01 00:00", periods=4, freq="1h")
        # b starts 1 hour before a ends
        b = _make_item(tmp_path, "b.ad2cp", "2024-01-01 02:00", periods=4, freq="1h")
        result = analyze([a, b], DEFAULT_TIME_GAP_THRESHOLD_SECONDS)
        assert len(result.gaps) == 1
        assert result.gaps[0].delta.total_seconds() < 0

    def test_instrument_mismatch(self, tmp_path: Path) -> None:
        a = _make_item(tmp_path, "a.ad2cp", "2024-01-01")
        b = _make_item(tmp_path, "b.ad2cp", "2024-01-02", inst_model="Signature500")
        result = analyze([a, b], DEFAULT_TIME_GAP_THRESHOLD_SECONDS)
        attrs = [m.attribute for m in result.mismatches]
        assert "Instrument" in attrs

    def test_coord_and_fs_mismatch(self, tmp_path: Path) -> None:
        a = _make_item(tmp_path, "a.ad2cp", "2024-01-01")
        b = _make_item(tmp_path, "b.ad2cp", "2024-01-02", coord_sys="beam", fs=16)
        result = analyze([a, b], DEFAULT_TIME_GAP_THRESHOLD_SECONDS)
        attrs = {m.attribute for m in result.mismatches}
        assert "Coordinate system" in attrs
        assert "Sampling frequency" in attrs

    def test_no_mismatches_for_identical_items(self, tmp_path: Path) -> None:
        a = _make_item(tmp_path, "a.ad2cp", "2024-01-01")
        b = _make_item(tmp_path, "b.ad2cp", "2024-01-02")
        result = analyze([a, b], DEFAULT_TIME_GAP_THRESHOLD_SECONDS)
        assert result.mismatches == ()

    def test_coverage_durations(self, tmp_path: Path) -> None:
        a = _make_item(tmp_path, "a.ad2cp", "2024-01-01", periods=4, freq="1h")
        result = analyze([a], DEFAULT_TIME_GAP_THRESHOLD_SECONDS)
        assert len(result.coverage) == 1
        row = result.coverage[0]
        assert row.duration is not None
        assert row.duration.total_seconds() > 0
