"""MainWindow integration tests — exercise the full add → read → display pipeline."""

from __future__ import annotations

import time
from unittest.mock import patch

from mhkit_dolfyn_gui.models.file_item import FileStatus


def _add_file(window, path):
    """Drive the sidebar's add path the same way the file dialog does."""
    window._file_sidebar._list._add_paths([path])


def _make_binary(tmp_path, name: str = "fake.000"):
    p = tmp_path / name
    p.write_bytes(b"\x00" * 16)
    return p


def test_add_file_triggers_read_and_populates_panels(
    qtbot, main_window, tmp_path, fake_dolfyn_dataset
):
    test_file = _make_binary(tmp_path)

    with patch("mhkit.dolfyn.read", return_value=fake_dolfyn_dataset):
        _add_file(main_window, test_file)
        qtbot.waitUntil(
            lambda: (
                main_window._file_sidebar.file_items
                and main_window._file_sidebar.file_items[0].status == FileStatus.READY
            ),
            timeout=5000,
        )

    items = main_window._file_sidebar.file_items
    assert len(items) == 1
    assert items[0].dataset is fake_dolfyn_dataset
    # The export sidebar must have been told about the same item.
    assert main_window._export_sidebar._config._file_items == items


def test_clear_during_read_drops_stale_results(qtbot, main_window, tmp_path, fake_dolfyn_dataset):
    """Clearing while a worker is mid-read must not leave stale UI state."""
    test_file = _make_binary(tmp_path)

    def slow_read(*_args, **_kwargs):
        time.sleep(0.4)
        return fake_dolfyn_dataset

    with patch("mhkit.dolfyn.read", side_effect=slow_read):
        _add_file(main_window, test_file)
        # Clear immediately while the worker is still running.
        main_window._file_sidebar._list._on_clear()
        qtbot.wait(700)

    assert main_window._file_sidebar.file_items == []


def test_remove_during_read_routes_by_identity(qtbot, main_window, tmp_path, fake_dolfyn_dataset):
    """If A and B are reading and A is removed, B's result must still land."""
    a = _make_binary(tmp_path, "a.000")
    b = _make_binary(tmp_path, "b.000")

    def slow_read(*_args, **_kwargs):
        time.sleep(0.2)
        return fake_dolfyn_dataset

    with patch("mhkit.dolfyn.read", side_effect=slow_read):
        _add_file(main_window, a)
        _add_file(main_window, b)
        # Remove A immediately — index shifts, but identity routing handles it.
        main_window._file_sidebar._list._remove_file(0)

        qtbot.waitUntil(
            lambda: (
                main_window._file_sidebar.file_items
                and main_window._file_sidebar.file_items[0].status == FileStatus.READY
            ),
            timeout=5000,
        )

    items = main_window._file_sidebar.file_items
    assert len(items) == 1
    assert items[0].path == b
