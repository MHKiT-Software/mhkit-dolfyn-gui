"""Centralized logging policy for mhkit_dolfyn_gui.

All routing decisions live here so the rest of the app (and the EventLog
widget in particular) stays a passive sink. To onboard a new library,
add one entry to ``LOGGER_LEVELS``.

Why this module exists
----------------------
Third-party libraries (notably ``mhkit.dolfyn``) call ``logging.getLogger()``
with no name, which targets the **root** logger. If we only attached our
handler to ``mhkit_dolfyn_gui``, those records would fall through Python's
``lastResort`` writer to stderr — and our previous stderr capture tagged
*everything* on stderr as ERROR. That produced false-positive ERRORs for
ordinary library warnings.

The fix is two-fold:

1. Attach our handler **once** to the root logger so library records are
   delivered at their real, library-assigned severity.
2. For residual raw stderr (libraries that ``print`` to stderr or C
   extensions), classify *structurally* — recognize Python tracebacks and
   the standard warning format — and default unknown lines to WARNING
   (never ERROR), since stderr is a stream, not a severity.
"""

from __future__ import annotations

import logging
import re
import sys
import warnings
from typing import TextIO

APP_LOGGER_NAME = "mhkit_dolfyn_gui"

# ---------------------------------------------------------------------------
# Per-logger level policy — the growable surface.
#
# Add a new library by adding a row. The handler is attached to root once;
# these levels just decide which records each logger lets through.
# ---------------------------------------------------------------------------
LOGGER_LEVELS: dict[str, int] = {
    "": logging.WARNING,  # root catch-all (covers dolfyn's getLogger())
    APP_LOGGER_NAME: logging.DEBUG,  # our own app code — verbose
    "py.warnings": logging.WARNING,  # warnings.warn() routed via captureWarnings
    "mhkit": logging.INFO,
    "xarray": logging.WARNING,
    "numpy": logging.WARNING,
    "scipy": logging.WARNING,
    "netCDF4": logging.WARNING,
}

# Default level applied to raw stdout / stderr text that the classifier can't
# match against a known structure. stderr defaults to WARNING (not ERROR) —
# stderr is a stream, not a severity.
STDOUT_DEFAULT_LEVEL = logging.INFO
STDERR_DEFAULT_LEVEL = logging.WARNING

# Child loggers used for raw stream capture. Kept distinct so users can
# tell stream output apart from real logging records.
STDOUT_LOGGER_NAME = f"{APP_LOGGER_NAME}.stdout"
STDERR_LOGGER_NAME = f"{APP_LOGGER_NAME}.stderr"


# ---------------------------------------------------------------------------
# Stderr structural classifier
# ---------------------------------------------------------------------------

# Standard CPython warning format from warnings.formatwarning():
#   /path/to/file.py:LINE: SomeWarning: message text
_WARNING_LINE_RE = re.compile(r"^.+?:\d+:\s+\w*Warning:\s")

# Traceback start marker (CPython, including chained variants).
_TRACEBACK_START_RE = re.compile(
    r"^Traceback \(most recent call last\):$"
    r"|^During handling of the above exception"
    r"|^The above exception was the direct cause"
)

# A non-indented "ExceptionName: message" or bare "ExceptionName" — the line
# that closes a traceback block.
_EXCEPTION_TAIL_RE = re.compile(r"^[A-Za-z_][\w.]*(Error|Exception|Warning|Exit|Interrupt)(:|$)")


class StderrClassifier:
    """Buffers stderr lines and emits log records at accurate levels.

    Multi-line tracebacks are collected and emitted as a single ERROR
    record. Python warning-format lines become WARNING. Anything else
    falls back to ``default_level``.
    """

    def __init__(self, logger: logging.Logger, default_level: int) -> None:
        self._logger = logger
        self._default_level = default_level
        self._tb_buffer: list[str] = []

    def feed_line(self, line: str) -> None:
        """Process one stripped, non-empty line of stderr text."""
        # Inside an in-progress traceback?
        if self._tb_buffer:
            self._tb_buffer.append(line)
            # An exception tail line at column 0 closes the block.
            if not line.startswith(" ") and _EXCEPTION_TAIL_RE.match(line):
                self._flush_traceback()
            return

        # Start of a new traceback?
        if _TRACEBACK_START_RE.match(line):
            self._tb_buffer.append(line)
            return

        # Standalone Python warning line.
        if _WARNING_LINE_RE.match(line):
            self._logger.log(logging.WARNING, "%s", line)
            return

        # Unknown — be honest and use the default (WARNING for stderr).
        self._logger.log(self._default_level, "%s", line)

    def flush(self) -> None:
        """Emit any partial traceback that never saw its tail line."""
        if self._tb_buffer:
            self._flush_traceback()

    def _flush_traceback(self) -> None:
        block = "\n".join(self._tb_buffer)
        self._tb_buffer.clear()
        self._logger.log(logging.ERROR, "%s", block)


# ---------------------------------------------------------------------------
# Stream redirector
# ---------------------------------------------------------------------------


