"""
MHKiT Dolfyn ADCP Standardizer - PyQt6 GUI
Simple GUI for standardizing ADCP files to NetCDF using mhkit.dolfyn
"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QProgressBar,
    QTextEdit,
    QGroupBox,
    QCheckBox,
    QSpinBox,
    QLineEdit,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont


class StandardizeWorker(QThread):
    """Background thread for file standardization to keep GUI responsive"""

    progress = pyqtSignal(str)  # Status messages
    finished = pyqtSignal(bool, str)  # Success flag, message

    def __init__(self, input_file, output_file, use_userdata, nens_value):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.use_userdata = use_userdata
        self.nens_value = nens_value

    def run(self):
        try:
            self.progress.emit("Importing mhkit.dolfyn...")
            import mhkit.dolfyn.io.api as dolfyn

            self.progress.emit(f"Reading ADCP file: {Path(self.input_file).name}")

            # Prepare kwargs
            kwargs = {}
            if self.nens_value > 0:
                kwargs['nens'] = self.nens_value

            # Read the ADCP file
            ds = dolfyn.read(
                self.input_file,
                userdata=self.use_userdata,
                **kwargs
            )

            self.progress.emit(f"Converting to NetCDF...")

            # Save as NetCDF
            # ds.to_netcdf(self.output_file)
            dolfyn.save(ds, self.output_file)

            # Get some basic info about the dataset
            dims_info = ", ".join([f"{k}={v}" for k, v in ds.dims.items()])
            vars_info = f"{len(ds.data_vars)} variables"

            success_msg = (
                f"✓ Conversion successful!\n\n"
                f"Output: {self.output_file}\n"
                f"Dimensions: {dims_info}\n"
                f"Variables: {vars_info}"
            )

            self.finished.emit(True, success_msg)

        except Exception as e:
            error_msg = f"✗ Conversion failed:\n\n{str(e)}"
            self.finished.emit(False, error_msg)


class ADCPConverterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.input_file = None
        self.output_file = None
        self.worker = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("MHKiT Dolfyn - ADCP Converter")
        self.setMinimumSize(700, 500)

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)

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
        subtitle.setStyleSheet("color: gray;")
        main_layout.addWidget(subtitle)

        # File selection group
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
        main_layout.addWidget(file_group)

        # Options group
        options_group = QGroupBox("Conversion Options")
        options_layout = QVBoxLayout()

        # Userdata checkbox
        self.userdata_cb = QCheckBox("Read userdata.json file (if available)")
        self.userdata_cb.setChecked(True)
        options_layout.addWidget(self.userdata_cb)

        # Nens (number of ensembles) option
        nens_layout = QHBoxLayout()
        nens_layout.addWidget(QLabel("Number of ensembles (0 = read all):"))
        self.nens_spin = QSpinBox()
        self.nens_spin.setMinimum(0)
        self.nens_spin.setMaximum(1000000)
        self.nens_spin.setValue(0)
        self.nens_spin.setToolTip("Limit the number of pings/ensembles to read. 0 means read entire file.")
        nens_layout.addWidget(self.nens_spin)
        nens_layout.addStretch()
        options_layout.addLayout(nens_layout)

        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)

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

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Status/log area
        status_label = QLabel("Status:")
        main_layout.addWidget(status_label)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(150)
        self.status_text.setPlainText("Ready. Select an ADCP file to begin.")
        main_layout.addWidget(self.status_text)

        # Stretch to push everything up
        main_layout.addStretch()

    def select_input_file(self):
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

            # Enable convert button
            self.convert_btn.setEnabled(True)
            self.status_text.setPlainText(f"Ready to convert: {input_path.name}")

    def select_output_file(self):
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
        if not self.input_file:
            return

        # Disable UI during conversion
        self.convert_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.status_text.clear()

        # Create and start worker thread
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
        self.status_text.append(message)

    def conversion_finished(self, success, message):
        self.progress_bar.setVisible(False)
        self.convert_btn.setEnabled(True)
        self.status_text.append("\n" + message)

        if success:
            self.convert_btn.setText("Convert Another File")


def main():
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle('Fusion')

    window = ADCPConverterGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
