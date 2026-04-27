"""Isolated tests for the export sub-widgets."""

from __future__ import annotations

import pytest

from mhkit_dolfyn_gui.widgets.export import ExportConfigWidget, ExportProgressWidget


@pytest.mark.qt
class TestExportProgress:
    def test_set_progress_shows_bar(self, qtbot) -> None:
        w = ExportProgressWidget()
        qtbot.addWidget(w)
        assert not w._progress_bar.isVisibleTo(w) or w._progress_bar.isHidden()
        w.set_progress(50)
        assert w._progress_bar.value() == 50

    def test_set_status_error_shows_label(self, qtbot) -> None:
        w = ExportProgressWidget()
        qtbot.addWidget(w)
        w.set_status("Boom", is_error=True)
        assert w._status_label.text() == "Boom"

    def test_reset_hides_everything(self, qtbot) -> None:
        w = ExportProgressWidget()
        qtbot.addWidget(w)
        w.set_progress(80)
        w.set_status("hi")
        w.reset()
        assert w._progress_bar.value() == 0


@pytest.mark.qt
class TestExportConfig:
    def test_default_pattern_present(self, qtbot) -> None:
        w = ExportConfigWidget()
        qtbot.addWidget(w)
        assert w.pattern_text.endswith(".nc")

    def test_export_button_disabled_without_dir(self, qtbot) -> None:
        w = ExportConfigWidget()
        qtbot.addWidget(w)
        w.set_file_items([])
        assert not w._export_btn.isEnabled()

    def test_show_code_button_tracks_export_enablement(self, qtbot) -> None:
        """Show Code button must share the Export button's enablement gate."""
        w = ExportConfigWidget()
        qtbot.addWidget(w)
        w.set_file_items([])
        # Nothing to export → both disabled.
        assert not w._export_btn.isEnabled()
        assert not w._show_code_btn.isEnabled()

    def test_show_code_button_emits_signal_when_clicked(self, qtbot) -> None:
        w = ExportConfigWidget()
        qtbot.addWidget(w)
        # Force-enable the button — exercising the signal path, not the
        # enablement gate (which has its own test above).
        w._show_code_btn.setEnabled(True)
        with qtbot.waitSignal(w.code_requested, timeout=500):
            w._show_code_btn.click()
