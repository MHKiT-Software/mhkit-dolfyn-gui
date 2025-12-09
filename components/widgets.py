"""
Base UI widgets - theme-aware, reusable components
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDoubleValidator, QIntValidator, QPalette

# Note: matplotlib imports are deferred to MatplotlibCanvas.__init__ to speed up startup


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

    valueChanged = pyqtSignal(float)

    def __init__(
        self,
        label,
        unit="",
        default=0.0,
        min_val=None,
        max_val=None,
        decimals=2,
        tooltip="",
        param_type="float",
    ):
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

        self.input.editingFinished.connect(self._on_value_changed)
        layout.addWidget(self.input)

        # Unit label
        if unit:
            self.unit_label = QLabel(unit)
            palette = self.unit_label.palette()
            palette.setColor(
                QPalette.ColorRole.WindowText,
                palette.color(
                    QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText
                ),
            )
            self.unit_label.setPalette(palette)
            layout.addWidget(self.unit_label)

        # Tooltip
        if tooltip:
            self.setToolTip(tooltip)
            label_widget.setToolTip(tooltip)
            self.input.setToolTip(tooltip)

        # Error label
        self.error_label = QLabel()
        font = self.error_label.font()
        font.setPointSize(max(8, font.pointSize() - 2))
        self.error_label.setFont(font)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        layout.addStretch()

    def _on_value_changed(self):
        try:
            value = self.get_value()
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
        text = self.input.text()
        if not text:
            raise ValueError("Empty value")
        return float(text) if self.param_type == "float" else int(text)

    def set_value(self, value):
        self.input.setText(str(value))

    def show_error(self, message):
        self.error_label.setText(f"⚠ {message}")
        self.error_label.setVisible(True)

    def clear_error(self):
        self.error_label.setVisible(False)


class CollapsibleSection(QWidget):
    """Collapsible section widget with title bar and content area"""

    def __init__(self, title="", expanded=True, parent=None):
        super().__init__(parent)
        self.is_expanded = expanded
        self._base_title = title
        self._is_active = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Toggle button
        self.toggle_button = QToolButton()
        self.toggle_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        font = self.toggle_button.font()
        font.setBold(True)
        self.toggle_button.setFont(font)

        self.toggle_button.clicked.connect(self.toggle)
        main_layout.addWidget(self.toggle_button)

        # Content area
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(20, 10, 10, 10)
        self.content_area.setVisible(expanded)
        main_layout.addWidget(self.content_area)

    def toggle(self):
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            self.toggle_button.setArrowType(Qt.ArrowType.DownArrow)
            self.content_area.setVisible(True)
        else:
            self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
            self.content_area.setVisible(False)

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)

    def set_active(self, active: bool):
        """Update section title to show active/inactive state"""
        self._is_active = active
        if active:
            self.toggle_button.setText(f"{self._base_title} [Enabled]")
        else:
            self.toggle_button.setText(self._base_title)


class MatplotlibCanvas(QWidget):
    """Matplotlib figure embedded in Qt widget with navigation toolbar"""

    def __init__(self, parent=None, width=8, height=6, dpi=100):
        super().__init__(parent)

        # Defer matplotlib import to first use for faster app startup
        from matplotlib.backends.backend_qtagg import (
            FigureCanvasQTAgg,
            NavigationToolbar2QT,
        )
        from matplotlib.figure import Figure

        self.figure = Figure(figsize=(width, height), dpi=dpi)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        layout = QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.axes = None

    def get_axes(self, clear=True):
        if clear:
            self.figure.clear()
        if self.axes is None or clear:
            self.axes = self.figure.add_subplot(111)
        return self.axes

    def clear(self):
        self.figure.clear()
        self.axes = None
        self.canvas.draw()

    def refresh(self):
        self.figure.tight_layout()
        self.canvas.draw()

    def plot_xarray(self, data_array, **kwargs):
        ax = self.get_axes(clear=True)
        data_array.plot(ax=ax, **kwargs)
        self.refresh()

    def save_figure(self, filename):
        self.figure.savefig(filename, dpi=300, bbox_inches="tight")
