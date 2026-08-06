"""Generate a runnable Python script that reproduces a GUI export run.

Pure module (no Qt), safe to call from any thread. Takes a list of
:class:`ExportJobSpec` built from GUI state and returns a self-contained script.

The per-file body is not re-implemented here: the verbatim source of
:mod:`mhkit_dolfyn_gui.services.export_pipeline` (the module the export worker
runs) is embedded via :mod:`importlib.resources`, so the script runs the same
code as the app — nothing to drift.

The generated script has two or three top-level variables the user is
expected to edit if they want to re-run or adapt the export:

- ``INPUT_FILES`` — ordered list of absolute :class:`pathlib.Path` objects.
- ``OUTPUT_DIR`` — single directory where ``<stem>.nc`` files are written.
- ``USERDATA`` *(only emitted when at least one file has a non-default
  setting)* — ``dict[Path, bool | Path | dict]`` of per-file overrides.
  ``False`` suppresses loading; a ``Path`` points at an explicit userdata
  file; a plain ``dict`` is passed directly to dolfyn as inline metadata.
  Files absent from the dict (or when the variable is omitted entirely) use
  dolfyn's default (auto-load a sibling ``<stem>.userdata.json``).

Design choices
--------------
- **Paths are emitted as** ``Path(<repr>)`` **literals.** Using
  ``repr(str(path))`` produces a valid Python string literal on every
  platform (backslashes on Windows, forward slashes elsewhere, embedded
  quotes, unicode). The generated script re-wraps in :class:`pathlib.Path`
  so the reader gets a ``Path`` object they can manipulate idiomatically.
- **All paths must be absolute.** We validate this upfront and raise
  ``ValueError`` if a relative path slips through. Generated scripts that
  depend on ``cwd`` are a footgun — users run them from anywhere.
- **USERDATA only contains files with non-default settings** (``SKIP``,
  ``EXPLICIT``, or ``DICT`` mode).  ``AUTO`` and ``NONE`` files are omitted.
  When *no* file in the batch has a userdata override the ``USERDATA``
  variable is omitted entirely and the loop calls
  ``dolfyn.read(str(input_file))`` with no extra kwargs — keeping the script
  as simple as possible for the common case.
- **Dict userdata** is emitted via ``repr()`` so simple ``str``/``int``/
  ``float``/``bool`` values round-trip correctly as Python literals.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from functools import lru_cache
from importlib.resources import files
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@lru_cache(maxsize=1)
def _pipeline_source() -> str:
    """Return the source of the portable export_pipeline module for embedding.

    Read via importlib.resources so it resolves both from a normal install and
    from a PyInstaller bundle (the ``.spec`` ships this file as bundle data).
    The module's own docstring — internal maintainer notes about embed-safety —
    is stripped so the generated script isn't cluttered with it.
    """
    src = files("mhkit_dolfyn_gui.services").joinpath("export_pipeline.py").read_text(
        encoding="utf-8"
    )
    body = ast.parse(src).body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        # Drop the leading module docstring (lines up to and including its last).
        src = "\n".join(src.splitlines()[body[0].end_lineno :])
    return src.strip("\n")


class UserdataMode(StrEnum):
    """How the ``userdata`` kwarg should be emitted for a job.

    - ``AUTO``: omit the kwarg; ``dolfyn.read`` will auto-load the sibling
      ``<stem>.userdata.json`` via its default ``userdata=True``.
    - ``SKIP``: emit ``userdata=False`` to suppress auto-loading.
    - ``EXPLICIT``: emit ``userdata=Path(<path>)`` to point at a
      non-default file (e.g. a global userdata.json shared across runs).
    - ``DICT``: emit ``userdata=<dict>`` to pass inline metadata directly.
    - ``NONE``: omit the kwarg; no sidecar exists and no global is set.
      Functionally equivalent to ``AUTO`` in the generated script (both
      omit), but kept as a distinct mode so the caller's intent is
      legible and future tooling can treat them differently.
    """

    AUTO = "auto"
    SKIP = "skip"
    EXPLICIT = "explicit"
    DICT = "dict"
    NONE = "none"


@dataclass(frozen=True)
class ExportJobSpec:
    """Declarative description of one file → NetCDF export job.

    All paths are absolute — :meth:`__post_init__` raises ``ValueError``
    if any path is relative, so relative-path bugs fail fast at spec
    construction rather than producing a broken generated script.
    """

    source: Path
    output: Path
    profile_index: int
    is_multi_profile: bool
    userdata_mode: UserdataMode
    userdata_path: Path | None = None
    userdata_dict: dict[str, object] | None = None
    include_velds: bool = True

    def __post_init__(self) -> None:
        if not self.source.is_absolute():
            raise ValueError(f"source path must be absolute: {self.source}")
        if not self.output.is_absolute():
            raise ValueError(f"output path must be absolute: {self.output}")
        if self.userdata_mode is UserdataMode.EXPLICIT:
            if self.userdata_path is None:
                raise ValueError("userdata_path is required when mode is EXPLICIT")
            if not self.userdata_path.is_absolute():
                raise ValueError(f"userdata path must be absolute: {self.userdata_path}")
        if self.userdata_mode is UserdataMode.DICT:
            if self.userdata_dict is None:
                raise ValueError("userdata_dict is required when mode is DICT")


def generate_export_script(
    jobs: list[ExportJobSpec],
    *,
    now: datetime | None = None,
) -> str:
    """Return a self-contained Python script that reproduces *jobs*.

    Parameters
    ----------
    jobs:
        The list of export jobs to reproduce. Must all use absolute paths
        (enforced by :class:`ExportJobSpec`).
    now:
        Injected timestamp for the script header. Defaults to the current
        wall clock; kept injectable so tests stay deterministic.

    Returns
    -------
    str
        The script source text. Caller is responsible for writing it to
        disk or showing it to the user.
    """
    timestamp = (now or datetime.now()).isoformat(timespec="seconds")
    include_velds = any(j.include_velds for j in jobs)

    # --- header -------------------------------------------------------
    lines: list[str] = [
        '"""Reproduce mhkit_dolfyn_gui export pipeline.',
        "",
        f"Generated by mhkit_dolfyn_gui on {timestamp}.",
        '"""',
        "",
        "from pathlib import Path",
        "",
        "",
        "# Read -> process -> save body, embedded verbatim from the app's",
        "# export_pipeline module so this script runs the exact same code.",
        _pipeline_source(),
        "",
    ]

    # --- INPUT_FILES --------------------------------------------------
    lines.append("INPUT_FILES = [")
    lines.extend(f"    Path({j.source.as_posix()!r})," for j in jobs)
    lines.append("]")
    lines.append("")

    # --- OUTPUT_DIR ---------------------------------------------------
    # All jobs share the same output directory (first job's parent, or cwd
    # fallback for empty batches).
    output_dir = jobs[0].output.parent.as_posix() if jobs else "."
    lines.append(f"OUTPUT_DIR = Path({output_dir!r})")
    lines.append("")

    # --- INCLUDE_VELDS ------------------------------------------------
    lines.append(f"INCLUDE_VELDS = {include_velds!r}")
    lines.append("")

    # --- USERDATA dict ------------------------------------------------
    # Only files with non-default userdata settings are included.
    # AUTO and NONE files are omitted; absent files use dolfyn's default.
    # When no file has an override the USERDATA variable is skipped entirely
    # and the loop omits the userdata kwarg — keeps common-case scripts simple.
    userdata_entries: list[tuple[str, str]] = []  # (source_posix, value_repr)
    for j in jobs:
        if j.userdata_mode is UserdataMode.SKIP:
            userdata_entries.append((j.source.as_posix(), "False"))
        elif j.userdata_mode is UserdataMode.EXPLICIT:
            assert j.userdata_path is not None
            userdata_entries.append((j.source.as_posix(), f"Path({j.userdata_path.as_posix()!r})"))
        elif j.userdata_mode is UserdataMode.DICT:
            assert j.userdata_dict is not None
            userdata_entries.append((j.source.as_posix(), repr(j.userdata_dict)))

    has_userdata = bool(userdata_entries)

    if has_userdata:
        lines.append("# Per-file userdata overrides.  Files not listed use dolfyn's default")
        lines.append("# (auto-load a sibling <stem>.userdata.json when it exists).")
        lines.append(
            "# Values: False = skip loading; Path(...) = explicit file; dict = inline metadata."
        )
        lines.append("USERDATA = {")
        for src, val in userdata_entries:
            lines.append(f"    Path({src!r}): {val},")
        lines.append("}")
        lines.append("")

    # --- PROFILE_INDEX dict -------------------------------------------
    # Only multi-profile files whose selected profile is not 0 are listed;
    # absent files default to profile 0.
    profile_entries = [(j.source.as_posix(), j.profile_index) for j in jobs if j.profile_index]
    has_profile_index = bool(profile_entries)

    if has_profile_index:
        lines.append("# Profile selected in the GUI for multi-profile instruments.")
        lines.append("# Files not listed use profile 0.")
        lines.append("PROFILE_INDEX = {")
        for src, idx in profile_entries:
            lines.append(f"    Path({src!r}): {idx},")
        lines.append("}")
        lines.append("")

    # --- loop ---------------------------------------------------------
    lines.append("for input_file in INPUT_FILES:")
    lines.append('    output_file = OUTPUT_DIR / (input_file.stem + ".nc")')
    lines.append("    process_one_file(")
    lines.append("        input_file,")
    lines.append("        output_file,")
    if has_profile_index:
        lines.append("        profile_index=PROFILE_INDEX.get(input_file, 0),")
    if has_userdata:
        lines.append("        userdata=USERDATA.get(input_file),")
    lines.append("        include_velds=INCLUDE_VELDS,")
    lines.append("    )")
    lines.append('    print(f"Saved {output_file}")')
    lines.append("")

    return "\n".join(lines)