class _StreamToLogger:
    """Redirect a text stream to a classifier.

    Preserves the original stream so output still reaches the terminal.
    Buffers partial lines so each emitted record is one complete line.
    A reentrance guard prevents infinite recursion if logging itself
    writes to the stream we're capturing.

    ``original`` may be ``None`` — this happens on Windows PyInstaller
    builds compiled without a console (``--noconsole``).  In that case
    pass-through is silently skipped; classification still works so log
    records are still routed to the EventLog.
    """

    def __init__(
        self,
        classifier: StderrClassifier,
        original: TextIO | None,
    ) -> None:
        self._classifier = classifier
        self._original = original
        self._buffer = ""
        self._in_write = False

    def write(self, text: str) -> int:
        # Pass through to the real terminal when one exists.
        if self._original is not None:
            self._original.write(text)

        if not text or self._in_write:
            return len(text) if text else 0

        self._in_write = True
        try:
            self._buffer += text
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                stripped = line.rstrip()
                if stripped:
                    self._classifier.feed_line(stripped)
        finally:
            self._in_write = False
        return len(text)

    def flush(self) -> None:
        if self._original is not None:
            self._original.flush()
        if self._buffer.strip() and not self._in_write:
            self._in_write = True
            try:
                self._classifier.feed_line(self._buffer.strip())
                self._buffer = ""
                self._classifier.flush()
            finally:
                self._in_write = False

    def fileno(self) -> int:
        if self._original is not None:
            return self._original.fileno()
        raise OSError("fileno() not available: no underlying stream (frozen build)")

    def isatty(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# Warning capture
# ---------------------------------------------------------------------------


def _showwarning(
    message: Warning | str,
    category: type[Warning],
    filename: str,
    lineno: int,
    file: TextIO | None = None,
    line: str | None = None,
) -> None:
    """Single-line replacement for warnings.showwarning.

    The default ``warnings.showwarning`` calls ``warnings.formatwarning``,
    which returns a two-line string: the warning header followed by the raw
    source line at ``filename:lineno`` (read via linecache). For
    ``warnings.warn()`` callers that line is almost always just
    ``warnings.warn(`` — pure noise in a GUI log.

    This replacement logs one clean line to the ``py.warnings`` logger so
    each warning becomes exactly one record in the EventLog.
    """
    logging.getLogger("py.warnings").warning(
        "%s:%d: %s: %s", filename, lineno, category.__name__, message
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class LogRouter:
    """Installs a single handler at the root logger and routes streams.

    The handler is attached **once at root**. Per-logger levels in
    ``LOGGER_LEVELS`` decide what each origin logger emits; records
    propagate up to the root handler from there. This avoids
    double-emission and lets one config table cover every library.
    """

    def __init__(self, handler: logging.Handler) -> None:
        self._handler = handler
        self._installed = False
        self._original_stdout: TextIO | None = None
        self._original_stderr: TextIO | None = None
        self._original_showwarning: object = None

    def install(self) -> None:
        if self._installed:
            return
        self._installed = True

        # 1. Apply per-logger levels.
        for name, level in LOGGER_LEVELS.items():
            logging.getLogger(name).setLevel(level)

        # 2. Attach our handler ONCE at the root.
        root = logging.getLogger()
        if self._handler not in root.handlers:
            root.addHandler(self._handler)

        # 3. Route warnings.warn() through the logging system. We install
        #    our own showwarning instead of using logging.captureWarnings(True)
        #    so each warning becomes a single clean log line (no trailing
        #    "  warnings.warn(" source line from formatwarning).
        self._original_showwarning = warnings.showwarning
        warnings.showwarning = _showwarning

        # 4. Capture stdout/stderr for libraries that print() instead of log.
        #    On Windows frozen builds (PyInstaller --noconsole) sys.stdout and
        #    sys.stderr are None.  We still install the classifier wrappers so
        #    that log records reach the EventLog; we just skip pass-through to
        #    the missing underlying stream.
        stdout_logger = logging.getLogger(STDOUT_LOGGER_NAME)
        stderr_logger = logging.getLogger(STDERR_LOGGER_NAME)
        stdout_logger.setLevel(logging.DEBUG)
        stderr_logger.setLevel(logging.DEBUG)

        stdout_classifier = StderrClassifier(stdout_logger, STDOUT_DEFAULT_LEVEL)
        stderr_classifier = StderrClassifier(stderr_logger, STDERR_DEFAULT_LEVEL)

        self._original_stdout = sys.stdout  # may be None on frozen Windows build
        self._original_stderr = sys.stderr  # may be None on frozen Windows build
        sys.stdout = _StreamToLogger(stdout_classifier, self._original_stdout)  # type: ignore[assignment]
        sys.stderr = _StreamToLogger(stderr_classifier, self._original_stderr)  # type: ignore[assignment]

    def uninstall(self) -> None:
        if not self._installed:
            return
        self._installed = False

        root = logging.getLogger()
        if self._handler in root.handlers:
            root.removeHandler(self._handler)

        if self._original_showwarning is not None:
            warnings.showwarning = self._original_showwarning
            self._original_showwarning = None

        if self._original_stdout is not None:
            sys.stdout = self._original_stdout
            self._original_stdout = None
        if self._original_stderr is not None:
            sys.stderr = self._original_stderr
            self._original_stderr = None
