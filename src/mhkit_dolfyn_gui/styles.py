"""Single source of truth for all colors, fonts, and styles.

Every widget imports from here — no hardcoded colors or font names elsewhere.
Organized as frozen dataclasses for structure and IDE autocomplete.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from PySide6.QtGui import QColor, QPalette


@dataclass(frozen=True)
class PaletteColors:
    """Colors used to build the application-wide dark QPalette."""

    window: QColor = field(default_factory=lambda: QColor(43, 43, 43))
    window_text: QColor = field(default_factory=lambda: QColor(208, 208, 208))
    base: QColor = field(default_factory=lambda: QColor(30, 30, 30))
    alternate_base: QColor = field(default_factory=lambda: QColor(50, 50, 50))
    text: QColor = field(default_factory=lambda: QColor(208, 208, 208))
    button: QColor = field(default_factory=lambda: QColor(53, 53, 53))
    button_text: QColor = field(default_factory=lambda: QColor(208, 208, 208))
    bright_text: QColor = field(default_factory=lambda: QColor(255, 255, 255))
    link: QColor = field(default_factory=lambda: QColor(66, 165, 245))
    highlight: QColor = field(default_factory=lambda: QColor(33, 150, 243))
    highlight_text: QColor = field(default_factory=lambda: QColor(255, 255, 255))
    disabled_text: QColor = field(default_factory=lambda: QColor(128, 128, 128))
    tooltip_base: QColor = field(default_factory=lambda: QColor(50, 50, 50))
    tooltip_text: QColor = field(default_factory=lambda: QColor(208, 208, 208))


@dataclass(frozen=True)
class Fonts:
    mono: str = "'Menlo', 'Consolas', 'Courier New', monospace"
    size_sm: str = "10pt"
    size_md: str = "12pt"
    size_lg: str = "18pt"
    size_xl: str = "24pt"


@dataclass(frozen=True)
class AccentColors:
    primary: str = "#2196F3"
    spinner: QColor = field(default_factory=lambda: QColor(33, 150, 243))


@dataclass(frozen=True)
class TextColors:
    body: str = "#eee"
    muted: str = "#888"
    hint: str = "#999"
    upcoming: str = "#aaa"
    success: str = "#4caf50"
    error: str = "#ef5350"


@dataclass(frozen=True)
class SplashColors:
    header: str = "#004a72"
    text: str = "#666"
    progress_bg: str = "#e0e0e0"
    progress_chunk: str = "#004a72"
    bg: QColor = field(default_factory=lambda: QColor(255, 255, 255))
    text_area_bg: QColor = field(default_factory=lambda: QColor(245, 245, 245))
    border: QColor = field(default_factory=lambda: QColor(0, 0, 0, 30))


@dataclass(frozen=True)
class SplashLayout:
    """Layout constants for the splash screen."""

    corner_radius: int = 16
    logo_width: int = 400
    padding: int = 16
    text_margins: tuple[int, int, int, int] = (20, 14, 20, 16)
    text_spacing: int = 6
    progress_height: int = 6
    progress_radius: int = 3


@dataclass(frozen=True)
class StatusColors:
    """Colors for file status indicators in the sidebar."""

    pending: QColor = field(default_factory=lambda: QColor(160, 160, 160))  # grey
    reading: QColor = field(default_factory=lambda: QColor(33, 150, 243))  # blue
    ready: QColor = field(default_factory=lambda: QColor(76, 175, 80))  # green
    error: QColor = field(default_factory=lambda: QColor(244, 67, 54))  # red
    saving: QColor = field(default_factory=lambda: QColor(255, 152, 0))  # orange
    saved: QColor = field(default_factory=lambda: QColor(56, 142, 60))  # dark green

    def for_status(self, status: str) -> QColor:
        return getattr(self, status, self.pending)


@dataclass(frozen=True)
class StatusBarColors:
    """Colors for the main window status bar links and separators."""

    separator: str = "#666"
    link: str = "#42a5f5"
    link_hover: str = "#90caf9"
    link_padding: str = "2px 4px"
    background: str = "#222222"


@dataclass(frozen=True)
class BannerColors:
    """Colors for warning/info banners."""

    warning_bg: str = "#4a3f00"
    warning_text: str = "#ffd54f"
    warning_border: str = "#6d5b00"
    warning_padding: int = 8
    warning_radius: int = 4

    hover_bg: str = "#3d3d3d"


@dataclass(frozen=True)
class ProgressColors:
    bg: str = "#3a3a3a"
    chunk: str = "#2196F3"
    text: str = "#ffffff"
    border_radius: int = 6


@dataclass(frozen=True)
class LogColors:
    bg: str = "#1e1e1e"
    text: str = "#d4d4d4"
    border: str = "#444"
    selection: str = "#264f78"
    debug: QColor = field(default_factory=lambda: QColor(140, 140, 140))
    info: QColor = field(default_factory=lambda: QColor(100, 180, 255))
    warning: QColor = field(default_factory=lambda: QColor(255, 210, 60))
    error: QColor = field(default_factory=lambda: QColor(255, 90, 90))

    def for_level(self, level: int) -> QColor:
        return {
            logging.DEBUG: self.debug,
            logging.INFO: self.info,
            logging.WARNING: self.warning,
            logging.ERROR: self.error,
            logging.CRITICAL: self.error,
        }.get(level, self.info)


@dataclass(frozen=True)
class Layout:
    """Standard spacing and margin values used across all widgets."""

    # Margins — (left, top, right, bottom)
    no_margin: tuple[int, int, int, int] = (0, 0, 0, 0)
    panel_margin: tuple[int, int, int, int] = (4, 4, 4, 4)
    header_margin: tuple[int, int, int, int] = (4, 2, 4, 0)
    inner_margin: tuple[int, int, int, int] = (4, 4, 4, 0)
    status_bar_margin: tuple[int, int, int, int] = (4, 0, 4, 0)
    progress_margin: tuple[int, int, int, int] = (0, 0, 0, 4)

    # Spacing between items
    spacing_xs: int = 2
    spacing_sm: int = 4
    spacing_md: int = 8
    spacing_lg: int = 12

    # Form layout
    form_horizontal_spacing: int = 20

    # Widget dimensions
    progress_bar_height: int = 12


@dataclass(frozen=True)
class Theme:
    """Top-level style container. All widgets reference this."""

    fonts: Fonts = field(default_factory=Fonts)
    accent: AccentColors = field(default_factory=AccentColors)
    text: TextColors = field(default_factory=TextColors)
    status: StatusColors = field(default_factory=StatusColors)
    splash: SplashColors = field(default_factory=SplashColors)
    splash_layout: SplashLayout = field(default_factory=SplashLayout)
    status_bar: StatusBarColors = field(default_factory=StatusBarColors)
    banner: BannerColors = field(default_factory=BannerColors)
    progress: ProgressColors = field(default_factory=ProgressColors)
    log: LogColors = field(default_factory=LogColors)
    layout: Layout = field(default_factory=Layout)
    palette_colors: PaletteColors = field(default_factory=PaletteColors)

    def build_palette(self) -> QPalette:
        """Construct a dark QPalette from the palette_colors definitions."""
        p = QPalette()
        pc = self.palette_colors
        p.setColor(QPalette.ColorRole.Window, pc.window)
        p.setColor(QPalette.ColorRole.WindowText, pc.window_text)
        p.setColor(QPalette.ColorRole.Base, pc.base)
        p.setColor(QPalette.ColorRole.AlternateBase, pc.alternate_base)
        p.setColor(QPalette.ColorRole.ToolTipBase, pc.tooltip_base)
        p.setColor(QPalette.ColorRole.ToolTipText, pc.tooltip_text)
        p.setColor(QPalette.ColorRole.Text, pc.text)
        p.setColor(QPalette.ColorRole.Button, pc.button)
        p.setColor(QPalette.ColorRole.ButtonText, pc.button_text)
        p.setColor(QPalette.ColorRole.BrightText, pc.bright_text)
        p.setColor(QPalette.ColorRole.Link, pc.link)
        p.setColor(QPalette.ColorRole.Highlight, pc.highlight)
        p.setColor(QPalette.ColorRole.HighlightedText, pc.highlight_text)
        # Disabled group
        p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, pc.disabled_text)
        p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, pc.disabled_text)
        p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, pc.disabled_text)
        return p

    # -- Composite stylesheets --

    @property
    def progress_bar(self) -> str:
        return (
            f"QProgressBar {{ background: {self.progress.bg}; border: none;"
            f" border-radius: {self.progress.border_radius}px;"
            f" color: {self.progress.text}; text-align: center; }} "
            f"QProgressBar::chunk {{ background: {self.progress.chunk};"
            f" border-radius: {self.progress.border_radius}px; }}"
        )

    @property
    def splash_progress_bar(self) -> str:
        return (
            f"QProgressBar {{ background: {self.splash.progress_bg};"
            f" border: none; border-radius: {self.splash_layout.progress_radius}px; }} "
            f"QProgressBar::chunk {{ background: {self.splash.progress_chunk};"
            f" border-radius: {self.splash_layout.progress_radius}px; }}"
        )

    @property
    def event_log_text(self) -> str:
        return (
            "QPlainTextEdit { "
            f"  font-family: {self.fonts.mono}; font-size: {self.fonts.size_md}; "
            f"  background: {self.log.bg}; color: {self.log.text}; "
            f"  border: 1px solid {self.log.border}; "
            f"  selection-background-color: {self.log.selection}; "
            "}"
        )

    @property
    def preview_list(self) -> str:
        return f"font-family: {self.fonts.mono};"

    @property
    def section_title(self) -> str:
        return "font-weight: bold;"

    @property
    def hint(self) -> str:
        return f"color: {self.text.hint}; padding: {self.layout.spacing_sm}px;"

    @property
    def help_text(self) -> str:
        return f"color: {self.text.hint}; font-size: {self.fonts.size_sm};"

    @property
    def validation_error(self) -> str:
        return f"color: {self.text.error}; font-size: {self.fonts.size_sm};"

    @property
    def log_title(self) -> str:
        return "font-weight: bold; text-align: left; padding: 0;"

    @property
    def log_clear_btn(self) -> str:
        return ""

    @property
    def splash_header(self) -> str:
        return f"color: {self.splash.header}; font-weight: bold; font-size: {self.fonts.size_lg};"

    @property
    def splash_version(self) -> str:
        return f"color: {self.splash.text}; font-size: {self.fonts.size_md};"

    @property
    def splash_status(self) -> str:
        return f"color: {self.splash.text}; font-size: {self.fonts.size_sm};"

    @property
    def warning_banner(self) -> str:
        b = self.banner
        return (
            f"background: {b.warning_bg}; color: {b.warning_text};"
            f" padding: {b.warning_padding}px;"
            f" border: 1px solid {b.warning_border};"
            f" border-radius: {b.warning_radius}px;"
        )

    @property
    def empty_state(self) -> str:
        return f"color: {self.text.muted}; padding: 16px; font-size: {self.fonts.size_lg};"

    @property
    def placeholder(self) -> str:
        return f"color: {self.text.hint}; padding: 16px; font-size: {self.fonts.size_md};"

    @property
    def var_detail_value(self) -> str:
        return f"font-family: {self.fonts.mono};"

    @staticmethod
    def mono_qfont():
        """System fixed-width QFont for use in item-view cells (cached)."""
        from PySide6.QtGui import QFontDatabase

        cache = getattr(Theme, "_mono_qfont_cache", None)
        if cache is None:
            cache = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
            Theme._mono_qfont_cache = cache  # type: ignore[attr-defined]
        return cache

    @property
    def coverage_label(self) -> str:
        return f"padding: 4px; font-size: {self.fonts.size_md};"

    def status_label(self, *, is_error: bool) -> str:
        color = self.text.error if is_error else self.text.success
        return f"color: {color}; font-size: {self.fonts.size_md};"

    @property
    def breadcrumb(self) -> str:
        return (
            "QPushButton { border: none; padding: 1px 3px;"
            f" color: {self.accent.primary}; background: transparent; }}"
            "QPushButton:hover { text-decoration: underline; }"
        )

    @property
    def breadcrumb_separator(self) -> str:
        return f"color: {self.text.muted}; padding: 0 1px;"

    @property
    def breadcrumb_current(self) -> str:
        return "QPushButton { border: none; padding: 1px 3px; font-weight: bold; }"

    @property
    def included_header(self) -> str:
        return f"font-weight: bold; font-size: {self.fonts.size_md};"

    @property
    def summary_edit_btn(self) -> str:
        return f"QPushButton {{ font-size: {self.fonts.size_sm}; padding: 2px 8px; }}"

    @property
    def summary_field_action(self) -> str:
        return (
            "QToolButton { border: none; padding: 1px; }"
            f"QToolButton:hover {{ background: {self.banner.hover_bg}; border-radius: 3px; }}"
        )

    @property
    def status_bar_container(self) -> str:
        sb = self.status_bar
        return (
            f"QStatusBar {{ background: {sb.background}; }}"
            f" QStatusBar::item {{ border: none; }}"
            f" QStatusBar QLabel {{ background: transparent; }}"
        )

    @property
    def status_separator(self) -> str:
        return f"color: {self.status_bar.separator};"

    @property
    def status_link_button(self) -> str:
        sb = self.status_bar
        return (
            f"QPushButton {{ color: {sb.link}; text-decoration: underline;"
            f" border: none; padding: {sb.link_padding}; }}"
            f" QPushButton:hover {{ color: {sb.link_hover}; }}"
        )


# Module-level instance — import this in widgets
theme = Theme()
