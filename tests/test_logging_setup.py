"""Tests for logging_setup — accuracy of stderr classification.

These tests lock in the rule that stderr is a stream, not a severity:
unknown lines fall back to WARNING (never ERROR), tracebacks are
recognized structurally and emitted as a single ERROR record, and
Python warning-format lines map to WARNING.
"""

from __future__ import annotations

import logging
import warnings

import pytest

from mhkit_dolfyn_gui.logging_setup import (
    LOGGER_LEVELS,
    STDERR_DEFAULT_LEVEL,
    LogRouter,
    StderrClassifier,
)


class _RecordingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def captured_logger() -> tuple[logging.Logger, _RecordingHandler]:
    logger = logging.getLogger("test_logging_setup.capture")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    handler = _RecordingHandler()
    logger.addHandler(handler)
    return logger, handler


def test_stderr_default_is_warning_not_error() -> None:
    """The whole point: stderr is NOT inherently ERROR."""
    assert STDERR_DEFAULT_LEVEL == logging.WARNING


def test_unknown_line_uses_default_level(captured_logger) -> None:
    logger, handler = captured_logger
    classifier = StderrClassifier(logger, default_level=logging.WARNING)

    classifier.feed_line("Reading 1024 bytes from sensor")
    classifier.flush()

    assert len(handler.records) == 1
    assert handler.records[0].levelno == logging.WARNING


def test_python_warning_format_classified_as_warning(captured_logger) -> None:
    logger, handler = captured_logger
    classifier = StderrClassifier(logger, default_level=logging.ERROR)

    classifier.feed_line(
        "/opt/lib/python3.11/site-packages/numpy/core/_methods.py:184: "
        "RuntimeWarning: invalid value encountered in divide"
    )
    classifier.flush()

    assert len(handler.records) == 1
    assert handler.records[0].levelno == logging.WARNING


def test_traceback_collected_as_single_error(captured_logger) -> None:
    logger, handler = captured_logger
    classifier = StderrClassifier(logger, default_level=logging.WARNING)

    for line in [
        "Traceback (most recent call last):",
        '  File "/tmp/foo.py", line 12, in <module>',
        "    do_thing()",
        '  File "/tmp/foo.py", line 5, in do_thing',
        "    raise ValueError('bad')",
        "ValueError: bad",
    ]:
        classifier.feed_line(line)
    classifier.flush()

    assert len(handler.records) == 1
    rec = handler.records[0]
    assert rec.levelno == logging.ERROR
    assert "Traceback" in rec.getMessage()
    assert "ValueError: bad" in rec.getMessage()


def test_partial_traceback_flushed_on_close(captured_logger) -> None:
    """A traceback that never sees its tail line should still be emitted."""
    logger, handler = captured_logger
    classifier = StderrClassifier(logger, default_level=logging.WARNING)

    classifier.feed_line("Traceback (most recent call last):")
    classifier.feed_line('  File "/tmp/foo.py", line 12, in <module>')
    classifier.flush()

    assert len(handler.records) == 1
    assert handler.records[0].levelno == logging.ERROR


def test_lines_after_traceback_classified_independently(captured_logger) -> None:
    logger, handler = captured_logger
    classifier = StderrClassifier(logger, default_level=logging.WARNING)

    for line in [
        "Traceback (most recent call last):",
        '  File "/tmp/foo.py", line 1, in <module>',
        "RuntimeError: nope",
        "Reading next file",
    ]:
        classifier.feed_line(line)
    classifier.flush()

    assert len(handler.records) == 2
    assert handler.records[0].levelno == logging.ERROR
    assert handler.records[1].levelno == logging.WARNING
    assert "Reading next file" in handler.records[1].getMessage()


def test_router_attaches_handler_to_root_once() -> None:
    """LogRouter must attach the handler at root so dolfyn's getLogger() is captured."""
    handler = _RecordingHandler()
    router = LogRouter(handler)
    root = logging.getLogger()
    initial_handlers = list(root.handlers)
    try:
        router.install()
        assert handler in root.handlers
        # Idempotent
        router.install()
        assert root.handlers.count(handler) == 1

        # A library that uses the unnamed root logger (like dolfyn) is captured.
        logging.getLogger().warning("dolfyn-style warning")
        assert any("dolfyn-style warning" in r.getMessage() for r in handler.records)
    finally:
        router.uninstall()
        assert handler not in root.handlers
        # Don't leave behind extra handlers
        assert root.handlers == initial_handlers


def test_logger_levels_table_covers_dolfyn_via_root() -> None:
    """Root must be in the table — that's how dolfyn's getLogger() output is captured."""
    assert "" in LOGGER_LEVELS
    assert LOGGER_LEVELS[""] <= logging.WARNING


def test_warnings_warn_emits_single_line_record() -> None:
    """warnings.warn() must produce one clean log line — no embedded newlines
    and no trailing source-line continuation.

    Without our custom showwarning, ``logging.captureWarnings(True)`` would
    use ``warnings.formatwarning`` and emit a two-line message:
        /path/file.py:LINE: UserWarning: message
          warnings.warn(    <-- raw source line, redundant noise

    Our replacement collapses this into a single ``filename:lineno: Category:
    message`` record so each warning becomes one entry in the EventLog.
    """
    handler = _RecordingHandler()
    router = LogRouter(handler)
    try:
        router.install()
        # Make sure the warning is not filtered out by Python's dedup cache.
        warnings.simplefilter("always")
        warnings.warn("test message body", UserWarning, stacklevel=1)

        warning_records = [r for r in handler.records if r.name == "py.warnings"]
        assert len(warning_records) == 1, (
            f"expected exactly 1 py.warnings record, got {len(warning_records)}"
        )

        rec = warning_records[0]
        msg = rec.getMessage()
        assert rec.levelno == logging.WARNING
        assert "\n" not in msg, f"warning record contains embedded newline: {msg!r}"
        assert "warnings.warn" not in msg, f"warning record contains source-line noise: {msg!r}"
        assert "UserWarning" in msg
        assert "test message body" in msg
        # The format we promise: "filename:lineno: Category: message"
        assert msg.endswith("UserWarning: test message body")
    finally:
        router.uninstall()
