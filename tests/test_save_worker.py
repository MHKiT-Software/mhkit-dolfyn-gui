"""Tests for the streaming SaveWorker."""

from __future__ import annotations

import sys
import types
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from mhkit_dolfyn_gui.models.file_item import FileItem
from mhkit_dolfyn_gui.workers.save_worker import (
    SaveFailure,
    SaveJob,
    SaveProgress,
    SaveWorker,
)


@pytest.fixture
def fake_dolfyn(monkeypatch):
    """Install a stub ``mhkit.dolfyn`` module so the worker never imports the real package."""
    fake = types.ModuleType("mhkit.dolfyn")
    fake.read = MagicMock()  # type: ignore[attr-defined]
    fake.save = MagicMock()  # type: ignore[attr-defined]

    parent = sys.modules.get("mhkit")
    if parent is None:
        parent = types.ModuleType("mhkit")
        monkeypatch.setitem(sys.modules, "mhkit", parent)
    monkeypatch.setattr(parent, "dolfyn", fake, raising=False)
    monkeypatch.setitem(sys.modules, "mhkit.dolfyn", fake)
    return fake


def _job(tmp_path: Path, name: str, profile_index: int = 0, include_velds: bool = False) -> SaveJob:
    return SaveJob(
        file_item=FileItem(path=tmp_path / f"{name}.bin"),
        source_path=tmp_path / f"{name}.bin",
        profile_index=profile_index,
        output_path=tmp_path / "out" / f"{name}.nc",
        userdata=None,
        include_velds=include_velds,
    )


def test_save_worker_emits_per_job_progress(qtbot, tmp_path, fake_dolfyn):
    fake_ds = object()
    fake_dolfyn.read.return_value = fake_ds

    jobs = [_job(tmp_path, "a"), _job(tmp_path, "b")]
    worker = SaveWorker(jobs)

    progress: list[int] = []
    failures: list[SaveFailure] = []
    worker.file_saved.connect(lambda p: progress.append(p.index))
    worker.file_failed.connect(lambda f: failures.append(f))

    with qtbot.waitSignal(worker.all_done, timeout=5000):
        worker.start()
    worker.wait(2000)

    assert progress == [0, 1]
    assert failures == []
    assert fake_dolfyn.read.call_count == 2
    assert fake_dolfyn.save.call_count == 2


def test_save_worker_failure_emits_failure(qtbot, tmp_path, fake_dolfyn):
    fake_dolfyn.read.side_effect = RuntimeError("nope")

    jobs = [_job(tmp_path, "a")]
    worker = SaveWorker(jobs)

    failures: list[SaveFailure] = []
    worker.file_failed.connect(lambda f: failures.append(f))

    with qtbot.waitSignal(worker.all_done, timeout=5000):
        worker.start()
    worker.wait(2000)

    assert len(failures) == 1
    assert failures[0].index == 0
    assert "nope" in failures[0].error


def test_save_worker_handles_tuple_result_with_profile_index(qtbot, tmp_path, fake_dolfyn):
    profiles = (object(), object(), object())
    fake_dolfyn.read.return_value = profiles

    jobs = [_job(tmp_path, "multi", profile_index=2)]
    worker = SaveWorker(jobs)

    saved: list[SaveProgress] = []
    worker.file_saved.connect(lambda p: saved.append(p))

    with qtbot.waitSignal(worker.all_done, timeout=5000):
        worker.start()
    worker.wait(2000)

    assert len(saved) == 1
    # The dataset passed to dolfyn.save must be the selected profile.
    saved_ds = fake_dolfyn.save.call_args[0][0]
    assert saved_ds is profiles[2]


def test_save_worker_injects_velds_when_included(qtbot, tmp_path, fake_dolfyn, monkeypatch):
    fake_ds = object()
    injected_ds = object()
    fake_dolfyn.read.return_value = fake_ds

    inject_mock = MagicMock(return_value=injected_ds)
    monkeypatch.setattr(
        "mhkit_dolfyn_gui.services.export_pipeline.inject_derived_velocity", inject_mock
    )

    jobs = [_job(tmp_path, "a", include_velds=True)]
    worker = SaveWorker(jobs)

    with qtbot.waitSignal(worker.all_done, timeout=5000):
        worker.start()
    worker.wait(2000)

    inject_mock.assert_called_once_with(fake_ds)
    saved_ds = fake_dolfyn.save.call_args[0][0]
    assert saved_ds is injected_ds


def test_save_worker_skips_velds_injection_when_excluded(qtbot, tmp_path, fake_dolfyn, monkeypatch):
    fake_ds = object()
    fake_dolfyn.read.return_value = fake_ds

    inject_mock = MagicMock()
    monkeypatch.setattr(
        "mhkit_dolfyn_gui.services.export_pipeline.inject_derived_velocity", inject_mock
    )

    jobs = [_job(tmp_path, "a", include_velds=False)]
    worker = SaveWorker(jobs)

    with qtbot.waitSignal(worker.all_done, timeout=5000):
        worker.start()
    worker.wait(2000)

    inject_mock.assert_not_called()
    saved_ds = fake_dolfyn.save.call_args[0][0]
    assert saved_ds is fake_ds
