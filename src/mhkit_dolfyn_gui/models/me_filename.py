"""ME Data Pipeline filename builder.

Format::

    (location_id).(dataset_name)[-qualifier][-temporal].(data_level).(date).(time).(ext)

Per the ME Data Pipeline spec §8.1, processed NetCDF outputs use dots and
dashes as reserved delimiters. This module is a pure (no-Qt) implementation
of the builder, validators, and the fs-resolution helper; the export widget
collects user fields and calls into here.

``ext`` is always ``nc``.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from math import floor, isfinite, log10
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from datetime import datetime

# ME spec mandates .nc for these outputs.
ME_EXTENSION = "nc"

# Valid ME data_level codes per https://github.com/tsdat/data_standards/blob/main/ME_DataStandards.pdf
ME_DATA_LEVELS: tuple[str, ...] = ("00", "a1", "b1")

# ``location_id``/``dataset_name``/``qualifier`` may not use either delimiter
# the filename scheme reserves for itself.
_RESERVED_CHARS = frozenset(".-")

# Variance threshold above which the median-Δt fs estimate earns a warning.
_VARIANCE_WARN_PCT = 5.0


@dataclass(frozen=True)
class MENamingFields:
    """User-entered fields for ME Data Pipeline naming.

    ``temporal_override`` is used verbatim when non-empty; otherwise the
    caller auto-detects from the dataset (see :func:`format_temporal`).
    ``data_level`` of empty string means "omit" — the spec lists it as
    mandatory but we let the user opt out explicitly.
    """

    location_id: str
    dataset_name: str
    qualifier: str = ""
    data_level: str = "a1"
    include_temporal: bool = True
    temporal_override: str = ""


@dataclass(frozen=True)
class TemporalResolution:
    """Result of resolving sampling frequency for a dataset.

    ``source`` is ``"attrs"`` (fs attribute present), ``"median_dt"`` (fell
    back to the time-coordinate median), or ``"none"`` (could not determine).
    ``variance_pct`` is only populated for ``"median_dt"``.
    """

    fs_hz: float | None
    source: str
    variance_pct: float | None = None
    warning: str | None = None


def _sig_figs(value: float, digits: int = 3) -> str:
    """Render ``value`` with ``digits`` significant figures, trailing zeros stripped."""
    if not isfinite(value) or value == 0:
        return "0"
    decimals = digits - 1 - floor(log10(abs(value)))
    if decimals < 0:
        decimals = 0
    text = f"{value:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_temporal(fs_hz: float) -> str:
    """Convert a sampling frequency in Hz to an ME temporal string.

    ``fs >= 1``: emitted as ``{value}hz`` (e.g. ``250hz``, ``1.25hz``).
    ``fs < 1``: period ``T = 1/fs`` rendered in the coarsest unit that
    keeps the value in ``[1, threshold)``:

    * seconds (``s``) if ``T < 60``
    * minutes (``m``) if ``T < 3600``
    * hours   (``h``) if ``T < 86400``
    * days    (``d``) if ``T < 2592000`` (30 days)
    * months  (``mo``) if ``T < 31536000`` (365 days)
    * years   (``yr``) otherwise

    Values are rendered with 3 significant figures.
    """
    if not isfinite(fs_hz) or fs_hz <= 0:
        raise ValueError(f"fs_hz must be a positive finite number, got {fs_hz!r}")

    if fs_hz >= 1:
        return f"{_sig_figs(fs_hz)}hz"

    period_s = 1.0 / fs_hz
    for threshold, divisor, unit in (
        (60.0, 1.0, "s"),
        (3600.0, 60.0, "m"),
        (86400.0, 3600.0, "h"),
        (2592000.0, 86400.0, "d"),
        (31536000.0, 2592000.0, "mo"),
    ):
        if period_s < threshold:
            return f"{_sig_figs(period_s / divisor)}{unit}"
    return f"{_sig_figs(period_s / 31536000.0)}yr"


def validate_me_fields(fields: MENamingFields) -> list[str]:
    """Hard errors that must block export.

    Returns a list of human-readable error messages; empty list means valid.
    """
    errors: list[str] = []

    if not fields.location_id.strip():
        errors.append("location_id is required")
    elif any(c in _RESERVED_CHARS for c in fields.location_id):
        errors.append("location_id cannot contain '.' or '-'")

    if not fields.dataset_name.strip():
        errors.append("dataset_name is required")
    elif any(c in _RESERVED_CHARS for c in fields.dataset_name):
        errors.append("dataset_name cannot contain '.' or '-'")

    if fields.qualifier and any(c in _RESERVED_CHARS for c in fields.qualifier):
        errors.append("qualifier cannot contain '.' or '-'")

    if fields.data_level and fields.data_level not in ME_DATA_LEVELS:
        errors.append(f"data_level must be one of {', '.join(ME_DATA_LEVELS)} or empty")

    if fields.include_temporal and fields.temporal_override:
        if any(c in _RESERVED_CHARS for c in fields.temporal_override):
            errors.append("temporal cannot contain '.' or '-'")

    return errors


def warn_me_fields(fields: MENamingFields) -> list[str]:
    """Soft warnings — surface to the user but allow export.

    Per spec, ``dataset_name`` and ``qualifier`` should not end in a digit
    because it makes temporal parsing ambiguous. We only warn so the user
    can override.
    """
    warnings: list[str] = []
    if fields.dataset_name and fields.dataset_name[-1].isdigit():
        warnings.append("dataset_name ends in a digit (spec §8.1 recommends against)")
    if fields.qualifier and fields.qualifier[-1].isdigit():
        warnings.append("qualifier ends in a digit (spec §8.1 recommends against)")
    return warnings


def build_me_filename(
    fields: MENamingFields,
    *,
    temporal: str,
    start_dt: datetime,
    profile_suffix: str = "",
) -> str:
    """Assemble a filename per the ME Data Pipeline §8.1 format.

    Parameters
    ----------
    fields
        User-entered fields.
    temporal
        Pre-formatted temporal string (e.g. ``"250hz"``, ``"30s"``). Ignored
        when ``fields.include_temporal`` is False or the string is empty.
    start_dt
        The start time of the first data point, already in the target time
        zone (typically UTC — the caller applies any offset).
    profile_suffix
        Optional suffix for multi-profile files. Appended to ``qualifier``
        as ``qualifier_profile_<N>``; replaces it when ``qualifier`` is empty.
        Underscores are the only practical way to disambiguate profiles
        within the qualifier slot.
    """
    parts: list[str] = [fields.location_id]

    # Second block: dataset_name[-qualifier][-temporal]
    second = fields.dataset_name

    qualifier = fields.qualifier
    if profile_suffix:
        qualifier = f"{qualifier}_{profile_suffix}" if qualifier else profile_suffix
    if qualifier:
        second = f"{second}-{qualifier}"

    if fields.include_temporal and temporal:
        second = f"{second}-{temporal}"

    parts.append(second)

    if fields.data_level:
        parts.append(fields.data_level)

    parts.append(start_dt.strftime("%Y%m%d"))
    parts.append(start_dt.strftime("%H%M%S"))
    parts.append(ME_EXTENSION)

    return ".".join(parts)


def resolve_fs(
    attrs_fs: float | None,
    time_values: np.ndarray | None,
) -> TemporalResolution:
    """Resolve sampling frequency from attrs (preferred) or time coord.

    Primary source is ``attrs_fs`` (the dataset's ``fs`` global attribute).
    Fallback is the median of ``np.diff(time_values)``; if the spread of
    deltas is large we still return the estimate but attach a warning so
    the UI can display it.
    """
    if attrs_fs is not None and attrs_fs > 0:
        return TemporalResolution(fs_hz=float(attrs_fs), source="attrs")

    if time_values is None or len(time_values) < 2:
        return TemporalResolution(
            fs_hz=None,
            source="none",
            warning="Cannot resolve sampling frequency: no fs attr and <2 timestamps",
        )

    diffs = np.diff(time_values)
    if diffs.dtype.kind == "m":
        # timedelta64 — convert to float seconds
        deltas_s = diffs.astype("timedelta64[ns]").astype(np.float64) / 1e9
    else:
        # Fallback for object arrays of Python datetimes.
        deltas_s = np.array(
            [float((b - a).total_seconds()) for a, b in pairwise(time_values)],
            dtype=np.float64,
        )

    positive = deltas_s[deltas_s > 0]
    if positive.size == 0:
        return TemporalResolution(
            fs_hz=None,
            source="none",
            warning="Time coordinate has no positive deltas",
        )

    median_dt = float(np.median(positive))
    mean_abs_dev = float(np.mean(np.abs(positive - median_dt)))
    variance_pct = (mean_abs_dev / median_dt * 100.0) if median_dt > 0 else 0.0

    warning: str | None = None
    if variance_pct > _VARIANCE_WARN_PCT:
        warning = (
            f"Sampling rate varies by ~{variance_pct:.1f}% across the file — "
            "fs attribute absent; median-Δt estimate may be inaccurate"
        )

    return TemporalResolution(
        fs_hz=1.0 / median_dt,
        source="median_dt",
        variance_pct=variance_pct,
        warning=warning,
    )


def check_utc(attrs: dict[str, object]) -> tuple[bool, str | None]:
    """Best-effort check whether the dataset's time coordinate is UTC.

    dolfyn stores time as naive ``datetime64`` — there is no in-band
    tz info — so this is purely attribute-based. Returns
    ``(is_utc, message)``:

    * ``(True, None)``   — an attribute confirms UTC.
    * ``(False, msg)``   — an attribute names a non-UTC tz, **or** no tz
      attribute is present at all. ``msg`` is suitable for a UI warning.
    """
    for key in ("time_zone", "timezone", "tz"):
        raw = attrs.get(key)
        if raw is None:
            continue
        normalized = str(raw).strip().lower()
        if normalized in {"utc", "gmt", "z", "+00:00", "utc+0", "utc+00:00"}:
            return True, None
        return False, f"Time zone attribute '{key}'='{raw}' is not UTC"

    return False, "No time zone attribute on dataset — assuming naive/local time"
