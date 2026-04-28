"""Human-readable string formatting helpers for displaying data in the UI."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

# Map numpy dtype kinds to human-readable names
_DTYPE_NAMES: dict[str, str] = {
    "f": "Decimal",
    "i": "Integer",
    "u": "Unsigned integer",
    "b": "Boolean",
    "U": "Text",
    "S": "Bytes",
    "M": "Datetime",
    "m": "Timedelta",
    "O": "Object",
}


def truncate(value: object, max_len: int = 100) -> str:
    """Truncate long values to *max_len* characters for display."""
    text = str(value)
    if len(text) > max_len:
        return text[:max_len] + "…"
    return text


def human_dtype(dtype: np.dtype) -> str:
    """Convert a numpy dtype to a human-readable name (e.g. ``float32`` → ``Decimal``)."""
    return _DTYPE_NAMES.get(dtype.kind, str(dtype))


def human_shape(dims: tuple[str, ...], shape: tuple[int, ...]) -> str:
    """Format array shape as ``'N time x M range'`` instead of raw tuples.

    Returns ``'scalar'`` when there are no dimensions.
    """
    if not dims:
        return "scalar"
    return " x ".join(f"{size:,} {dim}" for dim, size in zip(dims, shape, strict=True))
