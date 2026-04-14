"""Persistent event log panel with log level filtering and CSV export.

This widget is a passive display sink. All routing policy (which loggers
to capture, how to classify raw stderr, etc.) lives in
``mhkit_dolfyn_gui.logging_setup``. The widget only knows how to render
``LogRecord``s delivered via a thread-safe Qt signal.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextOption,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mhkit_dolfyn_gui.logging_setup import LogRouter
from mhkit_dolfyn_gui.styles import theme

MAX_LINES = 100_000

# Width of the fixed log-line prefix in monospace characters:
#   "[HH:MM:SS] " (11) + "LEVEL___" (8, ljust) + " " (1) = 20
# Wrapped continuation lines hang-indent by this amount so they align under
# the start of the message column.
_PREFIX_CHARS = 20

# Log level filter options: (display_label, minimum_level)
_LEVEL_FILTERS: list[tuple[str, int]] = [
    ("All", logging.DEBUG),
    ("Info+", logging.INFO),
    ("Warnings & Errors", logging.WARNING),
]


class _LogSignalBridge(QObject):
    """Bridge between logging (any thread) and the GUI (main thread)."""

    message_logged = Signal(str, str, str, int)  # (timestamp, level_name, message, level_no)


class QtLogHandler(logging.Handler):
    """Logging handler that emits formatted records via a Qt signal."""

    def __init__(self, bridge: _LogSignalBridge) -> None:
        super().__init__()
        self._bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        try:
            ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
            level = record.levelname.ljust(8)
            msg = record.getMessage()
            self._bridge.message_logged.emit(ts, level, msg, record.levelno)
        except Exception:
            self.handleError(record)


class EventLog(QWidget):
    """Log panel with level filtering and CSV export, displayed at the bottom."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._messages: list[tuple[str, str, str, int]] = []  # stored for re-filtering
        self._min_level = logging.DEBUG

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.layout.no_margin)
        layout.setSpacing(theme.layout.spacing_xs)

        # Header row
        header = QHBoxLayout()
        header.setContentsMargins(*theme.layout.header_margin)

        title = QLabel("Event Log")
        title.setStyleSheet(theme.section_title)
        header.addWidget(title)
        header.addStretch()

        # Level filter with label
        filter_label = QLabel("Event Type Filter:")
        header.addWidget(filter_label)

        self._level_combo = QComboBox()
        self._level_combo.setFixedWidth(140)
        for label, _ in _LEVEL_FILTERS:
            self._level_combo.addItem(label)
        self._level_combo.currentIndexChanged.connect(self._on_level_changed)
        header.addWidget(self._level_combo)

        layout.addLayout(header)

        # Text area — dark background, hanging-indent wrapping.
        # We use QTextEdit (not QPlainTextEdit) because QPlainTextEdit's
        # QPlainTextDocumentLayout ignores QTextBlockFormat margins, so the
        # hanging-indent layout below would have no visual effect there.
        # MAX_LINES is enforced manually in _enforce_max_lines() since
        # QTextEdit lacks setMaximumBlockCount.
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setStyleSheet(theme.event_log_text)

        # Set the mono font explicitly so fontMetrics() is reliable for the
        # indent calculation below. The stylesheet also declares the same
        # font but is applied lazily via polish, so widget.font() can lag.
        mono_font = QFont()
        mono_font.setFamilies(["Menlo", "Consolas", "Courier New"])
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        mono_font.setPointSize(12)
        self._text_edit.setFont(mono_font)

        # Wrap long lines at the viewport width. Wrap at word boundaries when
        # possible, but break long unbroken tokens (file paths, URLs) so they
        # don't reintroduce a horizontal scrollbar.
        self._text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._text_edit.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)

        # Hanging indent: the entire block is indented by the prefix width,
        # and the first line is outdented back to column 0. The result: the
        # "[HH:MM:SS] LEVEL " prefix sits at the left margin, and any wrapped
        # continuation lines align under the start of the message.
        prefix_px = self._text_edit.fontMetrics().horizontalAdvance("X") * _PREFIX_CHARS
        self._block_fmt = QTextBlockFormat()
        self._block_fmt.setLeftMargin(prefix_px)
        self._block_fmt.setTextIndent(-prefix_px)

        # Continuation block format: used for the 2nd+ lines of multi-line
        # messages (warnings include a "  warnings.warn(" source line; tracebacks
        # span many lines). No outdent — every line stays at the message column.
        self._cont_fmt = QTextBlockFormat()
        self._cont_fmt.setLeftMargin(prefix_px)

        layout.addWidget(self._text_edit)

        # Footer row — Save Log and Clear buttons below the log
        footer = QHBoxLayout()
        footer.setContentsMargins(*theme.layout.header_margin)
        footer.addStretch()

        save_btn = QPushButton("Save Log")
        save_btn.setFixedWidth(70)
        save_btn.clicked.connect(self._on_save_csv)
        footer.addWidget(save_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(50)
        clear_btn.clicked.connect(self._on_clear)
        footer.addWidget(clear_btn)

        layout.addLayout(footer)

        # Set up logging bridge
        self._bridge = _LogSignalBridge()
        self._bridge.message_logged.connect(self._on_message)

        self._handler = QtLogHandler(self._bridge)
        self._handler.setLevel(logging.DEBUG)
        self._router = LogRouter(self._handler)

    @property
    def handler(self) -> QtLogHandler:
        return self._handler

    def install(self) -> None:
        """Install the log router (handler + warnings + stream capture)."""
        self._router.install()

    def uninstall(self) -> None:
        """Reverse install()."""
        self._router.uninstall()

    def _on_message(self, ts: str, level_name: str, msg: str, level_no: int) -> None:
        """Store message and append if it passes the current filter."""
        self._messages.append((ts, level_name, msg, level_no))
        if level_no >= self._min_level:
            self._append_log_line(ts, level_name, msg, level_no)

    def _on_level_changed(self, index: int) -> None:
        if 0 <= index < len(_LEVEL_FILTERS):
            self._min_level = _LEVEL_FILTERS[index][1]
            self._refilter()

    def _refilter(self) -> None:
        """Reapply the level filter to all stored messages."""
        self._text_edit.clear()
        for ts, level_name, msg, level_no in self._messages:
            if level_no >= self._min_level:
                self._append_log_line(ts, level_name, msg, level_no)

    def _append_log_line(self, ts: str, level_name: str, msg: str, level_no: int) -> None:
        """Append a single formatted log line.

        Multi-line messages (warnings include a "  warnings.warn(" source
        line; tracebacks span many lines) are split so the first line gets
        the hanging-indent block format and each continuation line gets a
        flat-margin block. Without this split, embedded ``\\n`` would create
        new Qt blocks with default formatting that render at column 0.
        """
        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Strip trailing whitespace so a trailing '\n' (common with
        # warnings.formatwarning) does not produce an empty block.
        # splitlines() handles \n, \r, and \r\n uniformly. ``or [""]``
        # guards an empty message so we still emit one (empty) entry.
        lines = msg.rstrip().splitlines() or [""]
        primary, continuations = lines[0], lines[1:]

        # First line: hanging-indent block. The "[ts] LEVEL " prefix sits at
        # column 0 thanks to the negative textIndent; any visual wrap of the
        # primary line aligns under the message column.
        cursor.setBlockFormat(self._block_fmt)

        # Timestamp — dim grey
        dim_fmt = QTextCharFormat()
        dim_fmt.setForeground(theme.log.debug)
        cursor.insertText(f"[{ts}] ", dim_fmt)

        # Level name — colored by level
        level_fmt = QTextCharFormat()
        level_fmt.setForeground(theme.log.for_level(level_no))
        cursor.insertText(level_name, level_fmt)

        # Message — default light text
        msg_fmt = QTextCharFormat()
        msg_fmt.setForeground(QColor(theme.log.text))
        cursor.insertText(f" {primary}", msg_fmt)

        # Continuation lines from embedded newlines: each becomes its own
        # block with the flat continuation format (no outdent), so it
        # aligns under the message column.
        for line in continuations:
            cursor.insertText("\n", msg_fmt)
            cursor.setBlockFormat(self._cont_fmt)
            cursor.insertText(line, msg_fmt)

        # Terminate the entry. The next call's setBlockFormat will overwrite
        # this trailing empty block's format, so it doesn't matter that it's
        # currently in _cont_fmt (or _block_fmt for single-line entries).
        cursor.insertText("\n", msg_fmt)

        self._enforce_max_lines()

        scrollbar = self._text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _enforce_max_lines(self) -> None:
        """Trim the oldest blocks to keep the document under MAX_LINES.

        QTextEdit lacks ``setMaximumBlockCount``, so this is the manual
        equivalent. Block-level granularity (not entry-level) — a multi-line
        warning may be partially trimmed during overflow, which is acceptable
        for a runaway-log safety cap.
        """
        doc = self._text_edit.document()
        excess = doc.blockCount() - MAX_LINES
        if excess <= 0:
            return
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(excess):
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # remove the trailing newline left behind

    def _on_save_csv(self) -> None:
        """Save all log messages to a CSV file with datetime filename."""
        default_name = f"mhkit_dolfyn_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Save Log", default_name, "CSV Files (*.csv)")
        if not path:
            return

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["timestamp", "level", "message"])
        for ts, level_name, msg, _level_no in self._messages:
            writer.writerow([ts, level_name.strip(), msg])

        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write(buf.getvalue())

    def _on_clear(self) -> None:
        self._messages.clear()
        self._text_edit.clear()
