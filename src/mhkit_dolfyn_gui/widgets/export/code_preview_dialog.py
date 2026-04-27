"""Modal dialog that displays a generated export script.

Read-only preview with Copy and Save As… actions. The caller is
responsible for building the script text via
:func:`mhkit_dolfyn_gui.services.code_generator.generate_export_script`;
this dialog does no code generation of its own.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CodePreviewDialog(QDialog):
    """Show a read-only Python script with Copy / Save As / Close.

    Modal so the user cannot edit the underlying GUI state while
    inspecting the generated script (the script would then silently
    diverge from the current config).
    """

    def __init__(self, script_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._script_text = script_text
        self.setWindowTitle("Export — Generated Script")
        self.setModal(True)
        self.resize(760, 560)

        root = QVBoxLayout(self)

        self._editor = QPlainTextEdit()
        self._editor.setPlainText(script_text)
        self._editor.setReadOnly(True)
        # Monospace font via style-hint so the chosen face gracefully
        # falls back on systems that lack Menlo.
        font = QFont("Menlo")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(11)
        self._editor.setFont(font)
        self._editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        root.addWidget(self._editor, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setToolTip("Copy the script to the clipboard.")
        self._copy_btn.clicked.connect(self._on_copy)
        buttons.addButton(self._copy_btn, QDialogButtonBox.ButtonRole.ActionRole)

        self._save_btn = QPushButton("Save As…")
        self._save_btn.setToolTip("Save the script to a .py file.")
        self._save_btn.clicked.connect(self._on_save_as)
        buttons.addButton(self._save_btn, QDialogButtonBox.ButtonRole.ActionRole)

        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_copy(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._script_text)

    def _on_save_as(self) -> None:
        default = Path.home() / "export_script.py"
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save Script",
            str(default),
            "Python files (*.py);;All Files (*)",
        )
        if not path_str:
            return
        try:
            Path(path_str).write_text(self._script_text)
        except OSError as exc:
            QMessageBox.warning(self, "Save Failed", str(exc))
