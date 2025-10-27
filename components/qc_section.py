"""
Step 2: Quality Control and Data Preparation Section
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QMessageBox
)
from PyQt6.QtCore import pyqtSignal
from .widgets import CollapsibleSection, ParameterInput, MatplotlibCanvas


class QCSection(QWidget):
    """
    Quality Control and Data Preparation:
    - Set deployment height / range offset
    - Remove surface interference
    - Apply correlation filter
    - Rotate coordinate system
    """

    qcApplied = pyqtSignal()

    def __init__(self, workflow_state, parent=None):
        super().__init__(parent)
        self.state = workflow_state
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.section = CollapsibleSection("Step 2: Quality Control and Data Preparation")

        # 2.1: Set Deployment Height
        self._create_deployment_height_section()

        # 2.2: Remove Surface Interference
        self._create_surface_removal_section()

        # 2.3: Correlation Filter
        self._create_correlation_filter_section()

        # 2.4: Rotate Coordinate System
        self._create_rotation_section()

        layout.addWidget(self.section)

    def _create_deployment_height_section(self):
        """2.1: Set Deployment Height"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        label = QLabel("2.1: Set Deployment Height")
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        layout.addWidget(label)

        self.deployment_height = ParameterInput(
            label="Deployment Height",
            unit="m",
            default=0.6,
            min_val=0.0,
            max_val=100.0,
            decimals=2,
            tooltip="Height of ADCP transducers from seafloor",
            param_type="float"
        )
        layout.addWidget(self.deployment_height)

        btn = QPushButton("Apply Range Offset")
        btn.clicked.connect(self.apply_range_offset)
        layout.addWidget(btn)

        self.status_21 = QLabel()
        layout.addWidget(self.status_21)

        self.section.add_widget(widget)

    def _create_surface_removal_section(self):
        """2.2: Remove Surface Interference"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        label = QLabel("2.2: Remove Surface Interference")
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        layout.addWidget(label)

        self.salinity = ParameterInput(
            label="Salinity",
            unit="PSU",
            default=35.0,
            min_val=0.0,
            max_val=50.0,
            decimals=1,
            tooltip="Water salinity for depth calculation",
            param_type="float"
        )
        layout.addWidget(self.salinity)

        btn = QPushButton("Remove Surface Interference & Plot")
        btn.clicked.connect(self.remove_surface_interference)
        layout.addWidget(btn)

        self.status_22 = QLabel()
        layout.addWidget(self.status_22)

        self.canvas_22 = MatplotlibCanvas(width=8, height=4, dpi=80)
        self.canvas_22.setMinimumHeight(300)
        layout.addWidget(self.canvas_22)

        self.section.add_widget(widget)

    def _create_correlation_filter_section(self):
        """2.3: Correlation Filter"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        label = QLabel("2.3: Acoustic Correlation Filter")
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        layout.addWidget(label)

        self.correlation_threshold = ParameterInput(
            label="Correlation Threshold",
            unit="%",
            default=50,
            min_val=0,
            max_val=100,
            decimals=0,
            tooltip="Minimum correlation for valid data (30-50%)",
            param_type="int"
        )
        layout.addWidget(self.correlation_threshold)

        btn = QPushButton("Apply Filter & Plot")
        btn.clicked.connect(self.apply_correlation_filter)
        layout.addWidget(btn)

        self.status_23 = QLabel()
        layout.addWidget(self.status_23)

        self.canvas_23 = MatplotlibCanvas(width=8, height=4, dpi=80)
        self.canvas_23.setMinimumHeight(300)
        layout.addWidget(self.canvas_23)

        self.section.add_widget(widget)

    def _create_rotation_section(self):
        """2.4: Rotate Coordinate System"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        label = QLabel("2.4: Rotate Coordinate System")
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        layout.addWidget(label)

        self.declination = ParameterInput(
            label="Magnetic Declination",
            unit="deg",
            default=0.0,
            min_val=-180.0,
            max_val=180.0,
            decimals=1,
            tooltip="Magnetic declination angle (East +, West -)",
            param_type="float"
        )
        layout.addWidget(self.declination)

        coord_layout = QHBoxLayout()
        coord_layout.addWidget(QLabel("Target Coordinate System:"))
        self.coord_system = QComboBox()
        self.coord_system.addItems(["earth", "principal"])
        self.coord_system.setToolTip("earth = ENU, principal = streamwise")
        coord_layout.addWidget(self.coord_system)
        coord_layout.addStretch()
        layout.addLayout(coord_layout)

        btn = QPushButton("Apply Rotation")
        btn.clicked.connect(self.rotate_coordinates)
        layout.addWidget(btn)

        self.status_24 = QLabel()
        layout.addWidget(self.status_24)

        self.section.add_widget(widget)

    def apply_range_offset(self):
        """Apply deployment height"""
        if not self.state.has_dataset():
            QMessageBox.warning(self, "No Dataset", "Please convert an ADCP file first.")
            return

        try:
            from mhkit.dolfyn.adp import api

            offset = self.deployment_height.get_value()
            api.clean.set_range_offset(self.state.ds, offset)

            self.status_21.setText(f"✓ Range offset: {offset} m")
            self.state.parameters['deployment_height'] = offset

        except Exception as e:
            self.status_21.setText(f"✗ Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed:\n{str(e)}")

    def remove_surface_interference(self):
        """Remove surface interference"""
        if not self.state.has_dataset():
            QMessageBox.warning(self, "No Dataset", "Please convert first.")
            return

        try:
            from mhkit.dolfyn.adp import api

            salinity = self.salinity.get_value()

            api.clean.water_depth_from_pressure(self.state.ds, salinity=salinity)

            # Plot before removal
            self.canvas_22.clear()
            ax = self.canvas_22.get_axes(clear=True)
            if 'vel' in self.state.ds:
                self.state.ds['vel'][1].plot(ax=ax)
                ax.set_title("Velocity (before surface removal)")
            self.canvas_22.refresh()

            self.state.ds = api.clean.remove_surface_interference(self.state.ds)

            self.status_22.setText(f"✓ Surface removed (salinity: {salinity} PSU)")
            self.state.parameters['salinity'] = salinity

        except Exception as e:
            self.status_22.setText(f"✗ Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed:\n{str(e)}")

    def apply_correlation_filter(self):
        """Apply correlation filter"""
        if not self.state.has_dataset():
            QMessageBox.warning(self, "No Dataset", "Please convert first.")
            return

        try:
            from mhkit.dolfyn.adp import api

            thresh = self.correlation_threshold.get_value()

            # Plot correlation
            self.canvas_23.clear()
            ax = self.canvas_23.get_axes(clear=True)
            if 'corr' in self.state.ds:
                try:
                    self.state.ds['corr'].sel(beam=1, range=slice(0, 10)).plot(ax=ax)
                    ax.axhline(y=thresh, color='r', linestyle='--', label=f'{thresh}%')
                    ax.legend()
                except:
                    self.state.ds['corr'].isel(beam=0).plot(ax=ax)
                ax.set_title(f"Correlation (threshold: {thresh}%)")
            self.canvas_23.refresh()

            self.state.ds = api.clean.correlation_filter(self.state.ds, thresh=thresh)

            self.status_23.setText(f"✓ Filter applied ({thresh}%)")
            self.state.parameters['correlation_threshold'] = thresh

        except Exception as e:
            self.status_23.setText(f"✗ Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed:\n{str(e)}")

    def rotate_coordinates(self):
        """Rotate to target coordinate system"""
        if not self.state.has_dataset():
            QMessageBox.warning(self, "No Dataset", "Please convert first.")
            return

        try:
            import mhkit.dolfyn as dolfyn

            decl = self.declination.get_value()
            target = self.coord_system.currentText()

            dolfyn.set_declination(self.state.ds, decl, inplace=True)

            if target == "principal":
                self.state.ds.attrs['principal_heading'] = dolfyn.calc_principal_heading(
                    self.state.ds['vel'].mean('range')
                )
                dolfyn.rotate2(self.state.ds, "principal", inplace=True)
            else:
                dolfyn.rotate2(self.state.ds, "earth", inplace=True)

            self.status_24.setText(f"✓ Rotated to '{target}' (decl: {decl}°)")
            self.state.parameters['declination'] = decl
            self.state.parameters['coordinate_system'] = target

            self.qcApplied.emit()

        except Exception as e:
            self.status_24.setText(f"✗ Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed:\n{str(e)}")