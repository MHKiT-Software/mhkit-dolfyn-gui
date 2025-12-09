"""
Help system for MHKiT DOLFyN GUI

Provides:
- Rich tooltips with docstrings dynamically loaded from dolfyn module
- Links to documentation, examples, and GitHub issues
- Info buttons for contextual help
"""

import inspect
from typing import Optional, Dict, Any, Callable
from functools import lru_cache

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QDialog,
    QTextBrowser,
    QMenuBar,
    QMenu,
)
from PyQt6.QtCore import Qt, QSize, QUrl
from PyQt6.QtGui import QAction, QDesktopServices, QPalette


# Documentation URLs
HELP_URLS = {
    "api_docs": "https://mhkit-software.github.io/MHKiT/mhkit-python/api.dolfyn.html",
    "adcp_example": "https://mhkit-software.github.io/MHKiT/adcp_example.html",
    "adv_example": "https://mhkit-software.github.io/MHKiT/adv_example.html",
    "github_issues": "https://github.com/MHKiT-Software/MHKiT-Python/issues",
    "github_new_issue": "https://github.com/MHKiT-Software/MHKiT-Python/issues/new",
}


# Mapping of function keys to their module paths for dynamic lookup
FUNCTION_PATHS = {
    # File I/O
    "read": ("mhkit.dolfyn.io.api", "read"),
    "save": ("mhkit.dolfyn.io.api", "save"),
    "load": ("mhkit.dolfyn.io.api", "load"),
    # Rotation
    "rotate2": ("mhkit.dolfyn", "rotate2"),
    "set_declination": ("mhkit.dolfyn", "set_declination"),
    "calc_principal_heading": ("mhkit.dolfyn", "calc_principal_heading"),
    # QC / Cleaning (ADCP)
    "set_range_offset": ("mhkit.dolfyn.adp.clean", "set_range_offset"),
    "water_depth_from_pressure": (
        "mhkit.dolfyn.adp.clean",
        "water_depth_from_pressure",
    ),
    "remove_surface_interference": (
        "mhkit.dolfyn.adp.clean",
        "remove_surface_interference",
    ),
    "correlation_filter": ("mhkit.dolfyn.adp.clean", "correlation_filter"),
    # QC / Cleaning (ADV)
    "GN2002": ("mhkit.dolfyn.adv.clean", "GN2002"),
    "clean_fill": ("mhkit.dolfyn.adv.clean", "clean_fill"),
    # Binning classes
    "ADPBinner": ("mhkit.dolfyn.adp.api", "ADPBinner"),
    "ADVBinner": ("mhkit.dolfyn.adv.api", "ADVBinner"),
    "VelBinner": ("mhkit.dolfyn.velocity", "VelBinner"),
    # Velocity accessor (velds)
    "Velocity": ("mhkit.dolfyn.velocity", "Velocity"),
}

# Methods on binner classes - these need special handling
BINNER_METHODS = {
    "dudz": "ADPBinner",
    "dvdz": "ADPBinner",
    "dwdz": "ADPBinner",
    "shear_squared": "ADPBinner",
    "reynolds_stress_4beam": "ADPBinner",
    "stress_tensor_5beam": "ADPBinner",
    "dissipation_rate_LT83": "ADPBinner",
    "dissipation_rate_SF": "ADPBinner",
    "friction_velocity": "ADPBinner",
    "bin_average": "VelBinner",
    "bin_variance": "VelBinner",
    "turbulent_kinetic_energy": "ADVBinner",
    "reynolds_stress": "ADVBinner",
    "power_spectral_density": "VelBinner",
}

# Properties on the velds accessor (Velocity class)
VELDS_PROPERTIES = {
    "u": "Velocity",
    "v": "Velocity",
    "w": "Velocity",
    "U": "Velocity",
    "U_mag": "Velocity",
    "U_dir": "Velocity",
    "tke": "Velocity",
    "upup_": "Velocity",
    "vpvp_": "Velocity",
    "wpwp_": "Velocity",
    "upvp_": "Velocity",
    "upwp_": "Velocity",
    "vpwp_": "Velocity",
    "E_coh": "Velocity",
    "I_tke": "Velocity",
    "I": "Velocity",
}


