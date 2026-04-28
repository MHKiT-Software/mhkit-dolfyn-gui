"""Collapsible reference panel listing supported instrument file types."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QToolButton, QVBoxLayout, QWidget

from mhkit_dolfyn_gui.constants import SUPPORTED_EXTENSIONS, SUPPORTED_INSTRUMENTS
from mhkit_dolfyn_gui.styles import theme


class SupportedFileTypesPanel(QWidget):
    """Collapsible reference: list of extensions when collapsed, instrument
    table when expanded. Starts collapsed.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.layout.no_margin)
        layout.setSpacing(theme.layout.spacing_xs)

        self._toggle = QToolButton()
        self._toggle.setText("Supported File Types")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(False)
        self._toggle.setArrowType(Qt.ArrowType.RightArrow)
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; padding: 2px; text-align: left; }"
        )
        self._toggle.toggled.connect(self._on_toggled)
        layout.addWidget(self._toggle)

        primary = [".ad2cp", ".vec", ".pd0"]
        rest = sorted(e for e in SUPPORTED_EXTENSIONS if e not in primary)
        ordered = [e for e in primary if e in SUPPORTED_EXTENSIONS] + rest
        ext_list = "  ".join(ordered)
        self._collapsed = QLabel(ext_list)
        self._collapsed.setStyleSheet(f"color: {theme.text.body}; padding: 0 4px 4px 18px;")
        self._collapsed.setWordWrap(True)
        layout.addWidget(self._collapsed)

        self._expanded = QLabel(self._build_table_html())
        self._expanded.setTextFormat(Qt.TextFormat.RichText)
        self._expanded.setStyleSheet(f"color: {theme.text.body}; padding: 2px 4px 4px 18px;")
        self._expanded.setVisible(False)
        layout.addWidget(self._expanded)

    def _on_toggled(self, checked: bool) -> None:
        self._toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self._collapsed.setVisible(not checked)
        self._expanded.setVisible(checked)

    @staticmethod
    def _build_table_html() -> str:
        rows = []
        for name, (exts, inst_type) in SUPPORTED_INSTRUMENTS.items():
            ext_str = ", ".join(f"<code>{e}</code>" for e in exts)
            rows.append(
                f"<tr><td><b>{name}</b>&nbsp;&nbsp;</td>"
                f"<td>{ext_str}&nbsp;&nbsp;</td>"
                f"<td>{inst_type}</td></tr>"
            )
        return (
            "<table cellspacing='2'>"
            "<tr><th align='left'>Instrument</th>"
            "<th align='left'>Extensions</th>"
            "<th align='left'>Type</th></tr>"
            f"{''.join(rows)}"
            "</table>"
        )
