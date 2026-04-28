"""Splash screen for application startup.

Rounded-corner splash with the MHKiT logo, progress bar, and status text.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from mhkit_dolfyn_gui.constants import APP_NAME, APP_VERSION
from mhkit_dolfyn_gui.styles import theme

_sl = theme.splash_layout


def _load_logo() -> QPixmap:
    """Load MHKiT logo, handling frozen (PyInstaller) and dev paths."""
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            base_path = Path(getattr(sys, "_MEIPASS"))  # noqa: B009 — PyInstaller runtime attr
        elif sys.platform == "darwin":
            base_path = Path(sys.executable).parent.parent / "Resources"
        else:
            base_path = Path(sys.executable).parent
    else:
        base_path = Path(__file__).parent.parent.parent.parent

    logo_path = base_path / "assets" / "MHKiT_logo.png"
    pixmap = QPixmap(str(logo_path))
    if pixmap.width() > _sl.logo_width:
        pixmap = pixmap.scaledToWidth(_sl.logo_width, Qt.TransformationMode.SmoothTransformation)
    return pixmap


class SplashScreen(QWidget):
    """Custom splash screen with rounded corners, logo, progress bar, and status text."""

    def __init__(self) -> None:
        super().__init__(None)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._logo = _load_logo()
        logo_w = self._logo.width() if not self._logo.isNull() else _sl.logo_width
        logo_h = self._logo.height() if not self._logo.isNull() else 200
        self._logo_height = logo_h

        layout = QVBoxLayout(self)
        layout.setContentsMargins(_sl.padding, _sl.padding, _sl.padding, _sl.padding)
        layout.setSpacing(0)

        logo_spacer = QWidget()
        logo_spacer.setFixedSize(logo_w, logo_h)
        layout.addWidget(logo_spacer)

        text_container = QWidget()
        text_container.setFixedWidth(logo_w)
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(*_sl.text_margins)
        text_layout.setSpacing(_sl.text_spacing)

        header = QLabel(f"Starting {APP_NAME}...")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(theme.splash_header)
        text_layout.addWidget(header)

        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet(theme.splash_version)
        text_layout.addWidget(version_label)

        text_layout.addSpacing(theme.layout.spacing_sm)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(_sl.progress_height)
        self._progress_bar.setStyleSheet(theme.splash_progress_bar)
        text_layout.addWidget(self._progress_bar)

        text_layout.addSpacing(theme.layout.spacing_xs)

        self._status_label = QLabel("Initializing...")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(theme.splash_status)
        text_layout.addWidget(self._status_label)

        layout.addWidget(text_container)

        self.setFixedSize(
            logo_w + _sl.padding * 2,
            logo_h + text_container.sizeHint().height() + _sl.padding * 2,
        )

        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
            )

    def set_progress(self, percent: int, message: str = "") -> None:
        self._progress_bar.setValue(percent)
        if message:
            self._status_label.setText(message)
        QApplication.processEvents()

    def finish(self, window: QWidget) -> None:
        self.close()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cr = _sl.corner_radius

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), cr, cr)
        painter.setClipPath(clip)

        painter.fillRect(0, 0, w, h, theme.splash.bg)

        if not self._logo.isNull():
            painter.drawPixmap(_sl.padding, _sl.padding, self._logo)

        text_y = _sl.padding + self._logo_height
        painter.fillRect(QRectF(0, text_y, w, h - text_y), theme.splash.text_area_bg)

        painter.setClipping(False)
        border = QPainterPath()
        border.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), cr, cr)
        painter.setPen(theme.splash.border)
        painter.drawPath(border)

        painter.end()
