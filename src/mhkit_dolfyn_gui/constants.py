"""Application constants."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from mhkit_dolfyn_gui import __version__ as APP_VERSION

APP_NAME = "MHKiT-DOLFyN-GUI"
APP_DISPLAY_NAME = "Marine and Hydrokinetic Toolkit - Doppler Oceanographic Library for Python"

MAIN_WINDOW_TITLE = f"{APP_DISPLAY_NAME} [{APP_NAME}] | Version {APP_VERSION}"

# External links (matching mhkit-gui pattern)
GITHUB_ISSUES_URL = "https://github.com/MHKiT-Software/mhkit_dolfyn_pyqt_gui/issues"
MHKIT_REPO_URL = "https://github.com/MHKiT-Software/MHKiT-Python"
MHKIT_DOCS_URL = "https://mhkit-software.github.io/MHKiT/mhkit-python/api.dolfyn.html"

# Python strftime reference URL
STRFTIME_DOCS_URL = (
    "https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes"
)


def _load_supported_instruments() -> dict[str, Any]:
    """Load the supported-instruments JSON generated from DOLFyN source.

    The JSON is produced by `scripts/generate_supported_instruments.py` which
    parses mhkit.dolfyn directly. Re-run that script after upgrading mhkit.
    """
    data_path = files("mhkit_dolfyn_gui").joinpath("data/supported_instruments.json")
    return json.loads(data_path.read_text())


_INSTRUMENTS_DATA = _load_supported_instruments()

# Raw instrument file extensions that mhkit.dolfyn can read
SUPPORTED_EXTENSIONS = frozenset(_INSTRUMENTS_DATA["all_extensions"])

# Mapping of instrument display name → (extensions, instrument type) for
# user-facing docs. Built from supported_instruments.json (sourced from
# DOLFyN); preserved as a tuple-of-tuples for backwards compatibility.
SUPPORTED_INSTRUMENTS: dict[str, tuple[tuple[str, ...], str]] = {
    f"{inst['manufacturer']} {inst['name']}": (tuple(inst["extensions"]), inst["type"])
    for inst in _INSTRUMENTS_DATA["instruments"]
}

# File dialog filter string
_ext_glob = " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))
FILE_FILTER = f"ADCP/ADV Files ({_ext_glob});;All Files (*)"

# SETTINGS DEFAULT VALUES

# Default filename pattern for export
DEFAULT_FILENAME_PATTERN = "{filename}_{start_date:%Y%m%d}.nc"

# Threshold (seconds) above which a gap between consecutive files is flagged
# in the deployment overview. Anything below ``-1`` is treated as overlap.
DEFAULT_TIME_GAP_THRESHOLD_SECONDS = 60.0

# How long to wait for background QThread workers to finish on shutdown before
# logging a warning and abandoning them. dolfyn.read() is uninterruptible C
# code, so this is a safety net rather than a hard cancel.
DEFAULT_WORKER_SHUTDOWN_TIMEOUT_MS = 5000

# Pixel size of the MHKiT logo rendered in the status bar.
STATUS_BAR_LOGO_SIZE_PX = 20

# Minimum width of the file sidebar dock so the file list stays usable.
MIN_FILE_SIDEBAR_WIDTH_PX = 180

# Maximum number of FileReadWorker QThreads that may run concurrently.
# Add Files dispatches reads through a bounded scheduler so the UI stays
# responsive when the user picks hundreds of files at once.
DEFAULT_MAX_CONCURRENT_READS = 4

# Resident dataset cache limits. Eviction (LRU) triggers as soon as either
# limit is exceeded; whichever fires first wins.
DEFAULT_DATASET_CACHE_MAX_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
DEFAULT_DATASET_CACHE_MAX_ITEMS = 10

# How often the status-bar memory indicator polls process RSS.
DEFAULT_MEMORY_POLL_INTERVAL_MS = 2000
