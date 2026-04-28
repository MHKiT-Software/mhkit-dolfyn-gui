"""Template dropdown with QSettings persistence."""

from __future__ import annotations

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from mhkit_dolfyn_gui.models.summary_template import (
    SummaryTemplate,
    get_default_combined_template,
    get_default_template,
    list_templates,
    load_template,
)
from mhkit_dolfyn_gui.styles import theme


class TemplateSelector(QWidget):
    """Combo box of bundled + user templates. Persists last selection per mode."""

    template_changed = Signal(object)  # SummaryTemplate

    def __init__(self, mode: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode = mode
        self._settings_key = f"summary/last_template_{mode}"
        self._template: SummaryTemplate = self._default_template()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(*theme.layout.no_margin)
        layout.addWidget(QLabel("Template:"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(120)
        self.combo.currentIndexChanged.connect(self._on_changed)
        layout.addWidget(self.combo)
        layout.addStretch()

        self.refresh()

    @property
    def current_template(self) -> SummaryTemplate:
        return self._template

    def refresh(self) -> None:
        """Re-read templates from disk and restore the last-used selection."""
        self.combo.blockSignals(True)
        self.combo.clear()
        for name, path in list_templates(mode=self._mode):
            self.combo.addItem(name, path)

        default_name = "Default Combined" if self._mode == "combined" else "Default"
        last = QSettings().value(self._settings_key, default_name)
        idx = self.combo.findText(str(last))
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
            self._load_at(idx)
        self.combo.blockSignals(False)

    def select_by_name(self, name: str) -> None:
        idx = self.combo.findText(name)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------

    def _on_changed(self, index: int) -> None:
        if index < 0:
            return
        self._load_at(index)
        QSettings().setValue(self._settings_key, self.combo.currentText())
        self.template_changed.emit(self._template)

    def _load_at(self, index: int) -> None:
        data = self.combo.itemData(index)
        if data is None:
            self._template = self._default_template()
        elif isinstance(data, SummaryTemplate):
            self._template = data
        else:
            try:
                self._template = load_template(data)
            except Exception:
                self._template = self._default_template()

    def _default_template(self) -> SummaryTemplate:
        if self._mode == "combined":
            return get_default_combined_template()
        return get_default_template()
