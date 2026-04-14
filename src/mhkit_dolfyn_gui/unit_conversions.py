"""Human-friendly unit formatting helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import timedelta

_BYTE_UNITS = ("B", "KB", "MB", "GB", "TB")
_BYTES_PER_UNIT = 1024.0
_BYTES_PER_GB = 1024 * 1024 * 1024


def bytes_to_gb(b: int) -> float:
    """Convert a byte count to gigabytes."""
    return b / _BYTES_PER_GB


def gb_to_bytes(gb: float) -> int:
    """Convert gigabytes to a byte count (rounded to the nearest byte)."""
    return round(gb * _BYTES_PER_GB)


def format_duration(td: timedelta) -> str:
    """Format a timedelta as a human-readable string like '1d 4h 30m'."""
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return "N/A"
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def format_bytes(n: int) -> str:
    """Format a byte count as a human-readable string (e.g. ``1.5 MB``).

    Bytes are reported as integers; larger units use one decimal place.
    Sizes beyond the largest known unit (TB) are clamped to TB.
    """
    size = float(n)
    for unit in _BYTE_UNITS:
        if size < _BYTES_PER_UNIT or unit == _BYTE_UNITS[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= _BYTES_PER_UNIT
    # Unreachable: the loop always returns.
    return f"{size:.1f} {_BYTE_UNITS[-1]}"
