"""User-facing Preferences dialog.

Single-page ``QDialog`` (no tabs) that exposes the values from
:class:`mhkit_dolfyn_gui.settings.Settings` so users can tune
machine-specific knobs (concurrency, RAM ceiling, poll cadence,
deployment-gap threshold) plus the persisted defaults that today are
edited inline in the sidebars (output dir, filename pattern, global
userdata.json). Sections are grouped with ``QGroupBox`` so the layout
stays scannable without tab navigation.

Apply / OK / Reset all to defaults
----------------------------------
- ``Apply`` writes every field to ``Settings`` and emits
  ``settings_changed`` so live consumers refresh in place.
- ``OK`` does an Apply followed by ``accept()``.
- ``Cancel`` discards in-flight edits and leaves the dialog.
- ``Reset all to defaults`` clears every preference key — getters then
  fall back to the constants defined in :mod:`mhkit_dolfyn_gui.constants`.
  The dialog widgets reload from those defaults but nothing is persisted
  until the user clicks Apply or OK.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from mhkit_dolfyn_gui.unit_conversions import bytes_to_gb, gb_to_bytes

if TYPE_CHECKING:
    from mhkit_dolfyn_gui.settings import Settings


# ---------------------------------------------------------------------------
# Per-field help blurbs. One sentence each, shown inline under the field.
# State the value's behavior and the default. No recommendations.
# ---------------------------------------------------------------------------
_HELP: dict[str, str] = {
    "max_concurrent_reads": (
        "Maximum number of FileReadWorker threads dispatched in parallel. Default 4."
    ),
    "worker_shutdown_timeout_ms": (
        "Maximum time to wait for an in-flight read worker to exit on shutdown "
        "before abandoning the thread. dolfyn.read() is uninterruptible. "
        "Default 5000 ms."
    ),
    "dataset_cache_max_bytes": (
        "Maximum memory used to keep recently-opened files loaded. When "
        "exceeded, the oldest loaded file is unloaded; clicking it again "
        "reloads it from disk. Default 2.0 GB."
    ),
    "dataset_cache_max_items": (
        "Maximum number of files kept loaded at once. Whichever limit "
        "(memory or count) is reached first unloads the oldest file. "
        "Default 10."
    ),
    "memory_poll_interval_ms": (
        "How often the status-bar memory usage display updates. Default 2000 ms."
    ),
    "time_gap_threshold_seconds": (
        "Gap between consecutive file end and start times above which the "
        "deployment overview flags a potential gap. Default 60 s."
    ),
}


def _add_field(
    form: QFormLayout,
    label: str,
    field: QWidget,
    help_text: str,
) -> None:
    """Append a form row plus a muted help line directly underneath."""
    form.addRow(label, field)
    help_label = QLabel(help_text)
    help_label.setWordWrap(True)
    help_label.setStyleSheet("color: gray; font-size: 11px; padding: 0 0 6px 0;")
    form.addRow(help_label)


class PreferencesDialog(QDialog):
    """Tabbed Preferences dialog.

    Holds a reference to the shared ``Settings`` instance so changes are
    written through the same path as elsewhere in the app.
    """

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setSpacing(12)

        # Sections stacked vertically — no tabs. Each builder returns a
        # QGroupBox so users can scan the whole dialog at once.
        root.addWidget(self._build_performance_section())
        root.addWidget(self._build_cache_section())
        root.addWidget(self._build_deployment_section())
        root.addWidget(self._build_defaults_section())

        # Bottom row: Reset all (left), OK / Cancel / Apply (right).
        button_row = QHBoxLayout()
        self._reset_btn = QPushButton("Reset all to defaults")
        self._reset_btn.setToolTip(
            "Restore every Preferences field to its built-in default. "
            "Changes are not persisted until you click Apply or OK."
        )
        self._reset_btn.clicked.connect(self._on_reset_to_defaults)
        button_row.addWidget(self._reset_btn)
        button_row.addStretch()

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        apply_btn = self._buttons.button(QDialogButtonBox.StandardButton.Apply)
        if apply_btn is not None:
            apply_btn.clicked.connect(self._on_apply)
        button_row.addWidget(self._buttons)

        root.addLayout(button_row)

        self._load_from_settings()

    # ------------------------------------------------------------------
    # Section construction
    # ------------------------------------------------------------------

    def _build_performance_section(self) -> QGroupBox:
        box = QGroupBox("Performance")
        form = QFormLayout(box)

        self._max_reads_spin = QSpinBox()
        self._max_reads_spin.setRange(1, 32)
        _add_field(
            form,
            "Max concurrent file reads:",
            self._max_reads_spin,
            _HELP["max_concurrent_reads"],
        )

        self._shutdown_timeout_spin = QSpinBox()
        self._shutdown_timeout_spin.setRange(500, 600_000)
        self._shutdown_timeout_spin.setSingleStep(500)
        self._shutdown_timeout_spin.setSuffix(" ms")
        _add_field(
            form,
            "Worker shutdown timeout:",
            self._shutdown_timeout_spin,
            _HELP["worker_shutdown_timeout_ms"],
        )

        return box

    def _build_cache_section(self) -> QGroupBox:
        box = QGroupBox("Memory")
        form = QFormLayout(box)

        self._cache_bytes_spin = QDoubleSpinBox()
        # 1-decimal display, so step in 0.5 GB increments — keeps the
        # spinner snap-to-grid clean.
        self._cache_bytes_spin.setRange(0.5, 64.0)
        self._cache_bytes_spin.setDecimals(1)
        self._cache_bytes_spin.setSingleStep(0.5)
        self._cache_bytes_spin.setSuffix(" GB")
        _add_field(
            form,
            "Maximum loaded files memory:",
            self._cache_bytes_spin,
            _HELP["dataset_cache_max_bytes"],
        )

        self._cache_items_spin = QSpinBox()
        self._cache_items_spin.setRange(1, 1000)
        _add_field(
            form,
            "Maximum loaded files:",
            self._cache_items_spin,
            _HELP["dataset_cache_max_items"],
        )

        self._poll_interval_spin = QSpinBox()
        self._poll_interval_spin.setRange(250, 60_000)
        self._poll_interval_spin.setSingleStep(250)
        self._poll_interval_spin.setSuffix(" ms")
        _add_field(
            form,
            "Memory display update interval:",
            self._poll_interval_spin,
            _HELP["memory_poll_interval_ms"],
        )

        return box

    def _build_deployment_section(self) -> QGroupBox:
        box = QGroupBox("Deployment")
        form = QFormLayout(box)

        self._gap_threshold_spin = QDoubleSpinBox()
        self._gap_threshold_spin.setRange(0.0, 86_400.0)
        self._gap_threshold_spin.setDecimals(1)
        self._gap_threshold_spin.setSuffix(" s")
        _add_field(
            form,
            "Time gap threshold:",
            self._gap_threshold_spin,
            _HELP["time_gap_threshold_seconds"],
        )

        return box

    def _build_defaults_section(self) -> QGroupBox:
        box = QGroupBox("Defaults")
        form = QFormLayout(box)

        # Output directory
        self._output_dir_edit = QLineEdit()
        self._output_dir_edit.setPlaceholderText("Default output directory")
        out_row = QHBoxLayout()
        out_row.setContentsMargins(0, 0, 0, 0)
        out_row.addWidget(self._output_dir_edit, stretch=1)
        out_browse = QPushButton("…")
        out_browse.setFixedWidth(32)
        out_browse.clicked.connect(self._on_browse_output_dir)
        out_row.addWidget(out_browse)
        out_container = QWidget()
        out_container.setLayout(out_row)
        form.addRow("Default output directory:", out_container)

        # Filename pattern
        self._pattern_edit = QLineEdit()
        self._pattern_edit.setPlaceholderText("{filename}_{start_date:%Y%m%d}.nc")
        self._pattern_edit.setToolTip(
            "Default filename pattern used by the export sidebar. "
            "Tokens: {filename}, {stem}, {start_date}, {end_date}, "
            "{index}, {profile}. Date tokens accept strftime format."
        )
        form.addRow("Default filename pattern:", self._pattern_edit)

        # Global userdata.json path
        self._userdata_edit = QLineEdit()
        self._userdata_edit.setPlaceholderText("Path to global userdata.json (optional)")
        ud_row = QHBoxLayout()
        ud_row.setContentsMargins(0, 0, 0, 0)
        ud_row.addWidget(self._userdata_edit, stretch=1)
        ud_browse = QPushButton("…")
        ud_browse.setFixedWidth(32)
        ud_browse.clicked.connect(self._on_browse_userdata)
        ud_row.addWidget(ud_browse)
        ud_clear = QPushButton("\u2715")
        ud_clear.setFixedWidth(32)
        ud_clear.setToolTip("Clear the global userdata.json path")
        ud_clear.clicked.connect(self._userdata_edit.clear)
        ud_row.addWidget(ud_clear)
        ud_container = QWidget()
        ud_container.setLayout(ud_row)
        form.addRow("Global userdata.json:", ud_container)

        hint = QLabel(
            "<i>These defaults are also editable inline in the sidebars; "
            "changes here keep both views in sync.</i>"
        )
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow(hint)

        return box

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def _load_from_settings(self) -> None:
        """Populate every widget from the current ``Settings`` values."""
        self._max_reads_spin.setValue(self._settings.max_concurrent_reads)
        self._shutdown_timeout_spin.setValue(self._settings.worker_shutdown_timeout_ms)

        self._cache_bytes_spin.setValue(bytes_to_gb(self._settings.dataset_cache_max_bytes))
        self._cache_items_spin.setValue(self._settings.dataset_cache_max_items)
        self._poll_interval_spin.setValue(self._settings.memory_poll_interval_ms)

        self._gap_threshold_spin.setValue(self._settings.time_gap_threshold_seconds)

        self._output_dir_edit.setText(self._settings.output_dir)
        self._pattern_edit.setText(self._settings.filename_pattern)
        self._userdata_edit.setText(self._settings.global_userdata_path)

    def _save_to_settings(self) -> None:
        """Write every widget value back into ``Settings``."""
        self._settings.max_concurrent_reads = self._max_reads_spin.value()
        self._settings.worker_shutdown_timeout_ms = self._shutdown_timeout_spin.value()

        self._settings.dataset_cache_max_bytes = gb_to_bytes(self._cache_bytes_spin.value())
        self._settings.dataset_cache_max_items = self._cache_items_spin.value()
        self._settings.memory_poll_interval_ms = self._poll_interval_spin.value()

        self._settings.time_gap_threshold_seconds = self._gap_threshold_spin.value()

        self._settings.output_dir = self._output_dir_edit.text().strip()
        self._settings.filename_pattern = self._pattern_edit.text().strip()
        self._settings.global_userdata_path = self._userdata_edit.text().strip()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_apply(self) -> None:
        self._save_to_settings()
        self._settings.notify_changed()

    def _on_accept(self) -> None:
        self._on_apply()
        self.accept()

    def _on_reset_to_defaults(self) -> None:
        """Clear stored overrides so widgets reload the constants.py defaults.

        Nothing is persisted until Apply / OK is clicked, so the user can
        still cancel the reset.
        """
        self._settings.reset_to_defaults()
        self._load_from_settings()

    def _on_browse_output_dir(self) -> None:
        start = self._output_dir_edit.text() or str(Path.home())
        dir_path = QFileDialog.getExistingDirectory(self, "Select Default Output Directory", start)
        if dir_path:
            self._output_dir_edit.setText(dir_path)

    def _on_browse_userdata(self) -> None:
        start = self._userdata_edit.text() or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select global userdata.json",
            start,
            "userdata.json (*.json);;All Files (*)",
        )
        if path:
            self._userdata_edit.setText(path)
