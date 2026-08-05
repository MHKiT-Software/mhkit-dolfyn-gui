"""Shared test fixtures."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

# Force Qt to use the offscreen (software) platform on Linux so the xcb
# platform plugin — which requires a live display server and specific system
# libraries — is never loaded.  Widgets are still fully functional; only
# actual screen rendering is skipped, which no test requires.
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
import xarray as xr

if TYPE_CHECKING:
    from collections.abc import Iterator

    from mhkit_dolfyn_gui.main_window import MainWindow


@pytest.fixture
def sample_adcp_dataset() -> xr.Dataset:
    """Create a minimal xarray Dataset mimicking mhkit.dolfyn ADCP output."""
    n_time = 100
    n_range = 20
    n_beam = 4

    times = np.arange(
        np.datetime64("2024-01-15T08:00:00"),
        np.datetime64("2024-01-15T08:00:00") + np.timedelta64(n_time, "s"),
        np.timedelta64(1, "s"),
    )

    ds = xr.Dataset(
        {
            "vel": (["dir", "range", "time"], np.random.randn(3, n_range, n_time)),
            "amp": (["beam", "range", "time"], np.random.randn(n_beam, n_range, n_time)),
            "corr": (["beam", "range", "time"], np.random.randn(n_beam, n_range, n_time)),
            "heading": (["time"], np.random.uniform(0, 360, n_time)),
            "pitch": (["time"], np.random.uniform(-5, 5, n_time)),
            "roll": (["time"], np.random.uniform(-5, 5, n_time)),
        },
        coords={
            "time": times,
            "range": np.arange(n_range, dtype=float),
            "dir": np.array([1, 2, 3], dtype=np.int32),
        },
        attrs={
            "inst_type": "ADCP",
            "inst_make": "Nortek",
            "inst_model": "Signature1000",
            "serial_number": "12345",
            "fs": 1.0,
            "coord_sys": "beam",
            "n_bins": 20,
            "n_beams": 4,
        },
    )
    return ds


@pytest.fixture
def sample_adv_dataset() -> xr.Dataset:
    """Create a minimal xarray Dataset mimicking mhkit.dolfyn ADV output."""
    n_time = 3200
    n_beam = 3

    times = np.arange(
        np.datetime64("2024-03-10T14:00:00"),
        np.datetime64("2024-03-10T14:00:00") + np.timedelta64(n_time * 31250, "us"),
        np.timedelta64(31250, "us"),  # 32 Hz
    )[:n_time]

    ds = xr.Dataset(
        {
            "vel": (["dir", "time"], np.random.randn(3, n_time)),
            "amp": (["beam", "time"], np.random.randn(n_beam, n_time)),
            "corr": (["beam", "time"], np.random.randn(n_beam, n_time)),
            "pressure": (["time"], np.random.uniform(10, 11, n_time)),
        },
        coords={
            "time": times,
            "dir": np.array([1, 2, 3], dtype=np.int32),
        },
        attrs={
            "inst_type": "ADV",
            "inst_make": "Nortek",
            "inst_model": "Vector",
            "serial_number": "67890",
            "fs": 32.0,
            "coord_sys": "inst",
            "n_beams": 3,
        },
    )
    return ds


@pytest.fixture
def fake_dolfyn_dataset(sample_adcp_dataset: xr.Dataset) -> xr.Dataset:
    """Alias for the ADCP fixture — used by pipeline tests that just need
    *some* dataset that looks enough like dolfyn output."""
    return sample_adcp_dataset


@pytest.fixture(autouse=True)
def isolated_qsettings(tmp_path, monkeypatch):
    """Redirect QSettings to a per-test temp dir so no test can read or write
    the developer's real preferences.

    ``autouse=True`` means every test is isolated automatically; tests may
    still request ``isolated_qsettings`` by name (e.g. to reference the
    returned temp dir) without conflict.

    ``QSettings.setPath`` only affects the ``IniFormat`` backend. On macOS
    (and Windows) the ``QSettings(org, app)`` constructor used by ``Settings``
    defaults to ``NativeFormat`` (a plist / the registry), which ignores
    ``setPath`` — so we must force the Ini backend for the settings module.
    We monkeypatch the ``QSettings`` name imported into ``settings`` with a
    factory that constructs an ``IniFormat``/``UserScope`` instance rooted at
    ``tmp_path``; production code is untouched.
    """
    from PySide6.QtCore import QSettings

    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )

    def _isolated_factory(*args, **kwargs):
        return QSettings(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            *args,
            **kwargs,
        )

    from mhkit_dolfyn_gui import settings as settings_mod

    monkeypatch.setattr(settings_mod, "QSettings", _isolated_factory)
    return tmp_path


@pytest.fixture
def main_window(qtbot, isolated_qsettings) -> Iterator[MainWindow]:
    """A fully-staged MainWindow with PreloadWorker stubbed out.

    The preload worker imports mhkit.dolfyn on a background thread. We stub
    its ``run`` method so tests do not pay the import cost or risk a slow
    teardown when ``mhkit`` is unavailable.
    """
    from mhkit_dolfyn_gui.main_window import MainWindow
    from mhkit_dolfyn_gui.workers import preload_worker

    # No-op the preload thread before constructing the window.
    original_run = preload_worker.PreloadWorker.run
    preload_worker.PreloadWorker.run = lambda self: None

    try:
        window = MainWindow()
        window.init_stage_ui()
        window.init_stage_restore()
        qtbot.addWidget(window)
        yield window
    finally:
        # Ensure any spawned QThreads are stopped before the test ends.
        if window._preload_worker is not None and window._preload_worker.isRunning():
            window._preload_worker.wait(2000)
        for w in list(window._read_scheduler._read_workers):
            if w.isRunning():
                w.wait(2000)
        preload_worker.PreloadWorker.run = original_run
