"""Form-based editor for mhkit.dolfyn ``userdata.json`` sidecar files.

Provides ``UserdataEditor.open_for(parent, path, allow_save_as)`` which
loads (or starts blank), lets the user edit known fields plus arbitrary
custom attributes, and writes pretty-printed JSON. Returns the saved
path on success or ``None`` if the dialog was cancelled.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from mhkit_dolfyn_gui.services.userdata_service import load_userdata

log = logging.getLogger(__name__)

# Fields with first-class form widgets. Order matches display order.
# Each entry: (json_key, label, suffix, kind)
#   kind ∈ {"float", "orientation"}
_FORM_FIELDS: list[tuple[str, str, str, str]] = [
    ("declination", "Declination", "°", "float"),
    ("lat", "Latitude", "°", "float"),
    ("lon", "Longitude", "°", "float"),
    ("h_deploy", "Deployment depth (h_deploy)", "m", "float"),
    ("orientation", "Orientation", "", "orientation"),
    ("salinity", "Salinity", "PSU", "float"),
]

_KNOWN_KEYS = frozenset(k for k, _, _, _ in _FORM_FIELDS)

_HELP_HTML = """
<p><b>What is userdata.json?</b></p>
<p>It is a small JSON sidecar that mhkit.dolfyn reads alongside an
instrument file to supply (or override) deployment metadata that the
binary file cannot record. The most common reason to use one is to
correct compass headings via <b>declination</b>: without it, ENU
rotations point to magnetic north, not true north.</p>
<p>Other supported fields:</p>
<ul>
<li><b>lat</b>, <b>lon</b> — deployment coordinates (decimal degrees)</li>
<li><b>h_deploy</b> — instrument depth/height in metres</li>
<li><b>orientation</b> — <code>up</code> or <code>down</code></li>
<li><b>salinity</b> — PSU, used for sound-speed correction</li>
</ul>
<p>Anything not in the form goes into the <b>Custom attributes</b> tab
and is copied verbatim into the dataset's attributes.</p>
"""


def _parse_value(text: str) -> Any:
    """Parse a value-cell string. Try JSON literal first, fall back to
    plain string. Empty string → empty string (kept as-is).
    """
    text = text.strip()
    if not text:
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _format_value(value: Any) -> str:
    """Render a value for display in the custom-attributes table."""
    if isinstance(value, str):
        return value
    return json.dumps(value)


class UserdataEditor(QDialog):
    """Modal editor for a single ``userdata.json`` file."""

    def __init__(
        self,
        path: Path | None,
        allow_save_as: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit userdata.json")
        self.setMinimumSize(520, 560)

        self._path = path
        self._allow_save_as = allow_save_as
        self._saved_path: Path | None = None

        root = QVBoxLayout(self)

        # Header help text + path indicator
        help_label = QLabel(_HELP_HTML)
        help_label.setWordWrap(True)
        help_label.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(help_label)

        self._path_label = QLabel()
        self._path_label.setStyleSheet("color: #888;")
        self._path_label.setWordWrap(True)
        root.addWidget(self._path_label)

        # Tabs: form + custom attrs
        self._tabs = QTabWidget()
        root.addWidget(self._tabs, stretch=1)

        self._tabs.addTab(self._build_form_tab(), "Standard fields")
        self._tabs.addTab(self._build_custom_tab(), "Custom attributes")

        # Buttons
        btn_row = QHBoxLayout()
        self._reload_btn = QPushButton("Reload")
        self._reload_btn.setToolTip("Discard changes and reload from disk")
        self._reload_btn.clicked.connect(self._on_reload)
        btn_row.addWidget(self._reload_btn)
        btn_row.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        if allow_save_as:
            self._save_as_btn = buttons.addButton(
                "Save As\u2026", QDialogButtonBox.ButtonRole.ActionRole
            )
            self._save_as_btn.clicked.connect(self._on_save_as)
        buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        btn_row.addWidget(buttons)
        root.addLayout(btn_row)

        self._refresh_path_label()
        self._load_from_disk_if_exists()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    @classmethod
    def open_for(
        cls,
        parent: QWidget | None,
        path: Path | None,
        allow_save_as: bool = True,
    ) -> Path | None:
        """Show the editor; return the path the user saved to, or None."""
        dlg = cls(path=path, allow_save_as=allow_save_as, parent=parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg._saved_path
        return None

    # ------------------------------------------------------------------
    # Tab construction
    # ------------------------------------------------------------------

    def _build_form_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._field_widgets: dict[str, QWidget] = {}

        for key, label, suffix, kind in _FORM_FIELDS:
            row_label = f"{label} ({suffix}):" if suffix else f"{label}:"
            if kind == "orientation":
                combo = QComboBox()
                combo.addItem("(unset)", "")
                combo.addItem("up", "up")
                combo.addItem("down", "down")
                self._field_widgets[key] = combo
                form.addRow(row_label, combo)
            else:
                edit = QLineEdit()
                edit.setPlaceholderText("(unset)")
                self._field_widgets[key] = edit
                form.addRow(row_label, edit)

        return widget

    def _build_custom_tab(self) -> QWidget:
        widget = QWidget()
        v = QVBoxLayout(widget)

        info = QLabel(
            "Free-form key/value pairs. Values are parsed as JSON when "
            "possible (numbers, booleans, lists), otherwise stored as text."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #888;")
        v.addWidget(info)

        self._custom_table = QTableWidget(0, 2)
        self._custom_table.setHorizontalHeaderLabels(["Key", "Value"])
        self._custom_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._custom_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        v.addWidget(self._custom_table, stretch=1)

        btns = QHBoxLayout()
        add_btn = QPushButton("+ Add row")
        add_btn.clicked.connect(lambda: self._custom_table.insertRow(self._custom_table.rowCount()))
        btns.addWidget(add_btn)
        remove_btn = QPushButton("- Remove selected")
        remove_btn.clicked.connect(self._on_remove_custom_row)
        btns.addWidget(remove_btn)
        btns.addStretch()
        v.addLayout(btns)

        return widget

    def _on_remove_custom_row(self) -> None:
        rows = sorted({idx.row() for idx in self._custom_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self._custom_table.removeRow(row)

    # ------------------------------------------------------------------
    # Load / populate
    # ------------------------------------------------------------------

    def _load_from_disk_if_exists(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            data = load_userdata(self._path)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid userdata.json", str(exc))
            return
        self._populate(data)

    def _populate(self, data: dict[str, Any]) -> None:
        # Standard fields
        for key, _label, _suffix, kind in _FORM_FIELDS:
            widget = self._field_widgets[key]
            value = data.get(key)
            if kind == "orientation":
                assert isinstance(widget, QComboBox)
                idx = widget.findData(str(value) if value else "")
                widget.setCurrentIndex(idx if idx >= 0 else 0)
            else:
                assert isinstance(widget, QLineEdit)
                widget.setText("" if value is None else str(value))

        # Custom attributes — anything not in the standard form
        self._custom_table.setRowCount(0)
        for key, value in data.items():
            if key in _KNOWN_KEYS:
                continue
            row = self._custom_table.rowCount()
            self._custom_table.insertRow(row)
            self._custom_table.setItem(row, 0, QTableWidgetItem(str(key)))
            self._custom_table.setItem(row, 1, QTableWidgetItem(_format_value(value)))

    def _on_reload(self) -> None:
        if self._path is None or not self._path.exists():
            QMessageBox.information(
                self, "Nothing to reload", "No file on disk yet.", QMessageBox.StandardButton.Ok
            )
            return
        self._load_from_disk_if_exists()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _collect(self) -> dict[str, Any] | None:
        """Collect form + table into a dict. Returns None on validation error."""
        out: dict[str, Any] = {}

        # Standard fields
        for key, label, _suffix, kind in _FORM_FIELDS:
            widget = self._field_widgets[key]
            if kind == "orientation":
                assert isinstance(widget, QComboBox)
                value = widget.currentData()
                if value:
                    out[key] = value
            else:
                assert isinstance(widget, QLineEdit)
                text = widget.text().strip()
                if not text:
                    continue
                try:
                    out[key] = float(text)
                except ValueError:
                    QMessageBox.warning(
                        self,
                        "Invalid value",
                        f"{label} must be a number (got {text!r}).",
                    )
                    return None

        # Custom attributes
        seen_keys: set[str] = set()
        for row in range(self._custom_table.rowCount()):
            key_item = self._custom_table.item(row, 0)
            value_item = self._custom_table.item(row, 1)
            key = key_item.text().strip() if key_item else ""
            if not key:
                continue
            if key in _KNOWN_KEYS:
                QMessageBox.warning(
                    self,
                    "Reserved key",
                    f"'{key}' belongs in the Standard fields tab. Remove the row.",
                )
                return None
            if key in seen_keys:
                QMessageBox.warning(self, "Duplicate key", f"Custom key '{key}' is duplicated.")
                return None
            seen_keys.add(key)
            value_text = value_item.text() if value_item else ""
            out[key] = _parse_value(value_text)

        return out

    def _on_save(self) -> None:
        data = self._collect()
        if data is None:
            return
        if self._path is None:
            self._on_save_as(data=data)
            return
        self._write(self._path, data)

    def _on_save_as(self, *_args: Any, data: dict[str, Any] | None = None) -> None:
        if data is None:
            data = self._collect()
            if data is None:
                return
        start = str(self._path) if self._path is not None else str(Path.home() / "userdata.json")
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save userdata.json", start, "userdata.json (*.json)"
        )
        if not path_str:
            return
        self._write(Path(path_str), data)

    def _write(self, path: Path, data: dict[str, Any]) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        except OSError as exc:
            QMessageBox.critical(self, "Write failed", f"Could not write {path}:\n{exc}")
            return
        self._saved_path = path
        self._path = path
        self._refresh_path_label()
        log.info("Wrote userdata.json: %s", path)
        self.accept()

    def _refresh_path_label(self) -> None:
        if self._path is None:
            self._path_label.setText("Path: <new file — choose location on save>")
        else:
            exists = " (exists)" if self._path.exists() else " (will be created)"
            self._path_label.setText(f"Path: {self._path}{exists}")
