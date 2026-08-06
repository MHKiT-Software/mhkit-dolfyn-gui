"""Dataset field extractors and field registries.

Pure functions that pull human-readable values from ``xr.Dataset`` objects (or
lists of ``FileItem``s for combined/multi-file views).  No Qt dependency.

Public API
----------
- ``get_attr``               — look up one of several attribute keys, first-wins
- ``get_summary_fields``     — instrument-aware list of (label, extractor) pairs
- ``FIELD_REGISTRY``         — maps ``computed.<name>`` DSL paths to extractors
- ``COMBINED_FIELD_REGISTRY``— maps ``combined.<name>`` DSL paths to aggregators
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mhkit_dolfyn_gui.unit_conversions import format_duration

if TYPE_CHECKING:
    from collections.abc import Callable

    import xarray as xr

    from mhkit_dolfyn_gui.models.file_item import FileItem


# ---------------------------------------------------------------------------
# Attribute helpers
# ---------------------------------------------------------------------------


def get_attr(ds: xr.Dataset, *keys: str) -> str:
    """Try multiple attribute keys; return the first found value or 'N/A'."""
    for key in keys:
        val = ds.attrs.get(key)
        if val is not None:
            return str(val)
    return "N/A"


# ---------------------------------------------------------------------------
# Single-dataset extractors
# ---------------------------------------------------------------------------


def _extract_instrument(ds: xr.Dataset) -> str:
    make = get_attr(ds, "inst_make")
    model = get_attr(ds, "inst_model")
    inst_type = get_attr(ds, "inst_type")
    parts = [p for p in [make, model] if p != "N/A"]
    if not parts:
        return inst_type
    return " ".join(parts)


def _extract_time_range(ds: xr.Dataset) -> tuple[Any, Any]:
    """Return (start, end) as pandas Timestamps or None."""
    import pandas as pd

    if "time" in ds.coords:
        times = ds.coords["time"].values
        if len(times) > 0:
            return pd.Timestamp(times[0]), pd.Timestamp(times[-1])
    return None, None


def _extract_start(ds: xr.Dataset) -> str:
    start, _ = _extract_time_range(ds)
    return str(start) if start is not None else "N/A"


def _extract_end(ds: xr.Dataset) -> str:
    _, end = _extract_time_range(ds)
    return str(end) if end is not None else "N/A"


def _extract_duration(ds: xr.Dataset) -> str:
    start, end = _extract_time_range(ds)
    if start is not None and end is not None:
        return format_duration(end - start)
    return "N/A"


def _extract_ensembles(ds: xr.Dataset) -> str:
    if "time" in ds.dims:
        return f"{ds.sizes['time']:,}"
    return "N/A"


def _extract_bins_beams(ds: xr.Dataset) -> str:
    n_bins = get_attr(ds, "n_bins")
    n_beams = get_attr(ds, "n_beams")
    if n_bins != "N/A" or n_beams != "N/A":
        return f"{n_bins} / {n_beams}"
    bins = ds.sizes.get("range", "N/A")
    beams = ds.sizes.get("beam", "N/A")
    return f"{bins} / {beams}"


def _detect_inst_type(ds: xr.Dataset) -> str:
    """Detect instrument type from dataset attributes."""
    return str(ds.attrs.get("inst_type", "")).upper()


# ---------------------------------------------------------------------------
# Summary field tables
# ---------------------------------------------------------------------------

# Base fields shown for all instruments
_BASE_FIELDS: list[tuple[str, Any]] = [
    ("Instrument", _extract_instrument),
    ("Serial", lambda ds: get_attr(ds, "serial_number", "serialnum")),
    ("Coord System", lambda ds: get_attr(ds, "coord_sys")),
    ("Sampling Freq", lambda ds: f"{get_attr(ds, 'fs')} Hz"),
    ("Start", _extract_start),
    ("End", _extract_end),
    ("Duration", _extract_duration),
    ("Ensembles", _extract_ensembles),
]

# Fields only shown for ADCPs (not ADVs)
_ADCP_ONLY_FIELDS: list[tuple[str, Any]] = [
    ("Bins / Beams", _extract_bins_beams),
]


def get_summary_fields(ds: xr.Dataset) -> list[tuple[str, Any]]:
    """Return the appropriate summary fields for the given dataset's instrument type."""
    inst_type = _detect_inst_type(ds)
    if inst_type == "ADV":
        return list(_BASE_FIELDS)
    return list(_BASE_FIELDS + _ADCP_ONLY_FIELDS)


# ---------------------------------------------------------------------------
# Field registry (computed.<name> DSL paths)
# ---------------------------------------------------------------------------

# Registry mapping computed field names to extractor functions.
# Used by the field resolver DSL for ``computed.<name>`` paths.
FIELD_REGISTRY: dict[str, Any] = {
    "instrument": _extract_instrument,
    "serial": lambda ds: get_attr(ds, "serial_number", "serialnum"),
    "coord_sys": lambda ds: get_attr(ds, "coord_sys"),
    "sampling_freq": lambda ds: f"{get_attr(ds, 'fs')} Hz",
    "start": _extract_start,
    "end": _extract_end,
    "duration": _extract_duration,
    "ensembles": _extract_ensembles,
    "bins_beams": _extract_bins_beams,
}


# ---------------------------------------------------------------------------
# Combined (multi-dataset) field extractors
# ---------------------------------------------------------------------------


def _combined_files_loaded(items: list[FileItem]) -> str:
    return str(len(items))


def _combined_earliest_start(items: list[FileItem]) -> str:
    starts = [it.start_time for it in items if it.start_time is not None]
    return str(min(starts)) if starts else "N/A"


def _combined_latest_end(items: list[FileItem]) -> str:
    ends = [it.end_time for it in items if it.end_time is not None]
    return str(max(ends)) if ends else "N/A"


def _combined_total_duration(items: list[FileItem]) -> str:
    starts = [it.start_time for it in items if it.start_time is not None]
    ends = [it.end_time for it in items if it.end_time is not None]
    if starts and ends:
        return format_duration(max(ends) - min(starts))
    return "N/A"


def _combined_total_ensembles(items: list[FileItem]) -> str:
    total = 0
    for it in items:
        if it.dataset is not None:
            total += int(it.dataset.sizes.get("time", 0))
        elif it.summary_snapshot is not None:
            total += it.summary_snapshot.n_ensembles
    return f"{total:,}"


# Registry for ``combined.<name>`` paths.
# Each function receives a list of FileItems (with loaded datasets).
COMBINED_FIELD_REGISTRY: dict[str, Callable[[list[FileItem]], str]] = {
    "files_loaded": _combined_files_loaded,
    "earliest_start": _combined_earliest_start,
    "latest_end": _combined_latest_end,
    "total_duration": _combined_total_duration,
    "total_ensembles": _combined_total_ensembles,
}
