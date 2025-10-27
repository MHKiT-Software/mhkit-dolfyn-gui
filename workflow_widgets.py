"""
Reusable widgets for ADCP workflow GUI
Includes parameter inputs, collapsible sections, and matplotlib integration
NO HARDCODED STYLES - fully theme-aware
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QToolButton, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDoubleValidator, QIntValidator, QPalette
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure


class ParameterInput(QWidget):
    """
    Input field with label, unit display, validation, and tooltip

    Args:
        label: Parameter name to display
        unit: Unit of measurement (e.g., "m", "deg", "%")
        default: Default value
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        decimals: Number of decimal places (for floats)
        tooltip: Explanatory tooltip text
        param_type: "float" or "int"
    """

    valueChanged = pyqtSignal(float)  # Emitted when valid value changes

    def __init__(self, label, unit="", default=0.0, min_val=None, max_val=None,
                 decimals=2, tooltip="", param_type="float"):
        super().__init__()
        self.param_type = param_type
        self.min_val = min_val
        self.max_val = max_val

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Label
        label_widget = QLabel(f"{label}:")
        label_widget.setMinimumWidth(150)
        layout.addWidget(label_widget)

        # Input field
        self.input = QLineEdit()
        self.input.setText(str(default))
        self.input.setMaximumWidth(100)

        # Set validator
        if param_type == "float":
            validator = QDoubleValidator()
            validator.setDecimals(decimals)
            if min_val is not None:
                validator.setBottom(min_val)
            if max_val is not None:
                validator.setTop(max_val)
            self.input.setValidator(validator)
        elif param_type == "int":
            validator = QIntValidator()
            if min_val is not None:
                validator.setBottom(int(min_val))
            if max_val is not None:
                validator.setTop(int(max_val))
            self.input.setValidator(validator)

        # Connect signal
        self.input.editingFinished.connect(self._on_value_changed)

        layout.addWidget(self.input)

        # Unit label - use palette for theme-aware dim color
        if unit:
            self.unit_label = QLabel(unit)
            palette = self.unit_label.palette()
            palette.setColor(QPalette.ColorRole.WindowText, palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText))
            self.unit_label.setPalette(palette)
            layout.addWidget(self.unit_label)

        # Tooltip
        if tooltip:
            self.setToolTip(tooltip)
            label_widget.setToolTip(tooltip)
            self.input.setToolTip(tooltip)

        # Error label (initially hidden) - use smaller font
        self.error_label = QLabel()
        font = self.error_label.font()
        font.setPointSize(max(8, font.pointSize() - 2))
        self.error_label.setFont(font)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        layout.addStretch()

    def _on_value_changed(self):
        """Validate and emit value change signal"""
        try:
            value = self.get_value()

            # Additional range validation
            if self.min_val is not None and value < self.min_val:
                self.show_error(f"Value must be >= {self.min_val}")
                return
            if self.max_val is not None and value > self.max_val:
                self.show_error(f"Value must be <= {self.max_val}")
                return

            self.clear_error()
            self.valueChanged.emit(value)

        except ValueError:
            self.show_error("Invalid value")

    def get_value(self):
        """Get current value as float or int"""
        text = self.input.text()
        if not text:
            raise ValueError("Empty value")

        if self.param_type == "float":
            return float(text)
        elif self.param_type == "int":
            return int(text)

    def set_value(self, value):
        """Set the input value"""
        self.input.setText(str(value))

    def show_error(self, message):
        """Display error message - theme aware"""
        self.error_label.setText(f"⚠ {message}")
        self.error_label.setVisible(True)

    def clear_error(self):
        """Clear error message"""
        self.error_label.setVisible(False)


class CollapsibleSection(QWidget):
    """
    Collapsible section widget with title bar and content area
    Uses native Qt styling - NO hardcoded colors

    Args:
        title: Section title text
        parent: Parent widget
    """

    def __init__(self, title="", parent=None):
        super().__init__(parent)

        self.is_expanded = True

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Toggle button (title bar) - use native button styling
        self.toggle_button = QToolButton()
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow)
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Make text bold using font
        font = self.toggle_button.font()
        font.setBold(True)
        self.toggle_button.setFont(font)

        self.toggle_button.clicked.connect(self.toggle)

        main_layout.addWidget(self.toggle_button)

        # Content area (collapsible)
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(20, 10, 10, 10)

        main_layout.addWidget(self.content_area)

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

    def toggle(self):
        """Toggle section expanded/collapsed"""
        self.is_expanded = not self.is_expanded

        if self.is_expanded:
            self.toggle_button.setArrowType(Qt.ArrowType.DownArrow)
            self.content_area.setVisible(True)
        else:
            self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
            self.content_area.setVisible(False)

    def add_widget(self, widget):
        """Add a widget to the content area"""
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        """Add a layout to the content area"""
        self.content_layout.addLayout(layout)


class MatplotlibCanvas(QWidget):
    """
    Matplotlib figure embedded in Qt widget with navigation toolbar

    Args:
        parent: Parent widget
        width: Figure width in inches
        height: Figure height in inches
        dpi: Figure DPI
    """

    def __init__(self, parent=None, width=8, height=6, dpi=100):
        super().__init__(parent)

        # Create matplotlib figure
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        self.canvas = FigureCanvasQTAgg(self.figure)

        # Create navigation toolbar
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        # Initial axes
        self.axes = None

    def get_axes(self, clear=True):
        """
        Get or create axes for plotting

        Args:
            clear: If True, clear existing figure

        Returns:
            Matplotlib axes object
        """
        if clear:
            self.figure.clear()

        if self.axes is None or clear:
            self.axes = self.figure.add_subplot(111)

        return self.axes

    def clear(self):
        """Clear the figure"""
        self.figure.clear()
        self.axes = None
        self.canvas.draw()

    def refresh(self):
        """Redraw the canvas"""
        self.figure.tight_layout()
        self.canvas.draw()

    def plot_xarray(self, data_array, **kwargs):
        """
        Convenience method to plot xarray DataArray

        Args:
            data_array: xarray DataArray to plot
            **kwargs: Additional arguments passed to DataArray.plot()
        """
        ax = self.get_axes(clear=True)
        data_array.plot(ax=ax, **kwargs)
        self.refresh()

    def save_figure(self, filename):
        """Save figure to file"""
        self.figure.savefig(filename, dpi=300, bbox_inches='tight')


class WorkflowState:
    """
    Maintains state of the ADCP dataset throughout workflow steps
    """

    def __init__(self):
        self.raw_ds = None          # Original dataset after conversion
        self.ds = None              # Working dataset (after QC steps)
        self.ds_avg = None          # Averaged dataset
        self.avg_tool = None        # ADPBinner instance
        self.plots = {}             # Cached matplotlib figures
        self.parameters = {}        # User-set parameters

    def reset(self):
        """Reset all state"""
        self.raw_ds = None
        self.ds = None
        self.ds_avg = None
        self.avg_tool = None
        self.plots.clear()
        self.parameters.clear()

    def load_dataset(self, dataset):
        """Load initial dataset"""
        self.raw_ds = dataset
        self.ds = dataset.copy(deep=True)  # Working copy

    def has_dataset(self):
        """Check if dataset is loaded"""
        return self.ds is not None

    def get_dataset_info(self):
        """Get basic info about current dataset"""
        if not self.has_dataset():
            return "No dataset loaded"

        dims = ", ".join([f"{k}={v}" for k, v in self.ds.dims.items()])
        vars_count = len(self.ds.data_vars)
        return f"Dimensions: {dims} | Variables: {vars_count}"