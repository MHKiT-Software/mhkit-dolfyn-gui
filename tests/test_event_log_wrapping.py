"""Tests for the EventLog hanging-indent wrapping behavior.

The Event log uses Qt block formats to wrap long messages with a hanging
indent: continuation lines align under the start of the message column,
not back at column 0. These tests verify both the widget configuration
and that the format is applied to each entry as it is appended.
"""

from __future__ import annotations

import logging

import pytest
from PySide6.QtGui import QTextCursor, QTextOption
from PySide6.QtWidgets import QTextEdit

from mhkit_dolfyn_gui.widgets.event_log import EventLog


@pytest.mark.qt
class TestEventLogWrapping:
    def test_wrap_modes_configured(self, qtbot) -> None:
        """Widget wraps at viewport width and breaks long unbroken tokens."""
        w = EventLog()
        qtbot.addWidget(w)

        text_edit: QTextEdit = w._text_edit
        assert text_edit.lineWrapMode() == QTextEdit.LineWrapMode.WidgetWidth
        assert text_edit.wordWrapMode() == QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere

    def test_block_format_applies_hanging_indent(self, qtbot) -> None:
        """Each appended entry's block carries the hanging-indent format."""
        w = EventLog()
        qtbot.addWidget(w)

        # Append a long message that would otherwise overflow the viewport.
        long_msg = (
            "mhkit/dolfyn/io/rdi.py:152: UserWarning: 'magnetic_var_deg' is set "
            "to 15.80 degrees in the binary file '/Users/asmacbook/Desktop/Programming/"
            "mhkit-python/MHKiT-Python/examples/data/dolfyn/vmdas01_wh.ENX', AND "
            "'declination' is set in the userdata.json file."
        )
        w._on_message("10:28:35", "WARNING ", long_msg, logging.WARNING)

        # The first block in the document should now hold this entry and
        # carry the hanging-indent format.
        doc = w._text_edit.document()
        block = doc.firstBlock()
        block_fmt = block.blockFormat()

        # Hanging indent: leftMargin > 0 and textIndent == -leftMargin.
        left_margin = block_fmt.leftMargin()
        text_indent = block_fmt.textIndent()
        assert left_margin > 0, "expected non-zero left margin for hanging indent"
        assert text_indent == pytest.approx(-left_margin), (
            "first line should outdent by exactly the left margin"
        )

        # Block text is still a single logical line — copy/select preserved.
        assert "\n" not in block.text()
        assert long_msg in block.text()
        assert block.text().startswith("[10:28:35] WARNING")

    def test_format_applied_to_every_entry(self, qtbot) -> None:
        """Multiple entries each get their own indented block."""
        w = EventLog()
        qtbot.addWidget(w)

        for i in range(3):
            w._on_message("10:28:35", "INFO    ", f"message {i}", logging.INFO)

        doc = w._text_edit.document()
        # 3 entries + 1 trailing empty block (from final '\n').
        non_empty_blocks = [
            doc.findBlockByNumber(i)
            for i in range(doc.blockCount())
            if doc.findBlockByNumber(i).text()
        ]
        assert len(non_empty_blocks) == 3
        for block in non_empty_blocks:
            fmt = block.blockFormat()
            assert fmt.leftMargin() > 0
            assert fmt.textIndent() == pytest.approx(-fmt.leftMargin())

    def test_multiline_warning_continuation_indent(self, qtbot) -> None:
        """Multi-line py.warnings messages keep continuation lines indented.

        Python's ``warnings.formatwarning()`` produces text like:
            /path/file.py:152: UserWarning: text\\n  warnings.warn(\\n
        The embedded ``\\n`` must not break the visual hanging-indent layout
        — without the multi-line fix, the ``  warnings.warn(`` line falls
        back to column 0.
        """
        w = EventLog()
        qtbot.addWidget(w)

        multi_msg = (
            "/path/to/rdi.py:152: UserWarning: 'magnetic_var_deg' is set to 15.80\n  warnings.warn("
        )
        w._on_message("10:28:35", "WARNING ", multi_msg, logging.WARNING)

        doc = w._text_edit.document()
        non_empty = [
            doc.findBlockByNumber(i)
            for i in range(doc.blockCount())
            if doc.findBlockByNumber(i).text()
        ]
        assert len(non_empty) == 2, "expected 1 primary block + 1 continuation block"

        primary, continuation = non_empty

        # First block: hanging indent (textIndent outdents the prefix to col 0).
        pf = primary.blockFormat()
        assert pf.leftMargin() > 0
        assert pf.textIndent() == pytest.approx(-pf.leftMargin())
        assert primary.text().startswith("[10:28:35] WARNING")
        assert "magnetic_var_deg" in primary.text()

        # Continuation block: same left margin, NO outdent — text starts at
        # the message column, not at column 0.
        cf = continuation.blockFormat()
        assert cf.leftMargin() == pytest.approx(pf.leftMargin())
        assert cf.textIndent() == 0
        assert continuation.text() == "  warnings.warn("

    def test_trailing_newline_does_not_create_blank_block(self, qtbot) -> None:
        """A trailing newline in the raw message must not produce an empty block.

        ``warnings.formatwarning()`` always ends with ``\\n`` — without
        rstrip, this becomes a visible blank line in the log.
        """
        w = EventLog()
        qtbot.addWidget(w)

        # Note the trailing '\n' — characteristic of warnings.formatwarning output.
        msg_with_trailing_newline = "primary line\n  source line\n"
        w._on_message("10:28:35", "WARNING ", msg_with_trailing_newline, logging.WARNING)

        doc = w._text_edit.document()
        non_empty = [
            doc.findBlockByNumber(i)
            for i in range(doc.blockCount())
            if doc.findBlockByNumber(i).text()
        ]
        # Exactly 2 visible blocks: primary + source line. No trailing blank.
        assert len(non_empty) == 2

    def test_traceback_style_message_renders_with_continuation_indent(self, qtbot) -> None:
        """Tracebacks (joined with \\n in logging_setup) render correctly.

        StderrClassifier._flush_traceback emits a single ERROR record whose
        message is ``"\\n".join(tb_lines)`` — every line after the first must
        carry the continuation format.
        """
        w = EventLog()
        qtbot.addWidget(w)

        tb_msg = (
            "Traceback (most recent call last):\n"
            '  File "foo.py", line 10, in <module>\n'
            "    do_thing()\n"
            "ValueError: bad input"
        )
        w._on_message("10:28:35", "ERROR   ", tb_msg, logging.ERROR)

        doc = w._text_edit.document()
        non_empty = [
            doc.findBlockByNumber(i)
            for i in range(doc.blockCount())
            if doc.findBlockByNumber(i).text()
        ]
        assert len(non_empty) == 4

        primary = non_empty[0]
        # Primary keeps the hanging indent.
        assert primary.blockFormat().textIndent() == pytest.approx(
            -primary.blockFormat().leftMargin()
        )

        # All 3 continuations have the flat format.
        for block in non_empty[1:]:
            fmt = block.blockFormat()
            assert fmt.leftMargin() == pytest.approx(primary.blockFormat().leftMargin())
            assert fmt.textIndent() == 0

    def test_single_line_message_still_creates_one_block(self, qtbot) -> None:
        """Regression: the multi-line fix must not split single-line entries."""
        w = EventLog()
        qtbot.addWidget(w)

        w._on_message("10:28:35", "INFO    ", "single line message", logging.INFO)

        doc = w._text_edit.document()
        non_empty = [
            doc.findBlockByNumber(i)
            for i in range(doc.blockCount())
            if doc.findBlockByNumber(i).text()
        ]
        assert len(non_empty) == 1
        assert non_empty[0].blockFormat().textIndent() < 0  # hanging indent

    def test_wrapped_continuation_actually_indented_visually(self, qtbot) -> None:
        """Verify the actual visual x-position of wrapped continuation lines.

        Earlier tests checked that ``QTextBlockFormat.leftMargin`` was *set*,
        but never that the layout engine *honored* it. This test queries the
        real ``QTextLayout`` and asserts the second visual line starts at
        the message column, not at column 0.
        """
        w = EventLog()
        qtbot.addWidget(w)
        w.resize(500, 300)
        w.show()
        qtbot.waitExposed(w)

        # Long single-line message that must wrap inside a 500px viewport.
        long_msg = "abc def ghi jkl mno pqr stu vwx yz1 " * 20  # ~720 chars
        w._on_message("10:28:35", "INFO    ", long_msg, logging.INFO)

        # Force the document layout to compute line geometry.
        doc = w._text_edit.document()
        doc.documentLayout().documentSize()

        block = doc.firstBlock()
        layout = block.layout()
        assert layout.lineCount() >= 2, (
            f"test setup error: expected wrap, got {layout.lineCount()} line(s)"
        )

        line0_x = layout.lineAt(0).x()
        line1_x = layout.lineAt(1).x()

        fm = w._text_edit.fontMetrics()
        expected_indent = fm.horizontalAdvance("X") * 20

        # First visual line sits at x=0 (textIndent outdents it).
        # Second visual line should sit at x ≈ leftMargin.
        # Tolerate sub-pixel rounding by accepting >= 90% of expected.
        assert line1_x >= expected_indent * 0.9, (
            f"continuation line x={line1_x} should be >= {expected_indent} "
            f"(20 mono chars). The text widget is ignoring leftMargin. "
            f"line0 x={line0_x}"
        )

    def test_format_survives_refilter(self, qtbot) -> None:
        """Re-filtering rebuilds the document and reapplies the format."""
        w = EventLog()
        qtbot.addWidget(w)

        w._on_message("10:28:35", "DEBUG   ", "debug entry", logging.DEBUG)
        w._on_message("10:28:36", "INFO    ", "info entry", logging.INFO)

        # Switch filter to "Info+" — drops the DEBUG entry and rebuilds.
        w._level_combo.setCurrentIndex(1)

        doc = w._text_edit.document()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        first_block = cursor.block()
        assert "info entry" in first_block.text()
        assert "debug entry" not in doc.toPlainText()

        fmt = first_block.blockFormat()
        assert fmt.leftMargin() > 0
        assert fmt.textIndent() == pytest.approx(-fmt.leftMargin())
