"""velds computed velocity property extraction.

Wraps the ``ds.velds`` xarray accessor (registered by mhkit.dolfyn) so the
rest of the application can consume computed velocity properties without
knowing the accessor's internals.

Public API
----------
- ``VELDS_PROP_NAMES`` — ordered tuple of the always-available property names
- ``get_velds_dataarrays``    — extract float32 DataArrays from a dataset
- ``inject_velds_into_dataset`` — return a dataset copy with velds vars added
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import xarray as xr

# Ordered names used for display and injection.
VELDS_PROP_NAMES: tuple[str, ...] = (
    "u",
    "v",
    "w",
    "U_mag",
    "U_dir",
    "U_real",
    "U_imag",
)

# Internal extractor table — (name, callable(velds_accessor) -> DataArray).
# All extractors must return float32. U is complex64 so it is always split.
_EXTRACTORS: tuple[tuple[str, object], ...] = (
    ("u", lambda v: v.u.astype("float32")),
    ("v", lambda v: v.v.astype("float32")),
    ("w", lambda v: v.w.astype("float32")),
    ("U_mag", lambda v: v.U_mag),
    ("U_dir", lambda v: v.U_dir),
    ("U_real", lambda v: v.U.real.astype("float32")),
    ("U_imag", lambda v: v.U.imag.astype("float32")),
)

# Frame-aware long_name for u/v/w, keyed by ds.attrs["coord_sys"].
_UVW_LONG_NAMES: dict[str, dict[str, str]] = {
    "earth": {
        "u": "Eastward Velocity",
        "v": "Northward Velocity",
        "w": "Upward Velocity",
    },
    "inst": {
        "u": "X Velocity (instrument frame)",
        "v": "Y Velocity (instrument frame)",
        "w": "Z Velocity (instrument frame)",
    },
    "beam": {
        "u": "Beam 1 Velocity (along-beam)",
        "v": "Beam 2 Velocity (along-beam)",
        "w": "Beam 3 Velocity (along-beam)",
    },
    "principal": {
        "u": "Streamwise Velocity",
        "v": "Cross-stream Velocity",
        "w": "Vertical Velocity",
    },
}

# CF standard_name only applies to the earth (geographic) frame.
_UVW_STANDARD_NAMES: dict[str, str] = {
    "u": "eastward_sea_water_velocity",
    "v": "northward_sea_water_velocity",
    "w": "upward_sea_water_velocity",
}

_UVW_FALLBACK_INDEX: dict[str, int] = {"u": 1, "v": 2, "w": 3}

_DERIVED_COMMENT = "Derived from 'vel' via mhkit.dolfyn; not present in the raw source file."

_U_REAL_LONG_NAME = "Horizontal Velocity — Real/Eastward-equivalent Component"
_U_IMAG_LONG_NAME = "Horizontal Velocity — Imaginary/Northward-equivalent Component"
_U_COMPLEX_COMMENT = (
    "NetCDF cannot store complex values directly; this is the real/imaginary "
    "decomposition of the complex horizontal velocity U = u + v·j."
)


def _apply_velds_metadata(name: str, da: xr.DataArray, coord_sys: str) -> xr.DataArray:
    """Attach accurate, frame-aware attrs to a computed velds DataArray in place.

    Never raises — a metadata-setting bug must never break extraction.
    """
    try:
        if name in ("u", "v", "w"):
            frame_names = _UVW_LONG_NAMES.get(coord_sys)
            if frame_names:
                da.attrs["long_name"] = frame_names[name]
                if coord_sys == "earth":
                    da.attrs["standard_name"] = _UVW_STANDARD_NAMES[name]
            else:
                da.attrs["long_name"] = f"Velocity Component {_UVW_FALLBACK_INDEX[name]}"
        elif name == "U_real":
            da.attrs["long_name"] = _U_REAL_LONG_NAME
            da.attrs["comment"] = _U_COMPLEX_COMMENT
        elif name == "U_imag":
            da.attrs["long_name"] = _U_IMAG_LONG_NAME
            da.attrs["comment"] = _U_COMPLEX_COMMENT

        da.attrs.setdefault("comment", _DERIVED_COMMENT)
    except Exception:
        pass
    return da


def get_velds_dataarrays(ds: xr.Dataset) -> list[tuple[str, xr.DataArray]]:
    """Return (name, DataArray) pairs for all successfully computed velds properties.

    Silently skips any property that raises (e.g. missing ``vel`` variable or
    missing ``dir`` coordinate). All returned DataArrays are float32 and carry
    accurate, frame-aware ``long_name``/``standard_name``/``comment`` attrs.

    Never raises — returns an empty list on total failure.
    """
    try:
        accessor = ds.velds
    except Exception:
        return []

    coord_sys = ds.attrs.get("coord_sys", "")

    results: list[tuple[str, xr.DataArray]] = []
    for name, fn in _EXTRACTORS:
        try:
            da = fn(accessor)  # type: ignore[operator]
            da = _apply_velds_metadata(name, da, coord_sys)
            results.append((name, da))
        except Exception:
            pass
    return results


def inject_velds_into_dataset(ds: xr.Dataset) -> xr.Dataset:
    """Return a copy of *ds* with velds computed properties added as data variables.

    - Raw variable wins on name collision: any name already present in
      ``ds.data_vars`` is skipped and left unchanged.
    - Uses ``ds.assign(...)`` which always returns a new Dataset — the input
      is never mutated.
    - If no properties can be computed, returns ``ds.assign({})`` (a shallow
      copy with no new variables).
    """
    pairs = get_velds_dataarrays(ds)
    to_assign = {name: da for name, da in pairs if name not in ds.data_vars}
    return ds.assign(to_assign)
