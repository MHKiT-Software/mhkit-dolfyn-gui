"""
MHKiT Dolfyn ADCP Converter - Main Application
Clean, modular GUI for converting ADCP files and processing workflows
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTextEdit,
    QGroupBox, QCheckBox, QSpinBox, QLineEdit, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from components import (
    WorkflowState,
    ConversionWorker,
    PreloadWorker,
    QCSection,
    AveragingSection,
    SpeedDirectionSection,
    VisualizationSection
)


class ADCPConverterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.input_file = None
        self.output_file = None
        self.worker = None
        self.workflow_state = WorkflowState()
        self.preload_worker = None
        self.init_ui()
        self.start_preload()

    def init_ui(self):
        self.setWindowTitle("MHKiT Dolfyn - ADCP Converter")
        self.setMinimumSize(900, 800)

        # Central widget with scroll area
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Title
        title = QLabel("ADCP to NetCDF Converter")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Convert Nortek (.VEC, .wpr, .ad2cp) and RDI (.000, .PD0, .ENX) files to NetCDF")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(subtitle)

        # File selection
        main_layout.addWidget(self.create_file_selection_group())

        # Conversion options
        main_layout.addWidget(self.create_conversion_options_group())

        # Convert button
        self.convert_btn = QPushButton("Convert to NetCDF")
        self.convert_btn.setEnabled(False)
        self.convert_btn.setMinimumHeight(40)
        convert_font = QFont()
        convert_font.setPointSize(12)
        convert_font.setBold(True)
        self.convert_btn.setFont(convert_font)
        self.convert_btn.clicked.connect(self.start_conversion)
        main_layout.addWidget(self.convert_btn)

        # Status area
        status_label = QLabel("Status:")
        main_layout.addWidget(status_label)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(100)
        self.status_text.setPlainText("Ready. Select an ADCP file to begin.")
        main_layout.addWidget(self.status_text)

        # Workflow sections (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        workflow_widget = QWidget()
        workflow_layout = QVBoxLayout(workflow_widget)

        # Add workflow sections
        self.qc_section = QCSection(self.workflow_state)
        workflow_layout.addWidget(self.qc_section)

        self.averaging_section = AveragingSection(self.workflow_state)
        workflow_layout.addWidget(self.averaging_section)

        self.speed_dir_section = SpeedDirectionSection(self.workflow_state)
        workflow_layout.addWidget(self.speed_dir_section)

        self.viz_section = VisualizationSection(self.workflow_state)
        workflow_layout.addWidget(self.viz_section)

        workflow_layout.addStretch()

        scroll.setWidget(workflow_widget)
        main_layout.addWidget(scroll, stretch=1)

    def create_file_selection_group(self):
        """Create file selection group box"""
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout()

        # Input file
        input_layout = QHBoxLayout()
        self.input_label = QLineEdit()
        self.input_label.setReadOnly(True)
        self.input_label.setPlaceholderText("No input file selected")
        input_btn = QPushButton("Select ADCP File...")
        input_btn.clicked.connect(self.select_input_file)
        input_layout.addWidget(self.input_label, stretch=1)
        input_layout.addWidget(input_btn)
        file_layout.addLayout(input_layout)

        # Output file
        output_layout = QHBoxLayout()
        self.output_label = QLineEdit()
        self.output_label.setReadOnly(True)
        self.output_label.setPlaceholderText("Output will be auto-generated")
        output_btn = QPushButton("Change Output Location...")
        output_btn.clicked.connect(self.select_output_file)
        output_layout.addWidget(self.output_label, stretch=1)
        output_layout.addWidget(output_btn)
        file_layout.addLayout(output_layout)

        file_group.setLayout(file_layout)
        return file_group

    def create_conversion_options_group(self):
        """Create conversion options group box"""
        options_group = QGroupBox("Conversion Options")
        options_layout = QVBoxLayout()

        # Userdata checkbox
        self.userdata_cb = QCheckBox("Read userdata.json file (if available)")
        self.userdata_cb.setChecked(True)
        options_layout.addWidget(self.userdata_cb)

        # Nens option
        nens_layout = QHBoxLayout()
        nens_layout.addWidget(QLabel("Number of ensembles (0 = read all):"))
        self.nens_spin = QSpinBox()
        self.nens_spin.setMinimum(0)
        self.nens_spin.setMaximum(1000000)
        self.nens_spin.setValue(0)
        self.nens_spin.setToolTip("Limit pings/ensembles. 0 = read entire file.")
        nens_layout.addWidget(self.nens_spin)
        nens_layout.addStretch()
        options_layout.addLayout(nens_layout)

        options_group.setLayout(options_layout)
        return options_group

    def select_input_file(self):
        """Select input ADCP file"""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select ADCP File",
            "",
            "ADCP Files (*.VEC *.vec *.wpr *.ad2cp *.000 *.PD0 *.ENX *.enx);;All Files (*.*)"
        )

        if filename:
            self.input_file = filename
            self.input_label.setText(filename)

            # Auto-generate output filename
            input_path = Path(filename)
            self.output_file = str(input_path.with_suffix('.nc'))
            self.output_label.setText(self.output_file)

            self.convert_btn.setEnabled(True)
            self.status_text.setPlainText(f"Ready to convert: {input_path.name}")

    def select_output_file(self):
        """Select output NetCDF file location"""
        if not self.input_file:
            self.status_text.setPlainText("⚠ Please select an input file first.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save NetCDF File As",
            self.output_file or "",
            "NetCDF Files (*.nc);;All Files (*.*)"
        )

        if filename:
            self.output_file = filename
            self.output_label.setText(filename)

    def start_conversion(self):
        """Start ADCP file conversion"""
        if not self.input_file:
            return

        # Disable UI
        self.convert_btn.setEnabled(False)
        self.status_text.clear()

        # Create and start worker
        self.worker = ConversionWorker(
            self.input_file,
            self.output_file,
            self.userdata_cb.isChecked(),
            self.nens_spin.value()
        )
        self.worker.progress.connect(self.update_status)
        self.worker.finished.connect(self.conversion_finished)
        self.worker.start()

    def update_status(self, message):
        """Update status text"""
        self.status_text.append(message)

    def start_preload(self):
        """Start preloading heavy libraries in background"""
        self.preload_worker = PreloadWorker()
        self.preload_worker.finished.connect(self.preload_finished)
        self.preload_worker.start()

    def preload_finished(self, success, message):
        """Handle preload completion (silent, no UI update needed)"""
        # Libraries are now cached in memory for faster first use
        pass

    def conversion_finished(self, success, message, dataset):
        """Handle conversion completion"""
        self.convert_btn.setEnabled(True)
        self.status_text.append("\n" + message)

        if success and dataset is not None:
            self.convert_btn.setText("Convert Another File")
            # Load dataset into workflow state
            self.workflow_state.load_dataset(dataset)
            self.status_text.append("\n✓ Dataset loaded into workflow. Proceed to Step 2.")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = ADCPConverterGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()