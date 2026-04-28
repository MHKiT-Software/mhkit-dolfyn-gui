"""Center panel with Combined and Per-File tabs for dataset review."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSplitter, QTabWidget, QVBoxLayout, QWidget

from mhkit_dolfyn_gui.styles import theme
from mhkit_dolfyn_gui.widgets.combined_overview import CombinedOverview
from mhkit_dolfyn_gui.widgets.dataset_tree import DatasetTree
from mhkit_dolfyn_gui.widgets.summary import SummaryCard
from mhkit_dolfyn_gui.widgets.variable_detail import VariableDetail

if TYPE_CHECKING:
    import xarray as xr

    from mhkit_dolfyn_gui.models.file_item import FileItem


class CenterPanel(QWidget):
    """Main content area showing dataset review in Combined and Per-File tabs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.layout.no_margin)

        title = QLabel("Review")
        title.setStyleSheet(theme.section_title)
        title.setContentsMargins(*theme.layout.inner_margin)
        layout.addWidget(title)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # --- Combined tab ---
        self._combined = CombinedOverview()
        self._tabs.addTab(self._combined, "Combined")

        # --- Per-File tab ---
        per_file_widget = QWidget()
        per_file_layout = QVBoxLayout(per_file_widget)
        per_file_layout.setContentsMargins(*theme.layout.no_margin)

        # Vertical splitter: summary + tree on top, variable detail on bottom
        self._per_file_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top section: summary card + tree
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(*theme.layout.inner_margin)

        self._summary = SummaryCard()
        top_layout.addWidget(self._summary)

        self._tree = DatasetTree()
        top_layout.addWidget(self._tree, stretch=1)

        self._per_file_splitter.addWidget(top_widget)

        # Bottom section: variable detail
        self._var_detail = VariableDetail()
        self._per_file_splitter.addWidget(self._var_detail)

        self._per_file_splitter.setStretchFactor(0, 3)
        self._per_file_splitter.setStretchFactor(1, 1)

        per_file_layout.addWidget(self._per_file_splitter)

        # Error banner (hidden by default)
        self._error_banner = QLabel()
        self._error_banner.setWordWrap(True)
        self._error_banner.setStyleSheet(theme.warning_banner)
        self._error_banner.hide()
        per_file_layout.insertWidget(0, self._error_banner)

        self._tabs.addTab(per_file_widget, "Per-File")

        # Wire tree click → variable detail
        self._tree.variable_clicked.connect(self._on_variable_clicked)

        # Placeholder when nothing selected
        self._no_selection_label = QLabel("Select a file from the sidebar to view its data.")
        self._no_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_selection_label.setStyleSheet(theme.placeholder)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_file(self, item: FileItem) -> None:
        """Display a single file's summary and structure in the Per-File tab."""
        self._tabs.setCurrentIndex(1)  # Switch to Per-File

        if item.dataset is None:
            self._summary.clear()
            self._tree.clear_dataset()
            self._var_detail.clear()
            if item.error:
                self._summary.set_flat_dict({"Error": item.error})
            elif item.summary_snapshot is not None:
                # Cached/evicted: show what we know from the snapshot.
                # The full Dataset will be re-read in the background; this
                # placeholder keeps the panel from looking empty.
                self._summary.setTitle(f"Summary: {item.path.name} (cached)")
                self._summary.set_flat_dict(item.summary)
            return

        self._summary.set_data(item.dataset, item)
        self._summary.setTitle(f"Summary: {item.path.name}")
        self._tree.set_dataset(item.dataset)
        self._var_detail.clear()

    def set_gap_threshold_seconds(self, value: float) -> None:
        """Forward the gap threshold to the Combined overview."""
        self._combined.set_gap_threshold_seconds(value)

    def update_combined(self, items: list[FileItem]) -> None:
        """Refresh the Combined tab with all file items."""
        self._combined.update_overview(items)

        # Update error banner
        failed = [it for it in items if it.error]
        if failed:
            names = ", ".join(it.path.name for it in failed)
            self._error_banner.setText(f"⚠ {len(failed)} file(s) could not be read: {names}")
            self._error_banner.show()
        else:
            self._error_banner.hide()

    def clear(self) -> None:
        """Reset all panels."""
        self._summary.clear()
        self._tree.clear_dataset()
        self._var_detail.clear()
        self._combined.update_overview([])
        self._error_banner.hide()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_variable_clicked(self, name: str, var: xr.DataArray) -> None:
        self._var_detail.show_variable(name, var)
