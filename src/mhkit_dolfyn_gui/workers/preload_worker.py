"""Background thread to preload heavy imports at startup.

mhkit.dolfyn pulls in numpy, scipy, xarray, netCDF4 etc. on first import.
Doing this during the splash screen means it's already cached when
the user triggers their first file read.
"""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)


class PreloadWorker(QThread):
    """Import mhkit.dolfyn on a background thread so it's ready when needed."""

    done = Signal(float)  # elapsed seconds

    def run(self) -> None:
        t0 = time.perf_counter()
        log.info("Preloading mhkit.dolfyn...")
        try:
            import mhkit.dolfyn
            import mhkit.dolfyn.io.api

            _ = mhkit.dolfyn, mhkit.dolfyn.io.api  # ensure not optimized away

            elapsed = time.perf_counter() - t0
            log.info("mhkit.dolfyn preloaded in %.1fs", elapsed)
            self.done.emit(elapsed)
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            log.error("Preload failed after %.1fs: %s", elapsed, exc)
            self.done.emit(elapsed)
