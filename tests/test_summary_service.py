"""Tests for the pure summary template resolution service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import xarray as xr

from mhkit_dolfyn_gui.models.file_item import FileItem
from mhkit_dolfyn_gui.models.summary_template import (
    SummaryField,
    SummaryTemplate,
    get_default_combined_template,
    get_default_template,
)
from mhkit_dolfyn_gui.services.summary_service import resolve_template

if TYPE_CHECKING:
    from pathlib import Path


def _make_dataset() -> xr.Dataset:
    times = pd.date_range("2024-01-01", periods=4, freq="1h")
    ds = xr.Dataset(
        data_vars={"vel": (("time",), np.array([1.0, 2.0, 3.0, 4.0]))},
        coords={"time": times},
        attrs={
            "inst_make": "Nortek",
            "inst_model": "Signature1000",
            "inst_type": "ADCP",
            "serial_number": "SN123",
            "coord_sys": "earth",
            "fs": 8,
            "n_bins": 20,
            "n_beams": 4,
        },
    )
    return ds


def _make_item(tmp_path: Path, ds: xr.Dataset) -> FileItem:
    p = tmp_path / "file.ad2cp"
    p.write_bytes(b"")
    item = FileItem(path=p)
    item.dataset = ds
    return item


class TestResolveTemplatePerFile:
    def test_default_template_resolves_all_rows(self, tmp_path: Path) -> None:
        ds = _make_dataset()
        item = _make_item(tmp_path, ds)
        template = get_default_template()

        rows = resolve_template(template, ds=ds, file_item=item)

        expected_count = len(template.left) + len(template.right)
        assert len(rows) == expected_count
        # Order: all left rows first, then all right rows
        left_rows = [r for r in rows if r.column == "left"]
        right_rows = [r for r in rows if r.column == "right"]
        assert len(left_rows) == len(template.left)
        assert len(right_rows) == len(template.right)
        # No row should be empty string
        assert all(r.value for r in rows)

    def test_unknown_path_returns_na(self, tmp_path: Path) -> None:
        ds = _make_dataset()
        item = _make_item(tmp_path, ds)
        template = SummaryTemplate(
            name="t",
            left=[SummaryField(path="attr.does_not_exist", label="Missing")],
        )

        rows = resolve_template(template, ds=ds, file_item=item)

        assert rows[0].value == "N/A"

    def test_no_dataset_returns_na_rows(self) -> None:
        template = SummaryTemplate(
            name="t",
            left=[SummaryField(path="attr.inst_make", label="Make")],
        )
        rows = resolve_template(template, ds=None, file_item=None)
        assert rows[0].value == "N/A"


class TestResolveTemplateCombined:
    def test_combined_template_resolves(self, tmp_path: Path) -> None:
        items = []
        for name in ("a.ad2cp", "b.ad2cp"):
            p = tmp_path / name
            p.write_bytes(b"")
            item = FileItem(path=p)
            item.dataset = _make_dataset()
            items.append(item)

        template = get_default_combined_template()
        rows = resolve_template(template, ds=items[0].dataset, file_item=items[0], items=items)

        expected_count = len(template.left) + len(template.right)
        assert len(rows) == expected_count
        # The "files_loaded" combined field should report 2
        files_loaded = [r for r in rows if r.field.path == "combined.files_loaded"]
        assert files_loaded
        assert files_loaded[0].value == "2"
