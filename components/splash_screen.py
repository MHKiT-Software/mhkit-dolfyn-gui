"""
Splash screen for application startup
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QSplashScreen
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor


class SplashScreen(QSplashScreen):
    """Custom splash screen with logo and version"""

    # Height of the white text area at the bottom
    TEXT_AREA_HEIGHT = 50

    def __init__(self, version="1.0.0"):
        # Determine the correct path for the logo
        if getattr(sys, "frozen", False):
            # Running as bundled executable
            if hasattr(sys, "_MEIPASS"):
                # PyInstaller onefile mode - assets extracted to temp dir
                base_path = Path(sys._MEIPASS)
            elif sys.platform == "darwin":
                # macOS .app bundle - assets in Contents/Resources
                base_path = Path(sys.executable).parent.parent / "Resources"
            else:
                # Windows/Linux onedir - assets next to executable
                base_path = Path(sys.executable).parent
        else:
            # Running in development
            base_path = Path(__file__).parent.parent

        logo_path = base_path / "assets" / "MHKiT_logo.png"

        # Load the logo
        logo_pixmap = QPixmap(str(logo_path))

        # Scale to a reasonable size if needed
        if logo_pixmap.width() > 400:
            logo_pixmap = logo_pixmap.scaledToWidth(
                400, Qt.TransformationMode.SmoothTransformation
            )

        # Create a new pixmap with extra space for text area
        total_height = logo_pixmap.height() + self.TEXT_AREA_HEIGHT
        pixmap = QPixmap(logo_pixmap.width(), total_height)
        pixmap.fill(QColor(255, 255, 255))  # White background

        # Draw the logo onto the new pixmap
        painter = QPainter(pixmap)
        painter.drawPixmap(0, 0, logo_pixmap)
        painter.end()

        super().__init__(pixmap, Qt.WindowType.WindowStaysOnTopHint)

        self.version = version
        self.logo_height = logo_pixmap.height()

    def drawContents(self, painter: QPainter):
        """Draw the splash screen contents with version text"""
        super().drawContents(painter)

        # Text area rect (the white area at bottom, with some top padding)
        text_rect = QRect(0, self.logo_height + 8, self.width(), self.TEXT_AREA_HEIGHT)

        # Draw version and loading text together
        # painter.setPen(QColor(0, 74, 114))  # MHKiT blue color
        painter.setPen(QColor(10, 10, 10))  # MHKiT blue color
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            f"Version {self.version}\nLoading...",
        )
