"""Tree view of an xarray Dataset structure with human-readable labels.

Branches: Dimensions, Coordinate Axes, Measurement Variables, Derived Variables,
Metadata. Emits variable_clicked when user clicks on a data variable, coordinate,
or derived variable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHeaderView, QTreeWidget, QTreeWidgetItem

from mhkit_dolfyn_gui.data_to_display_string_formatters import human_dtype, human_shape, truncate
from mhkit_dolfyn_gui.services.export_pipeline import derived_velocity_pairs

if TYPE_CHECKING:
    import xarray as xr
    from PySide6.QtWidgets import QWidget


class DatasetTree(QTreeWidget):
    """Shows the structure of an xarray Dataset as an expandable tree.

    Top-level branches: Dimensions, Coordinate Axes, Measurement Variables,
    Derived Variables, Metadata.
    """

    variable_clicked = Signal(str, object)  # (var_name, xr.DataArray)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderLabels(["Name", "Details"])
        self.setAlternatingRowColors(True)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.header().setStretchLastSection(True)

        self._dataset: xr.Dataset | None = None
        self._derived_data: dict[str, xr.DataArray] = {}
        self.itemClicked.connect(self._on_item_clicked)

    def set_dataset(self, ds: xr.Dataset) -> None:
        """Populate the tree from an xarray Dataset."""
        self.clear()
        self._dataset = ds

        # Dimensions
        dims_root = QTreeWidgetItem(self, ["Dimensions", ""])
        for name, size in ds.sizes.items():
            QTreeWidgetItem(dims_root, [str(name), f"{size:,}"])

        # Coordinate Axes
        coords_root = QTreeWidgetItem(self, ["Coordinate Axes", ""])
        for name, coord in ds.coords.items():
            detail = self._format_var_detail(coord)
            ci = QTreeWidgetItem(coords_root, [self._display_name(str(name), coord), detail])
            ci.setToolTip(0, f"Coordinate: {name} (click for details)")

        # Measurement Variables
        vars_root = QTreeWidgetItem(self, ["Measurement Variables", ""])
        for name, var in ds.data_vars.items():
            detail = self._format_var_detail(var)
            var_item = QTreeWidgetItem(vars_root, [self._display_name(str(name), var), detail])
            var_item.setToolTip(0, f"Variable: {name} (click for details)")
            # Variable-level attributes (collapsed by default)
            for attr_name, attr_val in var.attrs.items():
                QTreeWidgetItem(var_item, [str(attr_name), truncate(attr_val)])

        # Derived Variables (computed via mhkit.dolfyn's velds accessor)
        self._derived_data = dict(derived_velocity_pairs(ds))
        derived_root = None
        if self._derived_data:
            derived_root = QTreeWidgetItem(self, ["Derived Variables", ""])
            italic_font = QFont()
            italic_font.setItalic(True)
            for name, da in self._derived_data.items():
                detail = self._format_var_detail(da)
                derived_item = QTreeWidgetItem(derived_root, [self._display_name(name, da), detail])
                derived_item.setFont(0, italic_font)
                derived_item.setToolTip(
                    0,
                    "Derived from measured data — not present in the raw file (click for details)",
                )

        # Metadata (global attributes)
        attrs_root = QTreeWidgetItem(self, ["Metadata", ""])
        for attr_name, attr_val in ds.attrs.items():
            QTreeWidgetItem(attrs_root, [str(attr_name), truncate(attr_val)])

        # Expand useful branches, collapse detail-heavy ones
        self.expandItem(dims_root)
        self.expandItem(coords_root)
        self.expandItem(vars_root)
        if derived_root is not None:
            self.expandItem(derived_root)
        # Metadata and variable attrs stay collapsed

    def clear_dataset(self) -> None:
        """Remove all items."""
        self.clear()
        self._dataset = None
        self._derived_data = {}

    def _format_var_detail(self, var: xr.DataArray) -> str:
        """Build a human-readable detail string for a variable."""
        dtype_str = human_dtype(var.dtype)
        shape_str = human_shape(tuple(str(d) for d in var.dims), var.shape)
        parts = [dtype_str, shape_str]

        units = var.attrs.get("units")
        if units:
            parts.append(f"[{units}]")

        return ", ".join(parts)

    @staticmethod
    def _display_name(name: str, var: xr.DataArray) -> str:
        """Use long_name or standard_name as primary label if available."""
        long_name = var.attrs.get("long_name") or var.attrs.get("standard_name")
        if long_name:
            return f"{long_name} ({name})"
        return str(name)

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """Emit variable_clicked if the user clicked a data var or coordinate."""
        if self._dataset is None:
            return

        # Only respond to direct children of Coordinate Axes or Measurement Variables
        parent = item.parent()
        if parent is None:
            return

        parent_text = parent.text(0)
        if parent_text not in ("Coordinate Axes", "Measurement Variables", "Derived Variables"):
            return

        if parent_text == "Derived Variables":
            name = self._extract_paren_name(item.text(0))
            if name is not None and name in self._derived_data:
                self.variable_clicked.emit(name, self._derived_data[name])
            return

        # Extract the xarray name — it may be in parens if we used a display name
        item_text = item.text(0)
        var_name = self._extract_var_name(item_text, parent_text)
        if var_name is None:
            return

        if parent_text == "Coordinate Axes" and var_name in self._dataset.coords:
            self.variable_clicked.emit(var_name, self._dataset.coords[var_name])
        elif parent_text == "Measurement Variables" and var_name in self._dataset.data_vars:
            self.variable_clicked.emit(var_name, self._dataset.data_vars[var_name])

    @staticmethod
    def _extract_paren_name(display_text: str) -> str | None:
        """Recover the internal name from a "long_name (name)" display string."""
        if "(" in display_text and display_text.endswith(")"):
            return display_text.rsplit("(", 1)[1].rstrip(")")
        return None

    def _extract_var_name(self, display_text: str, parent_text: str) -> str | None:
        """Extract the xarray variable name from the display text."""
        # If format is "long_name (var_name)", extract var_name
        if "(" in display_text and display_text.endswith(")"):
            name = display_text.rsplit("(", 1)[1].rstrip(")")
        else:
            name = display_text

        ds = self._dataset
        if ds is None:
            return None

        if parent_text == "Coordinate Axes" and name in ds.coords:
            return name
        if parent_text == "Measurement Variables" and name in ds.data_vars:
            return name
        return None
