"""Background thread for reading a single ADCP/ADV file with mhkit.dolfyn.

Each FileReadWorker is an independent QThread that owns its own state.
Spawn one per file for parallel reads.

Worker contract
---------------
- ``finished`` carries a :class:`ReadResult` (success).
- ``failed`` carries a :class:`ReadFailure` (exception during read).
Both payloads include the originating :class:`FileItem` so the receiver
can route by identity — the file list may have mutated since the read
was scheduled.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QThread, Signal

from mhkit_dolfyn_gui.services.userdata_service import resolve_userdata

if TYPE_CHECKING:
    from pathlib import Path

    import xarray as xr

    from mhkit_dolfyn_gui.models.file_item import FileItem

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReadResult:
    """Successful read of a single file. Routed by ``file_item`` identity."""

    file_item: FileItem
    primary: xr.Dataset
    extras: tuple[xr.Dataset, ...]
    userdata_source: Path | None


@dataclass(frozen=True)
class ReadFailure:
    """Failed read of a single file."""

    file_item: FileItem
    error: str


class FileReadWorker(QThread):
    """Read a single ADCP/ADV binary file on its own thread.

    Each worker is independent — no shared state between workers.
    The ``file_item`` attribute is the routing key for identity-based
    lookup on the receiving side.
    """

    finished = Signal(object)  # ReadResult
    failed = Signal(object)  # ReadFailure

    def __init__(
        self,
        path: Path,
        file_item: FileItem,
        global_userdata_path: Path | None = None,
    ) -> None:
        super().__init__()
        self._path = path
        self._file_item = file_item
        self._global_userdata_path = global_userdata_path

    @property
    def file_item(self) -> FileItem:
        """The FileItem this worker is reading. Use for identity-based lookup."""
        return self._file_item

    def run(self) -> None:
        import mhkit.dolfyn as dolfyn

        name = self._path.name
        log.debug("Reading %s", name)
        t0 = time.perf_counter()

        try:
            userdata: dict[str, Any] | None
            userdata_source = None
            try:
                userdata, userdata_source = resolve_userdata(
                    self._file_item, self._global_userdata_path
                )
            except ValueError as exc:
                log.warning("Userdata not applied for %s: %s", name, exc)
                userdata = None

            if userdata_source is not None:
                log.info("Applying userdata from %s to %s", userdata_source.name, name)

            if userdata is not None:
                result = dolfyn.read(str(self._path), userdata=userdata)  # pyright: ignore[reportArgumentType] — dolfyn stub types userdata as bool, actually accepts dict
            else:
                result = dolfyn.read(str(self._path))

            elapsed = time.perf_counter() - t0

            if isinstance(result, tuple):
                primary = result[0]
                extras = tuple(result[1:])
                total_ens = sum(int(ds.sizes.get("time", 0)) for ds in result)
                log.info(
                    "Read %s: %d profile(s), %d ensembles total in %.1fs",
                    name,
                    len(result),
                    total_ens,
                    elapsed,
                )
            else:
                primary = result
                extras = ()
                n_ens = int(primary.sizes.get("time", 0))
                log.info("Read %s: %d ensembles in %.1fs", name, n_ens, elapsed)

            self.finished.emit(
                ReadResult(
                    file_item=self._file_item,
                    primary=primary,
                    extras=extras,
                    userdata_source=userdata_source,
                )
            )
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            log.error("Failed to read %s after %.1fs: %s", name, elapsed, exc)
            self.failed.emit(ReadFailure(file_item=self._file_item, error=str(exc)))
