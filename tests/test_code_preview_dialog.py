"""Tests for the CodePreviewDialog modal."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from PySide6.QtGui import QGuiApplication

from mhkit_dolfyn_gui.widgets.export import CodePreviewDialog

if TYPE_CHECKING:
    from pathlib import Path

    from pytestqt.qtbot import QtBot

SCRIPT = "import mhkit.dolfyn as dolfyn\nprint('hello from generated script')\n"


@pytest.mark.qt
class TestCodePreviewDialog:
    def test_shows_script_text(self, qtbot: QtBot) -> None:
        dialog = CodePreviewDialog(SCRIPT)
        qtbot.addWidget(dialog)
        assert dialog._editor.toPlainText() == SCRIPT
        assert dialog._editor.isReadOnly()

    def test_window_title_and_modal(self, qtbot: QtBot) -> None:
        dialog = CodePreviewDialog(SCRIPT)
        qtbot.addWidget(dialog)
        assert "Export" in dialog.windowTitle()
        assert dialog.isModal()

    def test_copy_button_sets_clipboard(self, qtbot: QtBot) -> None:
        dialog = CodePreviewDialog(SCRIPT)
        qtbot.addWidget(dialog)
        dialog._on_copy()
        clipboard = QGuiApplication.clipboard()
        assert clipboard is not None
        assert clipboard.text() == SCRIPT

    def test_save_as_writes_file(
        self,
        qtbot: QtBot,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        dialog = CodePreviewDialog(SCRIPT)
        qtbot.addWidget(dialog)
        target = tmp_path / "out.py"
        monkeypatch.setattr(
            "mhkit_dolfyn_gui.widgets.export.code_preview_dialog.QFileDialog.getSaveFileName",
            staticmethod(lambda *a, **k: (str(target), "Python files (*.py)")),
        )
        dialog._on_save_as()
        assert target.read_text() == SCRIPT

    def test_save_as_cancel_is_noop(
        self,
        qtbot: QtBot,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """User dismissing the file dialog must not raise or write."""
        dialog = CodePreviewDialog(SCRIPT)
        qtbot.addWidget(dialog)
        monkeypatch.setattr(
            "mhkit_dolfyn_gui.widgets.export.code_preview_dialog.QFileDialog.getSaveFileName",
            staticmethod(lambda *a, **k: ("", "")),
        )
        dialog._on_save_as()  # no exception
        assert list(tmp_path.iterdir()) == []
