"""Resolve and load mhkit.dolfyn userdata.json sidecars.

Resolution order for an input file:
    1. If the FileItem has ``userdata_skip`` set, return None.
    2. If a sibling ``<stem>.userdata.json`` exists, load it.
    3. Else if the global userdata path is set and exists, load it.
    4. Else None.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from mhkit_dolfyn_gui.models.file_item import FileItem


def load_userdata(path: Path) -> dict[str, Any]:
    """Load and parse a userdata JSON file. Raises ValueError on bad JSON."""
    try:
        text = path.read_text()
    except OSError as exc:
        raise ValueError(f"Could not read userdata file {path}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in userdata file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Userdata file {path} must contain a JSON object")
    return data


def sidecar_path_for(input_path: Path) -> Path:
    """Return the conventional sidecar path for an input file."""
    return input_path.with_suffix(input_path.suffix + ".userdata.json").with_name(
        input_path.stem + ".userdata.json"
    )


def resolve_userdata(
    file_item: FileItem,
    global_userdata_path: Path | None,
) -> tuple[dict[str, Any] | None, Path | None]:
    """Resolve which userdata payload to apply for *file_item*.

    Returns ``(payload, source_path)``. ``payload`` is None if no userdata
    should be applied. ``source_path`` is the file the payload came from
    (or None).
    """
    if getattr(file_item, "userdata_skip", False):
        return None, None

    sidecar = sidecar_path_for(file_item.path)
    if sidecar.exists():
        return load_userdata(sidecar), sidecar

    if global_userdata_path is not None and global_userdata_path.exists():
        return load_userdata(global_userdata_path), global_userdata_path

    return None, None
