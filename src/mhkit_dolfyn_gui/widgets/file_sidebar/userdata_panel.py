"""Global userdata.json picker — label + browse/edit/clear/help buttons."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from mhkit_dolfyn_gui.styles import theme
from mhkit_dolfyn_gui.widgets.userdata_editor import UserdataEditor

log = logging.getLogger(__name__)


class UserDataPanel(QFrame):
    """Picker for the optional global userdata.json sidecar.

    Source of truth for the global userdata path. Emits ``path_changed`` when
    the user changes it via browse/edit/clear (not when the host calls
    ``set_path`` programmatically).
    """

    path_changed = Signal(str)  # path string ("" if cleared)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._path: Path | None = None
        self._last_dir = str(Path.home())

        v = QVBoxLayout(self)
        v.setContentsMargins(6, 4, 6, 4)
        v.setSpacing(theme.layout.spacing_xs)

        title = QLabel("Custom Deployment Metadata <code>[userdata.json]</code>")
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setStyleSheet("font-weight: bold;")
        title.setToolTip(
            "Optional mhkit.dolfyn userdata.json sidecar — supplies declination, "
            "lat/lon, depth, orientation, salinity, and any custom attributes. "
            "A sibling <stem>.userdata.json next to an input file overrides the global."
        )
        v.addWidget(title)

        ud_row = QHBoxLayout()
        ud_row.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel("(none)")
        self._label.setStyleSheet(f"color: {theme.text.muted};")
        self._label.setToolTip("No global userdata.json selected")
        ud_row.addWidget(self._label, stretch=1)

        self._help_btn = QToolButton()
        self._help_btn.setText("?")
        self._help_btn.setToolTip("What is userdata.json?")
        self._help_btn.clicked.connect(self._on_help)
        ud_row.addWidget(self._help_btn)

        self._edit_btn = QToolButton()
        self._edit_btn.setText("Edit")
        self._edit_btn.setToolTip("Create or edit the global userdata.json")
        self._edit_btn.clicked.connect(self._on_edit)
        ud_row.addWidget(self._edit_btn)

        self._browse_btn = QToolButton()
        self._browse_btn.setText("\u2026")
        self._browse_btn.setToolTip("Browse for an existing global userdata.json")
        self._browse_btn.clicked.connect(self._on_browse)
        ud_row.addWidget(self._browse_btn)

        self._clear_btn = QToolButton()
        self._clear_btn.setText("\u2715")
        self._clear_btn.setToolTip("Clear global userdata.json")
        self._clear_btn.clicked.connect(self._on_clear)
        ud_row.addWidget(self._clear_btn)

        v.addLayout(ud_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def path(self) -> Path | None:
        return self._path

    def set_path(self, path: str) -> None:
        """Update the displayed path. Does not emit ``path_changed``."""
        if path:
            p = Path(path)
            self._path = p
            self._label.setText(p.name)
            self._label.setToolTip(str(p))
            self._label.setStyleSheet("")
        else:
            self._path = None
            self._label.setText("(none)")
            self._label.setToolTip("No global userdata.json selected")
            self._label.setStyleSheet(f"color: {theme.text.muted};")

    # ------------------------------------------------------------------

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select global userdata.json",
            self._last_dir,
            "userdata.json (*.json);;All Files (*)",
        )
        if not path:
            return
        self._last_dir = str(Path(path).parent)
        self.set_path(path)
        self.path_changed.emit(path)
        log.info("Global userdata set: %s", path)

    def _on_clear(self) -> None:
        self.set_path("")
        self.path_changed.emit("")
        log.info("Global userdata cleared")

    def _on_edit(self) -> None:
        saved = UserdataEditor.open_for(self, path=self._path, allow_save_as=True)
        if saved is None:
            return
        self.set_path(str(saved))
        self.path_changed.emit(str(saved))

    def _on_help(self) -> None:
        QMessageBox.information(
            self,
            "About userdata.json",
            "<p><b>userdata.json</b> is an mhkit.dolfyn sidecar that supplies "
            "deployment metadata the binary file cannot record.</p>"
            "<p>The most common use is <b>declination</b> — without it, ENU "
            "rotations point to magnetic north, not true north. Other supported "
            "fields: lat, lon, h_deploy, orientation, salinity, plus arbitrary "
            "custom attributes.</p>"
            "<p>Resolution order per file:<br>"
            "1. Per-file <code>&lt;stem&gt;.userdata.json</code> next to the input<br>"
            "2. Global userdata.json (this picker)<br>"
            "3. None</p>"
            "<p>Use <b>Edit</b> to create or modify the global file. Right-click "
            "a row in the file list to edit a per-file sidecar.</p>",
            QMessageBox.StandardButton.Ok,
        )
