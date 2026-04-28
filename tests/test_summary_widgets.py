"""Isolated tests for the summary sub-widgets (display + selector)."""

from __future__ import annotations

import pytest

from mhkit_dolfyn_gui.models.summary_template import SummaryField
from mhkit_dolfyn_gui.services.summary_service import ResolvedRow
from mhkit_dolfyn_gui.widgets.summary import SummaryDisplay, TemplateSelector


@pytest.mark.qt
class TestSummaryDisplay:
    def test_set_rows_distributes_columns(self, qtbot) -> None:
        w = SummaryDisplay()
        qtbot.addWidget(w)
        rows = [
            ResolvedRow(column="left", field=SummaryField(path="a", label="A"), value="1"),
            ResolvedRow(column="left", field=SummaryField(path="b", label="B"), value="2"),
            ResolvedRow(column="right", field=SummaryField(path="c", label="C"), value="3"),
        ]
        w.set_rows(rows)
        assert w.left_form.rowCount() == 2
        assert w.right_form.rowCount() == 1

    def test_clear_empties_both_columns(self, qtbot) -> None:
        w = SummaryDisplay()
        qtbot.addWidget(w)
        w.set_rows([ResolvedRow(column="left", field=SummaryField(path="a", label="A"), value="1")])
        w.clear()
        assert w.left_form.rowCount() == 0
        assert w.right_form.rowCount() == 0

    def test_legacy_summary_left_column_only(self, qtbot) -> None:
        w = SummaryDisplay()
        qtbot.addWidget(w)
        w.set_flat_dict({"Error": "Could not read", "File": "x.vec"})
        assert w.left_form.rowCount() == 2
        assert w.right_form.rowCount() == 0


@pytest.mark.qt
class TestTemplateSelector:
    def test_default_per_file_template_loaded(self, qtbot) -> None:
        w = TemplateSelector(mode="per_file")
        qtbot.addWidget(w)
        assert w.combo.count() >= 1
        assert w.current_template is not None
        assert w.current_template.left or w.current_template.right

    def test_template_changed_signal_emits(self, qtbot) -> None:
        w = TemplateSelector(mode="per_file")
        qtbot.addWidget(w)
        # "Default" + "Nortek Signature" are always bundled — no skip needed.
        assert w.combo.count() >= 2
        with qtbot.waitSignal(w.template_changed, timeout=500):
            w.combo.setCurrentIndex(1 if w.combo.currentIndex() == 0 else 0)
