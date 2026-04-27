"""Tests for the LRU DatasetCache."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from mhkit_dolfyn_gui.models.file_item import FileItem, FileStatus
from mhkit_dolfyn_gui.services.dataset_cache import DatasetCache


def _make_dataset(n_elements: int) -> xr.Dataset:
    """Build a real xarray Dataset of ``n_elements`` float64 samples."""
    n = max(1, n_elements)
    times = np.datetime64("2024-01-01T00:00:00") + np.arange(n) * np.timedelta64(1, "s")
    return xr.Dataset(
        {"v": (["time"], np.zeros(n, dtype=np.float64))},
        coords={"time": times},
        attrs={"inst_type": "ADV"},
    )


def _make_item(name: str, n_elements: int = 10, status: FileStatus = FileStatus.READY) -> FileItem:
    item = FileItem(path=Path(f"/tmp/{name}"))
    item.dataset = _make_dataset(n_elements)
    item.status = status
    return item


def test_byte_limit_evicts_lru() -> None:
    a = _make_item("a", n_elements=100)
    b = _make_item("b", n_elements=100)
    c = _make_item("c", n_elements=100)
    one = a.dataset.nbytes  # type: ignore[union-attr]
    # Cap at exactly two of these datasets so adding the third forces eviction.
    cache = DatasetCache(max_bytes=int(one * 2.5), max_items=100)

    assert cache.put(a) == []
    assert cache.put(b) == []
    evicted = cache.put(c)  # third one pushes us over

    assert evicted == [a]  # LRU first
    assert a.dataset is None
    assert a.status == FileStatus.CACHED
    assert a.summary_snapshot is not None  # snapshot retained for combined views
    assert b.dataset is not None
    assert c.dataset is not None


def test_item_limit_evicts_lru() -> None:
    cache = DatasetCache(max_bytes=10**12, max_items=2)
    a = _make_item("a", 1)
    b = _make_item("b", 1)
    c = _make_item("c", 1)

    cache.put(a)
    cache.put(b)
    evicted = cache.put(c)

    assert evicted == [a]
    assert len(cache) == 2


def test_reading_and_saving_items_are_pinned() -> None:
    cache = DatasetCache(max_bytes=100, max_items=100)
    pinned = _make_item("pinned", 200, status=FileStatus.READING)
    cache.put(pinned)
    # Over limit, but only entry is pinned → no eviction, warning logged.
    assert pinned.dataset is not None
    assert pinned.status == FileStatus.READING

    saving = _make_item("saving", 200, status=FileStatus.SAVING)
    cache.put(saving)
    assert saving.dataset is not None


def test_touch_reorders_lru() -> None:
    cache = DatasetCache(max_bytes=10**12, max_items=2)
    a = _make_item("a", 1)
    b = _make_item("b", 1)
    cache.put(a)
    cache.put(b)
    cache.touch(a)  # a is now most-recently-used

    c = _make_item("c", 1)
    evicted = cache.put(c)
    assert evicted == [b]
    assert a.dataset is not None


def test_explicit_evict() -> None:
    cache = DatasetCache(max_bytes=10**12, max_items=10)
    a = _make_item("a", 5)
    cache.put(a)
    cache.evict(a)
    assert a.dataset is None
    assert len(cache) == 0
    assert cache.total_bytes() == 0


def test_set_limits_shrink_evicts_lru() -> None:
    """Shrinking the item cap below current size evicts LRU until under."""
    cache = DatasetCache(max_bytes=10**12, max_items=5)
    a = _make_item("a", 1)
    b = _make_item("b", 1)
    c = _make_item("c", 1)
    cache.put(a)
    cache.put(b)
    cache.put(c)

    evicted = cache.set_limits(max_bytes=10**12, max_items=2)

    assert evicted == [a]  # LRU first
    assert len(cache) == 2
    assert a.dataset is None
    assert a.status == FileStatus.CACHED
    assert b.dataset is not None
    assert c.dataset is not None


def test_set_limits_shrink_bytes_evicts() -> None:
    """Shrinking the byte cap below current usage evicts LRU."""
    a = _make_item("a", 100)
    b = _make_item("b", 100)
    one = a.dataset.nbytes  # type: ignore[union-attr]

    cache = DatasetCache(max_bytes=int(one * 3), max_items=100)
    cache.put(a)
    cache.put(b)

    evicted = cache.set_limits(max_bytes=int(one * 1.5), max_items=100)

    assert evicted == [a]
    assert b.dataset is not None


def test_set_limits_grow_does_not_evict() -> None:
    """Growing the limits never evicts."""
    cache = DatasetCache(max_bytes=10**6, max_items=2)
    a = _make_item("a", 1)
    b = _make_item("b", 1)
    cache.put(a)
    cache.put(b)

    evicted = cache.set_limits(max_bytes=10**12, max_items=10)
    assert evicted == []
    assert len(cache) == 2
