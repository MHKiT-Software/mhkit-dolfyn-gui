"""Files-to-Convert panel: tree browser + checkable file list + buttons.

Owns the canonical ``list[FileItem]`` for the file sidebar.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSplitter,
    QToolButton,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mhkit_dolfyn_gui.constants import FILE_FILTER
from mhkit_dolfyn_gui.models.file_item import FileItem, FileStatus
from mhkit_dolfyn_gui.services.userdata_service import sidecar_path_for
from mhkit_dolfyn_gui.styles import theme
from mhkit_dolfyn_gui.widgets.file_sidebar.constants import (
    COL_CONVERT,
    COL_FILE,
    COL_REMOVE,
    COL_STATUS,
    STATUS_TEXT_COLORS,
    status_label,
)
from mhkit_dolfyn_gui.widgets.file_sidebar.files_tree import FilesTreeWidget
from mhkit_dolfyn_gui.widgets.file_tree_browser import FileTreeBrowser
from mhkit_dolfyn_gui.widgets.userdata_editor import UserdataEditor

if TYPE_CHECKING:
    from PySide6.QtCore import QPoint

log = logging.getLogger(__name__)


class FileListPanel(QWidget):
    """Single source of truth for ``list[FileItem]`` in the sidebar.

    No other widget keeps its own copy of FileItems; observers subscribe
    to the signals below and refresh from the payload.

    Signals
    -------
    files_added(list[Path])
        Fired once per add operation with the *new* paths only.
    files_changed(list[FileItem])
        Fired on every mutation (add, remove, clear) with the *full*
        current list. Subscribe to this to refresh a view.
    file_clicked(int)
        The user selected a row.
    cleared()
        The list went from non-empty to empty.
    check_state_changed(int, bool)
        A row's checkbox toggled. This is the canonical state — observers
        echoing checkboxes elsewhere update from this signal and push
        user intent back via :meth:`set_item_checked`.
    """

    files_added = Signal(list)  # list[Path]
    file_clicked = Signal(int)
    check_state_changed = Signal(int, bool)
    cleared = Signal()
    files_changed = Signal(list)  # list[FileItem]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._file_items: list[FileItem] = []
        self._last_dir = str(Path.home())
        self._global_userdata_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.layout.no_margin)
        layout.setSpacing(theme.layout.spacing_xs)

        # Splitter: tree browser (top) + files-to-convert panel (bottom)
        self._splitter = QSplitter(Qt.Orientation.Vertical)

        self._browser = FileTreeBrowser()
        self._browser.file_activated.connect(self._on_tree_file_activated)
        self._splitter.addWidget(self._browser)

        self._splitter.addWidget(self._build_files_panel())

        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)
        layout.addWidget(self._splitter, stretch=1)

    def _build_files_panel(self) -> QWidget:
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setContentsMargins(*theme.layout.no_margin)
        v.setSpacing(theme.layout.spacing_xs)

        self._header = QLabel("Files to Convert")
        self._header.setStyleSheet(theme.included_header)
        v.addWidget(self._header)

        self._tree = FilesTreeWidget()
        self._tree.itemChanged.connect(self._on_item_changed)
        self._tree.currentItemChanged.connect(self._on_current_changed)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.files_dropped.connect(self._add_paths)
        v.addWidget(self._tree, stretch=1)

        self._hint = QLabel("Click a row to view file details")
        self._hint.setStyleSheet(theme.help_text)
        v.addWidget(self._hint)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("&Add Files\u2026")
        self._add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(self._add_btn)
        self._clear_btn = QPushButton("&Clear")
        self._clear_btn.clicked.connect(self._on_clear)
        btn_row.addWidget(self._clear_btn)
        btn_row.addStretch()
        v.addLayout(btn_row)

        return panel

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def file_items(self) -> list[FileItem]:
        return self._file_items

    @property
    def last_dir(self) -> str:
        return self._last_dir

    @last_dir.setter
    def last_dir(self, value: str) -> None:
        self._last_dir = value

    @property
    def current_index(self) -> int:
        item = self._tree.currentItem()
        return self._tree.indexOfTopLevelItem(item) if item is not None else -1

    def open_add_dialog(self) -> None:
        self._on_add()

    def update_item_status(self, index: int, status: FileStatus) -> None:
        if not (0 <= index < len(self._file_items)):
            return
        self._file_items[index].status = status
        self._refresh_status(index)

    def set_item_checked(self, index: int, checked: bool) -> None:
        if not (0 <= index < len(self._file_items)):
            return
        if self._file_items[index].checked == checked:
            return  # No-op guard: terminates any accidental sync loop in O(1).
        self._file_items[index].checked = checked
        item = self._tree.topLevelItem(index)
        if item is None:
            return
        self._tree.blockSignals(True)
        item.setCheckState(
            COL_CONVERT, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        )
        self._tree.blockSignals(False)

    def checked_indices(self) -> list[int]:
        return [i for i, f in enumerate(self._file_items) if f.checked]

    def has_files(self) -> bool:
        return len(self._file_items) > 0

    def set_global_userdata_path(self, path: str) -> None:
        """Inform the panel of the current global userdata path so file
        badges can label their userdata source correctly. Display-only.
        """
        self._global_userdata_path = Path(path) if path else None
        for i in range(len(self._file_items)):
            self._refresh_status(i)

    # ------------------------------------------------------------------
    # Internal — input handling
    # ------------------------------------------------------------------

    def _on_tree_file_activated(self, path: Path) -> None:
        self._add_paths([path])

    def _on_add(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select ADCP/ADV Files", self._last_dir, FILE_FILTER
        )
        if not paths:
            return
        self._last_dir = str(Path(paths[0]).parent)
        self._add_paths([Path(p) for p in paths])

    def _add_paths(self, paths: list[Path]) -> None:
        existing = {item.path for item in self._file_items}
        new_paths: list[Path] = []

        # Bulk insert: silence per-row signals and repaints, otherwise the
        # tree fires itemChanged and re-paints once per row, which is what
        # made the dialog hang on hundreds of files.
        self._tree.setUpdatesEnabled(False)
        self._tree.blockSignals(True)
        try:
            for path in paths:
                if path in existing:
                    continue
                self._file_items.append(FileItem(path=path))
                existing.add(path)
                new_paths.append(path)
                self._append_list_item(len(self._file_items) - 1)
        finally:
            self._tree.blockSignals(False)
            self._tree.setUpdatesEnabled(True)

        # Defer the (potentially expensive) tree-browser refresh so the
        # add dialog returns to the user immediately.
        QTimer.singleShot(0, self._sync_included_to_browser)
        if new_paths:
            log.info("Added %d file(s)", len(new_paths))
            self.files_added.emit(new_paths)
            self._emit_files_changed()
            if self._tree.currentItem() is None:
                self._tree.setCurrentItem(self._tree.topLevelItem(0))  # pyright: ignore[reportArgumentType] — items were just added

    def _on_clear(self) -> None:
        self._file_items.clear()
        self._tree.clear()
        self._sync_included_to_browser()
        self._refresh_header()
        log.info("Cleared all files")
        self.cleared.emit()
        self._emit_files_changed()

    def _emit_files_changed(self) -> None:
        self.files_changed.emit(list(self._file_items))

    def _on_current_changed(
        self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None
    ) -> None:
        if current is None:
            return
        row = self._tree.indexOfTopLevelItem(current)
        if 0 <= row < len(self._file_items):
            self.file_clicked.emit(row)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != COL_CONVERT:
            return
        row = self._tree.indexOfTopLevelItem(item)
        if not (0 <= row < len(self._file_items)):
            return
        checked = item.checkState(COL_CONVERT) == Qt.CheckState.Checked
        self._file_items[row].checked = checked
        self.check_state_changed.emit(row, checked)

    def _on_context_menu(self, pos: QPoint) -> None:
        item = self._tree.itemAt(pos)
        if item is None:
            return
        row = self._tree.indexOfTopLevelItem(item)
        file_item = self._file_items[row]
        menu = QMenu(self)
        remove_action = menu.addAction("Remove")
        retry_action = menu.addAction("Retry")
        retry_action.setEnabled(file_item.status == FileStatus.ERROR)
        edit_sidecar_action = menu.addAction("Edit userdata sidecar\u2026")
        skip_action = menu.addAction("Skip userdata for this file")
        skip_action.setCheckable(True)
        skip_action.setChecked(file_item.userdata_skip)
        action = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if action == remove_action:
            self._remove_file(row)
        elif action == retry_action:
            self._retry_file(row)
        elif action == edit_sidecar_action:
            self._on_edit_sidecar(row)
        elif action == skip_action:
            file_item.userdata_skip = skip_action.isChecked()
            self._refresh_status(row)
            log.info(
                "Userdata %s for %s",
                "skipped" if file_item.userdata_skip else "enabled",
                file_item.path.name,
            )

    def _on_edit_sidecar(self, row: int) -> None:
        if not (0 <= row < len(self._file_items)):
            return
        file_item = self._file_items[row]
        sidecar = sidecar_path_for(file_item.path)
        saved = UserdataEditor.open_for(self, path=sidecar, allow_save_as=False)
        if saved is None:
            return
        log.info("Wrote sidecar %s — re-read the file to apply", saved.name)
        self._refresh_status(row)

    def _remove_file(self, index: int) -> None:
        if not (0 <= index < len(self._file_items)):
            return
        name = self._file_items[index].path.name
        del self._file_items[index]
        self._tree.takeTopLevelItem(index)
        self._sync_included_to_browser()
        self._refresh_header()
        log.info("Removed file: %s", name)
        self._emit_files_changed()

    def _retry_file(self, index: int) -> None:
        self._file_items[index].status = FileStatus.PENDING
        self._file_items[index].error = None
        self._file_items[index].dataset = None
        self._refresh_status(index)
        self.files_added.emit([self._file_items[index].path])
        log.info("Retrying file: %s", self._file_items[index].path.name)

    # ------------------------------------------------------------------
    # Tree row helpers
    # ------------------------------------------------------------------

    def _append_list_item(self, index: int) -> None:
        """Add a new tree row for the FileItem at the given index."""
        file_item = self._file_items[index]
        row = QTreeWidgetItem()
        row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        row.setCheckState(
            COL_CONVERT,
            Qt.CheckState.Checked if file_item.checked else Qt.CheckState.Unchecked,
        )
        row.setText(COL_FILE, file_item.path.name)
        row.setToolTip(COL_FILE, str(file_item.path))
        row.setText(COL_STATUS, status_label(file_item.status))
        color_hex = STATUS_TEXT_COLORS.get(file_item.status)
        initial_color = (
            QColor(color_hex) if color_hex else theme.status.for_status(file_item.status.value)
        )
        row.setForeground(COL_STATUS, QBrush(initial_color))
        self._tree.addTopLevelItem(row)

        remove_btn = QToolButton()
        remove_btn.setText("\u2715")
        remove_btn.setAutoRaise(True)
        remove_btn.setToolTip("Remove this file from the list")
        remove_btn.setFixedSize(QSize(20, 20))
        remove_btn.setStyleSheet(
            "QToolButton { border: none; color: #888; }QToolButton:hover { color: #ef5350; }"
        )
        remove_btn.clicked.connect(lambda: self._remove_clicked(row))
        self._tree.setItemWidget(row, COL_REMOVE, remove_btn)

        self._refresh_header()

    def _remove_clicked(self, row: QTreeWidgetItem) -> None:
        index = self._tree.indexOfTopLevelItem(row)
        if index >= 0:
            self._remove_file(index)

    def _refresh_status(self, index: int) -> None:
        item = self._tree.topLevelItem(index)
        if item is None:
            return
        file_item = self._file_items[index]
        item.setText(COL_STATUS, status_label(file_item.status))
        color_hex = STATUS_TEXT_COLORS.get(file_item.status)
        color = QColor(color_hex) if color_hex else theme.status.for_status(file_item.status.value)
        item.setForeground(COL_STATUS, QBrush(color))

        name = file_item.path.name
        tooltip = str(file_item.path)
        sidecar = sidecar_path_for(file_item.path)
        if file_item.userdata_skip:
            name = f"{name}  [ud:skip]"
            tooltip += "\nUserdata: skipped for this file"
        elif file_item.userdata_source is not None:
            kind = "sidecar" if file_item.userdata_source == sidecar else "global"
            name = f"{name}  [ud:{kind}]"
            tooltip += f"\nUserdata ({kind}): {file_item.userdata_source}"
        elif sidecar.exists():
            name = f"{name}  [ud:sidecar?]"
            tooltip += f"\nSidecar present (re-read to apply): {sidecar}"
        elif self._global_userdata_path is not None and self._global_userdata_path.exists():
            tooltip += f"\nGlobal userdata available: {self._global_userdata_path}"
        item.setText(COL_FILE, name)
        item.setToolTip(COL_FILE, tooltip)

    def _refresh_header(self) -> None:
        count = len(self._file_items)
        self._header.setText(f"Files to Convert ({count})" if count else "Files to Convert")

    def _sync_included_to_browser(self) -> None:
        paths = {item.path for item in self._file_items}
        self._browser.set_included_paths(paths)
