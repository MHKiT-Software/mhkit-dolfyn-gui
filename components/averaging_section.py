"""
Step 3: Data Averaging Section
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QMessageBox
from PyQt6.QtCore import pyqtSignal
from .widgets import CollapsibleSection, ParameterInput


class AveragingSection(QWidget):
    """Step 3: Bin average data into time ensembles"""

    averagingComplete = pyqtSignal()

    def __init__(self, workflow_state, parent=None):
        super().__init__(parent)
        self.state = workflow_state
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.section = CollapsibleSection("Step 3: Data Averaging")

        self.averaging_window = ParameterInput(
            label="Averaging Window",
            unit="seconds",
            default=300.0,
            min_val=10.0,
            max_val=3600.0,
            decimals=1,
            tooltip="Duration of each time bin (300s = 5 min)",
            param_type="float"
        )
        self.section.add_widget(self.averaging_window)

        self.sample_rate = ParameterInput(
            label="Sample Rate",
            unit="Hz",
            default=1.0,
            min_val=0.1,
            max_val=10.0,
            decimals=2,
            tooltip="Auto-detected from dataset",
            param_type="float"
        )
        self.section.add_widget(self.sample_rate)

        self.bin_size_label = QLabel("Calculated Bin Size: N/A")
        self.section.add_widget(self.bin_size_label)

        btn = QPushButton("Apply Averaging")
        btn.clicked.connect(self.apply_averaging)
        self.section.add_widget(btn)

        self.status = QLabel()
        self.section.add_widget(self.status)

        layout.addWidget(self.section)

    def apply_averaging(self):
        """Apply bin averaging"""
        if not self.state.has_dataset():
            QMessageBox.warning(self, "No Dataset", "Please load dataset first.")
            return

        try:
            from mhkit.dolfyn.adp import api

            window = self.averaging_window.get_value()
            fs = self.sample_rate.get_value()

            # Auto-detect sample rate
            if hasattr(self.state.ds, 'fs'):
                fs = float(self.state.ds.fs)
                self.sample_rate.set_value(fs)

            n_bin = int(fs * window)
            self.bin_size_label.setText(f"Calculated Bin Size: {n_bin} samples")

            self.state.avg_tool = api.ADPBinner(n_bin=n_bin, fs=fs)
            self.state.ds_avg = self.state.avg_tool.bin_average(self.state.ds)

            n_ensembles = len(self.state.ds_avg['time'])
            self.status.setText(f"✓ Averaged into {n_ensembles} ensembles ({window}s bins)")

            self.state.parameters['averaging_window'] = window
            self.state.parameters['sample_rate'] = fs

            self.averagingComplete.emit()

        except Exception as e:
            self.status.setText(f"✗ Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to average:\n{str(e)}")