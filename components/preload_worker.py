"""
Background worker for preloading heavy imports
"""

from PyQt6.QtCore import QThread, pyqtSignal


class PreloadWorker(QThread):
    """Preload heavy libraries in background to speed up first use"""

    finished = pyqtSignal(bool, str)  # Success, message

    def run(self):
        try:
            # Import heavy libraries
            import mhkit.dolfyn.io.api
            import mhkit.dolfyn.adp.api
            import mhkit.dolfyn
            import matplotlib.pyplot

            self.finished.emit(True, "Libraries preloaded")

        except Exception as e:
            self.finished.emit(False, f"Preload warning: {str(e)}")