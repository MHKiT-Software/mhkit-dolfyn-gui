"""FileReadWorker lifecycle tests — independent of MainWindow."""

from __future__ import annotations

from unittest.mock import patch

from mhkit_dolfyn_gui.models.file_item import FileItem
from mhkit_dolfyn_gui.workers.read_worker import FileReadWorker


def test_read_worker_emits_finished_on_success(qtbot, tmp_path, fake_dolfyn_dataset):
    path = tmp_path / "x.000"
    path.write_bytes(b"\x00")
    item = FileItem(path=path)
    worker = FileReadWorker(path=path, file_item=item)

    with (
        patch("mhkit.dolfyn.read", return_value=fake_dolfyn_dataset),
        qtbot.waitSignal(worker.finished, timeout=3000) as blocker,
    ):
        worker.start()

    result = blocker.args[0]
    assert result.file_item is item
    assert result.primary is fake_dolfyn_dataset
    assert result.extras == ()
    worker.wait(2000)


def test_read_worker_emits_failed_on_exception(qtbot, tmp_path):
    path = tmp_path / "x.000"
    path.write_bytes(b"\x00")
    item = FileItem(path=path)
    worker = FileReadWorker(path=path, file_item=item)

    with (
        patch("mhkit.dolfyn.read", side_effect=RuntimeError("boom")),
        qtbot.waitSignal(worker.failed, timeout=3000) as blocker,
    ):
        worker.start()

    failure = blocker.args[0]
    assert failure.file_item is item
    assert "boom" in failure.error
    worker.wait(2000)
