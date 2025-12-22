"""
MHKiT DOLFyN GUI - Main Application

Batch standardization of original ADCP/ADV files to NetCDF using MHKiT-DOLFyN
"""

import sys
import tomllib
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStatusBar,
    QLabel,
    QPushButton,
)
from PyQt6.QtGui import QAction, QIcon, QPixmap, QCursor, QPalette, QDesktopServices
from PyQt6.QtCore import Qt, QUrl


def _get_version() -> str:
    """Get version from pyproject.toml."""
    pyproject_path = Path(__file__).parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


__version__ = _get_version()

# Note: Heavy imports (components, StandardizeMode) are deferred until after
# splash screen is shown in main() to improve perceived startup time.


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.preload_worker = None
        self.init_ui()
        self.start_preload()

    def init_ui(self):
        from components.modes import StandardizeMode
        from components.help_system import create_help_menu

        self.setWindowTitle("MHKiT DOLFyN")
        self.setMinimumSize(1000, 800)

        # Set window icon
        self._set_window_icon()

        # Menu bar
        self._create_menu_bar(create_help_menu)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Standardize mode
        self.standardize_mode = StandardizeMode()
        main_layout.addWidget(self.standardize_mode, stretch=1)

        # Status bar
        self._create_status_bar()

    def _get_base_path(self) -> Path:
        """Get the base path for assets, handling both dev and bundled modes"""
        if getattr(sys, "frozen", False):
            # Running as bundled executable
            if hasattr(sys, "_MEIPASS"):
                # PyInstaller onefile mode - assets extracted to temp dir
                return Path(sys._MEIPASS)
            elif sys.platform == "darwin":
                # macOS .app bundle - assets in Contents/Resources
                return Path(sys.executable).parent.parent / "Resources"
            else:
                # Windows/Linux onedir - assets next to executable
                return Path(sys.executable).parent
        else:
            # Development mode - assets in project directory
            return Path(__file__).parent

    def _set_window_icon(self):
        """Set the window icon"""
        icon_path = (
            self._get_base_path()
            / "assets"
            / "app_icon"
            / "linux"
            / "mhkit-dolfyn-256x256.png"
        )
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _create_status_bar(self):
        """Create status bar with branding and links"""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # Container widget for left-aligned items
        left_container = QWidget()
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(4, 2, 4, 2)
        left_layout.setSpacing(8)

        # MHKiT logo (use square icon, scaled to fit status bar)
        logo_path = (
            self._get_base_path()
            / "assets"
            / "app_icon"
            / "linux"
            / "mhkit-dolfyn-64x64.png"
        )
        if logo_path.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                # Scale to 20x20 for status bar (smooth scaling)
                scaled = pixmap.scaled(
                    20,
                    20,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                logo_label.setPixmap(scaled)
                left_layout.addWidget(logo_label)

        # App version label
        version_label = QLabel(f"v{__version__}")
        left_layout.addWidget(version_label)

        # Separator
        sep1 = QLabel("|")
        palette = sep1.palette()
        muted = palette.color(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText
        )
        sep1.setStyleSheet(f"color: {muted.name()};")
        left_layout.addWidget(sep1)

        # MHKiT link to GitHub repo
        mhkit_btn = self._create_link_button(
            "MHKiT",
            "https://github.com/MHKiT-Software/MHKiT-Python",
            "View MHKiT-Python on GitHub",
        )
        left_layout.addWidget(mhkit_btn)

        # Separator
        sep2 = QLabel("|")
        sep2.setStyleSheet(f"color: {muted.name()};")
        left_layout.addWidget(sep2)

        # Documentation link
        docs_btn = self._create_link_button(
            "Documentation",
            "https://mhkit-software.github.io/MHKiT/",
            "Open MHKiT documentation in browser",
        )
        left_layout.addWidget(docs_btn)

        # Separator
        sep3 = QLabel("|")
        sep3.setStyleSheet(f"color: {muted.name()};")
        left_layout.addWidget(sep3)

        # Issues link
        issues_btn = self._create_link_button(
            "Report Issue",
            "https://github.com/MHKiT-Software/MHKiT-Python/issues",
            "Report bugs or request features on GitHub",
        )
        left_layout.addWidget(issues_btn)

        left_layout.addStretch()
        status_bar.addWidget(left_container, 1)

    def _create_link_button(self, text: str, url: str, tooltip: str) -> QPushButton:
        """Create a clickable link-styled button for status bar"""
        btn = QPushButton(text)
        btn.setFlat(True)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setToolTip(tooltip)
        btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))

        # Use palette-based link color for dark mode compatibility
        palette = btn.palette()
        link_color = palette.color(QPalette.ColorRole.Link)
        btn.setStyleSheet(f"""
            QPushButton {{
                color: {link_color.name()};
                text-decoration: underline;
                border: none;
                padding: 2px 4px;
            }}
            QPushButton:hover {{
                color: {link_color.lighter(120).name()};
            }}
        """)
        return btn

    def _create_menu_bar(self, create_help_menu):
        """Create the application menu bar"""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")

        # We'll add file actions later if needed
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Help menu (from help_system)
        create_help_menu(menu_bar)

    def start_preload(self):
        """Start preloading heavy libraries in background"""
        from components import PreloadWorker

        self.preload_worker = PreloadWorker()
        self.preload_worker.start()


def _get_app_icon_path() -> Path:
    """Get the application icon path for taskbar/dock"""
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(sys.executable).parent.parent / "Resources"
    else:
        base_path = Path(__file__).parent
    return base_path / "assets" / "app_icon" / "linux" / "mhkit-dolfyn-256x256.png"


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Set application icon for taskbar/dock
    icon_path = _get_app_icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Import splash screen directly (not through components package)
    # to avoid loading heavy dependencies before showing the splash
    from components.splash_screen import SplashScreen

    # Show splash screen immediately - before loading heavy modules
    splash = SplashScreen(version=__version__)
    splash.show()
    app.processEvents()

    # Now create main window (this triggers heavy imports)
    window = MainWindow()

    # Close splash and show main window
    splash.finish(window)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
