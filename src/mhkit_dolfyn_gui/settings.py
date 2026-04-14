"""Persistent application settings using QSettings.

``Settings`` is a thin ``QObject`` wrapper around ``QSettings``. The
constants in :mod:`mhkit_dolfyn_gui.constants` are the canonical default
values; ``Settings`` reads them via ``QSettings.value(..., default=...)``
so a fresh install always behaves like the bundled defaults until the
user overrides them in the Preferences dialog.

The ``settings_changed`` signal is emitted whenever ``apply_changes`` is
called by the Preferences dialog. Listeners (the cache, the memory
indicator, the deployment overview, etc.) refresh themselves from the
new values without requiring a restart.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QObject, QSettings, Signal

from mhkit_dolfyn_gui.constants import (
    APP_NAME,
    DEFAULT_DATASET_CACHE_MAX_BYTES,
    DEFAULT_DATASET_CACHE_MAX_ITEMS,
    DEFAULT_FILENAME_PATTERN,
    DEFAULT_MAX_CONCURRENT_READS,
    DEFAULT_MEMORY_POLL_INTERVAL_MS,
    DEFAULT_TIME_GAP_THRESHOLD_SECONDS,
    DEFAULT_WORKER_SHUTDOWN_TIMEOUT_MS,
)

# Keys whose default lives in constants.py. Listed here so reset_to_defaults
# and the Preferences dialog can iterate them uniformly.
_PREFERENCE_KEYS: tuple[str, ...] = (
    "max_concurrent_reads",
    "dataset_cache_max_bytes",
    "dataset_cache_max_items",
    "worker_shutdown_timeout_ms",
    "memory_poll_interval_ms",
    "time_gap_threshold_seconds",
    "output_dir",
    "filename_pattern",
    "global_userdata_path",
    # ME Data Pipeline naming fields (persisted per-deployment)
    "me_location_id",
    "me_dataset_name",
    "me_qualifier",
    "me_data_level",
    "me_include_temporal",
    "me_timezone_offset_hours",
)


class Settings(QObject):
    """Type-safe wrapper around ``QSettings`` for app preferences.

    Inherits from ``QObject`` so the Preferences dialog can broadcast a
    single ``settings_changed`` signal after a batch of edits, instead of
    every consumer polling on a timer.
    """

    settings_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._qs = QSettings(APP_NAME, APP_NAME)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_int(self, key: str, default: int) -> int:
        # QSettings on some platforms returns strings even for ints written
        # in the same session — coerce defensively. ``QSettings.value`` is
        # typed as returning ``object``, so accept anything ``int()`` will
        # take and fall back to the default for everything else.
        val = self._qs.value(key, default)
        if isinstance(val, int):
            return val
        if isinstance(val, (str, float, bool)):
            try:
                return int(val)
            except (TypeError, ValueError):
                return default
        return default

    def _get_float(self, key: str, default: float) -> float:
        val = self._qs.value(key, default)
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, (str, bool)):
            try:
                return float(val)
            except (TypeError, ValueError):
                return default
        return default

    # ------------------------------------------------------------------
    # Output directory
    # ------------------------------------------------------------------

    @property
    def output_dir(self) -> str:
        return str(self._qs.value("output_dir", ""))

    @output_dir.setter
    def output_dir(self, value: str) -> None:
        self._qs.setValue("output_dir", value)

    # ------------------------------------------------------------------
    # Filename pattern
    # ------------------------------------------------------------------

    @property
    def filename_pattern(self) -> str:
        return str(self._qs.value("filename_pattern", DEFAULT_FILENAME_PATTERN))

    @filename_pattern.setter
    def filename_pattern(self, value: str) -> None:
        self._qs.setValue("filename_pattern", value)

    # ------------------------------------------------------------------
    # Last input directory
    # ------------------------------------------------------------------

    @property
    def last_input_dir(self) -> str:
        return str(self._qs.value("last_input_dir", ""))

    @last_input_dir.setter
    def last_input_dir(self, value: str) -> None:
        self._qs.setValue("last_input_dir", value)

    # ------------------------------------------------------------------
    # Global userdata.json path
    # ------------------------------------------------------------------

    @property
    def global_userdata_path(self) -> str:
        return str(self._qs.value("global_userdata_path", ""))

    @global_userdata_path.setter
    def global_userdata_path(self, value: str) -> None:
        self._qs.setValue("global_userdata_path", value)

    # ------------------------------------------------------------------
    # Performance: max concurrent reads
    # ------------------------------------------------------------------

    @property
    def max_concurrent_reads(self) -> int:
        return self._get_int("max_concurrent_reads", DEFAULT_MAX_CONCURRENT_READS)

    @max_concurrent_reads.setter
    def max_concurrent_reads(self, value: int) -> None:
        self._qs.setValue("max_concurrent_reads", int(value))

    # ------------------------------------------------------------------
    # Performance: worker shutdown timeout
    # ------------------------------------------------------------------

    @property
    def worker_shutdown_timeout_ms(self) -> int:
        return self._get_int("worker_shutdown_timeout_ms", DEFAULT_WORKER_SHUTDOWN_TIMEOUT_MS)

    @worker_shutdown_timeout_ms.setter
    def worker_shutdown_timeout_ms(self, value: int) -> None:
        self._qs.setValue("worker_shutdown_timeout_ms", int(value))

    # ------------------------------------------------------------------
    # Cache: max bytes (RAM ceiling)
    # ------------------------------------------------------------------

    @property
    def dataset_cache_max_bytes(self) -> int:
        return self._get_int("dataset_cache_max_bytes", DEFAULT_DATASET_CACHE_MAX_BYTES)

    @dataset_cache_max_bytes.setter
    def dataset_cache_max_bytes(self, value: int) -> None:
        self._qs.setValue("dataset_cache_max_bytes", int(value))

    # ------------------------------------------------------------------
    # Cache: max items
    # ------------------------------------------------------------------

    @property
    def dataset_cache_max_items(self) -> int:
        return self._get_int("dataset_cache_max_items", DEFAULT_DATASET_CACHE_MAX_ITEMS)

    @dataset_cache_max_items.setter
    def dataset_cache_max_items(self, value: int) -> None:
        self._qs.setValue("dataset_cache_max_items", int(value))

    # ------------------------------------------------------------------
    # Cache: memory poll interval
    # ------------------------------------------------------------------

    @property
    def memory_poll_interval_ms(self) -> int:
        return self._get_int("memory_poll_interval_ms", DEFAULT_MEMORY_POLL_INTERVAL_MS)

    @memory_poll_interval_ms.setter
    def memory_poll_interval_ms(self, value: int) -> None:
        self._qs.setValue("memory_poll_interval_ms", int(value))

    # ------------------------------------------------------------------
    # Deployment: time gap threshold
    # ------------------------------------------------------------------

    @property
    def time_gap_threshold_seconds(self) -> float:
        return self._get_float("time_gap_threshold_seconds", DEFAULT_TIME_GAP_THRESHOLD_SECONDS)

    @time_gap_threshold_seconds.setter
    def time_gap_threshold_seconds(self, value: float) -> None:
        self._qs.setValue("time_gap_threshold_seconds", float(value))

    # ------------------------------------------------------------------
    # Window geometry
    # ------------------------------------------------------------------

    @property
    def window_geometry(self) -> QByteArray:
        val = self._qs.value("window_geometry")
        if isinstance(val, QByteArray):
            return val
        return QByteArray()

    @window_geometry.setter
    def window_geometry(self, value: QByteArray) -> None:
        self._qs.setValue("window_geometry", value)

    # ------------------------------------------------------------------
    # ME Data Pipeline naming fields
    # ------------------------------------------------------------------

    @property
    def me_location_id(self) -> str:
        return str(self._qs.value("me_location_id", ""))

    @me_location_id.setter
    def me_location_id(self, value: str) -> None:
        self._qs.setValue("me_location_id", value)

    @property
    def me_dataset_name(self) -> str:
        return str(self._qs.value("me_dataset_name", ""))

    @me_dataset_name.setter
    def me_dataset_name(self, value: str) -> None:
        self._qs.setValue("me_dataset_name", value)

    @property
    def me_qualifier(self) -> str:
        return str(self._qs.value("me_qualifier", ""))

    @me_qualifier.setter
    def me_qualifier(self, value: str) -> None:
        self._qs.setValue("me_qualifier", value)

    @property
    def me_data_level(self) -> str:
        return str(self._qs.value("me_data_level", "a1"))

    @me_data_level.setter
    def me_data_level(self, value: str) -> None:
        self._qs.setValue("me_data_level", value)

    @property
    def me_include_temporal(self) -> bool:
        val = self._qs.value("me_include_temporal", True)
        if isinstance(val, bool):
            return val
        return str(val).lower() not in ("false", "0", "")

    @me_include_temporal.setter
    def me_include_temporal(self, value: bool) -> None:
        self._qs.setValue("me_include_temporal", value)

    @property
    def me_timezone_offset_hours(self) -> int:
        return self._get_int("me_timezone_offset_hours", 0)

    @me_timezone_offset_hours.setter
    def me_timezone_offset_hours(self, value: int) -> None:
        self._qs.setValue("me_timezone_offset_hours", int(value))

    # ------------------------------------------------------------------
    # Generic bytes storage (for splitter states etc.)
    # ------------------------------------------------------------------

    def get_bytes(self, key: str) -> QByteArray:
        val = self._qs.value(key)
        if isinstance(val, QByteArray):
            return val
        return QByteArray()

    def set_bytes(self, key: str, value: QByteArray) -> None:
        self._qs.setValue(key, value)

    # ------------------------------------------------------------------
    # Bulk update / reset
    # ------------------------------------------------------------------

    def reset_to_defaults(self) -> None:
        """Remove every preference key so getters fall back to constants.py.

        Window geometry, splitter state, and last_input_dir are session
        scratch — left untouched.
        """
        for key in _PREFERENCE_KEYS:
            self._qs.remove(key)

    def notify_changed(self) -> None:
        """Emit ``settings_changed`` after a batch of edits.

        Called by the Preferences dialog on Apply/OK so subscribers can
        refresh themselves from the new values in one pass.
        """
        self._qs.sync()
        self.settings_changed.emit()
