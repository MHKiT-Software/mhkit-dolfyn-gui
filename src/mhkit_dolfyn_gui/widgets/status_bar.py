"""Composite status-bar widget: branding, links, memory indicator, file status."""

from __future__ import annotations

import sys
from importlib.metadata import version
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStatusBar,
    QWidget,
)

from mhkit_dolfyn_gui.constants import (
    APP_NAME,
    APP_VERSION,
    GITHUB_ISSUES_URL,
    MHKIT_DOCS_URL,
    MHKIT_REPO_URL,
    STATUS_BAR_LOGO_SIZE_PX,
)
from mhkit_dolfyn_gui.models.file_item import FileStatus
from mhkit_dolfyn_gui.styles import theme
from mhkit_dolfyn_gui.widgets.memory_indicator import ActivityState, MemoryIndicator

if TYPE_CHECKING:
    from collections.abc import Callable

    from mhkit_dolfyn_gui.models.file_item import FileItem
    from mhkit_dolfyn_gui.settings import Settings


class StatusBarWidget(QWidget):
    """Builds and manages all status-bar content.

    Call :meth:`install` after construction to populate an existing
    ``QStatusBar`` (typically ``QMainWindow.statusBar()``).
    """

    def __init__(
        self,
        settings: Settings,
        activity_provider: Callable[[], ActivityState],
        open_preferences: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._activity_provider = activity_provider
        self._open_preferences = open_preferences

        # Built during install()
        self._status_label: QLabel | None = None
        self._memory_indicator: MemoryIndicator | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def install(self, status_bar: QStatusBar) -> None:
        """Populate *status_bar* with branding (left), memory indicator, and file status (right)."""
        status_bar.setStyleSheet(theme.status_bar_container)

        # Left side: logo + version + links
        left_container = QWidget()
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(*theme.layout.status_bar_margin)
        left_layout.setSpacing(theme.layout.spacing_md)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # MHKiT logo
        from mhkit_dolfyn_gui.app import _get_base_path

        base = _get_base_path() / "assets" / "app_icon"
        if sys.platform == "darwin":
            logo_path = base / "macos" / "AppIcon-256x256.png"
        else:
            logo_path = base / "linux" / "mhkit-dolfyn-256x256.png"
        if logo_path.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                dpr = self.devicePixelRatioF() or 1.0
                scaled = pixmap.scaled(
                    int(STATUS_BAR_LOGO_SIZE_PX * dpr),
                    int(STATUS_BAR_LOGO_SIZE_PX * dpr),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                scaled.setDevicePixelRatio(dpr)
                logo_label.setPixmap(scaled)
                logo_label.setFixedSize(STATUS_BAR_LOGO_SIZE_PX, STATUS_BAR_LOGO_SIZE_PX)
                left_layout.addWidget(logo_label)

        # Version
        mhkit_version = version("mhkit")
        version_label = QLabel(f"{APP_NAME} v{APP_VERSION} | MHKiT v{mhkit_version}")
        left_layout.addWidget(version_label)

        _add_separator(left_layout)
        left_layout.addWidget(
            _create_link_button(
                "Report Issue", GITHUB_ISSUES_URL, "Report issues or propose improvements"
            )
        )
        _add_separator(left_layout)
        left_layout.addWidget(
            _create_link_button(
                "DOLFyN Documentation", MHKIT_DOCS_URL, "Open MHKiT-DOLFyN documentation"
            )
        )
        _add_separator(left_layout)
        left_layout.addWidget(
            _create_link_button("MHKiT-Python", MHKIT_REPO_URL, "View MHKiT-Python on GitHub")
        )

        _add_separator(left_layout)
        left_layout.addWidget(
            _create_action_button(
                "Preferences",
                self._open_preferences,
                "Open the Preferences dialog (\u2318/Ctrl+,)",
            )
        )

        left_layout.addStretch()
        status_bar.addWidget(left_container, 1)

        # Memory + activity indicator
        self._memory_indicator = MemoryIndicator(
            self._activity_provider,
            self._settings.memory_poll_interval_ms,
            self,
        )
        self._memory_indicator.setToolTip(
            "Process RSS. Cached datasets are evicted (LRU) above the configured "
            "RAM ceiling or item count (see Preferences \u2192 Cache)."
        )
        status_bar.addPermanentWidget(self._memory_indicator)
        sep = QLabel("|")
        sep.setStyleSheet(theme.status_separator)
        status_bar.addPermanentWidget(sep)

        # Right side: file status
        self._status_label = QLabel("No files loaded")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        status_bar.addPermanentWidget(self._status_label)

    def update_file_status(self, items: list[FileItem]) -> None:
        """Refresh the right-side label from the current file list."""
        if self._status_label is None:
            return
        total = len(items)
        ready = sum(
            1
            for it in items
            if it.status in (FileStatus.READY, FileStatus.CACHED, FileStatus.SAVED)
        )
        checked = sum(1 for it in items if it.checked and it.has_been_read)
        if total == 0:
            self._status_label.setText("No files loaded")
        else:
            self._status_label.setText(f"{total} file(s), {ready} ready, {checked} selected")

    def set_memory_poll_interval(self, interval_ms: int) -> None:
        """Forward to MemoryIndicator when Preferences change."""
        if self._memory_indicator is not None:
            self._memory_indicator.set_interval(interval_ms)

    @property
    def memory_indicator(self) -> MemoryIndicator | None:
        return self._memory_indicator


# ------------------------------------------------------------------
# Module-level helpers (no state needed)
# ------------------------------------------------------------------


def _add_separator(layout: QHBoxLayout) -> None:
    sep = QLabel("|")
    sep.setStyleSheet(theme.status_separator)
    layout.addWidget(sep)


def _create_link_button(text: str, url: str, tooltip: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setFlat(True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip(tooltip)
    btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
    btn.setStyleSheet(theme.status_link_button)
    return btn


def _create_action_button(text: str, callback: Callable[[], None], tooltip: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setFlat(True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip(tooltip)
    btn.clicked.connect(callback)
    btn.setStyleSheet(theme.status_link_button)
    return btn
