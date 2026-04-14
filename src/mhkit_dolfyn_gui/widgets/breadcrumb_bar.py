"""Breadcrumb navigation bar for file system paths.

Displays clickable path segments (e.g. ``/ > Users > data``) with an
overflow menu when the path is too deep to fit.
"""

from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from mhkit_dolfyn_gui.styles import theme

if TYPE_CHECKING:
    from PySide6.QtGui import QResizeEvent


class BreadcrumbBar(QWidget):
    """Clickable breadcrumb path bar with overflow for deep paths."""

    path_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._segments: list[tuple[str, str]] = []  # (display_name, full_path)
        self._crumb_widgets: list[QWidget] = []

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(*theme.layout.no_margin)
        self._layout.setSpacing(0)

        # Overflow button (hidden by default)
        self._overflow_btn = QPushButton("\u2026")
        self._overflow_btn.setStyleSheet(theme.breadcrumb)
        self._overflow_btn.setFixedWidth(24)
        self._overflow_btn.hide()
        self._layout.addWidget(self._overflow_btn)

        self._overflow_menu = QMenu(self._overflow_btn)
        self._overflow_btn.setMenu(self._overflow_menu)

        self._layout.addStretch()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_path(self, path: str) -> None:
        """Update the breadcrumb to display *path*."""
        self._segments = self._parse_path(path)
        self._rebuild()

    def current_path(self) -> str:
        """Return the full path of the current (rightmost) segment."""
        if self._segments:
            return self._segments[-1][1]
        return ""

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_path(path: str) -> list[tuple[str, str]]:
        """Split *path* into ``(display_name, cumulative_path)`` pairs."""
        parts = PurePath(path).parts
        segments: list[tuple[str, str]] = []
        for i, part in enumerate(parts):
            full = str(PurePath(*parts[: i + 1]))
            display = "/" if part == "/" else part
            segments.append((display, full))
        return segments

    def _rebuild(self) -> None:
        """Rebuild all breadcrumb widgets from current segments."""
        # Remove old widgets (skip overflow button and stretch)
        for w in self._crumb_widgets:
            self._layout.removeWidget(w)
            w.deleteLater()
        self._crumb_widgets.clear()

        if not self._segments:
            self._overflow_btn.hide()
            return

        # Insert crumbs before the stretch
        stretch_idx = self._layout.count() - 1

        for i, (display, full_path) in enumerate(self._segments):
            is_current = i == len(self._segments) - 1

            # Separator (except before first segment)
            if i > 0:
                sep = QLabel("\u203a")
                sep.setStyleSheet(theme.breadcrumb_separator)
                self._layout.insertWidget(stretch_idx, sep)
                self._crumb_widgets.append(sep)
                stretch_idx += 1

            btn = QPushButton(display)
            if is_current:
                btn.setStyleSheet(theme.breadcrumb_current)
                btn.setEnabled(False)
            else:
                btn.setStyleSheet(theme.breadcrumb)
                btn.clicked.connect(lambda checked=False, p=full_path: self.path_clicked.emit(p))

            self._layout.insertWidget(stretch_idx, btn)
            self._crumb_widgets.append(btn)
            stretch_idx += 1

        self._update_overflow()

    def _update_overflow(self) -> None:
        """Show/hide overflow menu based on available width."""
        # Simple heuristic: if more than 4 segments, collapse early ones
        visible_count = 4
        crumb_buttons = [w for w in self._crumb_widgets if isinstance(w, QPushButton)]
        if len(crumb_buttons) <= visible_count:
            self._overflow_btn.hide()
            for w in self._crumb_widgets:
                w.show()
            return

        # Hide early segments + their separators, show in overflow menu
        self._overflow_menu.clear()
        hidden_count = len(crumb_buttons) - visible_count

        seg_idx = 0
        for w in self._crumb_widgets:
            if isinstance(w, QPushButton) and seg_idx < hidden_count:
                display, full_path = self._segments[seg_idx]
                self._overflow_menu.addAction(
                    display,
                    lambda p=full_path: self.path_clicked.emit(p),
                )
                w.hide()
                seg_idx += 1
            elif isinstance(w, QLabel) and seg_idx <= hidden_count:
                w.hide()
            else:
                w.show()

        self._overflow_btn.show()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_overflow()
