"""Background thread for streaming ADCP/ADV files to NetCDF.

Worker contract
---------------
- Constructor takes a list of :class:`SaveJob`. Each job names a *source*
  file to read and an *output* path to write — the worker reads, saves,
  then drops the dataset before moving to the next job. This keeps peak
  memory bounded to one dataset regardless of corpus size, so the GUI can
  export collections that are larger than RAM.
- ``file_saved`` carries a :class:`SaveProgress` after each successful
  read+save round-trip.
- ``file_failed`` carries a :class:`SaveFailure` for each failure.
- ``all_done`` fires once when the run is complete.

The ``index`` on the progress/failure payloads is the position in the
original job list (stable for the duration of one run).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QThread, Signal

if TYPE_CHECKING:
    from pathlib import Path

    from mhkit_dolfyn_gui.models.file_item import FileItem

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SaveJob:
    """One source file → one NetCDF output.

    The worker re-reads the source on its own thread (independent of the
    GUI dataset cache) and saves it. ``profile_index`` selects which
    profile to keep when ``dolfyn.read`` returns a tuple for multi-profile
    instruments. ``userdata`` is resolved on the main thread before the
    worker is started so the worker stays free of GUI services.
    """

    file_item: FileItem
    source_path: Path
    profile_index: int
    output_path: Path
    userdata: dict[str, Any] | None


@dataclass(frozen=True)
class SaveProgress:
    """A single file finished saving successfully."""

    index: int


@dataclass(frozen=True)
class SaveFailure:
    """A single file failed to save."""

    index: int
    error: str


class SaveWorker(QThread):
    """Stream save: read > save > drop, one job at a time.

    Emits per-job signals so the UI can update a progress bar.
    """

    file_saved = Signal(object)  # SaveProgress
    file_failed = Signal(object)  # SaveFailure
    all_done = Signal()

    def __init__(self, jobs: list[SaveJob]) -> None:
        super().__init__()
        self._jobs = jobs

    def run(self) -> None:
        import mhkit.dolfyn as dolfyn

        log.info("Save worker started: %d job(s)", len(self._jobs))

        for i, job in enumerate(self._jobs):
            t0 = time.perf_counter()
            result = None
            ds = None
            try:
                if job.userdata is not None:
                    result = dolfyn.read(str(job.source_path), userdata=job.userdata)  # pyright: ignore[reportArgumentType] — dolfyn stub types userdata as bool, actually accepts dict
                else:
                    result = dolfyn.read(str(job.source_path))
                ds = result[job.profile_index] if isinstance(result, tuple) else result

                job.output_path.parent.mkdir(parents=True, exist_ok=True)
                log.debug("Writing %s", job.output_path.name)
                dolfyn.save(ds, str(job.output_path))
                elapsed = time.perf_counter() - t0
                log.info("Saved %s (%.1fs)", job.output_path.name, elapsed)
                self.file_saved.emit(SaveProgress(index=i))
            except Exception as exc:
                elapsed = time.perf_counter() - t0
                log.error(
                    "Failed to save %s after %.1fs: %s",
                    job.output_path.name,
                    elapsed,
                    exc,
                )
                self.file_failed.emit(SaveFailure(index=i, error=str(exc)))
            finally:
                # Release the dataset before the next iteration so peak
                # memory stays at ~one dataset regardless of corpus size.
                del result, ds

        self.all_done.emit()
        log.info("Save worker finished")
