"""Thin composer that wires SummaryDisplay + TemplateSelector + SummaryEditor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from mhkit_dolfyn_gui.services.summary_service import resolve_template
from mhkit_dolfyn_gui.styles import theme
from mhkit_dolfyn_gui.widgets.summary.summary_display import SummaryDisplay
from mhkit_dolfyn_gui.widgets.summary.summary_editor import SummaryEditor
from mhkit_dolfyn_gui.widgets.summary.template_selector import TemplateSelector

if TYPE_CHECKING:
    import xarray as xr

    from mhkit_dolfyn_gui.models.file_item import FileItem
    from mhkit_dolfyn_gui.models.summary_template import SummaryTemplate


class SummaryCard(QGroupBox):
    """Configurable 2-column summary backed by templates and a field DSL.

    *mode* is ``"per_file"`` (default) or ``"combined"``.
    """

    def __init__(self, mode: str = "per_file", parent: QWidget | None = None) -> None:
        title = "Deployment Summary" if mode == "combined" else "Dataset Summary"
        super().__init__(title, parent)

        self.mode = mode
        self._ds: xr.Dataset | None = None
        self._file_item: FileItem | None = None
        self._items: list[FileItem] | None = None

        root = QVBoxLayout(self)

        self._display = SummaryDisplay()
        root.addWidget(self._display)

        # Template + edit toggle row
        header = QHBoxLayout()
        header.setContentsMargins(*theme.layout.no_margin)
        self.selector = TemplateSelector(mode)
        header.addWidget(self.selector, stretch=1)
        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setStyleSheet(theme.summary_edit_btn)
        self._edit_btn.clicked.connect(self._toggle_edit_mode)
        header.addWidget(self._edit_btn)
        root.addLayout(header)

        # Edit-mode action bar (buttons hidden until toggled)
        action_bar = QHBoxLayout()
        action_bar.setContentsMargins(0, theme.layout.spacing_sm, 0, 0)
        self._editor = SummaryEditor(self, action_bar)
        action_bar.addStretch()
        root.addLayout(action_bar)

        self._template: SummaryTemplate = self.selector.current_template
        self.selector.template_changed.connect(self._on_template_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def template(self) -> SummaryTemplate:
        return self._template

    def active_dataset(self) -> xr.Dataset | None:
        if self._ds is not None:
            return self._ds
        if self._items:
            return self._items[0].dataset
        return None

    def set_data(
        self,
        ds: xr.Dataset,
        file_item: FileItem,
        template: SummaryTemplate | None = None,
    ) -> None:
        """Resolve all template fields against *ds* and display in 2 columns."""
        self._ds = ds
        self._file_item = file_item
        self._items = None
        if template is not None:
            self._template = template
        self._render()

    def set_combined_data(
        self,
        items: list[FileItem],
        template: SummaryTemplate | None = None,
    ) -> None:
        """Resolve template fields against multiple datasets (combined mode)."""
        self._items = items
        self._ds = items[0].dataset if items else None
        self._file_item = items[0] if items else None
        if template is not None:
            self._template = template
        self._render()

    def set_flat_dict(self, summary: dict[str, str]) -> None:
        """Render a flat dict into the left column only (for error/cached-snapshot display)."""
        self._ds = None
        self._file_item = None
        self._items = None
        self._display.set_flat_dict(summary)

    def clear(self) -> None:
        """Remove all displayed fields."""
        self._ds = None
        self._file_item = None
        self._items = None
        self._display.clear()
        self.setTitle("Summary")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_template_changed(self, template: SummaryTemplate) -> None:
        self._template = template
        if self._ds is not None or self._items:
            self._render()

    def _toggle_edit_mode(self) -> None:
        editing = self._editor.toggle()
        self._edit_btn.setText("Done" if editing else "Edit")
        if self._ds is not None or self._items:
            self._render()

    def _render(self) -> None:
        if self._ds is None and not self._items:
            self._display.clear()
            return
        rows = resolve_template(
            self._template,
            ds=self._ds,
            file_item=self._file_item,
            items=self._items,
        )
        if self._editor.editing:
            self._display.set_rows(rows, edit_row_factory=self._editor.make_edit_row)
        else:
            self._display.set_rows(rows)
