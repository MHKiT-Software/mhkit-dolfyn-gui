"""Inline edit-mode controller for SummaryCard.

Owns the action-bar buttons (Add Field, Save as Template) and provides a
factory that wraps each value label in move-up / move-down / remove buttons.
Mutates the template held by the parent ``SummaryCard`` and triggers a
re-render via the parent's ``_render`` method.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QToolButton,
    QWidget,
)

from mhkit_dolfyn_gui.models.summary_template import (
    SummaryField,
    SummaryTemplate,
    get_user_templates_dir,
    save_template,
)
from mhkit_dolfyn_gui.styles import theme
from mhkit_dolfyn_gui.widgets.summary.field_picker import FieldPickerDialog

if TYPE_CHECKING:
    from mhkit_dolfyn_gui.widgets.summary.summary_card import SummaryCard


class SummaryEditor:
    """Inline edit-mode controller. Plain helper, not a QWidget."""

    def __init__(self, card: SummaryCard, action_bar: QHBoxLayout) -> None:
        self._card = card
        self.editing = False

        self.add_field_btn = QPushButton("+ Add Field")
        self.add_field_btn.setStyleSheet(theme.summary_edit_btn)
        self.add_field_btn.clicked.connect(self._on_add_field)
        self.add_field_btn.hide()
        action_bar.addWidget(self.add_field_btn)

        self.save_template_btn = QPushButton("Save as Template")
        self.save_template_btn.setStyleSheet(theme.summary_edit_btn)
        self.save_template_btn.clicked.connect(self._on_save_template)
        self.save_template_btn.hide()
        action_bar.addWidget(self.save_template_btn)

    def toggle(self) -> bool:
        self.editing = not self.editing
        self.add_field_btn.setVisible(self.editing)
        self.save_template_btn.setVisible(self.editing)
        return self.editing

    def make_edit_row(self, sf: SummaryField, value_label: QLabel) -> QWidget:
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(*theme.layout.no_margin)
        h.setSpacing(theme.layout.spacing_xs)
        h.addWidget(value_label, stretch=1)

        for icon, tip, slot in (
            ("\u25b2", "Move up", lambda: self._move(sf, -1)),
            ("\u25bc", "Move down", lambda: self._move(sf, 1)),
            ("\u2715", "Remove field", lambda: self._remove(sf)),
        ):
            btn = QToolButton()
            btn.setText(icon)
            btn.setStyleSheet(theme.summary_field_action)
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            h.addWidget(btn)
        return container

    # ------------------------------------------------------------------

    def _move(self, sf: SummaryField, direction: int) -> None:
        tpl = self._card.template
        for col in (tpl.left, tpl.right):
            if sf in col:
                idx = col.index(sf)
                new_idx = idx + direction
                if 0 <= new_idx < len(col):
                    col[idx], col[new_idx] = col[new_idx], col[idx]
                break
        self._card._render()

    def _remove(self, sf: SummaryField) -> None:
        tpl = self._card.template
        for col in (tpl.left, tpl.right):
            if sf in col:
                col.remove(sf)
                break
        self._card._render()

    def _on_add_field(self) -> None:
        ds = self._card.active_dataset()
        if ds is None:
            return
        dlg = FieldPickerDialog(
            ds, include_combined=self._card.mode == "combined", parent=self._card
        )
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.selected_path:
            return
        path = dlg.selected_path
        label = dlg.selected_label or path.split(".")[-1].replace("_", " ").title()
        new_field = SummaryField(path=path, label=label)
        tpl = self._card.template
        if len(tpl.left) <= len(tpl.right):
            tpl.left.append(new_field)
        else:
            tpl.right.append(new_field)
        self._card._render()

    def _on_save_template(self) -> None:
        name, ok = QInputDialog.getText(self._card, "Save Template", "Template name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name)
        path = get_user_templates_dir() / f"{safe_name}.yaml"
        tpl = self._card.template
        template = SummaryTemplate(
            name=name,
            left=list(tpl.left),
            right=list(tpl.right),
            mode=self._card.mode,
        )
        try:
            save_template(template, path)
            self._card.selector.refresh()
            self._card.selector.select_by_name(name)
        except Exception as exc:
            QMessageBox.warning(self._card, "Save Error", f"Could not save template:\n{exc}")
