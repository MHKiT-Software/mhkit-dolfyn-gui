"""
Step 5: Plotting and Visualization Section
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QMessageBox
)
from .widgets import CollapsibleSection, MatplotlibCanvas


class VisualizationSection(QWidget):
    """Step 5: Plot speed and direction"""

    def __init__(self, workflow_state, parent=None):
        super().__init__(parent)
        self.state = workflow_state
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.section = CollapsibleSection("Step 5: Visualization")

        # Speed plot
        self._create_speed_plot()

        # Direction plot
        self._create_direction_plot()

        layout.addWidget(self.section)

    def _create_speed_plot(self):
        """Create speed plotting section"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        label = QLabel("Flow Speed")
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        layout.addWidget(label)

        cmap_layout = QHBoxLayout()
        cmap_layout.addWidget(QLabel("Colormap:"))
        self.speed_cmap = QComboBox()
        self.speed_cmap.addItems(["Blues", "viridis", "plasma", "coolwarm", "turbo"])
        cmap_layout.addWidget(self.speed_cmap)
        cmap_layout.addStretch()
        layout.addLayout(cmap_layout)

        btn = QPushButton("Plot Speed")
        btn.clicked.connect(self.plot_speed)
        layout.addWidget(btn)

        self.canvas_speed = MatplotlibCanvas(width=10, height=5, dpi=80)
        self.canvas_speed.setMinimumHeight(400)
        layout.addWidget(self.canvas_speed)

        self.section.add_widget(widget)

    def _create_direction_plot(self):
        """Create direction plotting section"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        label = QLabel("Flow Direction")
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        layout.addWidget(label)

        cmap_layout = QHBoxLayout()
        cmap_layout.addWidget(QLabel("Colormap:"))
        self.dir_cmap = QComboBox()
        self.dir_cmap.addItems(["twilight", "hsv", "twilight_shifted", "rainbow"])
        cmap_layout.addWidget(self.dir_cmap)
        cmap_layout.addStretch()
        layout.addLayout(cmap_layout)

        btn = QPushButton("Plot Direction")
        btn.clicked.connect(self.plot_direction)
        layout.addWidget(btn)

        self.canvas_dir = MatplotlibCanvas(width=10, height=5, dpi=80)
        self.canvas_dir.setMinimumHeight(400)
        layout.addWidget(self.canvas_dir)

        self.section.add_widget(widget)

    def plot_speed(self):
        """Plot flow speed"""
        if self.state.ds_avg is None or 'U_mag' not in self.state.ds_avg:
            QMessageBox.warning(self, "No Data",
                              "Please complete Step 4 first.")
            return

        try:
            import mhkit.dolfyn as dolfyn
            import matplotlib.dates as dt

            self.canvas_speed.clear()
            ax = self.canvas_speed.get_axes(clear=True)

            t = dolfyn.time.dt642date(self.state.ds_avg['time'])
            cmap = self.speed_cmap.currentText()

            mesh = ax.pcolormesh(t, self.state.ds_avg['range'],
                                self.state.ds_avg['U_mag'],
                                cmap=cmap, shading='nearest')

            if 'depth' in self.state.ds_avg:
                ax.plot(t, self.state.ds_avg['depth'], 'b-',
                       linewidth=2, label='Water Surface')
                ax.legend()

            ax.set_xlabel("Time")
            ax.xaxis.set_major_formatter(dt.DateFormatter("%H:%M"))
            ax.set_ylabel("Range (m)")
            ax.set_title("Flow Speed")

            cbar = self.canvas_speed.figure.colorbar(mesh, ax=ax)
            cbar.set_label("Speed (m/s)")

            self.canvas_speed.refresh()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to plot:\n{str(e)}")

    def plot_direction(self):
        """Plot flow direction"""
        if self.state.ds_avg is None or 'U_dir' not in self.state.ds_avg:
            QMessageBox.warning(self, "No Data",
                              "Please complete Step 4 first.")
            return

        try:
            import mhkit.dolfyn as dolfyn
            import matplotlib.dates as dt

            self.canvas_dir.clear()
            ax = self.canvas_dir.get_axes(clear=True)

            t = dolfyn.time.dt642date(self.state.ds_avg['time'])
            cmap = self.dir_cmap.currentText()

            mesh = ax.pcolormesh(t, self.state.ds_avg['range'],
                                self.state.ds_avg['U_dir'],
                                cmap=cmap, shading='nearest')

            if 'depth' in self.state.ds_avg:
                ax.plot(t, self.state.ds_avg['depth'], 'k-',
                       linewidth=2, label='Water Surface')
                ax.legend()

            ax.set_xlabel("Time")
            ax.xaxis.set_major_formatter(dt.DateFormatter("%H:%M"))
            ax.set_ylabel("Range (m)")
            ax.set_title("Flow Direction")

            cbar = self.canvas_dir.figure.colorbar(mesh, ax=ax)
            cbar.set_label("Direction (° CW from true N)")

            self.canvas_dir.refresh()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to plot:\n{str(e)}")