"""Pure analysis of a multi-file deployment.

``CombinedOverview`` should call :func:`analyze` and render the resulting
``DeploymentAnalysis`` — all dataset math lives here so it can be tested
without spinning up Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from typing import TYPE_CHECKING

from mhkit_dolfyn_gui.services.field_extractors import get_attr

if TYPE_CHECKING:
    from typing import Any

    from mhkit_dolfyn_gui.models.file_item import FileItem


def _attr_for(item: FileItem, *keys: str) -> str:
    """Read an attribute from the item's dataset or its cached snapshot.

    Lets deployment analysis keep working after the LRU cache has evicted
    the full Dataset — the snapshot's attrs dict carries the small bits
    needed for instrument-mismatch detection.
    """
    if item.dataset is not None:
        return get_attr(item.dataset, *keys)
    snap = item.summary_snapshot
    if snap is None:
        return "N/A"
    attrs: dict[str, Any] = snap.attrs
    for key in keys:
        val = attrs.get(key)
        if val is not None:
            return str(val)
    return "N/A"


@dataclass(frozen=True)
class CoverageRow:
    """Time-coverage entry for a single file in a deployment."""

    item: FileItem
    start: datetime | None
    end: datetime | None
    duration: timedelta | None


@dataclass(frozen=True)
class TimeGap:
    """A gap or overlap between two consecutive files."""

    before: FileItem
    after: FileItem
    delta: timedelta  # positive = gap, negative = overlap


@dataclass(frozen=True)
class InstrumentMismatch:
    """A per-attribute deviation from the reference (first) file."""

    item: FileItem
    attribute: str  # human-readable: "Instrument", "Coordinate system", "Sampling frequency"
    expected: str
    actual: str


@dataclass(frozen=True)
class DeploymentAnalysis:
    """Everything ``CombinedOverview`` needs to render. Pure data."""

    sorted_items: tuple[FileItem, ...]
    coverage: tuple[CoverageRow, ...]
    gaps: tuple[TimeGap, ...]
    mismatches: tuple[InstrumentMismatch, ...]


_EPOCH = datetime.min


def analyze(
    items: list[FileItem],
    gap_threshold_seconds: float,
) -> DeploymentAnalysis:
    """Compute a complete deployment analysis from loaded file items.

    Only items with a loaded dataset are considered. Items are sorted by
    ``start_time`` (items without a start time sort to the front, matching
    the previous behavior).
    """
    ready = [it for it in items if it.has_been_read]
    if not ready:
        return DeploymentAnalysis(sorted_items=(), coverage=(), gaps=(), mismatches=())

    sorted_items = sorted(ready, key=lambda it: it.start_time or _EPOCH)

    coverage = tuple(
        CoverageRow(
            item=it,
            start=it.start_time,
            end=it.end_time,
            duration=(it.end_time - it.start_time) if it.start_time and it.end_time else None,
        )
        for it in sorted_items
    )

    gaps = _detect_gaps(sorted_items, gap_threshold_seconds)
    mismatches = _detect_mismatches(sorted_items)

    return DeploymentAnalysis(
        sorted_items=tuple(sorted_items),
        coverage=coverage,
        gaps=gaps,
        mismatches=mismatches,
    )


def _detect_gaps(
    sorted_items: list[FileItem],
    gap_threshold_seconds: float,
) -> tuple[TimeGap, ...]:
    if len(sorted_items) < 2:
        return ()
    out: list[TimeGap] = []
    for a, b in pairwise(sorted_items):
        end_a = a.end_time
        start_b = b.start_time
        if end_a is None or start_b is None:
            continue
        delta = start_b - end_a
        secs = delta.total_seconds()
        if secs > gap_threshold_seconds or secs < -1:
            out.append(TimeGap(before=a, after=b, delta=delta))
    return tuple(out)


def _detect_mismatches(
    sorted_items: list[FileItem],
) -> tuple[InstrumentMismatch, ...]:
    if len(sorted_items) < 2:
        return ()
    ref = sorted_items[0]
    if not ref.has_been_read:
        return ()

    ref_inst = f"{_attr_for(ref, 'inst_make')} {_attr_for(ref, 'inst_model')}"
    ref_cs = _attr_for(ref, "coord_sys")
    ref_fs = _attr_for(ref, "fs")

    out: list[InstrumentMismatch] = []
    for it in sorted_items[1:]:
        if not it.has_been_read:
            continue
        inst = f"{_attr_for(it, 'inst_make')} {_attr_for(it, 'inst_model')}"
        if inst != ref_inst:
            out.append(
                InstrumentMismatch(item=it, attribute="Instrument", expected=ref_inst, actual=inst)
            )
        cs = _attr_for(it, "coord_sys")
        if cs != ref_cs:
            out.append(
                InstrumentMismatch(
                    item=it,
                    attribute="Coordinate system",
                    expected=ref_cs,
                    actual=cs,
                )
            )
        fs = _attr_for(it, "fs")
        if fs != ref_fs:
            out.append(
                InstrumentMismatch(
                    item=it,
                    attribute="Sampling frequency",
                    expected=f"{ref_fs} Hz",
                    actual=f"{fs} Hz",
                )
            )
    return tuple(out)
