"""Thin composer that stacks supported types + file list + userdata panels."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from mhkit_dolfyn_gui.styles import theme
from mhkit_dolfyn_gui.widgets.file_sidebar.file_list_panel import FileListPanel
from mhkit_dolfyn_gui.widgets.file_sidebar.supported_types_panel import SupportedFileTypesPanel
from mhkit_dolfyn_gui.widgets.file_sidebar.userdata_panel import UserDataPanel

if TYPE_CHECKING:
    from mhkit_dolfyn_gui.models.file_item import FileStatus


class FileSidebar(QWidget):
    """Composer: supported types (top), file list (middle), userdata (bottom).

    Re-exports the file-list and userdata signals so ``MainWindow`` can wire
    them as if to a single widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.layout.panel_margin)
        layout.setSpacing(theme.layout.spacing_xs)

        title = QLabel("Import")
        title.setStyleSheet(theme.section_title)
        layout.addWidget(title)

        self._supported = SupportedFileTypesPanel()
        layout.addWidget(self._supported)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #444;")
        layout.addWidget(sep)

        self._list = FileListPanel()
        layout.addWidget(self._list, stretch=1)

        self._userdata = UserDataPanel()
        layout.addWidget(self._userdata)

        # Forward userdata path changes to the file list so badges refresh.
        self._userdata.path_changed.connect(self._list.set_global_userdata_path)

        # Re-export sub-widget signals as instance attributes so MainWindow's
        # existing wiring (sidebar.files_added.connect(...)) works unchanged.
        self.files_added = self._list.files_added
        self.files_changed = self._list.files_changed
        self.file_clicked = self._list.file_clicked
        self.cleared = self._list.cleared
        self.check_state_changed = self._list.check_state_changed
        self.global_userdata_changed = self._userdata.path_changed

    # ------------------------------------------------------------------
    # Public API forwarded to FileListPanel
    # ------------------------------------------------------------------

    @property
    def file_items(self):
        return self._list.file_items

    @property
    def last_dir(self) -> str:
        return self._list.last_dir

    @last_dir.setter
    def last_dir(self, value: str) -> None:
        self._list.last_dir = value

    @property
    def current_index(self) -> int:
        return self._list.current_index

    def open_add_dialog(self) -> None:
        self._list.open_add_dialog()

    def update_item_status(self, index: int, status: FileStatus) -> None:
        self._list.update_item_status(index, status)

    def set_item_checked(self, index: int, checked: bool) -> None:
        self._list.set_item_checked(index, checked)

    def checked_indices(self) -> list[int]:
        return self._list.checked_indices()

    def has_files(self) -> bool:
        return self._list.has_files()

    def set_global_userdata_path(self, path: str) -> None:
        """Programmatic setter (used at startup to restore from QSettings)."""
        self._userdata.set_path(path)
        self._list.set_global_userdata_path(path)
