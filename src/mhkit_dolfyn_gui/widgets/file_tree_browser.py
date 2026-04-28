"""Navigable file system tree browser for ADCP/ADV instrument files.

Composes a :class:`BreadcrumbBar` for path navigation and a ``QTreeView``
backed by ``QFileSystemModel`` + :class:`FileFilterProxyModel`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileSystemModel,
    QHeaderView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from mhkit_dolfyn_gui.constants import SUPPORTED_EXTENSIONS
from mhkit_dolfyn_gui.styles import theme
from mhkit_dolfyn_gui.widgets.breadcrumb_bar import BreadcrumbBar
from mhkit_dolfyn_gui.widgets.file_filter_proxy import FileFilterProxyModel

if TYPE_CHECKING:
    from PySide6.QtCore import QModelIndex

_SETTINGS_KEY = "browser/last_dir"


class FileTreeBrowser(QWidget):
    """File system tree with breadcrumb navigation and extension filtering.

    Signals:
        file_activated: Emitted with the ``Path`` of a supported file on double-click.
        directory_changed: Emitted with the new directory path after navigation.
    """

    file_activated = Signal(Path)
    directory_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.layout.no_margin)
        layout.setSpacing(theme.layout.spacing_xs)

        # Breadcrumb bar
        self._breadcrumb = BreadcrumbBar()
        self._breadcrumb.path_clicked.connect(self.set_folder)
        layout.addWidget(self._breadcrumb)

        # File system model
        self._fs_model = QFileSystemModel()
        self._fs_model.setReadOnly(True)
        self._fs_model.setRootPath("")

        # Proxy model for filtering/styling
        self._proxy = FileFilterProxyModel(self)
        self._proxy.setSourceModel(self._fs_model)

        # Tree view
        self._tree = QTreeView()
        self._tree.setModel(self._proxy)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setAlternatingRowColors(True)
        self._tree.setAnimated(False)
        self._tree.setIndentation(20)
        self._tree.setHeaderHidden(True)

        # Hide all columns except Name
        header = self._tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, self._fs_model.columnCount()):
            self._tree.setColumnHidden(col, True)

        self._tree.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._tree, stretch=1)

        # Navigate to last-used or home directory
        qs = QSettings()
        start_dir = str(qs.value(_SETTINGS_KEY, str(Path.home())))
        if not Path(start_dir).is_dir():
            start_dir = str(Path.home())
        self.set_folder(start_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_folder(self, path: str) -> None:
        """Navigate the tree to *path* and update the breadcrumb."""
        resolved = str(Path(path).resolve())
        source_idx = self._fs_model.index(resolved)
        proxy_idx = self._proxy.mapFromSource(source_idx)
        self._tree.setRootIndex(proxy_idx)
        self._breadcrumb.set_path(resolved)

        # Persist
        qs = QSettings()
        qs.setValue(_SETTINGS_KEY, resolved)
        self.directory_changed.emit(resolved)

    @property
    def current_folder(self) -> str:
        return self._breadcrumb.current_path()

    def set_included_paths(self, paths: set[Path]) -> None:
        """Forward to proxy model to bold already-included files."""
        self._proxy.set_included_paths(paths)

    def go_up(self) -> None:
        """Navigate to the parent directory."""
        current = Path(self.current_folder)
        parent = current.parent
        if parent != current:
            self.set_folder(str(parent))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_double_click(self, proxy_idx: QModelIndex) -> None:
        source_idx = self._proxy.mapToSource(proxy_idx)
        if self._fs_model.isDir(source_idx):
            self.set_folder(self._fs_model.filePath(source_idx))
        else:
            file_path = Path(self._fs_model.filePath(source_idx))
            if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                self.file_activated.emit(file_path)
