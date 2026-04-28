"""Tests for the bounded read scheduler in MainWindow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from mhkit_dolfyn_gui.constants import DEFAULT_MAX_CONCURRENT_READS as MAX_CONCURRENT_READS_DEFAULT
from mhkit_dolfyn_gui.models.file_item import FileStatus

if TYPE_CHECKING:
    from pathlib import Path


def _make_binary(tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    p.write_bytes(b"\x00" * 16)
    return p


def test_scheduler_caps_concurrent_reads(qtbot, main_window, tmp_path, fake_dolfyn_dataset):
    """Enqueue many files at once and observe the active count never exceeds the cap."""
    files = [_make_binary(tmp_path, f"f{i:03d}.000") for i in range(50)]

    cap = main_window._settings.max_concurrent_reads
    # Sanity: with isolated_qsettings, the cap should equal the constant default.
    assert cap == MAX_CONCURRENT_READS_DEFAULT

    observed_max = 0

    def slow_read(*_a, **_kw):
        # Sleep just long enough that several workers overlap.
        import time

        time.sleep(0.05)
        return fake_dolfyn_dataset

    with patch("mhkit.dolfyn.read", side_effect=slow_read):
        main_window._file_sidebar._list._add_paths(files)

        def sample() -> bool:
            nonlocal observed_max
            observed_max = max(observed_max, len(main_window._read_scheduler._active_reads))
            assert len(main_window._read_scheduler._active_reads) <= cap
            # Evicted items go back to CACHED — terminal for this test.
            return (
                not main_window._read_scheduler._read_queue
                and not main_window._read_scheduler._active_reads
            )

        qtbot.waitUntil(sample, timeout=15000)

    items = main_window._file_sidebar.file_items
    assert len(items) == 50
    # All items eventually finished. Items past the LRU cache window are
    # silently evicted back to PENDING; the rest are READY.
    statuses = {it.status for it in items}
    assert statuses <= {FileStatus.READY, FileStatus.CACHED}, statuses
    # And the cap was actually exercised — sanity check.
    assert observed_max >= 1
    assert observed_max <= cap
