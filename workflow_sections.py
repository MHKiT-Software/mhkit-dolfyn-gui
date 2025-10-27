"""
Workflow sections for ADCP data processing
Implements Steps 2-5 from the ADCP workflow example
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from workflow_widgets import CollapsibleSection, ParameterInput, MatplotlibCanvas


class QCSection(QWidget):
    """
    Step 2: Quality Control and Data Preparation
    - Set deployment height / range offset
    - Remove surface interference
    - Apply correlation filter
    - Rotate coordinate system
    """

    qcApplied = pyqtSignal()  # Emitted when QC step is completed

    def __init__(self, workflow_state, parent=None):
        super().__init__(parent)
        self.state = workflow_state
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main collapsible section
        self.section = CollapsibleSection("Step 2: Quality Control and Data Preparation")

        # 2.1: Set Deployment Height
        subsection_21 = QWidget()
        layout_21 = QVBoxLayout(subsection_21)

        label_21 = QLabel("2.1: Set Deployment Height")
        font = label_21.font()
        font.setBold(True)
        label_21.setFont(font)
        layout_21.addWidget(label_21)

        self.deployment_height = ParameterInput(
            label="Deployment Height",
            unit="m",
            default=0.6,
            min_val=0.0,
            max_val=100.0,
            decimals=2,
            tooltip="Height of ADCP transducers from seafloor (or depth from surface for downward-facing)",
            param_type="float"
        )
        layout_21.addWidget(self.deployment_height)

        btn_21 = QPushButton("Apply Range Offset")
        btn_21.clicked.connect(self.apply_range_offset)
        layout_21.addWidget(btn_21)

        self.status_21 = QLabel()
        layout_21.addWidget(self.status_21)

        self.section.add_widget(subsection_21)

        # 2.2: Remove Surface Interference
        subsection_22 = QWidget()
        layout_22 = QVBoxLayout(subsection_22)

        label_22 = QLabel("2.2: Remove Surface Interference")
        label_22.setFont(font)
        layout_22.addWidget(label_22)

        self.salinity = ParameterInput(
            label="Salinity",
            unit="PSU",
            default=35.0,
            min_val=0.0,
            max_val=50.0,
            decimals=1,
            tooltip="Water salinity for depth calculation from pressure sensor",
            param_type="float"
        )
        layout_22.addWidget(self.salinity)

        btn_22 = QPushButton("Remove Surface Interference & Plot")
        btn_22.clicked.connect(self.remove_surface_interference)
        layout_22.addWidget(btn_22)

        self.status_22 = QLabel()
        layout_22.addWidget(self.status_22)

        # Canvas for velocity plot
        self.canvas_22 = MatplotlibCanvas(width=8, height=4, dpi=80)
        layout_22.addWidget(self.canvas_22)

        self.section.add_widget(subsection_22)

        # 2.3: Correlation Filter
        subsection_23 = QWidget()
        layout_23 = QVBoxLayout(subsection_23)

        label_23 = QLabel("2.3: Acoustic Correlation Filter")
        label_23.setFont(font)
        layout_23.addWidget(label_23)

        self.correlation_threshold = ParameterInput(
            label="Correlation Threshold",
            unit="%",
            default=50,
            min_val=0,
            max_val=100,
            decimals=0,
            tooltip="Minimum correlation percentage for valid data (typical: 30-50%)",
            param_type="int"
        )
        layout_23.addWidget(self.correlation_threshold)

        btn_23 = QPushButton("Apply Filter & Plot")
        btn_23.clicked.connect(self.apply_correlation_filter)
        layout_23.addWidget(btn_23)

        self.status_23 = QLabel()
        layout_23.addWidget(self.status_23)

        # Canvas for correlation plot
        self.canvas_23 = MatplotlibCanvas(width=8, height=4, dpi=80)
        layout_23.addWidget(self.canvas_23)

        self.section.add_widget(subsection_23)

        # 2.4: Rotate Coordinate System
        subsection_24 = QWidget()
        layout_24 = QVBoxLayout(subsection_24)

        label_24 = QLabel("2.4: Rotate Coordinate System")
        label_24.setFont(font)
        layout_24.addWidget(label_24)

        self.declination = ParameterInput(
            label="Magnetic Declination",
            unit="deg",
            default=0.0,
            min_val=-180.0,
            max_val=180.0,
            decimals=1,
            tooltip="Magnetic declination angle (East positive, West negative)",
            param_type="float"
        )
        layout_24.addWidget(self.declination)

        coord_layout = QHBoxLayout()
        coord_layout.addWidget(QLabel("Target Coordinate System:"))
        self.coord_system = QComboBox()
        self.coord_system.addItems(["earth", "principal"])
        self.coord_system.setToolTip("earth = East-North-Up, principal = streamwise-cross-stream-vertical")
        coord_layout.addWidget(self.coord_system)
        coord_layout.addStretch()
        layout_24.addLayout(coord_layout)

        btn_24 = QPushButton("Apply Rotation")
        btn_24.clicked.connect(self.rotate_coordinates)
        layout_24.addWidget(btn_24)

        self.status_24 = QLabel()
        layout_24.addWidget(self.status_24)

        self.section.add_widget(subsection_24)

        layout.addWidget(self.section)

    def apply_range_offset(self):
        """Apply deployment height / range offset"""
        if not self.state.has_dataset():
            QMessageBox.warning(self, "No Dataset", "Please load a dataset first by converting an ADCP file.")
            return

        try:
            from mhkit.dolfyn.adp import api

            offset = self.deployment_height.get_value()
            api.clean.set_range_offset(self.state.ds, offset)

            self.status_21.setText(f"✓ Range offset set to {offset} m")
            self.state.parameters['deployment_height'] = offset

        except Exception as e:
            self.status_21.setText(f"✗ Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to set range offset:\n{str(e)}")

    def remove_surface_interference(self):
        """Remove data above surface and plot"""
        if not self.state.has_dataset():
            QMessageBox.warning(self, "No Dataset", "Please load a dataset first.")
            return

        try:
            from mhkit.dolfyn.adp import api

            salinity = self.salinity.get_value()

            # Calculate water depth from pressure
            api.clean.water_depth_from_pressure(self.state.ds, salinity=salinity)

            # Plot before removal
            self.canvas_22.clear()
            ax = self.canvas_22.get_axes(clear=True)

            # Check if velocity data exists and plot
            if 'vel' in self.state.ds:
                # Plot one velocity component
                self.state.ds['vel'][1].plot(ax=ax)
                ax.set_title("Velocity (before surface removal)")
                ax.set_ylabel("Range (m)")

            self.canvas_22.refresh()

            # Remove surface interference
            self.state.ds = api.clean.remove_surface_interference(self.state.ds)

            self.status_22.setText(f"✓ Surface interference removed (salinity: {salinity} PSU)")
            self.state.parameters['salinity'] = salinity

        except Exception as e:
            self.status_22.setText(f"✗ Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to remove surface interference:\n{str(e)}")

    def apply_correlation_filter(self):
        """Apply correlation filter and plot"""
        if not self.state.has_dataset():
            QMessageBox.warning(self, "No Dataset", "Please load a dataset first.")
            return

        try:
            from mhkit.dolfyn.adp import api

            thresh = self.correlation_threshold.get_value()

            # Plot correlation data before filtering
            self.canvas_23.clear()
            ax = self.canvas_23.get_axes(clear=True)

            if 'corr' in self.state.ds:
                # Plot correlation from beam 1, range 0-10m
                try:
                    self.state.ds['corr'].sel(beam=1, range=slice(0, 10)).plot(ax=ax)
                    ax.set_title(f"Correlation (beam 1, threshold: {thresh}%)")
                    ax.axhline(y=thresh, color='r', linestyle='--', label=f'Threshold: {thresh}%')
                    ax.legend()
                except:
                    # Fallback if slicing doesn't work
                    self.state.ds['corr'].isel(beam=0).plot(ax=ax)
                    ax.set_title(f"Correlation (threshold: {thresh}%)")

            self.canvas_23.refresh()

            # Apply filter
            self.state.ds = api.clean.correlation_filter(self.state.ds, thresh=thresh)

            self.status_23.setText(f"✓ Correlation filter applied ({thresh}% threshold)")
            self.state.parameters['correlation_threshold'] = thresh

        except Exception as e:
            self.status_23.setText(f"✗ Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to apply correlation filter:\n{str(e)}")

    def rotate_coordinates(self):
        """Rotate to target coordinate system"""
        if not self.state.has_dataset():
            QMessageBox.warning(self, "No Dataset", "Please load a dataset first.")
            return

        try:
            import mhkit.dolfyn as dolfyn

            decl = self.declination.get_value()
            target = self.coord_system.currentText()

            # Set declination
            dolfyn.set_declination(self.state.ds, decl, inplace=True)

            # Rotate to target coordinate system
            if target == "principal":
                # Calculate principal heading first
                self.state.ds.attrs['principal_heading'] = dolfyn.calc_principal_heading(
                    self.state.ds['vel'].mean('range')
                )
                dolfyn.rotate2(self.state.ds, "principal", inplace=True)
            else:
                dolfyn.rotate2(self.state.ds, "earth", inplace=True)

            self.status_24.setText(f"✓ Rotated to '{target}' coordinates (declination: {decl}°)")
            self.state.parameters['declination'] = decl
            self.state.parameters['coordinate_system'] = target

            self.qcApplied.emit()

        except Exception as e:
            self.status_24.setText(f"✗ Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to rotate coordinates:\n{str(e)}")


class AveragingSection(QWidget):
    """
    Step 3: Data Averaging
    Bin average data into time ensembles
    """

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
            tooltip="Duration of each time bin (typical: 300s = 5 min)",
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
            tooltip="Auto-detected from dataset, override if needed",
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
            QMessageBox.warning(self, "No Dataset", "Please load a dataset first.")
            return

        try:
            from mhkit.dolfyn.adp import api

            window = self.averaging_window.get_value()
            fs = self.sample_rate.get_value()

            # Auto-detect sample rate from dataset if available
            if hasattr(self.state.ds, 'fs'):
                fs = float(self.state.ds.fs)
                self.sample_rate.set_value(fs)

            n_bin = int(fs * window)
            self.bin_size_label.setText(f"Calculated Bin Size: {n_bin} samples")

            # Create averaging tool and average
            self.state.avg_tool = api.ADPBinner(n_bin=n_bin, fs=fs)
            self.state.ds_avg = self.state.avg_tool.bin_average(self.state.ds)

            n_ensembles = len(self.state.ds_avg['time'])
            self.status.setText(f"✓ Data averaged into {n_ensembles} ensembles ({window}s bins)")

            self.state.parameters['averaging_window'] = window
            self.state.parameters['sample_rate'] = fs

            self.averagingComplete.emit()

        except Exception as e:
            self.status.setText(f"✗ Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to average data:\n{str(e)}")


class SpeedDirectionSection(QWidget):
    """
    Step 4: Calculate Speed and Direction
    """

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
                              "Please complete data averaging (Step 3) first.")
            return

        try:
            # Calculate speed and direction using velds shortcuts
            self.state.ds_avg['U_mag'] = self.state.ds_avg.velds.U_mag
            self.state.ds_avg['U_dir'] = self.state.ds_avg.velds.U_dir

            # Calculate statistics
            u_mag_mean = float(self.state.ds_avg['U_mag'].mean().values)
            u_mag_max = float(self.state.ds_avg['U_mag'].max().values)
            u_mag_min = float(self.state.ds_avg['U_mag'].min().values)

            u_dir_mean = float(self.state.ds_avg['U_dir'].mean().values)

            results = (
                f"Results:\n"
                f"├─ U_mag (Speed): Mean = {u_mag_mean:.2f} m/s, "
                f"Max = {u_mag_max:.2f} m/s, Min = {u_mag_min:.2f} m/s\n"
                f"└─ U_dir (Direction): Mean = {u_dir_mean:.1f}° (from true North)"
            )

            self.results_label.setText(results)
            self.status.setText("✓ Speed and direction calculated")

            self.calculationComplete.emit()

        except Exception as e:
            self.status.setText(f"✗ Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to calculate speed/direction:\n{str(e)}")


class VisualizationSection(QWidget):
    """
    Step 5: Plotting and Visualization
    """

    def __init__(self, workflow_state, parent=None):
        super().__init__(parent)
        self.state = workflow_state
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.section = CollapsibleSection("Step 5: Visualization")

        # Speed plot
        speed_widget = QWidget()
        speed_layout = QVBoxLayout(speed_widget)

        speed_header = QLabel("Flow Speed")
        font = speed_header.font()
        font.setBold(True)
        speed_header.setFont(font)
        speed_layout.addWidget(speed_header)

        cmap_layout = QHBoxLayout()
        cmap_layout.addWidget(QLabel("Colormap:"))
        self.speed_cmap = QComboBox()
        self.speed_cmap.addItems(["Blues", "viridis", "plasma", "coolwarm", "turbo"])
        cmap_layout.addWidget(self.speed_cmap)
        cmap_layout.addStretch()
        speed_layout.addLayout(cmap_layout)

        btn_speed = QPushButton("Plot Speed")
        btn_speed.clicked.connect(self.plot_speed)
        speed_layout.addWidget(btn_speed)

        self.canvas_speed = MatplotlibCanvas(width=10, height=5, dpi=80)
        speed_layout.addWidget(self.canvas_speed)

        self.section.add_widget(speed_widget)

        # Direction plot
        dir_widget = QWidget()
        dir_layout = QVBoxLayout(dir_widget)

        dir_header = QLabel("Flow Direction")
        dir_header.setFont(font)
        dir_layout.addWidget(dir_header)

        cmap_layout2 = QHBoxLayout()
        cmap_layout2.addWidget(QLabel("Colormap:"))
        self.dir_cmap = QComboBox()
        self.dir_cmap.addItems(["twilight", "hsv", "twilight_shifted", "rainbow"])
        cmap_layout2.addWidget(self.dir_cmap)
        cmap_layout2.addStretch()
        dir_layout.addLayout(cmap_layout2)

        btn_dir = QPushButton("Plot Direction")
        btn_dir.clicked.connect(self.plot_direction)
        dir_layout.addWidget(btn_dir)

        self.canvas_dir = MatplotlibCanvas(width=10, height=5, dpi=80)
        dir_layout.addWidget(self.canvas_dir)

        self.section.add_widget(dir_widget)

        layout.addWidget(self.section)

    def plot_speed(self):
        """Plot flow speed colormap"""
        if self.state.ds_avg is None or 'U_mag' not in self.state.ds_avg:
            QMessageBox.warning(self, "No Data",
                              "Please complete speed/direction calculation (Step 4) first.")
            return

        try:
            import mhkit.dolfyn as dolfyn
            import matplotlib.dates as dt

            self.canvas_speed.clear()
            ax = self.canvas_speed.get_axes(clear=True)

            # Convert time to datetime
            t = dolfyn.time.dt642date(self.state.ds_avg['time'])

            # Plot speed
            cmap = self.speed_cmap.currentText()
            mesh = ax.pcolormesh(t, self.state.ds_avg['range'],
                                self.state.ds_avg['U_mag'].T,
                                cmap=cmap, shading='nearest')

            # Plot water surface if available
            if 'depth' in self.state.ds_avg:
                ax.plot(t, self.state.ds_avg['depth'], 'b-', linewidth=2, label='Water Surface')
                ax.legend()

            ax.set_xlabel("Time")
            ax.xaxis.set_major_formatter(dt.DateFormatter("%H:%M"))
            ax.set_ylabel("Range (m)")
            ax.set_title("Flow Speed")

            cbar = self.canvas_speed.figure.colorbar(mesh, ax=ax)
            cbar.set_label("Speed (m/s)")

            self.canvas_speed.refresh()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to plot speed:\n{str(e)}")

    def plot_direction(self):
        """Plot flow direction colormap"""
        if self.state.ds_avg is None or 'U_dir' not in self.state.ds_avg:
            QMessageBox.warning(self, "No Data",
                              "Please complete speed/direction calculation (Step 4) first.")
            return

        try:
            import mhkit.dolfyn as dolfyn
            import matplotlib.dates as dt

            self.canvas_dir.clear()
            ax = self.canvas_dir.get_axes(clear=True)

            # Convert time to datetime
            t = dolfyn.time.dt642date(self.state.ds_avg['time'])

            # Plot direction
            cmap = self.dir_cmap.currentText()
            mesh = ax.pcolormesh(t, self.state.ds_avg['range'],
                                self.state.ds_avg['U_dir'].T,
                                cmap=cmap, shading='nearest')

            # Plot water surface if available
            if 'depth' in self.state.ds_avg:
                ax.plot(t, self.state.ds_avg['depth'], 'k-', linewidth=2, label='Water Surface')
                ax.legend()

            ax.set_xlabel("Time")
            ax.xaxis.set_major_formatter(dt.DateFormatter("%H:%M"))
            ax.set_ylabel("Range (m)")
            ax.set_title("Flow Direction")

            cbar = self.canvas_dir.figure.colorbar(mesh, ax=ax)
            cbar.set_label("Direction (° CW from true N)")

            self.canvas_dir.refresh()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to plot direction:\n{str(e)}")