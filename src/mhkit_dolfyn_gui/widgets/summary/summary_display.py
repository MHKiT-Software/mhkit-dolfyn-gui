"""Render-only 2-column key/value grid for the summary card."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QWidget

from mhkit_dolfyn_gui.styles import theme
from mhkit_dolfyn_gui.widgets.elided_label import ElidedLabel

if TYPE_CHECKING:
    from mhkit_dolfyn_gui.models.summary_template import SummaryField
    from mhkit_dolfyn_gui.services.summary_service import ResolvedRow

EditRowFactory = Callable[["SummaryField", QLabel], QWidget]


class SummaryDisplay(QWidget):
    """Two QFormLayouts side by side. No template, dataset, or edit logic.

    Given a list of ``ResolvedRow`` (already-resolved by ``summary_service``),
    lays each row out in its column. An optional ``edit_row_factory`` wraps
    each value label in an action-button row for inline edit mode.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*theme.layout.no_margin)

        self.left_form = QFormLayout()
        self.left_form.setHorizontalSpacing(theme.layout.form_horizontal_spacing)
        self.right_form = QFormLayout()
        self.right_form.setHorizontalSpacing(theme.layout.form_horizontal_spacing)

        layout.addLayout(self.left_form, stretch=1)
        layout.addLayout(self.right_form, stretch=1)

    def set_rows(
        self,
        rows: list[ResolvedRow],
        edit_row_factory: EditRowFactory | None = None,
    ) -> None:
        """Replace displayed fields with *rows*. Each row goes to its column."""
        self.clear()
        forms = {"left": self.left_form, "right": self.right_form}
        for row in rows:
            form = forms[row.column]
            value_label = ElidedLabel(row.value)
            if edit_row_factory is not None:
                form.addRow(f"{row.field.label}:", edit_row_factory(row.field, value_label))
            else:
                form.addRow(f"{row.field.label}:", value_label)

    def set_flat_dict(self, summary: dict[str, str]) -> None:
        """Render a flat dict into the left column only (used for error/cached display)."""
        self.clear()
        for label_text, value_text in summary.items():
            value_label = QLabel(value_text)
            value_label.setTextInteractionFlags(
                value_label.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse
            )
            self.left_form.addRow(f"{label_text}:", value_label)

    def clear(self) -> None:
        """Remove all displayed rows."""
        for form in (self.left_form, self.right_form):
            while form.rowCount() > 0:
                form.removeRow(0)
