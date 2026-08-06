"""Export configuration widget: output dir + pattern + file checklist + Export button."""

from __future__ import annotations

import contextlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from mhkit_dolfyn_gui.constants import STRFTIME_DOCS_URL
from mhkit_dolfyn_gui.models.filename_pattern import PATTERN_PRESETS, FilenamePattern
from mhkit_dolfyn_gui.models.me_filename import (
    ME_DATA_LEVELS,
    MENamingFields,
    build_me_filename,
    check_utc,
    format_temporal,
    resolve_fs,
    validate_me_fields,
    warn_me_fields,
)
from mhkit_dolfyn_gui.styles import theme

if TYPE_CHECKING:
    from mhkit_dolfyn_gui.models.file_item import FileItem

log = logging.getLogger(__name__)

_CUSTOM_LABEL = "Custom…"
_ME_PIPELINE_LABEL = "ME Data Pipeline"
_ME_PIPELINE_SENTINEL = "__ME_PIPELINE__"


class ExportConfigWidget(QWidget):
    """Output directory, filename pattern, file checklist, Export button.

    Owns the export configuration view only — the canonical file list and
    canonical check state live in :class:`FileListPanel`.

    Signals
    -------
    export_requested()
        The user clicked Export. ``MainWindow`` builds the save list.
    code_requested()
        The user clicked Show Code. ``MainWindow`` builds an equivalent
        Python script and shows it in a modal preview dialog. Gated by
        the same enablement as ``export_requested`` so the script only
        fires when a valid export would fire.
    user_toggled(int, bool)
        The user toggled a checkbox in *this* widget. Forwarded to the
        sidebar via :meth:`FileListPanel.set_item_checked`; the resulting
        ``check_state_changed`` then echoes back into :meth:`on_check_changed`.
        This one-way intent → canonical → echo loop terminates in O(1)
        thanks to the no-op guard in ``set_item_checked``.
    output_dir_changed(str)
        The user edited the output directory. Lets MainWindow persist the
        new default eagerly so the Preferences dialog reflects it.
    pattern_changed(str)
        The user edited the filename pattern (preset selection or custom
        text). Same persistence rationale as ``output_dir_changed``.
    """

    export_requested = Signal()
    code_requested = Signal()
    user_toggled = Signal(int, bool)
    output_dir_changed = Signal(str)
    pattern_changed = Signal(str)
    me_fields_changed = Signal()
    include_velds_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._file_items: list[FileItem] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.layout.no_margin)
        layout.setSpacing(theme.layout.spacing_md)

        # Output directory
        layout.addWidget(QLabel("Output directory:"))
        dir_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("Select directory…")
        # editingFinished fires on focus-out / Enter — broadcasts the new
        # value so MainWindow can persist it as the default.
        self._dir_edit.editingFinished.connect(self._on_dir_edited)
        dir_row.addWidget(self._dir_edit)
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(30)
        browse_btn.setToolTip("Browse for output directory")
        browse_btn.clicked.connect(self._on_browse)
        dir_row.addWidget(browse_btn)
        layout.addLayout(dir_row)

        # Pattern preset dropdown
        layout.addWidget(QLabel("Filename pattern:"))
        self._pattern_combo = QComboBox()
        for label, _ in PATTERN_PRESETS:
            self._pattern_combo.addItem(label)
        self._pattern_combo.addItem(_ME_PIPELINE_LABEL)
        self._pattern_combo.addItem(_CUSTOM_LABEL)
        self._me_combo_index = len(PATTERN_PRESETS)
        self._custom_combo_index = len(PATTERN_PRESETS) + 1
        self._pattern_combo.currentIndexChanged.connect(self._on_preset_changed)
        layout.addWidget(self._pattern_combo)

        # Custom pattern field (hidden unless Custom selected)
        self._custom_edit = QLineEdit()
        self._custom_edit.setPlaceholderText("{filename}_{start_date:%Y%m%d}.nc")
        self._custom_edit.textChanged.connect(self._on_pattern_changed)
        self._custom_edit.hide()
        layout.addWidget(self._custom_edit)

        # Token legend (hidden unless Custom selected)
        self._token_help = QLabel(
            "Tokens: <code>{filename}</code> · <code>{stem}</code> · "
            "<code>{start_date:%Y%m%d}</code> · <code>{end_date:%Y%m%d}</code> · "
            "<code>{index:03d}</code> · <code>{profile}</code><br>"
            f'Date tokens accept any <a href="{STRFTIME_DOCS_URL}">strftime</a> format. '
            "Filename must end with <code>.nc</code>."
        )
        self._token_help.setTextFormat(Qt.TextFormat.RichText)
        self._token_help.setWordWrap(True)
        self._token_help.setOpenExternalLinks(True)
        self._token_help.setStyleSheet("color: gray; font-size: 11px;")
        self._token_help.hide()
        layout.addWidget(self._token_help)

        # ME Data Pipeline controls (hidden unless ME mode selected)
        self._me_group = self._build_me_group()
        self._me_group.hide()
        layout.addWidget(self._me_group)

        # Live preview (hidden unless Custom selected and valid)
        self._preview_label = QLabel()
        self._preview_label.setWordWrap(True)
        self._preview_label.setStyleSheet("color: gray; font-size: 11px;")
        self._preview_label.hide()
        layout.addWidget(self._preview_label)

        # Validation error
        self._error_label = QLabel()
        self._error_label.setStyleSheet(theme.validation_error)
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        # Derived velocity fields (speed, direction, components) — orthogonal
        # to ME naming mode, so this lives at the top level, not in the ME group.
        self._include_velds = QCheckBox(
            "Include derived velocity fields (speed, direction, components)"
        )
        self._include_velds.setChecked(True)
        self._include_velds.setToolTip(
            "Adds speed, direction, and velocity-component fields computed "
            "from the raw velocity data (via mhkit.dolfyn)."
        )
        self._include_velds.toggled.connect(self.include_velds_changed.emit)
        layout.addWidget(self._include_velds)

        # File checklist
        files_group = QGroupBox("Files to export")
        files_layout = QVBoxLayout(files_group)
        files_layout.setContentsMargins(*theme.layout.panel_margin)
        self._file_list = QListWidget()
        self._file_list.setAlternatingRowColors(True)
        self._file_list.itemChanged.connect(self._on_file_check_changed)
        files_layout.addWidget(self._file_list)
        layout.addWidget(files_group, stretch=1)

        # Action buttons — Show Code and Export share one enablement gate
        # so the script preview only fires when a valid export would fire.
        button_row = QHBoxLayout()
        self._show_code_btn = QPushButton("Show &Code")
        self._show_code_btn.setToolTip(
            "Preview a Python script that reproduces this export using mhkit.dolfyn."
        )
        self._show_code_btn.clicked.connect(self.code_requested.emit)
        self._show_code_btn.setEnabled(False)
        button_row.addWidget(self._show_code_btn)

        self._export_btn = QPushButton("&Export")
        self._export_btn.clicked.connect(self.trigger_export)
        self._export_btn.setEnabled(False)
        button_row.addWidget(self._export_btn, stretch=1)
        layout.addLayout(button_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def output_dir(self) -> str:
        return self._dir_edit.text().strip()

    @output_dir.setter
    def output_dir(self, value: str) -> None:
        self._dir_edit.setText(value)

    @property
    def is_me_mode(self) -> bool:
        """True when the ME Data Pipeline naming mode is active."""
        return self._pattern_combo.currentIndex() == self._me_combo_index

    @property
    def pattern_text(self) -> str:
        idx = self._pattern_combo.currentIndex()
        if idx < len(PATTERN_PRESETS):
            return PATTERN_PRESETS[idx][1]
        if idx == self._me_combo_index:
            return _ME_PIPELINE_SENTINEL
        return self._custom_edit.text().strip()

    @pattern_text.setter
    def pattern_text(self, value: str) -> None:
        if value == _ME_PIPELINE_SENTINEL:
            self._pattern_combo.setCurrentIndex(self._me_combo_index)
            return
        for i, (_, template) in enumerate(PATTERN_PRESETS):
            if value == template:
                self._pattern_combo.setCurrentIndex(i)
                return
        self._pattern_combo.setCurrentIndex(self._custom_combo_index)
        self._custom_edit.setText(value)

    def set_file_items(self, items: list[FileItem]) -> None:
        self._file_items = items
        self._rebuild_file_list()
        self._update_export_enabled()
        if self.is_me_mode:
            fields = self._get_me_fields()
            self._update_me_temporal_preview(fields)
            self._update_me_tz_warning()

    def on_check_changed(self, index: int, checked: bool) -> None:
        """Display-only sync of checkbox state from the file sidebar.

        The file list panel is the canonical owner of check state; this slot
        only mirrors it into the export view's QListWidget. ``blockSignals``
        suppresses the redundant ``user_toggled`` round-trip that the item
        change would otherwise emit.
        """
        if not (0 <= index < self._file_list.count()):
            return
        item = self._file_list.item(index)
        if item is None:
            return
        self._file_list.blockSignals(True)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._file_list.blockSignals(False)
        self._update_export_enabled()

    def get_output_paths(self) -> list[tuple[int, int, Path]]:
        """Return ``(file_index, profile_index, output_path)`` for each
        dataset that should be exported.

        Multi-profile files yield one entry per non-empty profile. If the
        filename pattern contains ``{profile}``, it is rendered per-profile;
        otherwise ``_profileN`` is inserted before the suffix.

        When ME Data Pipeline mode is active, filenames are built by
        :func:`build_me_filename` instead of :class:`FilenamePattern`.
        """
        output_dir = Path(self.output_dir)
        result: list[tuple[int, int, Path]] = []

        if self.is_me_mode:
            self._get_me_output_paths(output_dir, result)
        else:
            self._get_pattern_output_paths(output_dir, result)

        return result

    def trigger_export(self) -> None:
        """Validate and emit ``export_requested`` (called by the Export button)."""
        if not self.output_dir:
            QMessageBox.warning(self, "No Output Directory", "Please select an output directory.")
            return

        if self.is_me_mode:
            fields = self._get_me_fields()
            errors = validate_me_fields(fields)
            if errors:
                QMessageBox.warning(self, "Invalid ME Fields", "\n".join(errors))
                return
        else:
            pattern = FilenamePattern(self.pattern_text)
            errors = pattern.validate()
            if errors:
                QMessageBox.warning(self, "Invalid Pattern", "\n".join(errors))
                return

        output_paths = self.get_output_paths()
        existing = [p for _, _, p in output_paths if p.exists()]
        if existing:
            names = "\n".join(f"  • {p.name}" for p in existing)
            reply = QMessageBox.question(
                self,
                "Overwrite Files?",
                f"The following files already exist:\n{names}\n\nOverwrite them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.export_requested.emit()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_browse(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self._dir_edit.text() or str(Path.home())
        )
        if dir_path:
            self._dir_edit.setText(dir_path)
            self._update_export_enabled()
            self.output_dir_changed.emit(dir_path)

    def _on_dir_edited(self) -> None:
        """User typed in the output dir field; broadcast the new value."""
        self.output_dir_changed.emit(self._dir_edit.text().strip())

    def _on_preset_changed(self, index: int) -> None:
        is_custom = index == self._custom_combo_index
        is_me = index == self._me_combo_index

        self._custom_edit.setVisible(is_custom)
        self._token_help.setVisible(is_custom)
        self._me_group.setVisible(is_me)

        if is_me:
            self._error_label.hide()
            self._preview_label.hide()
            self._on_me_field_changed()
        else:
            self._me_error_label.hide()
            self._me_warning_label.hide()
            self._me_preview.hide()
            self._me_temporal_auto.hide()
            self._me_tz_warning.hide()
            self._on_pattern_changed()

    def _on_pattern_changed(self) -> None:
        is_custom = self._pattern_combo.currentIndex() == self._custom_combo_index
        pattern = FilenamePattern(self.pattern_text)
        errors = pattern.validate()
        if errors:
            self._error_label.setText("\n".join(errors))
            self._error_label.show()
        else:
            self._error_label.hide()

        # Broadcast so MainWindow can persist the new default.
        self.pattern_changed.emit(self.pattern_text)

        # Live preview: only meaningful for custom patterns and when valid
        if is_custom and not errors:
            sample = next(
                (it for it in self._file_items if it.has_been_read),
                None,
            )
            if sample is not None:
                rendered = pattern.render(
                    filename=sample.filename,
                    start_date=sample.start_time,
                    end_date=sample.end_time,
                    index=1,
                    profile=1,
                )
                self._preview_label.setText(f"Preview: {sample.path.name} → {rendered}")
            else:
                rendered = pattern.render(
                    filename="example",
                    start_date=datetime(2024, 1, 15, 8, 0, 0),
                    end_date=datetime(2024, 1, 16, 12, 30, 0),
                    index=1,
                    profile=1,
                )
                self._preview_label.setText(f"Preview: {rendered}")
            self._preview_label.show()
        else:
            self._preview_label.hide()

        self._rebuild_file_list()
        self._update_export_enabled()

    def _on_file_check_changed(self, item: QListWidgetItem) -> None:
        row = self._file_list.row(item)
        if not (0 <= row < len(self._file_items)):
            return
        checked = item.checkState() == Qt.CheckState.Checked
        self._file_items[row].checked = checked
        self.user_toggled.emit(row, checked)
        self._update_export_enabled()

    def _rebuild_file_list(self) -> None:
        self._file_list.blockSignals(True)
        self._file_list.clear()

        if self.is_me_mode:
            self._rebuild_file_list_me()
        else:
            self._rebuild_file_list_pattern()

        self._file_list.blockSignals(False)

    def _rebuild_file_list_pattern(self) -> None:
        pattern = FilenamePattern(self.pattern_text)
        errors = pattern.validate()

        for i, item in enumerate(self._file_items):
            if item.has_been_read and not errors:
                rendered = pattern.render(
                    filename=item.filename,
                    start_date=item.start_time,
                    end_date=item.end_time,
                    index=i + 1,
                )
                text = f"{item.path.name}\n    \u2192 {rendered}"
            elif item.error:
                text = f"{item.path.name} (failed)"
            else:
                text = item.path.name

            li = QListWidgetItem(text)
            li.setFlags(li.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            li.setCheckState(Qt.CheckState.Checked if item.checked else Qt.CheckState.Unchecked)
            if not item.has_been_read and item.error:
                li.setFlags(li.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._file_list.addItem(li)

    def _rebuild_file_list_me(self) -> None:
        fields = self._get_me_fields()
        errors = validate_me_fields(fields)

        for item in self._file_items:
            if item.has_been_read and not errors:
                temporal = self._resolve_temporal_for_item(fields, item)
                start_dt = self._apply_tz_offset(item.start_time)
                if start_dt is not None:
                    rendered = build_me_filename(
                        fields,
                        temporal=temporal,
                        start_dt=start_dt,
                    )
                    text = f"{item.path.name}\n    \u2192 {rendered}"
                else:
                    text = f"{item.path.name} (no start time)"
            elif item.error:
                text = f"{item.path.name} (failed)"
            else:
                text = item.path.name

            li = QListWidgetItem(text)
            li.setFlags(li.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            li.setCheckState(Qt.CheckState.Checked if item.checked else Qt.CheckState.Unchecked)
            if not item.has_been_read and item.error:
                li.setFlags(li.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._file_list.addItem(li)

    def _update_export_enabled(self) -> None:
        has_dir = bool(self.output_dir)
        checked_count = sum(1 for it in self._file_items if it.checked and it.has_been_read)

        if self.is_me_mode:
            fields = self._get_me_fields()
            valid_pattern = not validate_me_fields(fields)
        else:
            pattern = FilenamePattern(self.pattern_text)
            valid_pattern = not pattern.validate()

        enabled = has_dir and checked_count > 0 and valid_pattern

        self._export_btn.setEnabled(enabled)
        self._show_code_btn.setEnabled(enabled)

        if enabled:
            noun = "File" if checked_count == 1 else "Files"
            self._export_btn.setText(f"&Export {checked_count} {noun} to .nc")
        else:
            self._export_btn.setText("&Export")

    # ------------------------------------------------------------------
    # ME Data Pipeline helpers
    # ------------------------------------------------------------------

    def _build_me_group(self) -> QGroupBox:
        """Create the ME Data Pipeline naming controls group."""
        group = QGroupBox("ME Data Pipeline Naming")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(*theme.layout.panel_margin)
        layout.setSpacing(theme.layout.spacing_md)

        # location_id
        layout.addWidget(QLabel("Location ID:"))
        self._me_location_id = QLineEdit()
        self._me_location_id.setPlaceholderText("e.g. axys1")
        self._me_location_id.setToolTip("Mandatory string identifying the data location")
        self._me_location_id.textChanged.connect(self._on_me_field_changed)
        layout.addWidget(self._me_location_id)

        # dataset_name
        layout.addWidget(QLabel("Dataset Name:"))
        self._me_dataset_name = QLineEdit()
        self._me_dataset_name.setPlaceholderText("e.g. adcp_vel")
        self._me_dataset_name.setToolTip("Mandatory string identifying the data type")
        self._me_dataset_name.textChanged.connect(self._on_me_field_changed)
        layout.addWidget(self._me_dataset_name)

        # qualifier
        layout.addWidget(QLabel("Qualifier (optional):"))
        self._me_qualifier = QLineEdit()
        self._me_qualifier.setPlaceholderText("e.g. raw")
        self._me_qualifier.setToolTip(
            "Optional qualifier to distinguish datasets from the same instrument"
        )
        self._me_qualifier.textChanged.connect(self._on_me_field_changed)
        layout.addWidget(self._me_qualifier)

        # data_level
        dl_row = QHBoxLayout()
        dl_row.addWidget(QLabel("Data Level:"))
        self._me_data_level = QComboBox()
        for level in ME_DATA_LEVELS:
            self._me_data_level.addItem(level)
        self._me_data_level.addItem("(omit)")
        self._me_data_level.setCurrentText("a1")
        self._me_data_level.currentIndexChanged.connect(self._on_me_field_changed)
        dl_row.addWidget(self._me_data_level)
        layout.addLayout(dl_row)

        # include_temporal checkbox + override field
        self._me_include_temporal = QCheckBox("Include temporal")
        self._me_include_temporal.setChecked(True)
        self._me_include_temporal.toggled.connect(self._on_me_temporal_toggled)
        layout.addWidget(self._me_include_temporal)

        self._me_temporal_override = QLineEdit()
        self._me_temporal_override.setPlaceholderText("Auto-detected (e.g. 10hz, 30s)")
        self._me_temporal_override.setToolTip(
            "Leave blank to auto-detect from sampling frequency; or type a value like 10hz, 30s, 5m"
        )
        self._me_temporal_override.textChanged.connect(self._on_me_field_changed)
        layout.addWidget(self._me_temporal_override)

        # Auto-detected temporal preview
        self._me_temporal_auto = QLabel()
        self._me_temporal_auto.setStyleSheet("color: gray; font-size: 11px;")
        self._me_temporal_auto.setWordWrap(True)
        self._me_temporal_auto.hide()
        layout.addWidget(self._me_temporal_auto)

        # UTC offset
        tz_row = QHBoxLayout()
        self._me_tz_warning = QLabel()
        self._me_tz_warning.setStyleSheet("color: #b8860b; font-size: 11px;")
        self._me_tz_warning.setWordWrap(True)
        self._me_tz_warning.hide()
        layout.addWidget(self._me_tz_warning)

        tz_row.addWidget(QLabel("UTC offset (hours):"))
        self._me_tz_offset = QSpinBox()
        self._me_tz_offset.setRange(-12, 14)
        self._me_tz_offset.setValue(0)
        self._me_tz_offset.setToolTip(
            "Hours to add to timestamps to convert to UTC. 0 means data is already UTC."
        )
        self._me_tz_offset.valueChanged.connect(self._on_me_field_changed)
        tz_row.addWidget(self._me_tz_offset)
        layout.addLayout(tz_row)

        # ME validation errors
        self._me_error_label = QLabel()
        self._me_error_label.setStyleSheet(theme.validation_error)
        self._me_error_label.setWordWrap(True)
        self._me_error_label.hide()
        layout.addWidget(self._me_error_label)

        # ME soft warnings
        self._me_warning_label = QLabel()
        self._me_warning_label.setStyleSheet("color: #b8860b; font-size: 11px;")
        self._me_warning_label.setWordWrap(True)
        self._me_warning_label.hide()
        layout.addWidget(self._me_warning_label)

        # ME live preview
        self._me_preview = QLabel()
        self._me_preview.setStyleSheet("color: gray; font-size: 11px;")
        self._me_preview.setWordWrap(True)
        self._me_preview.hide()
        layout.addWidget(self._me_preview)

        return group

    def _on_me_temporal_toggled(self, checked: bool) -> None:
        self._me_temporal_override.setVisible(checked)
        self._me_temporal_auto.setVisible(checked)
        self._on_me_field_changed()

    def _on_me_field_changed(self) -> None:
        """React to any ME field edit: re-validate, update preview, broadcast."""
        fields = self._get_me_fields()

        # Hard errors
        errors = validate_me_fields(fields)
        if errors:
            self._me_error_label.setText("\n".join(errors))
            self._me_error_label.show()
        else:
            self._me_error_label.hide()

        # Soft warnings
        warnings = warn_me_fields(fields)
        if warnings:
            self._me_warning_label.setText("\n".join(warnings))
            self._me_warning_label.show()
        else:
            self._me_warning_label.hide()

        # Auto-detected temporal from first loaded file
        self._update_me_temporal_preview(fields)

        # UTC warning from first loaded file
        self._update_me_tz_warning()

        # ME live preview
        if not errors:
            self._update_me_preview(fields)
        else:
            self._me_preview.hide()

        # Broadcast for persistence and rebuild file list
        self.pattern_changed.emit(self.pattern_text)
        self.me_fields_changed.emit()
        self._rebuild_file_list()
        self._update_export_enabled()

    def _get_me_fields(self) -> MENamingFields:
        """Read current ME field values from the widgets."""
        dl_text = self._me_data_level.currentText()
        return MENamingFields(
            location_id=self._me_location_id.text().strip(),
            dataset_name=self._me_dataset_name.text().strip(),
            qualifier=self._me_qualifier.text().strip(),
            data_level="" if dl_text == "(omit)" else dl_text,
            include_temporal=self._me_include_temporal.isChecked(),
            temporal_override=self._me_temporal_override.text().strip(),
        )

    def _get_item_attrs(self, item: FileItem) -> dict[str, object]:
        """Get the attrs dict from a FileItem (dataset or snapshot)."""
        if item.dataset is not None:
            return dict(item.dataset.attrs)
        if item.summary_snapshot is not None:
            return dict(item.summary_snapshot.attrs)
        return {}

    def _get_item_fs(self, item: FileItem) -> float | None:
        """Get sampling frequency for a FileItem from attrs or time coord."""
        attrs = self._get_item_attrs(item)
        fs_val = attrs.get("fs")
        if isinstance(fs_val, (int, float)):
            return float(fs_val)
        if isinstance(fs_val, str):
            try:
                return float(fs_val)
            except ValueError:
                pass

        # Fallback: median delta-t from time coordinate
        if item.dataset is not None and "time" in item.dataset.coords:
            time_values = item.dataset.coords["time"].values
            resolution = resolve_fs(None, time_values)
            return resolution.fs_hz

        return None

    def _resolve_temporal_for_item(self, fields: MENamingFields, item: FileItem) -> str:
        """Resolve the temporal string for a single file item."""
        if fields.temporal_override:
            return fields.temporal_override
        if not fields.include_temporal:
            return ""
        fs = self._get_item_fs(item)
        if fs is not None and fs > 0:
            return format_temporal(fs)
        return ""

    def _apply_tz_offset(self, dt: datetime | None) -> datetime | None:
        """Apply the UTC offset from the timezone spinbox."""
        if dt is None:
            return None
        offset_hours = self._me_tz_offset.value()
        if offset_hours == 0:
            return dt
        return dt + timedelta(hours=offset_hours)

    def _update_me_temporal_preview(self, fields: MENamingFields) -> None:
        """Show auto-detected temporal for the first loaded file."""
        if not fields.include_temporal or fields.temporal_override:
            self._me_temporal_auto.hide()
            return

        sample = next((it for it in self._file_items if it.has_been_read), None)
        if sample is None:
            self._me_temporal_auto.hide()
            return

        attrs = self._get_item_attrs(sample)
        fs_val = attrs.get("fs")
        attrs_fs: float | None = None
        if isinstance(fs_val, (int, float)):
            attrs_fs = float(fs_val)
        elif isinstance(fs_val, str):
            with contextlib.suppress(ValueError):
                attrs_fs = float(fs_val)

        time_values = None
        if sample.dataset is not None and "time" in sample.dataset.coords:
            time_values = sample.dataset.coords["time"].values

        resolution = resolve_fs(attrs_fs, time_values)
        if resolution.fs_hz is not None:
            temporal_str = format_temporal(resolution.fs_hz)
            source = f"from {'fs attr' if resolution.source == 'attrs' else 'median Δt'}"
            text = f"Auto-detected: {temporal_str} ({source}, fs={resolution.fs_hz:.4g} Hz)"
            if resolution.warning:
                text += f"\n⚠ {resolution.warning}"
            self._me_temporal_auto.setText(text)
            self._me_temporal_auto.show()
        else:
            self._me_temporal_auto.setText(
                f"⚠ {resolution.warning or 'Cannot determine sampling frequency'}"
            )
            self._me_temporal_auto.show()

    def _update_me_tz_warning(self) -> None:
        """Check UTC status from the first loaded file's attrs."""
        sample = next((it for it in self._file_items if it.has_been_read), None)
        if sample is None:
            self._me_tz_warning.hide()
            return

        attrs = self._get_item_attrs(sample)
        is_utc, msg = check_utc(attrs)
        if is_utc:
            self._me_tz_warning.hide()
        else:
            self._me_tz_warning.setText(
                f"⚠ {msg}\nME spec recommends UTC. Adjust the UTC offset above if needed."
            )
            self._me_tz_warning.show()

    def _update_me_preview(self, fields: MENamingFields) -> None:
        """Show a live preview of the ME filename for the first loaded file."""
        sample = next((it for it in self._file_items if it.has_been_read), None)
        if sample is None:
            # Show preview with placeholder values
            start_dt = datetime(2024, 1, 15, 8, 30, 0)
            temporal = fields.temporal_override or "10hz"
        else:
            start_dt_raw = sample.start_time
            if start_dt_raw is None:
                self._me_preview.hide()
                return
            start_dt = self._apply_tz_offset(start_dt_raw) or start_dt_raw
            temporal = self._resolve_temporal_for_item(fields, sample)

        rendered = build_me_filename(fields, temporal=temporal, start_dt=start_dt)
        if sample is not None:
            self._me_preview.setText(f"Preview: {sample.path.name} → {rendered}")
        else:
            self._me_preview.setText(f"Preview: {rendered}")
        self._me_preview.show()

    def _get_me_output_paths(
        self,
        output_dir: Path,
        result: list[tuple[int, int, Path]],
    ) -> None:
        """Build output paths using ME Data Pipeline naming."""
        fields = self._get_me_fields()

        for i, item in enumerate(self._file_items):
            if not item.has_been_read or not item.checked:
                continue

            start_dt_raw = item.start_time
            if start_dt_raw is None:
                log.warning("Skipping %s: no start time", item.path.name)
                continue
            start_dt = self._apply_tz_offset(start_dt_raw) or start_dt_raw
            temporal = self._resolve_temporal_for_item(fields, item)

            profile_sizes = item.profile_time_sizes
            if len(profile_sizes) <= 1:
                rendered = build_me_filename(
                    fields,
                    temporal=temporal,
                    start_dt=start_dt,
                )
                result.append((i, 0, output_dir / rendered))
                continue

            for p_idx, n_time in enumerate(profile_sizes):
                if n_time == 0:
                    log.info(
                        "Skipping empty profile %d of %s (no time samples)",
                        p_idx + 1,
                        item.path.name,
                    )
                    continue
                rendered = build_me_filename(
                    fields,
                    temporal=temporal,
                    start_dt=start_dt,
                    profile_suffix=f"profile_{p_idx + 1}",
                )
                result.append((i, p_idx, output_dir / rendered))

    def _get_pattern_output_paths(
        self,
        output_dir: Path,
        result: list[tuple[int, int, Path]],
    ) -> None:
        """Build output paths using the template-based FilenamePattern."""
        pattern_text = self.pattern_text
        pattern = FilenamePattern(pattern_text)
        has_profile_token = "{profile" in pattern_text

        for i, item in enumerate(self._file_items):
            if not item.has_been_read or not item.checked:
                continue
            profile_sizes = item.profile_time_sizes
            if len(profile_sizes) <= 1:
                rendered = pattern.render(
                    filename=item.filename,
                    start_date=item.start_time,
                    end_date=item.end_time,
                    index=i + 1,
                    profile=1,
                )
                result.append((i, 0, output_dir / rendered))
                continue

            for p_idx, n_time in enumerate(profile_sizes):
                if n_time == 0:
                    log.info(
                        "Skipping empty profile %d of %s (no time samples)",
                        p_idx + 1,
                        item.path.name,
                    )
                    continue
                rendered = pattern.render(
                    filename=item.filename,
                    start_date=item.start_time,
                    end_date=item.end_time,
                    index=i + 1,
                    profile=p_idx + 1,
                )
                if has_profile_token:
                    out = Path(rendered)
                else:
                    base = Path(rendered)
                    out = base.with_name(f"{base.stem}_profile{p_idx + 1}{base.suffix}")
                result.append((i, p_idx, output_dir / out))

    # ------------------------------------------------------------------
    # ME Data Pipeline: public properties for settings persistence
    # ------------------------------------------------------------------

    @property
    def me_location_id(self) -> str:
        return self._me_location_id.text().strip()

    @me_location_id.setter
    def me_location_id(self, value: str) -> None:
        self._me_location_id.setText(value)

    @property
    def me_dataset_name(self) -> str:
        return self._me_dataset_name.text().strip()

    @me_dataset_name.setter
    def me_dataset_name(self, value: str) -> None:
        self._me_dataset_name.setText(value)

    @property
    def me_qualifier(self) -> str:
        return self._me_qualifier.text().strip()

    @me_qualifier.setter
    def me_qualifier(self, value: str) -> None:
        self._me_qualifier.setText(value)

    @property
    def me_data_level(self) -> str:
        dl_text = self._me_data_level.currentText()
        return "" if dl_text == "(omit)" else dl_text

    @me_data_level.setter
    def me_data_level(self, value: str) -> None:
        if not value:
            self._me_data_level.setCurrentText("(omit)")
        else:
            self._me_data_level.setCurrentText(value)

    @property
    def me_include_temporal(self) -> bool:
        return self._me_include_temporal.isChecked()

    @me_include_temporal.setter
    def me_include_temporal(self, value: bool) -> None:
        self._me_include_temporal.setChecked(value)

    @property
    def include_velds(self) -> bool:
        return self._include_velds.isChecked()

    @include_velds.setter
    def include_velds(self, value: bool) -> None:
        self._include_velds.setChecked(value)

    @property
    def me_timezone_offset_hours(self) -> int:
        return self._me_tz_offset.value()

    @me_timezone_offset_hours.setter
    def me_timezone_offset_hours(self, value: int) -> None:
        self._me_tz_offset.setValue(value)
