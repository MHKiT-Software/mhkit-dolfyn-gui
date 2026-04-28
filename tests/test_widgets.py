"""Smoke tests for widget instantiation."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from mhkit_dolfyn_gui.models.file_item import FileItem, FileStatus
from mhkit_dolfyn_gui.widgets.breadcrumb_bar import BreadcrumbBar
from mhkit_dolfyn_gui.widgets.center_panel import CenterPanel
from mhkit_dolfyn_gui.widgets.combined_overview import CombinedOverview
from mhkit_dolfyn_gui.widgets.dataset_tree import DatasetTree
from mhkit_dolfyn_gui.widgets.export import ExportSidebar
from mhkit_dolfyn_gui.widgets.file_sidebar import FileListPanel, FileSidebar
from mhkit_dolfyn_gui.widgets.file_tree_browser import FileTreeBrowser
from mhkit_dolfyn_gui.widgets.summary import SummaryCard
from mhkit_dolfyn_gui.widgets.variable_detail import VariableDetail


@pytest.mark.qt
class TestWidgetSmoke:
    """Verify widgets can be instantiated without crashing."""

    def test_summary_card(self, qtbot) -> None:
        w = SummaryCard()
        qtbot.addWidget(w)
        w.set_flat_dict({"Key": "Value", "Another": "Data"})
        w.clear()

    def test_summary_card_set_data(self, qtbot, sample_adcp_dataset) -> None:
        w = SummaryCard()
        qtbot.addWidget(w)
        item = FileItem(path=Path("/tmp/test.ad2cp"), dataset=sample_adcp_dataset)
        item.status = FileStatus.READY
        w.set_data(sample_adcp_dataset, item)
        # Both columns should have rows
        assert w._display.left_form.rowCount() > 0
        assert w._display.right_form.rowCount() > 0

    def test_summary_card_template_dropdown(self, qtbot) -> None:
        w = SummaryCard()
        qtbot.addWidget(w)
        assert w.selector.combo.count() >= 1
        assert w.selector.combo.itemText(0) == "Default"

    def test_summary_card_edit_toggle(self, qtbot, sample_adcp_dataset) -> None:
        w = SummaryCard()
        qtbot.addWidget(w)
        item = FileItem(path=Path("/tmp/test.ad2cp"), dataset=sample_adcp_dataset)
        w.set_data(sample_adcp_dataset, item)
        assert not w._editor.editing
        w._edit_btn.click()
        assert w._editor.editing
        assert w._edit_btn.text() == "Done"
        w._edit_btn.click()
        assert not w._editor.editing
        assert w._edit_btn.text() == "Edit"

    def test_dataset_tree(self, qtbot, sample_adcp_dataset) -> None:
        w = DatasetTree()
        qtbot.addWidget(w)
        w.set_dataset(sample_adcp_dataset)
        # Branches: Dimensions, Coordinate Axes, Measurement Variables, Metadata
        assert w.topLevelItemCount() == 4
        w.clear_dataset()
        assert w.topLevelItemCount() == 0

    def test_dataset_tree_branch_names(self, qtbot, sample_adcp_dataset) -> None:
        w = DatasetTree()
        qtbot.addWidget(w)
        w.set_dataset(sample_adcp_dataset)
        branch_names = [w.topLevelItem(i).text(0) for i in range(w.topLevelItemCount())]
        assert branch_names == [
            "Dimensions",
            "Coordinate Axes",
            "Measurement Variables",
            "Metadata",
        ]

    # -- New dashboard widgets --

    def test_breadcrumb_bar(self, qtbot, tmp_path) -> None:
        w = BreadcrumbBar()
        qtbot.addWidget(w)
        path_str = str(tmp_path)
        w.set_path(path_str)
        assert w.current_path() == path_str

    def test_breadcrumb_bar_segments(self, qtbot) -> None:
        w = BreadcrumbBar()
        qtbot.addWidget(w)
        import os

        test_path = os.path.join(os.sep, "Users", "test")
        segments = w._parse_path(test_path)
        assert len(segments) == 3
        assert segments[0][0] in ("/", "\\")  # root separator (platform-dependent)
        assert segments[-1][0] == "test"

    def test_file_tree_browser(self, qtbot) -> None:
        w = FileTreeBrowser()
        qtbot.addWidget(w)
        assert w.current_folder  # Should have a default folder

    def test_file_tree_browser_set_included(self, qtbot) -> None:
        w = FileTreeBrowser()
        qtbot.addWidget(w)
        w.set_included_paths({Path("/tmp/test.vec")})

    def test_file_sidebar(self, qtbot) -> None:
        w = FileSidebar()
        qtbot.addWidget(w)
        assert not w.has_files()
        assert w.checked_indices() == []
        assert w.current_index == -1

    def test_file_sidebar_update_status(self, qtbot) -> None:
        w = FileSidebar()
        qtbot.addWidget(w)
        # Manually add a file item via the inner list panel
        item = FileItem(path=Path("/tmp/test.vec"))
        w._list._file_items.append(item)
        w._list._append_list_item(0)
        w.update_item_status(0, FileStatus.READING)
        assert w.file_items[0].status == FileStatus.READING

    def test_file_list_panel_add_paths_emits(self, qtbot, tmp_path) -> None:
        w = FileListPanel()
        qtbot.addWidget(w)
        added_signals: list = []
        changed_signals: list = []
        w.files_added.connect(added_signals.append)
        w.files_changed.connect(changed_signals.append)
        fake = tmp_path / "x.vec"
        fake.write_bytes(b"")
        w._add_paths([fake])
        assert len(added_signals) == 1
        assert added_signals[0] == [fake]
        assert len(changed_signals) == 1
        assert len(changed_signals[0]) == 1
        # Toggling check state emits check_state_changed
        check_signals: list = []
        w.check_state_changed.connect(lambda i, c: check_signals.append((i, c)))
        w._tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Unchecked)
        assert check_signals == [(0, False)]

    def test_file_sidebar_open_add_dialog_exists(self, qtbot) -> None:
        w = FileSidebar()
        qtbot.addWidget(w)
        assert hasattr(w, "open_add_dialog")
        assert callable(w.open_add_dialog)

    def test_export_sidebar(self, qtbot) -> None:
        w = ExportSidebar()
        qtbot.addWidget(w)
        assert w.pattern_text  # Should have a default pattern from presets

    def test_export_sidebar_pattern_presets(self, qtbot) -> None:
        w = ExportSidebar()
        qtbot.addWidget(w)
        # First preset should be selected by default
        assert w.pattern_text.endswith(".nc")

    def test_center_panel(self, qtbot) -> None:
        w = CenterPanel()
        qtbot.addWidget(w)
        w.clear()

    def test_center_panel_show_file(self, qtbot, sample_adcp_dataset) -> None:
        w = CenterPanel()
        qtbot.addWidget(w)
        item = FileItem(path=Path("/tmp/test.ad2cp"), dataset=sample_adcp_dataset)
        item.status = FileStatus.READY
        w.show_file(item)

    def test_combined_overview(self, qtbot, sample_adcp_dataset) -> None:
        w = CombinedOverview()
        qtbot.addWidget(w)
        item = FileItem(path=Path("/tmp/test.vec"), dataset=sample_adcp_dataset)
        item.status = FileStatus.READY
        w.update_overview([item])

    def test_variable_detail(self, qtbot, sample_adcp_dataset) -> None:
        w = VariableDetail()
        qtbot.addWidget(w)
        var = sample_adcp_dataset.data_vars["vel"]
        w.show_variable("vel", var)
        w.clear()

    def test_variable_detail_time(self, qtbot, sample_adcp_dataset) -> None:
        w = VariableDetail()
        qtbot.addWidget(w)
        time_coord = sample_adcp_dataset.coords["time"]
        w.show_variable("time", time_coord)
