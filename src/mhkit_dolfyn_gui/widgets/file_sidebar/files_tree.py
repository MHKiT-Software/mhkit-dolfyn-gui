"""QTreeWidget subclass with drag-and-drop support and an empty placeholder."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QWidget,
)

from mhkit_dolfyn_gui.constants import SUPPORTED_EXTENSIONS
from mhkit_dolfyn_gui.styles import theme
from mhkit_dolfyn_gui.widgets.file_sidebar.constants import (
    COL_CONVERT,
    COL_FILE,
    COL_REMOVE,
    COL_STATUS,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent


class FilesTreeWidget(QTreeWidget):
    """Tree widget with drag-and-drop, an empty-state placeholder,
    and a left-accent highlight on the selected row.
    """

    files_dropped = Signal(list)  # list[Path]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setColumnCount(4)
        self.setHeaderLabels(["Convert", "File", "Status", ""])
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        header = self.header()
        header.setSectionResizeMode(COL_CONVERT, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_FILE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_REMOVE, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(COL_REMOVE, 24)
        header.setStretchLastSection(False)

        accent = theme.accent.primary
        self.setStyleSheet(
            "QTreeWidget { border: 1px solid #444; }"
            "QTreeWidget::item { padding: 3px 2px; border: none; }"
            "QTreeWidget::item:selected {"
            "  background: rgba(33, 150, 243, 0.14);"
            "  color: palette(text);"
            f"  border-left: 3px solid {accent};"
            "}"
            "QTreeWidget::item:!selected { border-left: 3px solid transparent; }"
        )

        self._placeholder = QLabel("Drop files here or click Add Files", self.viewport())
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(
            f"color: {theme.text.hint}; font-size: {theme.fonts.size_md};"
        )
        self._placeholder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._update_placeholder()

    # -- placeholder management ---------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._placeholder.setGeometry(self.viewport().rect())

    def _update_placeholder(self) -> None:
        self._placeholder.setVisible(self.topLevelItemCount() == 0)

    def addTopLevelItem(self, item):
        super().addTopLevelItem(item)
        self._update_placeholder()

    def takeTopLevelItem(self, index):
        result = super().takeTopLevelItem(index)
        self._update_placeholder()
        return result

    def clear(self) -> None:
        super().clear()
        self._update_placeholder()

    # -- drag and drop -------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime: QMimeData | None = event.mimeData()
        if mime is not None and mime.hasUrls():
            event.acceptProposedAction()
            self._set_drag_active(True)
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        mime = event.mimeData()
        if mime is not None and mime.hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_drag_active(False)
        mime: QMimeData | None = event.mimeData()
        if mime is None:
            return
        paths: list[Path] = []
        for url in mime.urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                paths.append(path)
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()

    def _set_drag_active(self, active: bool) -> None:
        accent = theme.accent.primary
        border = f"2px dashed {accent}" if active else "1px solid #444"
        self.setStyleSheet(
            f"QTreeWidget {{ border: {border}; }}"
            "QTreeWidget::item { padding: 3px 2px; border: none; }"
            "QTreeWidget::item:selected {"
            "  background: rgba(33, 150, 243, 0.14);"
            "  color: palette(text);"
            f"  border-left: 3px solid {accent};"
            "}"
            "QTreeWidget::item:!selected { border-left: 3px solid transparent; }"
        )
