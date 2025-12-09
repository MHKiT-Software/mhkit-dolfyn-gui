"""
MHKiT DOLFyN GUI Components
Modular components for workflow, UI widgets, and processing
"""

# Base widgets
from .widgets import ParameterInput, CollapsibleSection, MatplotlibCanvas

# State management
from .state import WorkflowState

# Workers
from .standardize_worker import StandardizeWorker
from .preload_worker import PreloadWorker
from .batch_processor import (
    BatchStandardizeWorker,
    StandardizeOptions,
    PartitionMethod,
    OutputNamer,
    TimePartitioner,
)

# UI components
from .splash_screen import SplashScreen

# Workflow sections
from .qc_section import QCSection
from .averaging_section import AveragingSection
from .speed_direction_section import SpeedDirectionSection
from .visualization_section import VisualizationSection

# Help system
from .help_system import (
    InfoButton,
    HelpDialog,
    LabelWithInfo,
    create_help_menu,
    get_docstring,
    get_tooltip_for_function,
    HELP_URLS,
)

__all__ = [
    # Widgets
    "ParameterInput",
    "CollapsibleSection",
    "MatplotlibCanvas",
    # State
    "WorkflowState",
    # Workers
    "StandardizeWorker",
    "PreloadWorker",
    "BatchStandardizeWorker",
    "StandardizeOptions",
    "PartitionMethod",
    "OutputNamer",
    "TimePartitioner",
    # UI
    "SplashScreen",
    # Workflow sections
    "QCSection",
    "AveragingSection",
    "SpeedDirectionSection",
    "VisualizationSection",
    # Help system
    "InfoButton",
    "HelpDialog",
    "LabelWithInfo",
    "create_help_menu",
    "get_docstring",
    "get_tooltip_for_function",
    "HELP_URLS",
]
