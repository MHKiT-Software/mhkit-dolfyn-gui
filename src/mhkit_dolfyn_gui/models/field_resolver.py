"""Dot-notation DSL for resolving xarray Dataset fields.

Paths follow the pattern ``category.name[.operation[.args...]]``:
  - ``attr.<name>``                  — global dataset attribute
  - ``var.<name>.min/max/mean/std``  — variable statistic (auto-appends units)
  - ``var.<name>.nan_count/nan_pct`` — NaN info
  - ``var.<name>.shape/size/dtype``  — variable metadata
  - ``var.<name>.attr.<attr_name>``  — variable-level attribute
  - ``var.<name>.values.<start>.<count>`` — value preview slice
  - ``dim.<name>``                   — dimension size
  - ``coord.<name>.first/last``      — coordinate bounds
  - ``computed.<name>``              — delegates to FIELD_REGISTRY
  - ``file.name/path/extension``     — input file metadata
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import xarray as xr

    from mhkit_dolfyn_gui.models.file_item import FileItem

NA = "N/A"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_field(
    ds: xr.Dataset,
    path: str,
    file_item: FileItem | None = None,
) -> str:
    """Resolve a dot-notation *path* against *ds* (and optional *file_item*).

    Returns a human-readable string.  Any error yields ``"N/A"``.
    """
    try:
        parts = path.split(".")
        category = parts[0]
        resolver = _CATEGORY_RESOLVERS.get(category)
        if resolver is None:
            return NA
        return resolver(ds, parts[1:], file_item)
    except Exception:
        return NA


def resolve_combined_field(
    items: list[FileItem],
    path: str,
) -> str:
    """Resolve a field path in combined (multi-dataset) context.

    Paths starting with ``combined.`` are resolved against the full list of items.
    All other paths are resolved against the first item's dataset.
    """
    try:
        parts = path.split(".")
        if parts[0] == "combined":
            from mhkit_dolfyn_gui.services.field_extractors import COMBINED_FIELD_REGISTRY

            name = parts[1] if len(parts) > 1 else ""
            fn = COMBINED_FIELD_REGISTRY.get(name)
            return fn(items) if fn is not None else NA
        # Fall back to per-file resolution against the first dataset
        if items and items[0].dataset is not None:
            return resolve_field(items[0].dataset, path, items[0])
        return NA
    except Exception:
        return NA


def list_available_fields(
    ds: xr.Dataset,
    include_combined: bool = False,
) -> dict[str, list[str]]:
    """Return available field paths grouped by category for the UI picker."""
    from mhkit_dolfyn_gui.services.field_extractors import FIELD_REGISTRY

    groups: dict[str, list[str]] = {}

    # Attributes
    if ds.attrs:
        groups["attr"] = [f"attr.{k}" for k in sorted(ds.attrs)]

    # Variables
    var_paths: list[str] = []
    for name in sorted(str(n) for n in ds.data_vars):
        var_paths.extend(
            f"var.{name}.{stat}" for stat in ("min", "max", "mean", "std", "nan_count", "nan_pct")
        )
        var_paths.extend(f"var.{name}.{meta}" for meta in ("shape", "size", "dtype"))
    if var_paths:
        groups["var"] = var_paths

    # Dimensions
    if ds.dims:
        groups["dim"] = [f"dim.{d}" for d in sorted(str(d) for d in ds.dims)]

    # Coordinates
    coord_paths: list[str] = []
    for name in sorted(str(n) for n in ds.coords):
        coord_paths.append(f"coord.{name}.first")
        coord_paths.append(f"coord.{name}.last")
    if coord_paths:
        groups["coord"] = coord_paths

    # Computed
    groups["computed"] = [f"computed.{k}" for k in sorted(FIELD_REGISTRY)]

    # File (always available)
    groups["file"] = ["file.name", "file.path", "file.extension"]

    # Combined fields (multi-dataset aggregations)
    if include_combined:
        from mhkit_dolfyn_gui.services.field_extractors import COMBINED_FIELD_REGISTRY

        groups["combined"] = [f"combined.{k}" for k in sorted(COMBINED_FIELD_REGISTRY)]

    return groups


# ---------------------------------------------------------------------------
# Category resolvers
# ---------------------------------------------------------------------------


def _resolve_attr(
    ds: xr.Dataset,
    parts: list[str],
    _file_item: FileItem | None,
) -> str:
    if not parts:
        return NA
    name = ".".join(parts)  # allow dotted attr names
    val = ds.attrs.get(name)
    return str(val) if val is not None else NA


def _resolve_var(
    ds: xr.Dataset,
    parts: list[str],
    _file_item: FileItem | None,
) -> str:
    if len(parts) < 2:
        return NA
    var_name = parts[0]
    if var_name not in ds.data_vars:
        return NA
    var = ds[var_name]
    operation = parts[1]

    # Statistics — auto-append units when available
    stat_funcs = {
        "min": np.nanmin,
        "max": np.nanmax,
        "mean": np.nanmean,
        "std": np.nanstd,
    }
    if operation in stat_funcs:
        values = var.values
        result = stat_funcs[operation](values)
        text = f"{result:.6g}"
        units = var.attrs.get("units")
        if units:
            text += f" [{units}]"
        return text

    if operation == "nan_count":
        return str(int(np.isnan(var.values).sum()))

    if operation == "nan_pct":
        vals = var.values
        total = vals.size
        if total == 0:
            return NA
        pct = np.isnan(vals).sum() / total * 100
        return f"{pct:.1f}%"

    if operation == "shape":
        return str(var.shape)

    if operation == "size":
        return f"{var.size:,}"

    if operation == "dtype":
        return str(var.dtype)

    if operation == "attr" and len(parts) >= 3:
        attr_name = ".".join(parts[2:])
        val = var.attrs.get(attr_name)
        return str(val) if val is not None else NA

    if operation == "values" and len(parts) >= 4:
        start = int(parts[2])
        count = int(parts[3])
        flat = var.values.flat
        sliced = flat[start : start + count]
        return str(list(sliced))

    return NA


def _resolve_dim(
    ds: xr.Dataset,
    parts: list[str],
    _file_item: FileItem | None,
) -> str:
    if not parts:
        return NA
    name = parts[0]
    if name in ds.dims:
        return f"{ds.sizes[name]:,}"
    return NA


def _resolve_coord(
    ds: xr.Dataset,
    parts: list[str],
    _file_item: FileItem | None,
) -> str:
    if len(parts) < 2:
        return NA
    name, bound = parts[0], parts[1]
    if name not in ds.coords:
        return NA
    coord = ds.coords[name]
    values = coord.values
    if len(values) == 0:
        return NA

    raw = values[0] if bound == "first" else values[-1]

    # Format datetime-like coords via pandas
    if np.issubdtype(coord.dtype, np.datetime64):
        import pandas as pd

        return str(pd.Timestamp(raw))

    return str(raw)


def _resolve_computed(
    ds: xr.Dataset,
    parts: list[str],
    _file_item: FileItem | None,
) -> str:
    if not parts:
        return NA
    from mhkit_dolfyn_gui.services.field_extractors import FIELD_REGISTRY

    name = parts[0]
    fn = FIELD_REGISTRY.get(name)
    if fn is None:
        return NA
    return fn(ds)


def _resolve_file(
    _ds: xr.Dataset,
    parts: list[str],
    file_item: FileItem | None,
) -> str:
    if not parts or file_item is None:
        return NA
    prop = parts[0]
    if prop == "name":
        return file_item.path.name
    if prop == "path":
        return file_item.path.as_posix()
    if prop == "extension":
        return file_item.extension
    return NA


_CATEGORY_RESOLVERS = {
    "attr": _resolve_attr,
    "var": _resolve_var,
    "dim": _resolve_dim,
    "coord": _resolve_coord,
    "computed": _resolve_computed,
    "file": _resolve_file,
}
