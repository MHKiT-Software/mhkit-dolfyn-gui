"""Proxy model that filters and styles files by extension for the file tree.

Supported instrument files are shown normally.  Unsupported files are grayed
out and made non-selectable.  Files already included in the session are
rendered in bold.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import QFileSystemModel

from mhkit_dolfyn_gui.constants import SUPPORTED_EXTENSIONS
from mhkit_dolfyn_gui.styles import theme

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


class FileFilterProxyModel(QSortFilterProxyModel):
    """Filter/style proxy for ``QFileSystemModel``.

    * Directories are always shown.
    * Files with a supported extension are shown normally.
    * Other files are shown grayed-out and non-selectable.
    * Files in ``_included_paths`` are rendered bold.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._included_paths: set[Path] = set()
        self._gray_brush = QBrush(QColor(theme.text.muted))

    def set_included_paths(self, paths: set[Path]) -> None:
        """Update the set of paths shown as already-included (bold)."""
        self._included_paths = {p.resolve() for p in paths}
        self.invalidateFilter()

    # ------------------------------------------------------------------
    # QSortFilterProxyModel overrides
    # ------------------------------------------------------------------

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        model = self.sourceModel()
        if not isinstance(model, QFileSystemModel):
            return False
        idx = model.index(source_row, 0, source_parent)
        if model.isDir(idx):
            return True
        # Show all files (supported shown normally, others grayed)
        return True

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return super().data(index, role)

        source_idx = self.mapToSource(index)
        model = self.sourceModel()
        if not isinstance(model, QFileSystemModel):
            return super().data(index, role)

        # Only style the name column
        if index.column() != 0:
            return super().data(index, role)

        if not model.isDir(source_idx):
            file_path = Path(model.filePath(source_idx))
            is_supported = file_path.suffix.lower() in SUPPORTED_EXTENSIONS
            is_included = file_path.resolve() in self._included_paths

            if role == Qt.ItemDataRole.ForegroundRole and not is_supported:
                return self._gray_brush

            if role == Qt.ItemDataRole.FontRole:
                font = QFont()
                if is_included:
                    font.setBold(True)
                return font

            if role == Qt.ItemDataRole.DecorationRole and is_included:
                # Return a checkmark character via a colored icon
                # We use the ToolTipRole approach instead — see below
                pass

            if role == Qt.ItemDataRole.ToolTipRole and is_included:
                return "Already included"

        return super().data(index, role)

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        default = super().flags(index)
        source_idx = self.mapToSource(index)
        model = self.sourceModel()
        if not isinstance(model, QFileSystemModel):
            return default

        if not model.isDir(source_idx):
            file_path = Path(model.filePath(source_idx))
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                return default & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsEnabled

        return default
