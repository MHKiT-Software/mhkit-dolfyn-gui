"""Status-bar widget showing process RSS and current read/save activity.

Polls ``psutil.Process().memory_info().rss`` on a configurable interval
and asks the parent window for an ``ActivityState`` snapshot so the
readout combines memory and progress in one label, e.g.
``RAM: 412 MB · Reading 3/27``.

The poll interval is provided by the caller (the main window pulls it
from :class:`Settings`) so the Preferences dialog can change it live.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import psutil
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class ActivityState:
    """Snapshot of read/save activity provided by the main window."""

    reads_active: int
    reads_total: int  # active + queued + completed in the current batch
    saves_done: int
    saves_total: int


def _format_bytes(rss: int) -> str:
    mb = rss / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.0f} MB"


def _format_label(rss: int, activity: ActivityState) -> str:
    parts = [f"Memory Usage: {_format_bytes(rss)}"]
    if activity.reads_total > 0 and activity.reads_active > 0:
        parts.append(f"Reading {activity.reads_active}/{activity.reads_total}")
    if activity.saves_total > 0:
        parts.append(f"Saving {activity.saves_done}/{activity.saves_total}")
    return " · ".join(parts)


class MemoryIndicator(QLabel):
    """QLabel that periodically renders RAM + activity."""

    def __init__(
        self,
        activity_provider: Callable[[], ActivityState],
        interval_ms: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._activity_provider = activity_provider
        self._process = psutil.Process()

        self.setText("Memory Usage: …")
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._tick()

    def set_interval(self, interval_ms: int) -> None:
        """Update the polling interval at runtime.

        Called by the main window when the user changes the value in
        Preferences.
        """
        self._timer.setInterval(interval_ms)

    def _tick(self) -> None:
        try:
            rss = int(self._process.memory_info().rss)
        except Exception:
            return
        try:
            activity = self._activity_provider()
        except Exception:
            activity = ActivityState(0, 0, 0, 0)
        self.setText(_format_label(rss, activity))

    def closeEvent(self, event: QCloseEvent) -> None:  # pragma: no cover - Qt lifecycle
        self._timer.stop()
        super().closeEvent(event)