def _load_velds_attrs_cache():
    """Load cached velds attrs from JSON file (generated from example data)"""
    import json
    from pathlib import Path

    cache_file = Path(__file__).parent / "velds_attrs.json"
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                return json.load(f)
        except Exception:
            pass
    return None


# Cached velds documentation (loaded once)
_VELDS_ATTRS_CACHE = None


def get_velds_attrs_doc(prop_name: str) -> Optional[Dict[str, str]]:
    """Get documentation for a velds property including xarray attrs"""
    global _VELDS_ATTRS_CACHE

    if _VELDS_ATTRS_CACHE is None:
        _VELDS_ATTRS_CACHE = _load_velds_attrs_cache()

    if _VELDS_ATTRS_CACHE is None:
        return None

    velds_props = _VELDS_ATTRS_CACHE.get("velds_properties", {})
    if prop_name in velds_props:
        prop_doc = velds_props[prop_name]
        attrs = prop_doc.get("attrs", {})

        # Build enhanced description with attrs
        description = prop_doc.get("docstring", "") or ""
        if attrs:
            description += "\n\nxarray Attributes:\n"
            for k, v in attrs.items():
                description += f"  - {k}: {v}\n"

        return {
            "name": prop_doc.get("name", f"velds.{prop_name}"),
            "summary": (prop_doc.get("docstring", "") or "").split("\n")[0],
            "description": description,
            "signature": "",
        }

    return None


def get_dataset_var_doc(var_name: str) -> Optional[Dict[str, str]]:
    """Get documentation for a dataset variable including xarray attrs"""
    global _VELDS_ATTRS_CACHE

    if _VELDS_ATTRS_CACHE is None:
        _VELDS_ATTRS_CACHE = _load_velds_attrs_cache()

    if _VELDS_ATTRS_CACHE is None:
        return None

    ds_vars = _VELDS_ATTRS_CACHE.get("dataset_variables", {})
    if var_name in ds_vars:
        var_doc = ds_vars[var_name]
        attrs = var_doc.get("attrs", {})

        # Build description from attrs
        long_name = attrs.get("long_name", var_name)
        units = attrs.get("units", "")
        standard_name = attrs.get("standard_name", "")

        description = f"{long_name}"
        if units:
            description += f"\n\nUnits: {units}"
        if standard_name:
            description += f"\nStandard Name: {standard_name}"

        description += "\n\nxarray Attributes:\n"
        for k, v in attrs.items():
            description += f"  - {k}: {v}\n"

        return {
            "name": var_name,
            "summary": long_name,
            "description": description,
            "signature": "",
        }

    return None


def _import_module(module_path: str):
    """Dynamically import a module by path"""
    import importlib

    return importlib.import_module(module_path)


def _get_function_or_class(module_path: str, name: str) -> Optional[Any]:
    """Get a function or class from a module"""
    try:
        module = _import_module(module_path)
        return getattr(module, name, None)
    except (ImportError, AttributeError):
        return None


def _get_binner_method(binner_class_name: str, method_name: str) -> Optional[Callable]:
    """Get a method from a binner class"""
    if binner_class_name == "ADPBinner":
        module_path = "mhkit.dolfyn.adp.api"
    elif binner_class_name == "ADVBinner":
        module_path = "mhkit.dolfyn.adv.api"
    elif binner_class_name == "VelBinner":
        module_path = "mhkit.dolfyn.velocity"
    else:
        return None

    binner_class = _get_function_or_class(module_path, binner_class_name)
    if binner_class is None:
        return None

    return getattr(binner_class, method_name, None)


def _get_velds_property(property_name: str) -> Optional[Any]:
    """Get a property from the Velocity (velds) accessor class"""
    velocity_class = _get_function_or_class("mhkit.dolfyn.velocity", "Velocity")
    if velocity_class is None:
        return None

    # Get the property object (not the value)
    prop = getattr(velocity_class, property_name, None)
    return prop


