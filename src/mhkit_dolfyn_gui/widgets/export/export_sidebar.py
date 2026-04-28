"""Thin composer that stacks ExportConfigWidget on top of ExportProgressWidget."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from mhkit_dolfyn_gui.styles import theme
from mhkit_dolfyn_gui.widgets.export.export_config import ExportConfigWidget
from mhkit_dolfyn_gui.widgets.export.export_progress import ExportProgressWidget

if TYPE_CHECKING:
    from pathlib import Path

    from mhkit_dolfyn_gui.models.file_item import FileItem


class ExportSidebar(QWidget):
    """Right sidebar: configuration on top, progress slides in below."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.layout.panel_margin)
        layout.setSpacing(theme.layout.spacing_md)

        title = QLabel("Export")
        title.setStyleSheet(theme.section_title)
        layout.addWidget(title)

        self._config = ExportConfigWidget()
        layout.addWidget(self._config, stretch=1)

        self._progress = ExportProgressWidget()
        layout.addWidget(self._progress)

        # Re-export config signals so MainWindow can wire them as before.
        self.export_requested = self._config.export_requested
        self.code_requested = self._config.code_requested
        self.user_toggled = self._config.user_toggled
        self.output_dir_changed = self._config.output_dir_changed
        self.pattern_changed = self._config.pattern_changed
        self.me_fields_changed = self._config.me_fields_changed

    # ------------------------------------------------------------------
    # Configuration API forwarded to ExportConfigWidget
    # ------------------------------------------------------------------

    @property
    def output_dir(self) -> str:
        return self._config.output_dir

    @output_dir.setter
    def output_dir(self, value: str) -> None:
        self._config.output_dir = value

    @property
    def pattern_text(self) -> str:
        return self._config.pattern_text

    @pattern_text.setter
    def pattern_text(self, value: str) -> None:
        self._config.pattern_text = value

    def set_file_items(self, items: list[FileItem]) -> None:
        self._config.set_file_items(items)

    def on_check_changed(self, index: int, checked: bool) -> None:
        self._config.on_check_changed(index, checked)

    def get_output_paths(self) -> list[tuple[int, int, Path]]:
        return self._config.get_output_paths()

    def trigger_export(self) -> None:
        """Programmatic trigger (used by the menu Export action)."""
        self._config.trigger_export()

    # ------------------------------------------------------------------
    # ME Data Pipeline properties forwarded to ExportConfigWidget
    # ------------------------------------------------------------------

    @property
    def me_location_id(self) -> str:
        return self._config.me_location_id

    @me_location_id.setter
    def me_location_id(self, value: str) -> None:
        self._config.me_location_id = value

    @property
    def me_dataset_name(self) -> str:
        return self._config.me_dataset_name

    @me_dataset_name.setter
    def me_dataset_name(self, value: str) -> None:
        self._config.me_dataset_name = value

    @property
    def me_qualifier(self) -> str:
        return self._config.me_qualifier

    @me_qualifier.setter
    def me_qualifier(self, value: str) -> None:
        self._config.me_qualifier = value

    @property
    def me_data_level(self) -> str:
        return self._config.me_data_level

    @me_data_level.setter
    def me_data_level(self, value: str) -> None:
        self._config.me_data_level = value

    @property
    def me_include_temporal(self) -> bool:
        return self._config.me_include_temporal

    @me_include_temporal.setter
    def me_include_temporal(self, value: bool) -> None:
        self._config.me_include_temporal = value

    @property
    def me_timezone_offset_hours(self) -> int:
        return self._config.me_timezone_offset_hours

    @me_timezone_offset_hours.setter
    def me_timezone_offset_hours(self, value: int) -> None:
        self._config.me_timezone_offset_hours = value

    # ------------------------------------------------------------------
    # Progress lifecycle
    # ------------------------------------------------------------------

    def begin_export(self) -> None:
        """Reset the progress widget at the start of an export run."""
        self._progress.reset()

    def set_progress(self, value: int) -> None:
        self._progress.set_progress(value)

    def finish_export(self, ok: bool, message: str) -> None:
        self._progress.set_status(message, is_error=not ok)
