"""Settings round-trip — values written by Settings must come back on reload."""

from __future__ import annotations


def test_settings_round_trip(isolated_qsettings):
    from mhkit_dolfyn_gui.settings import Settings

    s1 = Settings()
    s1.output_dir = "/tmp/out"
    s1.filename_pattern = "{stem}_test.nc"
    s1.last_input_dir = "/tmp/in"
    s1._qs.sync()

    s2 = Settings()
    assert s2.output_dir == "/tmp/out"
    assert s2.filename_pattern == "{stem}_test.nc"
    assert s2.last_input_dir == "/tmp/in"


def test_window_geometry_round_trip(qtbot, isolated_qsettings):
    """A MainWindow's geometry survives a close/reopen via QSettings."""
    from PySide6.QtCore import QByteArray

    from mhkit_dolfyn_gui.settings import Settings

    s1 = Settings()
    payload = QByteArray(b"some-opaque-geometry")
    s1.window_geometry = payload
    s1._qs.sync()

    s2 = Settings()
    assert bytes(s2.window_geometry) == b"some-opaque-geometry"


def test_preference_defaults_match_constants(isolated_qsettings):
    """A fresh Settings instance returns the constants.py defaults."""
    from mhkit_dolfyn_gui import constants
    from mhkit_dolfyn_gui.settings import Settings

    s = Settings()
    assert s.max_concurrent_reads == constants.DEFAULT_MAX_CONCURRENT_READS
    assert s.worker_shutdown_timeout_ms == constants.DEFAULT_WORKER_SHUTDOWN_TIMEOUT_MS
    assert s.dataset_cache_max_bytes == constants.DEFAULT_DATASET_CACHE_MAX_BYTES
    assert s.dataset_cache_max_items == constants.DEFAULT_DATASET_CACHE_MAX_ITEMS
    assert s.memory_poll_interval_ms == constants.DEFAULT_MEMORY_POLL_INTERVAL_MS
    assert s.time_gap_threshold_seconds == constants.DEFAULT_TIME_GAP_THRESHOLD_SECONDS


def test_preference_round_trip(isolated_qsettings):
    """All new numeric preferences survive write → reload."""
    from mhkit_dolfyn_gui.settings import Settings

    s1 = Settings()
    s1.max_concurrent_reads = 8
    s1.worker_shutdown_timeout_ms = 12345
    s1.dataset_cache_max_bytes = 5 * 1024 * 1024 * 1024
    s1.dataset_cache_max_items = 25
    s1.memory_poll_interval_ms = 3500
    s1.time_gap_threshold_seconds = 120.5
    s1._qs.sync()

    s2 = Settings()
    assert s2.max_concurrent_reads == 8
    assert s2.worker_shutdown_timeout_ms == 12345
    assert s2.dataset_cache_max_bytes == 5 * 1024 * 1024 * 1024
    assert s2.dataset_cache_max_items == 25
    assert s2.memory_poll_interval_ms == 3500
    assert s2.time_gap_threshold_seconds == 120.5


def test_reset_to_defaults_restores_constants(isolated_qsettings):
    """reset_to_defaults clears overrides so getters fall back to constants."""
    from mhkit_dolfyn_gui import constants
    from mhkit_dolfyn_gui.settings import Settings

    s = Settings()
    s.max_concurrent_reads = 16
    s.dataset_cache_max_items = 99
    s.output_dir = "/tmp/somewhere"
    s.filename_pattern = "custom.nc"
    s._qs.sync()

    s.reset_to_defaults()
    s._qs.sync()

    s2 = Settings()
    assert s2.max_concurrent_reads == constants.DEFAULT_MAX_CONCURRENT_READS
    assert s2.dataset_cache_max_items == constants.DEFAULT_DATASET_CACHE_MAX_ITEMS
    assert s2.output_dir == ""  # default for unset string
    assert s2.filename_pattern == constants.DEFAULT_FILENAME_PATTERN


def test_notify_changed_emits_signal(isolated_qsettings):
    """Settings.notify_changed should fire settings_changed exactly once."""
    from mhkit_dolfyn_gui.settings import Settings

    s = Settings()
    received: list[int] = []
    s.settings_changed.connect(lambda: received.append(1))

    s.max_concurrent_reads = 6
    s.notify_changed()

    assert received == [1]