@lru_cache(maxsize=64)
def get_docstring(func_key: str) -> Optional[Dict[str, str]]:
    """
    Get docstring info for a dolfyn function or class.

    Returns dict with:
        - name: Full function/class name
        - summary: First line of docstring
        - description: Full docstring
        - signature: Function signature if available
    """
    obj = None
    full_name = func_key

    # Check if it's a known function/class path
    if func_key in FUNCTION_PATHS:
        module_path, name = FUNCTION_PATHS[func_key]
        obj = _get_function_or_class(module_path, name)
        full_name = f"{module_path.split('.')[-1]}.{name}"

    # Check if it's a binner method
    elif func_key in BINNER_METHODS:
        binner_class = BINNER_METHODS[func_key]
        obj = _get_binner_method(binner_class, func_key)
        full_name = f"{binner_class}.{func_key}"

    # Check if it's a velds property - try cached attrs first
    elif func_key in VELDS_PROPERTIES:
        # First try the cached documentation (includes xarray attrs)
        cached_doc = get_velds_attrs_doc(func_key)
        if cached_doc:
            return cached_doc
        # Fall back to dynamic loading from mhkit
        obj = _get_velds_property(func_key)
        full_name = f"velds.{func_key}"

    if obj is None:
        return None

    docstring = inspect.getdoc(obj)
    if not docstring:
        return None

    # Parse docstring
    lines = docstring.strip().split("\n")
    summary = lines[0] if lines else ""

    # Try to get signature
    try:
        if inspect.isclass(obj):
            sig = inspect.signature(obj.__init__)
            # Remove 'self' from signature display
            params = [p for p in sig.parameters.values() if p.name != "self"]
            sig_str = f"({', '.join(str(p) for p in params)})"
        else:
            sig = inspect.signature(obj)
            sig_str = str(sig)
    except (ValueError, TypeError):
        sig_str = ""

    return {
        "name": full_name,
        "summary": summary,
        "description": docstring,
        "signature": sig_str,
    }


def get_all_available_docstrings() -> Dict[str, Dict[str, str]]:
    """Get all available docstrings from mhkit.dolfyn"""
    result = {}

    # Get function/class docstrings
    for key in FUNCTION_PATHS:
        doc = get_docstring(key)
        if doc:
            result[key] = doc

    # Get binner method docstrings
    for key in BINNER_METHODS:
        doc = get_docstring(key)
        if doc:
            result[key] = doc

    # Get velds property docstrings
    for key in VELDS_PROPERTIES:
        doc = get_docstring(key)
        if doc:
            result[key] = doc

    return result


def open_url(url: str):
    """Open URL in default browser"""
    QDesktopServices.openUrl(QUrl(url))


class InfoButton(QToolButton):
    """Small info button that shows a help dialog when clicked"""

    def __init__(self, func_key: str, parent=None):
        super().__init__(parent)
        self.func_key = func_key
        self.setText("ⓘ")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.setMaximumSize(QSize(24, 24))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Use palette-based link color for dark mode compatibility
        palette = self.palette()
        link_color = palette.color(QPalette.ColorRole.Link)
        self.setStyleSheet(f"""
            QToolButton {{
                border: none;
                color: {link_color.name()};
                font-size: 14px;
            }}
            QToolButton:hover {{
                color: {link_color.lighter(120).name()};
            }}
        """)

        # Set tooltip from docstring
        doc = get_docstring(func_key)
        if doc:
            self.setToolTip(f"{doc['name']}\n\n{doc['summary']}")

        self.clicked.connect(self._show_help)

    def _show_help(self):
        """Show the help dialog"""
        doc = get_docstring(self.func_key)
        if not doc:
            return

        dialog = HelpDialog(self.func_key, self)
        dialog.exec()


