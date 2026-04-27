"""Data model for a tracked file in the conversion pipeline."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    import xarray as xr

from mhkit_dolfyn_gui.services.field_extractors import get_summary_fields


class FileStatus(enum.Enum):
    """Status of a file in the read/save pipeline."""

    PENDING = "pending"
    READING = "reading"
    READY = "ready"
    # File was successfully read at least once but its dataset has been
    # evicted from the in-memory LRU cache to free RAM. A lightweight
    # ``FileSummary`` snapshot is retained on the FileItem so combined
    # summaries and per-file metadata still work; clicking the file
    # silently re-reads it.
    CACHED = "cached"
    ERROR = "error"
    SAVING = "saving"
    SAVED = "saved"


@dataclass(frozen=True)
class FileSummary:
    """Lightweight snapshot of the bits of a Dataset the GUI needs to
    keep showing after the full Dataset has been evicted from the cache.

    Holds only Python primitives + a small attrs dict, so it costs ~bytes
    per file regardless of how big the original Dataset was.
    """

    start_time: datetime | None
    end_time: datetime | None
    n_ensembles: int  # primary dataset's time-dimension size
    profile_time_sizes: tuple[int, ...]  # per-profile time sizes
    n_profiles: int
    attrs: dict[str, Any]  # snapshot of primary ds.attrs
    summary_dict: dict[str, str]  # rendered summary fields (label → value)


@dataclass
class FileItem:
    """Represents a single ADCP/ADV file being processed.

    Holds the file path, current status, the loaded xarray Dataset (once read),
    and any error message if reading failed.
    """

    path: Path
    status: FileStatus = FileStatus.PENDING
    dataset: xr.Dataset | None = field(default=None, repr=False)
    # Additional datasets returned by dolfyn for multi-profile files (e.g.
    # Signature "Dual Profile" .ad2cp). The first profile lives in `dataset`;
    # any extras are stored here so the rest of the UI can keep treating
    # `dataset` as the primary view.
    extra_datasets: tuple[xr.Dataset, ...] = field(default=(), repr=False)
    error: str | None = None
    checked: bool = True
    # User opt-out: if True, do not apply any userdata.json on read.
    userdata_skip: bool = False
    # Path of the userdata.json that was applied during the last read (or
    # None). Set by the read worker; for display only.
    userdata_source: Path | None = None
    # Lightweight snapshot taken right before the dataset is evicted from
    # the cache (or just after a successful read). Lets combined summaries
    # and per-file metadata keep working without holding the full Dataset
    # in RAM.
    summary_snapshot: FileSummary | None = field(default=None, repr=False)

    @property
    def has_been_read(self) -> bool:
        """True if the file was successfully read at least once.

        Use this in preference to ``self.dataset is not None`` whenever
        the question is "do we know what's in this file?" rather than
        "is the full Dataset currently resident in memory?".
        """
        return self.dataset is not None or self.summary_snapshot is not None

    @property
    def all_datasets(self) -> tuple[xr.Dataset, ...]:
        """Every dataset associated with this file (primary + extras)."""
        if self.dataset is None:
            return ()
        return (self.dataset, *self.extra_datasets)

    @property
    def profile_time_sizes(self) -> tuple[int, ...]:
        """Per-profile time-dimension sizes (from dataset or snapshot)."""
        if self.dataset is not None:
            return tuple(int(ds.sizes.get("time", 0)) for ds in self.all_datasets)
        if self.summary_snapshot is not None:
            return self.summary_snapshot.profile_time_sizes
        return ()

    @property
    def filename(self) -> str:
        """Original filename without extension."""
        return self.path.stem

    @property
    def extension(self) -> str:
        """File extension (lowercase, with dot)."""
        return self.path.suffix.lower()

    @property
    def summary(self) -> dict[str, str]:
        """Extract summary statistics from the loaded dataset.

        Returns a dict of {label: value} driven by ``get_summary_fields()``,
        Falls back to the cached snapshot when the dataset has been
        evicted; returns an empty dict if neither is available.
        """
        if self.dataset is not None:
            result: dict[str, str] = {}
            for label, extractor in get_summary_fields(self.dataset):
                try:
                    result[label] = extractor(self.dataset)
                except Exception:
                    result[label] = "N/A"
            return result
        if self.summary_snapshot is not None:
            return dict(self.summary_snapshot.summary_dict)
        return {}

    @property
    def start_time(self) -> datetime | None:
        """Start time from the dataset's time coordinate (or snapshot)."""
        bound = self._get_time_bound(first=True)
        if bound is not None:
            return bound
        return self.summary_snapshot.start_time if self.summary_snapshot else None

    @property
    def end_time(self) -> datetime | None:
        """End time from the dataset's time coordinate (or snapshot)."""
        bound = self._get_time_bound(first=False)
        if bound is not None:
            return bound
        return self.summary_snapshot.end_time if self.summary_snapshot else None

    def _get_time_bound(self, *, first: bool) -> datetime | None:
        if self.dataset is None:
            return None
        if "time" not in self.dataset.coords:
            return None
        times = self.dataset.coords["time"].values
        if len(times) == 0:
            return None
        import pandas as pd

        ts = pd.Timestamp(times[0] if first else times[-1])
        # Replace nanoseconds with 0 to avoid UserWarning from to_pydatetime()
        return ts.floor("us").to_pydatetime()  # pyright: ignore[reportReturnType] — NaT impossible: empty-array check above

    def build_summary_snapshot(self) -> FileSummary | None:
        """Capture a lightweight snapshot of the currently-loaded dataset.

        Returns ``None`` if no dataset is loaded. The snapshot is stored
        on the FileItem and returned for the caller's convenience.
        """
        if self.dataset is None:
            return None
        # Capture summary fields *while* the dataset is still resident.
        snap = FileSummary(
            start_time=self._get_time_bound(first=True),
            end_time=self._get_time_bound(first=False),
            n_ensembles=int(self.dataset.sizes.get("time", 0)),
            profile_time_sizes=tuple(int(ds.sizes.get("time", 0)) for ds in self.all_datasets),
            n_profiles=len(self.all_datasets),
            attrs=dict(self.dataset.attrs),
            summary_dict=self.summary,
        )
        self.summary_snapshot = snap
        return snap

    def format_for_list(self) -> str:
        """Format for display in the file list widget."""
        status_icons: dict[FileStatus, str] = {
            FileStatus.PENDING: "[ ]",
            FileStatus.READING: "[...]",
            FileStatus.READY: "[ok]",
            FileStatus.ERROR: "[X]",
            FileStatus.SAVING: "[...]",
            FileStatus.SAVED: "[ok]",
        }
        icon = status_icons.get(self.status, "[ ]")
        return f"{icon} {self.path.name}"
