"""Tests for the Preferences dialog: load, save, reset, bounds."""

from __future__ import annotations


def test_dialog_loads_current_settings(qtbot, isolated_qsettings):
    """Opening the dialog populates every widget from Settings."""
    from mhkit_dolfyn_gui.settings import Settings
    from mhkit_dolfyn_gui.unit_conversions import bytes_to_gb
    from mhkit_dolfyn_gui.widgets.preferences_dialog import PreferencesDialog

    s = Settings()
    s.max_concurrent_reads = 7
    s.worker_shutdown_timeout_ms = 9000
    s.dataset_cache_max_bytes = 4 * 1024 * 1024 * 1024
    s.dataset_cache_max_items = 15
    s.memory_poll_interval_ms = 1500
    s.time_gap_threshold_seconds = 90.0
    s.output_dir = "/tmp/out"
    s.filename_pattern = "x.nc"
    s.global_userdata_path = "/tmp/userdata.json"

    dlg = PreferencesDialog(s)
    qtbot.addWidget(dlg)

    assert dlg._max_reads_spin.value() == 7
    assert dlg._shutdown_timeout_spin.value() == 9000
    assert dlg._cache_bytes_spin.value() == bytes_to_gb(4 * 1024 * 1024 * 1024)
    assert dlg._cache_items_spin.value() == 15
    assert dlg._poll_interval_spin.value() == 1500
    assert dlg._gap_threshold_spin.value() == 90.0
    assert dlg._output_dir_edit.text() == "/tmp/out"
    assert dlg._pattern_edit.text() == "x.nc"
    assert dlg._userdata_edit.text() == "/tmp/userdata.json"


def test_apply_writes_back_and_emits(qtbot, isolated_qsettings):
    """Apply persists every value and emits settings_changed exactly once."""
    from mhkit_dolfyn_gui.settings import Settings
    from mhkit_dolfyn_gui.widgets.preferences_dialog import PreferencesDialog

    s = Settings()
    dlg = PreferencesDialog(s)
    qtbot.addWidget(dlg)

    dlg._max_reads_spin.setValue(12)
    dlg._cache_bytes_spin.setValue(3.5)  # GB
    dlg._cache_items_spin.setValue(20)
    dlg._gap_threshold_spin.setValue(45.0)
    dlg._output_dir_edit.setText("/tmp/x")
    dlg._pattern_edit.setText("file.nc")

    received: list[int] = []
    s.settings_changed.connect(lambda: received.append(1))

    dlg._on_apply()

    assert received == [1]
    assert s.max_concurrent_reads == 12
    assert s.dataset_cache_max_bytes == round(3.5 * 1024 * 1024 * 1024)
    assert s.dataset_cache_max_items == 20
    assert s.time_gap_threshold_seconds == 45.0
    assert s.output_dir == "/tmp/x"
    assert s.filename_pattern == "file.nc"


def test_reset_to_defaults_button(qtbot, isolated_qsettings):
    """Reset clears widgets back to constants.py defaults without persisting."""
    from mhkit_dolfyn_gui import constants
    from mhkit_dolfyn_gui.settings import Settings
    from mhkit_dolfyn_gui.widgets.preferences_dialog import PreferencesDialog

    s = Settings()
    s.max_concurrent_reads = 16
    s.dataset_cache_max_items = 99
    s.output_dir = "/tmp/somewhere"

    dlg = PreferencesDialog(s)
    qtbot.addWidget(dlg)
    assert dlg._max_reads_spin.value() == 16  # loaded the override

    dlg._on_reset_to_defaults()

    assert dlg._max_reads_spin.value() == constants.DEFAULT_MAX_CONCURRENT_READS
    assert dlg._cache_items_spin.value() == constants.DEFAULT_DATASET_CACHE_MAX_ITEMS
    assert dlg._output_dir_edit.text() == ""


def test_spinbox_bounds_clamp_extreme_values(qtbot, isolated_qsettings):
    """Spinboxes refuse out-of-range values, protecting Settings."""
    from mhkit_dolfyn_gui.settings import Settings
    from mhkit_dolfyn_gui.widgets.preferences_dialog import PreferencesDialog

    s = Settings()
    dlg = PreferencesDialog(s)
    qtbot.addWidget(dlg)

    dlg._max_reads_spin.setValue(9999)
    assert dlg._max_reads_spin.value() == 32  # upper bound

    dlg._max_reads_spin.setValue(-5)
    assert dlg._max_reads_spin.value() == 1  # lower bound

    dlg._cache_bytes_spin.setValue(9999.0)
    assert dlg._cache_bytes_spin.value() == 64.0  # upper bound (GB)

    dlg._cache_bytes_spin.setValue(0.0)
    assert dlg._cache_bytes_spin.value() == 0.5  # lower bound
