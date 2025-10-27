#!/usr/bin/env python
"""
Test script for Stage 1 foundation widgets
Run this to verify ParameterInput, CollapsibleSection, and MatplotlibCanvas work correctly
"""

import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton
from workflow_widgets import ParameterInput, CollapsibleSection, MatplotlibCanvas


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stage 1 Widget Tests")
        self.setMinimumSize(800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Test CollapsibleSection with ParameterInputs
        section1 = CollapsibleSection("Test Section 1: Parameter Inputs")

        # Test various parameter types
        param1 = ParameterInput(
            label="Deployment Height",
            unit="m",
            default=0.6,
            min_val=0.0,
            max_val=100.0,
            decimals=2,
            tooltip="Height of ADCP from seafloor",
            param_type="float"
        )
        param1.valueChanged.connect(lambda v: print(f"Height changed: {v} m"))
        section1.add_widget(param1)

        param2 = ParameterInput(
            label="Salinity",
            unit="PSU",
            default=35.0,
            min_val=0.0,
            max_val=50.0,
            decimals=1,
            tooltip="Water salinity for depth calculation",
            param_type="float"
        )
        param2.valueChanged.connect(lambda v: print(f"Salinity changed: {v} PSU"))
        section1.add_widget(param2)

        param3 = ParameterInput(
            label="Correlation Threshold",
            unit="%",
            default=50,
            min_val=0,
            max_val=100,
            tooltip="Minimum correlation for valid data",
            param_type="int"
        )
        param3.valueChanged.connect(lambda v: print(f"Threshold changed: {v}%"))
        section1.add_widget(param3)

        param4 = ParameterInput(
            label="Magnetic Declination",
            unit="deg",
            default=15.8,
            min_val=-180.0,
            max_val=180.0,
            decimals=1,
            tooltip="Magnetic declination angle",
            param_type="float"
        )
        param4.valueChanged.connect(lambda v: print(f"Declination changed: {v} deg"))
        section1.add_widget(param4)

        main_layout.addWidget(section1)

        # Test CollapsibleSection with MatplotlibCanvas
        section2 = CollapsibleSection("Test Section 2: Matplotlib Canvas")

        self.canvas = MatplotlibCanvas(width=6, height=4, dpi=100)

        # Add plot button
        plot_btn = QPushButton("Generate Test Plot")
        plot_btn.clicked.connect(self.plot_test_data)
        section2.add_widget(plot_btn)

        section2.add_widget(self.canvas)

        main_layout.addWidget(section2)

        # Test another collapsible section (initially collapsed)
        section3 = CollapsibleSection("Test Section 3: Initially Collapsed")
        section3.toggle()  # Collapse it

        test_label = QPushButton("This section starts collapsed")
        section3.add_widget(test_label)

        main_layout.addWidget(section3)

        main_layout.addStretch()

    def plot_test_data(self):
        """Generate a test plot on the canvas"""
        ax = self.canvas.get_axes(clear=True)

        # Generate sample data
        x = np.linspace(0, 10, 100)
        y1 = np.sin(x)
        y2 = np.cos(x)

        # Plot
        ax.plot(x, y1, label='sin(x)', linewidth=2)
        ax.plot(x, y2, label='cos(x)', linewidth=2)
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_title('Test Plot: Sine and Cosine')
        ax.legend()
        ax.grid(True, alpha=0.3)

        self.canvas.refresh()
        print("Test plot generated")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = TestWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()