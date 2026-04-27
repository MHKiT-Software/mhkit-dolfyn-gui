"""Generate a runnable Python script that reproduces a GUI export run.

Pure module — no Qt imports, no disk I/O — so it is trivially unit-testable
and safe to call from any thread. The caller translates GUI state (file items,
userdata settings, output paths) into a list of :class:`ExportJobSpec` and
receives a string containing a self-contained Python script.

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

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


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

    # --- header -------------------------------------------------------
    lines: list[str] = [
        '"""Reproduce mhkit_dolfyn_gui export pipeline.',
        "",
        f"Generated by mhkit_dolfyn_gui on {timestamp}.",
        '"""',
        "",
        "from pathlib import Path",
        "",
        "import mhkit.dolfyn as dolfyn",
        "",
    ]

    # --- INPUT_FILES --------------------------------------------------
    lines.append("INPUT_FILES = [")
    for j in jobs:
        lines.append(f"    Path({str(j.source)!r}),")
    lines.append("]")
    lines.append("")

    # --- OUTPUT_DIR ---------------------------------------------------
    # All jobs share the same output directory (first job's parent, or cwd
    # fallback for empty batches).
    output_dir = str(jobs[0].output.parent) if jobs else "."
    lines.append(f"OUTPUT_DIR = Path({output_dir!r})")
    lines.append("")

    # --- USERDATA dict ------------------------------------------------
    # Only files with non-default userdata settings are included.
    # AUTO and NONE files are omitted; absent files use dolfyn's default.
    # When no file has an override the USERDATA variable is skipped entirely
    # and the loop uses a bare dolfyn.read() call — keeps common-case scripts
    # as simple as possible.
    userdata_entries: list[tuple[str, str]] = []  # (source_str, value_repr)
    for j in jobs:
        if j.userdata_mode is UserdataMode.SKIP:
            userdata_entries.append((str(j.source), "False"))
        elif j.userdata_mode is UserdataMode.EXPLICIT:
            assert j.userdata_path is not None
            userdata_entries.append((str(j.source), f"Path({str(j.userdata_path)!r})"))
        elif j.userdata_mode is UserdataMode.DICT:
            assert j.userdata_dict is not None
            userdata_entries.append((str(j.source), repr(j.userdata_dict)))

    has_userdata = bool(userdata_entries)

    if has_userdata:
        lines.append(
            "# Per-file userdata overrides.  Files not listed use dolfyn's default"
        )
        lines.append("# (auto-load a sibling <stem>.userdata.json when it exists).")
        lines.append(
            "# Values: False = skip loading; Path(...) = explicit file; dict = inline metadata."
        )
        lines.append("USERDATA = {")
        for src, val in userdata_entries:
            lines.append(f"    Path({src!r}): {val},")
        lines.append("}")
        lines.append("")

    # --- loop ---------------------------------------------------------
    lines.append("for input_file in INPUT_FILES:")
    if has_userdata:
        lines.append("    ud = USERDATA.get(input_file)")
        lines.append('    kwargs = {"userdata": ud} if ud is not None else {}')
        lines.append("    ds = dolfyn.read(str(input_file), **kwargs)")
    else:
        lines.append("    ds = dolfyn.read(str(input_file))")
    lines += [
        "    # If your instrument produces multiple profiles, ds will be a tuple.",
        "    # Uncomment and adjust the line below to select a specific profile:",
        "    # ds = ds[0]",
        '    output_file = OUTPUT_DIR / (input_file.stem + ".nc")',
        "    output_file.parent.mkdir(parents=True, exist_ok=True)",
        "    dolfyn.save(ds, str(output_file))",
        '    print(f"Saved {output_file}")',
        "",
    ]

    return "\n".join(lines)
