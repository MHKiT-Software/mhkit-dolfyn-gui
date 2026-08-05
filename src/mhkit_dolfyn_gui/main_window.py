"""Main application window — single-page dashboard for ADCP/ADV to NetCDF conversion."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from mhkit_dolfyn_gui.constants import (
    APP_DISPLAY_NAME,
    APP_NAME,
    APP_VERSION,
    MAIN_WINDOW_TITLE,
    MIN_FILE_SIDEBAR_WIDTH_PX,
    SUPPORTED_INSTRUMENTS,
)
from mhkit_dolfyn_gui.models.file_item import FileStatus
from mhkit_dolfyn_gui.orchestration import ExportCoordinator, ReadScheduler
from mhkit_dolfyn_gui.services.dataset_cache import DatasetCache
from mhkit_dolfyn_gui.settings import Settings
from mhkit_dolfyn_gui.styles import theme
from mhkit_dolfyn_gui.widgets.center_panel import CenterPanel
from mhkit_dolfyn_gui.widgets.event_log import EventLog
from mhkit_dolfyn_gui.widgets.export import CodePreviewDialog, ExportSidebar
from mhkit_dolfyn_gui.widgets.file_sidebar import FileSidebar
from mhkit_dolfyn_gui.widgets.memory_indicator import ActivityState
from mhkit_dolfyn_gui.widgets.status_bar import StatusBarWidget
from mhkit_dolfyn_gui.workers.preload_worker import PreloadWorker

if TYPE_CHECKING:
    from pathlib import Path

    from PySide6.QtGui import QCloseEvent

    from mhkit_dolfyn_gui.models.file_item import FileItem

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Single-page dashboard: file sidebar | center panel | export sidebar.

    Signal flow
    -----------
    The single source of truth for the file list is ``FileSidebar``.
    Every list mutation fans out through ``_on_files_changed``, which is
    the ONLY place that pushes the new list to ``CenterPanel`` and
    ``ExportSidebar``.  No panel keeps its own copy.

    Check-state sync between the sidebar and the export view is
    unidirectional: ``FileListPanel`` is the canonical owner.  The export
    view emits ``user_toggled`` (user intent) which feeds back through
    ``FileListPanel.set_item_checked``; the panel then re-emits
    ``check_state_changed`` which the export view mirrors via
    ``on_check_changed``.  A no-op guard in ``set_item_checked`` terminates
    any accidental loop in O(1).

    Orchestration
    -------------
    Background-worker lifecycles are delegated to dedicated QObject
    coordinators:

    - ``ReadScheduler`` — bounded concurrent file-read queue with
      generation-based staleness.
    - ``ExportCoordinator`` — save-worker lifecycle, progress tracking,
      and code-preview generation.

    Both communicate outward through Qt signals; MainWindow wires those
    signals to the appropriate widget methods.
    """

    def __init__(self) -> None:
        super().__init__()
        self._settings = Settings()
        self._dataset_cache = DatasetCache(
            max_bytes=self._settings.dataset_cache_max_bytes,
            max_items=self._settings.dataset_cache_max_items,
        )
        self._preload_worker: PreloadWorker | None = None

        self._settings.settings_changed.connect(self._on_settings_changed)

    # ------------------------------------------------------------------
    # Staged initialization (called by app.py through splash)
    # ------------------------------------------------------------------

    def init_stage_ui(self, *, with_preload: bool = True) -> None:
        """Build the dashboard layout.

        Parameters
        ----------
        with_preload:
            When *False*, skip starting the background ``PreloadWorker`` that
            imports ``mhkit.dolfyn``.  Pass ``False`` in headless / smoke-test
            contexts where the import is not needed and the thread lifetime
            would outlast the process, causing an abort (macOS) or hang
            (Windows).
        """
        self.setWindowTitle(MAIN_WINDOW_TITLE)
        self.setMinimumSize(900, 600)
        self.resize(1200, 750)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(*theme.layout.no_margin)

        # Vertical splitter: dashboard on top, log on bottom
        self._vsplitter = QSplitter(Qt.Orientation.Vertical)
        root.addWidget(self._vsplitter)

        # Horizontal splitter: file sidebar | center | export sidebar
        self._hsplitter = QSplitter(Qt.Orientation.Horizontal)

        self._file_sidebar = FileSidebar()
        self._file_sidebar.setMinimumWidth(MIN_FILE_SIDEBAR_WIDTH_PX)
        self._hsplitter.addWidget(self._file_sidebar)

        self._center_panel = CenterPanel()
        self._center_panel.set_gap_threshold_seconds(self._settings.time_gap_threshold_seconds)
        self._hsplitter.addWidget(self._center_panel)

        self._export_sidebar = ExportSidebar()
        self._hsplitter.addWidget(self._export_sidebar)

        # Stretch factors: file sidebar 1, center 3, export sidebar 1
        self._hsplitter.setStretchFactor(0, 1)
        self._hsplitter.setStretchFactor(1, 3)
        self._hsplitter.setStretchFactor(2, 1)

        self._vsplitter.addWidget(self._hsplitter)

        # Event log (collapsible)
        self._event_log = EventLog()
        self._event_log.install()
        self._vsplitter.addWidget(self._event_log)

        # Log gets minimal space by default (collapsed)
        self._vsplitter.setStretchFactor(0, 9)
        self._vsplitter.setStretchFactor(1, 1)
        self._vsplitter.setCollapsible(1, True)

        # Orchestrators
        self._read_scheduler = ReadScheduler(
            settings=self._settings,
            dataset_cache=self._dataset_cache,
            file_items_provider=lambda: self._file_sidebar.file_items,
            parent=self,
        )
        self._export_coordinator = ExportCoordinator(
            settings=self._settings,
            file_items_provider=lambda: self._file_sidebar.file_items,
            output_paths_provider=self._export_sidebar.get_output_paths,
            include_velds_provider=lambda: self._export_sidebar.include_velds,
            parent=self,
        )

        # Status bar
        self._status_bar_widget = StatusBarWidget(
            self._settings, self._current_activity, self._open_preferences, self
        )
        self._status_bar_widget.install(self.statusBar())

        # Connect signals
        self._wire_signals()

        # Build menus
        self._build_menu_bar()

        # Preload mhkit.dolfyn on a background thread
        if with_preload:
            self._preload_worker = PreloadWorker()
            self._preload_worker.start()
        else:
            log.debug("Preload worker skipped (headless/smoke-test mode)")

        log.info("Application ready")

    def init_stage_restore(self) -> None:
        """Restore saved settings (geometry, output dir, pattern, splitters)."""
        geo = self._settings.window_geometry
        if not geo.isEmpty():
            self.restoreGeometry(geo)
            log.debug("Restored window geometry")

        if self._settings.output_dir:
            self._export_sidebar.output_dir = self._settings.output_dir

        # Restore ME Data Pipeline fields *before* setting pattern_text so
        # that switching to ME mode finds the fields already populated.
        if self._settings.me_location_id:
            self._export_sidebar.me_location_id = self._settings.me_location_id
        if self._settings.me_dataset_name:
            self._export_sidebar.me_dataset_name = self._settings.me_dataset_name
        if self._settings.me_qualifier:
            self._export_sidebar.me_qualifier = self._settings.me_qualifier
        if self._settings.me_data_level:
            self._export_sidebar.me_data_level = self._settings.me_data_level
        self._export_sidebar.me_include_temporal = self._settings.me_include_temporal
        self._export_sidebar.me_timezone_offset_hours = self._settings.me_timezone_offset_hours
        self._export_sidebar.include_velds = self._settings.include_velds

        if self._settings.filename_pattern:
            self._export_sidebar.pattern_text = self._settings.filename_pattern

        if self._settings.last_input_dir:
            self._file_sidebar.last_dir = self._settings.last_input_dir

        if self._settings.global_userdata_path:
            self._file_sidebar.set_global_userdata_path(self._settings.global_userdata_path)

        # Restore splitter states
        h_state = self._settings.get_bytes("hsplitter_state")
        if h_state and not h_state.isEmpty():
            self._hsplitter.restoreState(h_state)
        v_state = self._settings.get_bytes("vsplitter_state")
        if v_state and not v_state.isEmpty():
            self._vsplitter.restoreState(v_state)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        # File sidebar → orchestrators / panels
        self._file_sidebar.files_added.connect(self._on_files_added)
        self._file_sidebar.file_clicked.connect(self._on_file_clicked)
        self._file_sidebar.cleared.connect(self._on_cleared)
        self._file_sidebar.global_userdata_changed.connect(self._on_global_userdata_changed)
        self._file_sidebar.files_changed.connect(self._on_files_changed)

        # Unidirectional checkbox sync
        self._file_sidebar.check_state_changed.connect(self._export_sidebar.on_check_changed)
        self._export_sidebar.user_toggled.connect(self._file_sidebar.set_item_checked)

        # Export sidebar → ExportCoordinator
        self._export_sidebar.export_requested.connect(self._export_coordinator.start_export)
        self._export_sidebar.code_requested.connect(self._export_coordinator.generate_code_preview)
        self._export_sidebar.output_dir_changed.connect(self._on_output_dir_changed)
        self._export_sidebar.pattern_changed.connect(self._on_pattern_changed)
        self._export_sidebar.me_fields_changed.connect(self._on_me_fields_changed)
        self._export_sidebar.include_velds_changed.connect(self._on_include_velds_changed)

        # ReadScheduler → MainWindow (UI dispatch)
        self._read_scheduler.item_status_changed.connect(self._on_read_status_changed)
        self._read_scheduler.file_read_finished.connect(self._on_read_file_finished)
        self._read_scheduler.reads_changed.connect(self._on_reads_changed)

        # ExportCoordinator → MainWindow (UI dispatch)
        self._export_coordinator.item_status_changed.connect(self._on_export_status_changed)
        self._export_coordinator.export_started.connect(self._export_sidebar.begin_export)
        self._export_coordinator.export_progress.connect(self._export_sidebar.set_progress)
        self._export_coordinator.export_finished.connect(self._export_sidebar.finish_export)
        self._export_coordinator.export_complete.connect(self._on_export_complete)
        self._export_coordinator.code_preview_ready.connect(self._show_code_preview)

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        add_action = QAction("&Add Files\u2026", self)
        add_action.setShortcut(QKeySequence.StandardKey.Open)
        add_action.triggered.connect(self._file_sidebar.open_add_dialog)
        file_menu.addAction(add_action)

        export_action = QAction("&Export", self)
        export_action.setShortcut(QKeySequence.StandardKey.Save)
        export_action.triggered.connect(self._export_sidebar.trigger_export)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        prefs_action = QAction("&Preferences\u2026", self)
        prefs_action.setShortcut(QKeySequence.StandardKey.Preferences)
        prefs_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        prefs_action.triggered.connect(self._open_preferences)
        file_menu.addAction(prefs_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")

        instruments_action = QAction("Supported &Instruments", self)
        instruments_action.triggered.connect(self._show_instruments_dialog)
        help_menu.addAction(instruments_action)

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)

    # ------------------------------------------------------------------
    # File-list events
    # ------------------------------------------------------------------

    def _on_global_userdata_changed(self, path: str) -> None:
        """Persist the new global userdata path; applies to subsequent reads."""
        self._settings.global_userdata_path = path

    def _on_output_dir_changed(self, value: str) -> None:
        """Persist the export sidebar's output directory as the default."""
        self._settings.output_dir = value

    def _on_pattern_changed(self, value: str) -> None:
        """Persist the export sidebar's filename pattern as the default."""
        self._settings.filename_pattern = value

    def _on_include_velds_changed(self, value: bool) -> None:
        """Persist the export sidebar's derived-velocity checkbox as the default."""
        self._settings.include_velds = value

    def _on_me_fields_changed(self) -> None:
        """Persist ME Data Pipeline naming fields from the export sidebar."""
        self._settings.me_location_id = self._export_sidebar.me_location_id
        self._settings.me_dataset_name = self._export_sidebar.me_dataset_name
        self._settings.me_qualifier = self._export_sidebar.me_qualifier
        self._settings.me_data_level = self._export_sidebar.me_data_level
        self._settings.me_include_temporal = self._export_sidebar.me_include_temporal
        self._settings.me_timezone_offset_hours = self._export_sidebar.me_timezone_offset_hours

    def _on_cleared(self) -> None:
        """Cancel any in-flight reads when the user clears the file list."""
        self._read_scheduler.cancel_all()

    def _on_files_changed(self, items: list[FileItem]) -> None:
        """Single fan-out point for file-list mutations (add / remove / clear).

        All panels that display "the current set of files" must refresh from
        this one slot -- no panel keeps its own copy.
        """
        self._center_panel.update_combined(items)
        self._export_sidebar.set_file_items(items)

        if not items:
            self._center_panel.clear()
        else:
            current = self._file_sidebar.current_index
            if 0 <= current < len(items):
                self._center_panel.show_file(items[current])
            else:
                self._center_panel.clear()

        self._status_bar_widget.update_file_status(items)

    def _on_files_added(self, paths: list[Path]) -> None:
        """Enqueue newly added files for the bounded read scheduler."""
        items = self._file_sidebar.file_items
        path_set = set(paths)
        pending = [it for it in items if it.path in path_set and it.status == FileStatus.PENDING]
        if pending:
            self._read_scheduler.enqueue(pending)
        self._status_bar_widget.update_file_status(items)

    def _on_file_clicked(self, index: int) -> None:
        items = self._file_sidebar.file_items
        if not (0 <= index < len(items)):
            return
        item = items[index]

        # Silently re-read pending or evicted (CACHED) files.
        if item.dataset is None and item.status in (
            FileStatus.PENDING,
            FileStatus.CACHED,
        ):
            self._read_scheduler.enqueue_single(item)
            self._center_panel.show_file(item)
            return
        self._dataset_cache.touch(item)
        self._center_panel.show_file(item)

    # ------------------------------------------------------------------
    # ReadScheduler signal dispatch
    # ------------------------------------------------------------------

    def _on_read_status_changed(self, file_item: FileItem, status: FileStatus) -> None:
        idx = self._read_scheduler.index_of(file_item)
        if idx >= 0:
            self._file_sidebar.update_item_status(idx, status)

    def _on_read_file_finished(self, file_item: FileItem) -> None:
        idx = self._read_scheduler.index_of(file_item)
        if idx >= 0 and self._file_sidebar.current_index == idx:
            self._center_panel.show_file(file_item)

    def _on_reads_changed(self) -> None:
        items = self._file_sidebar.file_items
        self._center_panel.update_combined(items)
        self._export_sidebar.set_file_items(items)
        self._status_bar_widget.update_file_status(items)

    # ------------------------------------------------------------------
    # ExportCoordinator signal dispatch
    # ------------------------------------------------------------------

    def _on_export_status_changed(self, file_item: FileItem, status: FileStatus) -> None:
        idx = self._read_scheduler.index_of(file_item)
        if idx >= 0:
            self._file_sidebar.update_item_status(idx, status)

    def _on_export_complete(self) -> None:
        self._settings.output_dir = self._export_sidebar.output_dir
        self._settings.filename_pattern = self._export_sidebar.pattern_text
        self._settings.last_input_dir = self._file_sidebar.last_dir
        self._status_bar_widget.update_file_status(self._file_sidebar.file_items)

    def _show_code_preview(self, script: str) -> None:
        CodePreviewDialog(script, self).exec()

    # ------------------------------------------------------------------
    # Activity snapshot (spans both orchestrators)
    # ------------------------------------------------------------------

    def _current_activity(self) -> ActivityState:
        """Snapshot of read+save progress for the status-bar memory indicator."""
        return ActivityState(
            reads_active=self._read_scheduler.reads_active,
            reads_total=self._read_scheduler.reads_batch_total,
            saves_done=self._export_coordinator.saves_done,
            saves_total=self._export_coordinator.saves_total,
        )

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------

    def _on_settings_changed(self) -> None:
        """Re-apply preference values to live components."""
        evicted = self._dataset_cache.set_limits(
            self._settings.dataset_cache_max_bytes,
            self._settings.dataset_cache_max_items,
        )
        for ev in evicted:
            ev_idx = self._read_scheduler.index_of(ev)
            if ev_idx >= 0:
                self._file_sidebar.update_item_status(ev_idx, FileStatus.CACHED)

        self._status_bar_widget.set_memory_poll_interval(self._settings.memory_poll_interval_ms)

        self._center_panel.set_gap_threshold_seconds(self._settings.time_gap_threshold_seconds)
        self._center_panel.update_combined(self._file_sidebar.file_items)

        self._export_sidebar.output_dir = self._settings.output_dir
        self._export_sidebar.pattern_text = self._settings.filename_pattern
        self._file_sidebar.set_global_userdata_path(self._settings.global_userdata_path)

        # Pump the read queue in case max_concurrent_reads went up.
        self._read_scheduler.pump_queue()

    def _open_preferences(self) -> None:
        """Show the Preferences dialog. Modal; live updates on Apply/OK."""
        from mhkit_dolfyn_gui.widgets.preferences_dialog import PreferencesDialog

        dlg = PreferencesDialog(self._settings, self)
        dlg.exec()

    # ------------------------------------------------------------------
    # Help dialogs
    # ------------------------------------------------------------------

    def _show_instruments_dialog(self) -> None:
        lines = ["<b>Supported Instruments</b><br><br>"]
        for name, (exts, inst_type) in SUPPORTED_INSTRUMENTS.items():
            ext_str = ", ".join(exts)
            lines.append(f"<b>{name}</b> ({ext_str}) - {inst_type}<br>")
        QMessageBox.information(
            self, "Supported Instruments", "".join(lines), QMessageBox.StandardButton.Ok
        )

    def _show_about_dialog(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_DISPLAY_NAME}",
            f"<b>{APP_NAME}</b> v{APP_VERSION}<br><br>"
            "Convert ADCP/ADV binary files to NetCDF<br>"
            "using the MHKiT-Python dolfyn module.<br><br>"
            "github.com/MHKiT-Software/MHKiT-Python",
        )

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        log.info("Application closing")
        self._settings.window_geometry = self.saveGeometry()
        self._settings.set_bytes("hsplitter_state", self._hsplitter.saveState())
        self._settings.set_bytes("vsplitter_state", self._vsplitter.saveState())

        if self._preload_worker is not None and self._preload_worker.isRunning():
            preload_timeout_ms = self._settings.worker_shutdown_timeout_ms
            if not self._preload_worker.wait(preload_timeout_ms):
                log.warning(
                    "Preload worker did not finish within %d ms; terminating",
                    preload_timeout_ms,
                )
                # terminate() is safe here: we're shutting down and the worker
                # only does Python imports.  Skip on Windows where
                # TerminateThread() is too dangerous.
                if sys.platform != "win32":
                    self._preload_worker.terminate()
                    self._preload_worker.wait(1000)
        self._read_scheduler.cleanup_workers()
        self._event_log.uninstall()
        super().closeEvent(event)
