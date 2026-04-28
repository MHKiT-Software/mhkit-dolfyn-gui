"""Modal dialog for picking a dataset field path to add to a summary template."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mhkit_dolfyn_gui.models.field_resolver import list_available_fields

if TYPE_CHECKING:
    import xarray as xr


class FieldPickerDialog(QDialog):
    """Modal dialog showing available fields grouped by category."""

    def __init__(
        self,
        ds: xr.Dataset,
        include_combined: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Field")
        self.setMinimumSize(400, 450)

        self.selected_path: str = ""
        self.selected_label: str = ""

        layout = QVBoxLayout(self)

        label_row = QHBoxLayout()
        label_row.addWidget(QLabel("Label:"))
        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("Auto-generated from path")
        label_row.addWidget(self._label_edit)
        layout.addLayout(label_row)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Field Path"])
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._tree)

        fields = list_available_fields(ds, include_combined=include_combined)
        for category, paths in fields.items():
            cat_item = QTreeWidgetItem([category])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            for path in paths:
                cat_item.addChild(QTreeWidgetItem([path]))
            self._tree.addTopLevelItem(cat_item)
        self._tree.expandAll()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        items = self._tree.selectedItems()
        if items and items[0].parent() is not None:
            self.selected_path = items[0].text(0)
            self.selected_label = self._label_edit.text().strip()
            self.accept()

    def _on_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        if item.parent() is not None:
            self.selected_path = item.text(0)
            self.selected_label = self._label_edit.text().strip()
            self.accept()
