"""Shared column indices and status label/color tables for the file sidebar."""

from __future__ import annotations

from mhkit_dolfyn_gui.models.file_item import FileStatus

# Tree column indices
COL_CONVERT = 0
COL_FILE = 1
COL_STATUS = 2
COL_REMOVE = 3

# User-facing labels for FileStatus values.
STATUS_LABELS: dict[FileStatus, str] = {
    FileStatus.PENDING: "Pending",
    FileStatus.READING: "Reading...",
    FileStatus.READY: "Ready",
    FileStatus.CACHED: "Cached",
    FileStatus.ERROR: "Error",
    FileStatus.SAVING: "Saving...",
    FileStatus.SAVED: "Saved",
}

# Color overrides for status text per state. Falls back to status palette.
STATUS_TEXT_COLORS: dict[FileStatus, str] = {
    FileStatus.PENDING: "#a0a0a0",
    FileStatus.READING: "#42a5f5",
    FileStatus.READY: "#66bb6a",
    FileStatus.CACHED: "#9575cd",
    FileStatus.ERROR: "#ef5350",
    FileStatus.SAVING: "#ffa726",
    FileStatus.SAVED: "#388e3c",
}


def status_label(status: FileStatus) -> str:
    return STATUS_LABELS.get(status, status.value)
