"""LRU cache of resident xarray datasets attached to FileItems.

The GUI may load hundreds of files but only a handful of datasets need to
stay materialized at once. ``DatasetCache`` tracks which ``FileItem``s
currently hold a dataset and evicts the least-recently-used ones when
either of two configured limits is exceeded.

Eviction releases the dataset references on the FileItem (so xarray and
the underlying numpy/HDF5 buffers can be garbage-collected) and resets
the item's status back to ``PENDING`` so the UI knows a re-read will be
needed before the data is shown again.

Items currently being read or saved are pinned and never evicted.
"""

from __future__ import annotations

import contextlib
import logging
from collections import OrderedDict
from typing import TYPE_CHECKING

from mhkit_dolfyn_gui.models.file_item import FileStatus

if TYPE_CHECKING:
    from mhkit_dolfyn_gui.models.file_item import FileItem

log = logging.getLogger(__name__)


def _estimate_bytes(item: FileItem) -> int:
    """Approximate resident size for ``item``'s primary + extra datasets."""
    total = 0
    for ds in item.all_datasets:
        # xarray.Dataset.nbytes is documented but be defensive: any
        # weird stub object should not crash the cache.
        with contextlib.suppress(Exception):
            total += int(ds.nbytes)
    return total


class DatasetCache:
    """LRU cache keyed by ``FileItem`` identity.

    The cache does not own the datasets — the FileItem still holds the
    references. The cache only tracks recency and triggers eviction by
    clearing those references on FileItems that fall out of the window.
    """

    def __init__(self, max_bytes: int, max_items: int) -> None:
        self._max_bytes = max_bytes
        self._max_items = max_items
        # id(item) → (item, nbytes). OrderedDict for O(1) LRU bookkeeping;
        # identity key avoids requiring FileItem to be hashable.
        self._entries: OrderedDict[int, tuple[FileItem, int]] = OrderedDict()
        self._total_bytes = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def put(self, item: FileItem) -> list[FileItem]:
        """Insert (or refresh) ``item`` and evict LRU entries until under limits.

        Returns the list of items that were evicted, so the caller can
        refresh sidebar status etc.
        """
        key = id(item)
        if key in self._entries:
            _, old_bytes = self._entries.pop(key)
            self._total_bytes -= old_bytes
        nbytes = _estimate_bytes(item)
        self._entries[key] = (item, nbytes)
        self._total_bytes += nbytes
        return self._evict_until_under_limits()

    def set_limits(self, max_bytes: int, max_items: int) -> list[FileItem]:
        """Replace the cache limits and immediately re-evict if needed.

        Called by the Preferences dialog when the user changes cache size.
        Returns any items evicted by the shrink so the caller can refresh
        sidebar status, mirroring the contract of :meth:`put`.
        """
        self._max_bytes = max_bytes
        self._max_items = max_items
        return self._evict_until_under_limits()

    def touch(self, item: FileItem) -> None:
        """Mark ``item`` as most-recently-used. No-op if not present."""
        key = id(item)
        if key in self._entries:
            self._entries.move_to_end(key)

    def evict(self, item: FileItem) -> None:
        """Forcibly evict ``item`` from the cache and drop its dataset refs."""
        key = id(item)
        if key not in self._entries:
            return
        _, nbytes = self._entries.pop(key)
        self._total_bytes -= nbytes
        self._release(item)

    def total_bytes(self) -> int:
        return self._total_bytes

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, item: object) -> bool:
        return id(item) in self._entries

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evict_until_under_limits(self) -> list[FileItem]:
        evicted: list[FileItem] = []
        while self._over_limit():
            victim = self._next_evictable()
            if victim is None:
                # All remaining items are pinned (READING/SAVING). Accept
                # the overshoot rather than block: the user will exceed
                # 2 GB temporarily during a large export, which is fine.
                log.warning(
                    "DatasetCache over limit (%d bytes / %d items) but no "
                    "evictable entries — all pinned by READING/SAVING",
                    self._total_bytes,
                    len(self._entries),
                )
                break
            key = id(victim)
            _, nbytes = self._entries.pop(key)
            self._total_bytes -= nbytes
            self._release(victim)
            evicted.append(victim)
        return evicted

    def _over_limit(self) -> bool:
        return self._total_bytes > self._max_bytes or len(self._entries) > self._max_items

    def _next_evictable(self) -> FileItem | None:
        """Return the LRU item that is not pinned, or None."""
        for item, _nbytes in self._entries.values():
            if item.status not in (FileStatus.READING, FileStatus.SAVING):
                return item
        return None

    @staticmethod
    def _release(item: FileItem) -> None:
        # Snapshot the lightweight summary fields *before* dropping the
        # dataset so combined views and the sidebar still have something
        # to display. The snapshot is a few hundred bytes regardless of
        # the original Dataset's size.
        item.build_summary_snapshot()
        item.dataset = None
        item.extra_datasets = ()
        item.status = FileStatus.CACHED
