"""A QLabel subclass that elides text with '...' and supports hover/click to reveal."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontMetrics, QMouseEvent, QPainter
from PySide6.QtWidgets import QLabel, QWidget


class ElidedLabel(QLabel):
    """Label that truncates long text with ellipsis based on available pixel width.

    Features:
        - Pixel-based elision using Qt.ElideRight
        - Tooltip showing full text when elided
        - Click to expand/collapse inline (with word wrap)
        - Pointing-hand cursor when text is elided
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._full_text = text
        self._expanded = False
        self._is_elided = False
        self.setTextInteractionFlags(
            self.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fullText(self) -> str:
        return self._full_text

    def setFullText(self, text: str) -> None:
        self._full_text = text
        if self._expanded:
            super().setText(text)
        self._update_elision_state()
        self.update()

    # ------------------------------------------------------------------
    # Size hints
    # ------------------------------------------------------------------

    def minimumSizeHint(self) -> QSize:
        if self._expanded:
            return super().minimumSizeHint()
        fm = QFontMetrics(self.font())
        # Allow shrinking to ~5 characters + ellipsis
        return QSize(fm.horizontalAdvance("XXXXX…"), fm.height())

    def sizeHint(self) -> QSize:
        if self._expanded:
            return super().sizeHint()
        fm = QFontMetrics(self.font())
        # Prefer showing the full text, but layout can shrink us
        return QSize(fm.horizontalAdvance(self._full_text), fm.height())

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        if self._expanded:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        fm = self.fontMetrics()
        available = self.contentsRect().width()
        elided = fm.elidedText(self._full_text, Qt.TextElideMode.ElideRight, available)
        was_elided = self._is_elided
        self._is_elided = elided != self._full_text

        if was_elided != self._is_elided:
            self._update_cursor_and_tooltip()

        painter.drawText(
            self.contentsRect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided
        )
        painter.end()

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._is_elided and not self._expanded:
            self._expand()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._expanded:
            self._collapse()
            return
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Expand / collapse
    # ------------------------------------------------------------------

    def _expand(self) -> None:
        self._expanded = True
        self.setWordWrap(True)
        super().setText(self._full_text)
        self.setToolTip("")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.updateGeometry()

    def _collapse(self) -> None:
        self._expanded = False
        self.setWordWrap(False)
        super().setText("")  # paintEvent handles drawing
        self._update_elision_state()
        self.updateGeometry()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_elision_state(self) -> None:
        fm = QFontMetrics(self.font())
        available = self.contentsRect().width() if self.contentsRect().width() > 0 else 0
        if available > 0:
            elided = fm.elidedText(self._full_text, Qt.TextElideMode.ElideRight, available)
            self._is_elided = elided != self._full_text
        else:
            # Before first layout pass, estimate based on size hint
            self._is_elided = False
        self._update_cursor_and_tooltip()

    def _update_cursor_and_tooltip(self) -> None:
        if self._is_elided and not self._expanded:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip(self._full_text)
        elif self._expanded:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("")
        else:
            self.unsetCursor()
            self.setToolTip("")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._expanded:
            self._update_elision_state()
