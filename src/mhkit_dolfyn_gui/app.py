"""Application entry point: QApplication, splash screen, and staged initialization."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from mhkit_dolfyn_gui.constants import APP_NAME, APP_VERSION
from mhkit_dolfyn_gui.main_window import MainWindow
from mhkit_dolfyn_gui.styles import theme
from mhkit_dolfyn_gui.widgets.splash_screen import SplashScreen

log = logging.getLogger(__name__)


def _get_base_path() -> Path:
    """Return the base path for assets, handling frozen (PyInstaller) builds."""
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return Path(getattr(sys, "_MEIPASS"))  # noqa: B009 — PyInstaller runtime attr
        if sys.platform == "darwin":
            return Path(sys.executable).parent.parent / "Resources"
        return Path(sys.executable).parent
    return Path(__file__).parent.parent.parent


def _set_app_icon(app: QApplication) -> None:
    """Set the platform-appropriate application icon."""
    base_icon = _get_base_path() / "assets" / "app_icon"
    if sys.platform == "darwin":
        icon_path = base_icon / "macos" / "AppIcon-256x256.png"
    elif sys.platform == "win32":
        icon_path = base_icon / "windows" / "AppIcon.ico"
    else:
        icon_path = base_icon / "linux" / "mhkit-dolfyn-256x256.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))


def main() -> None:
    """Launch the MHKiT-DOLFyN application."""
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # Dark Fusion theme — the only Qt style that fully respects custom QPalette
    app.setStyle("Fusion")
    app.setPalette(theme.build_palette())

    _set_app_icon(app)

    # Show splash
    splash = SplashScreen()
    splash.show()
    app.processEvents()

    # Staged initialization
    window = MainWindow()

    stages = [
        (50, "Building interface...", window.init_stage_ui),
        (90, "Restoring settings...", window.init_stage_restore),
    ]

    def run_stage(index: int = 0) -> None:
        if index < len(stages):
            percent, message, fn = stages[index]
            splash.set_progress(percent, message)
            fn()
            QTimer.singleShot(0, lambda: run_stage(index + 1))
        else:
            splash.set_progress(100, "Ready")
            splash.finish(window)
            window.show()
            log.info("%s v%s started on %s", APP_NAME, APP_VERSION, sys.platform)

    QTimer.singleShot(0, lambda: run_stage(0))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
