"""Combined deployment overview for verifying multi-file ADCP/ADV deployments."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from mhkit_dolfyn_gui.constants import DEFAULT_TIME_GAP_THRESHOLD_SECONDS
from mhkit_dolfyn_gui.services.deployment_service import analyze
from mhkit_dolfyn_gui.styles import theme
from mhkit_dolfyn_gui.unit_conversions import format_duration
from mhkit_dolfyn_gui.widgets.summary import SummaryCard

if TYPE_CHECKING:
    from mhkit_dolfyn_gui.models.file_item import FileItem
    from mhkit_dolfyn_gui.services.deployment_service import DeploymentAnalysis


class CombinedOverview(QWidget):
    """Deployment overview showing time coverage, instrument consistency, and gaps.

    The gap threshold (seconds between consecutive files above which a
    gap is flagged) is configurable: it defaults to the constants.py
    value but the main window updates it from Settings whenever the user
    changes it in the Preferences dialog.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gap_threshold_seconds: float = DEFAULT_TIME_GAP_THRESHOLD_SECONDS
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.layout.no_margin)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        layout.addWidget(scroll)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._content)

        self._placeholder = QLabel("Load files to see deployment overview.")
        self._placeholder.setStyleSheet(theme.placeholder)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._content_layout.addWidget(self._placeholder)

        # Template-driven deployment summary card
        self._summary_card = SummaryCard(mode="combined")
        self._summary_card.hide()
        self._content_layout.addWidget(self._summary_card)

    def set_gap_threshold_seconds(self, value: float) -> None:
        """Update the configured gap threshold and refresh on next render."""
        self._gap_threshold_seconds = value

    def update_overview(self, items: list[FileItem]) -> None:
        """Rebuild the overview from current file items."""
        self._clear()

        analysis = analyze(items, self._gap_threshold_seconds)
        if not analysis.sorted_items:
            self._placeholder.show()
            return
        self._placeholder.hide()

        self._render(analysis)

    def _render(self, analysis: DeploymentAnalysis) -> None:
        # Template-driven deployment summary
        self._summary_card.set_combined_data(list(analysis.sorted_items))
        self._summary_card.show()

        # Per-file time coverage
        coverage_box = QGroupBox("Time Coverage (sorted by start time)")
        cov_layout = QVBoxLayout(coverage_box)
        for row in analysis.coverage:
            duration = format_duration(row.duration) if row.duration is not None else "N/A"
            text = (
                f"<b>{row.item.path.name}</b><br>"
                f"&nbsp;&nbsp;{row.start or 'N/A'} → {row.end or 'N/A'} ({duration})"
            )
            lbl = QLabel(text)
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(theme.coverage_label)
            cov_layout.addWidget(lbl)
        self._content_layout.addWidget(coverage_box)

        if analysis.mismatches or analysis.gaps:
            issues = QGroupBox("Potential Issues")
            issues_layout = QVBoxLayout(issues)
            for m in analysis.mismatches:
                msg = (
                    f"{m.attribute} mismatch: {m.item.path.name} is {m.actual}, "
                    f"expected {m.expected}"
                )
                lbl = QLabel(msg)
                lbl.setWordWrap(True)
                lbl.setStyleSheet(theme.warning_banner)
                issues_layout.addWidget(lbl)
            for g in analysis.gaps:
                if g.delta.total_seconds() < 0:
                    msg = f"Time overlap between {g.before.path.name} and {g.after.path.name}"
                else:
                    msg = (
                        f"Time gap of {format_duration(g.delta)} between "
                        f"{g.before.path.name} and {g.after.path.name}"
                    )
                lbl = QLabel(msg)
                lbl.setWordWrap(True)
                lbl.setStyleSheet(theme.warning_banner)
                issues_layout.addWidget(lbl)
            self._content_layout.addWidget(issues)

        self._content_layout.addStretch()

    def _clear(self) -> None:
        # Remove dynamically-added widgets from the end, keeping placeholder
        # and summary card (the first two persistent widgets).
        _keep = {self._placeholder, self._summary_card}
        for i in range(self._content_layout.count() - 1, -1, -1):
            item = self._content_layout.itemAt(i)
            widget = item.widget() if item else None
            if widget in _keep:
                continue
            self._content_layout.takeAt(i)
            if widget:
                widget.deleteLater()
        self._summary_card.clear()
        self._summary_card.hide()
        self._placeholder.show()
