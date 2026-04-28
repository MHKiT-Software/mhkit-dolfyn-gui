"""Bounded concurrent file-read queue with generation-based staleness.

This QObject owns the read-worker lifecycle. It communicates UI updates
exclusively through Qt signals so it never imports from ``widgets/``.
"""

from __future__ import annotations

import collections
import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from mhkit_dolfyn_gui.models.file_item import FileStatus
from mhkit_dolfyn_gui.workers.read_worker import FileReadWorker, ReadFailure, ReadResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from mhkit_dolfyn_gui.models.file_item import FileItem
    from mhkit_dolfyn_gui.services.dataset_cache import DatasetCache
    from mhkit_dolfyn_gui.settings import Settings

log = logging.getLogger(__name__)


class ReadScheduler(QObject):
    """Bounded concurrent file-read queue with generation-based staleness.

    Threading model
    ---------------
    - File reads run on ``FileReadWorker`` QThreads, one per file.
    - Each worker is tagged with the current ``_read_generation`` at start.
    - On Clear, ``_read_generation`` is bumped; any in-flight worker that
      eventually emits a stale result is dropped by the generation check
      in ``_on_file_read_finished`` / ``_on_file_read_failed``.
    - Workers are also routed by *identity* (``index_of``) because the
      int index in their signal payload may have shifted if the file list
      mutated mid-read.
    - Worker shutdown disconnects signals before ``wait()`` so a late emit
      cannot reach a half-destroyed window; ``dolfyn.read()`` is uninter-
      ruptible C code, so a timeout abandons the thread rather than risks
      a crash.
    """

    # --- Signals (outbound to MainWindow for UI dispatch) ---
    item_status_changed = Signal(object, object)  # (FileItem, FileStatus)
    file_read_finished = Signal(object)  # FileItem — successfully read
    reads_changed = Signal()  # batch state changed (pump/complete)

    def __init__(
        self,
        settings: Settings,
        dataset_cache: DatasetCache,
        file_items_provider: Callable[[], list[FileItem]],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._dataset_cache = dataset_cache
        self._file_items_provider = file_items_provider

        self._read_workers: list[FileReadWorker] = []
        self._read_queue: collections.deque[FileItem] = collections.deque()
        self._active_reads: dict[int, FileReadWorker] = {}
        self._reads_batch_total = 0  # active + queued + completed for this batch
        self._read_generation = 0  # discard stale results

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(self, items: list[FileItem]) -> None:
        """Enqueue a batch of PENDING items for reading."""
        for item in items:
            if item.status == FileStatus.PENDING:
                self._read_queue.append(item)
        count = len(items)
        if count:
            self._reads_batch_total += count
            self._pump_read_queue()

    def enqueue_single(self, item: FileItem) -> None:
        """Enqueue a single item for (re-)read (e.g. click on evicted item)."""
        self._read_queue.append(item)
        self._reads_batch_total += 1
        self._pump_read_queue()

    def pump_queue(self) -> None:
        """Externally trigger the pump (e.g. after ``max_concurrent_reads`` changes)."""
        self._pump_read_queue()

    def cancel_all(self) -> None:
        """Bump generation, clear queue + active, cleanup workers.

        Called when the user clears the file list.
        """
        self._read_generation += 1
        self._read_queue.clear()
        self._active_reads.clear()
        self._reads_batch_total = 0
        self.cleanup_workers()

    def cleanup_workers(self) -> None:
        """Disconnect and join all workers.  Called on cancel or window close."""
        timeout_ms = self._settings.worker_shutdown_timeout_ms
        for worker in self._read_workers:
            with contextlib.suppress(TypeError, RuntimeError):
                worker.finished.disconnect(self._on_file_read_finished)
            with contextlib.suppress(TypeError, RuntimeError):
                worker.failed.disconnect(self._on_file_read_failed)

            if worker.isRunning():
                worker.requestInterruption()
                if not worker.wait(timeout_ms):
                    log.warning(
                        "Read worker for %s did not finish within %d ms; abandoning",
                        worker.file_item.path.name,
                        timeout_ms,
                    )
                    continue
        self._read_workers.clear()

    def index_of(self, file_item: FileItem) -> int:
        """Locate a FileItem in the current list by identity.

        Returns -1 if it has been removed.
        """
        for i, it in enumerate(self._file_items_provider()):
            if it is file_item:
                return i
        return -1

    # --- Activity snapshot (for MemoryIndicator) ---

    @property
    def reads_active(self) -> int:
        return len(self._active_reads)

    @property
    def reads_batch_total(self) -> int:
        return self._reads_batch_total

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _pump_read_queue(self) -> None:
        """Start workers up to ``settings.max_concurrent_reads`` from the queue."""
        generation = self._read_generation
        global_ud = self._settings.global_userdata_path
        global_ud_path = Path(global_ud) if global_ud else None

        while self._read_queue and len(self._active_reads) < self._settings.max_concurrent_reads:
            item = self._read_queue.popleft()
            index = self.index_of(item)
            if index < 0:
                self._reads_batch_total = max(0, self._reads_batch_total - 1)
                continue
            item.status = FileStatus.READING
            self.item_status_changed.emit(item, FileStatus.READING)

            worker = FileReadWorker(
                path=item.path,
                file_item=item,
                global_userdata_path=global_ud_path,
            )
            worker.setProperty("generation", generation)
            worker.finished.connect(self._on_file_read_finished)
            worker.failed.connect(self._on_file_read_failed)
            self._active_reads[id(item)] = worker
            self._read_workers.append(worker)
            worker.start()
            log.debug("Reading %s", item.path.name)

        self.reads_changed.emit()

    def _is_stale_read(self) -> bool:
        worker = self.sender()
        return worker is not None and worker.property("generation") != self._read_generation

    def _on_file_read_finished(self, result: ReadResult) -> None:
        if self._is_stale_read():
            self._active_reads.pop(id(result.file_item), None)
            self._pump_read_queue()
            return

        self._active_reads.pop(id(result.file_item), None)
        index = self.index_of(result.file_item)
        if index < 0:
            self._after_read_completed()
            return

        item = result.file_item
        item.dataset = result.primary
        item.extra_datasets = result.extras
        item.userdata_source = result.userdata_source
        item.status = FileStatus.READY
        self.item_status_changed.emit(item, FileStatus.READY)
        log.info("Read complete: %s", item.path.name)

        evicted = self._dataset_cache.put(item)
        for ev in evicted:
            self.item_status_changed.emit(ev, FileStatus.CACHED)

        self.file_read_finished.emit(item)
        self._after_read_completed()

    def _on_file_read_failed(self, failure: ReadFailure) -> None:
        if self._is_stale_read():
            self._active_reads.pop(id(failure.file_item), None)
            self._pump_read_queue()
            return

        self._active_reads.pop(id(failure.file_item), None)
        index = self.index_of(failure.file_item)
        if index < 0:
            self._after_read_completed()
            return

        item = failure.file_item
        item.error = failure.error
        item.status = FileStatus.ERROR
        self.item_status_changed.emit(item, FileStatus.ERROR)
        log.error("Read failed: %s — %s", item.path.name, failure.error)

        self._after_read_completed()

    def _after_read_completed(self) -> None:
        """Common tail for both success and failure: pump queue, refresh."""
        self._pump_read_queue()

        if not self._read_queue and not self._active_reads:
            items = self._file_items_provider()
            ready = sum(1 for it in items if it.status == FileStatus.READY)
            failed = sum(1 for it in items if it.status == FileStatus.ERROR)
            log.info("All reads complete: %d succeeded, %d failed", ready, failed)
            self._reads_batch_total = 0
            self.cleanup_workers()
