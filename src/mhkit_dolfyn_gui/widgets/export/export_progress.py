"""Export progress widget: progress bar + status label."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from mhkit_dolfyn_gui.styles import theme


class ExportProgressWidget(QWidget):
    """Progress bar + status label. Hidden until ``set_progress`` is called."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.layout.no_margin)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setStyleSheet(theme.progress_bar)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        self._status_label.hide()
        layout.addWidget(self._status_label)

    def reset(self) -> None:
        self._progress_bar.hide()
        self._progress_bar.setValue(0)
        self._status_label.hide()

    def set_progress(self, value: int) -> None:
        self._progress_bar.show()
        self._progress_bar.setValue(value)

    def set_status(self, message: str, *, is_error: bool = False) -> None:
        self._status_label.setText(message)
        self._status_label.setStyleSheet(theme.status_label(is_error=is_error))
        self._status_label.show()
