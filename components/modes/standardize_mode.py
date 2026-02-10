"""
Standardize Mode - Simple batch standardizer for ADCP/ADV files to NetCDF
"""

from pathlib import Path
from typing import List

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QTextEdit,
    QGroupBox,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QRadioButton,
    QButtonGroup,
    QProgressBar,
    QScrollArea,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPalette

from ..batch_processor import (
    BatchStandardizeWorker,
    StandardizeOptions,
    PartitionMethod,
    OutputNamer,
)
from ..widgets import CollapsibleSection
from ..help_system import InfoButton


# Supported file extensions (both cases for case-sensitive filesystems)
SUPPORTED_EXTENSIONS = [
    ".VEC",
    ".vec",
    ".WPR",
    ".wpr",
    ".AD2CP",
    ".ad2cp",
    ".000",
    ".PD0",
    ".pd0",
    ".ENX",
    ".enx",
    ".ENR",
    ".enr",
]


class TurbulenceStatsGroup(QWidget):
    """Group of turbulence statistics checkboxes with Select All functionality"""

    statsChanged = pyqtSignal()

    # Define available statistics with descriptions
    STATS = {
        "dudz": ("dudz (du/dz)", "Vertical shear of eastward velocity"),
        "dvdz": ("dvdz (dv/dz)", "Vertical shear of northward velocity"),
        "dwdz": ("dwdz (dw/dz)", "Vertical shear of vertical velocity"),
        "shear_squared": (
            "Shear Squared (S2)",
            "Total horizontal shear magnitude squared",
        ),
        "reynolds_stress_4beam": (
            "Reynolds Stress (4-beam)",
            "Stress tensor from 4-beam configuration",
        ),
        "reynolds_stress_5beam": (
            "Reynolds Stress (5-beam)",
            "Enhanced stress tensor from 5-beam configuration",
        ),
        "dissipation_rate_LT83": (
            "Dissipation Rate (LT83)",
            "TKE dissipation via Lumley-Terray spectral method",
        ),
        "dissipation_rate_SF": (
            "Dissipation Rate (SF)",
            "TKE dissipation via structure function method",
        ),
        "friction_velocity": (
            "Friction Velocity",
            "Approximate friction velocity from shear stress",
        ),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.checkboxes = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Select All / Deselect All buttons
        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self.deselect_all)
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(deselect_all_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Checkboxes in a grid with info buttons
        grid = QGridLayout()
        row = 0
        col = 0

        # Map STATS keys to help_system function keys (some differ)
        help_key_map = {
            "reynolds_stress_5beam": "stress_tensor_5beam",  # Different name in help system
        }

        for key, (label, tooltip) in self.STATS.items():
            # Container for checkbox + info button
            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(2)

            cb = QCheckBox(label)
            cb.setToolTip(tooltip)
            cb.stateChanged.connect(self.statsChanged.emit)
            self.checkboxes[key] = cb
            container_layout.addWidget(cb)

            # Add info button (use mapped key if exists)
            help_key = help_key_map.get(key, key)
            info_btn = InfoButton(help_key)
            container_layout.addWidget(info_btn)
            container_layout.addStretch()

            grid.addWidget(container, row, col)

            col += 1
            if col >= 2:  # 2 columns
                col = 0
                row += 1

        layout.addLayout(grid)

    def select_all(self):
        for cb in self.checkboxes.values():
            cb.setChecked(True)

    def deselect_all(self):
        for cb in self.checkboxes.values():
            cb.setChecked(False)

    def get_selected(self) -> dict:
        """Get dictionary of stat_name: bool for all stats"""
        return {key: cb.isChecked() for key, cb in self.checkboxes.items()}


class FileListWidget(QWidget):
    """Widget showing list of files to process with status in a table view"""

    # Signal emitted when files are removed
    filesChanged = pyqtSignal()

    # Status display text (professional, no emojis)
    STATUS_TEXT = {
        "pending": "Pending",
        "processing": "Processing...",
        "success": "Complete",
        "failed": "Failed",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files = []
        self.statuses = {}  # filepath -> (status, message)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Tree widget with columns
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["File", "Status"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setMaximumHeight(150)

        # Column sizing
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.tree)

        # Remove button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setEnabled(False)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.remove_btn.setToolTip("Remove selected files from the list")
        btn_layout.addWidget(self.remove_btn)
        layout.addLayout(btn_layout)

        # Enable remove button when selection changes
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self):
        """Enable/disable remove button based on selection"""
        has_selection = len(self.tree.selectedItems()) > 0
        self.remove_btn.setEnabled(has_selection)

    def _remove_selected(self):
        """Remove selected files from the list"""
        selected = self.tree.selectedItems()
        if not selected:
            return

        # Get filepaths to remove
        to_remove = set()
        for item in selected:
            filepath = item.data(0, Qt.ItemDataRole.UserRole)
            if filepath:
                to_remove.add(filepath)

        # Remove from internal lists
        self.files = [f for f in self.files if f not in to_remove]
        for f in to_remove:
            self.statuses.pop(f, None)

        self._update_display()
        self.filesChanged.emit()

    def set_files(self, files: List[str]):
        """Set the list of files"""
        self.files = list(files)
        self.statuses = {f: ("pending", "") for f in files}
        self._update_display()

    def get_files(self) -> List[str]:
        """Get the current list of files"""
        return self.files.copy()

    def update_file_status(self, filepath: str, status: str, message: str = ""):
        """Update status for a specific file"""
        # Find by filename match since we may get just the name
        for f in self.files:
            if Path(f).name == filepath or f == filepath:
                self.statuses[f] = (status, message)
                break
        self._update_display()

    def _update_display(self):
        """Refresh the tree display"""
        self.tree.clear()

        for f in self.files:
            name = Path(f).name
            status, msg = self.statuses.get(f, ("pending", ""))

            # Create tree item
            item = QTreeWidgetItem()
            item.setText(0, name)
            item.setToolTip(0, f)  # Full path as tooltip

            # Status text
            status_text = self.STATUS_TEXT.get(status, status)
            if msg and status == "failed":
                status_text = f"Failed: {msg}"
            item.setText(1, status_text)

            # Store full path for later retrieval
            item.setData(0, Qt.ItemDataRole.UserRole, f)

            self.tree.addTopLevelItem(item)

        # Show placeholder if empty
        if not self.files:
            item = QTreeWidgetItem()
            item.setText(0, "No files selected")
            item.setFlags(Qt.ItemFlag.NoItemFlags)  # Not selectable
            self.tree.addTopLevelItem(item)


class StandardizeMode(QWidget):
    """
    Simple standardization mode for batch standardizing ADCP/ADV files to NetCDF

    Features:
    - Single file or folder selection
    - Time partitioning options
    - Output file naming scheme
    - Turbulence statistics selection
    - Batch progress tracking
    - Error resilience (skip and continue)
    """

    standardizeStarted = pyqtSignal()
    standardizeCompleted = pyqtSignal(dict)  # summary

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files_to_process = []
        self.worker = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Create scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)

        # Header Section
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 15)
        header_layout.setSpacing(2)

        # Main title: MHKiT DOLFyN
        main_title = QLabel("MHKiT DOLFyN")
        main_title_font = QFont()
        main_title_font.setPointSize(20)
        main_title_font.setBold(True)
        main_title.setFont(main_title_font)
        main_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(main_title)

        # Subtitle: Doppler Oceanographic Library for PythoN
        acronym_label = QLabel("Doppler Oceanographic Library for PythoN")
        acronym_font = QFont()
        acronym_font.setPointSize(10)
        acronym_font.setItalic(True)
        acronym_label.setFont(acronym_font)
        acronym_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Use muted color for subtitle
        palette = acronym_label.palette()
        muted_color = palette.color(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText
        )
        acronym_label.setStyleSheet(f"color: {muted_color.name()};")
        header_layout.addWidget(acronym_label)

        # Separator space
        header_layout.addSpacing(10)

        # Tool description
        tool_title = QLabel("ADCP/ADV to NetCDF Standardizer")
        tool_font = QFont()
        tool_font.setPointSize(14)
        tool_font.setBold(True)
        tool_title.setFont(tool_font)
        tool_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(tool_title)

        tool_subtitle = QLabel(
            "Standardize Nortek and RDI files with optional averaging and turbulence statistics"
        )
        tool_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(tool_subtitle)

        content_layout.addWidget(header_widget)

        # Step 1: File Selection
        content_layout.addWidget(self._create_file_selection_section())

        # Step 2: Velocity Statistics (recommended, on by default)
        content_layout.addWidget(self._create_velocity_section())

        # Step 3: Averaging Specification (optional)
        content_layout.addWidget(self._create_averaging_section())

        # Step 4: Turbulence Specification (optional)
        content_layout.addWidget(self._create_turbulence_section())

        # Step 5: Output Specification
        content_layout.addWidget(self._create_output_section())

        # Step 6: Standardize Button
        self.standardize_btn = QPushButton("Standardize Files")
        self.standardize_btn.setEnabled(False)
        self.standardize_btn.setMinimumHeight(45)
        btn_font = QFont()
        btn_font.setPointSize(12)
        btn_font.setBold(True)
        self.standardize_btn.setFont(btn_font)
        self.standardize_btn.clicked.connect(self.start_standardize)
        content_layout.addWidget(self.standardize_btn)

        # Progress Section
        content_layout.addWidget(self._create_progress_section())

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _create_file_selection_section(self) -> QWidget:
        """Create file selection group"""
        group = QGroupBox("Step 1: Select Files to Standardize")
        layout = QVBoxLayout()

        # Input type selection
        input_type_layout = QHBoxLayout()
        self.single_file_radio = QRadioButton("Single File")
        self.folder_radio = QRadioButton("Folder (Batch)")
        self.single_file_radio.setChecked(True)

        input_type_layout.addWidget(self.single_file_radio)
        input_type_layout.addWidget(self.folder_radio)
        input_type_layout.addStretch()
        layout.addLayout(input_type_layout)

        # File/folder selection
        select_layout = QHBoxLayout()
        self.input_path = QLineEdit()
        self.input_path.setReadOnly(True)
        self.input_path.setPlaceholderText("No file or folder selected")

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_input)

        select_layout.addWidget(self.input_path, stretch=1)
        select_layout.addWidget(self.browse_btn)
        layout.addLayout(select_layout)

        # Supported formats info
        formats_label = QLabel(
            "Supported formats: .ad2cp, .VEC, .wpr, .PD0, .000, .ENX, .ENR"
        )
        formats_label.setStyleSheet("color: #666; font-size: 11px;")
        formats_label.setToolTip(
            "<b>Supported Instruments</b><br><br>"
            "<b>Nortek:</b><br>"
            "&nbsp;&nbsp;- Signature series (.ad2cp)<br>"
            "&nbsp;&nbsp;- Vector ADV (.VEC)<br>"
            "&nbsp;&nbsp;- AWAC (.wpr)<br><br>"
            "<b>Teledyne RDI:</b><br>"
            "&nbsp;&nbsp;- Workhorse, Sentinel, etc. (.PD0, .000)<br>"
            "&nbsp;&nbsp;- WinRiver processed ensembles (.ENX)<br>"
            "&nbsp;&nbsp;- WinRiver raw ensembles (.ENR)<br><br>"
            "<i>See MHKiT DOLfYN documentation for full details.</i>"
        )
        layout.addWidget(formats_label)

        # File list
        self.file_list = FileListWidget()
        layout.addWidget(self.file_list)

        # Options
        self.userdata_cb = QCheckBox("Read userdata.json files (if available)")
        self.userdata_cb.setChecked(True)
        self.userdata_cb.setToolTip(
            "Look for userdata.json files alongside ADCP files for metadata.\n"
            "These files can contain deployment info, coordinate offsets, etc."
        )
        layout.addWidget(self.userdata_cb)

        nens_layout = QHBoxLayout()
        nens_layout.addWidget(QLabel("Limit ensembles (0 = read all):"))
        self.nens_spin = QSpinBox()
        self.nens_spin.setMinimum(0)
        self.nens_spin.setMaximum(1000000)
        self.nens_spin.setValue(0)
        self.nens_spin.setToolTip(
            "Limit the number of pings/ensembles to read. 0 = read entire file."
        )
        nens_layout.addWidget(self.nens_spin)
        nens_layout.addStretch()
        layout.addLayout(nens_layout)

        group.setLayout(layout)
        return group

    def _create_velocity_section(self) -> QWidget:
        """Create velocity statistics section"""
        self.velocity_section = CollapsibleSection(
            "Step 2: Velocity Statistics Specification", expanded=True
        )

        # Enable checkbox
        self.compute_velds = QCheckBox("Compute velocity statistics (velds accessor)")
        self.compute_velds.setChecked(True)
        self.compute_velds.setToolTip(
            "Computes standard velocity statistics from raw (u, v) velocity components. "
            "\tU_mag - Water speed (horizontal velocity magnitude)\n"
            "\tU_dir - Flow direction (with respect to u, v directions in original data)\n"
        )
        self.compute_velds.stateChanged.connect(
            lambda state: self.velocity_section.set_active(
                state == Qt.CheckState.Checked.value
            )
        )
        self.velocity_section.add_widget(self.compute_velds)

        # Description
        desc_label = QLabel(
            "Computes standard velocity statistics from raw velocity (u, v) components. "
            "Adds water speed (U_mag) and flow direction (U_dir) to output files."
        )
        desc_label.setWordWrap(True)
        self.velocity_section.add_widget(desc_label)

        # Set initial active state
        self.velocity_section.set_active(True)

        return self.velocity_section

    def _create_output_section(self) -> QWidget:
        """Create output specification section"""
        section = CollapsibleSection("Step 5: Output Specification", expanded=False)

        # Output directory
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Output Directory:"))
        self.output_dir = QLineEdit()
        self.output_dir.setPlaceholderText("Same as input (default)")
        self.output_dir.setToolTip(
            "Leave empty to save in the same directory as input files"
        )
        dir_btn = QPushButton("Browse...")
        dir_btn.clicked.connect(self._browse_output_dir)
        dir_layout.addWidget(self.output_dir, stretch=1)
        dir_layout.addWidget(dir_btn)
        section.add_layout(dir_layout)

        # Time partitioning
        partition_group = QGroupBox("Time Partitioning")
        partition_layout = QVBoxLayout()

        self.partition_group = QButtonGroup(self)

        self.partition_none = QRadioButton(
            "No partition (single output file per input)"
        )
        self.partition_none.setChecked(True)
        self.partition_group.addButton(self.partition_none)
        partition_layout.addWidget(self.partition_none)

        duration_layout = QHBoxLayout()
        self.partition_duration = QRadioButton("Split by duration:")
        self.partition_group.addButton(self.partition_duration)
        duration_layout.addWidget(self.partition_duration)
        self.duration_hours = QDoubleSpinBox()
        self.duration_hours.setMinimum(0.1)
        self.duration_hours.setMaximum(168)  # 1 week
        self.duration_hours.setValue(1.0)
        self.duration_hours.setSuffix(" hours")
        self.duration_hours.setToolTip("Duration of each output file in hours")
        duration_layout.addWidget(self.duration_hours)
        duration_layout.addStretch()
        partition_layout.addLayout(duration_layout)

        tod_layout = QHBoxLayout()
        self.partition_tod = QRadioButton("Split by time of day:")
        self.partition_group.addButton(self.partition_tod)
        tod_layout.addWidget(self.partition_tod)
        self.tod_start = QSpinBox()
        self.tod_start.setMinimum(0)
        self.tod_start.setMaximum(23)
        self.tod_start.setValue(0)
        self.tod_start.setSuffix(":00")
        tod_layout.addWidget(self.tod_start)
        tod_layout.addWidget(QLabel("to"))
        self.tod_end = QSpinBox()
        self.tod_end.setMinimum(1)
        self.tod_end.setMaximum(24)
        self.tod_end.setValue(24)
        self.tod_end.setSuffix(":00")
        tod_layout.addWidget(self.tod_end)
        tod_layout.addStretch()
        partition_layout.addLayout(tod_layout)

        ens_layout = QHBoxLayout()
        self.partition_ensemble = QRadioButton("Split by ensemble count:")
        self.partition_group.addButton(self.partition_ensemble)
        ens_layout.addWidget(self.partition_ensemble)
        self.ensemble_count = QSpinBox()
        self.ensemble_count.setMinimum(100)
        self.ensemble_count.setMaximum(100000)
        self.ensemble_count.setValue(1000)
        self.ensemble_count.setToolTip("Number of ensembles per output file")
        ens_layout.addWidget(self.ensemble_count)
        ens_layout.addWidget(QLabel("ensembles"))
        ens_layout.addStretch()
        partition_layout.addLayout(ens_layout)

        partition_group.setLayout(partition_layout)
        section.add_widget(partition_group)

        # Output naming scheme
        naming_group = QGroupBox("Output File Naming")
        naming_layout = QVBoxLayout()

        pattern_layout = QHBoxLayout()
        pattern_layout.addWidget(QLabel("Pattern:"))
        self.naming_pattern = QLineEdit()
        self.naming_pattern.setText("{input_name}.nc")
        self.naming_pattern.setToolTip(
            "Output filename pattern with tokens:\n"
            "  {input_name} - Original filename without extension\n"
            "  {date} - YYYY-MM-DD format\n"
            "  {time} - HH-MM-SS format\n"
            "  {datetime} - YYYY-MM-DD_HH-MM-SS\n"
            "  {partition} - Partition number (001, 002, ...)\n"
            "  {duration} - Duration in hours"
        )
        self.naming_pattern.textChanged.connect(self._update_naming_preview)
        pattern_layout.addWidget(self.naming_pattern, stretch=1)
        naming_layout.addLayout(pattern_layout)

        # Token help
        tokens_label = QLabel(
            "<small>Tokens: {input_name}, {date}, {time}, {datetime}, {partition}, {duration}</small>"
        )
        tokens_label.setTextFormat(Qt.TextFormat.RichText)
        naming_layout.addWidget(tokens_label)

        # Preview (use palette for dark mode compatibility)
        preview_layout = QHBoxLayout()
        preview_layout.addWidget(QLabel("Preview:"))
        self.naming_preview = QLabel("Sig1000_tidal.nc")
        palette = self.naming_preview.palette()
        muted_color = palette.color(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText
        )
        self.naming_preview.setStyleSheet(
            f"color: {muted_color.name()}; font-style: italic;"
        )
        preview_layout.addWidget(self.naming_preview, stretch=1)
        naming_layout.addLayout(preview_layout)

        naming_group.setLayout(naming_layout)
        section.add_widget(naming_group)

        return section

    def _create_averaging_section(self) -> QWidget:
        """Create averaging specification section"""
        self.averaging_section = CollapsibleSection(
            "Step 3: Averaging Specification (Optional)", expanded=False
        )

        # Description
        desc_label = QLabel(
            "Average data into time bins to reduce data volume and compute "
            "ensemble statistics. Useful for long deployments."
        )
        desc_label.setWordWrap(True)
        self.averaging_section.add_widget(desc_label)

        # Checkbox with info button for ADPBinner
        avg_layout = QHBoxLayout()
        self.apply_averaging = QCheckBox("Apply bin averaging before saving")
        self.apply_averaging.setChecked(False)
        self.apply_averaging.setToolTip(
            "Average data into time bins using ADPBinner/ADVBinner.\n"
            "This reduces data volume and computes ensemble statistics."
        )
        self.apply_averaging.stateChanged.connect(
            lambda state: self.averaging_section.set_active(
                state == Qt.CheckState.Checked.value
            )
        )
        avg_layout.addWidget(self.apply_averaging)
        avg_layout.addWidget(InfoButton("ADPBinner"))
        avg_layout.addStretch()
        self.averaging_section.add_layout(avg_layout)

        # Averaging window with info button for bin_average
        window_layout = QHBoxLayout()
        window_layout.addWidget(QLabel("Averaging Window:"))
        self.averaging_window = QDoubleSpinBox()
        self.averaging_window.setMinimum(10)
        self.averaging_window.setMaximum(3600)
        self.averaging_window.setValue(300)
        self.averaging_window.setSuffix(" seconds")
        self.averaging_window.setToolTip(
            "Duration of each time bin (300s = 5 minutes is typical)"
        )
        window_layout.addWidget(self.averaging_window)
        window_layout.addWidget(InfoButton("bin_average"))
        window_layout.addStretch()
        self.averaging_section.add_layout(window_layout)

        return self.averaging_section

    def _create_turbulence_section(self) -> QWidget:
        """Create turbulence specification section"""
        self.turbulence_section = CollapsibleSection(
            "Step 4: Turbulence Specification (Optional)", expanded=False
        )

        info_label = QLabel(
            "Select turbulence statistics to compute and save. "
            "These require bin-averaged data and may increase processing time."
        )
        info_label.setWordWrap(True)
        self.turbulence_section.add_widget(info_label)

        self.turbulence_stats = TurbulenceStatsGroup()
        self.turbulence_stats.statsChanged.connect(self._update_turbulence_active_state)
        self.turbulence_section.add_widget(self.turbulence_stats)

        return self.turbulence_section

    def _update_turbulence_active_state(self):
        """Update turbulence section indicator based on selected stats"""
        selected = self.turbulence_stats.get_selected()
        any_selected = any(selected.values())
        self.turbulence_section.set_active(any_selected)

    def _create_progress_section(self) -> QWidget:
        """Create progress tracking section"""
        group = QGroupBox("Progress")
        layout = QVBoxLayout()

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Current file label
        self.current_file_label = QLabel("Ready")
        layout.addWidget(self.current_file_label)

        # Summary
        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

        # Log
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        self.log_text.setPlaceholderText("Standardization log will appear here...")
        layout.addWidget(self.log_text)

        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_standardize)
        layout.addWidget(self.cancel_btn)

        group.setLayout(layout)
        return group

    def _browse_input(self):
        """Browse for input file or folder"""
        if self.single_file_radio.isChecked():
            filename, _ = QFileDialog.getOpenFileName(
                self,
                "Select ADCP/ADV File",
                "",
                "ADCP/ADV Files (*.VEC *.vec *.WPR *.wpr *.AD2CP *.ad2cp *.000 *.PD0 *.pd0 *.ENX *.enx *.ENR *.enr);;All Files (*.*)",
            )
            if filename:
                self.input_path.setText(filename)
                self.files_to_process = [filename]
                self.file_list.set_files([filename])
                self.standardize_btn.setEnabled(True)
        else:
            folder = QFileDialog.getExistingDirectory(
                self, "Select Folder Containing ADCP/ADV Files"
            )
            if folder:
                self.input_path.setText(folder)
                # Find all supported files
                folder_path = Path(folder)
                files = []
                for ext in SUPPORTED_EXTENSIONS:
                    files.extend(folder_path.glob(f"*{ext}"))
                    files.extend(folder_path.glob(f"**/*{ext}"))  # Recursive

                # Remove duplicates and sort
                files = sorted(set(str(f) for f in files))
                self.files_to_process = files
                self.file_list.set_files(files)

                if files:
                    self.standardize_btn.setEnabled(True)
                    self.log_text.setPlainText(f"Found {len(files)} file(s) to process")
                else:
                    self.standardize_btn.setEnabled(False)
                    self.log_text.setPlainText("No supported files found in folder")

    def _browse_output_dir(self):
        """Browse for output directory"""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder:
            self.output_dir.setText(folder)

    def _update_naming_preview(self):
        """Update the naming pattern preview"""
        pattern = self.naming_pattern.text()
        preview = OutputNamer.preview(pattern)
        self.naming_preview.setText(preview)

    def _get_standardize_options(self) -> StandardizeOptions:
        """Build StandardizeOptions from UI state"""
        options = StandardizeOptions()

        # Basic options
        options.use_userdata = self.userdata_cb.isChecked()
        options.nens = self.nens_spin.value()

        # Averaging
        options.apply_averaging = self.apply_averaging.isChecked()
        options.averaging_window = self.averaging_window.value()
        options.compute_velds = self.compute_velds.isChecked()

        # Time partitioning
        if self.partition_none.isChecked():
            options.partition_method = PartitionMethod.NONE
        elif self.partition_duration.isChecked():
            options.partition_method = PartitionMethod.DURATION
            options.partition_duration_hours = self.duration_hours.value()
        elif self.partition_tod.isChecked():
            options.partition_method = PartitionMethod.TIME_OF_DAY
            options.partition_start_hour = self.tod_start.value()
            options.partition_end_hour = self.tod_end.value()
        elif self.partition_ensemble.isChecked():
            options.partition_method = PartitionMethod.ENSEMBLE_COUNT
            options.partition_ensemble_count = self.ensemble_count.value()

        # Output
        options.output_pattern = self.naming_pattern.text()
        output_dir = self.output_dir.text().strip()
        options.output_directory = output_dir if output_dir else None

        # Turbulence statistics
        options.turbulence_stats = self.turbulence_stats.get_selected()

        return options

    def start_standardize(self):
        """Start the batch standardization process"""
        if not self.files_to_process:
            QMessageBox.warning(self, "No Files", "Please select files to standardize.")
            return

        # Get options
        options = self._get_standardize_options()

        # Disable UI
        self.standardize_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.browse_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_text.clear()

        # Reset file statuses
        self.file_list.set_files(self.files_to_process)

        # Create and start worker
        self.worker = BatchStandardizeWorker(self.files_to_process, options)
        self.worker.batchStarted.connect(self._on_batch_started)
        self.worker.fileStarted.connect(self._on_file_started)
        self.worker.fileProgress.connect(self._on_file_progress)
        self.worker.fileCompleted.connect(self._on_file_completed)
        self.worker.batchCompleted.connect(self._on_batch_completed)
        self.worker.start()

        self.standardizeStarted.emit()

    def _cancel_standardize(self):
        """Cancel the current standardization"""
        if self.worker:
            self.worker.cancel()
            self.log_text.append("Cancellation requested...")

    def _on_batch_started(self, total: int):
        """Handle batch start"""
        self.progress_bar.setMaximum(total)
        self.log_text.append(f"Starting standardization of {total} file(s)...")

    def _on_file_started(self, filename: str, current: int, total: int):
        """Handle file start"""
        self.current_file_label.setText(f"Processing: {filename} ({current}/{total})")
        self.progress_bar.setValue(current - 1)
        self.file_list.update_file_status(filename, "processing")

    def _on_file_progress(self, filename: str, message: str):
        """Handle file progress update"""
        self.log_text.append(f"  {message}")

    def _on_file_completed(
        self, filename: str, success: bool, message: str, output_files: list
    ):
        """Handle file completion"""
        if success:
            self.file_list.update_file_status(filename, "success")
            self.log_text.append(f"[OK] {filename}: {message}")
        else:
            self.file_list.update_file_status(filename, "failed", message)
            self.log_text.append(f"[ERR] {filename}: {message}")

    def _on_batch_completed(self, summary: dict):
        """Handle batch completion"""
        self.standardize_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.browse_btn.setEnabled(True)
        self.progress_bar.setValue(self.progress_bar.maximum())

        # Build summary message
        total = summary["total"]
        success_count = len(summary["success"])
        failed_count = len(summary["failed"])

        if summary.get("cancelled"):
            self.current_file_label.setText("Standardization cancelled")
        else:
            self.current_file_label.setText("Standardization complete")

        self.summary_label.setText(
            f"Completed: {success_count} successful, {failed_count} failed out of {total} files"
        )

        if failed_count > 0:
            self.log_text.append("\n--- Failed Files ---")
            for filepath, error in summary["failed"]:
                self.log_text.append(f"  {Path(filepath).name}: {error}")

        self.log_text.append(f"\n{'=' * 50}")
        self.log_text.append(
            f"Batch standardization finished: {success_count}/{total} successful"
        )

        self.standardizeCompleted.emit(summary)
