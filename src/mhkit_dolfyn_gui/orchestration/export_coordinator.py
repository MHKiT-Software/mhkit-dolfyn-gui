"""Save-worker lifecycle and code-preview generation.

This QObject owns the export pipeline that was previously inlined in
``MainWindow``.  It communicates UI updates exclusively through Qt
signals so it never imports from ``widgets/``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from mhkit_dolfyn_gui.models.file_item import FileStatus
from mhkit_dolfyn_gui.services.code_generator import (
    ExportJobSpec,
    UserdataMode,
    generate_export_script,
)
from mhkit_dolfyn_gui.services.userdata_service import resolve_userdata, sidecar_path_for
from mhkit_dolfyn_gui.workers.save_worker import SaveFailure, SaveJob, SaveProgress, SaveWorker

if TYPE_CHECKING:
    from collections.abc import Callable

    from mhkit_dolfyn_gui.models.file_item import FileItem
    from mhkit_dolfyn_gui.settings import Settings

log = logging.getLogger(__name__)


class ExportCoordinator(QObject):
    """Manages SaveWorker lifecycle, progress tracking, and code preview."""

    # --- Signals ---
    item_status_changed = Signal(object, object)  # (FileItem, FileStatus)
    export_started = Signal()
    export_progress = Signal(int)  # percent 0-100
    export_finished = Signal(bool, str)  # (ok, message)
    export_complete = Signal()  # all done — persist settings, refresh status
    code_preview_ready = Signal(str)  # script text

    def __init__(
        self,
        settings: Settings,
        file_items_provider: Callable[[], list[FileItem]],
        output_paths_provider: Callable[[], list[tuple[int, int, Path]]],
        include_velds_provider: Callable[[], bool],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._file_items_provider = file_items_provider
        self._output_paths_provider = output_paths_provider
        self._include_velds_provider = include_velds_provider

        self._save_worker: SaveWorker | None = None
        self._current_output_paths: list[tuple[int, int, Path]] = []
        self._saves_done = 0
        self._saves_total = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_export(self) -> None:
        """Build jobs from current items + output paths, start SaveWorker."""
        output_paths = self._output_paths_provider()
        if not output_paths:
            log.warning("No files to save")
            return

        items = self._file_items_provider()
        global_ud = self._settings.global_userdata_path
        global_ud_path = Path(global_ud) if global_ud else None
        include_velds = self._include_velds_provider()

        jobs: list[SaveJob] = []
        for item_idx, profile_idx, out_path in output_paths:
            item = items[item_idx]
            item.status = FileStatus.SAVING
            self.item_status_changed.emit(item, FileStatus.SAVING)
            try:
                userdata, _src = resolve_userdata(item, global_ud_path)
            except ValueError as exc:
                log.warning("Userdata not applied for %s: %s", item.path.name, exc)
                userdata = None
            jobs.append(
                SaveJob(
                    file_item=item,
                    source_path=item.path,
                    profile_index=profile_idx,
                    output_path=out_path,
                    userdata=userdata,
                    include_velds=include_velds,
                )
            )

        log.info("Saving %d file(s)", len(jobs))
        self.export_started.emit()

        self._current_output_paths = output_paths
        self._saves_total = len(jobs)
        self._saves_done = 0

        self._save_worker = SaveWorker(jobs)
        self._save_worker.file_saved.connect(self._on_file_saved)
        self._save_worker.file_failed.connect(self._on_file_save_failed)
        self._save_worker.all_done.connect(self._on_all_saves_done)
        self._save_worker.start()

    def generate_code_preview(self) -> None:
        """Build ExportJobSpec list and emit the script text via signal.

        Mirrors the first half of :meth:`start_export`: builds the same
        (item, profile_index, output_path) list, resolves userdata by
        **path** only (no JSON parsing -- we don't want a malformed
        sidecar to block the preview), and hands the list to the pure
        generator.
        """
        output_paths = self._output_paths_provider()
        if not output_paths:
            return

        items = self._file_items_provider()
        global_ud = self._settings.global_userdata_path
        global_ud_path = Path(global_ud).resolve() if global_ud else None
        include_velds = self._include_velds_provider()

        specs: list[ExportJobSpec] = []
        for item_idx, profile_idx, out_path in output_paths:
            item = items[item_idx]
            is_multi = len(item.profile_time_sizes) > 1

            if getattr(item, "userdata_skip", False):
                mode, ud_path = UserdataMode.SKIP, None
            else:
                sidecar = sidecar_path_for(item.path)
                if sidecar.exists():
                    mode, ud_path = UserdataMode.AUTO, None
                elif global_ud_path is not None and global_ud_path.exists():
                    mode, ud_path = UserdataMode.EXPLICIT, global_ud_path
                else:
                    mode, ud_path = UserdataMode.NONE, None

            specs.append(
                ExportJobSpec(
                    source=item.path.resolve(),
                    output=out_path.resolve(),
                    profile_index=profile_idx,
                    is_multi_profile=is_multi,
                    userdata_mode=mode,
                    userdata_path=ud_path,
                    include_velds=include_velds,
                )
            )

        script = generate_export_script(specs)
        self.code_preview_ready.emit(script)

    # --- Activity snapshot ---

    @property
    def saves_done(self) -> int:
        return self._saves_done

    @property
    def saves_total(self) -> int:
        return self._saves_total

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_file_saved(self, progress: SaveProgress) -> None:
        total = len(self._current_output_paths)
        index = progress.index
        self._saves_done = index + 1
        self.export_progress.emit(int((index + 1) / total * 100))

        if index < total:
            item_idx, _profile_idx, out_path = self._current_output_paths[index]
            items = self._file_items_provider()
            if 0 <= item_idx < len(items):
                items[item_idx].status = FileStatus.SAVED
                self.item_status_changed.emit(items[item_idx], FileStatus.SAVED)
            log.info("Saved: %s", out_path.name)

    def _on_file_save_failed(self, failure: SaveFailure) -> None:
        log.error("Save failed for file %d: %s", failure.index + 1, failure.error)
        self.export_finished.emit(False, f"Error saving file {failure.index + 1}: {failure.error}")

    def _on_all_saves_done(self) -> None:
        self.export_progress.emit(100)
        self.export_finished.emit(True, "All files saved successfully!")
        self._saves_total = 0
        self._saves_done = 0
        log.info("Export complete")
        self.export_complete.emit()
