"""Portable read -> process -> save pipeline shared by the GUI and generated scripts.

This module is the **single source of truth** for the per-file export body:
reading a raw instrument file, selecting a profile, deriving velocity fields via
mhkit.dolfyn's ``velds`` accessor, and saving to NetCDF.

- The GUI's :class:`~mhkit_dolfyn_gui.workers.save_worker.SaveWorker` imports and
  calls these functions directly at runtime.
- :mod:`~mhkit_dolfyn_gui.services.code_generator` embeds this module's *verbatim
  source text* into the standalone script it generates, so the generated script
  runs exactly the same code — no hand-maintained copy, no drift.

Embed-safety rules (do not break these — they keep the source droppable into a
generated script mid-file):

- **No** ``from __future__ import annotations``. A future statement is only legal
  at the very top of a module; embedded mid-script it is a ``SyntaxError``.
  Annotations that reference ``xarray`` are therefore written as *strings* so they
  are never evaluated at runtime.
- **No top-level third-party imports.** ``mhkit.dolfyn`` and ``pathlib`` are
  imported lazily inside :func:`process_one_file`. Only stdlib ``typing`` is
  imported at module scope (harmless, and inert when embedded).
- **No** ``mhkit_dolfyn_gui`` imports — the generated script must run without this
  package installed.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import xarray as xr

# Ordered names used for display and injection.
VELDS_PROP_NAMES = (
    "u",
    "v",
    "w",
    "U_mag",
    "U_dir",
    "U_real",
    "U_imag",
)

# Internal extractor table -- (name, callable(velds_accessor) -> DataArray).
# All extractors must return float32. U is complex64 so it is always split.
_EXTRACTORS = (
    ("u", lambda v: v.u.astype("float32")),
    ("v", lambda v: v.v.astype("float32")),
    ("w", lambda v: v.w.astype("float32")),
    ("U_mag", lambda v: v.U_mag),
    ("U_dir", lambda v: v.U_dir),
    ("U_real", lambda v: v.U.real.astype("float32")),
    ("U_imag", lambda v: v.U.imag.astype("float32")),
)

# Frame-aware long_name for u/v/w, keyed by ds.attrs["coord_sys"].
_UVW_LONG_NAMES = {
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
_UVW_STANDARD_NAMES = {
    "u": "eastward_sea_water_velocity",
    "v": "northward_sea_water_velocity",
    "w": "upward_sea_water_velocity",
}

_UVW_FALLBACK_INDEX = {"u": 1, "v": 2, "w": 3}

_DERIVED_COMMENT = "Derived from 'vel' via mhkit.dolfyn; not present in the raw source file."

_U_REAL_LONG_NAME = "Horizontal Velocity — Real/Eastward-equivalent Component"
_U_IMAG_LONG_NAME = "Horizontal Velocity — Imaginary/Northward-equivalent Component"
_U_COMPLEX_COMMENT = (
    "NetCDF cannot store complex values directly; this is the real/imaginary "
    "decomposition of the complex horizontal velocity U = u + v·j."
)


def _apply_velds_metadata(name: str, da: "xr.DataArray", coord_sys: str) -> "xr.DataArray":
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


def derived_velocity_pairs(ds: "xr.Dataset") -> "list[tuple[str, xr.DataArray]]":
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

    results = []
    for name, fn in _EXTRACTORS:
        try:
            da = fn(accessor)
            da = _apply_velds_metadata(name, da, coord_sys)
            results.append((name, da))
        except Exception:
            pass
    return results


def inject_derived_velocity(ds: "xr.Dataset") -> "xr.Dataset":
    """Return a copy of *ds* with velds computed properties added as data variables.

    - Raw variable wins on name collision: any name already present in
      ``ds.data_vars`` is skipped and left unchanged.
    - Uses ``ds.assign(...)`` which always returns a new Dataset — the input
      is never mutated.
    - If no properties can be computed, returns ``ds.assign({})`` (a shallow
      copy with no new variables).
    """
    pairs = derived_velocity_pairs(ds)
    to_assign = {name: da for name, da in pairs if name not in ds.data_vars}
    return ds.assign(to_assign)


def process_one_file(
    source_path: "Path | str",
    output_path: "Path | str",
    profile_index: int = 0,
    userdata: "dict | None" = None,
    include_velds: bool = True,
) -> "Path":
    """Read one raw file, optionally derive velocity fields, and save to NetCDF.

    - ``profile_index`` selects which profile to keep when ``dolfyn.read``
      returns a tuple for multi-profile instruments.
    - ``userdata`` is passed straight to ``dolfyn.read`` when not None
      (``dict`` of inline metadata, a path, or ``False`` to suppress loading).
    - ``include_velds`` gates :func:`inject_derived_velocity`.

    Returns the output path. Does not print or log — callers report progress.
    Only one dataset is held at a time, so peak memory stays bounded.
    """
    from pathlib import Path

    import mhkit.dolfyn as dolfyn

    kwargs = {"userdata": userdata} if userdata is not None else {}
    # dolfyn's stub types userdata as bool, but it also accepts a dict/path.
    result = dolfyn.read(str(source_path), **kwargs)  # type: ignore[arg-type]
    ds = result[profile_index] if isinstance(result, tuple) else result
    if include_velds:
        ds = inject_derived_velocity(ds)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dolfyn.save(ds, str(output_path))
    return output_path
