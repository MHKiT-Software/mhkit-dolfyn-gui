"""Detail panel showing statistics and sample values for a selected variable."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mhkit_dolfyn_gui.data_to_display_string_formatters import human_shape
from mhkit_dolfyn_gui.styles import theme
from mhkit_dolfyn_gui.unit_conversions import format_bytes

if TYPE_CHECKING:
    import xarray as xr


class VariableDetail(QWidget):
    """Shows shape, dtype, stats, and sample values for a variable in a table."""

    # Section header rows are styled distinctly so groups are scannable.
    _SECTIONS = ("Shape & Size", "Statistics", "Sample Values")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.layout.no_margin)

        self._group = QGroupBox("Variable Detail")
        group_layout = QVBoxLayout(self._group)
        group_layout.setContentsMargins(*theme.layout.no_margin)

        self._tree = QTreeWidget(self._group)
        self._tree.setHeaderLabels(["Property", "Value"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setStretchLastSection(True)
        group_layout.addWidget(self._tree)
        layout.addWidget(self._group)

        self._placeholder = QLabel("Click a variable in the tree to see details.")
        self._placeholder.setStyleSheet(theme.placeholder)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._placeholder)

        self._group.hide()

    def show_variable(self, name: str, var: xr.DataArray) -> None:
        """Populate the detail panel with stats for the given variable."""
        self._tree.clear()
        self._placeholder.hide()
        self._group.show()

        # Title with units
        units = var.attrs.get("units", "")
        long_name = var.attrs.get("long_name", var.attrs.get("standard_name", ""))
        title_parts = [name]
        if long_name:
            title_parts.append(f"({long_name})")
        if units:
            title_parts.append(f"[{units}]")
        self._group.setTitle(" ".join(title_parts))

        self._add_shape_section(var)

        if np.issubdtype(var.dtype, np.datetime64):
            self._add_time_section(var)
        elif np.issubdtype(var.dtype, np.number):
            self._add_numeric_section(var)
        else:
            self._add_generic_section(var)

        self._add_samples_section(var)

    def clear(self) -> None:
        """Reset to placeholder state."""
        self._tree.clear()
        self._group.hide()
        self._placeholder.show()

    # Sections
    def _add_shape_section(self, var: xr.DataArray) -> None:
        self._add_section("Shape & Size")
        self._add_row("Type", str(var.dtype))
        dims_str = human_shape(tuple(str(d) for d in var.dims), var.shape)
        self._add_row("Shape", dims_str)
        self._add_row("Dimensions", ", ".join(str(d) for d in var.dims) if var.dims else "—")
        self._add_row("Total elements", f"{var.size:,}")
        self._add_row("Memory", format_bytes(var.nbytes))

    def _add_numeric_section(self, var: xr.DataArray) -> None:
        self._add_section("Statistics")
        values = var.values.ravel()
        is_float = np.issubdtype(values.dtype, np.floating)
        nan_count = int(np.isnan(values).sum()) if is_float else 0
        total = values.size
        valid = values[~np.isnan(values)] if nan_count > 0 else values

        if valid.size > 0:
            self._add_row("Min", f"{np.nanmin(valid):.6g}")
            self._add_row("Max", f"{np.nanmax(valid):.6g}")
            self._add_row("Mean", f"{np.nanmean(valid):.6g}")
            self._add_row("Median", f"{np.nanmedian(valid):.6g}")
            self._add_row("Std", f"{np.nanstd(valid):.6g}")
        else:
            self._add_row("Values", "All NaN")

        if is_float:
            pct = (nan_count / total * 100) if total > 0 else 0
            self._add_row("NaN", f"{nan_count:,} / {total:,} ({pct:.1f}%)")
        if valid.size > 0:
            finite = valid[np.isfinite(valid)] if is_float else valid
            self._add_row("Finite", f"{finite.size:,} / {total:,}")

    def _add_time_section(self, var: xr.DataArray) -> None:
        import pandas as pd

        self._add_section("Statistics")
        values = var.values
        if values.size == 0:
            self._add_row("Values", "Empty")
            return

        first_ts = pd.Timestamp(values[0])
        last_ts = pd.Timestamp(values[-1])
        self._add_row("First", str(first_ts))
        self._add_row("Last", str(last_ts))
        self._add_row("Duration", str(last_ts - first_ts))
        self._add_row("Steps", f"{values.size:,}")
        if values.size > 1:
            step = pd.Timestamp(values[1]) - first_ts
            self._add_row("Step size", str(step))

    def _add_generic_section(self, var: xr.DataArray) -> None:
        self._add_section("Statistics")
        values = var.values.ravel()
        try:
            unique = np.unique(values)
            self._add_row("Unique", f"{unique.size:,}")
        except (TypeError, ValueError):
            pass

    def _add_samples_section(self, var: xr.DataArray) -> None:
        flat = var.values.ravel()
        if flat.size == 0:
            return
        self._add_section("Sample Values")
        n = min(5, flat.size)
        is_numeric = np.issubdtype(flat.dtype, np.number)
        fmt = (lambda v: f"{v:.6g}") if is_numeric else str
        self._add_row(f"First {n}", ", ".join(fmt(v) for v in flat[:n]))
        self._add_row(f"Last {n}", ", ".join(fmt(v) for v in flat[-n:]))

    # Helpers
    def _add_section(self, title: str) -> None:
        item = QTreeWidgetItem(self._tree, [title, ""])
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        item.setFirstColumnSpanned(True)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)

    def _add_row(self, label: str, value: str) -> None:
        item = QTreeWidgetItem(self._tree, [label, value])
        item.setFont(1, theme.mono_qfont())
        item.setToolTip(1, value)
