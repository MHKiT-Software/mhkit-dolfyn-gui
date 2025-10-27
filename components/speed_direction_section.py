"""
Step 4: Calculate Speed and Direction Section
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QMessageBox
from PyQt6.QtCore import pyqtSignal
from .widgets import CollapsibleSection


class SpeedDirectionSection(QWidget):
    """Step 4: Calculate speed and direction"""

    calculationComplete = pyqtSignal()

    def __init__(self, workflow_state, parent=None):
        super().__init__(parent)
        self.state = workflow_state
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.section = CollapsibleSection("Step 4: Speed and Direction")

        btn = QPushButton("Calculate Speed & Direction")
        btn.clicked.connect(self.calculate_speed_direction)
        self.section.add_widget(btn)

        self.status = QLabel()
        self.section.add_widget(self.status)

        self.results_label = QLabel()
        self.section.add_widget(self.results_label)

        layout.addWidget(self.section)

    def calculate_speed_direction(self):
        """Calculate U_mag and U_dir"""
        if self.state.ds_avg is None:
            QMessageBox.warning(self, "No Averaged Data",
                              "Please complete averaging (Step 3) first.")
            return

        try:
            self.state.ds_avg['U_mag'] = self.state.ds_avg.velds.U_mag
            self.state.ds_avg['U_dir'] = self.state.ds_avg.velds.U_dir

            # Statistics
            u_mag_mean = float(self.state.ds_avg['U_mag'].mean().values)
            u_mag_max = float(self.state.ds_avg['U_mag'].max().values)
            u_mag_min = float(self.state.ds_avg['U_mag'].min().values)
            u_dir_mean = float(self.state.ds_avg['U_dir'].mean().values)

            results = (
                f"Results:\n"
                f"├─ Speed: Mean={u_mag_mean:.2f} m/s, "
                f"Max={u_mag_max:.2f} m/s, Min={u_mag_min:.2f} m/s\n"
                f"└─ Direction: Mean={u_dir_mean:.1f}° (from true North)"
            )

            self.results_label.setText(results)
            self.status.setText("✓ Speed and direction calculated")

            self.calculationComplete.emit()

        except Exception as e:
            self.status.setText(f"✗ Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed:\n{str(e)}")