class HelpDialog(QDialog):
    """Dialog showing detailed function help with links"""

    def __init__(self, func_key: str, parent=None):
        super().__init__(parent)
        self.func_key = func_key
        self.doc = get_docstring(func_key)

        title = self.doc["name"] if self.doc else func_key
        self.setWindowTitle(f"Help: {title}")
        self.setMinimumSize(550, 450)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        if not self.doc:
            layout.addWidget(
                QLabel(
                    "Documentation not available.\n\n"
                    "This may be because the mhkit library is not installed "
                    "or the function doesn't exist in the current version."
                )
            )
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(self.accept)
            layout.addWidget(close_btn)
            return

        # Title with signature
        title_text = self.doc["name"]
        if self.doc["signature"]:
            title_text += self.doc["signature"]

        title = QLabel(title_text)
        title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title.setStyleSheet(
            "font-family: monospace; font-size: 12pt; font-weight: bold;"
        )
        layout.addWidget(title)

        # Summary (use palette for dark mode compatibility)
        summary = QLabel(self.doc["summary"])
        summary.setWordWrap(True)
        palette = summary.palette()
        muted_color = palette.color(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText
        )
        summary.setStyleSheet(f"color: {muted_color.name()}; margin-bottom: 10px;")
        layout.addWidget(summary)

        # Full description
        desc = QTextBrowser()
        desc.setPlainText(self.doc["description"])
        desc.setOpenExternalLinks(True)
        layout.addWidget(desc)

        # Links section
        links_layout = QHBoxLayout()

        api_btn = QPushButton("API Docs")
        api_btn.setToolTip("Open MHKiT DOLFyN API documentation")
        api_btn.clicked.connect(lambda: open_url(HELP_URLS["api_docs"]))
        links_layout.addWidget(api_btn)

        adcp_btn = QPushButton("ADCP Example")
        adcp_btn.setToolTip("Open ADCP processing example")
        adcp_btn.clicked.connect(lambda: open_url(HELP_URLS["adcp_example"]))
        links_layout.addWidget(adcp_btn)

        adv_btn = QPushButton("ADV Example")
        adv_btn.setToolTip("Open ADV processing example")
        adv_btn.clicked.connect(lambda: open_url(HELP_URLS["adv_example"]))
        links_layout.addWidget(adv_btn)

        issue_btn = QPushButton("Report Issue")
        issue_btn.setToolTip("Report a bug or request a feature on GitHub")
        issue_btn.clicked.connect(lambda: open_url(HELP_URLS["github_new_issue"]))
        links_layout.addWidget(issue_btn)

        layout.addLayout(links_layout)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


def create_help_menu(menu_bar: QMenuBar) -> QMenu:
    """Create Help menu with documentation links"""
    help_menu = menu_bar.addMenu("Help")

    # API Documentation
    api_action = QAction("DOLFyN API Documentation", menu_bar)
    api_action.setToolTip("Open MHKiT DOLFyN API reference")
    api_action.triggered.connect(lambda: open_url(HELP_URLS["api_docs"]))
    help_menu.addAction(api_action)

    help_menu.addSeparator()

    # Examples
    adcp_action = QAction("ADCP Processing Example", menu_bar)
    adcp_action.setToolTip("Open ADCP data processing tutorial")
    adcp_action.triggered.connect(lambda: open_url(HELP_URLS["adcp_example"]))
    help_menu.addAction(adcp_action)

    adv_action = QAction("ADV Processing Example", menu_bar)
    adv_action.setToolTip("Open ADV data processing tutorial")
    adv_action.triggered.connect(lambda: open_url(HELP_URLS["adv_example"]))
    help_menu.addAction(adv_action)

    help_menu.addSeparator()

    # GitHub
    issues_action = QAction("View GitHub Issues", menu_bar)
    issues_action.setToolTip("View existing issues on GitHub")
    issues_action.triggered.connect(lambda: open_url(HELP_URLS["github_issues"]))
    help_menu.addAction(issues_action)

    new_issue_action = QAction("Report Issue", menu_bar)
    new_issue_action.setToolTip("Report a bug or request a feature")
    new_issue_action.triggered.connect(lambda: open_url(HELP_URLS["github_new_issue"]))
    help_menu.addAction(new_issue_action)

    return help_menu


def get_tooltip_for_function(func_key: str) -> str:
    """
    Get a tooltip string for a function.
    Falls back to a generic message if docstring not available.
    """
    doc = get_docstring(func_key)
    if doc:
        tooltip = f"{doc['name']}\n\n{doc['summary']}"
        if doc["signature"]:
            tooltip = f"{doc['name']}{doc['signature']}\n\n{doc['summary']}"
        return tooltip
    return f"Help for {func_key} not available"


class LabelWithInfo(QWidget):
    """A label with an info button next to it"""

    def __init__(self, text: str, func_key: str, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel(text)
        layout.addWidget(label)

        info_btn = InfoButton(func_key)
        layout.addWidget(info_btn)

        layout.addStretch()

        # Set tooltip on the whole widget
        doc = get_docstring(func_key)
        if doc:
            self.setToolTip(f"{doc['name']}: {doc['summary']}")
