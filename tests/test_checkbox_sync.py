"""Bidirectional checkbox sync — proves the no-op guard prevents loops.

Contract (per ``FileListPanel.set_item_checked``):

* Programmatic ``set_item_checked`` updates the model and the tree row, but
  blocks tree signals so the canonical ``check_state_changed`` is **not**
  re-emitted. This is the loop-breaker.
* The signal only fires from genuine user input on the tree widget itself.
* A no-op set (current value == new value) returns in O(1) before touching
  any state.
"""

from __future__ import annotations

from unittest.mock import patch

from PySide6.QtCore import Qt

from mhkit_dolfyn_gui.models.file_item import FileStatus
from mhkit_dolfyn_gui.widgets.file_sidebar.constants import COL_CONVERT


def _ready_window(qtbot, main_window, tmp_path, fake_dolfyn_dataset):
    test_file = tmp_path / "x.000"
    test_file.write_bytes(b"\x00")
    with patch("mhkit.dolfyn.read", return_value=fake_dolfyn_dataset):
        main_window._file_sidebar._list._add_paths([test_file])
        qtbot.waitUntil(
            lambda: (
                main_window._file_sidebar.file_items
                and main_window._file_sidebar.file_items[0].status == FileStatus.READY
            ),
            timeout=5000,
        )


def test_programmatic_set_updates_state_without_emitting(
    qtbot, main_window, tmp_path, fake_dolfyn_dataset
):
    _ready_window(qtbot, main_window, tmp_path, fake_dolfyn_dataset)

    emitted: list[tuple[int, bool]] = []
    main_window._file_sidebar.check_state_changed.connect(lambda i, c: emitted.append((i, c)))

    main_window._file_sidebar.set_item_checked(0, False)

    # Model and tree row both flipped, but no signal emission (loop breaker).
    assert main_window._file_sidebar.file_items[0].checked is False
    panel = main_window._file_sidebar._list
    assert panel._tree.topLevelItem(0).checkState(COL_CONVERT) == Qt.CheckState.Unchecked
    assert emitted == []


def test_noop_set_returns_immediately(qtbot, main_window, tmp_path, fake_dolfyn_dataset):
    _ready_window(qtbot, main_window, tmp_path, fake_dolfyn_dataset)

    # Item is checked by default; setting True again must be a no-op.
    assert main_window._file_sidebar.file_items[0].checked is True

    emitted: list[tuple[int, bool]] = []
    main_window._file_sidebar.check_state_changed.connect(lambda i, c: emitted.append((i, c)))
    main_window._file_sidebar.set_item_checked(0, True)
    assert emitted == []


def test_user_toggle_emits_exactly_once(qtbot, main_window, tmp_path, fake_dolfyn_dataset):
    """A real user toggle on the tree fires the signal exactly once and the
    sync loop terminates without an avalanche."""
    _ready_window(qtbot, main_window, tmp_path, fake_dolfyn_dataset)

    emitted: list[tuple[int, bool]] = []
    main_window._file_sidebar.check_state_changed.connect(lambda i, c: emitted.append((i, c)))

    panel = main_window._file_sidebar._list
    row = panel._tree.topLevelItem(0)
    # Simulate the user clicking the checkbox: this fires _on_item_changed,
    # which is the only path that emits check_state_changed.
    row.setCheckState(COL_CONVERT, Qt.CheckState.Unchecked)

    assert emitted == [(0, False)]
    assert main_window._file_sidebar.file_items[0].checked is False
